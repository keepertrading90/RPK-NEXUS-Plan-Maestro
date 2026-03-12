import pandas as pd
from pathlib import Path

path = Path(r"\\145.3.0.54\ofimatica\Supply Chain\PLAN PRODUCCION\Listado ubicaciones vacias")
files = list(path.glob('*.xlsx'))
if files:
    latest_file = sorted(files)[-1]
    df = pd.read_excel(latest_file, engine='calamine')
    
    print("Columns:", df.columns.tolist())
    print("\nDistinct Tipo de Ubicación:", df.iloc[:, 2].dropna().unique().tolist())
    print("Distinct Mapa d:", df.iloc[:, 0].dropna().unique().tolist())
    print("\nCounts for ¿Vacía?:")
    print(df.iloc[:, 3].value_counts())
    print("\nCross tab:")
    c = pd.crosstab([df.iloc[:,0].fillna('NA'), df.iloc[:,2].fillna('NA')], df.iloc[:,3].fillna('NA'))
    print(c)
