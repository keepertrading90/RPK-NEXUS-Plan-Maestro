
import pandas as pd
from pathlib import Path

BASE_DIR = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS")
EXCEL_TIEMPOS = BASE_DIR / "backend" / "db" / "ANALISIS_MENSUAL_TIEMPOS_V2.xlsx"

if not EXCEL_TIEMPOS.exists():
    print(f"Error: {EXCEL_TIEMPOS} not found")
else:
    xl = pd.ExcelFile(EXCEL_TIEMPOS)
    print(f"Sheets: {xl.sheet_names}")
    for sheet in xl.sheet_names:
        df = pd.read_excel(EXCEL_TIEMPOS, sheet_name=sheet, nrows=5)
        print(f"\nSheet: {sheet}")
        print(f"Columns: {df.columns.tolist()}")
        print(df.head())
