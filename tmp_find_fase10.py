"""Buscar la ruta correcta de los archivos FORMA/COMPRESION/RETENES en OneDrive."""
from pathlib import Path
import shutil, tempfile

ONEDRIVE = Path(r"C:\Users\ismael.rodriguez\OneDrive - RPK S COOP")

print("=== BÚSQUEDA ARCHIVOS FASE 10 EN ONEDRIVE ===\n")

targets = [
    "CARGA FLEJE 2",
    "CARGA PRENSAS 2", 
    "CARGA FORMA 2",
    "CARGA MAQUINA COMPRESION",
    "CARGA MAQUINA RETENES",
]

found = {}
for pattern in targets:
    hits = list(ONEDRIVE.rglob(f"{pattern}*"))
    if hits:
        for h in hits:
            print(f"[OK] {h}")
            found[pattern] = h
    else:
        print(f"[NO] {pattern}")

# Verificar si CARGA PRENSAS 2 se puede copiar a temp (evitar Permission Denied)
print("\n=== TEST COPIA TEMPORAL (bypass file lock) ===")
for name, path in found.items():
    try:
        tmp = Path(tempfile.gettempdir()) / path.name
        shutil.copy2(path, tmp)
        import pandas as pd
        df = pd.read_excel(tmp, header=None, engine='calamine', nrows=15)
        print(f"[OK] {name}: shape={df.shape}")
        # Mostrar primeras celdas para ver estructura
        preview = df.dropna(how='all').head(8)
        print(preview.to_string())
        print()
    except Exception as e:
        print(f"[ERROR] {name}: {e}")
