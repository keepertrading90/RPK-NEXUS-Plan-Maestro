import pandas as pd

f = r'backend/db/MAESTRO FLEJE.xlsx'
df = pd.read_excel(f, engine='calamine', sheet_name='Hoja2', header=None)
print(df.head(20))
# Check if second column looks like centers
centers = sorted([str(c) for c in df[1].unique()])
print(f"\nUnique values in second column (index 1): {len(centers)}")
print(f"Sample: {centers[:20]}")
