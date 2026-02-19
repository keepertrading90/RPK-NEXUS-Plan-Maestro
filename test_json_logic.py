import os
import sqlite3
import pandas as pd
from pathlib import Path

# Mock query_db
def query_db(query, args=(), one=False):
    db_path = r"C:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_industrial.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def test_drilldown_logic(centro_id, mes):
    q = "SELECT Articulo, OF, Horas, Fecha FROM tiempos_detalle_articulo WHERE Centro = ? AND Fecha LIKE ?"
    data = query_db(q, (centro_id, f"{mes}%"))
    
    if not data: return {"articulos": [], "count": 0}
    
    df = pd.DataFrame([dict(r) for r in data])
    total_horas = df['Horas'].sum()
    
    res = df.groupby(['Articulo', 'OF']).agg({
        'Horas': 'sum',
        'Fecha': 'nunique'
    }).reset_index().rename(columns={'Fecha': 'dias'})
    
    res['porcentaje'] = (res['Horas'] / total_horas * 100).round(1)
    res = res.sort_values('Horas', ascending=False)
    
    final_data = []
    for r in res.to_dict('records'):
        final_data.append({
            "articulo": str(r['Articulo']),
            "of": str(r['OF']),
            "horas": float(r['Horas']),
            "dias": int(r['dias']),
            "porcentaje": float(r['porcentaje'])
        })
    
    return {"articulos": final_data[:5], "total": len(final_data)}

print("Testing Drilldown for 782, Feb 2026...")
print(test_drilldown_logic("782", "2026-02"))

print("\nTesting for 750, Feb 2026...")
print(test_drilldown_logic("750", "2026-02"))
