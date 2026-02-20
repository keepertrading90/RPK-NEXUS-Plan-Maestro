r"""
RPK NEXUS - Sincronizador Maestro v2.3 (Full Analytics Rebuild)
==============================================================
Sigue la lógica de agregación del script original de "Tiempos" y 
reconstruye la historia completa de Stock.
"""

import os
import sqlite3
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import shutil
import tempfile
import re
import glob

# --- CONFIGURACIÓN DE RUTAS ---
LOCAL_BASE = r"C:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS"
LOCAL_DB = os.path.join(LOCAL_BASE, "backend", "db", "rpk_industrial.db")

REMOTE_SERVER = "145.3.0.54"
REMOTE_ROOT = r"\\" + REMOTE_SERVER + r"\ofimatica\Supply Chain\PLAN PRODUCCION"
FOLDER_STOCK = os.path.join(REMOTE_ROOT, "Listado de existencias actuales")
FOLDER_TIME = os.path.join(REMOTE_ROOT, "List Avance Obra-Centro y Operacion")
FOLDER_PEDIDOS = os.path.join(REMOTE_ROOT, "Listado Pedidos Ventas")
REMOTE_STOCK_OBJETIVOS = os.path.join(REMOTE_ROOT, "PANEL", "_PROYECTOS", "DASHBOARD_STOCK", "backend", "OBJETIVOS_STOCK.xlsx")

def clean_val(v):
    if pd.isna(v): return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(' ', '')
    if not s: return 0.0
    # Spanish format support: 1.234,56 -> 1234.56
    if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    s = re.sub(r'[^\d.\-]', '', s)
    try: return float(s) if s else 0.0
    except: return 0.0

def sync_nexus():
    t_start = datetime.now()
    print(f"[{t_start.strftime('%H:%M:%S')}] [INIT] NEXUS v2.3 - Reconstrucción Total...")
    engine = create_engine(f"sqlite:///{LOCAL_DB.replace(os.sep, '/')}")
    temp_dir = tempfile.gettempdir()

    # --- 1. STOCK ---
    print(f"[STOCK] Escaneando historia...")
    all_stock_data = []
    stock_files = sorted(glob.glob(os.path.join(FOLDER_STOCK, "Listado de existencias actuales*.xlsx")))
    stock_by_date = {}
    for f in stock_files:
        m = re.search(r'\((\d{4}-\d{2}-\d{2})', os.path.basename(f))
        if m: stock_by_date[m.group(1)] = f
    
    # Cargar objetivos
    df_obj = None
    if os.path.exists(REMOTE_STOCK_OBJETIVOS):
        try:
            shutil.copy2(REMOTE_STOCK_OBJETIVOS, os.path.join(temp_dir, "obj.xlsx"))
            df_obj = pd.read_excel(os.path.join(temp_dir, "obj.xlsx"))
            df_obj.columns = [c.strip().upper() for c in df_obj.columns]
            art_col = [c for c in df_obj.columns if 'ART' in c][0]
            obj_col = [c for c in df_obj.columns if 'OBJ' in c][0]
            df_obj = df_obj.rename(columns={art_col: 'Articulo', obj_col: 'Stock_Objetivo'})
            df_obj['Articulo'] = df_obj['Articulo'].astype(str).str.strip().str.upper()
        except: pass

    for date_str, path in stock_by_date.items():
        try:
            local_p = os.path.join(temp_dir, f"s_{date_str}.xlsx")
            shutil.copy2(path, local_p)
            df_raw = pd.read_excel(local_p, header=None)
            current_cust = "DESCONOCIDO"
            for _, row in df_raw.iterrows():
                if len(row) > 7 and "Divisa:EUR" in str(row[7]):
                    current_cust = str(row[1]).strip()
                try:
                    if str(row[0]).strip() == '1' and not pd.isna(row[4]):
                        val = clean_val(row[7]) if clean_val(row[7]) > 0 else clean_val(row[9])
                        all_stock_data.append({
                            'Fecha': date_str, 'Cliente': current_cust,
                            'Articulo': str(row[1]).strip(), 'Descripcion': str(row[2]).strip(),
                            'Cantidad': clean_val(row[4]), 'Valor_Total': val
                        })
                except: continue
        except: pass
    
    if all_stock_data:
        df_stock_full = pd.DataFrame(all_stock_data)
        if df_obj is not None:
            df_stock_full['Articulo_M'] = df_stock_full['Articulo'].astype(str).str.strip().str.upper()
            df_stock_full = pd.merge(df_stock_full, df_obj[['Articulo', 'Stock_Objetivo']], left_on='Articulo_M', right_on='Articulo', how='left', suffixes=('', '_obj'))
            df_stock_full['Stock_Objetivo'] = df_stock_full['Stock_Objetivo'].fillna(0)
            df_stock_full = df_stock_full.drop(columns=['Articulo_M', 'Articulo_obj'])
        else: df_stock_full['Stock_Objetivo'] = 0.0

        df_evol = df_stock_full.groupby('Fecha')['Valor_Total'].sum().reset_index()

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM stock_snapshot"))
            df_stock_full.to_sql("stock_snapshot", conn, if_exists="append", index=False)
            conn.execute(text("DELETE FROM stock_evolucion"))
            df_evol.to_sql("stock_evolucion", conn, if_exists="append", index=False)
        print(f"  [OK] Stock: {len(df_stock_full)} registros inyectados.")

    # --- 2. TIEMPOS (Agregación histórica según ANALISIS_MENSUAL_TIEMPOS.PY) ---
    print(f"[TIEMPOS] Procesando historia...")
    all_time_rows = []
    time_files = sorted(glob.glob(os.path.join(FOLDER_TIME, "*.xlsx")))
    time_by_date = {}
    for f in time_files:
        m = re.search(r'\((\d{4}-\d{2}-\d{2})', os.path.basename(f))
        if m:
            date_str = m.group(1)
            # LOGICA DE CAPTURA DIARIA:
            # Se utiliza la PRIMERA captura del día (usualmente entre 06:00 y 08:00 AM)
            # Esto captura la carga planificada completa antes de que las OFs cerradas
            # desaparezcan del listado de Avance de Obra en capturas posteriores (ej: tarde).
            # Ejemplo: Día 2026-02-19 Centro 782 -> Mañana (291h) vs Tarde (258h).
            if date_str not in time_by_date:
                time_by_date[date_str] = f
            elif os.path.basename(f) < os.path.basename(time_by_date[date_str]):
                time_by_date[date_str] = f

    for date_str, path in time_by_date.items():
        try:
            local_p = os.path.join(temp_dir, f"t_{date_str}.xlsx")
            shutil.copy2(path, local_p)
            df_t_raw = pd.read_excel(local_p)
            
            mapping = {}
            for col in df_t_raw.columns:
                c = str(col).upper()
                if 'CENTRO' in c: mapping[col] = 'Centro'
                if 'ART' in c: mapping[col] = 'Articulo'
                if 'TEJEC_DISP' in c or 'TIEMPO EJECUCION DISP' in c or 'TEJEC_D' in c: mapping[col] = 'Horas'
                if 'TEJEC PTE' in c or 'TIEMPO EJECUCION PTE' in c or 'T.EJEC P' in c: mapping[col] = 'Horas_Pte'
                if 'O.F' in c or 'OF' in c: mapping[col] = 'OF'
            
            df_t = df_t_raw.rename(columns=mapping)
            # Asegurar que existan ambas columnas aunque el Excel varíe
            if 'Horas' not in df_t.columns: df_t['Horas'] = 0
            if 'Horas_Pte' not in df_t.columns: df_t['Horas_Pte'] = 0

            df_t['Centro'] = df_t['Centro'].astype(str).str.strip()
            df_t = df_t[df_t['Centro'].str.len() <= 4]
            
            # Lógica de fallback: si Disponible es 0, usamos Pendiente
            def get_final_h(r):
                h = clean_val(r.get('Horas'))
                if h > 0: return h
                return clean_val(r.get('Horas_Pte'))
            
            df_t['Horas_Final'] = df_t.apply(get_final_h, axis=1)
            df_t['Horas_Pte_Val'] = df_t['Horas_Pte'].apply(clean_val)
            df_t['Fecha'] = date_str
            all_time_rows.append(df_t[['Fecha', 'Centro', 'Articulo', 'OF', 'Horas_Final', 'Horas_Pte_Val']])
        except: pass

    if all_time_rows:
        df_all_t = pd.concat(all_time_rows, ignore_index=True)
        # 1. Carga Diaria Agregada
        df_diario = df_all_t.groupby(['Fecha', 'Centro'])['Horas_Final'].sum().reset_index()
        df_diario.columns = ['Fecha', 'Centro', 'Carga_Dia']
        
        # 2. Medias Mensuales (Aquí es donde agrupamos de verdad)
        df_diario['Mes'] = df_diario['Fecha'].str[:7] # YYYY-MM
        df_mensual = df_diario.groupby(['Mes', 'Centro'])['Carga_Dia'].agg(
            Media_Mensual='mean',
            Total_Mes='sum'
        ).reset_index()
        
        df_carga_final = pd.merge(df_diario, df_mensual, on=['Mes', 'Centro'], how='left')
        df_carga_final = df_carga_final[['Fecha', 'Centro', 'Carga_Dia', 'Media_Mensual', 'Total_Mes']]

        # 3. Detalle para drilldown: Sumamos 'Horas_Final' para el % de impacto, 
        # pero tomamos el MAX de 'Horas_Pte' para reflejar el estado de la orden.
        df_detalle = df_all_t.groupby(['Fecha', 'Centro', 'Articulo', 'OF']).agg({
            'Horas_Final': 'sum',
            'Horas_Pte_Val': 'max'
        }).reset_index()
        df_detalle.columns = ['Fecha', 'Centro', 'Articulo', 'OF', 'Horas', 'Horas_Pte']

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM tiempos_carga"))
            df_carga_final.to_sql("tiempos_carga", conn, if_exists="replace", index=False)
            conn.execute(text("DELETE FROM tiempos_detalle_articulo"))
            df_detalle.to_sql("tiempos_detalle_articulo", conn, if_exists="replace", index=False)
        print(f"  [OK] Tiempos: {len(df_carga_final)} fotos de carga y {len(df_detalle)} detalles inyectados.")

    # --- 3. PEDIDOS DE VENTA ---
    print(f"[PEDIDOS] Procesando historia...")
    all_orders = []
    order_files = sorted(glob.glob(os.path.join(FOLDER_PEDIDOS, "*.xlsx")))
    orders_by_date = {}
    for f in order_files:
        m = re.search(r'\((\d{4}-\d{2}-\d{2})', os.path.basename(f))
        if m:
            date_str = m.group(1)
            # SNAPSHOT MATUTINO: Preferimos la primera captura del día
            if date_str not in orders_by_date:
                orders_by_date[date_str] = f
            elif os.path.basename(f) < os.path.basename(orders_by_date[date_str]):
                orders_by_date[date_str] = f

    for date_str, path in orders_by_date.items():
        try:
            local_p = os.path.join(temp_dir, f"pv_{date_str}.xlsx")
            shutil.copy2(path, local_p)
            df_pv = pd.read_excel(local_p)
            
            # Limpieza: Buscar la cabecera real (F.Pedido o F.Ent.Prev suele estar en filas bajas)
            # Pero en este Excel parece estar en la primera fila, con ruido después.
            # Filtrar filas que no tengan información útil (ej: separadores '----------')
            df_pv = df_pv.dropna(subset=['Articulo', 'Pendient.'])
            df_pv = df_pv[df_pv['Articulo'].astype(str).str.strip() != '----------']
            # Omitir filas de cabeceras de cliente
            df_pv = df_pv[~df_pv['Articulo'].astype(str).str.contains('Cliente:', na=False)]
            
            for _, row in df_pv.iterrows():
                try:
                    all_orders.append({
                        'Fecha_Snapshot': date_str,
                        'Fecha_Entrega': str(row['F.Ent.Prev'])[:10] if not pd.isna(row['F.Ent.Prev']) else None,
                        'Fecha_Pedido': str(row['F.Pedido'])[:10] if not pd.isna(row['F.Pedido']) else None,
                        'Articulo': str(row['Articulo']).strip(),
                        'Referencia': str(row['Referencia']).strip() if not pd.isna(row['Referencia']) else "",
                        'Cant_Pendiente': clean_val(row['Pendient.']),
                        'Importe_EUR': clean_val(row['Importe'])
                    })
                except: continue
        except: pass

    if all_orders:
        df_orders_final = pd.DataFrame(all_orders)
        with engine.begin() as conn:
            df_orders_final.to_sql("pedidos_venta", conn, if_exists="replace", index=False)
        print(f"  [OK] Pedidos: {len(df_orders_final)} registros históricos inyectados.")

    print(f"[FIN] NEXUS DB Sincronizada con éxito en {(datetime.now()-t_start).total_seconds():.1f}s.")

if __name__ == "__main__":
    sync_nexus()
