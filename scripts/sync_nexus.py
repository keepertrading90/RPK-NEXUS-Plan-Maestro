"""
RPK NEXUS - Sincronizador Maestro (Perfect Migration)
Este script centraliza los datos de diversos orígenes (Excel y SQLite en red)
hacia la base de datos local RPK NEXUS (rpk_industrial.db).
Optimizado para eliminar la latencia de lectura de Excel en el servidor FastAPI.
"""

import os
import sqlite3
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# --- CONFIGURACIÓN DE RUTAS ---
LOCAL_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DB = os.path.join(LOCAL_BASE, "backend", "db", "rpk_industrial.db")

# Fuentes de Red (UNC) - Rutas especificadas por el usuario
REMOTE_STOCK_EXCEL = r"\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_PROYECTOS\DASHBOARD_STOCK\backend\RESUMEN_STOCK.xlsx"
REMOTE_TIME_EXCEL = r"\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_PROYECTOS\DASHBOARD_TIEMPOS\ANALISIS_MENSUAL_TIEMPOS_V2.xlsx"

# Opcional: Fuentes SQLite (para retrocompatibilidad o redundancia)
REMOTE_STOCK_DB = r"\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_PROYECTOS\DASHBOARD_STOCK\backend\db\rpk_industrial.db"
REMOTE_TIME_DB = r"\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_PROYECTOS\DASHBOARD_TIEMPOS\backend\db\rpk_industrial.db"

def sync_data():
    t_now = datetime.now().strftime('%H:%M:%S')
    print(f"[{t_now}] [INFO] Iniciando Sincronizacion Maestro RPK NEXUS...")
    
    if not os.path.exists(LOCAL_DB):
        print(f"[ERROR] No se encuentra la DB local en {LOCAL_DB}. Ejecute primero migrate_to_nexus.py")
        return

    engine_local = create_engine(f"sqlite:///{LOCAL_DB.replace(os.sep, '/')}")

    # --- 1. SINCRONIZACION DE STOCK ---
    if os.path.exists(REMOTE_STOCK_EXCEL):
        print("[INFO] Importando datos de STOCK desde Excel (Red)...")
        try:
            xl = pd.ExcelFile(REMOTE_STOCK_EXCEL)
            
            # Detalle actual (SNAPSHOT)
            if 'Datos_Detalle' in xl.sheet_names:
                df_det = xl.parse('Datos_Detalle')
                df_det.to_sql("stock_snapshot", engine_local, if_exists="replace", index=False)
                print(f"   [OK] stock_snapshot: {len(df_det)} registros.")
            
            # Evolucion historica
            if 'Evolucion_Diaria' in xl.sheet_names:
                df_ev = xl.parse('Evolucion_Diaria')
                df_ev.to_sql("stock_evolucion", engine_local, if_exists="replace", index=False)
                print(f"   [OK] stock_evolucion: {len(df_ev)} registros.")

            # Objetivos (si existen)
            if 'Objetivos' in xl.sheet_names:
                df_obj = xl.parse('Objetivos')
                df_obj.to_sql("stock_objetivos", engine_local, if_exists="replace", index=False)
                print(f"   [OK] stock_objetivos: {len(df_obj)} registros.")

        except Exception as e:
            print(f"   [WARN] Error procesando Excel de Stock: {e}")
    elif os.path.exists(REMOTE_STOCK_DB):
        print("[INFO] Sincronizando datos de STOCK desde DB remota...")
        try:
            engine_rem = create_engine(f"sqlite:///{REMOTE_STOCK_DB.replace(os.sep, '/')}")
            df = pd.read_sql("SELECT * FROM stock_snapshot", engine_rem)
            df.to_sql("stock_snapshot", engine_local, if_exists="replace", index=False)
            print(f"   [OK] stock_snapshot: {len(df)} registros.")
        except Exception as e:
            print(f"   [ERROR] {e}")
    else:
        print("[WARN] No se encontro ninguna fuente de Stock (Excel o DB).")

    # --- 2. SINCRONIZACION DE TIEMPOS ---
    if os.path.exists(REMOTE_TIME_EXCEL):
        print("[INFO] Importando datos de TIEMPOS desde Excel (Red)...")
        try:
            xl = pd.ExcelFile(REMOTE_TIME_EXCEL)
            
            if 'Datos_Centros' in xl.sheet_names:
                df_c = xl.parse('Datos_Centros')
                df_c.to_sql("tiempos_carga", engine_local, if_exists="replace", index=False)
                print(f"   [OK] tiempos_carga: {len(df_c)} registros.")
            
            if 'Datos_Centro_Articulo' in xl.sheet_names:
                df_ca = xl.parse('Datos_Centro_Articulo')
                df_ca.to_sql("tiempos_detalle_articulo", engine_local, if_exists="replace", index=False)
                print(f"   [OK] tiempos_detalle_articulo: {len(df_ca)} registros.")

        except Exception as e:
            print(f"   [WARN] Error procesando Excel de Tiempos: {e}")
    elif os.path.exists(REMOTE_TIME_DB):
        print("[INFO] Sincronizando datos de TIEMPOS desde DB remota...")
        try:
            engine_rem = create_engine(f"sqlite:///{REMOTE_TIME_DB.replace(os.sep, '/')}")
            df = pd.read_sql("SELECT * FROM tiempos_carga", engine_rem)
            df.to_sql("tiempos_carga", engine_local, if_exists="replace", index=False)
            print(f"   [OK] tiempos_carga: {len(df)} registros.")
        except Exception as e:
            print(f"   [ERROR] {e}")
    else:
        print("[WARN] No se encontro ninguna fuente de Tiempos (Excel o DB).")

    t_end = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{t_end}] [FIN] Proceso de sincronizacion finalizado.")

if __name__ == "__main__":
    sync_data()
