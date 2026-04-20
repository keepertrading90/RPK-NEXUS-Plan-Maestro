
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

# Parameters
YEAR = 2026
MONTH = '03'
START_DATE = '2026-02-27' # Baseline
END_DATE = '2026-03-31'

# 1. Total Shipped (Albaranes) in March 2026
q_shipped = f"""
SELECT Articulo, SUM(Cantidad) as Total_Enviado
FROM albaranes
WHERE year = {YEAR} AND month = '{MONTH}'
GROUP BY Articulo
"""
df_shipped = con.execute(q_shipped).df()

# 2. Stock at Start (Summed by Article)
q_stock_start = f"""
SELECT Articulo, SUM(Cantidad) as Stock_Inicio
FROM existencias
WHERE Fecha = '{START_DATE}'
GROUP BY Articulo
"""
df_stock_start = con.execute(q_stock_start).df()

# 3. Stock at End (Summed by Article)
q_stock_end = f"""
SELECT Articulo, SUM(Cantidad) as Stock_Fin
FROM existencias
WHERE Fecha = '{END_DATE}'
GROUP BY Articulo
"""
df_stock_end = con.execute(q_stock_end).df()

# Merge all
df = pd.merge(df_stock_start, df_stock_end, on='Articulo', how='outer').fillna(0)
df = pd.merge(df, df_shipped, on='Articulo', how='left').fillna(0)

# Calculate Difference and Implied Production
df['Diferencia_Stock'] = df['Stock_Fin'] - df['Stock_Inicio']
df['Produccion_Estimada'] = df['Diferencia_Stock'] + df['Total_Enviado']

# Clean up: only keep relevant columns for the final display
# Some articles might have negative production if data is inconsistent (e.g. stock corrections)
# We will treat "Fabricado" as the total incoming flow.
# If Diferencia_Stock > 0 and Shipped = 0, it was produced to stock.
# If Diferencia_Stock < 0 and Shipped > Produced, it was shipped from stock.

# Remove negative production artifacts (data noise)
df_clean = df[df['Produccion_Estimada'] >= 0].copy()

# Sort
top_10 = df_clean.sort_values(by='Produccion_Estimada', ascending=False).head(10)
bottom_10 = df_clean[df_clean['Produccion_Estimada'] > 0].sort_values(by='Produccion_Estimada', ascending=True).head(10)

print("--- ANALISIS MARZO 2026 ---")
print(f"Total articulos con actividad: {len(df_clean[df_clean['Produccion_Estimada'] > 0])}")

# Final selection of columns
cols = ['Articulo', 'Produccion_Estimada', 'Diferencia_Stock', 'Total_Enviado', 'Stock_Inicio', 'Stock_Fin']

print("\n--- TOP 10 FABRICACIÓN ---")
print(top_10[cols].to_string(index=False))

print("\n--- BOTTOM 10 FABRICACIÓN ---")
print(bottom_10[cols].to_string(index=False))

con.close()
