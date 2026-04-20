
"""
POST-CLEANUP: Re-sincronizar vistas DuckDB y verificar datos de 421653L
"""
import duckdb
from pathlib import Path

LAKE_DIR = Path(r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake')
DB_PATH = Path(r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb')

# Resincronizar vistas DuckDB
with duckdb.connect(str(DB_PATH)) as conn:
    transaccionales = ["existencias", "carga_centros", "carga_detalle", "pedidos", "albaranes"]
    for tb in transaccionales:
        glob_path = LAKE_DIR / "transaccional" / tb / "**" / "*.parquet"
        parquet_files = list((LAKE_DIR / "transaccional" / tb).glob("**/*.parquet"))
        if parquet_files:
            conn.execute(
                f"CREATE OR REPLACE VIEW {tb} AS SELECT * FROM read_parquet('{glob_path}', union_by_name=True)"
            )
            print(f"Vista resincronizada: {tb} ({len(parquet_files)} ficheros)")

# Verificar resultado para 421653L
print("\n--- VERIFICACION POST-LIMPIEZA: 421653L en Marzo 2026 ---")
with duckdb.connect(str(DB_PATH)) as conn:
    q_total = """
    SELECT SUM(Cantidad) as Total_Albaranado
    FROM albaranes
    WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
    """
    total = conn.execute(q_total).fetchone()[0]
    print(f"Total albaranado en DuckDB: {total:,.0f}")
    print(f"Total en ERP (referencia):  2,784,000")
    print(f"Diferencia: {abs(total - 2784000):,.0f}")
    
    print("\n--- Desglose por fecha de albaran ---")
    q_detail = """
    SELECT Fecha_Albaran, SUM(Cantidad) as Cantidad, COUNT(*) as Filas
    FROM albaranes
    WHERE Articulo = '421653L' AND year = 2026 AND month = '03'
    GROUP BY Fecha_Albaran
    ORDER BY Fecha_Albaran
    """
    print(conn.execute(q_detail).df().to_string(index=False))
