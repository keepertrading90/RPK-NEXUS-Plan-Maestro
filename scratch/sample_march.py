
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

print("--- ALBARANES SAMPLE (MARCH 2026) ---")
q_alb = """
SELECT * FROM albaranes 
WHERE year = 2026 AND month = '03'
LIMIT 5
"""
try:
    print(con.execute(q_alb).df())
except Exception as e:
    print(e)

print("\n--- CARGA_DETALLE SAMPLE (MARCH 2026) ---")
q_carga = """
SELECT * FROM carga_detalle 
WHERE year = 2026 AND month = '03'
LIMIT 5
"""
try:
    print(con.execute(q_carga).df())
except Exception as e:
    print(e)

print("\n--- EXISTENCIAS SAMPLE (MARCH 2026) ---")
q_stock = """
SELECT * FROM existencias 
WHERE year = 2026 AND month = '03'
ORDER BY Fecha
LIMIT 5
"""
try:
    print(con.execute(q_stock).df())
except Exception as e:
    print(e)

con.close()
