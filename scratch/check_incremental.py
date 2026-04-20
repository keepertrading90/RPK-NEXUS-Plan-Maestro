
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

print("--- ANALISIS DE CARGA DE ALBARANES POR SNAPSHOT (MARZO 2026) ---")
q_snapshot_sums = """
SELECT Fecha_Snapshot, SUM(Cantidad) as Suma_Snapshot
FROM albaranes
WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
GROUP BY Fecha_Snapshot
ORDER BY Fecha_Snapshot
"""
df_sums = con.execute(q_snapshot_sums).df()
print(df_sums)

total_erp = 2784000
current_sum = df_sums['Suma_Snapshot'].sum()
print(f"\nSuma de todos los snapshots en DuckDB: {current_sum}")
print(f"Valor en ERP (Screenshot): {total_erp}")

# Calculate cumulative sum to see if snapshots are incremental or full
df_sums['Suma_Acumulada'] = df_sums['Suma_Snapshot'].cumsum()
print("\nAnalisis: Si los snapshots fueran incrementales, la suma acumulada coincidiria con el ERP.")
print(df_sums)

con.close()
