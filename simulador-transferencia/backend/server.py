from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from simulator import simulate_transfer_batch
import sqlite3

app = FastAPI(title="Simulador de Lotes de Transferencia")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar Base de Datos SQLite (Carril Transaccional)
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_name TEXT,
            total_lot INTEGER,
            transfer_batch INTEGER,
            rate_a REAL,
            rate_c REAL,
            lead_time REAL,
            max_queue REAL
        )
    """)
    conn.commit()
    conn.close()

init_db()

class SimulationRequest(BaseModel):
    article_name: str
    total_lot: int
    transfer_batch: int
    rate_a: float
    rate_c: float

@app.post("/api/simulate")
def run_simulation(req: SimulationRequest):
    # Ejecutamos la simulación matemática
    result = simulate_transfer_batch(
        total_lot=req.total_lot,
        transfer_batch=req.transfer_batch,
        rate_a=req.rate_a,
        rate_c=req.rate_c
    )
    
    # Simulación tradicional usando el lote total como lote de transferencia
    traditional_result = simulate_transfer_batch(
        total_lot=req.total_lot,
        transfer_batch=req.total_lot,
        rate_a=req.rate_a,
        rate_c=req.rate_c
    )
    
    # Persistir en SQLite (Carril A)
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO simulations (article_name, total_lot, transfer_batch, rate_a, rate_c, lead_time, max_queue)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (req.article_name, req.total_lot, req.transfer_batch, req.rate_a, req.rate_c, result.lead_time_hours, result.max_queue))
        conn.commit()
    except Exception as e:
        print(f"Error saving to DB: {e}")
    finally:
        if conn:
            conn.close()
            
    return {
        "status": "success",
        "data": {
            "proposed": {
                "lead_time_hours": result.lead_time_hours,
                "max_queue": result.max_queue,
                "timeline": result.timeline
            },
            "traditional": {
                "lead_time_hours": traditional_result.lead_time_hours,
                "max_queue": traditional_result.max_queue,
                "timeline": traditional_result.timeline
            }
        },
        "message": "Simulación completada con éxito"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
