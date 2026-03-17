import pandas as pd
from python_calamine import CalamineWorkbook
from pathlib import Path

files = [
    r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\MAESTRO FLEJE.xlsx",
    r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\MAESTRO FLEJE_v1.xlsx",
    r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\MAESTRO FLEJE1.xlsx"
]

for f in files:
    try:
        wb = CalamineWorkbook.from_path(f)
        print(f"File: {f}")
        print(f"Sheets: {wb.sheet_names}")
    except Exception as e:
        print(f"Error reading {f}: {e}")
