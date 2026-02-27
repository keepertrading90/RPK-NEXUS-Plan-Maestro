import pandas as pd
import numpy as np
import duckdb
import logging
import time
import os
import unicodedata
import re
from datetime import datetime
from pathlib import Path
from python_calamine import CalamineWorkbook
import warnings

warnings.filterwarnings('ignore', category=UserWarning)

# --- CONFIGURACION DE RUTAS RPK ---
BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
NETWORK_IP = r"\\145.3.0.54\ofimatica\Supply Chain\PLAN PRODUCCION"

SOURCES = {
    "pedidos": Path(NETWORK_IP) / "Listado Pedidos Ventas",
    "albaranes": Path(NETWORK_IP) / "Consulta Listado de Albaranes",
    "existencias": Path(NETWORK_IP) / "Listado de Existencias Actuales",
    "carga_centros": Path(NETWORK_IP) / "List Avance Obra-Centro y Operacion",
    "maestro_local": BASE_DIR.parent / "MAESTRO FLEJE_v1.xlsx",
    "rutas_ingenieria": None
}

# Estructura de Data Lakehouse
LAKE_DIR = BASE_DIR / "data_lake"
DB_PATH = BASE_DIR / "db" / "rpk_analytical.duckdb"

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

def clean_val(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(' ', '')
    if not s: return 0.0
    if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    s = re.sub(r'[^\d.\-]', '', s)
    try: return float(s) if s else 0.0
    except: return 0.0

def get_latest_excel(folder_path: Path):
    try:
        files = list(folder_path.glob("*.xlsx"))
        if not files: return None
        return max(files, key=os.path.getmtime)
    except:
        return None

def extract_date_from_filename(filename):
    m = re.search(r'\((\d{4}-\d{2}-\d{2})', filename)
    if m: return m.group(1)
    return datetime.now().strftime("%Y-%m-%d")

def store_parquet(df: pd.DataFrame, target_path: Path, partition: bool = False):
    if partition:
        now = datetime.now()
        partition_path = target_path / f"year={now.year}" / f"month={now.month:02d}"
        partition_path.mkdir(parents=True, exist_ok=True)
        final_file = partition_path / f"{target_path.stem}_{now.strftime('%Y%m%d%H%M')}.parquet"
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        final_file = target_path.with_suffix(".parquet")

    # Cast object columns using PyArrow rule
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
            
    df.to_parquet(final_file, engine='pyarrow', index=False)
    return final_file

def sync_duckdb(parquet_files: dict):
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

def process_existencias(file_path):
    df_raw = pd.read_excel(file_path, header=None, engine='calamine')
    date_str = extract_date_from_filename(file_path.name)
    
    # Extract Customer using localized logic vectorized
    df_raw['Cliente_Mask'] = df_raw[7].astype(str).str.contains("Divisa:EUR", na=False)
    df_raw['Cliente_Tmp'] = np.where(df_raw['Cliente_Mask'], df_raw[1], np.nan)
    df_raw['Cliente'] = pd.Series(df_raw['Cliente_Tmp']).ffill().fillna("DESCONOCIDO")
    
    # Keep valid article rows
    df_valid = df_raw[(df_raw[0].astype(str).str.strip() == '1') & (df_raw[4].notna())].copy()
    
    df_valid['Articulo'] = df_valid[1].astype(str).str.strip()
    df_valid['Descripcion'] = df_valid[2].astype(str).str.strip()
    df_valid['Cantidad'] = df_valid[4].apply(clean_val)
    
    vr7 = df_valid[7].apply(clean_val)
    vr9 = df_valid[9].apply(clean_val)
    df_valid['Valor_Total'] = np.where(vr7 > 0, vr7, vr9)
    df_valid['Fecha'] = date_str
    
    df_stock = df_valid[['Fecha', 'Cliente', 'Articulo', 'Descripcion', 'Cantidad', 'Valor_Total']].copy()
    df_stock['Stock_Objetivo'] = 0.0 # Will be populated if we load OBJETIVOS in Lake
    return df_stock

def process_tiempos(file_path):
    df_t = pd.read_excel(file_path, engine='calamine')
    date_str = extract_date_from_filename(file_path.name)
    
    cols_upper = {c: str(c).upper() for c in df_t.columns}
    mapping = {}
    for col, c in cols_upper.items():
        if 'CENTRO' in c: mapping[col] = 'Centro'
        elif 'ART' in c: mapping[col] = 'Articulo'
        elif 'TEJEC_DISP' in c or 'TIEMPO EJECUCION DISP' in c or 'TEJEC_D' in c: mapping[col] = 'Horas'
        elif 'TEJEC PTE' in c or 'TIEMPO EJECUCION PTE' in c or 'T.EJEC P' in c: mapping[col] = 'Horas_Pte'
        elif 'O.F' in c or 'OF' in c: mapping[col] = 'OF'
        
    df_t = df_t.rename(columns=mapping)
    if 'Horas' not in df_t.columns: df_t['Horas'] = 0
    if 'Horas_Pte' not in df_t.columns: df_t['Horas_Pte'] = 0
    
    df_t['Centro'] = df_t['Centro'].astype(str).str.strip()
    df_t = df_t[df_t['Centro'].str.len() <= 4].copy()
    
    df_t['Horas_val'] = df_t['Horas'].apply(clean_val)
    df_t['Horas_Pte_Val'] = df_t['Horas_Pte'].apply(clean_val)
    df_t['Horas_Final'] = np.where(df_t['Horas_val'] > 0, df_t['Horas_val'], df_t['Horas_Pte_Val'])
    df_t['Fecha'] = date_str
    
    df_detalle = df_t[['Fecha', 'Centro', 'Articulo', 'OF', 'Horas_Final', 'Horas_Pte_Val']].copy()
    
    # Crear agregado base para carga_centros
    df_diario = df_detalle.groupby(['Fecha', 'Centro'])['Horas_Final'].sum().reset_index()
    df_diario = df_diario.rename(columns={'Horas_Final': 'Carga_Dia'})
    
    return df_detalle, df_diario

def process_pedidos(file_path):
    df_pv = pd.read_excel(file_path, engine='calamine')
    date_str = extract_date_from_filename(file_path.name)
    
    df_pv = df_pv.dropna(subset=['Articulo', 'Pendient.'])
    df_pv = df_pv[df_pv['Articulo'].astype(str).str.strip() != '----------']
    df_pv = df_pv[~df_pv['Articulo'].astype(str).str.contains('Cliente:', na=False)].copy()
    
    # Mapeo rapido vectorial
    df_res = pd.DataFrame()
    df_res['Fecha_Snapshot'] = [date_str] * len(df_pv)
    if 'F.Ent.Prev' in df_pv.columns:
        df_res['Fecha_Entrega'] = df_pv['F.Ent.Prev'].astype(str).str[:10]
    else: df_res['Fecha_Entrega'] = None
    
    if 'F.Pedido' in df_pv.columns:
        df_res['Fecha_Pedido'] = df_pv['F.Pedido'].astype(str).str[:10]
    else: df_res['Fecha_Pedido'] = None
    
    df_res['Articulo'] = df_pv['Articulo'].astype(str).str.strip()
    df_res['Referencia'] = df_pv['Referencia'].astype(str).str.strip() if 'Referencia' in df_pv.columns else ""
    df_res['Cant_Pendiente'] = df_pv['Pendient.'].apply(clean_val)
    df_res['Importe_EUR'] = df_pv['Importe'].apply(clean_val) if 'Importe' in df_pv.columns else 0.0
    
    return df_res

def run_etl():
    start = time.time()
    logging.info(">>> INICIANDO CORAZON ETL VECTORIZADO (LAKEHOUSE) v5.5 <<<")
    
    results = {}
    
    # 1. Existencias
    try:
        f = get_latest_excel(SOURCES["existencias"])
        if f:
            logging.info(f"Procesando Existencias... {f.name}")
            df = process_existencias(f)
            p = store_parquet(df, LAKE_DIR / "transaccional" / "existencias", partition=True)
            results["existencias"] = {"path": p, "type": "transaccional"}
            logging.info(f"Existencias guardado: {len(df)} filas.")
    except Exception as e:
        logging.warning(f"Error Existencias: {e}")
        
    # 2. Tiempos (Carga Centros -> Horas_Final + O.F)
    try:
        f = get_latest_excel(SOURCES["carga_centros"])
        if f:
            logging.info(f"Procesando Tiempos... {f.name}")
            df_det, df_dia = process_tiempos(f)
            # Guardamos los "detalle_articulo" y "carga_centros_dia"
            p1 = store_parquet(df_dia, LAKE_DIR / "transaccional" / "carga_centros", partition=True)
            p2 = store_parquet(df_det, LAKE_DIR / "transaccional" / "carga_detalle", partition=True)
            results["carga_centros"] = {"path": p1, "type": "transaccional"}
            results["tiempos_detalle_articulo"] = {"path": p2, "type": "transaccional"}
            logging.info(f"Tiempos guardado: {len(df_dia)} dias, {len(df_det)} dets.")
            
    except Exception as e:
        logging.warning(f"Error Tiempos: {e}")
        
    # 3. Pedidos Vendidos
    try:
        f = get_latest_excel(SOURCES["pedidos"])
        if f:
            logging.info(f"Procesando Pedidos... {f.name}")
            df = process_pedidos(f)
            p = store_parquet(df, LAKE_DIR / "transaccional" / "pedidos", partition=True)
            results["pedidos"] = {"path": p, "type": "transaccional"}
            logging.info(f"Pedidos guardado: {len(df)} filas.")
    except Exception as e:
        logging.warning(f"Error Pedidos: {e}")

    # Sincronizar DuckDB View mappings
    sync_duckdb(results)
    logging.info(f">>> ETL VECTORIZADO TERMINADO EN {time.time() - start:.2f}s <<")

if __name__ == "__main__":
    run_etl()
