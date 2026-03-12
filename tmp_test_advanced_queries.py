import duckdb
import pandas as pd
from pathlib import Path

BASE_DIR = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS")
DB_ANALYTICAL_PATH = BASE_DIR / "backend" / "db" / "rpk_analytical.duckdb"

def test():
    if not DB_ANALYTICAL_PATH.exists():
        print("DB Not found")
        return
    
    conn = duckdb.connect(str(DB_ANALYTICAL_PATH), read_only=True)
    
    try:
        print("Checking tables...")
        print(conn.execute("SHOW TABLES").df())
        
        print("\nChecking columns in existencias...")
        print(conn.execute("DESCRIBE existencias").df())
        
        # Test query 1
        print("\nTesting Evolution Query...")
        start, end = '2026-01-01', '2026-03-12'
        query_evo = f"SELECT Fecha, SUM(Valor_Total) as Valor FROM existencias WHERE Fecha BETWEEN '{start}' AND '{end}' GROUP BY Fecha ORDER BY Fecha"
        print(conn.execute(query_evo).df().head())
        
        # Test query 2
        print("\nTesting Monthly Query...")
        query_month = f"SELECT strftime(TRY_CAST(Fecha AS DATE), '%Y-%m') as Mes, LAST(Valor_Total) as Valor_Cierre FROM existencias WHERE Fecha BETWEEN '{start}' AND '{end}' GROUP BY Mes ORDER BY Mes"
        print(conn.execute(query_month).df().head())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test()
