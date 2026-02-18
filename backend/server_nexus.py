"""
RPK NEXUS - Servidor Central Optimizado (SQLite Native)
Arquitectura de alto rendimiento basada en FastAPI y SQLite local.
"""

import os
import sys
import sqlite3
import uvicorn
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# --- CONFIGURACION DE RUTAS ---
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "backend" / "db" / "rpk_industrial.db"
STATIC_DIR = BASE_DIR / "frontend"

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from backend.db.consultor import traducir_a_sql, ejecutar_consulta

app = FastAPI(title="RPK NEXUS API - v2.0")

# Middleware para evitar problemas de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos
class Message(BaseModel):
    text: str

# Auxiliares de Base de Datos
def query_db(query, args=(), one=False):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query, args)
        rv = cur.fetchall()
        conn.close()
        return (rv[0] if rv else None) if one else rv
    except Exception as e:
        print(f"DB Error: {e}")
        return None

# --- ENDPOINTS DE INTERFAZ (UI) ---

@app.get("/")
async def get_index():
    return FileResponse(STATIC_DIR / "ui" / "index.html")

@app.get("/mod/stock")
async def get_stock_mod():
    return FileResponse(STATIC_DIR / "modules" / "stock" / "index.html")

@app.get("/mod/tiempos")
async def get_tiempos_mod():
    path = STATIC_DIR / "modules" / "tiempos" / "index.html"
    if not path.exists():
        path = STATIC_DIR / "modules" / "tiempos" / "ui" / "index.html"
    return FileResponse(path)

@app.get("/mod/simulador")
async def get_simulador_mod():
    path = STATIC_DIR / "modules" / "simulador" / "index.html"
    if not path.exists():
        path = STATIC_DIR / "modules" / "simulador" / "ui" / "index.html"
    return FileResponse(path)

# Montar directorios estáticos
app.mount("/mod", StaticFiles(directory=str(STATIC_DIR / "modules")), name="modules")
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

# --- REDIRECCIONES PARA ACTIVOS RELATIVOS ---
@app.get("/mod/{mod_name}")
async def redirect_to_mod_with_slash(mod_name: str, request: Request):
    if not request.url.path.endswith("/"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=str(request.url).rstrip("/") + "/")
    
    # Si llega aquí con barra, servimos el index correspondiente
    path = STATIC_DIR / "modules" / mod_name / "index.html"
    if not path.exists():
        path = STATIC_DIR / "modules" / mod_name / "ui" / "index.html"
    
    if path.exists():
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Module not found")

# --- ENDPOINTS DE API - COMPATIBILIDAD Y DATOS ---

@app.get("/api/v1/status")
async def get_status():
    try:
        res_stock = query_db("SELECT COUNT(*) as n FROM stock_snapshot", one=True)
        res_tiempos = query_db("SELECT COUNT(*) as n FROM tiempos_carga", one=True)
        return {
            "status": "online",
            "db_path": str(DB_PATH),
            "records": {
                "stock": res_stock['n'] if res_stock else 0,
                "tiempos": res_tiempos['n'] if res_tiempos else 0
            }
        }
    except:
        return {"status": "error", "message": "Database disconnected"}

@app.get("/api/fechas")
async def get_dates(request: Request):
    referer = request.headers.get("referer", "")
    table = "tiempos_carga"
    if "mod/stock" in referer:
        table = "stock_snapshot"
        
    res = query_db(f"SELECT MIN(Fecha) as min, MAX(Fecha) as max FROM {table}", one=True)
    dates = query_db(f"SELECT DISTINCT Fecha FROM {table} ORDER BY Fecha")
    
    if not res or not dates:
        return {"fechas": [], "fecha_min": None, "fecha_max": None}
        
    return {
        "fecha_min": str(res['min']).split(' ')[0], # Limpiar si tiene hora
        "fecha_max": str(res['max']).split(' ')[0],
        "fechas": [str(d['Fecha']).split(' ')[0] for d in dates]
    }

@app.get("/api/summary")
async def get_summary(request: Request, fecha_inicio: str = None, fecha_fin: str = None):
    referer = request.headers.get("referer", "")
    
    # --- LOGICA DE STOCK ---
    if "mod/stock" in referer:
        latest_date = query_db("SELECT MAX(Fecha) FROM stock_snapshot", one=True)[0]
        kpis = query_db("""
            SELECT SUM(Valor_Total) as valor_total, 
                   COUNT(DISTINCT Articulo) as num_items, 
                   COUNT(DISTINCT Cliente) as num_clientes 
            FROM stock_snapshot WHERE Fecha = ?
        """, (latest_date,), one=True)
        evol = query_db("SELECT Fecha, Valor_Total FROM stock_evolucion ORDER BY Fecha")
        top_cust = query_db("""
            SELECT Cliente, SUM(Valor_Total) as Valor_Total 
            FROM stock_snapshot WHERE Fecha = ? 
            GROUP BY Cliente ORDER BY Valor_Total DESC LIMIT 5
        """, (latest_date,))
        top_items = query_db("""
            SELECT Articulo, Descripcion, SUM(Cantidad) as Cantidad, SUM(Valor_Total) as Valor_Total 
            FROM stock_snapshot WHERE Fecha = ? 
            GROUP BY Articulo, Descripcion ORDER BY Valor_Total DESC LIMIT 100
        """, (latest_date,))
        
        return {
            "kpis": dict(kpis) if kpis else {"valor_total": 0, "num_items": 0, "num_clientes": 0},
            "evolucion_total": {
                "fechas": [r['Fecha'] for r in evol],
                "valores": [r['Valor_Total'] for r in evol]
            },
            "top_customers": [dict(r) for r in top_cust],
            "top_items": [dict(r) for r in top_items],
            "ultima_fecha": latest_date
        }
    
    # --- LOGICA DE TIEMPOS ---
    else:
        q = "SELECT Fecha, Centro, Carga_Dia FROM tiempos_carga WHERE 1=1"
        params = []
        if fecha_inicio:
            q += " AND Fecha >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            q += " AND Fecha <= ?"
            params.append(fecha_fin)
            
        data = query_db(q, tuple(params))
        if not data: return {"kpis": {"total_carga": 0, "media_carga": 0, "num_centros": 0}, "rankings": [], "evolucion_total": {"fechas":[], "cargas":[]}, "evolucion_centros": {}}
        
        df = pd.DataFrame([dict(r) for r in data])
        df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d')
        
        num_dias = df['Fecha'].nunique()
        total_carga = df['Carga_Dia'].sum()
        
        evol = df.groupby('Fecha')['Carga_Dia'].sum()
        ranking = df.groupby('Centro')['Carga_Dia'].sum().reset_index().sort_values('Carga_Dia', ascending=False)
        ranking['Media_Diaria'] = ranking['Carga_Dia'] / num_dias
        
        # Evolucion de los Top 5 centros
        top_5_centros = ranking.head(5)['Centro'].tolist()
        evol_centros = {}
        for c in top_5_centros:
            c_data = df[df['Centro'] == c].groupby('Fecha')['Carga_Dia'].sum().reindex(evol.index, fill_value=0)
            evol_centros[str(c)] = {"cargas": c_data.values.tolist()}
            
        return {
            "kpis": {
                "total_carga": round(float(total_carga), 2),
                "media_carga": round(float(total_carga / num_dias), 2) if num_dias > 0 else 0,
                "num_centros": int(df['Centro'].nunique()),
                "num_dias": num_dias
            },
            "evolucion_total": {"fechas": evol.index.tolist(), "cargas": evol.values.tolist()},
            "evolucion_centros": evol_centros,
            "rankings": [{"Centro": str(r['Centro']), "Carga_Total": r['Carga_Dia'], "Media_Diaria": r['Media_Diaria']} for r in ranking.to_dict('records')],
            "ultima_fecha": df['Fecha'].max()
        }

# --- ENDPOINTS ESPECIFICOS DE STOCK ---

@app.get("/api/customers")
async def get_stock_customers():
    latest_date = query_db("SELECT MAX(Fecha) FROM stock_snapshot", one=True)[0]
    custs = query_db("SELECT Cliente, SUM(Valor_Total) as Valor_Total FROM stock_snapshot WHERE Fecha = ? GROUP BY Cliente ORDER BY Valor_Total DESC", (latest_date,))
    return {"customers": [dict(r) for r in custs]}

@app.get("/api/customer/{cliente_id}/items")
async def get_customer_items(cliente_id: str, fecha_inicio: str = None, fecha_fin: str = None):
    latest_date = query_db("SELECT MAX(Fecha) FROM stock_snapshot", one=True)[0]
    
    # Obtener artículos actuales
    items = query_db("""
        SELECT Articulo, Descripcion, Cantidad, Valor_Total, Stock_Objetivo 
        FROM stock_snapshot 
        WHERE Cliente = ? AND Fecha = ? 
        ORDER BY Valor_Total DESC
    """, (cliente_id, latest_date))
    
    # Calcular medias en el rango si se proporcionan
    res_items = []
    for item in items:
        media_q = "SELECT AVG(Cantidad) as media_q, AVG(Valor_Total) as media_v FROM stock_snapshot WHERE Cliente = ? AND Articulo = ?"
        params = [cliente_id, item['Articulo']]
        if fecha_inicio:
            media_q += " AND Fecha >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            media_q += " AND Fecha <= ?"
            params.append(fecha_fin)
            
        m = query_db(media_q, tuple(params), one=True)
        
        d = dict(item)
        d['Media_Cantidad'] = m['media_q'] if m['media_q'] else d['Cantidad']
        d['Media_Valor'] = m['media_v'] if m['media_v'] else d['Valor_Total']
        res_items.append(d)
        
    return {
        "items": res_items, 
        "cliente": cliente_id, 
        "fecha": latest_date,
        "fecha_inicio": fecha_inicio or latest_date
    }

@app.get("/api/item/{item_id}/evolution")
async def get_item_evolution(item_id: str, fecha_inicio: str = None, fecha_fin: str = None):
    q = """
        SELECT Fecha, Cantidad, Valor_Total, Stock_Objetivo, Descripcion 
        FROM stock_snapshot 
        WHERE Articulo = ?
    """
    params = [item_id]
    if fecha_inicio:
        q += " AND Fecha >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        q += " AND Fecha <= ?"
        params.append(fecha_fin)
        
    q += " ORDER BY Fecha"
    
    res = query_db(q, tuple(params))
    if not res:
        return {"fechas": [], "cantidades": [], "valores": [], "stock_objetivo": 0}
    
    return {
        "articulo": item_id,
        "descripcion": res[0]['Descripcion'],
        "fechas": [r['Fecha'] for r in res],
        "cantidades": [r['Cantidad'] for r in res],
        "valores": [r['Valor_Total'] for r in res],
        "stock_objetivo": res[-1]['Stock_Objetivo'] if res[-1]['Stock_Objetivo'] else 0
    }

@app.get("/api/debug/objectives")
async def debug_objectives():
    res = query_db("SELECT Articulo, Stock_Objetivo FROM stock_snapshot WHERE Stock_Objetivo > 0 LIMIT 20")
    return {"objectives_sample": [dict(r) for r in res]}

# --- ENDPOINTS ESPECIFICOS DE TIEMPOS ---

@app.get("/api/centros")
async def get_centros():
    res = query_db("SELECT DISTINCT Centro FROM tiempos_carga ORDER BY Centro")
    return {"centros": [{"id": str(r['Centro'])} for r in res]}

@app.get("/api/centro/{centros_ids}")
async def get_centro_evolution(centros_ids: str, fecha_inicio: str = None, fecha_fin: str = None):
    ids = [c.strip() for c in centros_ids.split(',')]
    placeholders = ','.join(['?'] * len(ids))
    
    q = f"SELECT Fecha, Centro, Carga_Dia FROM tiempos_carga WHERE Centro IN ({placeholders})"
    params = list(ids)
    
    if fecha_inicio:
        q += " AND Fecha >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        q += " AND Fecha <= ?"
        params.append(fecha_fin)
        
    data = query_db(q, tuple(params))
    if not data: return {"fechas": [], "centros": {}}
    
    df = pd.DataFrame([dict(r) for r in data])
    df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d')
    all_dates = sorted(df['Fecha'].unique())
    
    result = {"fechas": all_dates, "centros": {}}
    for cid in ids:
        c_df = df[df['Centro'] == int(cid) if cid.isdigit() else df['Centro'] == cid]
        if not c_df.empty:
            c_evol = c_df.groupby('Fecha')['Carga_Dia'].sum().reindex(all_dates, fill_value=0)
            result["centros"][cid] = {"cargas": c_evol.values.tolist()}
            
    return result

@app.get("/api/centro/{centro_id}/articulos/mes/{mes}")
async def get_centro_articles(centro_id: str, mes: str):
    # Formato mes: YYYY-MM
    q = "SELECT Articulo, OF, Horas, Fecha FROM tiempos_detalle_articulo WHERE Centro = ? AND Fecha LIKE ?"
    data = query_db(q, (centro_id, f"{mes}%"))
    
    if not data: return {"articulos": []}
    
    df = pd.DataFrame([dict(r) for r in data])
    total_horas = df['Horas'].sum()
    
    res = df.groupby(['Articulo', 'OF']).agg({
        'Horas': 'sum',
        'Fecha': 'nunique'
    }).reset_index().rename(columns={'Fecha': 'dias'})
    
    res['porcentaje'] = (res['Horas'] / total_horas * 100).round(1)
    res = res.sort_values('Horas', ascending=False)
    
    return {"articulos": res.to_dict('records')}

# --- ENDPOINTS ASISTENTE ---

@app.post("/api/v1/chat")
async def chat_with_nexus(msg: Message):
    try:
        sql = traducir_a_sql(msg.text)
        resultados, columnas = ejecutar_consulta(sql)
        if not resultados:
            return {"response": "No he encontrado datos. Prueba con 'stock total' o 'carga de trabajo'."}
        resp = f"Resultados:\n" + " | ".join(columnas) + "\n" + "-"*20 + "\n"
        for row in resultados[:3]:
            resp += " | ".join(map(str, row)) + "\n"
        return {"response": resp}
    except Exception as e:
        return {"response": f"Error: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
