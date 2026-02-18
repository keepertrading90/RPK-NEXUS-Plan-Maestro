"""
RPK NEXUS - Sincronizador Local FASE 2
Este script unifica los datos de los dashboards dispersos en la red (Y:) 
hacia la base de datos local RPK NEXUS (C:).
"""

import os
import sqlite3
import pandas as pd
from sqlalchemy import create_engine

# --- CONFIGURACIÓN DE RUTAS ---
# Local (Destino)
LOCAL_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DB = os.path.join(LOCAL_BASE, "backend", "db", "rpk_industrial.db")

# Remotos (Orígenes en Ruta UNC)
REMOTE_STOCK_DB = r"\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_PROYECTOS\DASHBOARD_STOCK\backend\db\rpk_industrial.db"
REMOTE_TIME_DB = r"\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\PANEL\_PROYECTOS\DASHBOARD_TIEMPOS\backend\db\rpk_industrial.db"

def sync_data():
    print("🔄 Iniciando Sincronización Local RPK NEXUS...")
    
    if not os.path.exists(LOCAL_DB):
        print(f"❌ Error: No se encuentra la DB local en {LOCAL_DB}. Ejecute primero migrate_to_nexus.py")
        return

    engine_local = create_engine(f"sqlite:///{LOCAL_DB.replace(os.sep, '/')}")

    # 1. Sincronizar Stock
    if os.path.exists(REMOTE_STOCK_DB):
        print("📊 Sincronizando datos de STOCK desde Red...")
        try:
            engine_rem_stock = create_engine(f"sqlite:///{REMOTE_STOCK_DB.replace(os.sep, '/')}")
            df_stock = pd.read_sql("SELECT * FROM stock_snapshot", engine_rem_stock)
            df_stock.to_sql("stock_snapshot", engine_local, if_exists="replace", index=False)
            print(f"   ✅ {len(df_stock)} registros de stock unificados.")
        except Exception as e:
            print(f"   ⚠️ Error al sincronizar stock: {e}")
    else:
        print("   ⚠️ No se encontró la DB remota de Stock.")

    # 2. Sincronizar Tiempos
    if os.path.exists(REMOTE_TIME_DB):
        print("⏳ Sincronizando datos de TIEMPOS desde Red...")
        try:
            engine_rem_time = create_engine(f"sqlite:///{REMOTE_TIME_DB.replace(os.sep, '/')}")
            df_time = pd.read_sql("SELECT * FROM tiempos_carga", engine_rem_time)
            df_time.to_sql("tiempos_carga", engine_local, if_exists="replace", index=False)
            print(f"   ✅ {len(df_time)} registros de tiempos unificados.")
        except Exception as e:
            print(f"   ⚠️ Error al sincronizar tiempos: {e}")
    else:
        print("   ⚠️ No se encontró la DB remota de Tiempos.")

    print("\n🏁 Proceso de sincronización finalizado.")

if __name__ == "__main__":
    sync_data()
