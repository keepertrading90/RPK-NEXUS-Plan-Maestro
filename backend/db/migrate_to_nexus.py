"""
RPK NEXUS - Script de Migración FASE 1
Generado por: Antigravity (Senior Python Data Engineer)
"""

import os
import shutil
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Index, create_engine
from sqlalchemy.orm import declarative_base

# --- CONFIGURACIÓN DE RUTAS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "backend", "db")
SIM_DB_FILE = os.path.join(DB_PATH, "simulador.db")
NEXUS_DB_FILE = os.path.join(DB_PATH, "rpk_industrial.db")

# --- GESTIÓN DE ARCHIVO DB ---
def manage_db_files():
    """Realiza la copia física de la base de datos si rpk_industrial.db no existe."""
    if not os.path.exists(NEXUS_DB_FILE):
        if os.path.exists(SIM_DB_FILE):
            print(f"[INFO] Preservando datos: Copiando {SIM_DB_FILE} a {NEXUS_DB_FILE}...")
            shutil.copy2(SIM_DB_FILE, NEXUS_DB_FILE)
        else:
            print("[WARN] Advertencia: No se detectó 'simulador.db'. Se iniciará una base de datos Nexus desde cero.")
    else:
        print(f"[INFO] El archivo {NEXUS_DB_FILE} ya existe. Procediendo a actualizar esquema.")

# --- DEFINICIÓN DE ESQUEMA (SQLAlchemy) ---
Base = declarative_base()

class StockSnapshot(Base):
    __tablename__ = 'stock_snapshot'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    articulo = Column(String, index=True, nullable=False)
    descripcion = Column(String)
    cantidad = Column(Float, default=0.0)
    valor_total = Column(Float, default=0.0)
    cliente = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class TiemposCarga(Base):
    __tablename__ = 'tiempos_carga'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    centro_trabajo = Column(String, index=True, nullable=False)
    horas_disponibles = Column(Float, default=0.0)
    horas_ocupadas = Column(Float, default=0.0)
    saturacion_pct = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)

# --- EJECUCIÓN ---
def run_migration():
    # 1. Asegurar existencia de archivo físico
    manage_db_files()
    
    # 2. Conexión con SQLite (uso de URL multiplataforma)
    engine_url = f"sqlite:///{NEXUS_DB_FILE.replace(os.sep, '/')}"
    engine = create_engine(engine_url)
    
    # 3. Creación de tablas (no afecta a las existentes en simulador.db)
    print("[INFO] Creando modelos RPK NEXUS (stock_snapshot, tiempos_carga)...")
    Base.metadata.create_all(bind=engine)
    
    print(f"[OK] Migración completada. Base de datos RPK Nexus lista en:\n   {NEXUS_DB_FILE}")

if __name__ == "__main__":
    run_migration()
