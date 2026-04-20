
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

print("--- AUDITORIA ARTICULO 421653L (MARZO 2026) ---")

# Check total sum as before
q_total = """
SELECT SUM(Cantidad) as Suma_Total 
FROM albaranes 
WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
"""
print(f"Suma Total duplicando snapshots: {con.execute(q_total).fetchone()[0]}")

# Check unique Snapshots
q_snapshots = """
SELECT DISTINCT Fecha_Snapshot 
FROM albaranes 
WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
ORDER BY Fecha_Snapshot
"""
print("\nSnapshots encontrados en Marzo:")
print(con.execute(q_snapshots).df())

# Check unique Albaranes
q_unique_albs = """
SELECT SUM(DISTINCT_CANT) FROM (
    SELECT Albaran, MAX(Cantidad) as DISTINCT_CANT
    FROM albaranes
    WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
    GROUP BY Albaran
)
"""
# Note: SUM(DISTINCT Cantidad) isn't right because different albaranes can have same quantity.
# We need to sum the quantity of each UNIQUE Albaran ID.
q_unique_albs_fix = """
WITH UniqueAlbs AS (
    SELECT Albaran, ANY_VALUE(Cantidad) as Cantidad
    FROM albaranes
    WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
    GROUP BY Albaran
)
SELECT SUM(Cantidad) FROM UniqueAlbs
"""
print(f"\nSuma de Albaranes Unicos: {con.execute(q_unique_albs_fix).fetchone()[0]}")

# Check detail of some albaranes to see if they repeat
q_detail = """
SELECT Albaran, Cantidad, Fecha_Snapshot, Fecha_Albaran
FROM albaranes
WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
LIMIT 10
"""
print("\nDetalle de registros (Primeros 10):")
print(con.execute(q_detail).df())

con.close()
