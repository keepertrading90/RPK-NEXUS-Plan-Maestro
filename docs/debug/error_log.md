# Registro de Errores y Debugging - RPK NEXUS

## [2026-02-18 09:52] ERR_CONNECTION_REFUSED
- **Síntoma**: Al iniciar la aplicación, el navegador mostraba "No se puede obtener acceso a esta página".
- **Causa**: El servidor FastAPI no había terminado de arrancar o el lanzador .bat estaba bloqueado por la ejecución del Consultor CLI antes de subir el server.
- **Solución**: Se ha reestructurado `INICIAR_NEXUS.bat` para que el servidor sea el proceso principal y el navegador se abra con un retardo controlado. Se ha eliminado el bloqueo del CLI secundario.

## [2026-02-17 15:03] ImportError: No module named 'tabulate'
- **Síntoma**: El consultor fallaba al intentar mostrar tablas.
- **Causa**: La librería `tabulate` no estaba instalada en el entorno portable `_SISTEMA`.
- **Solución**: Se implementó un "Fallback" en `consultor.py` que imprime los datos separados por barras (|) si la librería no está disponible.

## [2026-02-17 13:40] FileNotFoundError: rpk_industrial.db
- **Síntoma**: Los scripts de la red no encontraban la base de datos local de C:.
- **Causa**: Rutas relativas calculadas incorrectamente desde los subdirectorios.
- **Solución**: Uso de `Path(__file__).resolve().parent` para anclar las rutas a la ubicación absoluta del script.
