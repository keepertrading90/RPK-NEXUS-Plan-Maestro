import sqlite3
import pandas as pd

conn = sqlite3.connect("backend/db/rpk_industrial.db")

print("--- STOCK: VERIFICACIÓN DE HISTORIA ---")
df_evol = pd.read_sql("SELECT Fecha, Valor_Total FROM stock_evolucion ORDER BY Fecha DESC", conn)
print(f"Total días en evolución: {len(df_evol)}")
print("Últimos 5 días:")
print(df_evol.head(5))

print("\n--- STOCK: VERIFICACIÓN DE SNAPSHOT (DETALLE) ---")
df_snap = pd.read_sql("SELECT Fecha, COUNT(*) as ItemCount, SUM(Valor_Total) as TotalValue FROM stock_snapshot GROUP BY Fecha ORDER BY Fecha DESC", conn)
print(f"Total días en snapshot: {len(df_snap)}")
print("Resumen últimos 5 días:")
print(df_snap.head(5))

print("\n--- STOCK: VERIFICACIÓN DE OBJETIVOS ---")
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM stock_snapshot WHERE Stock_Objetivo > 0")
print(f"Registros con Objetivo > 0: {cur.fetchone()[0]}")

conn.close()
