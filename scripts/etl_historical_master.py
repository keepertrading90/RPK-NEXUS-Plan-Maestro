import pandas as pd
import numpy as np
import duckdb
import logging
import time
import os
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
    "objetivos_stock": Path(NETWORK_IP) / "PANEL" / "_PROYECTOS" / "DASHBOARD_STOCK" / "backend" / "OBJETIVOS_STOCK.xlsx"
}

# Estructura de Data Lakehouse
LAKE_DIR = BASE_DIR / "data_lake"
DB_PATH = BASE_DIR / "db" / "rpk_analytical.duckdb"

LOG_DIR = BASE_DIR.parent / "scripts" / "logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [ANTIGRAVITY-ETL-HIST] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "etl_historical.log"),
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

def extract_date_from_filename(filename):
    m = re.search(r'\((\d{4}-\d{2}-\d{2})', filename)
    if m: return m.group(1)
    return None

def store_parquet(df: pd.DataFrame, target_path: Path):
    # Determine year and month from the first available date in chunk
    first_date = str(df['Fecha'].iloc[0]) if 'Fecha' in df.columns else None
    if first_date is None and 'Fecha_Snapshot' in df.columns:
        first_date = str(df['Fecha_Snapshot'].iloc[0])
    
    if first_date and len(first_date) >= 7:
        year = first_date[:4]
        month = first_date[5:7]
    else:
        now = datetime.now()
        year = str(now.year)
        month = f"{now.month:02d}"

    partition_path = target_path / f"year={year}" / f"month={month}"
    partition_path.mkdir(parents=True, exist_ok=True)
    # FIX: Nombre basado SOLO en la fecha (YYYYMMDD), sin timestamp de hora.
    # Re-ejecutar el ETL para el mismo dia SOBRESCRIBE el fichero existente,
    # en lugar de crear uno nuevo duplicado (causa del error sistematico de duplicacion).
    final_file = partition_path / f"{target_path.stem}_{first_date.replace('-','')}.parquet"

    # Cast object columns using PyArrow rule
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
            
    df.to_parquet(final_file, engine='pyarrow', index=False)
    return final_file

def sync_duckdb():
    logging.info("Sincronizando rpk_analytical.duckdb...")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with duckdb.connect(str(DB_PATH)) as conn:
            # We recreate views for everything
            transaccionales = ["existencias", "carga_centros", "carga_detalle", "pedidos", "albaranes"]
            for tb in transaccionales:
                glob_path = LAKE_DIR / "transaccional" / tb / "**" / "*.parquet"
                # Check if path actually has parquet files
                if list((LAKE_DIR / "transaccional" / tb).glob("**/*.parquet")):
                    conn.execute(f"CREATE OR REPLACE VIEW {tb} AS SELECT * FROM read_parquet('{glob_path}', union_by_name=True)")
                    logging.info(f"Vista synced: {tb}")
    except Exception as e:
        logging.error(f"Error sincronizando DuckDB: {e}")

# Pre-load Obj
DF_OBJ = None
if SOURCES["objetivos_stock"] and SOURCES["objetivos_stock"].exists():
    try:
        df_obj = pd.read_excel(SOURCES["objetivos_stock"], engine='calamine')
        cols_upper = {c: str(c).upper() for c in df_obj.columns}
        art_col = next((c for c, upper in cols_upper.items() if 'ART' in upper), None)
        obj_col = next((c for c, upper in cols_upper.items() if 'OBJ' in upper), None)
        if art_col and obj_col:
            DF_OBJ = df_obj[[art_col, obj_col]].copy()
            DF_OBJ = DF_OBJ.rename(columns={art_col: 'ID_ARTICULO_OBJ', obj_col: 'VR_STOCK_OBJ'})
            DF_OBJ['ID_ARTICULO_OBJ'] = DF_OBJ['ID_ARTICULO_OBJ'].astype(str).str.strip().str.upper()
            DF_OBJ['VR_STOCK_OBJ'] = DF_OBJ['VR_STOCK_OBJ'].apply(clean_val)
    except Exception as e:
        logging.warning(f"Error parseando Objetivos globales: {e}")

def process_existencias(file_path, date_str):
    try:
        df_raw = pd.read_excel(file_path, header=None, engine='calamine')
        df_raw['Cliente_Mask'] = df_raw[7].astype(str).str.contains("Divisa:EUR", na=False)
        df_raw['Cliente_Tmp'] = np.where(df_raw['Cliente_Mask'], df_raw[1], np.nan)
        df_raw['Cliente'] = pd.Series(df_raw['Cliente_Tmp']).ffill().fillna("DESCONOCIDO")
        
        df_valid = df_raw[(df_raw[0].astype(str).str.strip() == '1') & (df_raw[4].notna())].copy()
        if df_valid.empty: return None

        df_valid['Articulo'] = df_valid[1].astype(str).str.strip()
        df_valid['Descripcion'] = df_valid[2].astype(str).str.strip()
        df_valid['Cantidad'] = df_valid[4].apply(clean_val)
        
        vr7 = df_valid[7].apply(clean_val)
        vr9 = df_valid[9].apply(clean_val)
        df_valid['Valor_Total'] = np.where(vr7 > 0, vr7, vr9)
        df_valid['Fecha'] = date_str
        
        df_stock = df_valid[['Fecha', 'Cliente', 'Articulo', 'Descripcion', 'Cantidad', 'Valor_Total']].copy()
        
        if DF_OBJ is not None:
            df_stock['Articulo_Merge'] = df_stock['Articulo'].str.upper()
            df_stock = pd.merge(df_stock, DF_OBJ, left_on='Articulo_Merge', right_on='ID_ARTICULO_OBJ', how='left')
            df_stock['Stock_Objetivo'] = df_stock['VR_STOCK_OBJ'].fillna(0.0)
            df_stock = df_stock.drop(columns=['Articulo_Merge', 'ID_ARTICULO_OBJ', 'VR_STOCK_OBJ'])
        else:
            df_stock['Stock_Objetivo'] = 0.0
                
        return df_stock
    except Exception as e:
        logging.warning(f"Error procesando {file_path.name}: {e}")
        return None

def process_tiempos(file_path, date_str):
    try:
        df_t = pd.read_excel(file_path, engine='calamine')
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
        
        if 'Centro' not in df_t.columns: return None, None

        df_t['Centro'] = df_t['Centro'].astype(str).str.strip()
        df_t = df_t[df_t['Centro'].str.len() <= 4].copy()
        if df_t.empty: return None, None
        
        df_t['Horas_val'] = df_t['Horas'].apply(clean_val)
        df_t['Horas_Pte_Val'] = df_t['Horas_Pte'].apply(clean_val)
        df_t['Horas_Final'] = np.where(df_t['Horas_val'] > 0, df_t['Horas_val'], df_t['Horas_Pte_Val'])
        df_t['Fecha'] = date_str
        
        if 'Articulo' not in df_t.columns: df_t['Articulo'] = 'DESCONOCIDO'
        if 'OF' not in df_t.columns: df_t['OF'] = 'DESCONOCIDA'

        df_detalle = df_t[['Fecha', 'Centro', 'Articulo', 'OF', 'Horas_Final', 'Horas_Pte_Val']].copy()
        
        # Crear agregado base para carga_centros
        df_diario = df_detalle.groupby(['Fecha', 'Centro'])['Horas_Final'].sum().reset_index()
        df_diario = df_diario.rename(columns={'Horas_Final': 'Carga_Dia'})
        
        return df_detalle, df_diario
    except Exception as e:
        logging.warning(f"Error procesando {file_path.name}: {e}")
        return None, None

def process_pedidos(file_path, date_str):
    try:
        df_pv = pd.read_excel(file_path, engine='calamine')
        
        if 'Articulo' not in df_pv.columns or 'Pendient.' not in df_pv.columns:
            return None

        df_pv = df_pv.dropna(subset=['Articulo', 'Pendient.'])
        df_pv = df_pv[df_pv['Articulo'].astype(str).str.strip() != '----------']
        df_pv = df_pv[~df_pv['Articulo'].astype(str).str.contains('Cliente:', na=False)].copy()
        if df_pv.empty: return None
        
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
    except Exception as e:
        logging.warning(f"Error procesando {file_path.name}: {e}")
        return None

def process_albaranes(file_path, date_str):
    try:
        df_raw = pd.read_excel(file_path, engine='calamine')
        if 'Articulo' not in df_raw.columns or 'Cantidad' not in df_raw.columns: return None
            
        df_raw['Cliente_Mask'] = df_raw['Articulo'].astype(str).str.strip() == 'Cliente:'
        cols = df_raw.columns.tolist()
        idx = cols.index('Articulo')
        cliente_cols = cols[idx+1:idx+4]
        
        df_raw['Cliente_Tmp'] = np.where(
            df_raw['Cliente_Mask'],
            df_raw[cliente_cols].fillna('').astype(str).agg(' '.join, axis=1).str.replace('nan', '', case=False).str.replace(r'\s+', ' ', regex=True).str.strip(),
            np.nan
        )
        df_raw['Cliente'] = pd.Series(df_raw['Cliente_Tmp']).replace('', np.nan).ffill().fillna("DESCONOCIDO")
        
        df_valid = df_raw[~df_raw['Cliente_Mask']].copy()
        if 'Importe' in df_valid.columns:
            df_valid = df_valid.dropna(subset=['Cantidad', 'Importe'])
        else:
            df_valid = df_valid.dropna(subset=['Cantidad'])
            
        df_valid = df_valid[df_valid['Articulo'].astype(str).str.strip() != '----------']
        if df_valid.empty: return None
        
        df_res = pd.DataFrame()
        df_res['Fecha_Snapshot'] = [date_str] * len(df_valid)
        df_res['Fecha_Albaran'] = df_valid['Fec.Alb.'].astype(str).str[:10] if 'Fec.Alb.' in df_valid.columns else None
        df_res['Cliente'] = df_valid['Cliente'].str.upper()
        df_res['Articulo'] = df_valid['Articulo'].astype(str).str.strip()
        
        alb_col = next((c for c in df_valid.columns if 'Albar' in c), None)
        df_res['Albaran'] = df_valid[alb_col].astype(str).str.strip() if alb_col else ''
        
        df_res['Pedido'] = df_valid['Pedido'].astype(str).str.strip() if 'Pedido' in df_valid.columns else ''
        df_res['Cantidad'] = df_valid['Cantidad'].apply(clean_val)
        df_res['Importe_EUR'] = df_valid['Importe'].apply(clean_val) if 'Importe' in df_valid.columns else 0.0
        
        return df_res
    except Exception as e:
        logging.warning(f"Error procesando {file_path.name}: {e}")
        return None

def ingest_module(mod_name, source_path, process_func, target_names, is_morning_snapshot=False):
    logging.info(f"--- Escaneando historicos para {mod_name} en {source_path} ---")
    if not source_path or not source_path.exists():
        logging.error(f"Ruta no existe: {source_path}")
        return

    files = list(source_path.glob("*.xlsx"))
    files_by_date = {}
    
    for f in files:
        date_str = extract_date_from_filename(f.name)
        if not date_str: continue
        
        if is_morning_snapshot:
            # PRIMERA captura del dia
            if date_str not in files_by_date:
                files_by_date[date_str] = f
            elif f.name < files_by_date[date_str].name:
                files_by_date[date_str] = f
        else:
            # ULTIMA captura del dia (ej. Existencias)
            if date_str not in files_by_date:
                files_by_date[date_str] = f
            elif f.name > files_by_date[date_str].name:
                files_by_date[date_str] = f

    logging.info(f"Se encontraron {len(files_by_date)} dias a procesar para {mod_name}.")
    
    success_count = 0
    for date_str, f in sorted(files_by_date.items()):
        logging.info(f"[{date_str}] Procesando: {f.name}")
        res = process_func(f, date_str)
        
        if isinstance(res, tuple):
            if res[0] is not None and len(res[0]) > 0:
                store_parquet(res[1], LAKE_DIR / "transaccional" / target_names[0]) # diario
                store_parquet(res[0], LAKE_DIR / "transaccional" / target_names[1]) # detalle
                success_count += 1
        else:
            if res is not None and len(res) > 0:
                store_parquet(res, LAKE_DIR / "transaccional" / target_names[0])
                success_count += 1

    logging.info(f"--- Finalizado {mod_name}: {success_count} dias procesados. ---")

def run_historical_etl():
    start = time.time()
    logging.info(">>> INICIANDO ETL HISTORICO (LAKEHOUSE) v5.5 <<<")
    
    # 1. Existencias (Ultima foto del dia)
    ingest_module("existencias", SOURCES["existencias"], process_existencias, ["existencias"], is_morning_snapshot=False)
    
    # 2. Tiempos (Primera foto del dia)
    ingest_module("carga_centros", SOURCES["carga_centros"], process_tiempos, ["carga_centros", "carga_detalle"], is_morning_snapshot=True)
    
    # 3. Pedidos (Primera foto del dia)
    ingest_module("pedidos", SOURCES["pedidos"], process_pedidos, ["pedidos"], is_morning_snapshot=True)

    # 4. Albaranes (Ultima foto del dia)
    ingest_module("albaranes", SOURCES["albaranes"], process_albaranes, ["albaranes"], is_morning_snapshot=False)

    # Re-Sincronizar vistas
    sync_duckdb()
    
    logging.info(f">>> ETL HISTORICO TERMINADO EN {(time.time() - start)/60:.2f} min <<<")

if __name__ == "__main__":
    run_historical_etl()
