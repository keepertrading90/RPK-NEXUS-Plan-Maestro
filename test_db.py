import sqlite3

conn = sqlite3.connect("backend/db/rpk_industrial.db")
cur = conn.cursor()

print("--- TABLE INFO: tiempos_carga ---")
cur.execute("PRAGMA table_info(tiempos_carga)")
for col in cur.fetchall():
    print(col)

print("\n--- SAMPLE DATA: tiempos_carga ---")
cur.execute("SELECT * FROM tiempos_carga LIMIT 10")
for row in cur.fetchall():
    print(row)

print("\n--- DATE CHECK ---")
cur.execute("SELECT DISTINCT Fecha FROM tiempos_carga")
fechas = cur.fetchall()
print(f"Fechas en DB: {fechas}")

print("\n--- TEST SUMMARY QUERY ---")
target_date = "2026-02-19"
cur.execute("SELECT SUM(Carga_Dia), COUNT(DISTINCT Centro) FROM tiempos_carga WHERE Fecha = ?", (target_date,))
res = cur.fetchone()
print(f"Fecha: {target_date} -> Carga: {res[0]}, Centros: {res[1]}")

conn.close()
