"""Verificar que los 5 archivos de Cabeceras Fase 10 son accesibles y parsear su estructura."""
from pathlib import Path
import pandas as pd

ONEDRIVE_BASE = Path(r"C:\Users\ismael.rodriguez\OneDrive - RPK S COOP\UATC Forma-Fleje\PLANIFICACION")

ARCHIVOS = {
    "fase10_prensas":     "CARGA PRENSAS 2.xlsx",
    "fase10_flej":        "CARGA FLEJ 2.xlsx",
    "fase10_forma":       "CARGA FORMA 2.xlsx",
    "fase10_compresion":  "CARGA MAQUINA COMPRESION.xlsx",
    "fase10_retenes":     "CARGA MAQUINA RETENES.xlsx",
}

# También probar con xlsm si xlsx no existe
print("=== VERIFICACIÓN DE ACCESO A ARCHIVOS FASE 10 ===\n")
for key, fname in ARCHIVOS.items():
    p = ONEDRIVE_BASE / fname
    p2 = ONEDRIVE_BASE / fname.replace(".xlsx", ".xlsm")
    
    if p.exists():
        print(f"[OK] {fname} -> {p.stat().st_size//1024}KB")
        try:
            df = pd.read_excel(p, header=None, engine='calamine', nrows=10)
            print(f"     Hojas disponibles: usando calamine, shape={df.shape}")
            print(f"     Primeras 3 celdas relevantes: {df.iloc[:3, :6].to_string()}")
        except Exception as e:
            print(f"     [ERROR parse] {e}")
    elif p2.exists():
        print(f"[OK] {fname.replace('.xlsx','.xlsm')} (xlsm) -> {p2.stat().st_size//1024}KB")
        try:
            df = pd.read_excel(p2, header=None, engine='calamine', nrows=10)
            print(f"     shape={df.shape}")
        except Exception as e:
            print(f"     [ERROR parse] {e}")
    else:
        print(f"[NO ENCONTRADO] {fname}")
        # Buscar variaciones
        matches = list(ONEDRIVE_BASE.glob(f"*{key.replace('fase10_', '').upper()}*"))
        if matches:
            print(f"  -> Posibles: {[m.name for m in matches[:3]]}")

print("\n=== CONTENIDO DE LA CARPETA PLANIFICACION ===")
if ONEDRIVE_BASE.exists():
    for f in sorted(ONEDRIVE_BASE.iterdir()):
        print(f"  {f.name} ({f.stat().st_size//1024}KB)")
else:
    print("[ERROR] Carpeta PLANIFICACION NO encontrada en OneDrive")
    # Buscar alternativa
    alt = Path(r"C:\Users\ismael.rodriguez\OneDrive - RPK S COOP")
    if alt.exists():
        print(f"  OneDrive raíz existe. Contenido:")
        for f in sorted(alt.iterdir()):
            print(f"    {f.name}")
