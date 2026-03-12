import pandas as pd
from python_calamine import CalamineWorkbook

f = r'backend/db/MAESTRO FLEJE.xlsx'
workbook = CalamineWorkbook.from_path(f)
print(f"Sheets in {f}: {workbook.sheet_names}")

for sheet in workbook.sheet_names:
    try:
        df = pd.read_excel(f, engine='calamine', sheet_name=sheet)
        center_cols = [c for c in df.columns if 'CENTRO' in str(c).upper()]
        if center_cols:
            col = center_cols[0]
            centers = sorted([str(c) for c in df[col].unique()])
            print(f"Sheet '{sheet}': {len(df)} rows, {len(centers)} unique centers in '{col}'")
        else:
            print(f"Sheet '{sheet}': {len(df)} rows, no 'Centro' column. Columns: {list(df.columns[:5])}")
    except Exception as e:
        print(f"Error reading {sheet}: {e}")
