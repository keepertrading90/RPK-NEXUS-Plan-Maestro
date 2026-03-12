import pandas as pd
f = r'backend/db/MAESTRO FLEJE.xlsx'
df = pd.read_excel(f, engine='calamine')
df['Articulo'] = df['Articulo'].astype(str)
df['Centro'] = df['Centro'].astype(str)
print(f"Total rows: {len(df)}")
print(f"Unique keys: {len(df.drop_duplicates(subset=['Articulo', 'Centro']))}")
