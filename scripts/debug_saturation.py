import duckdb
from pathlib import Path

DB_PATH = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb")

with duckdb.connect(str(DB_PATH)) as conn:
    print("--- Inspecting maestro_fleje data for saturation debugging ---")
    # Check extremes and some samples
    res = conn.execute("""
        SELECT Articulo, Centro, Piezas_Hora, OEE, Cadencia_Actual
        FROM maestro_fleje 
        ORDER BY Piezas_Hora ASC
        LIMIT 10
    """).df()
    print("Top 10 lowest Piezas_Hora:")
    print(res)
    
    res_high = conn.execute("""
        SELECT Articulo, Centro, Piezas_Hora, OEE, Cadencia_Actual
        FROM maestro_fleje 
        ORDER BY Piezas_Hora DESC
        LIMIT 10
    """).df()
    print("\nTop 10 highest Piezas_Hora:")
    print(res_high)
    
    # Check OEE values
    print("\nOEE Stats:")
    print(conn.execute("SELECT MIN(OEE), MAX(OEE), AVG(OEE) FROM maestro_fleje").df())
