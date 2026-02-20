import sqlite3

conn = sqlite3.connect("backend/db/rpk_industrial.db")
cur = conn.cursor()

print("--- TIEMPOS ---")
cur.execute("SELECT MIN(Fecha), MAX(Fecha), COUNT(*) FROM tiempos_carga")
print(f"Range: {cur.fetchone()}")
cur.execute("SELECT COUNT(DISTINCT Fecha) FROM tiempos_carga")
print(f"Days: {cur.fetchone()[0]}")

print("\n--- STOCK ---")
cur.execute("SELECT MIN(Fecha), MAX(Fecha), COUNT(*) FROM stock_evolucion")
print(f"Range: {cur.fetchone()}")
cur.execute("SELECT COUNT(DISTINCT Fecha) FROM stock_evolucion")
print(f"Days: {cur.fetchone()[0]}")

conn.close()
