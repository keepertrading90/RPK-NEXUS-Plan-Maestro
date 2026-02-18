# Historial de Actualizaciones - RPK NEXUS

## [2026-02-18] Integración de Simulador v1 Classic
- **Restauración de Interfaz**: Se ha copiado la interfaz y funcionalidad exacta del "iniciar v1 local" en el módulo de simulador.
- **Backend Unificado**: Integración de `simulation_core` y esquemas de base de datos SQLAlchemy dentro del servidor Nexus central.
- **Persistencia Local**: El simulador ahora utiliza la base de datos central `rpk_industrial.db` para escenarios e histórico, manteniendo independencia de red.
- **Optimización de Carga**: Implementación de caché binaria (.pkl) para el Maestro Fleje, reduciendo el tiempo de arranque de la simulación.

## [2026-02-18] Lanzamiento RPK NEXUS v3.2: Unificación de Módulos
- **Unificación Total**: Integración de los dashboards de Stock, Tiempos y Simulador de Producción en un solo portal centralizado.
- **Arquitectura de Parcheo**: Los frontends originales se sirven ahora localmente desde `frontend/modules/` para permitir ajustes de ruta sin tocar los originales de la red.
- **Endpoints de Compatibilidad**: Implementación en `server_nexus.py` de las rutas de API esperadas por los módulos originales (`/api/summary`, `/api/fechas`, etc.).
- **Módulo de Simulaciones**: Integración completa del Simulador de Fleje v3 como nueva tarjeta interactiva.
- **Control de Rutas**: Configuración de montajes estáticos dinámicos para servir activos CSS/JS de múltiples módulos simultáneamente.

## [2026-02-18] Solución Crítica de Rutas (ModuleNotFoundError)
- **Corrección de Paquetes**: Se ha configurado la raíz del proyecto dinámicamente en el entorno de Python (`sys.path`) para que el comando `import backend` funcione correctamente.
- **Estandarización**: Creación de archivos `__init__.py` en todos los directorios del backend para cumplir con los estándares de empaquetado de Python.
- **Migración a Rutas UNC**: Se han sustituido todas las dependencias de la unidad `Y:` por la ruta directa `\\RPK4TGN\ofimatica\Supply Chain\PLAN PRODUCCION\`. 
- **Documentación "Lujo de Detalle"**: Creación del `README.md` maestro que describe la arquitectura, estructura y uso del sistema NEXUS.
- **Unificación de Interfaz**: Se ha integrado el Consultor (Asistente de IA) directamente en el Popup de la aplicación web. Ya no se abre en una ventana secundaria.
- **Lanzador Optimizado**: Actualización de `INICIAR_NEXUS.bat`. Ahora sincroniza datos y levanta el servidor web en un solo paso, abriendo el navegador automáticamente.
- **Corrección de Rutas**: Se ha ajustado la lógica interna para que los módulos de analítica y base de datos sean accesibles desde el servidor FastAPI.

## [2026-02-17] Inicialización de Proyecto Nexus
- **Fase 1 & 2**: Sincronización de datos desde Y: (Stock y Tiempos) a la base de datos local Nexus.
- **Asistente CLI**: Creación de la primera versión del consultor.
- **GitHub**: Vinculación con repositorio remoto.
