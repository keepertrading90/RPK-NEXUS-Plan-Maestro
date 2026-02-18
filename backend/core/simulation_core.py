import pandas as pd
import os
import time
import functools
from sqlalchemy.orm import Session
from typing import List

# Configuración de rutas para RPK NEXUS
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_PATH = os.path.join(BASE_DIR, "db", "MAESTRO FLEJE_v1.xlsx")

try:
    from backend.db import models_sim as database
except ImportError:
    import sys
    sys.path.append(os.path.dirname(BASE_DIR))
    from backend.db import models_sim as database

print(f"DEBUG:simulation_core: Usando EXCEL_PATH = {EXCEL_PATH}", flush=True)

# Variable global para cachear el DataFrame
_df_cache = None

def time_it(func):
    """Decorador para medir el tiempo de ejecución de las funciones."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        print(f"⏱️ [PERF] {func.__name__} tardó {end_time - start_time:.4f} segundos")
        return result
    return wrapper

def get_base_dataframe():
    """Retorna una copia del DataFrame maestro, usando una caché binaria en disco para velocidad extra."""
    global _df_cache
    CACHE_PATH = EXCEL_PATH + ".cache.pkl"
    
    if _df_cache is not None:
        return _df_cache.copy()

    # Verificar si existe caché y si es más reciente que el Excel
    use_cache = False
    if os.path.exists(CACHE_PATH) and os.path.exists(EXCEL_PATH):
        if os.path.getmtime(CACHE_PATH) > os.path.getmtime(EXCEL_PATH):
            use_cache = True

    try:
        if use_cache:
            print(f"🚀 Cargando desde caché binaria (Modo Ultra Rápido)...", flush=True)
            start_load = time.perf_counter()
            _df_cache = pd.read_pickle(CACHE_PATH)
            end_load = time.perf_counter()
            print(f"✅ Caché cargada en {end_load - start_load:.4f} segundos.", flush=True)
        else:
            print(f"🚀 Cargando Excel Maestro por primera vez desde: {EXCEL_PATH}...", flush=True)
            if not os.path.exists(EXCEL_PATH):
                raise FileNotFoundError(f"No se encuentra el archivo maestro en: {EXCEL_PATH}")
            
            start_load = time.perf_counter()
            _df_cache = pd.read_excel(EXCEL_PATH)
            
            # Limpieza básica inicial
            _df_cache['Articulo'] = _df_cache['Articulo'].astype(str).str.replace(r'\.0$', '', regex=True)
            _df_cache['Centro'] = _df_cache['Centro'].astype(str).str.replace(r'\.0$', '', regex=True)
            _df_cache = _df_cache[~_df_cache['Centro'].isin(['nan', 'NaN', 'None', '', 'nan.0'])].copy()
            
            end_load = time.perf_counter()
            print(f"✅ Excel cargado en {end_load - start_load:.4f} segundos.", flush=True)
            
            # Guardar caché para la próxima vez
            print(f"🔄 Generando caché binaria para acelerar futuros arranques...", flush=True)
            _df_cache.to_pickle(CACHE_PATH)
            
    except Exception as e:
        print(f"❌ Error al cargar DataFrame maestro: {e}")
        return None

    # Asegurar que centro_original existe (por si la caché es vieja)
    if 'centro_original' not in _df_cache.columns:
        _df_cache['centro_original'] = _df_cache['Centro']
        
    return _df_cache.copy()

@time_it
def calculate_saturation(df: pd.DataFrame, dias_laborales_override: int = None, horas_turno_default: int = 16):
    """
    Calcula la saturación basada en las columnas del Excel.
    """
    
    # Aseguramos tipos de datos
    df['Volumen anual'] = pd.to_numeric(df['Volumen anual'], errors='coerce').fillna(0)
    df['Piezas por minuto'] = pd.to_numeric(df['Piezas por minuto'], errors='coerce').fillna(0)
    df['%OEE'] = pd.to_numeric(df['%OEE'], errors='coerce').fillna(0)
    
    # Aseguramos que existe la columna horas_turno (puede venir pre-configurada con overrides)
    if 'horas_turno' not in df.columns:
        df['horas_turno'] = horas_turno_default
    
    # Usar override si existe, sino columna del excel, sino default 238
    if dias_laborales_override is not None:
        df['dias laborales 2026'] = dias_laborales_override
    else:
        df['dias laborales 2026'] = pd.to_numeric(df['dias laborales 2026'], errors='coerce').fillna(238)

    # Aseguramos que existe la columna de setup (puede venir del Excel o ser 0)
    if 'Setup (h)' not in df.columns:
        # Intentar buscar nombres alternativos
        for col in ['Setup', 'Preparacion', 'Tiempo Preparacion']:
            if col in df.columns:
                df['Setup (h)'] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                break
        else:
            df['Setup (h)'] = 0.0
    else:
        df['Setup (h)'] = pd.to_numeric(df['Setup (h)'], errors='coerce').fillna(0)

    # --- NUEVA LÓGICA MOD (PERSONAL) ---
    # 1. Buscar columna en Excel
    if 'Ratio_MOD' not in df.columns:
        for col in ['Ratio MOD', 'Ratio Persona Maquina', 'Ratio Persona Articulo', 'MOD']:
            if col in df.columns:
                df['Ratio_MOD'] = pd.to_numeric(df[col], errors='coerce').fillna(1.0)
                break
        else:
            df['Ratio_MOD'] = 1.0
    else:
        df['Ratio_MOD'] = pd.to_numeric(df['Ratio_MOD'], errors='coerce').fillna(1.0)

    # El Ratio_MOD ya puede venir con pre-overrides de centro o articulo en get_simulation_data

    # Cálculos dinámicos
    df['Piezas por hora'] = df['Piezas por minuto'] * 60
    
    # Manejo de OEE: Si viene como 70 en lugar de 0.70, normalizamos
    # (Asumimos que si hay valores > 1, es escala 0-100)
    oee_mask = df['%OEE'] > 1.1
    df_oee_calc = df['%OEE'].copy()
    if oee_mask.any():
        df_oee_calc = df_oee_calc.apply(lambda x: x/100.0 if x > 1.1 else x)

    # Calculamos horas totales requeridas (Producción + Setup)
    # Evitamos división por cero asegurando que PPH y OEE sean > 0
    denominador = (df['Piezas por hora'] * df_oee_calc)
    df['Horas_Produccion'] = (df['Volumen anual'] / denominador).replace([float('inf'), -float('inf')], 0).fillna(0)
    df['Horas_Totales'] = df['Horas_Produccion'] + df['Setup (h)']
    
    # --- CÁLCULO HORAS HOMBRE (MOD) ---
    # Las horas de preparación (Setup) siempre tienen ratio 1.0 según requerimiento.
    # El Ratio_MOD solo afecta a las horas de producción pura.
    df['Horas_Hombre'] = (df['Horas_Produccion'] * df['Ratio_MOD'].fillna(1.0)) + df['Setup (h)']
    
    # Capacidad Anual en Horas
    df['Capacidad_Anual_H'] = df['dias laborales 2026'] * df['horas_turno']
    
    # % Saturación
    df['Saturacion'] = (df['Horas_Totales'] / df['Capacidad_Anual_H']).replace([float('inf'), -float('inf')], 0).fillna(0)

    # --- CÁLCULO IMPACTO (Peso del artículo sobre el total) ---
    total_horas_global = df['Horas_Totales'].sum()
    if total_horas_global > 0:
        df['Impacto'] = df['Horas_Totales'] / total_horas_global
    else:
        df['Impacto'] = 0.0
    
    return df

@time_it
def get_simulation_data(db: Session, scenario_id: int = None, dias_laborales: int = None, overrides_list: List = None, horas_turno: int = None, center_configs: dict = None):
    # En lugar de pd.read_excel, usamos la caché
    df = get_base_dataframe()
    
    # Asegurar que horas_turno es entero
    h_turno = int(horas_turno) if horas_turno is not None else 16
    df['horas_turno'] = h_turno
    
    # Aplicar configuraciones por centro si existen
    if center_configs:
        for centro, config in center_configs.items():
            mask_c = df['Centro'].astype(str) == str(centro)
            if isinstance(config, dict):
                if 'shifts' in config:
                    df.loc[mask_c, 'horas_turno'] = int(config['shifts'])
                if 'personnel_ratio' in config:
                    df.loc[mask_c, 'Ratio_MOD'] = float(config['personnel_ratio'])
    
    selected_overrides = []
    if scenario_id:
        selected_overrides = db.query(database.ScenarioDetail).filter(database.ScenarioDetail.scenario_id == scenario_id).all()
    elif overrides_list:
        selected_overrides = overrides_list

    for ov in selected_overrides:
        # Pydantic models (de server.py) o SQLAlchemy objects tienen atributos similares
        # Si es un dict (de un payload POST), usamos get, si es objeto usamos getattr
        art = getattr(ov, 'articulo', None) or (ov.articulo if hasattr(ov, 'articulo') else None)
        cen = getattr(ov, 'centro', None) or (ov.centro if hasattr(ov, 'centro') else None)
        
        mask = (df['Articulo'].astype(str) == str(art)) & (df['Centro'].astype(str) == str(cen))
        
        oee = getattr(ov, 'oee_override', None)
        ppm = getattr(ov, 'ppm_override', None)
        dem = getattr(ov, 'demanda_override', None)
        nc = getattr(ov, 'new_centro', None)
        ht = getattr(ov, 'horas_turno_override', None)

        if oee is not None: df.loc[mask, '%OEE'] = oee
        if ppm is not None: df.loc[mask, 'Piezas por minuto'] = ppm
        if dem is not None: df.loc[mask, 'Volumen anual'] = dem
        if nc is not None: df.loc[mask, 'Centro'] = nc
        if ht is not None: df.loc[mask, 'horas_turno'] = ht
        if hasattr(ov, 'personnel_ratio_override') and ov.personnel_ratio_override is not None:
            df.loc[mask, 'Ratio_MOD'] = ov.personnel_ratio_override
        if getattr(ov, 'setup_time_override', None) is not None: 
            df.loc[mask, 'Setup (h)'] = ov.setup_time_override

    d_lab = int(dias_laborales) if dias_laborales is not None else None
    df = calculate_saturation(df, d_lab, h_turno)
    
    # Agrupación por Centro para el resumen de saturación
    centro_summary = df.groupby('Centro').agg({
        'Saturacion': 'sum',
        'Volumen anual': 'sum',
        'Horas_Totales': 'sum',
        'Horas_Hombre': 'sum',
        'Articulo': 'count'
    }).reset_index()
    
    centro_summary.rename(columns={'Articulo': 'Num_Articulos'}, inplace=True)
    
    # Asegurar que no hay NaNs ni Valores Infinitos que rompan el JSON
    df = df.fillna(0).replace([float('inf'), -float('inf')], 0)
    centro_summary = centro_summary.fillna(0).replace([float('inf'), -float('inf')], 0)

    return {
        "detail": df.to_dict(orient="records"),
        "summary": centro_summary.to_dict(orient="records"),
        "meta": {
            "dias_laborales": d_lab if d_lab is not None else 238,
            "horas_turno_global": h_turno,
            "center_configs": center_configs or {},
            "applied_overrides": [
                {
                    "articulo": getattr(ov, 'articulo', None) or (ov.articulo if hasattr(ov, 'articulo') else None),
                    "centro": getattr(ov, 'centro', None) or (ov.centro if hasattr(ov, 'centro') else None),
                    "oee_override": getattr(ov, 'oee_override', None),
                    "ppm_override": getattr(ov, 'ppm_override', None),
                    "demanda_override": getattr(ov, 'demanda_override', None),
                    "new_centro": getattr(ov, 'new_centro', None),
                    "horas_turno_override": getattr(ov, 'horas_turno_override', None),
                    "personnel_ratio_override": getattr(ov, 'personnel_ratio_override', None),
                    "setup_time_override": getattr(ov, 'setup_time_override', None)
                } for ov in selected_overrides
            ] if selected_overrides else []
        }
    }
