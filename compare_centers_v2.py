import pandas as pd
import os

f1 = r'backend/db/MAESTRO FLEJE.xlsx'
f2 = r'backend/db/MAESTRO FLEJE_v1.xlsx'

for f in [f1, f2]:
    if os.path.exists(f):
        df = pd.read_excel(f, engine='calamine')
        centers = sorted([str(c) for c in df['Centro'].unique()])
        print(f"--- {f} ---")
        print(f"Total Rows: {len(df)}")
        print(f"Unique Centers Count: {len(centers)}")
        print(f"Centers: {', '.join(centers)}")
        print("\n")
    else:
        print(f"{f} not found\n")
