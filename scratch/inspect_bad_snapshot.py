
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

print("--- INSPECCION SNAPSHOT 2026-03-04 PARA 421653L ---")
q = """
SELECT Fecha_Albaran, SUM(Cantidad) as Cant, COUNT(*) as Filas
FROM albaranes
WHERE Articulo = '421653L' AND year = 2026 AND month = '03' AND Fecha_Snapshot = '2026-03-04'
GROUP BY Fecha_Albaran
ORDER BY Fecha_Albaran
"""
print(con.execute(q).df())

con.close()
