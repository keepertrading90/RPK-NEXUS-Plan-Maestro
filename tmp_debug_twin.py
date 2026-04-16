"""Debug del cruce Fase10 → rutas secundarias."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import duckdb
from backend.analytics_core import NexusDigitalTwin

twin = NexusDigitalTwin()
conn = twin.conn

# ¿Cuántos centros Fase 10 hay?
print("=== CENTROS DE FASE 10 (maestro_fleje) ===")
r = conn.execute("SELECT DISTINCT CAST(Centro AS VARCHAR) as Centro FROM rutas_maestras WHERE TRY_CAST(Fase AS DOUBLE) = 10.0").fetchall()
print(f"  {len(r)} centros Fase10:", [x[0] for x in r[:20]])

# ¿Cuántas OFs activas hay en esos centros? (última fecha carga_detalle)
print("\n=== OFs EN CENTROS FASE10 (última fecha) ===")
r2 = conn.execute("""
    SELECT d.Centro, d.OF, d.Articulo, d.Horas_Pte_Val, d.Fecha
    FROM carga_detalle_wip d
    INNER JOIN (
        SELECT DISTINCT CAST(Centro AS VARCHAR) as Centro FROM rutas_maestras WHERE TRY_CAST(Fase AS DOUBLE) = 10.0
    ) c ON CAST(d.Centro AS VARCHAR) = c.Centro
    WHERE d.Fecha = (SELECT MAX(Fecha) FROM carga_detalle_wip)
      AND CAST(d.Horas_Pte_Val AS DOUBLE) > 0
    LIMIT 10
""").fetchall()
print(f"  {len(r2)} filas encontradas:")
for row in r2:
    print(f"    Centro={row[0]}, OF={row[1]}, Art={row[2]}, Horas={row[3]}, Fecha={row[4]}")

# ¿Qué artículos de esas OFs tienen rutas secundarias?
if r2:
    art_set = tuple(set(str(row[2]) for row in r2))
    print(f"\n=== RUTAS SECUNDARIAS para articulos en F10 ===")
    safe = "','".join(art_set[:5])
    r3 = conn.execute(f"SELECT Articulo, Centro, Fase FROM rutas_maestras WHERE CAST(Articulo AS VARCHAR) IN ('{safe}') AND TRY_CAST(Fase AS DOUBLE) > 10 LIMIT 10").fetchall()
    print(f"  {len(r3)} rutas secundarias encontradas:")
    for row in r3:
        print(f"    Art={row[0]}, Centro_Sec={row[1]}, Fase={row[2]}")

twin.close()
