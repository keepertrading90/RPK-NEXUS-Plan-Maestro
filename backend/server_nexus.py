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

# --- CONFIGURACION DE RUTAS ---
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "backend" / "db" / "rpk_industrial.db"
STATIC_DIR = BASE_DIR / "frontend"

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from backend.db.consultor import traducir_a_sql, ejecutar_consulta
from backend.db import models_sim
from backend.core import simulation_core
from backend.analytics_core import get_cobertura_global
import json
from sqlalchemy.orm import Session

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

class PreviewPayload(BaseModel):
    overrides: List[OverrideBase]
    dias_laborales: Optional[int] = None
    horas_turno: Optional[int] = None
    center_configs: Optional[dict] = None

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
@app.get("/portal")
async def get_index():
    path = STATIC_DIR / "ui" / "index.html"
    print(f"[DEBUG] Sirviendo Portal desde: {path.absolute()}")
    return FileResponse(path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

# --- REDIRECCIONES Y SERVICIO DE MÓDULOS ---

@app.get("/mod/{mod_name}")
@app.get("/mod/{mod_name}/")
async def get_module_index(mod_name: str, request: Request):
    # Verificar si es un directorio de módulo válido
    mod_path = STATIC_DIR / "modules" / mod_name
    if not mod_path.is_dir():
        # Si no es un directorio, dejar que StaticFiles lo maneje (pero aquí devolvemos 404 para que siga la cadena)
        # En FastAPI, si una ruta no coincide, sigue buscando. Pero aquí ya coincidió con {mod_name}.
        # Por tanto, si no es un directorio, redirigimos al mount estático o devolvemos error.
        print(f"[DEBUG] {mod_name} no es un directorio, omitiendo get_module_index")
        raise HTTPException(status_code=404)

    # Forzar barra al final para que los activos relativos funcionen correctamente
    if not request.url.path.endswith("/"):
        return RedirectResponse(url=f"/mod/{mod_name}/")
    
    # Intentar servir index.html
    path = mod_path / "index.html"
    if not path.exists():
        # Fallback subcarpeta ui
        path_ui = mod_path / "ui" / "index.html"
        if path_ui.exists():
            path = path_ui
        else:
            print(f"[ERROR] Modulo {mod_name} no tiene index.html")
            return JSONResponse({"error": f"Modulo {mod_name} no encontrado"}, status_code=404)
            
    print(f"[DEBUG] Sirviendo index de {mod_name} desde: {path}")
    return FileResponse(path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

# Montar directorios estáticos para los activos de los módulos
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
        res_stock = query_db("SELECT SUM(Cantidad) as total, COUNT(DISTINCT Articulo) as items FROM stock_snapshot", one=True)
        
        # 2. Saturation Media (Tiempos)
        # Calculamos la saturacion media real de los ultimos 30 dias
        res_sat = query_db("""
            SELECT AVG(Carga_Dia / 16.0) as sat_avg 
            FROM tiempos_carga 
            WHERE Centro NOT LIKE '9%' 
            AND Fecha > date('now', '-30 days')
        """, one=True)
        
        # 3. Cobertura (Analítica Core)
        cobertura = get_cobertura_global()
        
        return {
            "stock": {
                "total": int(res_stock['total'] or 0),
                "items": int(res_stock['items'] or 0)
            },
            "saturation": round(float(res_sat['sat_avg'] or 0.74) * 100, 1),
            "cobertura": cobertura.get("dias_cobertura_teorica", 12.4)
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
        latest_available_date = query_db("SELECT MAX(Fecha) FROM stock_snapshot", one=True)[0]
        actual_latest = fecha_fin if fecha_fin else latest_available_date
        
        # Filtros para evolución
        evol_query = "SELECT Fecha, Valor_Total FROM stock_evolucion WHERE 1=1"
        evol_params = []
        if fecha_inicio:
            evol_query += " AND Fecha >= ?"
            evol_params.append(fecha_inicio)
        if fecha_fin:
            evol_query += " AND Fecha <= ?"
            evol_params.append(fecha_fin)
        evol_query += " ORDER BY Fecha"
        
        evol = query_db(evol_query, tuple(evol_params))
        
        # KPIs y Datos Puntuales (usamos la fecha_fin o la última disponible)
        kpis = query_db("""
            SELECT SUM(Valor_Total) as valor_total, 
                   COUNT(DISTINCT Articulo) as num_items, 
                   COUNT(DISTINCT Cliente) as num_clientes 
            FROM stock_snapshot WHERE Fecha = ?
        """, (actual_latest,), one=True)
        
        # Si no hay datos para esa fecha, intentamos la última disponible real
        if not kpis or kpis['valor_total'] is None:
             actual_latest = latest_available_date
             kpis = query_db("""
                SELECT SUM(Valor_Total) as valor_total, 
                       COUNT(DISTINCT Articulo) as num_items, 
                       COUNT(DISTINCT Cliente) as num_clientes 
                FROM stock_snapshot WHERE Fecha = ?
            """, (actual_latest,), one=True)

        top_cust = query_db("""
            SELECT Cliente, SUM(Valor_Total) as Valor_Total 
            FROM stock_snapshot WHERE Fecha = ? 
            GROUP BY Cliente ORDER BY Valor_Total DESC LIMIT 5
        """, (actual_latest,))
        
        top_items = query_db("""
            SELECT Articulo, Descripcion, SUM(Cantidad) as Cantidad, SUM(Valor_Total) as Valor_Total, MAX(Stock_Objetivo) as Stock_Objetivo
            FROM stock_snapshot WHERE Fecha = ? 
            GROUP BY Articulo, Descripcion ORDER BY Valor_Total DESC LIMIT 100
        """, (actual_latest,))
        
        return {
            "kpis": dict(kpis) if kpis else {"valor_total": 0, "num_items": 0, "num_clientes": 0},
            "evolucion_total": {
                "fechas": [r['Fecha'] for r in evol] if evol else [],
                "valores": [r['Valor_Total'] for r in evol] if evol else []
            },
            "top_customers": [dict(r) for r in top_cust] if top_cust else [],
            "top_items": [dict(r) for r in top_items] if top_items else [],
            "ultima_fecha": actual_latest
        }
    
    # --- LOGICA DE TIEMPOS ---
    else:
        # Regla: Excluir centros auxiliares (empiezan por 9)
        q = "SELECT Fecha, Centro, Carga_Dia FROM tiempos_carga WHERE Centro NOT LIKE '9%'"
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
        
        evol = df.groupby('Fecha')['Carga_Dia'].sum().sort_index()
        
        # Rankings (agregados por el periodo seleccionado)
        ranking = df.groupby('Centro')['Carga_Dia'].sum().reset_index().sort_values('Carga_Dia', ascending=False)
        ranking['Media_Diaria'] = ranking['Carga_Dia'] / (num_dias if num_dias > 0 else 1)
        
        # Evolucion de los Top 5 centros
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

# --- ENDPOINTS DEL SIMULADOR (CLASSIC V1 INTEGRATION) ---

@app.get("/api/scenarios", response_model=List[ScenarioResponse])
def list_scenarios(db: Session = Depends(get_db_sim)):
    return db.query(models_sim.Scenario).all()

@app.get("/api/scenarios/{scenario_id}/history", response_model=List[HistoryResponse])
def get_scenario_history(scenario_id: int, db: Session = Depends(get_db_sim)):
    hist = db.query(models_sim.ScenarioHistory).filter(models_sim.ScenarioHistory.scenario_id == scenario_id).order_by(models_sim.ScenarioHistory.timestamp.desc()).all()
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
async def get_base_simulation(db: Session = Depends(get_db_sim), dias_laborales: Optional[int] = None, horas_turno: Optional[int] = None):
    try:
        return simulation_core.get_simulation_data(db, dias_laborales=dias_laborales, horas_turno=horas_turno)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/simulate/{scenario_id}")
async def get_scenario_simulation(scenario_id: int, db: Session = Depends(get_db_sim), dias_laborales: Optional[int] = None, horas_turno: Optional[int] = None):
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
            center_configs=c_conf
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simulate/preview")
async def get_preview_simulation(payload: PreviewPayload, db: Session = Depends(get_db_sim)):
    try:
        return simulation_core.get_simulation_data(
            db, 
            overrides_list=payload.overrides, 
            dias_laborales=payload.dias_laborales,
            horas_turno=payload.horas_turno,
            center_configs=payload.center_configs
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/scenarios/{scenario_id}")
def delete_scenario(scenario_id: int, db: Session = Depends(get_db_sim)):
    db_scenario = db.query(models_sim.Scenario).filter(models_sim.Scenario.id == scenario_id).first()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
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

# --- MOTOR DE DATOS: TIEMPOS ---
EXCEL_TIEMPOS = BASE_DIR / "backend" / "db" / "ANALISIS_MENSUAL_TIEMPOS_V2.xlsx"
_tiempos_cache = None
_tiempos_cache_time = None

def load_tiempos_data():
    global _tiempos_cache, _tiempos_cache_time
    if _tiempos_cache is None or _tiempos_cache_time is None or (datetime.now() - _tiempos_cache_time).seconds > 60:
        if not EXCEL_TIEMPOS.exists():
            print(f"[ERROR] No existe el archivo {EXCEL_TIEMPOS}")
            return None, None, None
        try:
            df_centros = pd.read_excel(EXCEL_TIEMPOS, sheet_name='Datos_Centros').fillna(0)
            df_rankings = pd.read_excel(EXCEL_TIEMPOS, sheet_name='Rankings').fillna(0)
            try:
                df_ca = pd.read_excel(EXCEL_TIEMPOS, sheet_name='Datos_Centro_Articulo').fillna(0)
            except:
                df_ca = pd.DataFrame(columns=['Fecha', 'Centro', 'Articulo', 'Horas'])
            
            for df in [df_centros, df_rankings, df_ca]:
                if not df.empty and 'Fecha' in df.columns:
                    df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d')
            
            _tiempos_cache = (df_centros, df_rankings, df_ca)
            _tiempos_cache_time = datetime.now()
        except Exception as e:
            print(f"[ERROR] Cargando Tiempos: {e}")
            return _tiempos_cache if _tiempos_cache else (None, None, None)
    return _tiempos_cache

@app.get("/api/fechas")
async def get_tiempos_fechas():
    data = load_tiempos_data()
    if not data or data[0] is None: return {"error": "DB_NOT_FOUND"}
    fechas = sorted(data[0]['Fecha'].unique())
    return {"fecha_min": fechas[0] if fechas else None, "fecha_max": fechas[-1] if fechas else None, "fechas": fechas}

@app.get("/api/centros")
async def get_tiempos_centros():
    data = load_tiempos_data()
    if not data or data[0] is None: return {"error": "DB_NOT_FOUND"}
    centros_carga = data[0].groupby('Centro')['Carga_Dia'].sum().sort_values(ascending=False)
    return {"centros": [{"id": str(c), "carga_total": round(v, 2)} for c, v in centros_carga.items()]}

@app.get("/api/summary")
async def get_tiempos_summary(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None):
    data = load_tiempos_data()
    if not data or data[0] is None: return {"error": "DB_NOT_FOUND"}
    df_centros, _, _ = data
    if fecha_inicio: df_centros = df_centros[df_centros['Fecha'] >= fecha_inicio]
    if fecha_fin: df_centros = df_centros[df_centros['Fecha'] <= fecha_fin]
    
    if df_centros.empty: return {"kpis": {"total_carga": 0, "media_carga": 0, "num_centros": 0}}
    
    total_carga = float(df_centros['Carga_Dia'].sum())
    media_carga = float(df_centros.groupby('Fecha')['Carga_Dia'].sum().mean())
    num_centros = int(df_centros['Centro'].nunique())
    num_dias = df_centros['Fecha'].nunique() or 1
    
    evolucion = df_centros.groupby('Fecha')['Carga_Dia'].sum().sort_index()
    top_centros = df_centros.groupby('Centro')['Carga_Dia'].sum().nlargest(5).index.tolist()
    evolucion_centros = {str(c): {"fechas": df_centros[df_centros['Centro']==c]['Fecha'].tolist(), "cargas": df_centros[df_centros['Centro']==c]['Carga_Dia'].tolist()} for c in top_centros}
    
    rankings = df_centros.groupby('Centro').agg(Carga_Total=('Carga_Dia', 'sum'), Media_Diaria=('Carga_Dia', lambda x: x.sum()/num_dias)).reset_index().sort_values('Carga_Total', ascending=False)
    rankings['Centro'] = rankings['Centro'].astype(str)
    
    return {
        "kpis": {"total_carga": round(total_carga, 2), "media_carga": round(media_carga, 2), "num_centros": num_centros, "num_dias": num_dias},
        "evolucion_total": {"fechas": evolucion.index.tolist(), "cargas": evolucion.values.tolist()},
        "evolucion_centros": evolucion_centros,
        "rankings": rankings.to_dict(orient='records'),
        "ultima_fecha": df_centros['Fecha'].max()
    }

@app.get("/api/centro/{centro_id}")
async def get_tiempos_centro_detalle(centro_id: str, fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None):
    data = load_tiempos_data()
    df_centros = data[0]
    cids = [c.strip() for c in centro_id.split(',')]
    df_f = df_centros[df_centros['Centro'].astype(str).isin(cids)].copy()
    if fecha_inicio: df_f = df_f[df_f['Fecha'] >= fecha_inicio]
    if fecha_fin: df_f = df_f[df_f['Fecha'] <= fecha_fin]
    
    todas_fechas = sorted(df_f['Fecha'].unique())
    evoluciones = {}
    for cid in cids:
        df_c = df_f[df_f['Centro'].astype(str) == cid]
        if df_c.empty: continue
        evoluciones[cid] = {"fechas": df_c['Fecha'].tolist(), "cargas": df_c['Carga_Dia'].tolist(), "stats": {"total": round(df_c['Carga_Dia'].sum(), 2), "media": round(df_c['Carga_Dia'].mean(), 2)}}
    return {"fechas": todas_fechas, "centros": evoluciones}

@app.get("/api/centro/{centro_id}/articulos/mes/{mes}")
async def get_tiempos_breakdown(centro_id: str, mes: str):
    data = load_tiempos_data()
    _, _, df_ca = data
    cids = [c.strip() for c in centro_id.split(',')]
    df_f = df_ca[df_ca['Centro'].astype(str).isin(cids)].copy()
    df_f['Mes'] = pd.to_datetime(df_f['Fecha']).dt.strftime('%Y-%m')
    df_f = df_f[df_f['Mes'] == mes]
    
    if df_f.empty: return {"articulos": []}
    
    res = df_f.groupby('Articulo').agg(horas=('Horas', 'mean'), dias=('Fecha', 'nunique')).reset_index().sort_values('horas', ascending=False)
    total = res['horas'].sum()
    res['porcentaje'] = (res['horas'] / total * 100).round(2) if total > 0 else 0
    return {"mes": mes, "total_horas": round(total, 2), "articulos": res.to_dict(orient='records')}

# --- ENDPOINTS EXISTENTES (ESCENARIOS Y CHAT) ---

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
