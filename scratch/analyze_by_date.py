
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

print("--- ANALISIS POR FECHA DE ALBARAN (TOTAL MARZO 2026) ---")
# Only taking one snapshot per date to avoid redundancy
# But which one? Let's take the first one where an albaran appears? 
# Or just look at the distribution of all dates.

q = """
SELECT Fecha_Albaran, SUM(Cantidad) as Cant_Total, COUNT(*) as Filas
FROM albaranes
WHERE Articulo = '421653L' AND Fecha_Albaran LIKE '2026-03-%'
GROUP BY Fecha_Albaran
ORDER BY Fecha_Albaran
"""
print(con.execute(q).df())

con.close()
