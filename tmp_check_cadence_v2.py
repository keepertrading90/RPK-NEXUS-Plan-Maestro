import pandas as pd
from python_calamine import CalamineWorkbook

file_path = r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\MAESTRO FLEJE.xlsx"
sheet_name = "BASE DE DATOS_1"

df = pd.read_excel(file_path, sheet_name=sheet_name, engine='calamine')

# Columns: ['ARTICULO-MQUINA', 'dias laborables', 'Artculo', 'Demanda Anual', 'MAQUINA', 'prod_horaria', 't_prep', 'UATC', 'subuatc', '.', 'OEE.', '%PD_MI', '..1', 'FASE']
# Indices: 0: ARTICULO-MQUINA, 2: Artculo, 4: MAQUINA, 5: prod_horaria, 7: UATC, 13: FASE

# Get values for the first few articles to see patterns
# Group by Articulo (index 2)
art_col = df.columns[2]
fase_col = df.columns[13]
mq_col = df.columns[4]
prod_col = df.columns[5]

# Look at 400208
sub = df[df[art_col] == 400208].copy()
if sub.empty:
    # Maybe it's a string?
    sub = df[df[art_col].astype(str).str.contains('400208')].copy()

print(sub[[art_col, fase_col, mq_col, prod_col]].sort_values(fase_col))
