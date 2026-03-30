import pandas as pd
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
import warnings

# Silenciamos warnings genéricos
warnings.filterwarnings('ignore', category=UserWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [ANTIGRAVITY-ETL-FASE10] - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_tables_vectorized(df_raw: pd.DataFrame, source_name: str, fecha_str: str) -> pd.DataFrame:
    """
    Extracción robusta y matricial de tablas anidadas dentro de un Excel sin formato estructurado.
    Busca el header "ARTÍCULO" en toda la hoja para delimitar las tablas horizontales/verticales
    y extrae los lotes secuenciados asociándolos a su centro (máquina) de cabecera.
    """
    # 1. Crear máscara booleana de todo el DF buscando el ancla ("ARTÍCULO" u "OF")
    # Cast a minúsculas y vectorizado
    df_str = df_raw.fillna('').astype(str).apply(lambda x: x.str.strip().str.lower())
    mask_art = df_str.apply(lambda col: col.str.contains(r'^art', regex=True))
    
    # 2. Encontrar coordenadas (fila, columna) de los anclajes
    rows, cols = np.where(mask_art)
    
    if len(rows) == 0:
        logger.warning(f"No se detectaron tablas secuenciadas en {source_name}")
        return pd.DataFrame()
        
    extracted_dfs = []
    
    # Aunque haya un 'for', iteramos solo sobre la cantidad de centros observados (ej. ~3 a 10)
    # y nunca sobre los datos crudos (iterrows), manteniendo la complejidad O(1) de operaciones lógicas.
    for r, c in zip(rows, cols):
        try:
            # Buscar el "Centro / Máquina" en las 2-3 filas superiores a la columna del Artículo.
            # Idealmente, el centro está directamente arriba o en la diagonal.
            centro_candidatos = df_raw.iloc[max(0, r-3):r, max(0, c-1):c+2].astype(str).values.flatten()
            centro = "DESC"
            for cand in centro_candidatos:
                # Buscamos números de centro como '109', '127', 'MÁQUINA 109'
                if not pd.isna(cand) and cand.strip() and ('nan' not in cand.lower()):
                    # Filtramos a números o textos robustos
                    import re
                    match = re.search(r'\d{3}', cand)
                    if match:
                        centro = match.group()
                        break
                        
            # Bajar hasta encontrar una fila vacía en la columna de Artículo
            col_data = df_str.iloc[r+1:, c]
            
            # Encontrar el índice de la primera celda vacía para cortar la tabla
            empty_mask = (col_data == '') | (col_data == 'nan')
            if empty_mask.any():
                end_row = col_data[empty_mask].index[0]
            else:
                end_row = df_raw.shape[0]
                
            # Extraer el bloque (Normalmente OF, ART, CANT, HORAS, MATE)
            # Como la OF suele estar a la izquierda (c-1), probamos c-1 hasta c+3
            start_col = max(0, c-1)
            end_col = min(df_raw.shape[1], c+4)
            
            chunk = df_raw.iloc[r+1:end_row, start_col:end_col].copy()
            
            # Renombrar columnas inteligentemente según su contenido de cabecera (fila r)
            headers = df_str.iloc[r, start_col:end_col].tolist()
            map_cols = {}
            for idx, h in enumerate(headers):
                if 'of' in h:  map_cols[chunk.columns[idx]] = 'OF'
                elif 'art' in h: map_cols[chunk.columns[idx]] = 'Articulo'
                elif 'cant' in h: map_cols[chunk.columns[idx]] = 'Cantidad'
                elif 'hora' in h or 'hor.' in h: map_cols[chunk.columns[idx]] = 'Horas_Necesarias'
                
            chunk = chunk.rename(columns=map_cols)
            
            # Forzamos tener las columnas requeridas (si OF no existe, la inicializamos vacía)
            for req in ['OF', 'Articulo', 'Cantidad', 'Horas_Necesarias']:
                if req not in chunk.columns:
                    chunk[req] = ''
            
            chunk = chunk[['OF', 'Articulo', 'Cantidad', 'Horas_Necesarias']].copy()
            chunk['Centro_Cabecera'] = centro
            chunk['Origen'] = source_name
            chunk['Fecha_Carga'] = fecha_str
            # Orden de secuenciación según aparición
            chunk['Orden_Secuencia'] = np.arange(1, len(chunk) + 1)
            
            # Limpiar filas inútiles
            chunk = chunk[chunk['Articulo'].astype(str).str.strip() != '']
            chunk = chunk[chunk['Articulo'].notna()]
            
            extracted_dfs.append(chunk)
            
        except Exception as e:
            logger.error(f"Fallo al procesar un bloque anidado en {source_name}: {e}")
            continue
            
    if extracted_dfs:
        res = pd.concat(extracted_dfs, ignore_index=True)
        return res
    return pd.DataFrame()

def process_file_fase10(file_path: Path) -> pd.DataFrame:
    """Ingesta un Excel mediante Calamine (vectorizado y ultrarrápido)."""
    try:
        df_raw = pd.read_excel(file_path, engine='calamine', header=None)
        fecha_str = datetime.now().strftime("%Y-%m-%d")
        df_clean = extract_tables_vectorized(df_raw, file_path.stem, fecha_str)
        
        # Limpieza matricial
        if not df_clean.empty:
            df_clean['Cantidad'] = pd.to_numeric(df_clean['Cantidad'], errors='coerce').fillna(0)
            df_clean['Horas_Necesarias'] = pd.to_numeric(df_clean['Horas_Necesarias'], errors='coerce').fillna(0)
            df_clean['Articulo'] = df_clean['Articulo'].astype(str).str.strip()
            df_clean['Centro_Cabecera'] = df_clean['Centro_Cabecera'].astype(str).str.strip()
            
        return df_clean
    except Exception as e:
        logger.error(f"Error ingestando archivo ({file_path.name}): {e}")
        return pd.DataFrame()

def build_carga_consolidada(target_paths: list, data_lake_dir: Path):
    """
    Función principal que orquesta la lectura de los 5 Excels,
    los fusiona y los inyecta en el ecosistema Parquet (Carril B).
    """
    dfs = []
    for fpath in target_paths:
        f = Path(fpath)
        if f.exists():
            logger.info(f"Ingestando Fase 10 -> {f.name}")
            df = process_file_fase10(f)
            if not df.empty:
                dfs.append(df)
        else:
            logger.warning(f"Archivo no encontrado: {f.name}")
            
    if dfs:
        df_final = pd.concat(dfs, ignore_index=True)
        # Vectorizado casting para Parquet compatibilidad
        for col in df_final.columns:
            if df_final[col].dtype == 'object':
                df_final[col] = df_final[col].astype(str)
                
        now = datetime.now()
        partition_path = data_lake_dir / "transaccional" / "carga_cabeceras" / f"year={now.year}" / f"month={now.month:02d}"
        partition_path.mkdir(parents=True, exist_ok=True)
        
        final_file = partition_path / f"carga_cabeceras_{now.strftime('%Y%m%d')}.parquet"
        df_final.to_parquet(final_file, engine='pyarrow', index=False)
        logger.info(f"Guardado exitosamente {len(df_final)} secuencias en {final_file}")
        return final_file
    else:
        logger.warning(f"No se pudo recolectar data de Fase 10 para guardar.")
        return None

if __name__ == "__main__":
    # Test local / fallback
    base_dir = Path(__file__).resolve().parent.parent
    dl_dir = base_dir / "backend" / "data_lake"
    
    # NOMBRES ENVIADOS POR EL USUARIO:
    # "CARGA PRENSAS 2"; "CARGA FLEJ 2"; "CARGA FORMA 2"; "CARGA MAQUINA COMPRESION"; "CARGA MAQUINA RETENES"
    # Localizaciones teóricas en la red (o rutas compartidas de OneDrive mapeadas)
    NETWORK_IP = r"\\145.3.0.54\ofimatica\Supply Chain\PLAN PRODUCCION" 
    
    TARGETS = [
        Path(NETWORK_IP) / "PANEL" / "_PROYECTOS" / "MOCK_F10" / "CARGA PRENSAS 2.xlsx",
        Path(NETWORK_IP) / "PANEL" / "_PROYECTOS" / "MOCK_F10" / "CARGA FLEJ 2.xlsx",
        Path(NETWORK_IP) / "PANEL" / "_PROYECTOS" / "MOCK_F10" / "CARGA FORMA 2.xlsx",
        Path(NETWORK_IP) / "PANEL" / "_PROYECTOS" / "MOCK_F10" / "CARGA MAQUINA COMPRESION.xlsx",
        Path(NETWORK_IP) / "PANEL" / "_PROYECTOS" / "MOCK_F10" / "CARGA MAQUINA RETENES.xlsx",
    ]
    
    # Esta carpeta no existe aún en vivo, este script se mandará a integrar 
    # en la ejecución real cambiando los paths a la ubicación verdadera del usuario.
    build_carga_consolidada(TARGETS, dl_dir)
