import duckdb
from pathlib import Path

db = duckdb.connect(':memory:')

data_lake = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake")
maestro_path = str(data_lake / 'maestros' / 'maestro_fleje.parquet').replace("\\", "/")
cabeceras_path = str(data_lake / 'transaccional' / 'carga_cabeceras' / '**' / '*.parquet').replace("\\", "/")

db.execute(f"CREATE OR REPLACE VIEW rutas_maestras AS SELECT * FROM read_parquet('{maestro_path}') WHERE CAST(Fase AS VARCHAR) != 'nan'")
db.execute(f"CREATE OR REPLACE VIEW carga_cabeceras AS SELECT * FROM read_parquet('{cabeceras_path}', union_by_name=True)")

query_407 = """
SELECT DISTINCT Articulo, Fase, Centro, Piezas_Hora 
FROM rutas_maestras 
WHERE CAST(Centro AS VARCHAR) = '407'
"""

query_projection = """
WITH
cabeceras_407 AS (
    SELECT 
        TRY_CAST(c.Centro_Cabecera AS VARCHAR) as Centro_Cabecera,
        TRY_CAST(c.OF AS VARCHAR) as OF,
        TRY_CAST(c.Articulo AS VARCHAR) as Articulo,
        TRY_CAST(c.Horas_Necesarias AS DOUBLE) as Horas_Pendientes,
        c.Fecha_Carga as Fecha_Pedido,
        c.Fecha_Carga as Fecha_Entrega,
        ROW_NUMBER() OVER (PARTITION BY c.Centro_Cabecera, c.OF ORDER BY c.Fecha_Carga DESC) as rn
    FROM carga_cabeceras c
    WHERE c.Fecha_Carga = (SELECT MAX(Fecha_Carga) FROM carga_cabeceras)
      AND TRY_CAST(c.Horas_Necesarias AS DOUBLE) > 0
      AND CAST(c.Centro_Cabecera AS VARCHAR) = '407'
)
SELECT
    f.Centro_Cabecera,
    f.OF,
    f.Articulo,
    CAST(r.Centro AS VARCHAR) as Centro_Secundario,
    CAST(r.Fase AS DOUBLE) as Fase_Secundaria,
    f.Horas_Pendientes as Horas_F10,
    COALESCE(
        f.Horas_Pendientes * (CAST(r_f10.Piezas_Hora AS DOUBLE) / 
            NULLIF(CAST(r.Piezas_Hora AS DOUBLE), 0)),
        f.Horas_Pendientes
    ) as Horas_Proyectadas
FROM cabeceras_407 f
JOIN rutas_maestras r ON CAST(r.Articulo AS VARCHAR) = f.Articulo
    AND TRY_CAST(r.Fase AS DOUBLE) > 10.0
LEFT JOIN (
    SELECT 
        CAST(Articulo AS VARCHAR) as Articulo, 
        MAX(CAST(Piezas_Hora AS DOUBLE)) as Piezas_Hora
    FROM rutas_maestras 
    WHERE TRY_CAST(Fase AS DOUBLE) = 10.0
    GROUP BY 1
) r_f10 ON r_f10.Articulo = f.Articulo
WHERE f.rn = 1
ORDER BY f.Centro_Cabecera, f.Articulo, Fase_Secundaria
"""

import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

print("--- Maestro Rutas 407 ---")
print(db.execute(query_407).df().to_string(index=False))
print("\n--- Proyeccion Articulos de 407 ---")
print(db.execute(query_projection).df().to_string(index=False))
