import sqlite3
import pandas as pd

conn = sqlite3.connect("backend/db/rpk_industrial.db")

print("--- DAILY SUMMARY FOR 2026-02-19 ---")
df_summary = pd.read_sql("SELECT * FROM tiempos_carga WHERE Fecha = '2026-02-19' AND Centro = '782'", conn)
print(df_summary)

print("\n--- DAILY DETAILS FOR 2026-02-19 ---")
df_details = pd.read_sql("SELECT * FROM tiempos_detalle_articulo WHERE Fecha = '2026-02-19' AND Centro = '782'", conn)
print(f"Total Rows: {len(df_details)}")
print(f"Sum of Horas: {df_details['Horas'].sum()}")
print("\nTop Articles/OFs for this day:")
print(df_details.sort_values('Horas', ascending=False).head(10))

conn.close()
