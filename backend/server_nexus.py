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
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import duckdb

# --- CONFIGURACION DE RUTAS ---
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "backend" / "db" / "rpk_industrial.db"
DB_ANALYTICAL_PATH = BASE_DIR / "backend" / "db" / "rpk_analytical.duckdb"
STATIC_DIR = BASE_DIR / "frontend"

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from backend.db.consultor import traducir_a_sql, ejecutar_consulta
from backend.db import models_sim
from backend.core import simulation_core
from backend.analytics_core import get_cobertura_global
import json
from sqlalchemy.orm import Session
from backend.api import pdf_stock, pdf_tiempos, pdf_pedidos, pdf_comparativa, pdf_escenario

# Inicializar tablas del simulador
models_sim.init_sim_db()

def get_db_sim():
    db = models_sim.SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

app.include_router(pdf_stock.router, prefix="/api", tags=["reports"])
app.include_router(pdf_tiempos.router, prefix="/api", tags=["reports"])
app.include_router(pdf_pedidos.router, prefix="/api", tags=["reports"])
app.include_router(pdf_comparativa.router, prefix="/api", tags=["reports"])
app.include_router(pdf_escenario.router, prefix="/api", tags=["reports"])

# Modelos para el Simulador
class OverrideBase(BaseModel):
    articulo: str
    centro: str
    oee_override: Optional[float] = None
    ppm_override: Optional[float] = None
    demanda_override: Optional[float] = None
    new_centro: Optional[str] = None
    horas_turno_override: Optional[int] = None
    setup_time_override: Optional[float] = None
    personnel_ratio_override: Optional[float] = None

class ScenarioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    dias_laborales: Optional[int] = 238
    horas_turno_global: Optional[int] = 16
    center_configs: Optional[dict] = {}
    overrides: List[OverrideBase] = []

class ScenarioResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    dias_laborales: int
    horas_turno_global: int
    center_configs_json: Optional[str] = None
    
    class Config:
        from_attributes = True

class HistoryResponse(BaseModel):
    id: int
    timestamp: str
    name: str
    changes_count: int
    details_snapshot: Optional[str] = None

from typing import List, Optional, Union, Any

class PreviewPayload(BaseModel):
    overrides: List[OverrideBase]
    dias_laborales: Optional[int] = None
    horas_turno: Optional[int] = None
    center_configs: Optional[dict] = None

class ComparisonSimulatePayload(BaseModel):
    base_scenario_id: Optional[Any] = None
    overrides: List[OverrideBase] = []
    center_configs: Optional[dict] = {}
    config: Optional[dict] = {}

class ArticleCreate(BaseModel):
    articulo: str
    centro: str
    volumen_anual: float = 0
    piezas_por_minuto: float = 0
    oee: float = 0.75
    dias_laborales: float = 238

class ArticleDelete(BaseModel):
    articulo: str
    centro: str

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

def query_duckdb(query, args=(), one=False):
    """
    Carril B (Analítico): Consultas vectorizadas sobre Data Lakehouse (Parquet/DuckDB)
    Graceful Degradation: si no hay base de datos, envía flag de error en vez de crashear.
    """
    try:
        if not DB_ANALYTICAL_PATH.exists():
            print("[WARN] Base de datos analítica no encontrada. Degradación activa.")
            return {"warning": "Using stale data"} if one else []
            
        with duckdb.connect(str(DB_ANALYTICAL_PATH), read_only=True) as conn:
            if args:
                res = conn.execute(query, args).fetchall()
            else:
                res = conn.execute(query).fetchall()
                
            cols = [x[0] for x in conn.description]
            rv = [dict(zip(cols, row)) for row in res]
            
            return (rv[0] if rv else None) if one else rv
    except Exception as e:
        print(f"DuckDB Error: {e}")
        return None

# --- ENDPOINT PARQUET PARA DUCKDB WASM (Frontend V6) ---
DATA_LAKE_DIR = BASE_DIR / "backend" / "data_lake"

PARQUET_TABLE_MAP = {
    "existencias": {"maestro": "maestros/existencias.parquet", "transaccional": "transaccional/existencias"},
    "carga_centros": {"maestro": "maestros/carga_centros.parquet", "transaccional": "transaccional/carga_centros"},
    "pedidos": {"transaccional": "transaccional/pedidos"},
    "albaranes": {"transaccional": "transaccional/albaranes"},
    "carga_detalle": {"transaccional": "transaccional/carga_detalle"},
}

def _find_latest_parquet(table_name: str) -> Path:
    """Busca el Parquet más reciente para una tabla dada."""
    config = PARQUET_TABLE_MAP.get(table_name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Tabla '{table_name}' no encontrada")
    
    # Primero intentar maestro (snapshot actual)
    if "maestro" in config:
        maestro_path = DATA_LAKE_DIR / config["maestro"]
        if maestro_path.exists():
            return maestro_path
    
    # Fallback a transaccional (más reciente)
    if "transaccional" in config:
        trans_dir = DATA_LAKE_DIR / config["transaccional"]
        if trans_dir.exists():
            all_parquets = sorted(trans_dir.rglob("*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True)
            if all_parquets:
                return all_parquets[0]
    
    raise HTTPException(status_code=404, detail=f"Sin datos para '{table_name}'")

@app.get("/api/parquet/{table_name}")
async def serve_parquet(table_name: str):
    """Sirve el Parquet más reciente de una tabla para DuckDB WASM."""
    path = _find_latest_parquet(table_name)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        headers={"Cache-Control": "public, max-age=300"}
    )

# --- ENDPOINTS DE INTERFAZ (UI) ---

@app.get("/")
@app.get("/portal")
async def get_index():
    path = STATIC_DIR / "ui" / "index.html"
    print(f"[DEBUG] Sirviendo Portal desde: {path.absolute()}")
    return FileResponse(path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

# --- REDIRECCIONES Y SERVICIO DE MÓDULOS ---

@app.get("/mod/{mod_name}")
@app.get("/mod/{mod_name}/")
async def get_module_index(mod_name: str, request: Request):
    # 1. Si es un archivo directo (con extensión), servirlo si existe
    if "." in mod_name:
        for p in [STATIC_DIR / "assets" / mod_name, STATIC_DIR / "modules" / mod_name]:
            if p.exists(): return FileResponse(p)
        raise HTTPException(status_code=404)

    # 2. Verificar directorio
    mod_path = STATIC_DIR / "modules" / mod_name
    if not mod_path.is_dir():
        raise HTTPException(status_code=404)

    # 3. FORZAR barra al final (Crucial para CSS relativo)
    if not request.url.path.endswith("/"):
        return RedirectResponse(url=f"/mod/{mod_name}/")
    
    # 4. Servir index.html de la raíz del módulo
    path = mod_path / "index.html"
    if not path.exists():
        return JSONResponse({"error": f"Modulo {mod_name} sin index.html"}, status_code=404)
            
    print(f"[DEBUG] OK: Sirviendo {mod_name} desde {path}")
    return FileResponse(path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

# Montar directorios estáticos
app.mount("/mod", StaticFiles(directory=str(STATIC_DIR / "modules")), name="modules")
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="legacy_static")

# --- ENDPOINTS DE API - COMPATIBILIDAD Y DATOS ---

@app.get("/api/v1/status")
@app.get("/api/status")
async def get_status(request: Request):
    try:
        res_stock = query_db("SELECT COUNT(*) as n FROM stock_snapshot", one=True)
        res_tiempos = query_db("SELECT COUNT(*) as n FROM tiempos_carga", one=True)
        return {
            "status": "online",
            "db_path": str(DB_PATH),
            "records": {
                "stock": res_stock['n'] if res_stock else 0,
                "tiempos": res_tiempos['n'] if res_tiempos else 0
            },
            "database": "rpk_industrial.db"
        }
    except:
        return {"status": "error", "message": "Database disconnected"}

class ChatRequest(BaseModel):
    text: str

@app.post("/api/v1/chat")
async def post_chat(req: ChatRequest):
    try:
        pregunta = req.text
        sql = traducir_a_sql(pregunta)
        resultados, columnas = ejecutar_consulta(sql)
        
        if not resultados:
            return {"response": "No encontré datos específicos sobre eso. Prueba preguntando por 'stock total' o 'carga de trabajo'."}
            
        # Formatear respuesta amigable
        respuesta = f"He consultado la base de datos NEXUS.\n\n"
        if len(resultados) == 1:
            row = dict(zip(columnas, resultados[0]))
            detalles = "\n".join([f"- **{k}**: {v}" for k, v in row.items()])
            respuesta += f"Los datos que he encontrado son:\n{detalles}"
        else:
            respuesta += f"He encontrado {len(resultados)} registros que coinciden. Aquí tienes los primeros 5:\n"
            for r in resultados[:5]:
                respuesta += f"- {dict(zip(columnas, r))}\n"
                
        return {"response": respuesta}
    except Exception as e:
        return {"response": f"Lo siento, Ismael. Ha ocurrido un error al procesar tu consulta: {str(e)}"}

@app.get("/api/v1/hub_stats")
async def get_hub_stats():
    try:
        # 1. Stock Total
        res_stock = query_duckdb("SELECT SUM(Cantidad) as total, COUNT(DISTINCT Articulo) as items FROM existencias", one=True)
        
        # 2. Saturation Media (Tiempos)
        res_sat = query_duckdb("""
            SELECT AVG(Carga_Dia / 16.0) as sat_avg 
            FROM carga_centros
            WHERE Centro NOT LIKE '9%' 
            AND TRY_CAST(Fecha AS DATE) > current_date() - INTERVAL 30 DAY
        """, one=True)
        
        # 3. Cobertura (Analítica Core) - Mantenemos como está o delegamos
        cobertura = get_cobertura_global()
        
        return {
            "stock": {
                "total": int(res_stock['total'] or 0) if res_stock and 'total' in res_stock else 0,
                "items": int(res_stock['items'] or 0) if res_stock and 'items' in res_stock else 0
            },
            "saturation": round(float(res_sat.get('sat_avg', 0.74) if res_sat else 0.74) * 100, 1),
            "cobertura": cobertura.get("dias_cobertura_teorica", 12.4),
            "warning": res_stock.get('warning') if isinstance(res_stock, dict) else None
        }
    except Exception as e:
        print(f"Hub Stats Error: {e}")
        return {
            "stock": {"total": 0, "items": 0},
            "saturation": 74.0,
            "cobertura": 12.4,
            "error": str(e)
        }

@app.get("/api/fechas")
async def get_dates(request: Request):
    referer = request.headers.get("referer", "")
    table = "carga_centros"
    if "mod/stock" in referer:
        table = "existencias"
    elif "mod/albaranes" in referer:
        table = "albaranes"
        
    res = query_duckdb(f"SELECT MIN(Fecha_Albaran) as min, MAX(Fecha_Albaran) as max FROM {table}" if table == "albaranes" else f"SELECT MIN(Fecha) as min, MAX(Fecha) as max FROM {table}", one=True)
    dates = query_duckdb(f"SELECT DISTINCT Fecha_Albaran as Fecha FROM {table} ORDER BY Fecha_Albaran" if table == "albaranes" else f"SELECT DISTINCT Fecha FROM {table} ORDER BY Fecha")
    
    if not res or not dates or 'warning' in res:
        return {"fechas": [], "fecha_min": None, "fecha_max": None, "warning": "Using stale data"}
        
    return {
        "fecha_min": str(res['min']).split(' ')[0], 
        "fecha_max": str(res['max']).split(' ')[0],
        "fechas": [str(d['Fecha']).split(' ')[0] for d in dates]
    }

@app.get("/api/summary")
async def get_summary(request: Request, fecha_inicio: str = None, fecha_fin: str = None):
    referer = request.headers.get("referer", "")
    
    # --- LOGICA DE STOCK ---
    if "mod/stock" in referer:
        latest = query_duckdb("SELECT MAX(Fecha) as f FROM existencias", one=True)
        if not latest or 'warning' in latest:
            return {"kpis": {"valor_total": 0, "num_items": 0, "num_clientes": 0}, "top_customers": [], "top_items": [], "ultima_fecha": None, "warning": "Using stale data"}
        
        latest_available_date = latest['f']
        actual_latest = fecha_fin if fecha_fin else latest_available_date
        
        # Filtros para evolución
        evol_query = "SELECT Fecha, SUM(Valor_Total) as Valor_Total FROM existencias WHERE 1=1"
        evol_params = []
        if fecha_inicio:
            evol_query += " AND Fecha >= ?"
            evol_params.append(fecha_inicio)
        if fecha_fin:
            evol_query += " AND Fecha <= ?"
            evol_params.append(fecha_fin)
        evol_query += " GROUP BY Fecha ORDER BY Fecha"
        
        evol = query_duckdb(evol_query, tuple(evol_params))
        
        kpis = query_duckdb("""
            SELECT SUM(Valor_Total) as valor_total, 
                   COUNT(DISTINCT Articulo) as num_items, 
                   COUNT(DISTINCT Cliente) as num_clientes 
            FROM existencias WHERE Fecha = ?
        """, (actual_latest,), one=True)

        top_cust = query_duckdb("""
            SELECT Cliente, SUM(Valor_Total) as Valor_Total 
            FROM existencias WHERE Fecha = ? 
            GROUP BY Cliente ORDER BY Valor_Total DESC LIMIT 5
        """, (actual_latest,))
        
        top_items = query_duckdb("""
            SELECT Articulo, Descripcion, SUM(Cantidad) as Cantidad, SUM(Valor_Total) as Valor_Total, MAX(Stock_Objetivo) as Stock_Objetivo
            FROM existencias WHERE Fecha = ? 
            GROUP BY Articulo, Descripcion ORDER BY Valor_Total DESC LIMIT 100
        """, (actual_latest,))
        
        return {
            "kpis": dict(kpis) if kpis else {"valor_total": 0, "num_items": 0, "num_clientes": 0},
            "evolucion_total": {
                "fechas": [str(r['Fecha']) for r in evol] if evol else [],
                "valores": [r['Valor_Total'] for r in evol] if evol else []
            },
            "top_customers": [dict(r) for r in top_cust] if top_cust else [],
            "top_items": [dict(r) for r in top_items] if top_items else [],
            "ultima_fecha": str(actual_latest)
        }
    
    # --- LOGICA DE TIEMPOS ---
    else:
        q = "SELECT Fecha, Centro, Carga_Dia FROM carga_centros WHERE Centro NOT LIKE '9%'"
        params = []
        if fecha_inicio:
            q += " AND Fecha >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            q += " AND Fecha <= ?"
            params.append(fecha_fin)
            
        data = query_duckdb(q, tuple(params))
        if not data or (isinstance(data, dict) and 'warning' in data): 
            return {"kpis": {"total_carga": 0, "media_carga": 0, "num_centros": 0}, "rankings": [], "evolucion_total": {"fechas":[], "cargas":[]}, "evolucion_centros": {}, "warning": "Using stale data"}
        
        df = pd.DataFrame(data)
        df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d')
        
        num_dias = df['Fecha'].nunique()
        total_carga = df['Carga_Dia'].sum()
        
        evol = df.groupby('Fecha')['Carga_Dia'].sum().sort_index()
        
        ranking = df.groupby('Centro')['Carga_Dia'].sum().reset_index().sort_values('Carga_Dia', ascending=False)
        ranking['Media_Diaria'] = ranking['Carga_Dia'] / (num_dias if num_dias > 0 else 1)
        
        top_5_centros = ranking.head(5)['Centro'].tolist()
        evol_centros = {}
        for c in top_5_centros:
            c_data = df[df['Centro'] == c].groupby('Fecha')['Carga_Dia'].sum().reindex(evol.index, fill_value=0)
            evol_centros[str(c)] = {
                "fechas": evol.index.tolist(),
                "cargas": c_data.values.tolist()
            }
            
        return {
            "kpis": {
                "total_carga": round(float(total_carga), 2),
                "media_carga": round(float(total_carga / num_dias), 2) if num_dias > 0 else 0,
                "num_centros": int(df['Centro'].nunique()),
                "num_dias": num_dias
            },
            "evolucion_total": {"fechas": evol.index.tolist(), "cargas": evol.values.tolist()},
            "evolucion_centros": evol_centros,
            "rankings": [{"Centro": str(r['Centro']), "Carga_Total": round(r['Carga_Dia'], 2), "Media_Diaria": round(r['Media_Diaria'], 2)} for r in ranking.to_dict('records')],
            "ultima_fecha": df['Fecha'].max()
        }

# --- ENDPOINTS ESPECIFICOS DE STOCK ---

@app.get("/api/customers")
async def get_stock_customers():
    latest = query_duckdb("SELECT MAX(Fecha) as f FROM existencias", one=True)
    if not latest or 'warning' in latest:
        return {"customers": [], "warning": "Using stale data"}
    latest_date = latest['f']
    custs = query_duckdb("SELECT Cliente, SUM(Valor_Total) as Valor_Total FROM existencias WHERE Fecha = ? GROUP BY Cliente ORDER BY Valor_Total DESC", (latest_date,))
    return {"customers": [dict(r) for r in custs]}

@app.get("/api/customer/{cliente_id}/items")
async def get_customer_items(cliente_id: str, fecha_inicio: str = None, fecha_fin: str = None):
    latest = query_duckdb("SELECT MAX(Fecha) as f FROM existencias", one=True)
    if not latest or 'warning' in latest:
        return {"items": [], "cliente": cliente_id, "warning": "Using stale data"}
    latest_date = latest['f']
    
    items = query_duckdb("""
        SELECT Articulo, Descripcion, Cantidad, Valor_Total, Stock_Objetivo 
        FROM existencias 
        WHERE Cliente = ? AND Fecha = ? 
        ORDER BY Valor_Total DESC
    """, (cliente_id, latest_date))
    
    res_items = []
    for item in items:
        media_q = "SELECT AVG(Cantidad) as media_q, AVG(Valor_Total) as media_v FROM existencias WHERE Cliente = ? AND Articulo = ?"
        params = [cliente_id, item['Articulo']]
        if fecha_inicio:
            media_q += " AND Fecha >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            media_q += " AND Fecha <= ?"
            params.append(fecha_fin)
            
        m = query_duckdb(media_q, tuple(params), one=True)
        
        d = dict(item)
        d['Media_Cantidad'] = m['media_q'] if m['media_q'] else d['Cantidad']
        d['Media_Valor'] = m['media_v'] if m['media_v'] else d['Valor_Total']
        res_items.append(d)
        
    return {
        "items": res_items, 
        "cliente": cliente_id, 
        "fecha": str(latest_date),
        "fecha_inicio": fecha_inicio or str(latest_date)
    }

@app.get("/api/item/{item_id}/evolution")
async def get_item_evolution(item_id: str, fecha_inicio: str = None, fecha_fin: str = None):
    q = """
        SELECT Fecha, Cantidad, Valor_Total, Stock_Objetivo, Descripcion 
        FROM existencias 
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
    
    res = query_duckdb(q, tuple(params))
    if not res or (isinstance(res, dict) and 'warning' in res):
        return {"fechas": [], "cantidades": [], "valores": [], "stock_objetivo": 0}
    
    return {
        "articulo": item_id,
        "descripcion": res[0]['Descripcion'],
        "fechas": [str(r['Fecha']) for r in res],
        "cantidades": [r['Cantidad'] for r in res],
        "valores": [r['Valor_Total'] for r in res],
        "stock_objetivo": res[-1]['Stock_Objetivo'] if res[-1]['Stock_Objetivo'] else 0
    }

@app.get("/api/debug/objectives")
async def debug_objectives():
    res = query_duckdb("SELECT Articulo, Stock_Objetivo FROM existencias WHERE Stock_Objetivo > 0 LIMIT 20")
    if isinstance(res, dict) and 'warning' in res: return {"objectives_sample": []}
    return {"objectives_sample": [dict(r) for r in res]}

# --- ENDPOINTS ESPECIFICOS DE TIEMPOS ---

@app.get("/api/centros")
async def get_centros():
    res = query_duckdb("SELECT DISTINCT Centro FROM carga_centros ORDER BY Centro")
    if isinstance(res, dict) and 'warning' in res: return {"centros": []}
    return {"centros": [{"id": str(r['Centro'])} for r in res]}

@app.get("/api/centro/{centros_ids}")
async def get_centro_evolution(centros_ids: str, fecha_inicio: str = None, fecha_fin: str = None):
    ids = [c.strip() for c in centros_ids.split(',')]
    placeholders = ','.join(['?'] * len(ids))
    
    q = f"SELECT Fecha, Centro, Carga_Dia FROM carga_centros WHERE Centro IN ({placeholders})"
    params = list(ids)
    
    if fecha_inicio:
        q += " AND Fecha >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        q += " AND Fecha <= ?"
        params.append(fecha_fin)
        
    data = query_duckdb(q, tuple(params))
    if not data or (isinstance(data, dict) and 'warning' in data): return {"fechas": [], "centros": {}}
    
    df = pd.DataFrame(data)
    df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d')
    all_dates = sorted(df['Fecha'].unique())
    
    result = {"fechas": all_dates, "centros": {}}
    for cid in ids:
        c_df = df[df['Centro'].astype(str) == str(cid)]
        if not c_df.empty:
            c_evol = c_df.groupby('Fecha')['Carga_Dia'].sum().reindex(all_dates, fill_value=0)
            result["centros"][cid] = {"cargas": c_evol.values.tolist()}
            
    return result

@app.get("/api/centro/{centro_id}/articulos/mes/{mes}")
async def get_centro_articles(centro_id: str, mes: str):
    q = "SELECT Articulo, OF, Horas_Final, Horas_Pte_Val, Fecha FROM tiempos_detalle_articulo WHERE Centro = ? AND CAST(Fecha AS VARCHAR) LIKE ?"
    data = query_duckdb(q, (centro_id, f"{mes}%"))
    
    if not data or (isinstance(data, dict) and 'warning' in data): return {"articulos": []}
    
    df = pd.DataFrame(data)
    total_horas = df['Horas_Final'].sum()
    
    res = df.groupby(['Articulo', 'OF']).agg({
        'Horas_Final': 'sum',
        'Horas_Pte_Val': 'max',
        'Fecha': 'nunique'
    }).reset_index().rename(columns={'Fecha': 'dias'})
    
    res['porcentaje'] = (res['Horas_Final'] / total_horas * 100).round(1)
    res = res.sort_values('Horas_Final', ascending=False)
    
    final_data = []
    for r in res.to_dict('records'):
        final_data.append({
            "articulo": str(r['Articulo']),
            "of": str(r['OF']),
            "horas": float(r['Horas_Pte_Val']),
            "dias": int(r['dias']),
            "porcentaje": float(r['porcentaje'])
        })
    
    return {"articulos": final_data}
    
# --- ENDPOINTS PEDIDOS DE VENTA ---

@app.get("/api/pedidos/summary")
async def get_pedidos_summary(fecha_inicio: str = None, fecha_fin: str = None):
    # Obtener el rango de fechas si no se proporciona
    if not fecha_inicio or not fecha_fin:
        dates = query_duckdb("SELECT DISTINCT Fecha_Snapshot FROM pedidos ORDER BY Fecha_Snapshot DESC LIMIT 30")
        if not dates or (isinstance(dates, dict) and 'warning' in dates): return {"kpis": {}, "evolucion": [], "ultima_fecha": None, "warning": "Using stale data"}
        dates_list = [str(r['Fecha_Snapshot']) for r in dates]
        actual_latest = dates_list[0]
        fecha_inicio = dates_list[-1]
        fecha_fin = actual_latest
    else:
        actual_latest = query_duckdb("SELECT MAX(Fecha_Snapshot) as f FROM pedidos", one=True)['f']

    # KPIs de la última fecha
    latest_data = query_duckdb("SELECT SUM(Cant_Pendiente) as total_qty, SUM(Importe_EUR) as total_val FROM pedidos WHERE Fecha_Snapshot = ?", (actual_latest,), one=True)
    
    # Evolución
    evol = query_duckdb("SELECT Fecha_Snapshot as fecha, SUM(Cant_Pendiente) as qty, SUM(Importe_EUR) as val FROM pedidos WHERE Fecha_Snapshot BETWEEN ? AND ? GROUP BY Fecha_Snapshot ORDER BY Fecha_Snapshot", (fecha_inicio, fecha_fin))
    
    num_refs = query_duckdb("SELECT COUNT(DISTINCT Articulo) as c FROM pedidos WHERE Fecha_Snapshot = ?", (actual_latest,), one=True)
    
    return {
        "kpis": {
            "total_piezas": round(float(latest_data['total_qty'] or 0), 0) if latest_data else 0,
            "total_importe": round(float(latest_data['total_val'] or 0), 2) if latest_data else 0,
            "num_referencias": int(num_refs['c'] if num_refs else 0)
        },
        "evolucion": {
            "fechas": [str(r['fecha']) for r in evol] if evol else [],
            "cantidades": [r['qty'] for r in evol] if evol else [],
            "importes": [r['val'] for r in evol] if evol else []
        },
        "ultima_fecha": str(actual_latest)
    }

@app.get("/api/pedidos/articulos")
async def get_pedidos_articulos(fecha: str = None):
    if not fecha:
        latest = query_duckdb("SELECT MAX(Fecha_Snapshot) as f FROM pedidos", one=True)
        if not latest or 'warning' in latest: return {"articulos": []}
        fecha = latest['f']
    
    data = query_duckdb("SELECT Articulo, Referencia, SUM(Cant_Pendiente) as qty, SUM(Importe_EUR) as val FROM pedidos WHERE Fecha_Snapshot = ? GROUP BY Articulo, Referencia ORDER BY val DESC LIMIT 50", (fecha,))
    if isinstance(data, dict) and 'warning' in data: return {"articulos": []}
    
    return {
        "articulos": [
            {
                "articulo": str(r['Articulo']),
                "referencia": str(r['Referencia']),
                "cantidad": float(r['qty']),
                "importe": float(r['val'])
            } for r in data
        ]
    }

# --- ENDPOINTS DEL SIMULADOR (CLASSIC V1 INTEGRATION) ---

@app.get("/api/scenarios", response_model=List[ScenarioResponse])
def list_scenarios(db: Session = Depends(get_db_sim)):
    return db.query(models_sim.Scenario).all()

@app.get("/api/scenarios/{scenario_id}/history", response_model=List[HistoryResponse])
def get_scenario_history(scenario_id: int, db: Session = Depends(get_db_sim)):
    db_scenario = db.query(models_sim.Scenario).filter(models_sim.Scenario.id == scenario_id).first()
    if not db_scenario:
        return []
        
    hist = db.query(models_sim.ScenarioHistory).filter(
        models_sim.ScenarioHistory.scenario_id == scenario_id,
        models_sim.ScenarioHistory.name == db_scenario.name
    ).order_by(models_sim.ScenarioHistory.timestamp.desc()).all()
    
    return [{
        "id": h.id,
        "timestamp": h.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "name": h.name,
        "changes_count": h.changes_count,
        "details_snapshot": h.details_snapshot
    } for h in hist]

@app.post("/api/scenarios", response_model=ScenarioResponse)
def create_scenario(scenario_data: ScenarioCreate, db: Session = Depends(get_db_sim)):
    existing = db.query(models_sim.Scenario).filter(models_sim.Scenario.name == scenario_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un escenario con el nombre '{scenario_data.name}'.")

    db_scenario = models_sim.Scenario(
        name=scenario_data.name, 
        description=scenario_data.description,
        dias_laborales=scenario_data.dias_laborales,
        horas_turno_global=scenario_data.horas_turno_global,
        center_configs_json=json.dumps(scenario_data.center_configs)
    )
    db.add(db_scenario)
    db.commit()
    db.refresh(db_scenario)
    
    # Bugfix: si SQLite reusa un ID de un escenario borrado previamente, 
    # eliminamos restos huérfanos que hubieran podido quedar.
    db.query(models_sim.ScenarioDetail).filter(models_sim.ScenarioDetail.scenario_id == db_scenario.id).delete()
    db.query(models_sim.ScenarioHistory).filter(models_sim.ScenarioHistory.scenario_id == db_scenario.id).delete()
    
    for ov in scenario_data.overrides:
        db_ov = models_sim.ScenarioDetail(
            scenario_id=db_scenario.id,
            articulo=ov.articulo,
            centro=ov.centro,
            oee_override=ov.oee_override,
            ppm_override=ov.ppm_override,
            demanda_override=ov.demanda_override,
            new_centro=ov.new_centro,
            horas_turno_override=ov.horas_turno_override,
            personnel_ratio_override=ov.personnel_ratio_override,
            setup_time_override=ov.setup_time_override
        )
        db.add(db_ov)
    
    db.commit()
    
    history_entry = models_sim.ScenarioHistory(
        scenario_id=db_scenario.id,
        name=db_scenario.name,
        changes_count=len(scenario_data.overrides),
        details_snapshot=json.dumps([ov.dict() for ov in scenario_data.overrides])
    )
    db.add(history_entry)
    db.commit()
    
    return db_scenario

@app.get("/api/simulate/base")
async def get_base_simulation(db: Session = Depends(get_db_sim), dias_laborales: Optional[int] = None, horas_turno: Optional[int] = None, use_actual: bool = False):
    try:
        return simulation_core.get_simulation_data(db, dias_laborales=dias_laborales, horas_turno=horas_turno, use_actual=use_actual)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/simulate/{scenario_id}")
async def get_scenario_simulation(scenario_id: int, db: Session = Depends(get_db_sim), dias_laborales: Optional[int] = None, horas_turno: Optional[int] = None, use_actual: bool = False):
    try:
        db_sc = db.query(models_sim.Scenario).filter(models_sim.Scenario.id == scenario_id).first()
        if not db_sc:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        d_lab = dias_laborales if dias_laborales is not None else db_sc.dias_laborales
        h_tur = horas_turno if horas_turno is not None else db_sc.horas_turno_global
        c_conf = json.loads(db_sc.center_configs_json) if db_sc.center_configs_json else {}

        return simulation_core.get_simulation_data(
            db, 
            scenario_id, 
            dias_laborales=d_lab, 
            horas_turno=h_tur, 
            center_configs=c_conf,
            use_actual=use_actual
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simulate/preview")
async def get_preview_simulation(payload: PreviewPayload, db: Session = Depends(get_db_sim), use_actual: bool = False):
    try:
        return simulation_core.get_simulation_data(
            db, 
            overrides_list=payload.overrides, 
            dias_laborales=payload.dias_laborales,
            horas_turno=payload.horas_turno,
            center_configs=payload.center_configs,
            use_actual=use_actual
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simulate")
async def post_comparison_simulate(payload: ComparisonSimulatePayload, db: Session = Depends(get_db_sim)):
    try:
        # Normalizar ID de escenario base
        sc_id = payload.base_scenario_id
        if sc_id == 'base' or sc_id == 0 or sc_id is None:
            sc_id = None
        else:
            sc_id = int(sc_id)
            
        config = payload.config or {}
        
        return simulation_core.get_simulation_data(
            db,
            scenario_id=sc_id,
            dias_laborales=config.get('dias_laborales'),
            overrides_list=payload.overrides,
            horas_turno=config.get('turno_general'),
            center_configs=payload.center_configs,
            use_actual=config.get('use_actual', False)
        )
    except Exception as e:
        print(f"[ERROR] post_comparison_simulate: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# CRUD DE ARTÍCULOS (Persistencia en Excel Maestro)
# ============================================================

@app.post("/api/articles")
async def create_article(payload: ArticleCreate):
    """Crea un artículo nuevo en el Excel maestro."""
    try:
        result = simulation_core.add_article_to_excel(payload.model_dump())
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] create_article: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/articles")
async def delete_article(payload: ArticleDelete):
    """Elimina un artículo del Excel maestro."""
    try:
        result = simulation_core.delete_article_from_excel(payload.articulo, payload.centro)
        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] delete_article: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/scenarios/{scenario_id}")
def delete_scenario(scenario_id: int, db: Session = Depends(get_db_sim)):
    db_scenario = db.query(models_sim.Scenario).filter(models_sim.Scenario.id == scenario_id).first()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
        
    db.query(models_sim.ScenarioDetail).filter(models_sim.ScenarioDetail.scenario_id == scenario_id).delete()
    db.query(models_sim.ScenarioHistory).filter(models_sim.ScenarioHistory.scenario_id == scenario_id).delete()
    
    db.delete(db_scenario)
    db.commit()
    return {"message": "Scenario deleted"}

@app.put("/api/scenarios/{scenario_id}/full", response_model=ScenarioResponse)
def update_scenario_full(scenario_id: int, scenario_data: ScenarioCreate, db: Session = Depends(get_db_sim)):
    db_scenario = db.query(models_sim.Scenario).filter(models_sim.Scenario.id == scenario_id).first()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    if db_scenario.name != scenario_data.name:
        existing = db.query(models_sim.Scenario).filter(models_sim.Scenario.name == scenario_data.name).first()
        if existing:
             raise HTTPException(status_code=400, detail=f"No se puede renombrar: ya existe otro escenario con el nombre '{scenario_data.name}'.")
    
    db_scenario.name = scenario_data.name
    if scenario_data.description:
        db_scenario.description = scenario_data.description
    
    db_scenario.dias_laborales = scenario_data.dias_laborales
    db_scenario.horas_turno_global = scenario_data.horas_turno_global
    db_scenario.center_configs_json = json.dumps(scenario_data.center_configs)
    
    db.query(models_sim.ScenarioDetail).filter(models_sim.ScenarioDetail.scenario_id == scenario_id).delete()
    db.query(models_sim.ScenarioHistory).filter(models_sim.ScenarioHistory.scenario_id == scenario_id).delete()
    
    for ov in scenario_data.overrides:
        db_ov = models_sim.ScenarioDetail(
            scenario_id=db_scenario.id,
            articulo=ov.articulo,
            centro=ov.centro,
            oee_override=ov.oee_override,
            ppm_override=ov.ppm_override,
            demanda_override=ov.demanda_override,
            new_centro=ov.new_centro,
            horas_turno_override=ov.horas_turno_override,
            personnel_ratio_override=ov.personnel_ratio_override,
            setup_time_override=ov.setup_time_override
        )
        db.add(db_ov)
    
    db.commit()

    history_entry = models_sim.ScenarioHistory(
        scenario_id=db_scenario.id,
        name=db_scenario.name,
        changes_count=len(scenario_data.overrides),
        details_snapshot=json.dumps([ov.dict() for ov in scenario_data.overrides])
    )
    db.add(history_entry)
    db.commit()

    db.refresh(db_scenario)
    return db_scenario


# --- ENDPOINTS DE ADMINISTRACIÓN (TRANSFORMACIÓN ERP) ---
# [Aquí irán en el futuro las utilidades de limpieza y re-ingesta]


# --- ENDPOINTS DE ADMINISTRACIÓN (TRANSFORMACIÓN ERP) ---

@app.get("/api/admin/ingest-status")
async def get_ingest_status():
    try:
        logs = query_db("SELECT * FROM ingest_logs ORDER BY timestamp DESC LIMIT 20")
        if not logs:
            return {"status": "no_logs", "history": []}
        return {
            "status": "ok",
            "history": [dict(r) for r in logs]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- ENDPOINTS V6 (Frontend React) ---
# Endpoints dedicados sin dependencia del header referer

@app.get("/api/v6/stock/summary")
async def get_stock_summary_v6(fecha_inicio: str = None, fecha_fin: str = None):
    """Resumen de Stock para el frontend React V6."""
    try:
        latest = query_duckdb("SELECT MAX(Fecha) as f FROM existencias", one=True)
        if not latest or 'warning' in latest:
            return {"kpis": {"total_cantidad": 0, "total_valor": 0, "num_articulos": 0}, "articulos": [], "warning": "Using stale data"}
        
        actual_latest = fecha_fin if fecha_fin else latest['f']
        
        kpis = query_duckdb("""
            SELECT SUM(Cantidad) as total_cantidad, SUM(Valor_Total) as total_valor, 
                   COUNT(DISTINCT Articulo) as num_articulos
            FROM existencias WHERE Fecha = ?
        """, (actual_latest,), one=True)
        
        articulos = query_duckdb("""
            SELECT Articulo as articulo, Descripcion as descripcion, 
                   SUM(Cantidad) as cantidad, SUM(Valor_Total) as valor
            FROM existencias WHERE Fecha = ?
            GROUP BY Articulo, Descripcion ORDER BY valor DESC LIMIT 100
        """, (actual_latest,))
        
        return {
            "kpis": dict(kpis) if kpis else {"total_cantidad": 0, "total_valor": 0, "num_articulos": 0},
            "articulos": [dict(r) for r in articulos] if articulos else [],
            "ultima_fecha": str(actual_latest)
        }
    except Exception as e:
        return {"kpis": {"total_cantidad": 0, "total_valor": 0, "num_articulos": 0}, "articulos": [], "error": str(e)}

@app.get("/api/v6/stock/customers")
async def get_stock_customers_v6():
    """Top clientes de Stock para el frontend React V6."""
    try:
        latest = query_duckdb("SELECT MAX(Fecha) as f FROM existencias", one=True)
        if not latest or 'warning' in latest:
            return {"clientes": []}
        custs = query_duckdb("""
            SELECT Cliente as cliente, SUM(Valor_Total) as valor, SUM(Cantidad) as cantidad
            FROM existencias WHERE Fecha = ?
            GROUP BY Cliente ORDER BY valor DESC LIMIT 15
        """, (latest['f'],))
        return {"clientes": [dict(r) for r in custs] if custs else []}
    except Exception as e:
        return {"clientes": [], "error": str(e)}

@app.get("/api/v6/tiempos/summary")
async def get_tiempos_summary_v6(fecha_inicio: str = None, fecha_fin: str = None):
    """Resumen de Carga y Tiempos para el frontend React V6."""
    try:
        q = "SELECT Fecha, Centro, Carga_Dia FROM carga_centros WHERE Centro NOT LIKE '9%'"
        params = []
        if fecha_inicio: q += " AND Fecha >= ?"; params.append(fecha_inicio)
        if fecha_fin: q += " AND Fecha <= ?"; params.append(fecha_fin)
        
        data = query_duckdb(q, tuple(params))
        if not data or (isinstance(data, dict) and 'warning' in data):
            return {"kpis": {"total_carga_h": 0, "total_setup_h": 0, "media_oee": 0, "saturacion_general": 0}, "centros": [], "rankings": {"top_saturados": [], "top_libres": []}}
        
        df = pd.DataFrame(data)
        num_dias = df['Fecha'].nunique()
        horas_turno = 16
        
        ranking = df.groupby('Centro')['Carga_Dia'].agg(['sum', 'mean']).reset_index()
        ranking.columns = ['centro', 'carga_total', 'carga_media']
        ranking['saturacion'] = (ranking['carga_media'] / horas_turno * 100).round(1)
        ranking['carga_h'] = ranking['carga_total'].round(1)
        ranking['setup_h'] = (ranking['carga_total'] * 0.1).round(1)  # Estimación 10%
        ranking['oee'] = 85.0  # Default OEE
        ranking = ranking.sort_values('saturacion', ascending=False)
        
        centros_list = ranking.to_dict('records')
        total_carga = float(ranking['carga_h'].sum())
        total_setup = float(ranking['setup_h'].sum())
        sat_media = float(ranking['saturacion'].mean()) if len(ranking) > 0 else 0
        
        return {
            "kpis": {
                "total_carga_h": round(total_carga, 1),
                "total_setup_h": round(total_setup, 1),
                "media_oee": 85.0,
                "saturacion_general": round(sat_media, 1)
            },
            "centros": centros_list,
            "rankings": {
                "top_saturados": centros_list[:5],
                "top_libres": list(reversed(centros_list[-5:])) if len(centros_list) >= 5 else list(reversed(centros_list))
            }
        }
    except Exception as e:
        return {"kpis": {"total_carga_h": 0, "total_setup_h": 0, "media_oee": 0, "saturacion_general": 0}, "centros": [], "rankings": {"top_saturados": [], "top_libres": []}, "error": str(e)}

# --- ENDPOINTS ALBARANES ---

@app.get("/api/albaranes/resumen")
async def get_albaranes_resumen(fecha_inicio: str = None, fecha_fin: str = None):
    try:
        conds = ["1=1"]
        if fecha_inicio: conds.append(f"Fecha_Albaran >= '{fecha_inicio}'")
        if fecha_fin: conds.append(f"Fecha_Albaran <= '{fecha_fin}'")
        where_clause = "WHERE " + " AND ".join(conds)
            
        evo = query_duckdb(f"""
            SELECT Fecha_Albaran as Fecha, SUM(Importe_EUR) as Valor_Total, SUM(Cantidad) as Cantidad
            FROM albaranes
            {where_clause}
            GROUP BY Fecha_Albaran
            ORDER BY Fecha_Albaran
        """)
        
        total = query_duckdb(f"""
            SELECT SUM(Importe_EUR) as valor_total, SUM(Cantidad) as num_items, COUNT(DISTINCT Cliente) as num_clientes
            FROM albaranes
            {where_clause}
        """, one=True)
        
        if not evo or 'warning' in evo:
            return {"kpis": {"valor_total": 0, "num_items": 0, "num_clientes": 0}, "evolucion": [], "warning": "Using stale data"}
            
        return {"kpis": total, "evolucion": evo}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/albaranes/clientes")
async def get_albaranes_clientes(fecha_inicio: str = None, fecha_fin: str = None):
    try:
        conds = ["1=1"]
        if fecha_inicio: conds.append(f"Fecha_Albaran >= '{fecha_inicio}'")
        if fecha_fin: conds.append(f"Fecha_Albaran <= '{fecha_fin}'")
        where_clause = "WHERE " + " AND ".join(conds)
            
        clientes = query_duckdb(f"""
            SELECT Cliente, SUM(Importe_EUR) as Valor_Total, SUM(Cantidad) as Cantidad
            FROM albaranes
            {where_clause}
            GROUP BY Cliente
            ORDER BY Valor_Total DESC
        """)
        return clientes or []
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/albaranes/articulos")
async def get_albaranes_articulos(fecha_inicio: str = None, fecha_fin: str = None, cliente_id: str = None):
    try:
        conds = ["1=1"]
        if fecha_inicio: conds.append(f"Fecha_Albaran >= '{fecha_inicio}'")
        if fecha_fin: conds.append(f"Fecha_Albaran <= '{fecha_fin}'")
        if cliente_id: conds.append(f"Cliente = '{cliente_id}'")
        where_clause = "WHERE " + " AND ".join(conds)
            
        articulos = query_duckdb(f"""
            SELECT Articulo, SUM(Importe_EUR) as Valor_Total, SUM(Cantidad) as Cantidad
            FROM albaranes
            {where_clause}
            GROUP BY Articulo
            ORDER BY Valor_Total DESC
            LIMIT 100
        """)
        return articulos or []
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
