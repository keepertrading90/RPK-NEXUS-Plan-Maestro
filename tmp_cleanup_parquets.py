import os
from pathlib import Path
from collections import defaultdict
import re

LAKE_DIR = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake\transaccional\existencias")

# Buscar todos los parquets en las particiones year/month
all_files = list(LAKE_DIR.rglob("*.parquet"))

# Agrupar por prefijo de tabla y fecha YYYYMMDD
# Los nombres son: existencias_YYYYMMDDHHMM.parquet
files_by_day = defaultdict(list)

for f in all_files:
    # Buscar patrón de fecha YYYYMMDD
    match = re.search(r'(\d{8})\d{4}', f.name)
    if match:
        day = match.group(1)
        files_by_day[day].append(f)
    elif re.search(r'(\d{8})\.parquet', f.name):
        # Ya tiene el nuevo formato
        continue

# Para cada día, si hay más de uno, borrar todos menos el más reciente (por mtime o nombre)
for day, files in files_by_day.items():
    if len(files) > 1:
        # Ordenar por tiempo de modificación (el último debería ser el bueno)
        files.sort(key=os.path.getmtime)
        to_delete = files[:-1]
        for f in to_delete:
            print(f"Borrando duplicado: {f.name}")
            os.remove(f)
            
print("Limpieza de duplicados terminada.")
