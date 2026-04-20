
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

print("--- MARCH 2026 DATES ---")
q = """
SELECT DISTINCT Fecha FROM existencias 
WHERE year = 2026 AND month = '03'
ORDER BY Fecha
"""
print(con.execute(q).df())

con.close()
