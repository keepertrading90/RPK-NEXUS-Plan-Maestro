
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

# 1. Total Shipped (Albaranes) in March 2026
# Using month='03' since the system seems to use this partition
q_shipped = """
SELECT Articulo, SUM(Cantidad) as Total_Enviado
FROM albaranes
WHERE year = 2026 AND month = '03'
GROUP BY Articulo
"""
df_shipped = con.execute(q_shipped).df()

# 2. Stock at Start and End of March 2026
# Start date: 2026-03-02 (first actual March day in the list) or 2026-02-27 (the preceding snapshot)
# Let's use 2026-02-27 as the baseline if it exists, otherwise the first of march.
q_stock_start = """
SELECT Articulo, Cantidad as Stock_Inicio
FROM existencias
WHERE Fecha = '2026-02-27'
"""
df_stock_start = con.execute(q_stock_start).df()

q_stock_end = """
SELECT Articulo, Cantidad as Stock_Fin
FROM existencias
WHERE Fecha = '2026-03-31'
"""
df_stock_end = con.execute(q_stock_end).df()

# Combine
df = pd.merge(df_stock_start, df_stock_end, on='Articulo', how='outer').fillna(0)
df = pd.merge(df, df_shipped, on='Articulo', how='left').fillna(0)

# Calculate Difference and Implied Production
df['Diferencia_Stock'] = df['Stock_Fin'] - df['Stock_Inicio']
df['Produccion_Estimada'] = df['Diferencia_Stock'] + df['Total_Enviado']

# Filter out articles with zero activity
df = df[(df['Produccion_Estimada'] != 0) | (df['Diferencia_Stock'] != 0) | (df['Total_Enviado'] != 0)]

# Top produced
top_produced = df.sort_values(by='Produccion_Estimada', ascending=False).head(10)
bottom_produced = df[df['Produccion_Estimada'] > 0].sort_values(by='Produccion_Estimada', ascending=True).head(10)

print("--- TOP 10 PIEZAS FABRICADAS (MARZO 2026) ---")
print(top_produced[['Articulo', 'Produccion_Estimada', 'Diferencia_Stock', 'Stock_Inicio', 'Stock_Fin']])

print("\n--- BOTTOM 10 PIEZAS FABRICADAS (MARZO 2026) ---")
print(bottom_produced[['Articulo', 'Produccion_Estimada', 'Diferencia_Stock', 'Stock_Inicio', 'Stock_Fin']])

con.close()
