import os
import pandas as pd
from pathlib import Path
import re

def clean_val(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(' ', '')
    if not s: return 0.0
    if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    s = re.sub(r'[^\d.\-]', '', s)
    try: return float(s) if s else 0.0
    except: return 0.0

FILE_PATH = r"\\145.3.0.54\ofimatica\Supply Chain\PLAN PRODUCCION\List Avance Obra-Centro y Operacion\Listado Avance Obra - Centro y Operación (2026-02-19 14_06_48).xlsx"

print(f"Reading file: {Path(FILE_PATH).name}")
df = pd.read_excel(FILE_PATH)

# Search for center 782
df_782 = df[df['Centro'].astype(str).str.strip() == '782']

print(f"Total rows for 782: {len(df_782)}")
print("\nRows details (Center 782):")
for idx, row in df_782.iterrows():
    of = str(row.get('O.F', row.get('OF', 'N/A')))
    art = str(row.get('Artículo', row.get('Articulo', 'N/A')))
    tejec = row.get('TEjec_Disp', 'N/A')
    tejec_pte = row.get('T.Ejec Pte', 'N/A')
    print(f"OF: {of} | Art: {art} | TEjec_Disp: {tejec} | T.Ejec Pte: {tejec_pte}")

print("\n--- SUM CHECK ---")
sum_l = df_782['TEjec_Disp'].apply(clean_val).sum()
print(f"Sum of TEjec_Disp (Cleaned): {sum_l}")

# Check specifically for 150987
of_target = "150987"
df_target = df_782[df_782['O.F'].astype(str).str.contains(of_target, na=False)]
print(f"\nSpecifically for OF {of_target}:")
print(df_target)
