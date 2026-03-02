@echo off
title RPK NEXUS V6 - Frontend React
echo ==========================================
echo   RPK NEXUS V6 - Frontend React (Next.js)
echo ==========================================
echo.

REM Ruta portable al Node.js local
set NODE_PATH=%~dp0_SISTEMA\runtime_node
set PATH=%NODE_PATH%;%PATH%

echo [INFO] Usando Node.js portable: %NODE_PATH%\node.exe
echo.

REM Verificar que Node existe
if not exist "%NODE_PATH%\node.exe" (
    echo [ERROR] No se encontro Node.js en _SISTEMA\runtime_node\
    echo         Ejecuta primero la instalacion de Node.js portable.
    pause
    exit /b 1
)

echo [OK] Node.js version:
call "%NODE_PATH%\node.exe" -v
echo.

REM Navegar a la carpeta del frontend React
cd /d "%~dp0nexus-v6"

REM Verificar que existan las dependencias
if not exist "node_modules" (
    echo [INFO] Instalando dependencias por primera vez...
    call "%NODE_PATH%\npm.cmd" install
    echo.
)

echo [INFO] Arrancando servidor de desarrollo Next.js en http://localhost:3000
echo [INFO] Presiona Ctrl+C para detener.
echo.

call "%NODE_PATH%\npx.cmd" next dev

pause
