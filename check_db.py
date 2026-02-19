import sqlite3
import os
import pandas as pd

db_path = 'backend/db/rpk_industrial.db'
conn = sqlite3.connect(db_path)

print("--- Data: stock_snapshot (Top 5) ---")
df_stock = pd.read_sql("SELECT * FROM stock_snapshot LIMIT 5", conn)
print(df_stock)

print("\n--- Data: tiempos_carga (Top 5) ---")
df_time = pd.read_sql("SELECT * FROM tiempos_carga LIMIT 5", conn)
print(df_time)

conn.close()
