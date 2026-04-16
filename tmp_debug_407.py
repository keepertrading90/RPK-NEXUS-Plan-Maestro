import duckdb
from pathlib import Path
import pandas as pd

db = duckdb.connect(':memory:')

data_lake = Path(r"c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\data_lake")
cabeceras_path = str(data_lake / 'transaccional' / 'carga_cabeceras' / '**' / '*.parquet').replace("\\", "/")
detalle_path = str(data_lake / 'transaccional' / 'carga_detalle' / '**' / '*.parquet').replace("\\", "/")

db.execute(f"CREATE OR REPLACE VIEW carga_cabeceras AS SELECT * FROM read_parquet('{cabeceras_path}', union_by_name=True)")
db.execute(f"CREATE OR REPLACE VIEW carga_detalle AS SELECT * FROM read_parquet('{detalle_path}', union_by_name=True)")

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

print("--- OFs in Carga Cabeceras for Centro_Cabecera = '407' ---")
query_cabeceras = "SELECT Centro_Cabecera, OF, Articulo, Horas_Necesarias, Fecha_Carga FROM carga_cabeceras WHERE CAST(Centro_Cabecera AS VARCHAR) = '407'"
print(db.execute(query_cabeceras).df().to_string(index=False))

print("\n--- OFs in Carga Detalle for specific 407 OFs (e.g. 150909, 150872) ---")
query_detalle = "SELECT Centro, OF, Articulo, Horas_Pte_Val, Fecha FROM carga_detalle WHERE CAST(OF AS VARCHAR) IN ('150909', '150872')"
print(db.execute(query_detalle).df().to_string(index=False))
