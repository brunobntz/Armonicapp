"""
canciones_ajustes.py — Lo que la app sabe de cada canción y el archivo no dice.

La carpeta de una canción es del usuario y solo se lee (ver canciones.py).
Pero hay dos cosas que la app necesita recordar por canción y que no están
en ningún archivo del profe:

- QUE AUDIO ES LA BASE, cuando hay varios en la carpeta (la base sola, la
  base con el profe tocando encima, un audio de clase);
- EN QUE SEGUNDO DE ESE AUDIO CAE EL COMPAS 1. Band-in-a-Box exporta con
  compases de conteo adelante —dos, medido sobre una exportación real: el
  compás 1 cayó en 7,38 s a 65 BPM— y sin ese dato el cifrado no se puede
  iluminar siguiendo el audio.

Las dos van a material/_canciones.json, que es de la app, como _plan.json.
El nombre de la canción es la clave.
"""

import json
import os

CARPETA_POR_DEFECTO = "material"
ARCHIVO = "_canciones.json"

# Band-in-a-Box exporta, por defecto, dos compases de conteo antes del 1.
COMPASES_DE_CONTEO_POR_DEFECTO = 2


def ruta_del_archivo(carpeta=None):
    return os.path.join(carpeta or CARPETA_POR_DEFECTO, ARCHIVO)


def cargar(carpeta=None):
    """Los ajustes de todas las canciones, por nombre. {} si no hay archivo."""
    ruta = ruta_del_archivo(carpeta)
    if not os.path.isfile(ruta):
        return {}
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def guardar(nombre, ajustes, carpeta=None):
    """
    Guarda los ajustes de una canción, pisando solo los campos que vienen.
    Devuelve los ajustes que quedaron para esa canción.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("Falta el nombre de la canción.")
    limpios = {}
    if "audio" in ajustes:
        limpios["audio"] = str(ajustes["audio"] or "")
    if "explicacion" in ajustes:
        # Lo que el coach dijo de la base, con fecha y proveedor; None la borra.
        valor = ajustes["explicacion"]
        limpios["explicacion"] = dict(valor) if isinstance(valor, dict) else None
    if "compas1_origen" in ajustes:
        # De dónde salió el compás 1: "audio" (lo midió la app escuchando
        # dónde entra el bajo) o "marcado" (lo marcó el usuario).
        limpios["compas1_origen"] = str(ajustes["compas1_origen"] or "")
    if "compas1_seg" in ajustes:
        valor = ajustes["compas1_seg"]
        if valor is None or valor == "":
            limpios["compas1_seg"] = None
            limpios["compas1_origen"] = ""
        else:
            try:
                limpios["compas1_seg"] = round(float(valor), 3)
            except (TypeError, ValueError):
                raise ValueError("El instante del compás 1 tiene que ser un número de segundos.")
            if limpios["compas1_seg"] < 0:
                raise ValueError("El instante del compás 1 no puede ser negativo.")

    todos = cargar(carpeta)
    actual = dict(todos.get(nombre, {}))
    actual.update(limpios)
    todos[nombre] = actual

    carpeta = carpeta or CARPETA_POR_DEFECTO
    os.makedirs(carpeta, exist_ok=True)
    with open(ruta_del_archivo(carpeta), "w", encoding="utf-8") as archivo:
        json.dump(todos, archivo, indent=2, ensure_ascii=False)
    return actual


def compas1_por_defecto(base):
    """
    Dónde cae el compás 1 si nadie lo midió: dos compases de conteo al tempo
    del archivo. Es lo que Band-in-a-Box exporta por defecto.
    """
    if base is None or not base.bpm:
        return None
    return round(60.0 / base.bpm * base.pulsos_por_compas * COMPASES_DE_CONTEO_POR_DEFECTO, 3)


def de_la_cancion(cancion, todos=None):
    """
    Los ajustes de una canción con los valores por defecto ya puestos: el
    primer audio de la carpeta si no se eligió otro (o ninguno), y el
    compás 1 a dos compases de conteo si no se midió. `compas1_origen` dice
    de dónde salió: "audio", "marcado" o "supuesto".
    """
    todos = cargar() if todos is None else todos
    guardados = todos.get(cancion.nombre, {})
    audio = guardados.get("audio", cancion.audios[0] if cancion.audios else "")
    if audio and audio not in cancion.audios:
        audio = cancion.audios[0] if cancion.audios else ""
    compas1 = guardados.get("compas1_seg")
    medido = compas1 is not None
    origen = guardados.get("compas1_origen") or ("marcado" if medido else "supuesto")
    if not medido:
        compas1 = compas1_por_defecto(cancion.base)
    return {"audio": audio, "compas1_seg": compas1, "compas1_medido": medido,
            "compas1_origen": origen if medido else "supuesto",
            "explicacion": guardados.get("explicacion") or None}
