"""Test rápido del Gemelo Digital v2.1 contra el data lake real."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backend.analytics_core import NexusDigitalTwin
import json

twin = NexusDigitalTwin()
result = twin.proyectar_impacto_secundarios()
print("\n=== RESULTADO GEMELO DIGITAL v2.1 ===")
print(f"Status: {result['status']}")
print(f"Message: {result['message']}")
print(f"Centros proyectados: {len(result.get('data', []))}")
if result['data']:
    print("\nTop 5 centros:")
    for row in result['data'][:5]:
        print(f"  Centro {row['Centro']}: WIP={row['WIP_Actual_Horas']}h, "
              f"Entrante={row['WIP_Entrante_Fase10_Horas']}h, "
              f"Total={row['Saturacion_Total_Proyectada']}h, "
              f"Lotes={row['Lotes_En_Camino']}")
else:
    print("Sin datos de proyección.")
twin.close()
