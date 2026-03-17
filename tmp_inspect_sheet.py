import pandas as pd
from python_calamine import CalamineWorkbook
from pathlib import Path

file_path = r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\MAESTRO FLEJE.xlsx"
wb = CalamineWorkbook.from_path(file_path)
sheet_name = "base de datos_1"

if sheet_name in wb.sheet_names:
    df = pd.read_excel(file_path, sheet_name=sheet_name, engine='calamine')
    print(f"Columns: {df.columns.tolist()}")
    print(f"Head:\n{df.head(2)}")
    # Check the actual values in column H (UATC) and N (Fase)
    # Note: Excel columns are 0-indexed in pandas if no header, but typically we have headers.
    # The user said Column N is Fase, Column H is UATC. 
    # In 0-indexing: H is 7, N is 13.
    # Let's see if they have names.
else:
    print(f"Sheet {sheet_name} NOT FOUND in {wb.sheet_names}")
