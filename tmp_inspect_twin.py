import duckdb, json
from pathlib import Path

BASE = Path(__file__).parent / "backend" / "data_lake"

conn = duckdb.connect(':memory:')

try:
    df = conn.execute(
        f"SELECT * FROM read_parquet('{str(BASE / 'transaccional/carga_detalle/**/*.parquet').replace(chr(92),'/')}', union_by_name=True) LIMIT 3"
    ).df()
    print("COLUMNAS carga_detalle:", list(df.columns))
    print(df.to_string())
except Exception as e:
    print("ERROR carga_detalle:", e)

try:
    df2 = conn.execute(
        f"SELECT * FROM read_parquet('{str(BASE / 'maestros/maestro_fleje.parquet').replace(chr(92),'/')}') LIMIT 3"
    ).df()
    print("\nCOLUMNAS maestro_fleje:", list(df2.columns))
    print(df2.to_string())
except Exception as e:
    print("ERROR maestro_fleje:", e)

try:
    df3 = conn.execute(
        f"SELECT * FROM read_parquet('{str(BASE / 'transaccional/carga_centros/**/*.parquet').replace(chr(92),'/')}', union_by_name=True) LIMIT 3"
    ).df()
    print("\nCOLUMNAS carga_centros:", list(df3.columns))
    print(df3.to_string())
except Exception as e:
    print("ERROR carga_centros:", e)

conn.close()
