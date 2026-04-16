import duckdb

db = duckdb.connect(':memory:')
print('\n--- Cabeceras F10 ---')
print(db.execute("DESCRIBE SELECT * FROM read_parquet('data/analitica/cabeceras_fase10.parquet')").df().to_string(index=False))

print('\n--- Rutas Maestras ---')
print(db.execute("DESCRIBE SELECT * FROM read_parquet('data/analitica/rutas_maestras.parquet')").df().to_string(index=False))
