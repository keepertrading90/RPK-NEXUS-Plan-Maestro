"""
RPK NEXUS - Asistente de Consultas CLI
Este script permite realizar consultas en lenguaje natural a la base de datos NEXUS.
"""

import sqlite3
import os
import sys
from datetime import datetime

# Intentar importar tabulate, con fallback simple si no está instalado
try:
    from tabulate import tabulate
except ImportError:
    tabulate = None

# --- CONFIGURACIÓN DE BASE DE DATOS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "rpk_industrial.db")

# --- LÓGICA DE "IA" (PLACEHOLDER) ---
def traducir_a_sql(pregunta_usuario):
    """
    Traduce preguntas en lenguaje natural a SQL contra rpk_analytical.duckdb.
    Tablas: existencias, carga_centros, maestro_fleje, pedidos, albaranes, tiempos_detalle_articulo
    """
    pregunta = pregunta_usuario.strip().lower()
    
    import re
    numeros = re.findall(r'\d+', pregunta)
    centro_id = numeros[0] if numeros else None

    # ─── CARGA / SATURACIÓN ───────────────────────────────────────────────────
    if any(k in pregunta for k in ["saturacion", "carga", "trabajo"]):
        if centro_id:
            # Buscar en carga_centros (analítica) y también en maestro_fleje
            return f"""
                SELECT 'maestro' as fuente, CAST(Centro AS VARCHAR) as Centro,
                       AVG(Piezas_Hora) as Piezas_Hora, AVG(OEE) as OEE,
                       AVG(Cadencia_Actual) as Cadencia_Actual
                FROM maestro_fleje
                WHERE CAST(Centro AS VARCHAR) = '{centro_id}'
                GROUP BY Centro
                UNION ALL
                SELECT 'carga' as fuente, Centro,
                       AVG(Carga_Dia) as val1, NULL, NULL
                FROM carga_centros
                WHERE Centro = '{centro_id}'
                GROUP BY Centro
            """
        return "SELECT Centro, AVG(Carga_Dia) as carga_media, COUNT(*) as dias FROM carga_centros WHERE Centro NOT LIKE '9%' GROUP BY Centro ORDER BY carga_media DESC LIMIT 15"

    # ─── MAQUINA / CENTRO (sin saturación) ───────────────────────────────────
    if any(k in pregunta for k in ["maquina", "centro"]):
        if centro_id:
            return f"""
                SELECT CAST(Centro AS VARCHAR) as Centro, Articulo, Descripcion,
                       Piezas_Hora, OEE, Cadencia_Min, Cadencia_Max, Cadencia_Actual
                FROM maestro_fleje
                WHERE CAST(Centro AS VARCHAR) LIKE '%{centro_id}%'
                LIMIT 15
            """
        return "SELECT Centro, COUNT(DISTINCT Articulo) as articulos, AVG(OEE) as oee_medio FROM maestro_fleje GROUP BY Centro ORDER BY oee_medio ASC LIMIT 15"

    # ─── STOCK / EXISTENCIAS ──────────────────────────────────────────────────
    if any(k in pregunta for k in ["stock", "existencias", "cuanto hay", "cantidad"]):
        if "total" in pregunta:
            return "SELECT SUM(Cantidad) as Total_Stock, COUNT(DISTINCT Articulo) as Articulos FROM existencias"
        if centro_id:
            return f"SELECT Articulo, Descripcion, SUM(Cantidad) as Stock, Cliente FROM existencias WHERE Articulo = '{centro_id}' OR CAST(Articulo AS VARCHAR) LIKE '%{centro_id}%' GROUP BY Articulo, Descripcion, Cliente ORDER BY Stock DESC LIMIT 10"
        return "SELECT Articulo, Descripcion, SUM(Cantidad) as Total FROM existencias GROUP BY Articulo, Descripcion ORDER BY Total DESC LIMIT 10"

    # ─── ARTICULO sin palabras clave (solo número, ej: "422016") ─────────────
    if centro_id and (len(pregunta_usuario.strip()) <= 10 or
                      any(k in pregunta for k in ["articulo", "estock", "pieza", "referencia"])):
        return f"""
            SELECT e.Articulo, e.Descripcion, SUM(e.Cantidad) as Stock, e.Cliente,
                   m.Piezas_Hora, m.OEE, m.Cadencia_Actual
            FROM existencias e
            LEFT JOIN maestro_fleje m ON CAST(e.Articulo AS VARCHAR) = CAST(m.Articulo AS VARCHAR)
            WHERE CAST(e.Articulo AS VARCHAR) = '{centro_id}'
               OR CAST(e.Articulo AS VARCHAR) LIKE '%{centro_id}%'
            GROUP BY e.Articulo, e.Descripcion, e.Cliente, m.Piezas_Hora, m.OEE, m.Cadencia_Actual
            ORDER BY Stock DESC LIMIT 5
        """

    # ─── PEDIDOS ──────────────────────────────────────────────────────────────
    if any(k in pregunta for k in ["pedido", "orden", "entrega", "cliente", "cartera"]):
        if centro_id:
            return f"SELECT * FROM pedidos WHERE Cliente LIKE '%{centro_id}%' LIMIT 10"
        return "SELECT Cliente, SUM(Cantidad) as Cantidad, SUM(Valor_Total) as Valor FROM pedidos GROUP BY Cliente ORDER BY Valor DESC LIMIT 10"

    # ─── ALBARANES ────────────────────────────────────────────────────────────
    if any(k in pregunta for k in ["albaran", "expedicion", "enviado", "factura"]):
        return "SELECT Cliente, COUNT(*) as Num_Albaranes, SUM(Valor_Total) as Facturacion FROM albaranes GROUP BY Cliente ORDER BY Facturacion DESC LIMIT 10"

    # ─── TIEMPOS / OEE ───────────────────────────────────────────────────────
    if any(k in pregunta for k in ["tiempo", "oee", "rendimiento", "ciclo"]):
        return "SELECT Articulo, Centro, Tiempo_Ciclo, OEE FROM tiempos_detalle_articulo ORDER BY OEE ASC LIMIT 10"

    # ─── FALLBACK: si hay número, buscar como artículo ───────────────────────
    if centro_id:
        return f"SELECT Articulo, Descripcion, SUM(Cantidad) as Stock, Cliente FROM existencias WHERE CAST(Articulo AS VARCHAR) LIKE '%{centro_id}%' GROUP BY Articulo, Descripcion, Cliente ORDER BY Stock DESC LIMIT 8"

    # Fallback final → stock top
    return "SELECT Articulo, Descripcion, SUM(Cantidad) as Total FROM existencias GROUP BY Articulo, Descripcion ORDER BY Total DESC LIMIT 5"


DUCK_DB_PATH = os.path.join(BASE_DIR, "db", "rpk_analytical.duckdb")

def ejecutar_consulta(sql):
    """Ejecuta la query SQL en DuckDB (Carril B analítico) y devuelve resultados."""
    import duckdb
    if not os.path.exists(DUCK_DB_PATH):
        print(f"⚠️ NEXUS DuckDB no encontrada en: {DUCK_DB_PATH}")
        return None, None
    try:
        con = duckdb.connect(DUCK_DB_PATH, read_only=True)
        result = con.execute(sql).fetchdf()
        con.close()
        columnas = list(result.columns)
        resultados = [tuple(row) for row in result.itertuples(index=False)]
        return resultados, columnas
    except Exception as e:
        print(f"❌ Error DuckDB: {e}")
        return None, None

def mostrar_resultados(resultados, columnas):
    """Muestra los resultados en una tabla bonita."""
    if not resultados:
        print("📭 No se encontraron resultados.")
        return

    if tabulate:
        print(tabulate(resultados, headers=columnas, tablefmt="fancy_grid", numalign="center"))
    else:
        # Fallback simple si tabulate no está instalado
        print(" | ".join(columnas))
        print("-" * (len(columnas) * 15))
        for row in resultados:
            print(" | ".join(map(str, row)))

def main():
    print("========================================")
    print("      RPK NEXUS: ASISTENTE CLI")
    print("========================================")
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] RPK NEXUS Asistente")
            pregunta = input("¿Qué quieres saber de tu producción? (o escribe 'salir'): ")
            
            if pregunta.lower() in ['salir', 'exit', 'q']:
                print("👋 Cerrando asistente. ¡Buen trabajo!")
                break
                
            if not pregunta.strip():
                continue
                
            print("🔍 Analizando pregunta...")
            sql = traducir_a_sql(pregunta)
            
            print(f"⚙️ Ejecutando Query...")
            
            resultados, columnas = ejecutar_consulta(sql)
            
            print("\n📊 RESULTADOS:")
            mostrar_resultados(resultados, columnas)
            
        except KeyboardInterrupt:
            print("\n👋 Cerrando asistente...")
            break
        except Exception as e:
            print(f"❌ Error inesperado: {e}")

def formatear_humanamente(resultados, columnas, pregunta):
    """
    Convierte resultados de DuckDB en mensajes amistosos.
    Usa deteccion case-insensitive para columnas reales de rpk_analytical.duckdb.
    """
    if not resultados:
        return "No he encontrado datos para esa consulta en NEXUS. Prueba otra búsqueda."

    pregunta = pregunta.lower()
    # Mapa de columnas normalizadas: "articulo" -> "Articulo" (nombre real en df)
    col = {c.lower(): c for c in columnas}

    def get(d, *keys):
        for k in keys:
            v = d.get(col.get(k.lower(), k), None)
            if v is not None:
                return v
        return "?"

    def fmt_num(v):
        try: return f"{float(v):,.0f}"
        except: return str(v)

    # ─── CARGA / SATURACIÓN ───
    if any(k in pregunta for k in ["saturacion", "carga", "maquina", "centro", "trabajo"]):
        res = "📊 **Carga de Trabajo encontrada:**\n\n"
        for r in resultados[:10]:
            d = dict(zip(columnas, r))
            centro = get(d, 'Centro', 'centro_trabajo', 'centro')
            carga  = get(d, 'carga_total', 'carga_media', 'Carga_Dia', 'carga_dia')
            regs   = d.get(col.get('registros'), '')
            try:    carga_str = f"{float(carga):.1f}h"
            except: carga_str = str(carga)
            res += f"- **Centro {centro}**: {carga_str} de carga"
            if regs: res += f" ({regs} días)"
            res += "\n"
        return res

    # ─── ARTICULO / STOCK ───
    if any(k in pregunta for k in ["stock", "existencias", "cantidad", "articulo", "estock", "422"]) or any(c.isdigit() for c in pregunta):
        # Check si es total global
        if col.get('total_stock') and len(resultados) == 1:
            d = dict(zip(columnas, resultados[0]))
            total = fmt_num(get(d, 'Total_Stock', 'total'))
            arts  = get(d, 'Articulos', 'articulos', 'items')
            return f"📦 **Stock Global NEXUS:**\n- Total: **{total} piezas** en sistema\n- Artículos distintos: **{arts}**"

        res = "📦 **Existencias encontradas:**\n\n"
        for r in resultados[:8]:
            d = dict(zip(columnas, r))
            art  = get(d, 'Articulo', 'articulo')
            cant = get(d, 'Cantidad', 'cantidad', 'Total', 'total')
            cli  = d.get(col.get('cliente'), '')
            desc = get(d, 'Descripcion', 'descripcion')
            res += f"- **Art. {art}**: {fmt_num(cant)} pzs."
            if cli: res += f" — {cli}"
            if desc and str(desc) != '?': res += f" ({desc})"
            res += "\n"
        return res

    # ─── PEDIDOS ───
    if any(k in pregunta for k in ["pedido", "cliente", "cartera", "entrega"]):
        res = "💰 **Pedidos por Cliente:**\n\n"
        for r in resultados[:8]:
            d = dict(zip(columnas, r))
            cli = get(d, 'Cliente', 'cliente')
            cant = fmt_num(get(d, 'Cantidad', 'cantidad'))
            val  = get(d, 'Valor', 'valor', 'Valor_Total', 'valor_total')
            try:    val_str = f"{float(val):,.2f} €"
            except: val_str = str(val)
            res += f"- **{cli}**: {cant} uds. → {val_str}\n"
        return res

    # ─── GENÉRICO ───
    res = "✅ **Datos NEXUS:**\n\n"
    for r in resultados[:5]:
        d = dict(zip(columnas, r))
        linea = " | ".join([f"**{k}**: {v}" for k, v in d.items() if v is not None and str(v) not in ('nan', 'None', '')])
        res += f"- {linea}\n"
    return res

if __name__ == "__main__":
    main()
