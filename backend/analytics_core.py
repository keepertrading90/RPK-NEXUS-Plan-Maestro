"""
RPK NEXUS - Analítica Cruzada Core / Gemelo Digital Predictivo
Calcula métricas combinando Stock y Capacidad (Tiempos).
"""
import duckdb
import logging
from pathlib import Path
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NexusDigitalTwin:
    """
    Motor del Gemelo Digital Predictivo de NEXUS.
    Cruza el estado de cabeceras (Fase 10) con las Rutas Maestras para calcular el Efecto Cascada.
    """
    def __init__(self, data_lake_path: Path = None):
        base_dir = Path(__file__).resolve().parent
        self.data_lake = data_lake_path or base_dir / "data_lake"
        
        # Conexión in-memory con DuckDB para cruces zero-latency (Carril B)
        self.conn = duckdb.connect(database=':memory:')
        logger.info("Motor Gemelo Digital (DuckDB) inicializado en memoria RAM.")
        self._inicializar_vistas()

    def _inicializar_vistas(self):
        """Crea vistas lógicas apuntando a los parquets del Data Lake."""
        try:
            # Vista Maestro Fleje (Rutas)
            self.conn.execute(f"CREATE OR REPLACE VIEW rutas_maestras AS SELECT * FROM read_parquet('{self.data_lake}/maestros/**/*.parquet', union_by_name=True) WHERE CAST(Fase AS VARCHAR) != 'nan'")
            
            # Vista Carga Cabeceras Fase 10
            self.conn.execute(f"CREATE OR REPLACE VIEW carga_fase10 AS SELECT * FROM read_parquet('{self.data_lake}/transaccional/carga_cabeceras/**/*.parquet', union_by_name=True)")

            # Vista Carga Actual WIP en Centros
            self.conn.execute(f"CREATE OR REPLACE VIEW carga_centros_wip AS SELECT * FROM read_parquet('{self.data_lake}/transaccional/carga_centros/**/*.parquet', union_by_name=True)")
            
            logger.info("Vistas lógicas en memoria creadas correctamente.")
        except Exception as e:
            logger.warning(f"Advertencia al mapear vistas DuckDB (posible falta de parquets iniciales): {e}")

    def proyectar_impacto_secundarios(self, simulacion_params=None):
        """
        Calcula la saturación real = WIP(Actual) + Proyección hacia adelante (Fase10 -> Secundarios).
        """
        logger.info("Calculando proyecciones de impacto hacia adelante (Forward-Pass)...")
        query = """
        WITH secuenciacion_f10 AS (
            SELECT 
                Centro_Cabecera, 
                OF, 
                Articulo, 
                CAST(Cantidad AS DOUBLE) as Cantidad,
                CAST(Horas_Necesarias AS DOUBLE) as Horas_Necesarias,
                Orden_Secuencia,
                -- Tiempo estimado de llegada a su siguiente proceso
                SUM(CAST(Horas_Necesarias AS DOUBLE)) OVER (PARTITION BY Centro_Cabecera ORDER BY Orden_Secuencia) as Hora_Liberacion
            FROM carga_fase10
            -- Aislar la foto del snapshot más reciente parseado
            WHERE Fecha_Carga = (SELECT MAX(Fecha_Carga) FROM carga_fase10)
        ),
        impacto_rutas AS (
            SELECT 
                s.Centro_Cabecera,
                s.OF,
                s.Articulo,
                s.Hora_Liberacion,
                r.Centro as Centro_Secundario,
                r.Fase as Fase_Secundaria,
                (s.Cantidad / NULLIF(CAST(r.Piezas_Hora AS DOUBLE), 0)) as Horas_Nuevas_Proyectadas
            FROM secuenciacion_f10 s
            JOIN rutas_maestras r ON s.Articulo = r.Articulo
            -- Consideramos secundarios todo aquello > 10. La lógica es inclusiva.
            WHERE TRY_CAST(r.Fase AS INTEGER) > 10
        ),
        agregado_entrante AS (
            SELECT 
                Centro_Secundario,
                -- Asegurar que los NULLs se manejen como 0 en la suma
                SUM(COALESCE(Horas_Nuevas_Proyectadas, 0)) as Carga_Entrante_Predictiva,
                COUNT(DISTINCT OF) as Cantidad_Lotes_Entrantes
            FROM impacto_rutas
            GROUP BY Centro_Secundario
        ),
        wip_actual AS (
            SELECT 
                Centro,
                SUM(Carga_Dia) as Carga_WIP_Actual
            FROM carga_centros_wip
            WHERE Fecha = (SELECT MAX(Fecha) FROM carga_centros_wip)
            GROUP BY Centro
        )
        
        SELECT 
            COALESCE(w.Centro, a.Centro_Secundario) as Centro,
            ROUND(COALESCE(w.Carga_WIP_Actual, 0), 2) as WIP_Actual_Horas,
            ROUND(COALESCE(a.Carga_Entrante_Predictiva, 0), 2) as WIP_Entrante_Fase10_Horas,
            ROUND(COALESCE(w.Carga_WIP_Actual, 0) + COALESCE(a.Carga_Entrante_Predictiva, 0), 2) as Saturacion_Total_Proyectada,
            COALESCE(a.Cantidad_Lotes_Entrantes, 0) as Lotes_En_Camino
        FROM wip_actual w
        FULL OUTER JOIN agregado_entrante a ON w.Centro = a.Centro_Secundario
        ORDER BY Saturacion_Total_Proyectada DESC
        """
        
        try:
            df = self.conn.execute(query).df()
            # Convertimos NaN/NaT en None/0 para json 
            df = df.replace({np.nan: 0})
            resultado = df.to_dict(orient="records")
            logger.info(f"Proyección completada: {len(resultado)} centros secundarios impactados.")
            return {"status": "success", "data": resultado, "message": "Proyección simulada finalizada"}
        except duckdb.CatalogException as ce:
            logger.warning(f"Faltan tablas para el cruce: {ce}")
            return {"status": "error", "message": "No se encuentran todas las tablas parquet necesarias (ejecutar ETL)."}
        except duckdb.BinderException as be:
            logger.warning(f"Error de tipos en la DB: {be}")
            return {"status": "error", "message": f"Error cruzando datos: {be}"}
        except Exception as e:
            logger.error(f"Error Genérico: {e}")
            return {"status": "error", "message": str(e)}

    def get_cobertura_global(self):
        """Métrica de cobertura adaptada a DuckDB (simulada por ahora)."""
        return {
            "stock_total": 0.0,
            "carga_total_horas": 0.0,
            "dias_cobertura_teorica": 0.0
        }

    def close(self):
        self.conn.close()

if __name__ == "__main__":
    twin = NexusDigitalTwin()
    print(twin.proyectar_impacto_secundarios())
    twin.close()
