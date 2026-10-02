"""
ajustes.py — Lo que se elige en Ajustes, guardado para la próxima vez.

Hasta ahora lo que se cambiaba en la solapa Ajustes vivía en memoria: al
cerrar la app volvía todo a config.py y a lo que dijera Armonica.bat. Para
Bruno era una molestia; para el profe, que abre la app desde un ícono, sería
elegir el micrófono cada vez.

Se guarda en ajustes.json, en la carpeta desde donde arranca la app (en la
versión instalada, Documentos\\Armonica). Manda, de más a menos:

    lo escrito en la línea de comandos   (Armonica.bat)
    ajustes.json                          (lo que se eligió en pantalla)
    config.py                             (la fábrica)

EL MICRÓFONO SE GUARDA POR NOMBRE. Windows numera las entradas en el orden
en que las encuentra, y enchufar unos auriculares corre los números: el
número de ayer hoy puede ser la cámara.
"""

import json
import os

import config
from armonica import tablas

ARCHIVO = "ajustes.json"

# Con qué armónica arranca la app si nadie eligió nada.
FABRICA = {"tonalidad": "C", "posicion": None, "escala": None}


def _es_entero(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


def _valido(clave, valor):
    """Si `valor` sirve para `clave`. Lo que no se conoce, no sirve."""
    if clave == "microfono":
        return isinstance(valor, str)
    if clave == "umbral":
        return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
                and 0 < valor < 1)
    if clave == "tonalidad":
        return valor in tablas.TONALIDADES
    if clave == "posicion":
        return valor is None or (_es_entero(valor) and valor in tablas.POSICIONES_CON_TABLA)
    if clave == "escala":
        return valor is None or valor in tablas.ESCALAS_INTERVALOS
    if clave == "primeros_pasos":
        return isinstance(valor, bool)
    return False


def cargar(ruta=None):
    """
    Lo guardado, solo lo que sigue siendo válido. Un archivo que falta o que
    está roto da {}: la app arranca igual, con la fábrica.
    """
    ruta = ruta or ARCHIVO
    if not os.path.isfile(ruta):
        return {}
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError):
        return {}
    if not isinstance(datos, dict):
        return {}
    return {clave: valor for clave, valor in datos.items() if _valido(clave, valor)}


def guardar(cambios, ruta=None):
    """
    Guarda lo que viene, pisando solo eso. Algo inválido es un error y no se
    guarda nada: mejor ruidoso que un ajuste a medias.
    """
    for clave, valor in cambios.items():
        if not _valido(clave, valor):
            raise ValueError(f"Ajuste inválido: {clave} = {valor!r}")
    ruta = ruta or ARCHIVO
    actuales = cargar(ruta)
    actuales.update(cambios)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(actuales, archivo, indent=2, ensure_ascii=False)
    return actuales


def valores_de_arranque(guardados, tonalidad=None, posicion=None, escala=None):
    """
    Con qué armónica, posición y escala arrancar. Lo que viene en los
    argumentos es lo escrito en la línea de comandos (None = no se escribió);
    si no, lo guardado; si no, la fábrica.
    """
    escritos = {"tonalidad": tonalidad, "posicion": posicion, "escala": escala}
    return {clave: (escritos[clave] if escritos[clave] is not None
                    else guardados.get(clave, FABRICA[clave]))
            for clave in FABRICA}


def aplicar_a_config(guardados, modulo=None):
    """
    El umbral guardado pisa el de config.py. Se escribe sobre el módulo, así
    todo lo que lee config.UMBRAL_VOLUMEN_RMS (el hilo de audio, la barra de
    nivel, el análisis de archivos) usa el medido sin enterarse.
    """
    modulo = modulo or config
    if "umbral" in guardados:
        modulo.UMBRAL_VOLUMEN_RMS = guardados["umbral"]


def resolver_microfono(nombre, entradas):
    """
    El número del micrófono que se llama `nombre`, o None si no está
    conectado. Misma regla que la lista de Ajustes: Windows repite cada
    micrófono una vez por API de audio, y vale el primero.
    """
    buscado = (nombre or "").strip().lower()
    if not buscado:
        return None
    for numero, nombre_de_la_entrada, _canales in entradas:
        if nombre_de_la_entrada.strip().lower() == buscado:
            return numero
    return None
