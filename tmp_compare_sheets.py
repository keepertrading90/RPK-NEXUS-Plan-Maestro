import pandas as pd
from python_calamine import CalamineWorkbook

file_path = r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\MAESTRO FLEJE.xlsx"

wb = CalamineWorkbook.from_path(file_path)

for sheet in ['BASE DE DATOS', 'BASE DE DATOS_1']:
    df = pd.read_excel(file_path, sheet_name=sheet, engine='calamine')
    print(f"\n--- Sheet: {sheet} ---")
    print(f"Columns: {df.columns.tolist()[:15]}") # Show first 15 cols
    print(f"Head:\n{df.head(2)}")
