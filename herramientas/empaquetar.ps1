# empaquetar.ps1 - Arma el instalador de Armonica para el profe.
#
# Todo lo hace herramientas\empaquetar.py; esto solo lo llama con el Python
# del entorno virtual, desde la raiz del repo. Los pasos se pueden pedir de a
# uno:  .\herramientas\empaquetar.ps1 fijar | armar | humo | instalador
# Sin nada, arma, prueba y compila el instalador en dist\.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
& .\.venv\Scripts\python.exe -m herramientas.empaquetar @args
exit $LASTEXITCODE
