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
from backend.analytics_core import get_cobertura_global
from backend.db.consultor import traducir_a_sql, ejecutar_consulta

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
    """Métricas reales de analítica cruzada"""
    result = get_cobertura_global()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

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
