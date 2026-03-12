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
import sys

BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
NETWORK_IP = r"\\145.3.0.54\ofimatica\Supply Chain\PLAN PRODUCCION"

SOURCES = {
    "ocupacion": Path(NETWORK_IP) / "Listado ubicaciones vacias"
}

LAKE_DIR = BASE_DIR / "data_lake"
DB_PATH = BASE_DIR / "db" / "rpk_analytical.duckdb"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [ANTIGRAVITY-ETL-HISTORICO] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def extract_date_from_filename(filename):
    m = re.search(r'\((\d{4}-\d{2}-\d{2})', filename)
    if m: return m.group(1)
    return datetime.now().strftime("%Y-%m-%d")

def store_parquet(df: pd.DataFrame, target_path: Path, partition: bool = False):
    if df.empty: return None
    
    if partition:
        # Assuming df has 'Fecha_Snapshot'
        # Group by year and month
        df['year'] = pd.to_datetime(df['Fecha_Snapshot']).dt.year
        df['month'] = pd.to_datetime(df['Fecha_Snapshot']).dt.month
        
        for (year, month), group in df.groupby(['year', 'month']):
            partition_path = target_path / f"year={year}" / f"month={month:02d}"
            partition_path.mkdir(parents=True, exist_ok=True)
            # Find max date in group for filename
            max_date = pd.to_datetime(group['Fecha_Snapshot']).max().strftime('%Y%m%d%H%M')
            final_file = partition_path / f"{target_path.stem}_{max_date}.parquet"
            # Drop the helper columns
            to_save = group.drop(columns=['year', 'month']).copy()
            # Object to str
            for col in to_save.columns:
                if to_save[col].dtype == 'object':
                    to_save[col] = to_save[col].astype(str)
            to_save.to_parquet(final_file, engine='pyarrow', index=False)
        return target_path # return base path
    else:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        final_file = target_path.with_suffix(".parquet")
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str)
        df.to_parquet(final_file, engine='pyarrow', index=False)
        return final_file

def process_ocupacion_file(file_path):
    try:
        df = pd.read_excel(file_path, engine='calamine')
        date_str = extract_date_from_filename(file_path.name)
        
        # Cols: ['Mapa d', 'Ubicación', 'Tipo de Ubicación', '¿Vacía?']
        if len(df.columns) >= 4:
            df_res = pd.DataFrame()
            df_res['Fecha_Snapshot'] = [date_str] * len(df)
            df_res['Mapa'] = df.iloc[:, 0].astype(str).str.strip().replace('nan', '')
            df_res['Ubicacion'] = df.iloc[:, 1].astype(str).str.strip().replace('nan', '')
            df_res['Tipo_Ubicacion'] = df.iloc[:, 2].astype(str).str.strip().replace('nan', '')
            df_res['Vacia'] = df.iloc[:, 3].astype(str).str.strip().str.upper().replace('NAN', '')
            
            # Keep only valid rows
            df_res = df_res[df_res['Ubicacion'] != '']
            return df_res
    except Exception as e:
        logging.warning(f"Error reading {file_path.name}: {e}")
    return None

def run_historical():
    start = time.time()
    logging.info(">>> INICIANDO ETL HISTORICO DE OCUPACION <<<")
    
    source_dir = SOURCES["ocupacion"]
    if not source_dir.exists():
        logging.error(f"Directory not found: {source_dir}")
        return
        
    files = list(source_dir.glob('*.xlsx'))
    logging.info(f"Found {len(files)} files to process.")
    
    all_dfs = []
    
    for idx, f in enumerate(sorted(files)):
        if idx % 10 == 0:
            logging.info(f"Processing file {idx+1}/{len(files)}...")
        df = process_ocupacion_file(f)
        if df is not None and not df.empty:
            all_dfs.append(df)
            
    if all_dfs:
        logging.info("Concatenating and storing...")
        final_df = pd.concat(all_dfs, ignore_index=True)
        
        target_dir = LAKE_DIR / "transaccional" / "ocupacion"
        store_parquet(final_df, target_dir, partition=True)
        
        logging.info("Updating DuckDB view...")
        with duckdb.connect(str(DB_PATH)) as conn:
            glob_path = target_dir / "**" / "*.parquet"
            conn.execute(f"CREATE OR REPLACE VIEW ocupacion AS SELECT * FROM read_parquet('{glob_path}', union_by_name=True)")
            
        logging.info(f"Successfully processed {len(final_df)} rows.")
    else:
        logging.info("No data extracted.")
        
    logging.info(f">>> TERMINADO EN {time.time() - start:.2f}s <<<")

if __name__ == "__main__":
    run_historical()
