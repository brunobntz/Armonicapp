# acceso_directo.ps1 - Deja un acceso directo a la app en el escritorio.
#
#     powershell -ExecutionPolicy Bypass -File herramientas\acceso_directo.ps1
#
# Apunta a Armonica.bat con el icono Armonica.ico, los dos en la raiz del
# proyecto. Si ya habia un acceso directo con ese nombre, lo reemplaza.
# El escritorio se pregunta a Windows, asi funciona igual si esta en
# una carpeta sincronizada en la nube (que es lo comun en una maquina nueva).

$proyecto = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$bat = Join-Path $proyecto "Armonica.bat"
$icono = Join-Path $proyecto "Armonica.ico"

if (-not (Test-Path $bat)) {
    Write-Host "No encuentro $bat. Corre esto desde la carpeta del proyecto."
    exit 1
}
if (-not (Test-Path $icono)) {
    Write-Host "No esta el icono. Lo genero:"
    & (Join-Path $proyecto ".venv\Scripts\python.exe") -m herramientas.icono
}

$escritorio = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell

# Si ya hay un acceso directo que apunta a la app, con el nombre que sea
# (uno renombrado a mano, por ejemplo), se actualiza ese. Sin esto quedaban
# dos en el escritorio.
$destino = Join-Path $escritorio "Armonica.lnk"
foreach ($existente in Get-ChildItem $escritorio -Filter "*.lnk" -ErrorAction SilentlyContinue) {
    if ($shell.CreateShortcut($existente.FullName).TargetPath -ieq $bat) {
        $destino = $existente.FullName
        break
    }
}
$acceso = $shell.CreateShortcut($destino)
$acceso.TargetPath = $bat
$acceso.WorkingDirectory = $proyecto
$acceso.IconLocation = "$icono,0"
$acceso.Description = "Armonica: escucha tu armonica y la transcribe"
$acceso.Save()

Write-Host "Listo: $destino"
Write-Host "Doble clic ahi abre la app. La ventana negra que queda es el servidor."
