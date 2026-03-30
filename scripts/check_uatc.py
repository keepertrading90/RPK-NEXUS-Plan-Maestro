import duckdb
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "backend", "db", "rpk_analytical.duckdb")

con = duckdb.connect(DB_PATH, read_only=True)

print("=== DESCRIBE maestro_fleje ===")
print(con.execute("DESCRIBE maestro_fleje").df().to_string())

print("\n=== Sample UATC + Fase ===")
df = con.execute("SELECT Articulo, Centro, UATC, Fase FROM maestro_fleje LIMIT 20").df()
print(df.to_string())

print("\n=== DISTINCT UATC ===")
print(con.execute("SELECT DISTINCT UATC FROM maestro_fleje ORDER BY UATC").df().to_string())

print("\n=== DISTINCT Fase ===")
print(con.execute("SELECT DISTINCT Fase FROM maestro_fleje ORDER BY Fase").df().to_string())

con.close()
