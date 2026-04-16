import duckdb
from pathlib import Path

db = duckdb.connect(':memory:')

data_lake = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake")
maestro_path = str(data_lake / 'maestros' / 'maestro_fleje.parquet').replace("\\", "/")
detalle_path = str(data_lake / 'transaccional' / 'carga_detalle' / '**' / '*.parquet').replace("\\", "/")
cabeceras_path = str(data_lake / 'transaccional' / 'carga_cabeceras' / '**' / '*.parquet').replace("\\", "/")

db.execute(f"CREATE OR REPLACE VIEW rutas_maestras AS SELECT * FROM read_parquet('{maestro_path}')")
db.execute(f"CREATE OR REPLACE VIEW carga_detalle_wip AS SELECT * FROM read_parquet('{detalle_path}', union_by_name=True)")
db.execute(f"CREATE OR REPLACE VIEW carga_cabeceras_f10 AS SELECT * FROM read_parquet('{cabeceras_path}', union_by_name=True)")

query = """
WITH
centros_f10 AS (
    SELECT DISTINCT CAST(Centro AS VARCHAR) as Centro
    FROM rutas_maestras
    WHERE TRY_CAST(Fase AS DOUBLE) = 10.0
),
ordenes_activas_f10 AS (
    SELECT
        TRY_CAST(c.Centro_Cabecera AS VARCHAR) as Centro_Cabecera,
        TRY_CAST(c.OF AS VARCHAR) as OF,
        TRY_CAST(c.Articulo AS VARCHAR) as Articulo,
        TRY_CAST(c.Horas_Necesarias AS DOUBLE) as Horas_Pendientes,
        c.Fecha_Carga as Fecha_Carga,
        ROW_NUMBER() OVER (PARTITION BY c.Centro_Cabecera, c.OF ORDER BY c.Fecha_Carga DESC) as rn
    FROM carga_cabeceras_f10 c
    WHERE c.Fecha_Carga = (SELECT MAX(Fecha_Carga) FROM carga_cabeceras_f10)
      AND TRY_CAST(c.Horas_Necesarias AS DOUBLE) > 0
),
impacto_rutas AS (
    SELECT
        f.Centro_Cabecera,
        f.OF,
        f.Articulo,
        CAST(r.Centro AS VARCHAR) as Centro_Secundario,
        CAST(r.Fase AS DOUBLE) as Fase_Secundaria,
        f.Horas_Pendientes as Horas_F10,
        CAST(r_f10.Piezas_Hora AS DOUBLE) as PPM_F10,
        CAST(r.Piezas_Hora AS DOUBLE) as PPM_Secundario,
        
        -- EXPLICACIÓN: Horas F10 * (PPM secundario / PPM F10)
        COALESCE(
            f.Horas_Pendientes * (CAST(r.Piezas_Hora AS DOUBLE) / 
                NULLIF(CAST(r_f10.Piezas_Hora AS DOUBLE), 0)),
            f.Horas_Pendientes
        ) as Horas_Proyectadas_ACTUAL,
        
        -- FORMULA CORREGIDA: Horas F10 * (PPM F10 / PPM secundario)
        COALESCE(
            f.Horas_Pendientes * (CAST(r_f10.Piezas_Hora AS DOUBLE) / 
                NULLIF(CAST(r.Piezas_Hora AS DOUBLE), 0)),
            f.Horas_Pendientes
        ) as Horas_Proyectadas_NUEVA
    FROM ordenes_activas_f10 f
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
    WHERE f.rn = 1 AND CAST(r.Centro AS VARCHAR) = '2000'
)
SELECT * FROM impacto_rutas
WHERE Articulo IN ('451621', '452580', '453396', '400311', '450335A')
ORDER BY Horas_Proyectadas_ACTUAL DESC;
"""

print(db.execute(query).df().to_markdown())
