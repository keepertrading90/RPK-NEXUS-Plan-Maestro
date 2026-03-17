import sys
import os
import pandas as pd

# Añadir el directorio raíz al path para importar backend
sys.path.append(r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS')

from backend.core import simulation_core

print("--- Testing simulation_core with DuckDB ---")
data = simulation_core.get_simulation_data(db=None)

print(f"Total rows in detail: {len(data['detail'])}")
print(f"Total centers in summary: {len(data['summary'])}")

df_sum = pd.DataFrame(data['summary'])
print("\nSummary (First 5 centers):")
print(df_sum[['Centro', 'Saturacion', 'Num_Articulos']].head())

print("\nSaturation stats:")
print(df_sum['Saturacion'].describe())

# Verificar un centro específico si lo conocemos, ej. Centro 142
c142 = df_sum[df_sum['Centro'] == '142']
if not c142.empty:
    print(f"\nStats for Center 142:")
    print(c142)
else:
    print("\nCenter 142 not found in current results.")
