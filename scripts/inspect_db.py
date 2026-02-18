import sqlite3
import os

DB_PATH = r'c:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_industrial.db'

def inspect():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: No existe {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"Tablas encontradas: {tables}")
    
    for table in tables:
        print(f"\n--- Esquema de {table} ---")
        cursor.execute(f"PRAGMA table_info({table})")
        for col in cursor.fetchall():
            print(f"  {col[1]} ({col[2]})")
            
    conn.close()

if __name__ == "__main__":
    inspect()
