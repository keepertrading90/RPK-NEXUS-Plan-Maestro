from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import os

# Usamos la misma base de datos que Nexus Hub pero vía SQLAlchemy para el Simulador
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db", "rpk_industrial.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Scenario(Base):
    __tablename__ = "sim_scenarios" # Cambiamos nombre para evitar colisiones si las hubiera

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    dias_laborales = Column(Integer, default=238)
    horas_turno_global = Column(Integer, default=16)
    center_configs_json = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    details = relationship("ScenarioDetail", back_populates="scenario", cascade="all, delete-orphan")

class ScenarioDetail(Base):
    __tablename__ = "sim_scenario_details"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("sim_scenarios.id"))
    articulo = Column(String)
    centro = Column(String)
    oee_override = Column(Float, nullable=True)
    ppm_override = Column(Float, nullable=True)
    demanda_override = Column(Float, nullable=True)
    new_centro = Column(String, nullable=True)
    horas_turno_override = Column(Integer, nullable=True)
    setup_time_override = Column(Float, nullable=True)
    personnel_ratio_override = Column(Float, nullable=True)

    scenario = relationship("Scenario", back_populates="details")

class ScenarioHistory(Base):
    __tablename__ = "sim_scenario_history"

    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("sim_scenarios.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    name = Column(String)
    changes_count = Column(Integer)
    details_snapshot = Column(String)

    scenario = relationship("Scenario")

def init_sim_db():
    Base.metadata.create_all(bind=engine)
