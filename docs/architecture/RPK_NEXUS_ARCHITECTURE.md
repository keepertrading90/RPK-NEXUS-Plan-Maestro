# 🏗️ Documentación de Arquitectura Hiperdetallada: RPK NEXUS v4.0

## 1. 🎯 Visión y Propósito del Sistema
**RPK NEXUS** es el Centro de Mando Industrial diseñado para la Gestión del Plan Maestro de Producción de RPK. Actúa como un ecosistema unificado que centraliza información crítica de planta, logística y ventas en una **Single Source of Truth** (Única Fuente de Verdad) local, eliminando la latencia de red y la fragmentación de hojas de cálculo.

---

## 2. 📂 Estructura de Proyecto (Layout Físico)
El proyecto sigue el estándar **RPK Agentic Standard v7.0**, con una separación clara de responsabilidades:

```text
Plan Maestro RPK NEXUS/
├── .agent/                  # 🤖 Reglas y workflows del Agente AI
├── _SISTEMA/                # 🚀 Entorno Python Portable (runtime_python)
├── backend/                 # 🧠 Lógica de Negocio y Servidor
│   ├── core/                # Motores de simulación y analítica
│   ├── db/                  # Capa de datos (SQLite + Esquemas)
│   ├── api/                 # Endpoints especializados (Futuros)
│   └── server_nexus.py      # Servidor Central FastAPI (El Corazón)
├── frontend/                # 🎨 Interfaz de Usuario
│   ├── modules/             # Micro-Frontends (Dashboard Paneles)
│   │   ├── pedidos/         # Panel de Gestión de Pedidos de Venta
│   │   ├── simulador/       # Simulador de Producción / Escenarios
│   │   ├── stock/           # Dashboard de Existencias y Valoración
│   │   └── tiempos/         # Planificación de Cargas y Saturation
│   ├── ui/                  # Portal Hub Central (Portal de Usuario)
│   └── assets/              # Recursos globales (Logos, CSS base)
├── scripts/                 # ⚙️ Utilidades de Operaciones (Ops)
│   ├── qa_scanner.py        # Auditoría de sintaxis y patrones RPK
│   ├── ops_sync.py          # Sincronización Golden con GitHub
│   └── sync_nexus.py        # Motor ETL de ingesta diaria
├── docs/                    # 📄 Documentación y Logs
│   ├── architecture/        # [NUEVO] Este documento y diagramas
│   └── logs/                # Historial de cambios y actualizaciones
├── INICIAR_NEXUS.bat        # ⚡ Lanzador Maestro Único
└── README.md                # Guía rápida del proyecto
```

---

## 3. 🧠 Arquitectura Backend (Deep-Dive)

### 3.1. Servidor Central (`server_nexus.py`)
Utiliza el framework **FastAPI** por su alto rendimiento y tipado estático (Pydantic).
- **Enrutamiento Inteligente**: Gestiona tanto la API de datos como el servicio de archivos estáticos para los diferentes módulos.
- **Redirecciones Relativas**: Implementa lógica para forzar barras al final (`/mod/stock/`), asegurando que las rutas de assets (`./styles.css`) funcionen independientemente de dónde se despliegue el sistema.
- **Seguridad**: Sigue el patrón "Zero-Trust" validando cada entrada de datos.

### 3.2. Capa de Datos (SQLite Native)
- **Base de Datos**: `backend/db/rpk_industrial.db`.
- **Motor Dual**: 
  - **SQLite Native**: Para consultas de alta velocidad en dashboards de analítica.
  - **SQLAlchemy (ORM)**: Utilizado específicamente en el módulo del **Simulador** para gestionar la persistencia de escenarios, histórico de cambios y Overrides.
- **Inyección de Datos**: `sync_nexus.py` realiza un proceso ETL diario que lee archivos brutos del ERP (UNC: `\\RPK4TGN\ofimatica\...`) y los transforma en tablas normalizadas.

### 3.3. Motores Analíticos
- **`simulation_core.py`**: Motor de cálculo que procesa OEE, PPM y Demanda para proyectar saturaciones de centros.
- **`analytics_core.py`**: Algoritmos de cálculo de cobertura cruzando `Stock_Snapshot` con `Tiempos_Detalle`.

---

## 4. 🎨 Paneles de Control (Micro-Frontends)

### 4.1. Portal Hub (Nexus Hub)
- **Tecnología**: HTML5 / Vanilla JS.
- **Características**:
  - **Bento UI**: Tarjetas dinámicas con KPIs vivos.
  - **Integrated Assistant**: Chatbot que traduce lenguaje natural a consultas SQL (`/api/v1/chat`).
  - **Global Stats**: Consumo directo de `/api/v1/hub_stats`.

### 4.2. Dashboard de Tiempos (Planning Panel)
- **Foco**: Saturación de centros de trabajo (Centros de Coste).
- **Drilldown**: Capacidad de ver exactamente qué Orden de Fabricación (OF) está cargando un centro en un mes específico.
- **Carga de Trabajo**: Cálculo basado en la captura matutina (06:00-08:00 AM) para fidelidad total del plan.

### 4.3. Dashboard de Stock (Logistics Panel)
- **Foco**: Valoración de almacén y cumplimiento de objetivos.
- **Visualización**: Mapas de calor de clientes y evolución temporal del valor total.
- **Stock Objetivo**: Comparativa visual contra las metas de inventario definidas por la dirección.

### 4.4. Panel de Pedidos de Venta (Sales Orders)
- **Foco**: Cartera de pedidos pendiente de servir.
- **KPIs**: Importe total en piezas, Valor en Euros y recurrencia por artículos top.
- **Datos**: Ingesta masiva de >270,000 registros históricos para análisis de tendencias.

### 4.5. Simulador de Producción (Sim V3 Classic)
- **Foco**: "What-If" Planning.
- **Capacidades**: Cambiar cadencias, centros de trabajo y demanda para ver el impacto inmediato en el Plan Maestro de los centros afectados.

---

## 5. 💅 Design System: Estándares RPK

### 5.1. Colores y Estilos (CSS)
El sistema utiliza CSS nativo concentrado en `frontend/assets/` y estilos específicos por módulo:
- **Color Primario**: `#E30613` (RPK Red).
- **Fondo**: `#0f0f0f` (Carbon Dark Mode).
- **Cards**: Efecto Glassmorphism sutil con bordes definidos.
- **Tipografía**: `Roboto` para legibilidad técnica e `Inter` para interfaces modernas.

### 5.2. Visualización de Datos
- **Librería**: `Chart.js` personalizada con degradados RPK.
- **Estandarización**: Todos los gráficos mantienen la misma escala cromática para evitar fatiga cognitiva del usuario.

---

## 6. 🔄 Integraciones y Automatizaciones

### 6.1. Integración con ERP (Excel-Live)
El sistema no espera a que el ERP exporte a una base de datos central; lee directamente los archivos `.xlsx` maestros:
- **Ruta UNC**: `\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\...`
- **Sincronización**: Automática mediante el lanzador.

### 6.2. Ciclo de Vida de Desarrollo (Ops)
Cualquier cambio debe pasar por:
1.  **QA Audit**: `scripts/qa_scanner.py` verifica que no haya "print" residuales, rutas locales hardcodeadas o errores de sintaxis.
2.  **OPS Sync**: `scripts/ops_sync.py` realiza el commit y push coordinado a GitHub, manteniendo el repositorio limpio.

---

## 7. 📈 Registro de Actualizaciones Destacadas
- **v3.1**: Unificación de módulos Stock/Tiempos.
- **v3.2**: Integración de Simulador V1 Classic y Asistente IA.
- **v3.5**: Corrección de Snapshots de Tiempos (Prioridad Mañana) y normalización de API.
- **v4.0 (Actual)**: Inclusión del Módulo de Pedidos de Venta e infraestructura de Arquitectura Detallada.

---
**Documento generado por Antigravity (APS) - 2026-02-20**
**Validado por Sistema RPK Zero-Trust**
