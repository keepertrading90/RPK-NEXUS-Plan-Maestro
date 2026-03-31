"""
RPK NEXUS - ETL Cabeceras Fase 10 v2.1
=======================================
Lee los 5 Excel de planificación (fuente de verdad de Fase 10):
  - CARGA FLEJE 2.xlsm       (UATC Forma-Fleje / PLANIFICACION)
  - CARGA PRENSAS 2.xlsm     (UATC Forma-Fleje / PLANIFICACION)
  - CARGA FORMA 2.xlsm       (MESA UATC Tarragona - UATC RETENES-COMPRESION)
  - CARGA MAQUINA COMPRESION.xlsx  (MESA UATC Tarragona - UATC RETENES-COMPRESION)
  - CARGA MAQUINA RETENES.xlsx     (MESA UATC Tarragona - UATC RETENES-COMPRESION)

Estructura real de los Excel:
  - Fila 0: Título general (fecha actualización)
  - Fila 2: IDs de centro (ej: 109, 127, 207, 214, 782...)
  - Fila 3: Cabeceras de columna (OF'S, ARTÍCULO, CANTIDAD, HORAS NECESARIAS, MATERIAL)
  - Fila 4+: Datos de órdenes (pueden estar en WIP o en cola)

Cada archivo puede tener MÚLTIPLES centros dispuestos en columnas horizontales.
"""
import pandas as pd
import numpy as np
import shutil
import tempfile
import logging
import re
from pathlib import Path
from datetime import datetime

warnings_import = None
try:
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning)
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [ETL-FASE10-v2.1] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _safe_read_excel(file_path: Path) -> pd.DataFrame | None:
    """
    Lee un Excel con copia temporal para evitar Permission Denied (archivos abiertos).
    Patrón de resiliencia de red: si hay File Lock, registra warning y retorna None.
    """
    tmp_path = None
    try:
        # Copia a temp para evitar bloqueo del archivo original
        suffix = file_path.suffix
        tmp_path = Path(tempfile.gettempdir()) / f"nexus_fase10_{file_path.stem}_{datetime.now().strftime('%H%M%S')}{suffix}"
        shutil.copy2(file_path, tmp_path)
        df = pd.read_excel(tmp_path, header=None, engine='calamine')
        return df
    except PermissionError:
        logger.warning(f"[File Lock] {file_path.name} está abierto. Saltando silenciosamente.")
        return None
    except FileNotFoundError:
        logger.warning(f"[No encontrado] {file_path.name}")
        return None
    except Exception as e:
        logger.error(f"[Error leyendo] {file_path.name}: {e}")
        return None
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def _extract_numero_centro(cell_value: str) -> str | None:
    """Extrae un número de centro válido de una celda (ej: '109', 'MÁQUINA 109' -> '109')."""
    if not cell_value or str(cell_value).strip().lower() in ('nan', '', 'none'):
        return None
    match = re.search(r'\b\d{3,6}\b', str(cell_value))
    if match:
        return match.group()
    return None


def extract_centros_from_excel(df_raw: pd.DataFrame, source_name: str, fecha_str: str) -> pd.DataFrame:
    """
    Parsea la estructura horizontal multi-centro de los Excel de Fase 10.

    Estrategia vectorizada:
    1. Busca la fila de IDs de centro (números 3-6 dígitos en la fila 2 aproximadamente)
    2. Busca la fila de cabeceras (contiene 'OF' y 'ART')
    3. Extrae bloques de datos por cada bloque de columnas de centro
    """
    df_str = df_raw.fillna('').astype(str)
    df_str = pd.DataFrame(
        {col: df_str[col].str.strip() for col in df_str.columns},
        index=df_str.index
    )

    # ──────────────────────────────────────────────
    # 1. Localizar fila con IDs de centro
    # ──────────────────────────────────────────────
    centro_row_idx = None
    header_row_idx = None

    for i, row in df_str.iterrows():
        row_vals = [str(v) for v in row.tolist()]
        # La fila de centros tiene números de 3+ dígitos en múltiples columnas
        centros_found = [v for v in row_vals if re.search(r'^\d{3,6}$', v)]
        if len(centros_found) >= 1:
            centro_row_idx = i
            break

    # ──────────────────────────────────────────────
    # 2. Localizar fila de cabeceras (OF, ARTÍCULO, CANTIDAD...)
    # ──────────────────────────────────────────────
    if centro_row_idx is not None:
        for i in range(centro_row_idx, min(centro_row_idx + 5, len(df_str))):
            row_lower = df_str.iloc[i].str.lower()
            if row_lower.str.contains(r'of|o\.f', regex=True).any() and \
               row_lower.str.contains(r'art', regex=True).any():
                header_row_idx = i
                break

    if centro_row_idx is None or header_row_idx is None:
        logger.warning(f"No se detectó estructura multi-centro en {source_name}. "
                       f"(centro_row={centro_row_idx}, header_row={header_row_idx})")
        return pd.DataFrame()

    logger.info(f"{source_name}: fila_centros={centro_row_idx}, fila_headers={header_row_idx}")

    # ──────────────────────────────────────────────
    # 3. Detectar pares (centro, columna_inicio) desde la fila de centros
    # ──────────────────────────────────────────────
    centro_row = df_str.iloc[centro_row_idx]
    header_row = df_str.iloc[header_row_idx].str.lower()

    # Encontrar columnas donde hay un ID de centro
    centro_cols = {}
    for col_idx, val in enumerate(centro_row):
        centro_id = _extract_numero_centro(val)
        if centro_id:
            centro_cols[col_idx] = centro_id

    if not centro_cols:
        logger.warning(f"No se encontraron IDs de centro en {source_name}")
        return pd.DataFrame()

    # ──────────────────────────────────────────────
    # 4. Extraer datos por cada bloque de centro
    # ──────────────────────────────────────────────
    all_blocks = []
    data_start_row = header_row_idx + 1
    df_data = df_raw.iloc[data_start_row:].reset_index(drop=True)
    df_data_str = df_str.iloc[data_start_row:].reset_index(drop=True)

    centro_positions = sorted(centro_cols.keys())

    for pos_idx, col_start in enumerate(centro_positions):
        centro_id = centro_cols[col_start]

        # Determinar columnas del bloque: desde col_start hasta antes del siguiente centro
        if pos_idx + 1 < len(centro_positions):
            col_end = centro_positions[pos_idx + 1]
        else:
            col_end = df_raw.shape[1]

        # Mapear columnas del bloque usando la fila de cabeceras
        block_headers = header_row.iloc[col_start:col_end]
        col_map = {}
        for rel_idx, h in enumerate(block_headers):
            h = str(h)  # garantizar str antes de regex
            abs_col = col_start + rel_idx
            if re.search(r"of|o\.f'?s?", h):
                col_map[abs_col] = 'OF'
            elif re.search(r'art', h):
                col_map[abs_col] = 'Articulo'
            elif re.search(r'cant', h):
                col_map[abs_col] = 'Cantidad'
            elif re.search(r'hora', h):
                col_map[abs_col] = 'Horas_Necesarias'
            elif re.search(r'mat', h):
                col_map[abs_col] = 'Material'

        if 'Articulo' not in col_map.values():
            logger.warning(f"{source_name} / Centro {centro_id}: no se detectó columna Artículo.")
            continue

        # Extraer el bloque vectorizado
        block_cols = list(range(col_start, col_end))
        chunk = df_data.iloc[:, [c for c in block_cols if c < df_data.shape[1]]].copy()
        chunk.columns = range(len(chunk.columns))

        # Renombrar columnas según mapeo relativo
        rel_col_map = {}
        for abs_col, name in col_map.items():
            rel_col = abs_col - col_start
            if rel_col < len(chunk.columns):
                rel_col_map[rel_col] = name
        chunk = chunk.rename(columns=rel_col_map)

        # Eliminar posibles columnas duplicadas por nombre (e.g. dos 'OF' detectadas)
        chunk = chunk.loc[:, ~chunk.columns.duplicated()].copy()

        # Asegurar columnas requeridas
        for req in ['OF', 'Articulo', 'Cantidad', 'Horas_Necesarias']:
            if req not in chunk.columns:
                chunk[req] = np.nan

        chunk = chunk[['OF', 'Articulo', 'Cantidad', 'Horas_Necesarias']].copy()

        # Limpiar filas vacías (artículo vacío o NaN)
        chunk_str = chunk['Articulo'].astype(str).str.strip()
        chunk = chunk[chunk_str.notna() & (chunk_str != '') & (chunk_str != 'nan')]

        if chunk.empty:
            continue

        # Añadir metadatos
        chunk['Centro_Cabecera'] = centro_id
        chunk['Origen'] = source_name
        chunk['Fecha_Carga'] = fecha_str
        chunk['Orden_Secuencia'] = np.arange(1, len(chunk) + 1)

        all_blocks.append(chunk)
        logger.info(f"  Centro {centro_id}: {len(chunk)} órdenes extraídas.")

    if all_blocks:
        df_result = pd.concat(all_blocks, ignore_index=True)
        return df_result
    return pd.DataFrame()


def process_file_fase10(file_path: Path) -> pd.DataFrame:
    """Ingesta completa de un Excel Fase 10: copia temp → parse → limpieza vectorizada."""
    df_raw = _safe_read_excel(file_path)
    if df_raw is None:
        return pd.DataFrame()

    fecha_str = datetime.now().strftime("%Y-%m-%d")
    df_clean = extract_centros_from_excel(df_raw, file_path.stem, fecha_str)

    if not df_clean.empty:
        # Limpieza matricial final
        df_clean['Cantidad'] = pd.to_numeric(df_clean['Cantidad'], errors='coerce').fillna(0)
        df_clean['Horas_Necesarias'] = pd.to_numeric(df_clean['Horas_Necesarias'], errors='coerce').fillna(0)
        
        # String cleaning robusto (usando .astype(str).str.strip() individualmente)
        def clean_series(s):
            return s.astype(str).str.replace('nan', '', case=False).str.strip()

        df_clean['Articulo'] = clean_series(df_clean['Articulo'])
        df_clean['Centro_Cabecera'] = clean_series(df_clean['Centro_Cabecera'])
        df_clean['OF'] = clean_series(df_clean['OF'])

        # Filtrar filas con horas = 0 (OFs ya terminadas en la secuencia)
        df_clean = df_clean[df_clean['Horas_Necesarias'] > 0].copy()

    return df_clean


def build_carga_consolidada(target_paths: list, data_lake_dir: Path) -> Path | None:
    """
    Orquesta la lectura de los 5 Excels, los fusiona y los inyecta en el Data Lake (Parquet).
    Patrón Zero-Latency: fallo de un archivo no tumba el ETL.
    """
    dfs = []
    for fpath in target_paths:
        f = Path(fpath)
        if f.exists():
            logger.info(f"Ingestando Fase 10 → {f.name}")
            df = process_file_fase10(f)
            if not df.empty:
                dfs.append(df)
                logger.info(f"  [{f.stem}] {len(df)} órdenes activas detectadas.")
            else:
                logger.warning(f"  [{f.stem}] Sin datos extraíbles.")
        else:
            logger.warning(f"Archivo no encontrado: {f}")

    if not dfs:
        logger.warning("No se pudo recolectar data de Fase 10. Abortando guardado.")
        return None

    df_final = pd.concat(dfs, ignore_index=True)

    # Cast a str para compatibilidad Parquet
    for col in df_final.select_dtypes(include='object').columns:
        df_final[col] = df_final[col].astype(str)

    # Partición temporal (snapshot del día — sobrescribe el anterior del mismo día)
    now = datetime.now()
    partition_path = (
        data_lake_dir / "transaccional" / "carga_cabeceras"
        / f"year={now.year}" / f"month={now.month:02d}"
    )
    partition_path.mkdir(parents=True, exist_ok=True)

    final_file = partition_path / f"carga_cabeceras_{now.strftime('%Y%m%d')}.parquet"
    df_final.to_parquet(final_file, engine='pyarrow', index=False)
    logger.info(f"[OK] {len(df_final)} órdenes Fase 10 guardadas → {final_file}")
    return final_file


if __name__ == "__main__":
    from pathlib import Path as P
    base_dir = P(__file__).resolve().parent.parent
    dl_dir = base_dir / "backend" / "data_lake"
    ONEDRIVE = P(r"C:\Users\ismael.rodriguez\OneDrive - RPK S COOP")

    TARGETS = [
        ONEDRIVE / "UATC Forma-Fleje" / "PLANIFICACION" / "CARGA FLEJE 2.xlsm",
        ONEDRIVE / "UATC Forma-Fleje" / "PLANIFICACION" / "CARGA PRENSAS 2.xlsm",
        ONEDRIVE / "MESA UATC Tarragona - UATC RETENES-COMPRESION" / "CARGA FORMA 2.xlsm",
        ONEDRIVE / "MESA UATC Tarragona - UATC RETENES-COMPRESION" / "CARGA MAQUINA COMPRESION.xlsx",
        ONEDRIVE / "MESA UATC Tarragona - UATC RETENES-COMPRESION" / "CARGA MAQUINA RETENES.xlsx",
    ]

    result = build_carga_consolidada(TARGETS, dl_dir)
    if result:
        import pandas as pd
        df_check = pd.read_parquet(result)
        print(f"\n=== PARQUET GENERADO: {result.name} ===")
        print(f"Total órdenes: {len(df_check)}")
        print(f"Centros detectados: {sorted(df_check['Centro_Cabecera'].unique())}")
        print(df_check.head(10).to_string())
