
"""
SCRIPT DE LIMPIEZA DEL LAKEHOUSE v2 - Deduplicacion de Parquets
================================================================
Formato de los ficheros detectados:
  - CORRECTO (un solo dia):     nombre_YYYYMMDD.parquet
  - DUPLICADO (fecha+hora):     nombre_YYYYMMDDHHMMSS.parquet   (14 digitos)
  - DUPLICADO (alt):            nombre_YYYYMMDD_HHMMSS.parquet  (con guion bajo)

La solucion es agrupar por los primeros 8 digitos numericos del bloque final del nombre.
"""
import re
import logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [LAKEHOUSE-CLEANUP-v2] - %(levelname)s - %(message)s')

LAKE_DIR = Path(r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake\transaccional')
MODULES_TO_CLEAN = ["albaranes", "pedidos", "carga_centros", "carga_detalle"]

# Extrae los primeros 8 digitos del bloque numerico al final del nombre (antes de .parquet)
# Captura: albaranes_20260304.parquet     -> 20260304
#          albaranes_202603041111.parquet -> 20260304 (primeros 8 de 202603041111)
#          albaranes_20260304_123456.parquet -> 20260304
PATTERN = re.compile(r'_(\d{8})', )

def clean_module(module_name: str):
    module_path = LAKE_DIR / module_name
    if not module_path.exists():
        logging.warning(f"Modulo no existe: {module_path}")
        return

    logging.info(f"--- Limpiando {module_name} ---")
    groups = defaultdict(list)

    for parquet_file in module_path.rglob("*.parquet"):
        # Buscar el patron YYYYMMDD en el nombre del fichero
        m = PATTERN.search(parquet_file.stem)
        if m:
            date_key = m.group(1)  # YYYYMMDD
            group_key = (parquet_file.parent, date_key)
            groups[group_key].append(parquet_file)
        else:
            logging.warning(f"Sin fecha reconocible (no se toca): {parquet_file.name}")

    total_deleted = 0
    total_kept = 0

    for (partition_dir, date_key), files in sorted(groups.items()):
        if len(files) == 1:
            total_kept += 1
            continue

        # El "correcto" es el que tiene nombre mas corto (YYYYMMDD) o el mayor lexicograficamente
        # Preferimos el que tenga SOLO 8 digitos (ya tiene nombre limpio), sino el ultimo cronologicamente
        clean_files = [f for f in files if re.search(r'_\d{8}\.parquet$', f.name)]
        dirty_files = [f for f in files if not re.search(r'_\d{8}\.parquet$', f.name)]

        if clean_files:
            # Ya existe el fichero con nombre limpio: eliminar todos los sucios
            to_keep = clean_files[0]
            to_delete = dirty_files + clean_files[1:]  # Si hubiera duplicados del "limpio"
        else:
            # No hay versión limpia: conservar el mayor (mas reciente por timestamp en nombre)
            files_sorted = sorted(files, key=lambda f: f.name)
            to_keep = files_sorted[-1]
            to_delete = files_sorted[:-1]

        logging.info(f"  [{module_name}/{partition_dir.name}] Fecha {date_key}: "
                     f"CONSERVAR '{to_keep.name}', ELIMINAR {len(to_delete)} duplicado(s)")

        for f in to_delete:
            f.unlink()
            logging.info(f"    [DEL] {f.name}")
            total_deleted += 1
        total_kept += 1

    logging.info(f"  RESUMEN {module_name}: {total_kept} dias validos, {total_deleted} ficheros eliminados.\n")

def run_cleanup():
    logging.info(">>> INICIO LIMPIEZA LAKEHOUSE v2 <<<")
    for module in MODULES_TO_CLEAN:
        clean_module(module)
    logging.info(">>> LIMPIEZA COMPLETADA <<<")

if __name__ == "__main__":
    run_cleanup()
