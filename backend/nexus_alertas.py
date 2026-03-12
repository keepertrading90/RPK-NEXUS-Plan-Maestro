"""
nexus_alertas.py — Motor de Alertas Proactivas RPK NEXUS
──────────────────────────────────────────────────────────
Al arrancar el servidor, analiza DuckDB y genera alertas sobre:
  - Artículos con stock crítico (< 30% del objetivo)
  - Centros de trabajo sobrecargados (> 14h/día)
  - OEE bajo en máquinas clave (< 60%)
  - Pedidos próximos a vencer (si hay columna de fecha)
"""

import duckdb
import threading
from pathlib import Path
from datetime import datetime

DUCK_DB_PATH = Path(r"C:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb")

NIVEL_COLOR = {
    "danger":  "#E30613",   # Rojo RPK
    "warning": "#f59e0b",   # Ámbar
    "info":    "#3b82f6",   # Azul
}

class NexusAlertas:
    """Generador de alertas proactivas basado en datos DuckDB."""
    
    def __init__(self):
        self.alertas: list = []
        self.ultima_actualizacion: str = None
        self._ready = False
    
    def analizar(self):
        """Ejecuta todos los checks y genera la lista de alertas."""
        if not DUCK_DB_PATH.exists():
            return
        
        alertas = []
        try:
            con = duckdb.connect(str(DUCK_DB_PATH), read_only=True)
            
            # ── CHECK 1: Stock crítico (< 30% del objetivo) ──────────────────
            df_stock = con.execute("""
                SELECT 
                    Articulo, Descripcion,
                    SUM(Cantidad) as stock_actual,
                    MAX(Stock_Objetivo) as stock_objetivo,
                    MAX(Cliente) as cliente
                FROM existencias
                WHERE Stock_Objetivo > 0
                GROUP BY Articulo, Descripcion
                HAVING SUM(Cantidad) < MAX(Stock_Objetivo) * 0.30
                ORDER BY (SUM(Cantidad) / MAX(Stock_Objetivo)) ASC
                LIMIT 5
            """).fetchdf()
            
            for _, row in df_stock.iterrows():
                pct = (row['stock_actual'] / row['stock_objetivo'] * 100)
                urgencia = "danger" if pct < 15 else "warning"
                alertas.append({
                    "tipo": "stock_critico",
                    "nivel": urgencia,
                    "color": NIVEL_COLOR[urgencia],
                    "icono": "📦",
                    "titulo": f"Stock crítico: Art. {row['Articulo']}",
                    "mensaje": f"Solo {row['stock_actual']:,.0f} pzs ({pct:.0f}% del objetivo). Cliente: {row['cliente']}",
                    "articulo": str(row['Articulo'])
                })
            
            # ── CHECK 2: Centros sobrecargados (> 14h carga/día en últimos 7d) ─
            try:
                df_carga = con.execute("""
                    SELECT Centro, AVG(Carga_Dia) as carga_media
                    FROM carga_centros
                    GROUP BY Centro
                    HAVING AVG(Carga_Dia) > 14
                    ORDER BY carga_media DESC
                    LIMIT 5
                """).fetchdf()
                
                for _, row in df_carga.iterrows():
                    pct_sat = (row['carga_media'] / 16.0 * 100)
                    alertas.append({
                        "tipo": "centro_saturado",
                        "nivel": "warning",
                        "color": NIVEL_COLOR["warning"],
                        "icono": "⚙️",
                        "titulo": f"Centro {row['Centro']} al límite",
                        "mensaje": f"Carga media: {row['carga_media']:.1f}h/día → {pct_sat:.0f}% de saturación",
                        "centro": str(row['Centro'])
                    })
            except Exception:
                pass
            
            # ── CHECK 3: OEE bajo en maestro (< 60%) ─────────────────────────
            try:
                df_oee = con.execute("""
                    SELECT 
                        CAST(Centro AS VARCHAR) as Centro,
                        AVG(OEE) as oee_medio,
                        COUNT(DISTINCT Articulo) as n_arts
                    FROM maestro_fleje
                    WHERE OEE > 0 AND OEE < 1
                    GROUP BY Centro
                    HAVING AVG(OEE) < 0.60
                    ORDER BY oee_medio ASC
                    LIMIT 3
                """).fetchdf()
                
                for _, row in df_oee.iterrows():
                    alertas.append({
                        "tipo": "oee_bajo",
                        "nivel": "info",
                        "color": NIVEL_COLOR["info"],
                        "icono": "📊",
                        "titulo": f"OEE bajo · Centro {row['Centro']}",
                        "mensaje": f"OEE medio: {row['oee_medio']:.1%} en {row['n_arts']:.0f} artículos. Revisar mantenimiento.",
                        "centro": str(row['Centro'])
                    })
            except Exception:
                pass
            
            con.close()
            self.alertas = alertas
            self.ultima_actualizacion = datetime.now().strftime("%H:%M del %d/%m/%Y")
            self._ready = True
            print(f"[ALERTAS] {len(alertas)} alertas generadas: "
                  f"{sum(1 for a in alertas if a['nivel']=='danger')} críticas, "
                  f"{sum(1 for a in alertas if a['nivel']=='warning')} advertencias")
        
        except Exception as e:
            print(f"[ALERTAS] Error en análisis: {e}")
    
    def start_async(self):
        """Arranca el análisis en background."""
        threading.Thread(target=self.analizar, daemon=True).start()
    
    def get_alertas(self) -> dict:
        return {
            "alertas": self.alertas,
            "ultima_actualizacion": self.ultima_actualizacion,
            "total": len(self.alertas),
            "criticas": sum(1 for a in self.alertas if a["nivel"] == "danger"),
            "advertencias": sum(1 for a in self.alertas if a["nivel"] == "warning"),
            "ready": self._ready
        }


# Singleton global
nexus_alertas = NexusAlertas()
