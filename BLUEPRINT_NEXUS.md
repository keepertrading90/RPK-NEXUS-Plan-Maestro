# BLUEPRINT_NEXUS v5.5
Este documento es la **fuente de la verdad arquitectónica** para la IA y los desarrolladores humanos de acuerdo al protocolo de Industria 5.0.

## RESTICCIONES Y CARRILES
- **Carril A (Transaccional - SQLite)**: Para mutaciones de datos del usuario, guardar escenarios y configuraciones (server_nexus.py).
- **Carril B (Analítico - DuckDB/Parquet)**: Para lectura masiva. WASM en frontend. Prohibido openpyxl, usar calamine / polars / pyarrow.
- **Python Portable**: Siempre ejecutar usando `_SISTEMA\runtime_python\python.exe`.

## ESTRUCTURA DEL BACKEND (Python 3.12 / FastAPI)
- **Framework**: FastAPI
- **Vectorización Obligatoria**: Pandas/NumPy para cálculos. Prohibido usar bucles `for` o `.iterrows()`.
- **Nuevos Endpoints**:
  - `POST /api/reports/stock-pdf`: Generación de informes en PDF de Inventario Financiero utilizando ReportLab (`backend/api/pdf_stock.py`).

## ESTRUCTURA DEL FRONTEND (HTML/JS Vanilla y Next.js)
- **Diseño System**: TailwindCSS, CSS Variables. RPK Red `#E30613`, Dark bg `#0f0f0f`.
- **Módulo de Stock**: Interfaz Vanilla en `frontend/modules/stock/index.html` con sistema de descarga de PDF.
- **Componentes React**: Ubicados bajo Next.js App Router (si aplica en el futuro).

## DICCIONARIO DE DATOS (Contratos)
* FastAPI: Las respuestas siempre deben contener `status`, `data` y `message`.
* Interfaces TS: Situadas en `src/types/` (si Next.js está en uso). En `index.html` se consumen endpoints como `/api/summary` y `/api/reports/stock-pdf`.
