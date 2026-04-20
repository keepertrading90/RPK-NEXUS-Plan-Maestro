
import duckdb
import pandas as pd

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
con = duckdb.connect(db_path)

print("--- REVISIÓN DETALLADA 421653L ---")

# 1. ¿Cómo se reparten las filas por día?
q_days = """
SELECT Fecha_Albaran, Albaran, COUNT(*) as Num_Filas, SUM(Cantidad) as Cant_Total, ANY_VALUE(Cantidad) as Cant_Unitaria
FROM albaranes 
WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
GROUP BY Fecha_Albaran, Albaran
ORDER BY Fecha_Albaran
"""
df = con.execute(q_days).df()
print("\nDesglose por Día y Albarán:")
print(df)

# Sumar asumiendo que el 'Cant_Total' está multiplicado por 'Num_Filas' erróneamente
df['Cant_Corregida'] = df['Cant_Total'] / df['Num_Filas']
print(f"\nSuma total si dividimos cada grupo por su número de filas (Deduplicación agresiva): {df['Cant_Corregida'].sum()}")

# 2. ¿Qué pasa si sumamos solo el reporte del ERP?
# 2.784.000
# Veamos si alguna combinación de días suma eso.

con.close()
