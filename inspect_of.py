import os
import glob
import pandas as pd

def deep_inspect_tiempos():
    folder = r"\\145.3.0.54\ofimatica\Supply Chain\PLAN PRODUCCION\List Avance Obra-Centro y Operacion"
    files = glob.glob(os.path.join(folder, "Listado Avance Obra*.xlsx"))
    latest = max(files, key=os.path.getmtime)
    print(f"File: {os.path.basename(latest)}")
    
    df = pd.read_excel(latest)
    # Mapping
    mapping = {c: 'Centro' for c in df.columns if 'CENTRO' in str(c).upper()}
    mapping.update({c: 'OF' for c in df.columns if 'O.F' in str(c).upper() or 'OF' in str(c).upper()})
    mapping.update({c: 'TEjec' for c in df.columns if 'TEJEC_DISP' in str(c).upper()})
    mapping.update({c: 'TEjecPte' for c in df.columns if 'T.EJEC PTE' in str(c).upper()})
    
    df = df.rename(columns=mapping)
    
    # Pick a random OF with multiple rows
    of_counts = df['OF'].value_counts()
    sample_of = of_counts[of_counts > 1].index[0]
    
    print(f"\nOperations for OF {sample_of}:")
    print(df[df['OF'] == sample_of][['Centro', 'OF', 'TEjec', 'TEjecPte']])
    
    print("\nStats for numerical columns:")
    print(df[['TEjec', 'TEjecPte']].describe())
    
    print("\nTop 10 rows by TEjecPte:")
    print(df.nlargest(10, 'TEjecPte')[['Centro', 'OF', 'TEjec', 'TEjecPte']])

deep_inspect_tiempos()
