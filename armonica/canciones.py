"""
canciones.py — Las carpetas de canciones: una base, sus audios y la tab en foto.

Lo que manda el profe para una canción viene junto: la base de Band-in-a-Box
(.sgu o .mgu), un audio de la base sola, otro con él tocando encima, y la
tablatura en una foto. La app lo espera así, UNA CARPETA POR CANCIÓN:

    material/canciones/
        Georgia On My Mind/
            Georgia On My Mind.MGU
            base de guitarra en Sol.m4a
            guitarra + armonica.m4a
            tablatura.HEIC
        Aunque a nadie ya le importe/
            ...

La carpeta se crea a mano, con el nombre que uno quiera: ese nombre es el de
la canción. Se puede apuntar a otra carpeta con CARPETA_CANCIONES en el .env.

Igual que la carpeta de clases, ESTA CARPETA SOLO SE LEE. Este módulo no
abre nada para escribir y hay un test que lo garantiza. Lo único que la app
fabrica a partir de lo que hay acá —el JPG de una foto .HEIC, que el
navegador no sabe mostrar— va a una caché aparte (ver imagenes.py).
"""

import os
from dataclasses import dataclass, field

from armonica import bandinabox, mapeo, teoria
from armonica.coach import leer_env

CARPETA_POR_DEFECTO = os.path.join("material", "canciones")

# Lo que el navegador reproduce solo, sin pasar por ffmpeg. Un .opus suelto
# de WhatsApp no está: Chrome lo reproduce adentro de un .ogg, no pelado.
EXTENSIONES_AUDIO = (".m4a", ".mp3", ".mp4", ".ogg", ".wav", ".webm", ".flac")
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif")
EXTENSIONES_TEXTO = (".md", ".txt", ".pdf", ".docx")


@dataclass
class Cancion:
    nombre: str
    ruta: str
    archivo_base: str = ""      # el .sgu/.mgu, por nombre, o "" si no hay
    base: object = None         # bandinabox.Base, o None
    error_base: str = ""        # por qué no se pudo leer, si pasó
    audios: list = field(default_factory=list)
    imagenes: list = field(default_factory=list)
    documentos: list = field(default_factory=list)

    def como_diccionario(self, tonalidad_armonica=None):
        """Lo que va a la pantalla. La ruta de la carpeta no viaja: solo nombres."""
        return {
            "nombre": self.nombre,
            "archivo_base": self.archivo_base,
            "error_base": self.error_base,
            "ficha": ficha(self.base, tonalidad_armonica) if self.base else None,
            "audios": list(self.audios),
            "imagenes": list(self.imagenes),
            "documentos": list(self.documentos),
        }


def carpeta_de_canciones(ruta_env=None):
    """La carpeta configurada en el .env, o material/canciones."""
    valor = (leer_env(ruta_env).get("CARPETA_CANCIONES")
             or os.environ.get("CARPETA_CANCIONES") or "").strip()
    return valor or CARPETA_POR_DEFECTO


def listar(carpeta=None):
    """
    Una Cancion por subcarpeta, en orden alfabético. Los archivos sueltos en
    la carpeta de canciones no son de ninguna y se ignoran; las subcarpetas
    que empiezan con punto o guion bajo, también.
    """
    carpeta = carpeta or carpeta_de_canciones()
    if not os.path.isdir(carpeta):
        return []
    canciones = []
    for nombre in sorted(os.listdir(carpeta), key=str.lower):
        ruta = os.path.join(carpeta, nombre)
        if not os.path.isdir(ruta) or nombre.startswith((".", "_")):
            continue
        canciones.append(leer_carpeta(ruta))
    return canciones


def leer_carpeta(ruta):
    """Una Cancion a partir de lo que hay en su carpeta."""
    cancion = Cancion(nombre=os.path.basename(os.path.normpath(ruta)), ruta=ruta)
    bases = []
    for archivo in sorted(os.listdir(ruta), key=str.lower):
        if archivo.startswith(".") or not os.path.isfile(os.path.join(ruta, archivo)):
            continue
        extension = os.path.splitext(archivo)[1].lower()
        if extension in bandinabox.EXTENSIONES:
            bases.append(archivo)
        elif extension in EXTENSIONES_AUDIO:
            cancion.audios.append(archivo)
        elif extension in EXTENSIONES_IMAGEN:
            cancion.imagenes.append(archivo)
        elif extension in EXTENSIONES_TEXTO:
            cancion.documentos.append(archivo)

    if bases:
        # Si hay más de una base se usa la primera y se avisa: mejor que
        # elegir en silencio.
        cancion.archivo_base = bases[0]
        try:
            cancion.base = bandinabox.leer(os.path.join(ruta, bases[0]))
        except (ValueError, OSError) as error:
            cancion.error_base = str(error)
        if len(bases) > 1 and cancion.base is not None:
            cancion.base.avisos.append(
                f"Hay {len(bases)} bases en la carpeta; se usa {bases[0]}.")
    return cancion


def ruta_de_archivo(cancion, nombre, carpeta=None):
    """
    La ruta de un archivo de una canción, o None si el pedido no es sano.

    Los dos nombres vienen del navegador. Se aceptan solo nombres planos, sin
    carpetas, y se verifica que la ruta resultante siga adentro de la carpeta
    de canciones: nada de lo que se pida puede salir de ahí.
    """
    carpeta = os.path.abspath(carpeta or carpeta_de_canciones())
    for parte in (cancion, nombre):
        if not parte or parte != os.path.basename(parte) or parte.startswith("."):
            return None
    ruta = os.path.abspath(os.path.join(carpeta, cancion, nombre))
    if os.path.dirname(os.path.dirname(ruta)) != carpeta or not os.path.isfile(ruta):
        return None
    return ruta


def ficha(base, tonalidad_armonica=None):
    """
    Lo que la pantalla muestra de una base: tono, tempo, compás, el cifrado
    compás por compás y, si hay melodía y se sabe la armónica, la melodía en
    tablatura de esa armónica. Todo ya calculado: el navegador solo dibuja.
    """
    compases = []
    for numero in range(1, base.compases + 1):
        acordes = [a for a in base.acordes if a.compas == numero]
        compases.append({
            "compas": numero,
            "acordes": [_acorde_para_la_pantalla(a, tonalidad_armonica) for a in acordes],
        })

    melodia = None
    if base.melodia and tonalidad_armonica:
        melodia = melodia_en_tablatura(base, tonalidad_armonica)

    # La melodía cruda, en segundos y MIDI, para que el reproductor la toque.
    melodia_midi = [[round(n.inicio_seg, 3), round(n.duracion_seg, 3), n.midi]
                    for n in base.melodia]

    return {
        "titulo": base.titulo,
        "tonalidad": base.tonalidad,
        "modo": base.modo,
        "bpm": base.bpm,
        "pulsos_por_compas": base.pulsos_por_compas,
        "con_swing": base.con_swing,
        "subdivision": base.subdivision,
        "estilo": base.estilo,
        "compases": base.compases,
        "coro_desde": base.coro_desde,
        "coro_hasta": base.coro_hasta,
        "vueltas": base.vueltas,
        "compases_de_cambio": base.compases_de_cambio(),
        "cifrado": compases,
        "tiene_melodia": bool(base.melodia),
        "melodia": melodia,
        "melodia_midi": melodia_midi,
        "avisos": list(base.avisos),
    }


def _acorde_para_la_pantalla(acorde, tonalidad_armonica):
    """
    Un acorde con lo que el navegador necesita: el nombre para escribirlo,
    las clases de nota para que el reproductor lo toque, y —si la app sabe
    calcular ese tipo de acorde y se sabe la armónica— las notas guía (la 3a
    y la 7a) con los agujeros donde se agarran, para iluminarlas en el
    diagrama mientras suena.
    """
    datos = {
        "tiempo": acorde.tiempo,
        "nombre": acorde.nombre(),
        "familia": acorde.familia(),
        "raiz": acorde.clase_raiz(),
        "bajo": acorde.clase_bajo(),
        "clases": acorde.clases(),
        "guias": [],
    }
    if acorde.familia() and tonalidad_armonica:
        arpegio = teoria.arpegio(tonalidad_armonica, acorde.raiz, acorde.familia())
        for grado in arpegio.grados:
            if not grado.es_guia:
                continue
            for nota in grado.agujeros:
                datos["guias"].append({
                    "agujero": nota.agujero, "direccion": nota.direccion,
                    "bend": nota.bend, "tab": nota.como_tab(),
                    "grado": grado.nombre_grado, "nota": grado.nombre_nota,
                })
    return datos


def melodia_en_tablatura(base, tonalidad_armonica):
    """
    La melodía de la base pasada a la armónica, compás por compás. Las notas
    que esa armónica no tiene quedan como "·": se ven, y se cuentan.
    """
    tabla = mapeo.construir_tabla_inversa(tonalidad_armonica)
    duracion_compas = 60.0 / base.bpm * base.pulsos_por_compas
    por_compas = {}
    fuera = 0
    for nota in base.melodia:
        compas = int(nota.inicio_seg // duracion_compas) + 1
        forma = tabla.get(nota.midi)
        if forma is None:
            fuera += 1
        por_compas.setdefault(compas, []).append(forma.como_tab() if forma else "·")
    return {
        "tonalidad_armonica": tonalidad_armonica,
        "notas": len(base.melodia),
        "fuera": fuera,
        "compases": [{"compas": c, "tabs": por_compas[c]} for c in sorted(por_compas)],
    }
