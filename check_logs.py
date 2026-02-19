import sqlite3
import pandas as pd

conn = sqlite3.connect('backend/db/rpk_industrial.db')
print("--- Ingest Logs ---")
df = pd.read_sql("SELECT * FROM ingest_logs ORDER BY timestamp DESC LIMIT 10", conn)
print(df)
conn.close()
