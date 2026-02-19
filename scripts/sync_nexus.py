r"""
RPK NEXUS - Sincronizador Maestro v2.1 (Historical & Detailed)
==============================================================
Versión avanzada con soporte para:
1. Evolución histórica de Stock y Tiempos.
2. Desglose detallado por Artículo/OF para Tiempos.
3. Normalización robusta y prevención de duplicados.
"""

import os
import sys
import sqlite3
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import shutil
import tempfile
import re
import glob

# --- CONFIGURACIÓN DE RUTAS ---
LOCAL_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DB = os.path.join(LOCAL_BASE, "backend", "db", "rpk_industrial.db")

REMOTE_SERVER = "145.3.0.54"
REMOTE_ROOT = r"\\" + REMOTE_SERVER + r"\ofimatica\Supply Chain\PLAN PRODUCCION"
FOLDER_STOCK = os.path.join(REMOTE_ROOT, "Listado de existencias actuales")
FOLDER_TIME = os.path.join(REMOTE_ROOT, "List Avance Obra-Centro y Operacion")
REMOTE_STOCK_OBJETIVOS = os.path.join(REMOTE_ROOT, "PANEL", "DASHBOARD_STOCK", "backend", "OBJETIVOS_STOCK.xlsx")

def get_latest_file(folder_path, pattern):
    if not os.path.exists(folder_path):
        return None
    files = glob.glob(os.path.join(folder_path, pattern))
    if not files: return None
    try:
        def extract_date(f):
            m = re.search(r'\((\d{4}-\d{2}-\d{2})', os.path.basename(f))
            return m.group(1) if m else "0000-00-00"
        return max(files, key=lambda f: (extract_date(f), os.path.getmtime(f)))
    except:
        return max(files, key=os.path.getmtime)

def clean_val(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).replace(',', '.').replace(' ', ''))
    except: return 0.0

def sync_data():
    t_start = datetime.now()
    print(f"[{t_start.strftime('%H:%M:%S')}] [INFO] Iniciando Sincronización NEXUS v2.1...")
    
    if not os.path.exists(LOCAL_DB):
        print(f"[ERROR] DB no encontrada en {LOCAL_DB}")
        return

    engine = create_engine(f"sqlite:///{LOCAL_DB.replace(os.sep, '/')}")
    temp_dir = tempfile.gettempdir()

    # --- 1. PROCESAR STOCK ---
    try:
        latest_stock_file = get_latest_file(FOLDER_STOCK, "Listado de existencias actuales*.xlsx")
        if latest_stock_file:
            print(f"[STOCK] Usando: {os.path.basename(latest_stock_file)}")
            local_path = os.path.join(temp_dir, "latest_stock.xlsx")
            shutil.copy2(latest_stock_file, local_path)
            
            # Parsing RAW Stock
            df_raw = pd.read_excel(local_path, header=None)
            date_match = re.search(r'\((\d{4}-\d{2}-\d{2})', os.path.basename(latest_stock_file))
            date_str = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')
            
            data_rows = []
            current_customer = "DESCONOCIDO"
            for _, row in df_raw.iterrows():
                if len(row) > 7 and str(row[7]).strip() == "Divisa:EUR":
                    current_customer = str(row[1]).strip()
                    continue
                try:
                    if str(row[0]).strip() == '1' and not pd.isna(row[4]):
                        val_eur = row[7] if not pd.isna(row[7]) else 0.0
                        data_rows.append({
                            'Fecha': date_str, 'Cliente': current_customer,
                            'Articulo': str(row[1]).strip(), 'Descripcion': str(row[2]).strip(),
                            'Cantidad': float(row[4]), 'Valor_Total': float(val_eur)
                        })
                except: continue
            
            df_stock = pd.DataFrame(data_rows)
            if not df_stock.empty:
                # Merge con Objetivos
                if os.path.exists(REMOTE_STOCK_OBJETIVOS):
                    try:
                        shutil.copy2(REMOTE_STOCK_OBJETIVOS, os.path.join(temp_dir, "obj.xlsx"))
                        df_obj = pd.read_excel(os.path.join(temp_dir, "obj.xlsx"))
                        df_obj.columns = [c.strip().upper() for c in df_obj.columns]
                        art_col = [c for c in df_obj.columns if 'ART' in c][0]
                        obj_col = [c for c in df_obj.columns if 'OBJ' in c][0]
                        df_obj = df_obj.rename(columns={art_col: 'Articulo_M', obj_col: 'Stock_Objetivo'})
                        df_obj['Articulo_M'] = df_obj['Articulo_M'].astype(str).str.strip().str.upper()
                        
                        df_stock['Articulo_M'] = df_stock['Articulo'].astype(str).str.strip().str.upper()
                        df_stock = pd.merge(df_stock, df_obj[['Articulo_M', 'Stock_Objetivo']], on='Articulo_M', how='left')
                        df_stock['Stock_Objetivo'] = df_stock['Stock_Objetivo'].fillna(0)
                        df_stock = df_stock.drop(columns=['Articulo_M'])
                    except: df_stock['Stock_Objetivo'] = 0.0
                else: df_stock['Stock_Objetivo'] = 0.0

                # Guardar snapshot (reemplaza hoy) y evolución (acumula)
                with engine.connect() as conn:
                    # Limpiar hoy para evitar duplicados en snapshot y acumulación
                    conn.execute(text(f"DELETE FROM stock_snapshot WHERE Fecha = '{date_str}'"))
                    df_stock.to_sql("stock_snapshot", conn, if_exists="append", index=False)
                    
                    # Evolución Diaria
                    total_val = df_stock['Valor_Total'].sum()
                    conn.execute(text(f"DELETE FROM stock_evolucion WHERE Fecha = '{date_str}'"))
                    pd.DataFrame([{'Fecha': date_str, 'Valor_Total': total_val}]).to_sql("stock_evolucion", conn, if_exists="append", index=False)
                    
                    # Log
                    pd.DataFrame([{'timestamp': datetime.now(), 'modulo': 'STOCK', 'archivo': os.path.basename(latest_stock_file), 'registros': len(df_stock), 'estado': 'OK'}]).to_sql("ingest_logs", conn, if_exists="append", index=False)
                
                print(f"   [OK] Stock actualizado: {len(df_stock)} registros. Valor: {total_val:,.0f}€")

    except Exception as e: print(f"   [ERROR] Stock: {e}")

    # --- 2. PROCESAR TIEMPOS ---
    try:
        latest_time_file = get_latest_file(FOLDER_TIME, "Listado Avance Obra*.xlsx")
        if latest_time_file:
            print(f"[TIEMPOS] Usando: {os.path.basename(latest_time_file)}")
            local_path = os.path.join(temp_dir, "latest_time.xlsx")
            shutil.copy2(latest_time_file, local_path)
            
            df_raw_t = pd.read_excel(local_path)
            date_match = re.search(r'\((\d{4}-\d{2}-\d{2})', os.path.basename(latest_time_file))
            date_str = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')
            
            # Normalizar columnas (busqueda difusa)
            mapping = {}
            for col in df_raw_t.columns:
                c = str(col).upper()
                if 'CENTRO' in c: mapping[col] = 'Centro'
                if 'ART' in c: mapping[col] = 'Articulo'
                if 'TEJEC_DISP' in c or 'TIEMPO EJECUCION DISP' in c: mapping[col] = 'Horas'
                if 'O.F' in c or 'OF' in c or 'ORDEN FABRICACION' in c: mapping[col] = 'OF'

            df_t = df_raw_t.rename(columns=mapping)
            df_t['Centro'] = df_t['Centro'].astype(str).str.strip()
            df_t = df_t[df_t['Centro'].str.len() <= 4] # Filtro centros reales
            df_t['Horas'] = df_t['Horas'].apply(clean_val)
            
            if not df_t.empty:
                # A) Carga por Centro (para dashboard)
                df_centros = df_t.groupby('Centro')['Horas'].sum().reset_index()
                df_centros.columns = ['Centro', 'Carga_Dia']
                df_centros['Fecha'] = date_str
                # Placeholders para compatibilidad
                df_centros['Media_Mensual'] = df_centros['Carga_Dia']
                df_centros['Total_Mes'] = df_centros['Carga_Dia']

                # B) Detalle Artículo (para drilldown)
                df_detalle = df_t.groupby(['Centro', 'Articulo', 'OF'])['Horas'].sum().reset_index()
                df_detalle['Fecha'] = date_str

                with engine.connect() as conn:
                    # Limpiar hoy y guardar
                    conn.execute(text(f"DELETE FROM tiempos_carga WHERE Fecha = '{date_str}'"))
                    df_centros.to_sql("tiempos_carga", conn, if_exists="append", index=False)
                    
                    conn.execute(text(f"DELETE FROM tiempos_detalle_articulo WHERE Fecha = '{date_str}'"))
                    df_detalle.to_sql("tiempos_detalle_articulo", conn, if_exists="append", index=False)
                    
                    # Log
                    pd.DataFrame([{'timestamp': datetime.now(), 'modulo': 'TIEMPOS', 'archivo': os.path.basename(latest_time_file), 'registros': len(df_centros), 'estado': 'OK'}]).to_sql("ingest_logs", conn, if_exists="append", index=False)
                
                print(f"   [OK] Tiempos actualizados: {len(df_centros)} centros, {len(df_detalle)} detalles.")

    except Exception as e: print(f"   [ERROR] Tiempos: {e}")

    t_end = datetime.now()
    print(f"[{t_end.strftime('%H:%M:%S')}] [FIN] Sincronización exitosa ({ (t_end-t_start).total_seconds():.1f}s).")

if __name__ == "__main__":
    sync_data()
