import duckdb
conn = duckdb.connect(':memory:')
# Usar read_parquet con glob para cabeceras
df = conn.execute("SELECT * FROM read_parquet('backend/data_lake/transaccional/carga_cabeceras/**/*.parquet', union_by_name=True) WHERE Articulo = '452108'").df()
print(df[['Articulo', 'Centro_Cabecera', 'OF', 'Horas_Necesarias']].to_string())
conn.close()
