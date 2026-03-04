# BLUEPRINT_NEXUS v5.5 (Release Candidate - Marzo 2026)
Este documento es la **fuente de la verdad arquitectónica** para la IA y los desarrolladores humanos de acuerdo al protocolo de Industria 5.0.

---

## RESTRICCIONES Y CARRILES

| Carril | Motor | Propósito |
|--------|-------|-----------|
| **Carril A (Transaccional)** | SQLite | Mutaciones de usuario, escenarios, configuraciones |
| **Carril B (Analítico)** | DuckDB + Parquet | Lecturas masivas de Tiempos, Pedidos, Stock y Albaranes |

- **Python Portable**: Siempre `_SISTEMA\runtime_python\python.exe`
- **Vectorización Obligatoria**: Pandas/NumPy. Prohibido `for` o `.iterrows()`.
- **Lectura Excel**: Solo `calamine`. Prohibido `openpyxl` para lectura masiva.

---

## ESTRUCTURA DEL BACKEND (Python 3.12 / FastAPI)

### Motor ETL — Data Lakehouse
- **ETL Diario**: `scripts/etl_nexus_master.py` — Escribe Parquets particionados `year=/month=/`.
- **ETL Histórico**: `scripts/etl_historical_master.py` — Ingesta masiva de archivos históricos de red (`Y:\`).
- **Analytics DB**: `backend/db/rpk_analytical.duckdb` — Contiene vistas mapeadas con `union_by_name` (resiliencia de esquema).
- **Dominos**: existencias, carga_centros, carga_detalle, pedidos, **albaranes**.

### Endpoints API REST (`backend/server_nexus.py`)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/fechas` | GET | Rango de fechas disponibles en el Lakehouse |
| `/api/summary` | GET | KPIs de stock y top clientes con filtro fecha |
| `/api/customers` | GET | Top clientes de Stock por periodo |
| `/api/pedidos/summary` | GET | KPIs de pedidos pendientes + evolución |
| `/api/pedidos/articulos` | GET | Top artículos con cartera |
| `/api/tiempos/summary` | GET | KPIs de carga y tiempos por centro |
| `/api/albaranes/resumen` | GET | KPIs albaranado + evolución diaria |
| `/api/albaranes/clientes` | GET | Top clientes por importe albaranado |
| `/api/albaranes/articulos` | GET | Top artículos expedidos |
| `/api/reports/stock-pdf` | POST | Generación PDF Stock (`backend/api/pdf_stock.py`) |
| `/api/reports/tiempos-pdf` | POST | Generación PDF Tiempos (`backend/api/pdf_tiempos.py`) |
| `/api/reports/pedidos-pdf` | POST | Generación PDF Pedidos (`backend/api/pdf_pedidos.py`) |
| `/api/reports/comparativa-pdf` | POST | Generación PDF Comparativa (`backend/api/pdf_comparativa.py`) |
| `/api/reports/escenario-pdf` | POST | Generación PDF Escenario Individual (`backend/api/pdf_escenario.py`) |
| `/api/simulate/base` | GET | Carga dataframe del simulador. Acepta flag `?use_actual=true` para Motor Demanda ERP |
| `/api/simulate/{scenario}` | GET | Simulador mutado según DB. Acepta flag `?use_actual=true` |
| `/api/simulate/preview` | POST | Preview on-the-fly (`overrides_list`) sin guardado. Acepta flag `?use_actual=true` |
| `/api/scenarios` | GET/POST | Listado y Creación de escenarios |
| `/api/articulos/` | POST/DEL | CRUD de Artículos en Simulador (Añade/Borra con backup automático y cola JSON si el Excel está bloqueado) |

### Resiliencia de Red
- Todo acceso a `Y:\` envuelto en `try/except`. Si hay file lock → `logging.warning` + terminación silenciosa.

---

## ESTRUCTURA DEL FRONTEND (HTML/JS Vanilla)

### Design System
- **Paleta RPK**: Fondo `#0f0f0f`, Paneles `#1a1a1a`, Acento `#E30613`, Texto `#ffffff / #9ca3af`
- **Tipografía**: Inter (Google Fonts)
- **Estética**: Glassmorphism Dark Mode (`backdrop-filter: blur`)
- **Gráficos**: Chart.js

### Módulos (`frontend/modules/`)

| Módulo | Ruta Servida | Archivo HTML |
|--------|-------------|--------------|
| Portal Central | `/portal/` | `frontend/ui/index.html` |
| Stock y Almacén | `/mod/stock/` | `frontend/modules/stock/index.html` |
| Carga y Tiempos | `/mod/tiempos/` | `frontend/modules/tiempos/index.html` |
| Pedidos de Venta | `/mod/pedidos/` | `frontend/modules/pedidos/index.html` |
| Albaranes | `/mod/albaranes/` | `frontend/modules/albaranes/index.html` |
| Simulador | `/mod/simulador/` | `frontend/modules/simulador/index.html` |

---

## DICCIONARIO DE DATOS (Contratos API)

- **Respuesta estándar**: `{"status": "success|error", "data": [...], "message": "..."}`
- **Graceful Degradation**: Si el Parquet del día no existe → sirve el de ayer con flag `{"warning": "Using stale data"}`.
- **Parquets Transaccionales**: Particionados `year=YYYY/month=MM/` → nunca sobreescriben.
- **Parquets Maestros (Snapshots)**: Se sobreescriben como `snapshot_actual.parquet`.

---

## HISTORIAL DE VERSIONES

| Fecha | Versión | Cambios |
|-------|---------|---------|
| Mar 2026 | v5.6.0 | Módulo Simulador: Gestión de Artículos (CRUD) con persistencia directa y segura en Excel Maestro `MAESTRO FLEJE_v1.xlsx` |
| Mar 2026 | v5.5.2 | Comparativa KPI Avanzada, sanitización de ghost history SQLite, overrides dinámicos de MOD y Turnos en simulador |
| Mar 2026 | v5.5.1 | Evolución "Camino Dorado": V2 Motor Analítico inyectado en Simulador V1 (Demanda Neta real) vía `use_actual` |
| Mar 2026 | v5.5 | Integración nativa del Simulador V1 Classic (Zero-Latency con SQLAlchemy/Calamine/Cache .pkl) |
| Feb 2026 | v5.5 RC | Motor ETL Data Lakehouse, UI Glassmorphism, PDF Reports (Stock, Tiempos, Pedidos), Módulo Albaranes |
| Ene 2026 | v5.0 | Base FastAPI + DuckDB |
