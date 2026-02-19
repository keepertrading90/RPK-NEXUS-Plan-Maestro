import os
import glob
import pandas as pd
from datetime import datetime

# Rutas confirmadas
REMOTE_ROOT = r"\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION"
FOLDER_STOCK = os.path.join(REMOTE_ROOT, "Listado de Existencias Actuales")
FOLDER_TIME = os.path.join(REMOTE_ROOT, "List Avance Obra-Centro y Operacion")

def get_latest_file(folder_path, pattern):
    if not os.path.exists(folder_path):
        # Intentar con Y: drive si UNC falla en este enviroment
        alt_root = r"Y:\Supply Chain\PLAN PRODUCCION"
        folder_path = folder_path.replace(REMOTE_ROOT, alt_root)
        if not os.path.exists(folder_path):
            print(f"ERROR: {folder_path} no existe.")
            return None
    
    files = glob.glob(os.path.join(folder_path, pattern))
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def check_columns():
    print("--- Verificando Carpeta STOCK ---")
    latest_stock = get_latest_file(FOLDER_STOCK, "Listado de existencias actuales*.xlsx")
    if latest_stock:
        print(f"Encontrado: {os.path.basename(latest_stock)}")
        df = pd.read_excel(latest_stock, nrows=5)
        print("Columnas encontradas:", df.columns.tolist())
    else:
        print("No se encontró archivo de Stock.")

    print("\n--- Verificando Carpeta TIEMPOS ---")
    latest_time = get_latest_file(FOLDER_TIME, "Listado Avance Obra - Centro y Operaci*.xlsx")
    if latest_time:
        print(f"Encontrado: {os.path.basename(latest_time)}")
        df = pd.read_excel(latest_time, nrows=5)
        print("Columnas encontradas:", df.columns.tolist())
    else:
        print("No se encontró archivo de Tiempos.")

if __name__ == "__main__":
    check_columns()
