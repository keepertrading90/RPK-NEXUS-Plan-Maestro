
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

print("--- REFINAMIENTO DE SUMA CON DEDUPLICACION ---")

# Method 1: Distinct Albaran + Item + Quantity + Date
q_deduplicated = """
WITH Deduplicated AS (
    SELECT DISTINCT Albaran, Articulo, Cantidad, Fecha_Albaran
    FROM albaranes
    WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
)
SELECT SUM(Cantidad) as Suma_Limpia, COUNT(*) as Num_Albaranes_Lineas
FROM Deduplicated
"""
res = con.execute(q_deduplicated).df()
print(res)

print("\nValor ERP (Screenshot): 2,784,000")

# Method 2: Group by Albaran and Sum lines (but avoid snapshot duplication)
# We assume that for each Albaran, we only want its latest state or just one instance of its lines.
q_by_albaran = """
WITH UniqueLines AS (
    SELECT Albaran, Cantidad, Fecha_Albaran, Articulo
    FROM albaranes
    WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
    GROUP BY Albaran, Cantidad, Fecha_Albaran, Articulo
)
SELECT SUM(Cantidad) FROM UniqueLines
"""
print(f"\nSuma con Group By (Albaran, Cantidad, Fecha, Articulo): {con.execute(q_by_albaran).fetchone()[0]}")

con.close()
