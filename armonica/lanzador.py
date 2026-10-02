"""
lanzador.py — Abrir la app desde un ícono, sin ventana negra.

Lo usa el acceso directo de la versión instalada (lanzador.pyw, con
pythonw.exe). Hace lo que Armonica.bat hace para Bruno, más lo que necesita
alguien sin terminal:

1. Los datos van a Documentos\\Armonica: frases, sesiones, canciones,
   apuntes. La app guarda todo relativo a la carpeta desde donde arranca,
   así que alcanza con pararse ahí. Las canciones y los apuntes se le dicen
   por las mismas variables que usa el .env de Bruno.
2. Sin consola, lo que la app imprime va a registro.txt: es lo que Bruno
   pide cuando algo no anda.
3. ffmpeg viaja con el programa, en la carpeta de al lado: va primero en el
   PATH.
4. Una sola app: si ya hay una abierta, solo se abre el navegador.

Para probarlo desde el repo, sin tocar Documentos:

    set ARMONICA_DATOS=C:\\ruta\\de\\prueba
    .venv\\Scripts\\pythonw.exe lanzador.pyw
"""

import ctypes
import json
import os
import sys
import traceback
import urllib.request
import webbrowser
from datetime import datetime

PUERTOS = range(8000, 8011)
SUBCARPETAS = ("frases", "sesiones", "canciones", "apuntes", "material")
MAXIMO_REGISTRO = 1_000_000
CONSERVAR_REGISTRO = 200_000

# app\armonica\lanzador.py -> app -> la carpeta del programa, donde está ffmpeg\.
CARPETA_PROGRAMA = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def carpeta_de_documentos():
    """
    La carpeta Documentos de verdad. Con OneDrive puede no ser
    %USERPROFILE%\\Documents, así que se le pregunta a Windows.
    """
    if sys.platform == "win32":
        try:
            return _documentos_segun_windows()
        except OSError:
            pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def _documentos_segun_windows():
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
    documentos = GUID(0xFDD39AD0, 0x238F, 0x46AF,
                      (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
    ruta = ctypes.c_wchar_p()
    resultado = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(documentos), 0, None, ctypes.byref(ruta))
    if resultado != 0:
        raise OSError(f"SHGetKnownFolderPath devolvió {resultado}")
    try:
        return ruta.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(ruta)


def carpeta_de_datos(entorno=None):
    """Documentos\\Armonica, o ARMONICA_DATOS si está (pruebas)."""
    entorno = os.environ if entorno is None else entorno
    return entorno.get("ARMONICA_DATOS") or os.path.join(carpeta_de_documentos(), "Armonica")


def preparar_carpeta(raiz):
    for nombre in SUBCARPETAS:
        os.makedirs(os.path.join(raiz, nombre), exist_ok=True)


def recortar_registro(ruta, maximo=MAXIMO_REGISTRO, conservar=CONSERVAR_REGISTRO):
    """Si el registro pasa de `maximo` bytes, se queda con los últimos `conservar`."""
    if not os.path.isfile(ruta) or os.path.getsize(ruta) <= maximo:
        return
    with open(ruta, "rb") as archivo:
        archivo.seek(-conservar, os.SEEK_END)
        cola = archivo.read()
    with open(ruta, "wb") as archivo:
        archivo.write(cola)


def abrir_registro(raiz):
    """Manda stdout y stderr a registro.txt: con pythonw no hay consola."""
    ruta = os.path.join(raiz, "registro.txt")
    recortar_registro(ruta)
    registro = open(ruta, "a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = sys.stderr = registro
    return registro


def preparar_entorno(raiz, carpeta_programa, entorno=None):
    """Se para en la carpeta de datos y le dice a la app dónde está cada cosa."""
    entorno = os.environ if entorno is None else entorno
    os.chdir(raiz)
    entorno["CARPETA_CANCIONES"] = os.path.join(raiz, "canciones")
    entorno["CARPETA_CLASES"] = os.path.join(raiz, "apuntes")
    ffmpeg = os.path.join(carpeta_programa, "ffmpeg")
    if os.path.isdir(ffmpeg):
        entorno["PATH"] = ffmpeg + os.pathsep + entorno.get("PATH", "")


def buscar_instancia(puertos=PUERTOS, espera=0.5):
    """El puerto de una app ya abierta, o None. Pregunta /api/hola."""
    for puerto in puertos:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/hola",
                                        timeout=espera) as respuesta:
                if json.loads(respuesta.read()).get("app") == "armonica":
                    return puerto
        except (OSError, ValueError):
            continue
    return None


def avisar(texto):
    """
    Un cartel de Windows. Sin consola y antes de que haya página, es la
    única forma de decir que algo salió mal.
    """
    print(texto)
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, texto, "Armónica", 0x10)


def main():
    raiz = carpeta_de_datos()
    try:
        preparar_carpeta(raiz)
        abrir_registro(raiz)
        print(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} ---")
        preparar_entorno(raiz, CARPETA_PROGRAMA)

        puerto = buscar_instancia()
        if puerto is not None:
            print(f"Ya estaba abierta en el {puerto}: solo abro el navegador.")
            webbrowser.open(f"http://127.0.0.1:{puerto}")
            return 0

        # Recién ahora: con la carpeta y el entorno listos.
        from armonica import servidor
        try:
            return servidor.arrancar(puertos=PUERTOS, empaquetada=True)
        except servidor.PuertoOcupado as error:
            avisar(f"{error} Cerrá otros programas y probá de nuevo.")
            return 1
    except Exception:      # noqa: BLE001
        traceback.print_exc()
        avisar("La app no pudo arrancar. El detalle quedó en "
               + os.path.join(raiz, "registro.txt"))
        return 1
