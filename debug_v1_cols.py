import pandas as pd
from python_calamine import CalamineWorkbook

f = r'backend/db/MAESTRO FLEJE_v1.xlsx'
workbook = CalamineWorkbook.from_path(f)

for sheet in workbook.sheet_names:
    df = pd.read_excel(f, engine='calamine', sheet_name=sheet)
    print(f"--- Sheet: {sheet} ---")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Number of columns: {len(df.columns)}")
    print(df.head(5))
    print("\n")
