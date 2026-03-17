import pandas as pd
from python_calamine import CalamineWorkbook

file_path = r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\MAESTRO FLEJE.xlsx"
sheet_name = "BASE DE DATOS_1"

df = pd.read_excel(file_path, sheet_name=sheet_name, engine='calamine')
print(f"Columns: {df.columns.tolist()}")
print(f"Data Head:\n{df.head(5)}")

# Identify N (Fase) and H (UATC)
# Columns in pandas are 0-indexed.
# H is index 7. N is index 13.
# Let's see what's at these indices.
try:
    print(f"Index 7 (H): {df.columns[7]}")
    print(f"Index 13 (N): {df.columns[13]}")
    # User said Column N is 'fase'.
except Exception as e:
    print(f"Error accessing indices: {e}")

# Search for "Cadencia" or similar in columns
cadencia_cols = [c for c in df.columns if 'cadencia' in str(c).lower() or 'piezas' in str(c).lower()]
print(f"Potential cadence columns: {cadencia_cols}")
