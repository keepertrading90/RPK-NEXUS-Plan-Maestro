
import duckdb
import pandas as pd
from pathlib import Path

# Check the data lake structure for albaranes
LAKE_DIR = Path(r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake')

alb_dir = LAKE_DIR / "transaccional" / "albaranes"
print("--- ESTRUCTURA DEL LAKEHOUSE (ALBARANES) ---")
for p in sorted(alb_dir.rglob("*.parquet")):
    size_kb = p.stat().st_size / 1024
    print(f"  {p.relative_to(alb_dir)} ({size_kb:.1f} KB)")
