
import duckdb
import pandas as pd
import os

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'

con = duckdb.connect(db_path)

# List all tables
print("--- Tables ---")
tables = con.execute("SHOW TABLES").fetchall()
for t in tables:
    print(t[0])

# Inspect schemas of relevant tables
to_inspect = ['existencias', 'albaranes', 'pedidos', 'carga_detalle']
for table in to_inspect:
    try:
        print(f"\n--- Schema of {table} ---")
        cols = con.execute(f"DESCRIBE {table}").df()
        print(cols)
        
        # Check date range to confirm March data
        date_range = con.execute(f"SELECT MIN(Fecha), MAX(Fecha) FROM {table}").fetchone()
        print(f"Date Range: {date_range}")
    except Exception as e:
        print(f"Error inspecting {table}: {e}")

con.close()
