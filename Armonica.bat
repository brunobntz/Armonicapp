@echo off
REM ============================================================================
REM  Armonica.bat - Abre la app de un doble clic.
REM
REM  Hace las tres cosas que si no tenes que escribir a mano cada vez:
REM  pararse en la carpeta del proyecto, usar el Python del entorno virtual
REM  (y no el del sistema, que no tiene numpy), y levantar la interfaz web con
REM  tu configuracion de siempre.
REM
REM  Para cambiar la armonica, la posicion o la escala, editá la linea de
REM  OPCIONES de mas abajo. Son los mismos nombres que en la terminal.
REM
REM  La ventana negra que queda abierta ES el servidor: si la cerras, se apaga
REM  la app. Minimizala y listo.
REM ============================================================================

REM --- Tu configuracion. Cambiala aca. ---
set OPCIONES=--tonalidad C --posicion 12 --escala blues_mayor

REM --- De aca para abajo no hace falta tocar nada ---

REM %~dp0 es la carpeta donde esta este archivo. Asi el .bat funciona aunque lo
REM llames desde un acceso directo en el escritorio, que arranca en otro lado.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   No encuentro el entorno virtual en .venv
    echo.
    echo   Crealo una sola vez con:
    echo       python -m venv .venv
    echo       .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo.
echo   Abriendo la armonica...  (esta ventana es el servidor: no la cierres)
echo.

.venv\Scripts\python.exe main.py --web %OPCIONES%

REM Si algo salio mal, la ventana se cerraria de golpe y no llegarias a leer
REM el error. Esto la deja abierta hasta que aprietes una tecla.
if errorlevel 1 (
    echo.
    echo   La app termino con un error. El detalle esta arriba.
    echo.
    pause
)
