# BLUEPRINT_NEXUS v6.6 (Rediseño UI Visual-First — Abril 2026)
Este documento es la **fuente de la verdad arquitectónica** para la IA y los desarrolladores humanos de acuerdo al protocolo de Industria 5.0.

---

## MOTOR ANALÍTICO - RUTAS MAESTRAS (Novedad v5.9.3)
- **Fuente Única**: Hoja `BASE DE DATOS_1` en `MAESTRO FLEJE.xlsx`.
- **Lógica de Filtrado de Cadencias**: Se omiten centros de trabajo que tengan exactamente la misma cadencia (`prod_horaria`) que la fase anterior dentro del mismo artículo, salvo que sea la fase inicial (Fase 10).
- **Filtros Avanzados (Simulator)**:
    - **Fase 10 Priorizada**: Al cargar, el simulador selecciona automáticamente solo los centros de Fase 10 para una vista de cabecera limpia.
    - **Filtro UATC**: Nuevo desplegable en la barra de control para filtrar por Unidad de Atribución de Coste.

---

## SIMULADOR DINÁMICO N-MÁQUINAS (Novedad v6.5)
- **Arquitectura DAG**: Basado en un Grafo Dirigido Acíclico (Directed Acyclic Graph). Las máquinas se conectan vía `feedsInto`.
- **Motor Topológico**: Procesamiento en orden topológico (Algoritmo de Kahn) garantizando que ninguna máquina procese material antes de que su upstream termine el lote de transferencia.
- **Zero-Latency Client**: El motor de simulación (`simulator.engine.ts`) corre íntegramente en el navegador del usuario (Next.js).
- **UI Interactiva v6.6**:
    - **Navegación por Iconos**: Header minimalista con barra de acciones (Añadir, Guardar, Historial, KPIs).
    - **Drawer Lateral (Right Slide)**: La configuración de máquinas y resultados se desplaza a un panel lateral emergente para liberar el área de trabajo.
    - **Diagrama de Flujo Navegable**: Los nodos del DAG son clicables y actúan como lanzadores de configuración.
    - **Maximized Visuals**: Área central reservada íntegramente para Diagrama y Gantt en alta resolución.

---

## ARQUITECTURA HÍBRIDA NEXUS-IA
- **Framework Principal**: FastAPI + DuckDB (Analítico) + SQLite (Transaccional)
- **Capa Agential**: Google Agent Development Kit (ADK) en puerto 8004.
- **Motor IA activo**: Qwen 2.5-Coder 7B (via Ollama local).
- **Gemelo Digital (Fase 3/4)**: Integración de predicción hacia adelante (Forward-Pass) con motor in-memory DuckDB y persistencia de escenarios `what-if` en SQLite `nexus_transaccional.db`.

---

## RESTRICCIONES Y CARRILES

| Carril | Motor | Propósito |
|--------|-------|-----------|
| **Carril A (Transaccional)** | SQLite (`nexus_transaccional.db`) | Mutaciones de usuario, escenarios predictivos (`escenarios_simulacion`), configuraciones |
| **Carril B (Analítico)** | DuckDB + Parquet | Lecturas masivas de Tiempos, Pedidos, Stock, Albaranes y Gemelo Digital Forward-Pass |
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

### Motor ETL — Data Lakehouse (V5.6 Fix)
- **ETL Diario**: `scripts/etl_nexus_master.py` — Escribe Parquets particionados `year=/month=/`.
- **ETL Histórico**: `scripts/etl_historical_master.py` — Ingesta masiva con sobrescritura automática.
- **Protocolo de Idempotencia (CRÍTICO)**: 
    - Los Parquets se nombran como `[modulo]_[YYYYMMDD].parquet`. 
    - **PROHIBIDO** incluir timestamps de hora (`HHMMSS`) en el nombre, ya que DuckDB encadena todos los ficheros del directorio y esto causaría duplicación sistemática de totales.
    - Cada re-ejecución del ETL para una fecha dada DEBE sobrescribir el fichero anterior.
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

| Módulo | Ruta Servida | Archivo HTML / Framework |
|--------|-------------|--------------------------|
| Portal Central | `/portal/` | `frontend/ui/index.html` |
| Stock y Almacén | `/mod/stock/` | `frontend/modules/stock/index.html` |
| Carga y Tiempos | `/mod/tiempos/` | `frontend/modules/tiempos/index.html` |
| Pedidos de Venta | `/mod/pedidos/` | `frontend/modules/pedidos/index.html` |
| Albaranes | `/mod/albaranes/` | `frontend/modules/albaranes/index.html` |
| **Simulador Dinámico** | `/mod/simulador/` | **Next.js (App Router) v6.5** |
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
| 24/04/2026 | **v6.6.1** | **Limpieza Estructural (Zero-Noise)**: Refactorización del árbol de directorios aislando todos los scripts experimentales, de debug y de fases superadas en el directorio `OLD/`. Se estandarizó `INICIAR_NEXUS.bat` como única puerta de entrada válida y se depuró el directorio de scripts para dejar exclusivamente los archivos de producción. |
| 16/04/2026 | **v6.6** | **Rediseño UI "Visual-First"**: Maximización de Diagrama y Gantt (100% ancho). Implementación de Drawer lateral para parámetros. Header minimalista con iconos + tooltips. Interactividad total en nodos SVG para lanzamiendo de config. |
| 16/04/2026 | **v6.5** | **Simulador Dinámico N-Máquinas**: Refactorización completa de la arquitectura reactiva. Motor DAG (Kahn Algorithm) en frontend. Soporte para lotes de transferencia encadenados. Drag & Drop con dnd-kit. Visualización SVG de flujo y Gantt multi-fila (máx 10 máquinas). |
| 31/03/2026 | **v6.1.3** | **Hotfix Algoritmo Forward-Pass**: Corrección crítica en `analytics_core.py`. La ratio de cálculo de horas proyectadas estaba invertida (`PPM Secundario / PPM F10`), provocando cientos de horas ficticias en procesos rápidos. Se ha corregido la regla de tres a `Horas F10 * (PPM F10 / PPM Secundario)` garantizando un balance real de capacidad. |
| 31/03/2026 | **v6.1.2** | **Cierre Fase 4.1 (Estabilidad & UX)**: Resolución de `ReferenceError: TWIN_THRESHOLDS` en frontend. Implementación de tooltips explicativos (nativos `title`) en cabeceras de tabla y KPIs del Gemelo Digital. Reactividad total con `oninput` en horizonte de días. |
| 31/03/2026 | **v6.1.1** | **Escalado Dinámico Predictivo**: Umbrales de saturación (`TWIN_THRESHOLDS`) ahora vinculados al horizonte temporal. Exclusión del centro 799. Mejora de reactividad en el input de días (oninput). |
| 31/03/2026 | **v6.1** | **Refinamiento Gemelo Digital (Fase 4.1)**: Mejora del algoritmo Forward-Pass con resiliencia ante discrepancias ID de máquinas y centros. Integración de la ingesta directa desde `carga_cabeceras.parquet` (Fase 10). Scroll infinito en visualización de centros y filtrado de ruido (centros 9xx, 724, 798). |
| 30/03/2026 | **v6.0** | **Gemelo Digital Completado (Fase 3 & 4)**: Implementación de la `PredictiveDashboard` en frontend evidenciando cuellos de botella preventivos y flujo horario de OFs hacia secundarios. Transición del backend SQLite a `nexus_transaccional.db` aislando las tablas de escenarios de simulación y protegiendo el Carril A transaccional. |
| 16/03/2026 | **v5.9.2** | **Rutas Maestras**: Integración de la hoja `BASE DE DATOS_1` como fuente única. Implementado filtrado vectorial de fases redundantes por cadencia idéntica. Adición de campos `FASE` y `UATC` al motor DuckDB. |
| 12/03/2026 | v5.9.1 | **Informes de Automoción**: Implementación del motor `pdf_stock_advanced.py`. Análisis de capital inmovilizado, comparativas mensuales y Pareto de clientes con filtros profundos por fecha y artículo. |
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

## ESTRUCTURA DE ARCHIVO (`OLD`)
Para mantener el paradigma "Zero-Noise", cualquier archivo que no sea indispensable para el `INICIAR_NEXUS.bat` actual, ha sido movido al directorio `/OLD`. 
- **Contiene**: Versiones previas del simulador, scripts temporales (ej. `tmp_*.py`, `debug_*.py`), y excels de análisis ad-hoc.
- **Regla**: El motor ETL de producción y el backend de FastAPI NUNCA deben leer dependencias ni datos desde la carpeta `OLD`.

---

## TOPOLOGÍA DE DESPLIEGUE (AGENTES)
- **Backend Core**: Servidor Nexus port 8000.
- **Agent Server**: Google Agent Development Kit (ADK) port 8004.
- **LLM Engine**: Ollama (localhost:11434).
