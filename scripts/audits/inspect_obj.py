import pandas as pd
import os

# FIXED PATH with _PROYECTOS
path = r"\\145.3.0.54\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_PROYECTOS\DASHBOARD_STOCK\backend\OBJETIVOS_STOCK.xlsx"
if not os.path.exists(path):
    print(f"File not found: {path}")
    # Try different combinations
    alt_path = r"\\145.3.0.54\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\DASHBOARD_STOCK\backend\OBJETIVOS_STOCK.xlsx"
    print(f"Alt exists? {os.path.exists(alt_path)}")
else:
    df = pd.read_excel(path)
    print(f"Columns: {df.columns.tolist()}")
    print("\nData Sample:")
    print(df.head(5))
