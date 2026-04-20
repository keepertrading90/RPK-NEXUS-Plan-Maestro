
"""
ENTENDER LA NATURALEZA DEL INFORME DE ALBARANES
================================================
Los snapshots del ERP son ACUMULATIVOS (van creciendo a lo largo del mes).
Cada snapshot contiene TODOS los albaranes del mes hasta esa fecha, no solo los del dia.
La suma correcta es el valor del ULTIMO snapshot del mes.
"""
import duckdb, pandas as pd
from pathlib import Path

DB_PATH = Path(r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb')

with duckdb.connect(str(DB_PATH)) as con:
    # Comprobar si el ultimo snapshot del mes incluye todos los albaranes del mes
    q = """
    SELECT Fecha_Snapshot, Fecha_Albaran, Albaran, Cantidad
    FROM albaranes
    WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
    ORDER BY Fecha_Snapshot, Fecha_Albaran
    """
    df = con.execute(q).df()
    print("Todos los registros de 421653L en Marzo:")
    print(df)
    
    # Comprobar el ultimo snapshot
    last_snapshot = df['Fecha_Snapshot'].max()
    print(f"\nUltimo snapshot: {last_snapshot}")
    print(f"Total en ultimo snapshot: {df[df['Fecha_Snapshot'] == last_snapshot]['Cantidad'].sum():,.0f}")
    print(f"Total en TODOS los snapshots (suma): {df['Cantidad'].sum():,.0f}")
