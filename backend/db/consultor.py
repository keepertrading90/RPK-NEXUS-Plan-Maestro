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
    Simulación de IA: Traduce una pregunta en lenguaje natural a SQL.
    Aquí se integrará la llamada a la API de Gemini próximamente.
    """
    pregunta = pregunta_usuario.lower()
    
    # Diccionario de ejemplos predefinidos
    ejemplos = {
        "stock total": "SELECT SUM(cantidad) as Total_Stock, SUM(valor_total) as Valor_Total FROM stock_snapshot",
        "stock por cliente": "SELECT cliente, SUM(cantidad) as Cantidad FROM stock_snapshot GROUP BY cliente ORDER BY Cantidad DESC",
        "saturacion critica": "SELECT centro_trabajo, horas_ocupadas, saturacion_pct FROM tiempos_carga WHERE saturacion_pct > 80",
        "top 10 articulos": "SELECT articulo, descripcion, cantidad, valor_total FROM stock_snapshot ORDER BY valor_total DESC LIMIT 10",
        "carga de trabajo": "SELECT centro_trabajo, horas_ocupadas FROM tiempos_carga ORDER BY horas_ocupadas DESC"
    }
    
    # Búsqueda simple por palabras clave para el placeholder
    for clave, sql in ejemplos.items():
        if clave in pregunta:
            return sql
            
    # Si no hay coincidencia, devolvemos un SELECT genérico o None
    return "SELECT * FROM stock_snapshot LIMIT 5"

def ejecutar_consulta(sql):
    """Ejecuta la query SQL y devuelve los resultados."""
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: No se encuentra la base de datos en {DB_PATH}")
        return None, None
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql)
        
        columnas = [description[0] for description in cursor.description]
        resultados = cursor.fetchall()
        
        conn.close()
        return resultados, columnas
    except sqlite3.Error as e:
        print(f"❌ Error SQL: {e}")
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
            # print(f"DEBUG SQL: {sql}") # Desactiva print en producción
            
            resultados, columnas = ejecutar_consulta(sql)
            
            print("\n📊 RESULTADOS:")
            mostrar_resultados(resultados, columnas)
            
        except KeyboardInterrupt:
            print("\n👋 Cerrando asistente...")
            break
        except Exception as e:
            print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    main()
