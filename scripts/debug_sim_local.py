import sys
import os
import traceback

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from backend.core import simulation_core
from backend.db import models_sim

print("=== Ejecutando simulacion local ===")
try:
    with models_sim.SessionLocal() as db:
        simulation_core._df_cache = None
        
        # Llamar a get_simulation_data directamente
        res = simulation_core.get_simulation_data(db, dias_laborales=238, horas_turno=16)
        
        detail = res.get("detail", [])
        print(f"OK, total registros: {len(detail)}")
except Exception as e:
    print("ERROR FATAL TRACEBACK:")
    traceback.print_exc()
