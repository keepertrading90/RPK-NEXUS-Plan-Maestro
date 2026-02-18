# Historial de Actualizaciones - RPK NEXUS

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
