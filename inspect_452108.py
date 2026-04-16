import duckdb
conn = duckdb.connect(':memory:')
df = conn.execute("SELECT * FROM read_parquet('backend/data_lake/maestros/maestro_fleje.parquet') WHERE Articulo = '452108'").df()
print(df[['Articulo', 'Centro', 'Fase', 'Piezas_Hora']].to_string())
conn.close()
