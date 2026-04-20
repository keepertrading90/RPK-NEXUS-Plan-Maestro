
"""
ANALISIS CLAVE: El informe del ERP de Albaranes es ACUMULATIVO o INCREMENTAL?

Teoria A (ACUMULATIVO): El snapshot de 30/03 deberia incluir TODOS los albaranes desde 01/01.
Teoria B (INCREMENTAL): Cada snapshot solo tiene los albaranes del dia o de la semana.

La pantalla del ERP muestra 2.784.000 para TODO Marzo 2026.
El snapshot del 31/03 (fichero albaranes_20260331.parquet) deberia ser el mas completo.

Importante: el fichero del 31/03 tiene Fecha_Snapshot = "2026-02-27" (segun el nombre del Excel),
            lo que indica que el sistema asigna particion month=03 por la FECHA DEL FICHERO, no del albaran.
"""
import duckdb, pandas as pd
from pathlib import Path

DB_PATH = Path(r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb')

with duckdb.connect(str(DB_PATH)) as con:
    # Ver TODO para 421653L incluyendo todos los meses disponibles
    q = """
    SELECT Fecha_Snapshot, Fecha_Albaran, Albaran, Cantidad, month, year
    FROM albaranes
    WHERE Articulo = '421653L'
    ORDER BY Fecha_Snapshot DESC, Fecha_Albaran DESC
    LIMIT 50
    """
    df = con.execute(q).df()
    print("Todos los registros para 421653L (mas recientes primero):")
    print(df)
    
    # Obtener el ultimo snapshot disponible (global)
    q2 = """
    SELECT MAX(Fecha_Snapshot) FROM albaranes
    """
    last = con.execute(q2).fetchone()[0]
    print(f"\nUltimo snapshot global: {last}")
    
    q3 = f"""
    SELECT SUM(Cantidad) as Total_Ultimo_Snapshot
    FROM albaranes
    WHERE Articulo = '421653L' AND Fecha_Snapshot = '{last}'
    """
    res = con.execute(q3).fetchone()[0]
    print(f"Total 421653L en ultimo snapshot ({last}): {res:,.0f}")
    
    # Ver cuantos albaranes del mes de MARZO tiene el ultimo snapshot
    q4 = f"""
    SELECT SUM(Cantidad) as Total_Marzo_En_Ultimo_Snapshot
    FROM albaranes
    WHERE Articulo = '421653L' 
      AND Fecha_Snapshot = '{last}'
      AND Fecha_Albaran LIKE '2026-03-%'
    """
    res2 = con.execute(q4).fetchone()[0]
    print(f"Total 421653L (albaranes de Marzo) en ultimo snapshot: {res2}")
