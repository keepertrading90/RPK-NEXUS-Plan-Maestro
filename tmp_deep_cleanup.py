import os
from pathlib import Path
from collections import defaultdict
import re

LAKE_DIR = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake\transaccional\existencias")

# Buscar todos los parquets recursivamente
all_files = list(LAKE_DIR.rglob("*.parquet"))

# Agrupar por fecha extraída del nombre
files_by_day = defaultdict(list)

for f in all_files:
    # Buscar patrón de fecha YYYYMMDD o YYYY_MM_DD o similar
    match = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', f.name)
    if match:
        day = "".join(match.groups())  # YYYYMMDD
        files_by_day[day].append(f)

# Procesar cada día
for day, files in files_by_day.items():
    # Ordenar por tiempo de modificación descendente (el más nuevo primero)
    files.sort(key=os.path.getmtime, reverse=True)
    
    survivor = files[0]
    to_delete = files[1:]
    
    # Borrar duplicados
    for df in to_delete:
        print(f"Borrando duplicado: {df.relative_to(LAKE_DIR)}")
        try:
            os.remove(df)
        except Exception as e:
            print(f"Error borrando {df}: {e}")
            
    # Estandarizar nombre del superviviente
    new_name = survivor.parent / f"existencias_{day}.parquet"
    if survivor != new_name:
        print(f"Estandarizando: {survivor.name} -> {new_name.name}")
        if new_name.exists():
            # Si el destino ya existe (raro tras el borrado anterior), borrarlo antes de renombrar
            os.remove(new_name)
        try:
            os.rename(survivor, new_name)
        except Exception as e:
            print(f"Error renombrando {survivor}: {e}")

print("Saneamiento completo del Data Lake de existencias.")
