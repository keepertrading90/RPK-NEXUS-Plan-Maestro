
"""
DIAGNOSTICO: Descubrir por que 421653L solo suma 1.08M en vez de 2.784M
El problema es que el snapshot del 03-04 (el dia de mayor volumen)
contenia SOLO el fichero del dia anterior o falta el fichero correcto.
"""
import duckdb, pandas as pd
from pathlib import Path

DB_PATH = Path(r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb')
LAKE_DIR = Path(r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake\transaccional\albaranes')

print("--- FICHEROS PARQUET RESTANTES EN MARZO 2026 ---")
for f in sorted((LAKE_DIR / "year=2026" / "month=03").glob("*.parquet")):
    print(f"  {f.name}")

print("\n--- SNAPSHOTS EN LA VISTA DUCKDB ---")
with duckdb.connect(str(DB_PATH)) as con:
    # Ver que snapshots han quedado para 421653L
    q = """
    SELECT Fecha_Snapshot, SUM(Cantidad) as Total
    FROM albaranes
    WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
    GROUP BY Fecha_Snapshot
    ORDER BY Fecha_Snapshot
    """
    print(con.execute(q).df())
    
    # Ver que fechas de snapshot existen en total
    q2 = """
    SELECT DISTINCT Fecha_Snapshot, COUNT(*) as Filas
    FROM albaranes
    WHERE year = 2026 AND month = '03'
    GROUP BY Fecha_Snapshot
    ORDER BY Fecha_Snapshot
    """
    print("\nTodos los snapshots de Marzo 2026:")
    print(con.execute(q2).df())
