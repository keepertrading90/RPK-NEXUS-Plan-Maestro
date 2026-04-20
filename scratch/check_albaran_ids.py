
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

print("--- ALBARANES DEL 2026-03-04 (DETALLE ID) ---")
q = """
SELECT Albaran, COUNT(*) as Filas, SUM(Cantidad) as Cant_Albaran
FROM albaranes
WHERE Articulo = '421653L' AND Fecha_Albaran = '2026-03-04'
GROUP BY Albaran
ORDER BY Albaran
"""
print(con.execute(q).df())

con.close()
