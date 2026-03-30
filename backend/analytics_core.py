"""
RPK NEXUS - Analítica Cruzada Core / Gemelo Digital Predictivo v2.0
Calcula métricas combinando Stock y Capacidad (Tiempos).

Novedad v2.0:
  - proyectar_impacto_secundarios() ahora acepta opcionalmente un DataFrame simulado
    (df_fase10_override) que reemplaza al parquet en disco. Esto permite que el
    endpoint /api/simulate/preview calcule proyecciones dinámicas de los what-if
    sin necesidad de regenerar parquets.
"""
import duckdb
import logging
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NexusDigitalTwin:
    """
    Motor del Gemelo Digital Predictivo de NEXUS.
    Cruza el estado de cabeceras (Fase 10) con las Rutas Maestras para calcular el Efecto Cascada.

    Soporta dos modos de operación:
      - Modo Parquet   : Lee estado real del data_lake (uso estático / ETL).
      - Modo DataFrame : Acepta el resultado simulado en memoria (uso what-if dinámico).
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
            rutas_path = str(self.data_lake / 'maestros/**/*.parquet').replace("\\", "/")
            fase10_path = str(self.data_lake / 'transaccional/carga_cabeceras/**/*.parquet').replace("\\", "/")
            centros_wip_path = str(self.data_lake / 'transaccional/carga_centros/**/*.parquet').replace("\\", "/")

            self.conn.execute(
                f"CREATE OR REPLACE VIEW rutas_maestras AS "
                f"SELECT * FROM read_parquet('{rutas_path}', union_by_name=True) "
                f"WHERE CAST(Fase AS VARCHAR) != 'nan'"
            )
            self.conn.execute(
                f"CREATE OR REPLACE VIEW carga_fase10 AS "
                f"SELECT * FROM read_parquet('{fase10_path}', union_by_name=True)"
            )
            self.conn.execute(
                f"CREATE OR REPLACE VIEW carga_centros_wip AS "
                f"SELECT * FROM read_parquet('{centros_wip_path}', union_by_name=True)"
            )
            logger.info("Vistas lógicas en memoria creadas correctamente.")
        except Exception as e:
            logger.warning(f"Advertencia al mapear vistas DuckDB (posible falta de parquets iniciales): {e}")

    def proyectar_impacto_secundarios(
        self,
        simulacion_params: dict = None,
        df_fase10_override: Optional[pd.DataFrame] = None,
        df_centros_wip_override: Optional[pd.DataFrame] = None,
    ) -> dict:
        """
        Calcula la saturación real = WIP(Actual) + Proyección hacia adelante (Fase10 -> Secundarios).

        Args:
            simulacion_params: Parámetros adicionales del escenario (reservado para futuros usos).
            df_fase10_override: Si se proporciona, se usa en lugar de la vista parquet 'carga_fase10'.
                                Debe tener columnas: Centro_Cabecera, OF, Articulo, Cantidad,
                                Horas_Necesarias, Orden_Secuencia, Fecha_Carga.
            df_centros_wip_override: Si se proporciona, reemplaza la vista 'carga_centros_wip'.
                                     Columnas: Centro, Carga_Dia, Fecha.
        """
        logger.info("Calculando proyecciones de impacto hacia adelante (Forward-Pass)...")

        # --- Registrar DataFrames de override en DuckDB si existen ---
        if df_fase10_override is not None and not df_fase10_override.empty:
            try:
                self.conn.register("carga_fase10_sim", df_fase10_override)
                fase10_source = "carga_fase10_sim"
                logger.info(f"Override df_fase10 registrado: {len(df_fase10_override)} filas.")
            except Exception as e:
                logger.warning(f"No se pudo registrar df_fase10_override: {e}. Usando parquet.")
                fase10_source = "carga_fase10"
        else:
            fase10_source = "carga_fase10"

        if df_centros_wip_override is not None and not df_centros_wip_override.empty:
            try:
                self.conn.register("carga_centros_wip_sim", df_centros_wip_override)
                wip_source = "carga_centros_wip_sim"
                logger.info(f"Override df_centros_wip registrado: {len(df_centros_wip_override)} filas.")
            except Exception as e:
                logger.warning(f"No se pudo registrar df_centros_wip_override: {e}.")
                wip_source = "carga_centros_wip"
        else:
            wip_source = "carga_centros_wip"

        query = f"""
        WITH secuenciacion_f10 AS (
            SELECT
                Centro_Cabecera,
                OF,
                Articulo,
                CAST(Cantidad AS DOUBLE) as Cantidad,
                CAST(Horas_Necesarias AS DOUBLE) as Horas_Necesarias,
                Orden_Secuencia,
                SUM(CAST(Horas_Necesarias AS DOUBLE)) OVER (
                    PARTITION BY Centro_Cabecera ORDER BY Orden_Secuencia
                ) as Hora_Liberacion
            FROM {fase10_source}
            WHERE Fecha_Carga = (SELECT MAX(Fecha_Carga) FROM {fase10_source})
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
            WHERE TRY_CAST(r.Fase AS INTEGER) > 10
        ),
        agregado_entrante AS (
            SELECT
                Centro_Secundario,
                SUM(COALESCE(Horas_Nuevas_Proyectadas, 0)) as Carga_Entrante_Predictiva,
                COUNT(DISTINCT OF) as Cantidad_Lotes_Entrantes,
                -- Lista de artículos para el tooltip del frontend
                LIST(DISTINCT Articulo) as Articulos_En_Camino
            FROM impacto_rutas
            GROUP BY Centro_Secundario
        ),
        wip_actual AS (
            SELECT
                Centro,
                SUM(Carga_Dia) as Carga_WIP_Actual
            FROM {wip_source}
            WHERE Fecha = (SELECT MAX(Fecha) FROM {wip_source})
            GROUP BY Centro
        )

        SELECT
            COALESCE(w.Centro, a.Centro_Secundario) as Centro,
            ROUND(COALESCE(w.Carga_WIP_Actual, 0), 2) as WIP_Actual_Horas,
            ROUND(COALESCE(a.Carga_Entrante_Predictiva, 0), 2) as WIP_Entrante_Fase10_Horas,
            ROUND(
                COALESCE(w.Carga_WIP_Actual, 0) + COALESCE(a.Carga_Entrante_Predictiva, 0)
            , 2) as Saturacion_Total_Proyectada,
            COALESCE(a.Cantidad_Lotes_Entrantes, 0) as Lotes_En_Camino,
            COALESCE(a.Articulos_En_Camino, []) as Articulos_En_Camino
        FROM wip_actual w
        FULL OUTER JOIN agregado_entrante a ON w.Centro = a.Centro_Secundario
        ORDER BY Saturacion_Total_Proyectada DESC
        """

        try:
            df = self.conn.execute(query).df()
            df = df.replace({np.nan: 0})
            # Convertir listas DuckDB a listas Python estándar
            if "Articulos_En_Camino" in df.columns:
                df["Articulos_En_Camino"] = df["Articulos_En_Camino"].apply(
                    lambda x: list(x) if hasattr(x, '__iter__') and not isinstance(x, str) else []
                )
            resultado = df.to_dict(orient="records")
            logger.info(f"Proyección completada: {len(resultado)} centros secundarios impactados.")
            return {"status": "success", "data": resultado, "message": "Proyección Gemelo Digital finalizada"}

        except duckdb.CatalogException as ce:
            logger.warning(f"Faltan tablas para el cruce: {ce}")
            return {"status": "error", "message": "Faltan tablas parquet (ejecutar ETL primero)."}
        except duckdb.BinderException as be:
            logger.warning(f"Error de tipos en la DB: {be}")
            return {"status": "error", "message": f"Error cruzando datos: {be}"}
        except Exception as e:
            logger.error(f"Error Genérico proyectar_impacto: {e}")
            return {"status": "error", "message": str(e)}

    def get_cobertura_global(self) -> dict:
        """Métrica de cobertura global (simulada)."""
        return {
            "stock_total": 0.0,
            "carga_total_horas": 0.0,
            "dias_cobertura_teorica": 0.0
        }

    def close(self):
        self.conn.close()


# --- Instancia global reutilizable (Singleton por proceso) ---
_twin_instance: Optional[NexusDigitalTwin] = None


def get_twin() -> NexusDigitalTwin:
    """Retorna la instancia global del Gemelo Digital (lazy init)."""
    global _twin_instance
    if _twin_instance is None:
        _twin_instance = NexusDigitalTwin()
    return _twin_instance


def proyectar_impacto_secundarios(
    dias_horizonte: int = 7,
    df_fase10_override: Optional[pd.DataFrame] = None,
    df_centros_wip_override: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Función de acceso rápido al motor del Gemelo Digital.
    Wrapper para uso directo en server_nexus (sin instanciar manualmente la clase).
    """
    twin = get_twin()
    return twin.proyectar_impacto_secundarios(
        simulacion_params={"dias_horizonte": dias_horizonte},
        df_fase10_override=df_fase10_override,
        df_centros_wip_override=df_centros_wip_override,
    )


if __name__ == "__main__":
    twin = NexusDigitalTwin()
    result = twin.proyectar_impacto_secundarios()
    import json
    print(json.dumps(result, indent=2, default=str))
    twin.close()
