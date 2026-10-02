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
    set ARMONICA_SIN_NAVEGADOR=1     (opcional: no abre el navegador)
"""

import ctypes
import http.client
import json
import os
import sys
import time
import traceback
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

PUERTOS = range(8000, 8011)
SUBCARPETAS = ("frases", "sesiones", "canciones", "apuntes", "material")
MAXIMO_REGISTRO = 1_000_000
CONSERVAR_REGISTRO = 200_000

# app\armonica\lanzador.py -> app -> la carpeta del programa, donde está ffmpeg\.
CARPETA_PROGRAMA = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# El turno: un mutex de Windows con nombre. Lo toma el primer lanzador y lo
# tiene mientras vive su app; un segundo lanzador lo encuentra tomado.
NOMBRE_DEL_TURNO = "Local\\Armonica-lanzador"
ERROR_ALREADY_EXISTS = 183

# Cuánto espera un segundo lanzador a que la app del primero conteste.
ESPERA_A_LA_OTRA = 20.0

# La manija del turno: tiene que vivir lo que vive el proceso. Si se
# cerrara, el próximo lanzador creería que es el primero.
_turno = None


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
    """
    Documentos\\Armonica, o ARMONICA_DATOS si está (pruebas). Siempre absoluta:
    la app hace os.chdir a esta carpeta, y una ruta relativa dejaría de
    apuntar a ella.
    """
    entorno = os.environ if entorno is None else entorno
    return os.path.abspath(entorno.get("ARMONICA_DATOS")
                           or os.path.join(carpeta_de_documentos(), "Armonica"))


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


def _contesta_la_app(puerto, espera):
    """Si en ese puerto contesta la app: /api/hola con {"app": "armonica"}."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/hola",
                                    timeout=espera) as respuesta:
            datos = json.loads(respuesta.read())
    except (OSError, ValueError, http.client.HTTPException):
        return False
    return isinstance(datos, dict) and datos.get("app") == "armonica"


def buscar_instancia(puertos=PUERTOS, espera=0.5):
    """
    El puerto de una app ya abierta, o None. Pregunta /api/hola. Si contestan
    varias, el más bajo: es el primero que prueba arrancar().

    Los puertos se prueban a la vez. En Windows cada puerto cerrado de
    localhost gasta el tiempo de espera entero, y probados de a uno los 11
    harían esperar ~5,5 s en cada arranque en frío; a la vez, lo que tarda uno.

    En esos puertos puede haber cualquier otro programa: uno que no hable
    HTTP, o que conteste algo que no es un objeto JSON. Ninguno es la app, y
    ninguno puede impedir que se siga con el puerto que sigue.
    """
    puertos = list(puertos)
    if not puertos:
        return None
    with ThreadPoolExecutor(max_workers=len(puertos)) as hilos:
        contestaron = list(hilos.map(lambda puerto: _contesta_la_app(puerto, espera), puertos))
    de_la_app = [puerto for puerto, es_la_app in zip(puertos, contestaron) if es_la_app]
    return min(de_la_app) if de_la_app else None


def tomar_el_turno(nombre=NOMBRE_DEL_TURNO):
    """
    (es_el_primero, manija). Dos clics rápidos en el ícono abren dos
    lanzadores casi juntos: el segundo no llega a ver la app del primero,
    que todavía está arrancando, y levantaría otra con otro micrófono
    abierto. El que crea el mutex es el primero; el otro espera a que la
    app conteste y solo abre el navegador. Fuera de Windows no hay turno.
    """
    if sys.platform != "win32":
        return True, None
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    manija = kernel32.CreateMutexW(None, False, nombre)
    if not manija:
        raise OSError(f"CreateMutexW falló: {ctypes.get_last_error()}")
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS, manija


def esperar_instancia(espera=ESPERA_A_LA_OTRA, cada=0.5, buscar=None):
    """El puerto de la app cuando conteste, o None si no contesta a tiempo."""
    buscar = buscar or buscar_instancia
    limite = time.monotonic() + espera
    while True:
        puerto = buscar()
        if puerto is not None or time.monotonic() >= limite:
            return puerto
        time.sleep(cada)


def abrir_el_navegador(puerto, entorno=None):
    """
    Abre la página de la app. Con ARMONICA_SIN_NAVEGADOR no abre nada: la
    prueba de humo del armado abre y cierra la app sin tocar el navegador
    de quien la corre.
    """
    entorno = os.environ if entorno is None else entorno
    if entorno.get("ARMONICA_SIN_NAVEGADOR"):
        return False
    webbrowser.open(f"http://127.0.0.1:{puerto}")
    return True


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

        global _turno
        es_el_primero, _turno = tomar_el_turno()
        if not es_el_primero:
            puerto = esperar_instancia()
            if puerto is None:
                avisar("Armónica ya se está abriendo pero todavía no contesta. "
                       "Esperá un momento y volvé a probar.")
                return 1
            print(f"Otro lanzador la está abriendo en el {puerto}: solo abro el navegador.")
            abrir_el_navegador(puerto)
            return 0

        # Una app de una versión anterior, sin turno, también cuenta.
        puerto = buscar_instancia()
        if puerto is not None:
            print(f"Ya estaba abierta en el {puerto}: solo abro el navegador.")
            abrir_el_navegador(puerto)
            return 0

        # Recién ahora: con la carpeta y el entorno listos.
        from armonica import servidor
        try:
            return servidor.arrancar(puertos=PUERTOS, empaquetada=True,
                                     abrir_navegador=not os.environ.get("ARMONICA_SIN_NAVEGADOR"))
        except servidor.PuertoOcupado as error:
            avisar(f"{error} Cerrá otros programas y probá de nuevo.")
            return 1
    except Exception:      # noqa: BLE001
        traceback.print_exc()
        avisar("La app no pudo arrancar. El detalle quedó en "
               + os.path.join(raiz, "registro.txt"))
        return 1
