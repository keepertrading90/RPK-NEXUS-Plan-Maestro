import pandas as pd
from python_calamine import CalamineWorkbook

file_path = r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\MAESTRO FLEJE.xlsx"
sheet_name = "BASE DE DATOS_1"

df = pd.read_excel(file_path, sheet_name=sheet_name, engine='calamine')

# Focus on article 400208
sub = df[df['Articulo'] == 400208] if 'Articulo' in df.columns else df[df['Artculo'] == 400208]
cols_to_show = ['Artculo', 'FASE', 'MAQUINA', 'prod_horaria', 'UATC']
print(sub[cols_to_show].sort_values('FASE'))
