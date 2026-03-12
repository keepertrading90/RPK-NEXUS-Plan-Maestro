# BLUEPRINT_NEXUS v5.9.1 (Fase 3.1 Reportes Avanzados de Automoción — Marzo 2026)
Este documento es la **fuente de la verdad arquitectónica** para la IA y los desarrolladores humanos de acuerdo al protocolo de Industria 5.0.

## ARQUITECTURA HÍBRIDA NEXUS-IA
- **Framework Principal**: FastAPI + DuckDB (Analítico) + SQLite (Transaccional)
- **Capa Agential**: Google Agent Development Kit (ADK) en puerto 8004.
- **Motor IA activo**: Qwen 2.5-Coder 7B (via Ollama local).
- **Fases IA**: Fase 1 (keyword SQL) → Fase 2 (Qwen SQL+narrativa) → Fase 3 (RAG + ADK Proxy + Streaming SSE).

---

## RESTRICCIONES Y CARRILES

| Carril | Motor | Propósito |
|--------|-------|-----------|
| **Carril A (Transaccional)** | SQLite | Mutaciones de usuario, escenarios, configuraciones |
| **Carril B (Analítico)** | DuckDB + Parquet | Lecturas masivas de Tiempos, Pedidos, Stock y Albaranes |
| **Carril IA (Neuronal)** | Qwen 2.5 + RAG en memoria | Chat inteligente, SQL generado, respuesta narrativa |

- **Python Portable**: Siempre `_SISTEMA\runtime_python\python.exe`
- **Vectorización Obligatoria**: Pandas/NumPy. Prohibido `for` o `.iterrows()`.
- **Lectura Excel**: Solo `calamine`. Prohibido `openpyxl` para lectura masiva.

---

## MOTOR IA — FASE 3 (Activa desde 10/03/2026)

### Archivos del motor (`backend/`)

| Archivo | Propósito |
|---------|-----------|
| `nexus_rag.py` | Índice en memoria de artículos y centros (construido al arrancar desde DuckDB). Inyecta contexto exacto en el prompt de Qwen antes de cada consulta. |
| `nexus_memoria.py` | Memoria conversacional multi-turno por `session_id`. Máx 8 turnos. Formatea historial para el prompt de Qwen. |
| `nexus_alertas.py` | Alertas proactivas: analiza DuckDB al arrancar y detecta stock crítico (<30% objetivo), centros saturados (>14h/día), OEE bajo (<60%). |

### Flujo de una consulta de chat (Fase 3 - Integración ADK)
```
Usuario pregunta
  ↓
[NEXUS PROXY] intercepta /api/v1/chat/stream
  ↓
[ADK SERVER] localhost:8004/run_sse recibe payload y contexto de sesión
  ↓
[AGENTE QUEN_ARQUITECTO] evalúa e invoca herramientas (ej: consultar_base_datos_nexus)
  ↓
[DuckDB] Carril B ejecuta SQL analítico asegurado
  ↓
[ADK SERVER] emite JSON stream
  ↓
[NEXUS PROXY] formatea token a token (Event-Stream)
  ↓
[SSE FRONTEND] tokens llegan letra a letra (cursor ▋ parpadeante)
```

### Tablas DuckDB (`rpk_analytical.duckdb`)

| Tabla | Columnas clave | Notas |
|-------|---------------|-------|
| `existencias` | Fecha, Cliente, Articulo, Descripcion, Cantidad, Stock_Objetivo | Particionada year/month |
| `carga_centros` | Fecha, Centro(VARCHAR), Carga_Dia, month, year | Centros 256-800; Centro es texto |
| `maestro_fleje` | Articulo, Centro(INT), Piezas_Hora, OEE, Cadencia_Min/Max/Actual | Centros 109-550 incluyendo 142 |
| `pedidos` | Fecha, Cliente, Articulo, Cantidad, Valor_Total | |
| `albaranes` | Fecha, Cliente, Articulo, Cantidad, Valor_Total | |
| `tiempos_detalle_articulo` | Articulo, Centro, Tiempo_Ciclo, OEE | |
| `ocupacion` | Fecha_Snapshot, Mapa, Ubicacion, Tipo_Ubicacion, Vacia, month, year | Novedad V5.8.1 |

> ⚠️ **Centro 142 existe en `maestro_fleje` pero NO en `carga_centros`** (carga analítica solo cubre centros 256+).

---

## ESTRUCTURA DEL BACKEND (Python 3.12 / FastAPI)

### Motor ETL — Data Lakehouse
- **ETL Diario**: `scripts/etl_nexus_master.py` — Escribe Parquets particionados `year=/month=/`.
- **ETL Histórico**: `scripts/etl_historical_master.py`, `scripts/etl_historical_ocupacion.py` — Ingesta masiva.
- **Analytics DB**: `backend/db/rpk_analytical.duckdb` — Contiene vistas mapeadas con `union_by_name`.
- **Dominios**: existencias, carga_centros, carga_detalle, pedidos, albaranes, maestro_fleje, ocupacion.

### Endpoints API REST (`backend/server_nexus.py`)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1/chat` | POST | Chat IA. Actúa como **Proxy** síncrono conectando con el servidor ADK (localhost:8004) |
| `/api/v1/chat/stream` | POST | Chat IA con **Streaming SSE**. Proxy del tráfico JSON del Agente ADK hacia el Frontend en tiempo real |
| `/api/v1/alertas` | GET | Alertas proactivas del motor nexus_alertas (stock crítico, centros saturados, OEE bajo) |
| `/api/v1/rag/status` | GET | Estado de los motores IA: RAG, Memoria, Alertas |
| `/api/v1/artifacts` | GET | Lista de artifacts generados por la IA (JSON, MD) |
| `/api/v1/artifact/{name}` | GET | Contenido de un artifact |
| `/api/fechas` | GET | Rango de fechas disponibles en el Lakehouse |
| `/api/summary` | GET | KPIs de stock y top clientes |
| `/api/pedidos/summary` | GET | KPIs de pedidos pendientes |
| `/api/tiempos/summary` | GET | KPIs de carga y tiempos por centro |
| `/api/albaranes/resumen` | GET | KPIs albaranado |
| `/api/reports/stock-pdf` | POST | PDF Stock Básico |
| `/api/reports/stock-advanced` | POST | PDF Stock Avanzado (Evolución, Pareto, Objetivos) |
| `/api/reports/tiempos-pdf` | POST | PDF Tiempos |
| `/api/reports/pedidos-pdf` | POST | PDF Pedidos |
| `/api/reports/comparativa-pdf` | POST | PDF Comparativa |
| `/api/reports/escenario-pdf` | POST | PDF Escenario |
| `/api/simulate/base` | GET | Base simulador |
| `/api/simulate/{scenario}` | GET | Simulador con escenario |
| `/api/scenarios` | GET/POST | CRUD escenarios |
| `/api/articulos/` | POST/DEL | CRUD artículos simulador |
| `/api/ocupacion/summary`| GET | KPIs de ocupación y evolución histórica |

### Resiliencia de Red
- Todo acceso a `Y:\` envuelto en `try/except`. Si hay file lock → `logging.warning` + terminación silenciosa.

---

## ESTRUCTURA DEL FRONTEND (HTML/JS Vanilla)

### Design System
- **Paleta RPK**: Fondo `#0f0f0f`, Paneles `#1a1a1a`, Acento `#E30613`, Texto `#ffffff / #9ca3af`
- **Tipografía**: Inter (Google Fonts)
- **Estética**: Glassmorphism Dark Mode

### Módulos (`frontend/modules/`)

| Módulo | Ruta Servida | Archivo HTML |
|--------|-------------|--------------|
| Portal Central | `/portal/` | `frontend/ui/index.html` |
| Stock y Almacén | `/mod/stock/` | `frontend/modules/stock/index.html` |
| Carga y Tiempos | `/mod/tiempos/` | `frontend/modules/tiempos/index.html` |
| Pedidos de Venta | `/mod/pedidos/` | `frontend/modules/pedidos/index.html` |
| Albaranes | `/mod/albaranes/` | `frontend/modules/albaranes/index.html` |
| Simulador | `/mod/simulador/` | `frontend/modules/simulador/index.html` |
| **Central IA** | `/mod/ia_agents/` | `frontend/modules/ia_agents/index.html` |
| Ocupación | `/mod/ocupacion/` | `frontend/modules/ocupacion/index.html` |

---

## DICCIONARIO DE DATOS (Contratos API)

- **Chat Request**: `{"text": str, "session_id": str, "limpiar_historial": bool}`
- **Chat Response**: `{"response": str, "artifact": str|null}`
- **SSE Stream**: eventos `{status: thinking|query|streaming|done|error}` + `{token: str}` + `{full: str}`
- **Alertas**: `{"alertas": [{tipo, nivel, color, icono, titulo, mensaje}], "criticas": int, "advertencias": int}`
- **Respuesta estándar**: `{"status": "success|error", "data": [...], "message": "..."}`
- **Graceful Degradation**: Si Parquet del día no existe → sirve ayer con `{"warning": "Using stale data"}`.

---

## HISTORIAL DE VERSIONES

| Fecha | Versión | Cambios |
|-------|---------|---------|
| 12/03/2026 | **v5.9.1** | **Informes de Automoción**: Implementación del motor `pdf_stock_advanced.py`. Análisis de capital inmovilizado, comparativas mensuales y Pareto de clientes con filtros profundos por fecha y artículo. |
| 11/03/2026 | v5.9.0 | **Integración ADK Proxy**: Delegación de ejecución a Google ADK (puerto 8004). El backend Nexus ahora enruta peticiones SSE hacia el framework de agentes para evitar alucinaciones SQl monolíticas y dotar de acceso nativo DuckDB a *Quen_Arquitecto*. |
| 10/03/2026 | v5.8.0 | Motor IA Fase 3: RAG en memoria (`nexus_rag.py`), Memoria conversacional multi-turno (`nexus_memoria.py`), Alertas proactivas (`nexus_alertas.py`), Streaming SSE token a token (`/api/v1/chat/stream`), Auto-generación de artifacts MD, corrección de consultas DuckDB (Centro 142 → maestro_fleje). |
| 10/03/2026 | v5.7.5 | Fase 2 IA: Qwen2.5-Coder genera SQL + narrativa en una llamada. Prewarm del modelo al arrancar. `nexus_rag.py` indexa artículos y centros. |
| Mar 2026 | v5.7.0 | IA Hybrid Gateway: Chat unificado y acceso a artefactos de IA. |
| Mar 2026 | v5.6.0 | Módulo Simulador: Gestión de Artículos (CRUD) con persistencia en Excel Maestro. |
| Mar 2026 | v5.5.2 | Comparativa KPI Avanzada, sanitización de ghost history SQLite. |
| Mar 2026 | v5.5.1 | Evolución "Camino Dorado": V2 Motor Analítico inyectado en Simulador V1. |
| Mar 2026 | v5.5 | Integración nativa del Simulador V1 Classic. |
| Feb 2026 | v5.5 RC | Motor ETL Data Lakehouse, UI Glassmorphism, PDF Reports. |
| Ene 2026 | v5.0 | Base FastAPI + DuckDB. |

## TOPOLOGÍA DE DESPLIEGUE (AGENTES)
- **Backend Core**: Servidor Nexus port 8000.
- **Agent Server**: Google Agent Development Kit (ADK) port 8004.
- **LLM Engine**: Ollama (localhost:11434).


