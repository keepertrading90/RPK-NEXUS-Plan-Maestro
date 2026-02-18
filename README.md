# RPK NEXUS - Plan Maestro de Producción Industrial

![RPK NEXUS](https://img.shields.io/badge/RPK-NEXUS-E30613?style=for-the-badge) ![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge) ![Version](https://img.shields.io/badge/Version-3.1-blue?style=for-the-badge)

## 🎯 Visión General
**RPK NEXUS** es el ecosistema inteligente diseñado para centralizar, unificar y analizar la producción industrial de RPK. Su misión principal es eliminar la dispersión de datos entre múltiples dashboards y servidores, proporcionando una **Verdad Única** mediante una base de datos local unificada y una interfaz de control "Premium".

---

## 🏗️ Arquitectura del Sistema
El proyecto se basa en una arquitectura de tres capas diseñada para la eficiencia y la persistencia:

### 1. Capa de Datos (Local Nexus DB)
- **Motor**: SQLite (Local exclusivamente).
- **Origen de datos**: Sincronización automática de archivos Excel desde la unidad de red `Y:`.
- **Tablas Clave**:
  - `stock_snapshot`: Registro diario de existencias por artículo, cliente y valor.
  - `tiempos_carga`: Estado de carga y saturación de los centros de trabajo.

### 2. Capa de Inteligencia (Backend)
- **Servidor**: FastAPI (Python 3.12 Portable).
- **Módulos**:
  - `sync_nexus.py`: Motor de ETL que unifica datos de Stock y Tiempos.
  - `analytics_core.py`: Cálculo de KPIs cruzados (Días de Cobertura, Cuellos de Botella).
  - `consultor.py`: Motor de traducción de lenguaje natural a SQL (Futuro Gemini Core).

### 3. Capa de Usuario (Frontend)
- **Nexus Hub**: Interfaz web premium diseñada bajo los estándares RPK Red.
- **Micro-Frontend**: Popup dinámico de asistencia con IA integrado en la web.
- **Acceso Directo**: Lanzador `INICIAR_NEXUS.bat` que automatiza la sincronización y subida del servidor.

---

## 📂 Estructura del Proyecto
```text
RPK-NEXUS-Plan-Maestro/
├── _SISTEMA/               # Entorno Python portable y librerías
├── backend/                # Lógica de servidor y consulta
│   ├── db/                 # Base de datos y scripts de migración
│   └── server_nexus.py     # Servidor central FastAPI
├── frontend/               # Interfaz de usuario
│   ├── assets/             # Estilos CSS (RPK System Design)
│   └── ui/                 # Plantillas HTML5
├── scripts/                # Utilidades de sistema y sincronización
├── docs/                   # Documentación detallada
│   ├── logs/               # Historial de actualizaciones (Fecha/Cambio)
│   └── debug/              # Registro de errores y soluciones
├── INICIAR_NEXUS.bat       # Lanzador Único del Sistema
└── README.md               # Este documento maestro
```

---

## 🚀 Guía de Inicio Rápido
1.  **Asegurar Conexión**: Verifique que la unidad de red `Y:` está mapeada.
2.  **Lanzar NEXUS**: Haga doble clic en `INICIAR_NEXUS.bat`.
3.  **Acceder**: El sistema abrirá automáticamente `http://localhost:8000` en su navegador.
4.  **Consultar**: Utilice el asistente (icono 🤖) para preguntar sobre el stock o la carga.

---

## 🛡️ Estándares RPK y Seguridad
- **Color Corporativo**: `#E30613` (RPK Red).
- **Modo**: Dark Mode nativo.
- **Seguridad**: Zero-Trust (Validación mediante `qa_scanner.py` antes de cualquier commit).
- **Persistencia**: Registro obligatorio de actualizaciones en `docs/logs/actualizaciones.md`.

---

## 📅 Hoja de Ruta (Roadmap)
- [x] Fase 1: Unificación de BD local.
- [x] Fase 2: Implementación de Consultor Inteligente.
- [x] Fase 3: Portal Web Nexus Hub e Integración Popup.
- [ ] Fase 4: Integración real con Google Gemini API (IA Generativa Avanzada).
- [ ] Fase 5: Alertas automáticas de rotura de stock vía Email/Teams.

---
*Última actualización: 2026-02-18 | Auditoría: Antigravity APS*