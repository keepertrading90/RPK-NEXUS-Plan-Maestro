import os
import glob
import pandas as pd

folder = r"\\145.3.0.54\ofimatica\Supply Chain\PLAN PRODUCCION\Listado de Existencias Actuales"
files = glob.glob(os.path.join(folder, "Listado de existencias actuales*.xlsx"))
latest = max(files, key=os.path.getmtime)
print(f"File: {os.path.basename(latest)}")

df = pd.read_excel(latest, header=None)
print("\nWarehouse (Col 0) analysis:")
# Column 0 is "Alm." (Warehouse)
# We want to see how much stock/value is in each warehouse
# Col 4 is Stock, Col 7 is Value

# First, find the data row indices (where Col 0 is numeric or '1', '2' etc)
def is_numeric(x):
    try:
        float(str(x).strip())
        return True
    except:
        return False

df_data = df[df[0].apply(is_numeric)].copy()
df_data[0] = df_data[0].astype(str).str.strip()
print("Counts per warehouse:")
print(df_data.groupby(0).size())

# Clean column 7 (Value)
def clean_val(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(' ', '').replace('.', '').replace(',', '.')
    import re
    s = re.sub(r'[^\d.\-]', '', s)
    try: return float(s) if s else 0.0
    except: return 0.0

df_data[7] = df_data[7].apply(clean_val)
df_data[9] = df_data[9].apply(clean_val)
df_data['Val_Final'] = df_data.apply(lambda r: r[7] if r[7] > 0 else r[9], axis=1)

print("\nValue per warehouse:")
summary = df_data.groupby(0)['Val_Final'].sum()
print(summary)
print(f"\nTotal Stock Value (All Warehouses): {df_data['Val_Final'].sum():,.2f} EUR")
print(f"Total Stock Value (Warehouse 1 only): {df_data[df_data[0] == '1']['Val_Final'].sum():,.2f} EUR")
