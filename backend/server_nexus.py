"""
RPK NEXUS - Servidor Central FastAPI
Servicio web para el Nexus Hub y API de datos unificados.
"""

import os
import sys
import sqlite3
import uvicorn
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Configuración de rutas - Añadir raíz al path de Python
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
from datetime import datetime
from backend.analytics_core import get_cobertura_global
from backend.db.consultor import traducir_a_sql, ejecutar_consulta

# Rutas de Red para compatibilidad
STOCK_EXCEL = Path(r"\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_PROYECTOS\DASHBOARD_STOCK\backend\RESUMEN_STOCK.xlsx")
TIEMPOS_EXCEL = Path(r"\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_PROYECTOS\DASHBOARD_TIEMPOS\ANALISIS_MENSUAL_TIEMPOS_V2.xlsx")

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "backend" / "db" / "rpk_industrial.db"
STATIC_DIR = BASE_DIR / "frontend"

app = FastAPI(title="RPK NEXUS API")

# Montar archivos estáticos del Hub
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

# Montar directorios de módulos (Activos)
app.mount("/mod/stock/static", StaticFiles(directory=str(STATIC_DIR / "modules" / "stock")), name="stock_static")
app.mount("/mod/tiempos/static", StaticFiles(directory=str(STATIC_DIR / "modules" / "tiempos")), name="tiempos_static")
app.mount("/mod/simulador/static", StaticFiles(directory=str(STATIC_DIR / "modules" / "simulador")), name="simulador_static")

# Modelos
class Message(BaseModel):
    text: str

# Endpoints de UI
@app.get("/")
async def get_index():
    return FileResponse(STATIC_DIR / "ui" / "index.html")

@app.get("/mod/stock")
async def get_stock_mod():
    return FileResponse(STATIC_DIR / "modules" / "stock" / "index.html")

@app.get("/mod/tiempos")
async def get_tiempos_mod():
    # El dashboard de tiempos tiene el index en ui/index.html usualmente
    path = STATIC_DIR / "modules" / "tiempos" / "ui" / "index.html"
    if not path.exists(): path = STATIC_DIR / "modules" / "tiempos" / "index.html"
    return FileResponse(path)

@app.get("/mod/simulador")
async def get_simulador_mod():
    path = STATIC_DIR / "modules" / "simulador" / "index.html"
    if not path.exists(): path = STATIC_DIR / "modules" / "simulador" / "ui" / "index.html"
    return FileResponse(path)

# Endpoints de Datos
@app.get("/api/v1/status")
async def get_status():
    """Estado general de la base de datos Nexus"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM stock_snapshot")
        stock_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tiempos_carga")
        tiempos_count = cursor.fetchone()[0]
        
        conn.close()
        return {
            "status": "online",
            "database": "connected",
            "records": {
                "stock": stock_count,
                "tiempos": tiempos_count
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINTS COMPATIBILIDAD STOCK ---
@app.get("/api/fechas")
async def get_stock_dates(refresh: bool = False):
    try:
        xl = pd.ExcelFile(STOCK_EXCEL)
        df_ev = xl.parse('Evolucion_Diaria')
        fechas = sorted(pd.to_datetime(df_ev['Fecha']).dt.strftime('%Y-%m-%d').unique())
        return {"fecha_min": fechas[0], "fecha_max": fechas[-1], "fechas": fechas}
    except: return {"error": "No se pudo leer el Excel de Stock"}

@app.get("/api/summary")
async def get_stock_summary(fecha_inicio: str = None, fecha_fin: str = None):
    try:
        xl = pd.ExcelFile(STOCK_EXCEL)
        df_det = xl.parse('Datos_Detalle')
        df_ev = xl.parse('Evolucion_Diaria')
        df_det['Fecha'] = pd.to_datetime(df_det['Fecha']).dt.strftime('%Y-%m-%d')
        df_ev['Fecha'] = pd.to_datetime(df_ev['Fecha']).dt.strftime('%Y-%m-%d')
        latest = df_ev['Fecha'].max()
        df_l = df_det[df_det['Fecha'] == latest]
        return {
            "kpis": {"valor_total": float(df_l['Valor_Total'].sum()), "num_items": int(df_l['Articulo'].nunique()), "num_clientes": int(df_l['Cliente'].nunique())},
            "evolucion_total": {"fechas": df_ev['Fecha'].tolist(), "valores": df_ev['Valor_Total'].tolist()},
            "top_customers": df_l.groupby('Cliente')['Valor_Total'].sum().nlargest(5).reset_index().to_dict(orient='records'),
            "top_items": df_l.groupby(['Articulo','Descripcion']).agg({'Valor_Total':'sum','Cantidad':'sum'}).nlargest(100,'Valor_Total').reset_index().to_dict(orient='records'),
            "ultima_fecha": latest
        }
    except: return {"error": "Error cargando summary de stock"}

@app.post("/api/v1/chat")
async def chat_with_nexus(msg: Message):
    """Asistente inteligente integrado con la BD Nexus"""
    try:
        sql = traducir_a_sql(msg.text)
        resultados, columnas = ejecutar_consulta(sql)
        
        if not resultados:
            return {"response": "No he encontrado datos específicos para esa consulta. Prueba con 'stock total' o 'carga de trabajo'."}
        
        # Formatear respuesta simple (primeros 5 resultados)
        resp_text = f"He encontrado {len(resultados)} resultados. Aquí tienes el resumen:\n\n"
        resp_text += " | ".join(columnas) + "\n"
        resp_text += "-" * 30 + "\n"
        for row in resultados[:5]:
            resp_text += " | ".join(map(str, row)) + "\n"
            
        if len(resultados) > 5:
            resp_text += f"\n... y {len(resultados) - 5} resultados más."
            
        return {"response": resp_text}
    except Exception as e:
        return {"response": f"Lo siento, ha ocurrido un error al consultar: {str(e)}"}

if __name__ == "__main__":
    print(f"🚀 RPK NEXUS subiendo en http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
