import duckdb
conn = duckdb.connect('backend/db/rpk_analytical.duckdb')

print("--- Verificando Articulos del Top (Caso del Pantallazo) ---")
articulos = ['421654', '421653L', '421979B', '421109C']
for art in articulos:
    res = conn.execute("SELECT Cantidad, Valor_Total, Fecha FROM existencias WHERE Articulo = ? AND Fecha = '2026-03-12'", (art,)).fetchall()
    for row in res:
        print(f"Articulo: {art} | Fecha: {row[2]} | Cantidad: {row[0]}")

print("\n--- Verificando si hay duplicados por Fecha/Articulo (Deberia ser 1 registro por combinacion) ---")
dup = conn.execute("""
    SELECT Articulo, Fecha, COUNT(*) as c 
    FROM existencias 
    WHERE Fecha IN ('2026-03-11', '2026-03-12')
    GROUP BY Articulo, Fecha 
    HAVING c > 1 
    LIMIT 5
""").fetchall()
if dup:
    print("ALERTA: Se encontraron duplicados:")
    for d in dup: print(d)
else:
    print("EXITO: No hay duplicados para los ultimos dias.")

print("\n--- Verificando si hay algun 0.0 sospechoso en cantidades grandes ---")
zeros = conn.execute("SELECT Articulo, Cantidad, Fecha FROM existencias WHERE Cantidad = 0 LIMIT 5").fetchall()
print(f"Muestra de articulos con Cantidad 0: {zeros}")
