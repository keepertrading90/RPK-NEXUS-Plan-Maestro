import pandas as pd
import duckdb
import logging
import time
import os
import unicodedata
from datetime import datetime
from pathlib import Path
from python_calamine import CalamineWorkbook

# --- CONFIGURACION DE RUTAS RPK ---
BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
NETWORK_IP = r"\\145.3.0.54\ofimatica\Supply Chain\PLAN PRODUCCION"

SOURCES = {
    "pedidos": Path(NETWORK_IP) / "Listado Pedidos Ventas",
    "albaranes": Path(NETWORK_IP) / "Consulta Listado de Albaranes",
    "existencias": Path(NETWORK_IP) / "Listado de Existencias Actuales",
    "carga_centros": Path(NETWORK_IP) / "List Avance Obra-Centro y Operacion",
    "maestro_local": BASE_DIR.parent / "MAESTRO FLEJE_v1.xlsx",
    # RUTAS DE INGENIERIA: se resuelve luego porque el nombre puede tener tildes
    "rutas_ingenieria": None
}

# Estructura de Data Lakehouse
LAKE_DIR = BASE_DIR / "data_lake"
DB_PATH = BASE_DIR / "db" / "rpk_analytical.duckdb"

# Logs
LOG_DIR = BASE_DIR.parent / "scripts" / "logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [ANTIGRAVITY-ETL] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "etl_nexus.log"),
        logging.StreamHandler()
    ]
)

def normalize_col(name: str) -> str:
    """Elimina acentos y normaliza a ASCII para nombres de columnas SQL-safe."""
    nfkd = unicodedata.normalize('NFKD', str(name).strip().upper())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

def get_latest_excel(folder_path: Path) -> Path:
    """Busca el primer archivo .xlsx disponible en la carpeta especificada."""
    try:
        files = list(folder_path.glob("*.xlsx"))
        if not files:
            return None
        return max(files, key=os.path.getmtime)
    except Exception as e:
        logging.warning(f"No se pudo acceder a la carpeta {folder_path}: {e}")
        return None

def store_parquet(df: pd.DataFrame, target_path: Path, partition: bool = False):
    """Guarda un DataFrame en formato Parquet (pyarrow) con soporte de particionado."""
    if partition:
        now = datetime.now()
        partition_path = target_path / f"year={now.year}" / f"month={now.month:02d}"
        partition_path.mkdir(parents=True, exist_ok=True)
        final_file = partition_path / f"{target_path.stem}_{now.strftime('%Y%m%d')}.parquet"
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        final_file = target_path.with_suffix(".parquet")

    df.to_parquet(final_file, engine='pyarrow', index=False)
    return final_file

def sync_duckdb(parquet_files: dict):
    """Sincroniza DuckDB creando vistas/tablas apuntando a los archivos Parquet."""
    logging.info("Sincronizando rpk_analytical.duckdb...")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with duckdb.connect(str(DB_PATH)) as conn:
        for table_name, file_info in parquet_files.items():
            if file_info["path"] and file_info["path"].exists():
                if file_info["type"] == "transaccional":
                    glob_path = file_info["path"].parent.parent.parent / "**" / "*.parquet"
                    conn.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{glob_path}')")
                else:
                    conn.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{file_info['path']}')")
                logging.info(f"Vista synced: {table_name}")

def run_etl():
    start_total = time.time()
    logging.info(">>> INICIANDO CORAZON ETL RPK NEXUS v5.5 (LAKEHOUSE) <<<")
    
    results = {}

    processes = [
        {"id": "pedidos", "type": "transaccional", "folder": SOURCES["pedidos"]},
        {"id": "albaranes", "type": "transaccional", "folder": SOURCES["albaranes"]},
        {"id": "existencias", "type": "maestros", "folder": SOURCES["existencias"]},
        {"id": "carga_centros", "type": "maestros", "folder": SOURCES["carga_centros"]},
    ]

    for p in processes:
        try:
            excel_file = get_latest_excel(p["folder"])
            if not excel_file:
                logging.warning(f"No se encontro archivo para {p['id']} en {p['folder']}")
                results[p["id"]] = {"path": None, "type": p["type"]}
                continue

            logging.info(f"Leyendo {p['id']}: {excel_file.name}")
            df = pd.read_excel(excel_file, engine="calamine")
            
            df.columns = [normalize_col(c) for c in df.columns]
            
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str)
            
            target_base = LAKE_DIR / p["type"] / p["id"]
            parquet_path = store_parquet(df, target_base, partition=(p["type"] == "transaccional"))
            
            results[p["id"]] = {"path": parquet_path, "type": p["type"]}
            logging.info(f"Guardado: {p['id']} -> {len(df)} filas.")
            
        except Exception as e:
            logging.warning(f"Fallo en modulo {p['id']}: {e}")
            results[p["id"]] = {"path": None, "type": p["type"]}

    # --- MAESTRO LOCAL ---
    try:
        if SOURCES["maestro_local"].exists():
            logging.info(f"Procesando Maestro Local: {SOURCES['maestro_local'].name}")
            df_local = pd.read_excel(SOURCES["maestro_local"], engine="calamine")
            df_local.columns = [normalize_col(c) for c in df_local.columns]
            
            for col in df_local.select_dtypes(include=['object']).columns:
                df_local[col] = df_local[col].astype(str)
                
            path_local = store_parquet(df_local, LAKE_DIR / "maestros" / "maestro_local")
            results["maestro_local"] = {"path": path_local, "type": "maestros"}
        else:
            logging.warning(f"Archivo {SOURCES['maestro_local'].name} no encontrado.")
    except Exception as e:
        logging.warning(f"Error procesando maestro local: {e}")

    # --- RUTAS DE INGENIERIA (ARTICULO-MAQUINA) ---
    try:
        def _nombre_ascii(path: Path) -> str:
            nfkd = unicodedata.normalize('NFKD', path.name.upper())
            return ''.join(c for c in nfkd if not unicodedata.combining(c))

        ruta_ing = next(
            (f for f in BASE_DIR.parent.iterdir()
             if f.suffix == '.xlsx' and 'MAQUINA' in _nombre_ascii(f)),
            None
        )

        if ruta_ing and ruta_ing.exists():

            logging.info(f"Procesando Rutas Ingenieria: {ruta_ing.name}")
            df_rutas = pd.read_excel(ruta_ing, engine="calamine")

            df_rutas.columns = [normalize_col(c) for c in df_rutas.columns]

            col_map = {
                "ARTICULO-MAQUINA": "ID_RUTA",
                "ARTICULO":  "ARTICULO",
                "MAQUINA":   "MAQUINA",
                "PROD_HORARIA": "PROD_HORARIA",
                "OEE.": "OEE_REAL",
                "FASE":   "FASE",
                "T_PREP": "T_PREP",
            }
            existing = {k: v for k, v in col_map.items() if k in df_rutas.columns}
            df_rutas = df_rutas.rename(columns=existing)

            cols_utiles = [c for c in ["ARTICULO", "MAQUINA", "PROD_HORARIA", "OEE_REAL", "FASE", "T_PREP"]
                           if c in df_rutas.columns]
            df_rutas = df_rutas[cols_utiles].copy()

            for col in ["PROD_HORARIA", "OEE_REAL", "FASE", "T_PREP"]:
                if col in df_rutas.columns:
                    df_rutas[col] = pd.to_numeric(df_rutas[col], errors='coerce')

            df_rutas["ARTICULO"] = df_rutas["ARTICULO"].astype(str).str.strip()
            df_rutas["MAQUINA"]  = pd.to_numeric(df_rutas["MAQUINA"], errors='coerce')

            df_rutas = df_rutas.dropna(subset=["ARTICULO", "MAQUINA", "PROD_HORARIA"])
            df_rutas = df_rutas[df_rutas["PROD_HORARIA"] > 0].reset_index(drop=True)

            path_rutas = store_parquet(df_rutas, LAKE_DIR / "maestros" / "rutas_ingenieria")
            results["rutas_ingenieria"] = {"path": path_rutas, "type": "maestros"}
            logging.info(f"Guardado: rutas_ingenieria -> {len(df_rutas)} rutas.")
        else:
            logging.warning("Archivo ARTICULO-MAQUINA no encontrado. Rutas de ingenieria no actualizadas.")
    except Exception as e:
        logging.warning(f"Error procesando rutas_ingenieria: {e}")

    # --- SYNC DUCKDB ---
    sync_duckdb(results)

    elapsed = time.time() - start_total
    logging.info(f">>> ETL COMPLETADO EN {elapsed:.2f}s <<")

if __name__ == "__main__":
    run_etl()
