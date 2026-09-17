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

from armonica import bandinabox, mapeo, notas, tablas, teoria
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
    compás por compás con las notas de cada acorde, y la melodía cruda para
    el reproductor. Todo ya calculado: el navegador solo dibuja.
    """
    compases = []
    for numero in range(1, base.compases + 1):
        acordes = [a for a in base.acordes if a.compas == numero]
        compases.append({
            "compas": numero,
            "acordes": [_acorde_para_la_pantalla(a, tonalidad_armonica) for a in acordes],
        })

    # La melodía cruda, en segundos y MIDI, para que el reproductor la toque.
    # En tablatura no va: la tablatura de una canción es la foto del profe,
    # y la melodía de la base pasada a agujeros la muestra `--base` en la
    # terminal, para quien la quiera.
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
        "hechos": hechos_de_la_base(base),
        "tiene_melodia": bool(base.melodia),
        "melodia_midi": melodia_midi,
        "avisos": list(base.avisos),
    }


def _acorde_para_la_pantalla(acorde, tonalidad_armonica):
    """
    Un acorde con lo que el navegador necesita: el nombre para escribirlo,
    las clases de nota para que el reproductor lo toque y, si se sabe la
    armónica, cada nota del acorde con el agujero donde se agarra (`notas`),
    las notas guía con todas sus formas para iluminarlas en el diagrama
    (`guias`), y las notas naturales de la armónica que chocan con el
    acorde (`a_evitar`).
    """
    datos = {
        "tiempo": acorde.tiempo,
        "nombre": acorde.nombre(),
        "familia": acorde.familia(),
        "raiz": acorde.clase_raiz(),
        "bajo": acorde.clase_bajo(),
        "clases": acorde.clases(),
        "notas": [],
        "guias": [],
        "a_evitar": [],
    }
    if not tonalidad_armonica:
        return datos
    for grado in notas_del_acorde(acorde, tonalidad_armonica):
        facil = grado.el_mas_facil()
        datos["notas"].append({
            "intervalo": grado.intervalo,
            "grado": grado.nombre_grado,
            "nota": grado.nombre_nota,
            "es_guia": grado.es_guia,
            "facil": facil.como_tab() if facil else None,
            "formas": [nota.como_tab() for nota in grado.agujeros],
        })
        if grado.es_guia:
            for nota in grado.agujeros:
                datos["guias"].append({
                    "agujero": nota.agujero, "direccion": nota.direccion,
                    "bend": nota.bend, "tab": nota.como_tab(),
                    "grado": grado.nombre_grado, "nota": grado.nombre_nota,
                })
    datos["a_evitar"] = notas_a_evitar(acorde, tonalidad_armonica)
    return datos


def notas_del_acorde(acorde, tonalidad_armonica):
    """
    Las notas del acorde (las de su cifrado: tríada y séptima o sexta),
    cada una con todas las formas de tocarla en esa armónica, como
    GradoDelAcorde. Es el mismo cálculo que teoria.arpegio, pero sobre los
    intervalos que deduce bandinabox del cifrado, así cubre también los
    acordes que las tablas de la app no tienen (un Em7b5, un C7#5).
    """
    formas = mapeo.todas_las_formas(tonalidad_armonica)
    raiz = acorde.clase_raiz()
    grados = []
    for intervalo in acorde.intervalos():
        clase = (raiz + intervalo) % 12
        agujeros = [nota for midi in sorted(formas) if midi % 12 == clase
                    for nota in formas[midi]]
        grados.append(teoria.GradoDelAcorde(
            intervalo=intervalo,
            nombre_grado=tablas.NOMBRES_GRADOS.get(intervalo, f"{intervalo} semitonos"),
            nombre_nota=notas.nombre_de_clase(clase),
            agujeros=agujeros,
            es_guia=intervalo in tablas.GRADOS_GUIA,
        ))
    return grados


def notas_a_evitar(acorde, tonalidad_armonica):
    """
    Las notas NATURALES de la armónica (sin bend: las que salen solas) que
    están medio tono arriba de una nota del acorde y no son del acorde. Es
    la regla clásica de las notas a evitar: a medio tono por encima de una
    nota del acorde, chocan con ella. Sobre F7, el Mi (medio tono arriba
    de la 7a, Mib) y el Sib no: el Sib no es natural en una armónica en Do.
    La app dice la regla, no el gusto: una nota de paso puede ser esa.
    """
    raiz = acorde.clase_raiz()
    clases_del_acorde = set(acorde.clases())
    chocan = {}
    for intervalo in acorde.intervalos():
        clase = (raiz + intervalo) % 12
        arriba = (clase + 1) % 12
        if arriba not in clases_del_acorde:
            chocan[arriba] = tablas.NOMBRES_GRADOS.get(intervalo, f"{intervalo} semitonos"), \
                notas.nombre_de_clase(clase)
    resultado = []
    for midi, formas in sorted(mapeo.todas_las_formas(tonalidad_armonica).items()):
        clase = midi % 12
        if clase not in chocan:
            continue
        for nota in formas:
            if nota.bend == 0:
                grado, nombre = chocan[clase]
                resultado.append({
                    "nota": notas.nombre_de_clase(clase), "tab": nota.como_tab(),
                    "porque": f"medio tono arriba de la {grado} ({nombre})",
                })
    return resultado


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


# =============================================================================
# Los hechos de una base: lo que se puede contar del cifrado sin opinar
# =============================================================================

ESCALA_MAYOR = [0, 2, 4, 5, 7, 9, 11]
ESCALA_MENOR = [0, 2, 3, 5, 7, 8, 10]


def hechos_de_la_base(base):
    """
    Lo que se puede decir de una base mirando solo su cifrado: cuántos
    acordes distintos, cuántos compases con más de uno, dónde hay cadencias
    ii-V-I o V-I (un acorde dominante que resuelve una quinta abajo), y qué
    acordes tienen la raíz fuera de la tonalidad. Es la capa de hechos; la
    interpretación (la forma, cómo pensar cada acorde) es del coach.
    """
    acordes = list(base.acordes)
    nombres = [a.nombre() for a in acordes]
    distintos = []
    for nombre in nombres:
        if nombre not in distintos:
            distintos.append(nombre)
    por_compas = {}
    for a in acordes:
        por_compas[a.compas] = por_compas.get(a.compas, 0) + 1

    # La base da la vuelta: el ultimo acorde resuelve en el primero (el
    # turnaround del blues, C7 a F7), asi que se mira tambien ese par.
    cadencias = []
    cantidad = len(acordes)
    for indice in range(1, cantidad + (1 if cantidad > 1 else 0)):
        b, c = acordes[indice - 1], acordes[indice % cantidad]
        if not _es_dominante(b) or (b.clase_raiz() - c.clase_raiz()) % 12 != 7:
            continue
        a = acordes[indice - 2] if indice >= 2 else None
        if a is not None and _es_menor(a) and (a.clase_raiz() - c.clase_raiz()) % 12 == 2:
            cadencias.append({"tipo": "ii-V-I", "a": c.raiz, "compas": c.compas,
                              "acordes": f"{a.nombre()} {b.nombre()} {c.nombre()}"})
        else:
            cadencias.append({"tipo": "V-I", "a": c.raiz, "compas": c.compas,
                              "acordes": f"{b.nombre()} {c.nombre()}"})

    tonica = notas.nombre_a_midi(base.tonalidad + "4") % 12
    escala = ESCALA_MENOR if base.modo == "menor" else ESCALA_MAYOR
    diatonicas = {(tonica + grado) % 12 for grado in escala}
    fuera = []
    for a in acordes:
        if a.clase_raiz() not in diatonicas and a.nombre() not in fuera:
            fuera.append(a.nombre())

    return {
        "tonalidad": f"{base.tonalidad} {base.modo}",
        "compases": base.compases,
        "acordes_distintos": len(distintos),
        "lista_acordes": distintos,
        "compases_con_varios": sum(1 for cuantos in por_compas.values() if cuantos > 1),
        "cadencias": cadencias,
        "fuera_de_la_tonalidad": fuera,
    }


def _es_dominante(acorde):
    intervalos = acorde.intervalos()
    return 4 in intervalos and 10 in intervalos


def _es_menor(acorde):
    return 3 in acorde.intervalos()


def texto_de_los_hechos(hechos):
    """Una línea para la pantalla, con los hechos y nada más."""
    partes = [
        hechos["tonalidad"],
        f"{hechos['compases']} compases, {hechos['acordes_distintos']} acordes distintos"
        + (f", {hechos['compases_con_varios']} compases con más de un acorde"
           if hechos["compases_con_varios"] else ""),
    ]
    ii_v_i = [c for c in hechos["cadencias"] if c["tipo"] == "ii-V-I"]
    v_i = [c for c in hechos["cadencias"] if c["tipo"] == "V-I"]
    if ii_v_i:
        partes.append("ii-V-I " + ", ".join(
            f"a {c['a']} en el compás {c['compas']} ({c['acordes']})" for c in ii_v_i[:4])
            + (" y más" if len(ii_v_i) > 4 else ""))
    if v_i:
        partes.append("V-I " + ", ".join(
            f"a {c['a']} en el {c['compas']}" for c in v_i[:4]) + (" y más" if len(v_i) > 4 else ""))
    if hechos["fuera_de_la_tonalidad"]:
        partes.append("con la raíz fuera de la tonalidad: " + ", ".join(hechos["fuera_de_la_tonalidad"]))
    return " · ".join(partes)
