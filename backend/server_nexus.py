"""
RPK NEXUS - Servidor Central FastAPI
Servicio web para el Nexus Hub y API de datos unificados.
"""

import os
import sqlite3
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "backend" / "db" / "rpk_industrial.db"
STATIC_DIR = BASE_DIR / "frontend"

app = FastAPI(title="RPK NEXUS API")

# Montar archivos estáticos
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

# Modelos
class Message(BaseModel):
    text: str

# Endpoints de UI
@app.get("/")
async def get_index():
    return FileResponse(STATIC_DIR / "ui" / "index.html")

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

@app.get("/api/v1/analytics/cobertura")
async def get_cobertura():
    """Endpoint preliminar para analítica cruzada"""
    # Aquí se integrará analytics_core.py en el futuro
    return {"message": "Módulo de analítica en desarrollo"}

@app.post("/api/v1/chat")
async def chat_with_nexus(msg: Message):
    """Endpoint para el asistente Gemini (Mock por ahora)"""
    # En el futuro aquí invocaremos a Gemini
    text = msg.text.lower()
    if "stock" in text:
        return {"response": "Consultando stock unificado... He encontrado 296 referencias en local."}
    elif "tiempo" in text or "carga" in text:
        return {"response": "Análisis de carga: Hay 27 centros reportando actividad actualmente."}
    else:
        return {"response": "Nexus está escuchando. ¿Qué necesitas saber sobre la producción?"}

if __name__ == "__main__":
    print(f"🚀 RPK NEXUS subiendo en http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
