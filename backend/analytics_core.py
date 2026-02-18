"""
RPK NEXUS - Analítica Cruzada Core
Calcula métricas combinando Stock y Capacidad (Tiempos).
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "db" / "rpk_industrial.db"

def get_cobertura_global():
    """
    Calcula una métrica de cobertura cruzando stock total vs carga total.
    Ratio = (Stock Total / Carga Media Diaria)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # 1. Obtener Carga Total de Máquinas (Tiempos)
        df_tiempos = pd.read_sql("SELECT SUM(Carga) as total_carga FROM tiempos_carga", conn)
        total_carga = df_tiempos['total_carga'].iloc[0] or 1
        
        # 2. Obtener Stock Total
        df_stock = pd.read_sql("SELECT SUM(Cantidad) as total_stock FROM stock_snapshot", conn)
        total_stock = df_stock['total_stock'].iloc[0] or 0
        
        conn.close()
        
        # Cálculo simplificado para esta fase
        # Supongamos una cadencia media para convertir stock en horas (Ratio teórico)
        cobertura = (total_stock / 1000) / (total_carga / 24) # Ejemplo de ratio
        
        return {
            "stock_total": float(total_stock),
            "carga_total_horas": float(total_carga),
            "dias_cobertura_teorica": round(cobertura, 1)
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print(f"📊 Analítica NEXUS: {get_cobertura_global()}")
