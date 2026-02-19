import sqlite3
import pandas as pd

conn = sqlite3.connect("backend/db/rpk_industrial.db")
cur = conn.cursor()

print("--- DRILLDOWN CHECK: Centro 782, Feb 2026 ---")
cur.execute("SELECT Articulo, OF, Horas, Fecha FROM tiempos_detalle_articulo WHERE Centro = ? AND Fecha LIKE ?", ("782", "2026-02%"))
rows = cur.fetchall()
print(f"Total rows found: {len(rows)}")
if rows:
    print("Sample details:")
    for r in rows[:5]:
        print(r)

print("\n--- CENTROS CHECK ---")
cur.execute("SELECT DISTINCT Centro FROM tiempos_carga")
centros_carga = [str(r[0]) for r in cur.fetchall()]
print(f"Centros in tiempos_carga: {centros_carga[:20]}")

cur.execute("SELECT DISTINCT Centro FROM tiempos_detalle_articulo")
centros_detalle = [str(r[0]) for r in cur.fetchall()]
print(f"Centros in tiempos_detalle_articulo: {centros_detalle[:20]}")

# Check if 782 is in details
print(f"\nIs '782' in details? {'782' in centros_detalle}")

print("\n--- SCHEMA CHECK: tiempos_detalle_articulo ---")
cur.execute("PRAGMA table_info(tiempos_detalle_articulo)")
for col in cur.fetchall():
    print(col)

conn.close()
