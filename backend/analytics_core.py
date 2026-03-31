"""
RPK NEXUS - Analítica Cruzada Core / Gemelo Digital Predictivo v2.1
Calcula métricas combinando Stock y Capacidad (Tiempos).

v2.1 - Adaptado a esquema real del Data Lake:
  - Usa carga_detalle (Centro, Articulo, OF, Horas_Pte_Val) en lugar de carga_cabeceras.
  - Cruza con maestro_fleje para identificar Fase 10 y rutas secundarias.
  - carga_centros provee el WIP actual por centro.
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
    Cruza el estado de órdenes activas en centros Fase 10 con las Rutas Maestras
    para calcular el Efecto Cascada sobre centros secundarios.

    Esquema de datos reales (v2.1):
      - carga_detalle: Fecha, Centro, Articulo, OF, Horas_Final, Horas_Pte_Val
      - maestro_fleje: Articulo, Centro, Piezas_Hora, OEE, Fase, UATC, Volumen_Anual
      - carga_centros: Fecha, Centro, Carga_Dia
    """

    def __init__(self, data_lake_path: Path = None):
        base_dir = Path(__file__).resolve().parent
        self.data_lake = data_lake_path or base_dir / "data_lake"

        # Conexión in-memory con DuckDB para cruces zero-latency (Carril B)
        self.conn = duckdb.connect(database=':memory:')
        logger.info("Motor Gemelo Digital (DuckDB v2.1) inicializado en memoria RAM.")
        self._inicializar_vistas()

    def _inicializar_vistas(self):
        """Crea vistas lógicas apuntando a los parquets del Data Lake."""
        try:
            # Vista rutas maestras (globbing todos los parquets de maestros)
            maestro_path = str(self.data_lake / 'maestros' / 'maestro_fleje.parquet').replace("\\", "/")
            detalle_path = str(self.data_lake / 'transaccional/carga_detalle/**/*.parquet').replace("\\", "/")
            centros_path = str(self.data_lake / 'transaccional/carga_centros/**/*.parquet').replace("\\", "/")
            cabeceras_path = str(self.data_lake / 'transaccional/carga_cabeceras/**/*.parquet').replace("\\", "/")

            self.conn.execute(
                f"CREATE OR REPLACE VIEW rutas_maestras AS "
                f"SELECT * FROM read_parquet('{maestro_path}') "
                f"WHERE CAST(Fase AS VARCHAR) != 'nan'"
            )
            self.conn.execute(
                f"CREATE OR REPLACE VIEW carga_detalle_wip AS "
                f"SELECT * FROM read_parquet('{detalle_path}', union_by_name=True)"
            )
            self.conn.execute(
                f"CREATE OR REPLACE VIEW carga_centros_wip AS "
                f"SELECT * FROM read_parquet('{centros_path}', union_by_name=True)"
            )
            
            # Intentar cargar carga_cabeceras (Fase 10 real del usuario)
            import glob
            if glob.glob(str(self.data_lake / 'transaccional/carga_cabeceras/**/*.parquet'), recursive=True):
                self.conn.execute(
                    f"CREATE OR REPLACE VIEW carga_cabeceras_f10 AS "
                    f"SELECT * FROM read_parquet('{cabeceras_path}', union_by_name=True)"
                )
                self.has_cabeceras = True
            else:
                self.has_cabeceras = False
                logger.warning("Vista carga_cabeceras_f10 no disponible. Se usará el ERP como fallback.")

            logger.info("Vistas lógicas v2.2 creadas correctamente.")
        except Exception as e:
            self.has_cabeceras = False
            logger.warning(f"Advertencia al mapear vistas DuckDB: {e}")

    def proyectar_impacto_secundarios(
        self,
        simulacion_params: dict = None,
        df_fase10_override: Optional[pd.DataFrame] = None,
        df_centros_wip_override: Optional[pd.DataFrame] = None,
    ) -> dict:
        """
        Calcula la saturación real = WIP(Actual) + Proyección hacia adelante.

        Lógica v2.1:
          1. Identifica centros de Fase 10 desde rutas_maestras (Fase == 10).
          2. Filtra carga_detalle por esos centros para obtener órdenes activas (WIP F10).
          3. Cruza cada artículo con sus rutas secundarias (Fase > 10) en maestro_fleje.
          4. Calcula horas proyectadas = Horas_Pte_Val / PPM_F10 * PPM_secundario (normalizado).
          5. Suma WIP actual por centro secundario desde carga_centros.
        """
        logger.info("Calculando proyecciones Forward-Pass v2.1 (carga_detalle → rutas secundarias)...")

        # --- Registrar DataFrames de override si existen ---
        if df_fase10_override is not None and not df_fase10_override.empty:
            try:
                self.conn.register("carga_detalle_wip_sim", df_fase10_override)
                detalle_source = "carga_detalle_wip_sim"
                logger.info(f"Override df_fase10 registrado: {len(df_fase10_override)} filas.")
            except Exception as e:
                logger.warning(f"No se pudo registrar df_fase10_override: {e}. Usando parquet.")
                detalle_source = "carga_detalle_wip"
        else:
            detalle_source = "carga_detalle_wip"

        if df_centros_wip_override is not None and not df_centros_wip_override.empty:
            try:
                self.conn.register("carga_centros_wip_sim", df_centros_wip_override)
                wip_source = "carga_centros_wip_sim"
            except Exception as e:
                logger.warning(f"No se pudo registrar df_centros_wip_override: {e}.")
                wip_source = "carga_centros_wip"
        else:
            wip_source = "carga_centros_wip"

        # ──────────────────────────────────────────────────────────────────
        # Query principal: Forward-Pass desde centros Fase10 → secundarios
        # ──────────────────────────────────────────────────────────────────
        query = f"""
        WITH
        -- 1. Centros que pertenecen a Fase 10 en el maestro de rutas
        centros_f10 AS (
            SELECT DISTINCT CAST(Centro AS VARCHAR) as Centro
            FROM rutas_maestras
            WHERE TRY_CAST(Fase AS DOUBLE) = 10.0
        ),

        -- 2. Órdenes activas en Fase 10 (desde Excel si existe, sino Fallback ERP)
        ordenes_activas_f10 AS (
            {f'''
            -- Fuente Primaria: Excel de Planificacion (carga_cabeceras)
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
            ''' if self.has_cabeceras else f'''
            -- Fallback: Listado ERP (carga_detalle) filtrado por centros Fase 10
            SELECT
                TRY_CAST(d.Centro AS VARCHAR) as Centro_Cabecera,
                TRY_CAST(d.OF AS VARCHAR) as OF,
                TRY_CAST(d.Articulo AS VARCHAR) as Articulo,
                TRY_CAST(d.Horas_Pte_Val AS DOUBLE) as Horas_Pendientes,
                d.Fecha as Fecha_Carga,
                ROW_NUMBER() OVER (PARTITION BY d.Centro, d.OF ORDER BY d.Fecha DESC) as rn
            FROM {detalle_source} d
            INNER JOIN centros_f10 cf ON TRY_CAST(d.Centro AS VARCHAR) = cf.Centro
            WHERE d.Fecha = (SELECT MAX(Fecha) FROM {detalle_source})
              AND TRY_CAST(d.Horas_Pte_Val AS DOUBLE) > 0
            '''}
        ),

        -- 3. Cruce con rutas secundarias (Fase > 10) del maestro
        impacto_rutas AS (
            SELECT
                f.Centro_Cabecera,
                f.OF,
                f.Articulo,
                CAST(r.Centro AS VARCHAR) as Centro_Secundario,
                CAST(r.Fase AS DOUBLE) as Fase_Secundaria,
                -- Proyección: proporcional a las horas pendientes en F10
                -- Si tenemos Piezas_Hora en la fase secundaria, usamos ratio; si no, fallback a horas entrada
                COALESCE(
                    f.Horas_Pendientes * (CAST(r.Piezas_Hora AS DOUBLE) / 
                        NULLIF(CAST(r_f10.Piezas_Hora AS DOUBLE), 0)),
                    f.Horas_Pendientes
                ) as Horas_Proyectadas_Secundario
            FROM ordenes_activas_f10 f
            -- Rutas del mismo artículo, fases posteriores
            JOIN rutas_maestras r ON CAST(r.Articulo AS VARCHAR) = f.Articulo
                AND TRY_CAST(r.Fase AS DOUBLE) > 10.0
            -- Rutas del mismo artículo en Fase 10 para normalización (PPM de referencia)
            -- Flexibilizado: No requerimos que el Centro coincida exactamente (el Excel puede usar IDs de máquina)
            LEFT JOIN (
                SELECT 
                    CAST(Articulo AS VARCHAR) as Articulo, 
                    MAX(CAST(Piezas_Hora AS DOUBLE)) as Piezas_Hora
                FROM rutas_maestras 
                WHERE TRY_CAST(Fase AS DOUBLE) = 10.0
                GROUP BY 1
            ) r_f10 ON r_f10.Articulo = f.Articulo
            WHERE f.rn = 1
        ),

        -- 4. Agregado por centro secundario
        agregado_entrante AS (
            SELECT
                Centro_Secundario,
                SUM(COALESCE(Horas_Proyectadas_Secundario, 0)) as Carga_Entrante_Predictiva,
                COUNT(DISTINCT OF) as Cantidad_Lotes_Entrantes,
                LIST(DISTINCT Articulo) as Articulos_En_Camino
            FROM impacto_rutas
            GROUP BY Centro_Secundario
        ),

        -- 5. WIP actual por centro (última fecha disponible de carga_centros)
        wip_actual AS (
            SELECT
                CAST(Centro AS VARCHAR) as Centro,
                SUM(CAST(Carga_Dia AS DOUBLE)) as Carga_WIP_Actual
            FROM {wip_source}
            WHERE Fecha = (SELECT MAX(Fecha) FROM {wip_source})
            GROUP BY CAST(Centro AS VARCHAR)
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
        WHERE (COALESCE(w.Carga_WIP_Actual, 0) + COALESCE(a.Carga_Entrante_Predictiva, 0) > 0)
          AND (COALESCE(w.Centro, a.Centro_Secundario) NOT LIKE '9%')
          AND (COALESCE(w.Centro, a.Centro_Secundario) NOT IN ('724', '798'))
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
            logger.info(f"Proyección v2.1 completada: {len(resultado)} centros secundarios impactados.")
            return {"status": "success", "data": resultado, "message": f"Proyección Gemelo Digital: {len(resultado)} centros analizados"}

        except duckdb.CatalogException as ce:
            logger.warning(f"Faltan tablas para el cruce: {ce}")
            return {"status": "error", "data": [], "message": "Faltan tablas parquet (ejecutar ETL primero)."}
        except duckdb.BinderException as be:
            logger.warning(f"Error de tipos en la DB: {be}")
            return {"status": "error", "data": [], "message": f"Error cruzando datos: {be}"}
        except Exception as e:
            logger.error(f"Error Genérico proyectar_impacto: {e}")
            return {"status": "error", "data": [], "message": str(e)}

    def get_cobertura_global(self) -> dict:
        """Métrica de cobertura global."""
        try:
            result = self.conn.execute("""
                SELECT 
                    SUM(CAST(Carga_Dia AS DOUBLE)) as carga_total
                FROM carga_centros_wip
                WHERE Fecha = (SELECT MAX(Fecha) FROM carga_centros_wip)
            """).fetchone()
            carga = result[0] if result and result[0] else 0.0
            return {
                "stock_total": 0.0,
                "carga_total_horas": float(carga),
                "dias_cobertura_teorica": round(float(carga) / 16.0, 1) if carga > 0 else 0.0
            }
        except Exception:
            return {"stock_total": 0.0, "carga_total_horas": 0.0, "dias_cobertura_teorica": 0.0}

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
    Wrapper para uso directo en server_nexus.
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
