import os
import glob
import pandas as pd

def inspect_stock(latest):
    print(f"\n--- STOCK: {os.path.basename(latest)} ---")
    df = pd.read_excel(latest, header=None)
    print(f"Shape: {df.shape}")
    # Show column headers (row 0)
    headers = df.iloc[0].tolist()
    for i, h in enumerate(headers):
        print(f"Col {i}: {h}")
    
    print("\nData Sample (rows where Col 0 is '1'):")
    sample = df[df[0] == 1].head(5)
    print(sample)
    
    # Check what column corresponds to "Valor" or "Importe"
    # In my sync it was 7. In the dump, it looked like 9.

def inspect_tiempos(latest):
    print(f"\n--- TIEMPOS: {os.path.basename(latest)} ---")
    df = pd.read_excel(latest)
    print(f"Columns: {df.columns.tolist()}")
    
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    print(f"Numeric Columns: {numeric_cols}")
    
    print("\nColumn Sums (to see which one has real load):")
    for col in numeric_cols:
        print(f" - {col}: {df[col].sum():,.2f}")
    
    print("\nFirst 5 rows for key columns:")
    cols_of_interest = [c for c in df.columns if any(k in str(c).upper() for k in ['CENTRO', 'EJEC', 'HORA', 'TIEMPO', 'CAN', 'PH'])]
    print(df[cols_of_interest].head(5))

REMOTE_SERVER = "145.3.0.54"
REMOTE_ROOT = r"\\" + REMOTE_SERVER + r"\ofimatica\Supply Chain\PLAN PRODUCCION"
FOLDER_STOCK = os.path.join(REMOTE_ROOT, "Listado de existencias actuales")
FOLDER_TIME = os.path.join(REMOTE_ROOT, "List Avance Obra-Centro y Operacion")

latest_stock = max(glob.glob(os.path.join(FOLDER_STOCK, "Listado de existencias actuales*.xlsx")), key=os.path.getmtime)
latest_time = max(glob.glob(os.path.join(FOLDER_TIME, "Listado Avance Obra*.xlsx")), key=os.path.getmtime)

inspect_stock(latest_stock)
inspect_tiempos(latest_time)
