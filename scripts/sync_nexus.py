"""
RPK NEXUS - Sincronizador Maestro (Perfect Migration - High Performance)
Este script centraliza los datos de diversos orígenes (Excel y SQLite en red)
hacia la base de datos local RPK NEXUS (rpk_industrial.db).
Optimizado con copia local previa para evitar latencia de red en Pandas.
"""

import os
import sqlite3
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import shutil
import tempfile

# --- CONFIGURACIÓN DE RUTAS ---
LOCAL_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DB = os.path.join(LOCAL_BASE, "backend", "db", "rpk_industrial.db")

# Fuentes de Red (UNC) - Usamos IPs para mayor estabilidad
REMOTE_SERVER = "145.3.0.54"
REMOTE_PATH = r"\\"+REMOTE_SERVER+r"\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_PROYECTOS"

REMOTE_STOCK_EXCEL = os.path.join(REMOTE_PATH, "DASHBOARD_STOCK", "backend", "RESUMEN_STOCK.xlsx")
REMOTE_STOCK_OBJETIVOS = os.path.join(REMOTE_PATH, "DASHBOARD_STOCK", "backend", "OBJETIVOS_STOCK.xlsx")
REMOTE_TIME_EXCEL = os.path.join(REMOTE_PATH, "DASHBOARD_TIEMPOS", "backend", "ANALISIS_MENSUAL_TIEMPOS_V2.xlsx")

def sync_data():
    t_now = datetime.now().strftime('%H:%M:%S')
    print(f"[{t_now}] [INFO] Iniciando Sincronizacion Maestro RPK NEXUS...")
    
    if not os.path.exists(LOCAL_DB):
        print(f"[ERROR] No se encuentra la DB local en {LOCAL_DB}. Ejecute primero migrate_to_nexus.py")
        return

    engine_local = create_engine(f"sqlite:///{LOCAL_DB.replace(os.sep, '/')}")
    temp_dir = tempfile.gettempdir()

    def local_excel_load(remote_path):
        if not os.path.exists(remote_path):
            return None
        local_path = os.path.join(temp_dir, os.path.basename(remote_path))
        print(f"   [SYNC] Copiando {os.path.basename(remote_path)} a local...")
        shutil.copy2(remote_path, local_path)
        return pd.ExcelFile(local_path)

    # --- 1. SINCRONIZACION DE STOCK ---
    try:
        xl_stock = local_excel_load(REMOTE_STOCK_EXCEL)
        if xl_stock:
            print("[INFO] Procesando datos de STOCK...")
            
            # 1.1 Cargar Objetivos
            df_obj = None
            if os.path.exists(REMOTE_STOCK_OBJETIVOS):
                try:
                    local_obj_path = os.path.join(temp_dir, os.path.basename(REMOTE_STOCK_OBJETIVOS))
                    shutil.copy2(REMOTE_STOCK_OBJETIVOS, local_obj_path)
                    df_obj_raw = pd.read_excel(local_obj_path)
                    df_obj_raw.columns = [c.strip() for c in df_obj_raw.columns]
                    obj_cols = [c for c in df_obj_raw.columns if 'OBJETIVO' in c.upper()]
                    art_cols = [c for c in df_obj_raw.columns if 'ARTICULO' in c.upper() or 'ART' in c.upper()]
                    if obj_cols and art_cols:
                        df_obj = df_obj_raw.rename(columns={art_cols[0]: 'Articulo', obj_cols[0]: 'Stock_Objetivo'})
                        df_obj['Articulo'] = df_obj['Articulo'].astype(str).str.strip().str.upper()
                except: pass
            
            if df_obj is None and 'STOCK MEDIO-ARTICULO OBJETIVO' in xl_stock.sheet_names:
                df_obj_raw = xl_stock.parse('STOCK MEDIO-ARTICULO OBJETIVO')
                df_obj_raw.columns = [c.strip() for c in df_obj_raw.columns]
                obj_cols = [c for c in df_obj_raw.columns if 'OBJETIVO' in c.upper()]
                art_cols = [c for c in df_obj_raw.columns if 'ARTICULO' in c.upper() or 'ART' in c.upper()]
                if obj_cols and art_cols:
                    df_obj = df_obj_raw.rename(columns={art_cols[0]: 'Articulo', obj_cols[0]: 'Stock_Objetivo'})
                    df_obj['Articulo'] = df_obj['Articulo'].astype(str).str.strip().str.upper()

            # 1.2 Detalle actual
            if 'Datos_Detalle' in xl_stock.sheet_names:
                df_det = xl_stock.parse('Datos_Detalle')
                df_det['Articulo_Merge'] = df_det['Articulo'].astype(str).str.strip().str.upper()
                if df_obj is not None:
                    df_det = pd.merge(df_det, df_obj[['Articulo', 'Stock_Objetivo']], 
                                    left_on='Articulo_Merge', right_on='Articulo', 
                                    how='left', suffixes=('', '_new'))
                    if 'Stock_Objetivo_new' in df_det.columns:
                        df_det['Stock_Objetivo'] = df_det['Stock_Objetivo_new'].fillna(0)
                        df_det = df_det.drop(columns=['Stock_Objetivo_new', 'Articulo_y']).rename(columns={'Articulo_x': 'Articulo'})
                
                df_det.to_sql("stock_snapshot", engine_local, if_exists="replace", index=False)
                print(f"   [OK] stock_snapshot: {len(df_det)} registros.")
            
            # 1.3 Evolucion
            if 'Evolucion_Diaria' in xl_stock.sheet_names:
                df_ev = xl_stock.parse('Evolucion_Diaria')
                df_ev.to_sql("stock_evolucion", engine_local, if_exists="replace", index=False)
                print(f"   [OK] stock_evolucion: {len(df_ev)} registros.")
    except Exception as e:
        print(f"   [WARN] Error Stock: {e}")

    # --- 2. SINCRONIZACION DE TIEMPOS ---
    try:
        xl_time = local_excel_load(REMOTE_TIME_EXCEL)
        if xl_time:
            print("[INFO] Procesando datos de TIEMPOS...")
            if 'Datos_Centros' in xl_time.sheet_names:
                df_c = xl_time.parse('Datos_Centros')
                df_c.to_sql("tiempos_carga", engine_local, if_exists="replace", index=False)
                print(f"   [OK] tiempos_carga: {len(df_c)} registros.")
            
            if 'Datos_Centro_Articulo' in xl_time.sheet_names:
                df_ca = xl_time.parse('Datos_Centro_Articulo')
                df_ca.to_sql("tiempos_detalle_articulo", engine_local, if_exists="replace", index=False)
                print(f"   [OK] tiempos_detalle_articulo: {len(df_ca)} registros.")
    except Exception as e:
        print(f"   [WARN] Error Tiempos: {e}")

    t_end = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{t_end}] [FIN] Proceso de sincronizacion finalizado.")

if __name__ == "__main__":
    sync_data()
