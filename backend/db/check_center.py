import duckdb
import os

db_path = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb'
conn = duckdb.connect(db_path)
df = conn.execute("SELECT Articulo, Piezas_Hora, OEE, Volumen_Anual FROM maestro_fleje WHERE Centro = '793'").df()
print(df.to_string())
conn.close()
