import duckdb
conn = duckdb.connect('backend/db/rpk_analytical.duckdb')
res = conn.execute("SELECT Articulo, Cantidad, Valor_Total, Fecha FROM existencias WHERE Articulo = '421654'").fetchall()
for row in res:
    print(row)
