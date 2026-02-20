import sqlite3
import pandas as pd

def query_db(query, args=(), one=False):
    db_path = r"C:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_industrial.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

centro_id = "782"
mes = "2026-02"

q = "SELECT Articulo, OF, Horas, Horas_Pte, Fecha FROM tiempos_detalle_articulo WHERE Centro = ? AND Fecha LIKE ?"
data = query_db(q, (centro_id, f"{mes}%"))

if data:
    df = pd.DataFrame([dict(r) for r in data])
    total_horas = df['Horas'].sum()
    
    res = df.groupby(['Articulo', 'OF']).agg({
        'Horas': 'sum',
        'Horas_Pte': 'max',
        'Fecha': 'nunique'
    }).reset_index().rename(columns={'Fecha': 'dias'})
    
    res['porcentaje'] = (res['Horas'] / total_horas * 100).round(1)
    res = res.sort_values('Horas', ascending=False)
    
    print("--- NEW DRILLDOWN LOGIC CHECK ---")
    print(res[['Articulo', 'OF', 'Horas_Pte', 'dias', 'porcentaje']].head(10))
else:
    print("No data found for test.")
