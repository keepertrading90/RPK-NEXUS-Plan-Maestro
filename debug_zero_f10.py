import duckdb
from pathlib import Path
import pandas as pd

# Rutas de datos
BASE = Path(r"C:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake")
CABECERAS_GLOB = str(BASE / "transaccional" / "carga_cabeceras" / "**" / "*.parquet").replace("\\", "/")
MAESTRO_RUTAS = str(BASE / "maestros" / "maestro_fleje.parquet").replace("\\", "/")

print(f"Buscando Cabeceras en: {CABECERAS_GLOB}")
print(f"Buscando Rutas en: {MAESTRO_RUTAS}")

conn = duckdb.connect(':memory:')

# Registrar parquets
try:
    conn.execute(f"CREATE TABLE cabeceras AS SELECT TRY_CAST(Articulo AS VARCHAR) as Articulo, TRY_CAST(Centro_Cabecera AS VARCHAR) as Centro_Cabecera, Horas_Necesarias, OF FROM read_parquet('{CABECERAS_GLOB}', union_by_name=True)")
    conn.execute(f"CREATE TABLE rutas AS SELECT Articulo, Centro, Fase, Piezas_Hora FROM read_parquet('{MAESTRO_RUTAS}')")
except Exception as e:
    print(f"Error registrando tablas: {e}")
    conn.close()
    exit()

# Inspeccionar artículos problemáticos
target_articles = ['452108', '451106A']

print("\n--- ANALISIS DE ARTICULOS ---")
for art in target_articles:
    print(f"\n>> ARTICULO: {art}")
    
    # 1. ¿Está en Phase 10 en cabeceras?
    res_f10 = conn.execute(f"SELECT Articulo, OF, Centro_Cabecera, Horas_Necesarias FROM cabeceras WHERE Articulo = '{art}'").df()
    print("En Fase 10 (Planificación):")
    print(res_f10.to_string())
    
    # 2. ¿Tiene rutas posteriores en el maestro?
    res_rutas = conn.execute(f"SELECT Articulo, Fase, Centro, Piezas_Hora FROM rutas WHERE Articulo = '{art}' ORDER BY Fase").df()
    print("\nRutas en el Maestro:")
    print(res_rutas.to_string())

# Ver cálculo manual de la proyección
print("\n--- TEST DE CALCULO DE PROYECCION ---")
query_test = """
SELECT 
    f.Articulo,
    f.OF,
    f.Horas_Necesarias as Horas_F10,
    r.Centro as Centro_Secundario,
    r.Fase as Fase_Sec,
    r.Piezas_Hora as PPM_Sec,
    r_f10.Piezas_Hora as PPM_F10,
    CASE 
        WHEN CAST(r.Piezas_Hora AS DOUBLE) > 0 THEN 
            f.Horas_Necesarias * (CAST(r.Piezas_Hora AS DOUBLE) / NULLIF(CAST(r_f10.Piezas_Hora AS DOUBLE), 0))
        ELSE f.Horas_Necesarias
    END as Horas_Calc
FROM cabeceras f
JOIN rutas r ON r.Articulo = f.Articulo AND r.Fase > 10
JOIN rutas r_f10 ON r_f10.Articulo = f.Articulo AND r_f10.Fase = 10
WHERE f.Articulo IN ('452108', '451106A')
"""
try:
    res_test = conn.execute(query_test).df()
    print(res_test.to_string())
except Exception as e:
    print(f"Error en query de test: {e}")

conn.close()
