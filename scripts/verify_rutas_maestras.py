import duckdb
from pathlib import Path

DB_PATH = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb")

with duckdb.connect(str(DB_PATH)) as conn:
    print("--- Verificando Articulo 400208 ---")
    res = conn.execute("""
        SELECT Articulo, Fase, Centro, Piezas_Hora, UATC 
        FROM maestro_fleje 
        WHERE Articulo = '400208'
        ORDER BY Fase
    """).df()
    print(res)
    
    # Check if 798 or 910 are present
    redundant = res[res['Centro'].isin(['798', '910'])]
    if redundant.empty:
        print("\nSUCCESS: Centros 798 y 910 filtrados correctamente (misma cadencia que fase 10).")
    else:
        print("\nFAILURE: Centros redundantes encontrados:")
        print(redundant)

    print("\n--- Conteo Total ---")
    count = conn.execute("SELECT COUNT(*) FROM maestro_fleje").fetchone()[0]
    print(f"Total registros en maestro_fleje: {count}")
