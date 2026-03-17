import pandas as pd
from pathlib import Path

FILE_PATH = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\MAESTRO FLEJE.xlsx")

df = pd.read_excel(FILE_PATH, sheet_name="BASE DE DATOS_1", engine='calamine', nrows=2)
print("Columns in BASE DE DATOS_1:")
for i, col in enumerate(df.columns):
    print(f"{i}: {col}")

print("\nSample row:")
print(df.iloc[0].to_dict())
