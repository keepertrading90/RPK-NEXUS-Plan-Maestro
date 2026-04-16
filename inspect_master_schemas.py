import duckdb
import os
from pathlib import Path

BASE = Path(r"C:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake\maestros")
conn = duckdb.connect(':memory:')

for f in BASE.glob("*.parquet"):
    print(f"\n--- FILE: {f.name} ---")
    try:
        df = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{str(f).replace('\\','/')}')").df()
        print(df[['column_name', 'column_type']])
        
        # Muestra 1 fila
        sample = conn.execute(f"SELECT * FROM read_parquet('{str(f).replace('\\','/')}') LIMIT 1").df()
        print("\nSAMPLE ROW:")
        print(sample.to_string())
    except Exception as e:
        print(f"Error reading {f.name}: {e}")

conn.close()
