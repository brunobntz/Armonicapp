"""
clases.py — Leer los apuntes de las clases y entender qué hay que practicar.

QUÉ ES ESTO

Un profesor manda, después de cada clase, un resumen: qué se vio, qué salió
mal, qué practicar. Puede ser el recap automático de una reunión, un mail
escrito a mano, o los apuntes del propio alumno. Este módulo los lee de una
carpeta y saca de ahí lo que la solapa Aprendizaje muestra: qué estamos
viendo, qué tengo que practicar, y en qué parte de la app se trabaja cada
cosa.

DE DÓNDE LEE

De `material/` por defecto, que es la carpeta de cada usuario y no va al
repositorio. Se puede apuntar a otra con CARPETA_CLASES en el .env: por
ejemplo, a la carpeta donde un asistente personal ya deja los recaps
ordenados. Así no hay copias: la fuente de verdad es una sola.

ESTE MÓDULO SOLO LEE. Nunca escribe en esa carpeta, ni crea archivos, ni
toca nada. Hay un test que revisa este código fuente y falla si aparece una
apertura en modo escritura. Lo que la app genere va a otro lado.

QUÉ FORMATO ENTIENDE

Archivos .md y .txt, y también .docx (es un zip con XML adentro, se lee con
la biblioteca estándar). PDF solo si está instalado `pypdf`, que es opcional.

El nombre del archivo da la fecha si empieza con AAAA-MM-DD. Adentro, si
hay secciones en Markdown ("## Puntos clave", "## Próximos pasos"), se usan;
si no, el archivo es prosa y se muestra entero. Los recaps automáticos traen
justo esas secciones, y un apunte escrito a mano no necesita traerlas.
"""

import os
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field

from armonica.coach import ARCHIVO_ENV, leer_env

CARPETA_POR_DEFECTO = "material"

EXTENSIONES = (".md", ".txt", ".docx", ".pdf")

# Los nombres de sección que buscamos, en minúsculas y sin acentos. Cada
# entrada lista las variantes que se han visto.
SECCIONES = {
    "puntos_clave": ("puntos clave", "key points", "resumen", "puntos principales"),
    "proximos_pasos": ("proximos pasos", "next steps", "para practicar", "tareas", "action items"),
    "temas": ("temas", "topics"),
    "proposito": ("proposito de la reunion", "proposito", "purpose"),
}

# Archivos que no son clases aunque estén en la carpeta.
NO_SON_CLASES = ("leeme", "readme", "aprendizaje", "verificacion")

# La síntesis: la capa editable que alguien (el alumno, su asistente) escribe
# leyendo las clases juntas. Se muestra tal cual, nunca se reescribe.
ARCHIVO_DE_SINTESIS = "aprendizaje.md"


@dataclass
class Clase:
    """Un apunte de clase, ya leído y entendido."""

    archivo: str
    fecha: str = ""                     # "2026-09-08" o "" si el nombre no la trae
    titulo: str = ""
    texto: str = ""                     # el contenido entero, tal cual
    secciones: dict = field(default_factory=dict)
    puntos_clave: list = field(default_factory=list)
    proximos_pasos: list = field(default_factory=list)   # [{"para": "Bruno", "texto": "..."}]
    temas: list = field(default_factory=list)
    tema: str = ""                      # de qué fue la clase, en una línea
    con_recap: bool = True
    error: str = ""

    def como_diccionario(self, con_texto=False):
        datos = {
            "archivo": self.archivo,
            "fecha": self.fecha,
            "titulo": self.titulo,
            "tema": self.tema,
            "puntos_clave": self.puntos_clave,
            "proximos_pasos": self.proximos_pasos,
            "temas": self.temas,
            "con_recap": self.con_recap,
            "error": self.error,
        }
        if con_texto:
            datos["texto"] = self.texto
        return datos


# =============================================================================
# La carpeta
# =============================================================================

def carpeta_de_clases(ruta_env=None):
    """La carpeta configurada en el .env, o `material/` si no hay nada."""
    if ruta_env is None:
        ruta_env = ARCHIVO_ENV
    valor = (leer_env(ruta_env).get("CARPETA_CLASES")
             or os.environ.get("CARPETA_CLASES") or "").strip()
    return valor or CARPETA_POR_DEFECTO


def listar(carpeta=None):
    """
    Todas las clases de la carpeta, de la más vieja a la más nueva.

    Los archivos sin fecha en el nombre van al final, en orden alfabético.
    Una carpeta que no existe da una lista vacía, no un error: la solapa
    tiene que poder abrirse en una máquina donde todavía no hay nada.
    """
    if carpeta is None:
        carpeta = carpeta_de_clases()
    if not os.path.isdir(carpeta):
        return []

    clases = []
    for nombre in sorted(os.listdir(carpeta)):
        base, extension = os.path.splitext(nombre)
        if extension.lower() not in EXTENSIONES:
            continue
        if base.lower().startswith(NO_SON_CLASES) or base.startswith("_"):
            continue
        clases.append(leer_clase(os.path.join(carpeta, nombre)))

    clases.sort(key=lambda c: (c.fecha == "", c.fecha or c.archivo))
    return clases


def sintesis(carpeta=None):
    """
    El texto de la síntesis (aprendizaje.md), o "" si no hay.

    Se busca en la carpeta de clases y en la de arriba: cuando las clases
    viven en una subcarpeta `clases/` de un cuaderno, la síntesis suele
    estar al lado, no adentro.
    """
    if carpeta is None:
        carpeta = carpeta_de_clases()
    for donde in (carpeta, os.path.dirname(os.path.abspath(carpeta))):
        ruta = os.path.join(donde, ARCHIVO_DE_SINTESIS)
        if os.path.isfile(ruta):
            return _leer_texto(ruta)
    return ""


# =============================================================================
# Leer un archivo
# =============================================================================

def leer_clase(ruta):
    """Lee un archivo y devuelve una Clase, con lo que se pudo entender."""
    nombre = os.path.basename(ruta)
    clase = Clase(archivo=nombre, fecha=_fecha_del_nombre(nombre))
    try:
        clase.texto = _leer_texto(ruta)
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as error:
        clase.error = f"no se pudo leer: {error}"
        clase.con_recap = False
        return clase

    entender(clase)
    return clase


def _leer_texto(ruta):
    extension = os.path.splitext(ruta)[1].lower()
    if extension == ".docx":
        return _texto_de_docx(ruta)
    if extension == ".pdf":
        return _texto_de_pdf(ruta)
    with open(ruta, "r", encoding="utf-8", errors="replace") as archivo:
        return archivo.read()


def _texto_de_docx(ruta):
    """
    Un .docx es un zip; el texto está en word/document.xml, un párrafo por
    <w:p>. No hace falta ninguna biblioteca para sacarlo.
    """
    espacio = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(ruta) as zip_:
        raiz = ET.fromstring(zip_.read("word/document.xml"))
    parrafos = []
    for parrafo in raiz.iter(espacio + "p"):
        parrafos.append("".join(t.text or "" for t in parrafo.iter(espacio + "t")))
    return "\n".join(parrafos)


def _texto_de_pdf(ruta):
    try:
        import pypdf
    except ImportError:
        raise ValueError("para leer PDF hace falta instalar pypdf (pip install pypdf)")
    lector = pypdf.PdfReader(ruta)
    return "\n".join((pagina.extract_text() or "") for pagina in lector.pages)


def _fecha_del_nombre(nombre):
    coincidencia = re.match(r"(\d{4}-\d{2}-\d{2})", nombre)
    return coincidencia.group(1) if coincidencia else ""


# =============================================================================
# Entender el texto
# =============================================================================

def entender(clase):
    """
    Saca de `clase.texto` el título, las secciones y los puntos.

    Funciona con Markdown con secciones y con prosa sin ninguna. Lo que no
    encuentra lo deja vacío: mejor una lista vacía que una inventada.
    """
    lineas = clase.texto.splitlines()

    for linea in lineas:
        if linea.startswith("# "):
            clase.titulo = linea[2:].strip()
            break
    if not clase.titulo:
        clase.titulo = clase.fecha or os.path.splitext(clase.archivo)[0]

    # "sin recap" en el título es la convención para una clase que existió
    # pero de la que no quedó registro. Se muestra en la cronología, sin
    # inventarle contenido.
    clase.con_recap = "sin recap" not in clase.titulo.lower()

    clase.secciones = _secciones(lineas)
    if not clase.secciones:
        # Sin títulos de Markdown. Puede ser el mismo recap pero aplanado en
        # prosa —pasa cuando se pega un mail— o un apunte escrito a mano.
        clase.secciones = _secciones_en_prosa(clase.texto)

    clase.puntos_clave = _items(clase.secciones.get("puntos_clave", ""))
    clase.temas = _subtitulos(clase.secciones.get("temas", ""))
    clase.proximos_pasos = _pasos(clase.secciones.get("proximos_pasos", ""))
    clase.tema = _tema_principal(clase)
    return clase


def _tema_principal(clase):
    """
    Una línea que diga de qué fue la clase, para la cronología.

    El propósito de la reunión, si el recap lo trae: es una frase corta y
    escrita para eso. Si no, el título del primer punto clave. Si no, nada:
    la fila muestra el título del archivo y listo.
    """
    # La prosa de un mail viene cortada cada 75 caracteres: se juntan las
    # líneas y se toma la primera oración.
    proposito = " ".join(_limpiar(clase.secciones.get("proposito", "")).split())
    if proposito:
        primera_oracion = re.split(r"(?<=[.!?])\s", proposito, maxsplit=1)[0]
        return _recortar(primera_oracion, 110)
    if clase.puntos_clave:
        primero = clase.puntos_clave[0]
        return _recortar(primero.split(":")[0] if ":" in primero[:60] else primero, 110)
    return ""


def _recortar(texto, largo):
    texto = texto.strip().rstrip(".")
    return texto if len(texto) <= largo else texto[:largo - 1].rstrip() + "…"


# Los mismos nombres de sección, pero pegados en la prosa de un mail: "...
# Propósito de la reunión Revisar las frases. Puntos clave - Corregir ...".
_MARCAS_EN_PROSA = [
    ("proposito", r"prop[oó]sito de la reuni[oó]n"),
    ("puntos_clave", r"puntos clave"),
    ("temas", r"temas"),
    ("proximos_pasos", r"pr[oó]ximos pasos"),
]


def _secciones_en_prosa(texto):
    """
    Corta un recap aplanado en sus secciones, buscando los nombres de
    sección adentro del texto. Los ítems, que en el mail eran viñetas,
    quedaron como " - " en el medio de la prosa: se vuelven a abrir.
    """
    posiciones = []
    for clave, patron in _MARCAS_EN_PROSA:
        coincidencia = re.search(r"(?<![\w])" + patron + r"\b", texto, re.IGNORECASE)
        if coincidencia:
            posiciones.append((coincidencia.start(), coincidencia.end(), clave))
    if not posiciones:
        return {}
    posiciones.sort()

    secciones = {}
    for indice, (inicio, fin, clave) in enumerate(posiciones):
        hasta = posiciones[indice + 1][0] if indice + 1 < len(posiciones) else len(texto)
        cuerpo = texto[fin:hasta].strip(" :\n")
        # " - " separaba las viñetas: cada una vuelve a ser una línea con guion.
        cuerpo = re.sub(r"\s+-\s+", "\n- ", cuerpo)
        if cuerpo.startswith("- ") is False and "\n- " in cuerpo and clave != "proposito":
            # Lo que hay antes del primer guion es un título de tema, no un ítem.
            cuerpo = "- " + cuerpo if clave in ("puntos_clave", "proximos_pasos") else cuerpo
        secciones[clave] = cuerpo
    return secciones


def _pasos(texto):
    """
    Los próximos pasos, uno por persona y tarea.

    Vienen de dos formas, y las dos se han visto en recaps reales:

        - **Ana:** practicar el bend.          -> un paso de Ana
        - **Ana:**                             -> dos pasos de Ana
          - practicar el bend.
          - tocar sobre la pista.
    """
    pasos = []
    for item, subitems in _items_anidados(texto):
        item = _limpiar(item)
        if subitems and item.endswith(":"):
            para = item[:-1].strip()
            pasos.extend({"para": para, "texto": _limpiar(sub)} for sub in subitems)
        elif subitems:
            pasos.append(_quien_y_que(item + " " + " ".join(_limpiar(s) for s in subitems)))
        elif item:
            pasos.append(_quien_y_que(item))
    return [paso for paso in pasos if paso["texto"]]


def _sin_acentos(texto):
    return (texto.lower().replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))


def _secciones(lineas):
    """El texto de cada sección conocida, por su clave."""
    encontradas = {}
    actual = None
    cuerpo = []
    for linea in lineas:
        if linea.startswith("## "):
            if actual:
                encontradas[actual] = "\n".join(cuerpo).strip()
            titulo = _sin_acentos(linea[3:].strip())
            actual = next((clave for clave, variantes in SECCIONES.items()
                           if any(titulo.startswith(v) for v in variantes)), None)
            cuerpo = []
        elif actual:
            cuerpo.append(linea)
    if actual:
        encontradas[actual] = "\n".join(cuerpo).strip()
    return encontradas


def _items_anidados(texto):
    """
    Los ítems de una lista Markdown, cada uno con sus sub-ítems.

    Devuelve [(item, [subitem, ...]), ...]. Un ítem es una línea que empieza
    con "- " o "* " sin sangría; un sub-ítem, la misma cosa con sangría. Las
    líneas de continuación (sin guion) se pegan a lo último que se abrió.
    """
    items = []
    for linea in texto.splitlines():
        if re.match(r"^[-*] ", linea):
            items.append([linea[2:].strip(), []])
        elif re.match(r"^\s+[-*] ", linea) and items:
            items[-1][1].append(linea.strip()[2:].strip())
        elif linea.strip() and items:
            if items[-1][1]:
                items[-1][1][-1] += " " + linea.strip()
            else:
                items[-1][0] += " " + linea.strip()
    return [(item, subitems) for item, subitems in items]


def _items(texto):
    """Los ítems de primer nivel, con los sub-ítems pegados al de arriba."""
    items = []
    for item, subitems in _items_anidados(texto):
        completo = _limpiar(" ".join([item] + subitems))
        if completo:
            items.append(completo)
    return items


def _subtitulos(texto):
    return [linea[4:].strip() for linea in texto.splitlines() if linea.startswith("### ")]


def _quien_y_que(item):
    """'**Bruno:** practicar X' -> {"para": "Bruno", "texto": "practicar X"}."""
    coincidencia = re.match(r"^([A-ZÁÉÍÓÚ][\w\sÁÉÍÓÚáéíóúñ.]*?):\s*(.+)$", item)
    if coincidencia and len(coincidencia.group(1)) <= 30:
        return {"para": coincidencia.group(1).strip(), "texto": coincidencia.group(2).strip()}
    return {"para": "", "texto": item}


def _limpiar(texto):
    """Saca las marcas de Markdown que no aportan en una lista: negritas, código, enlaces."""
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    texto = re.sub(r"`(.+?)`", r"\1", texto)
    texto = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", texto)      # [[ruta|texto]]
    texto = re.sub(r"\[\[([^\]]+)\]\]", r"\1", texto)                # [[texto]]
    return texto.strip()


# =============================================================================
# Qué hacer en la app con cada cosa
# =============================================================================

# Cada regla: palabras que la disparan (sin acentos, minúsculas), y qué
# proponer. `solapa` es adónde ir; `config` es con qué abrir Teoría.
#
# Son reglas de palabras, y por eso son toscas a propósito: si el recap dice
# "bend" se propone el medidor. Lo fino lo hará el coach en la fase 2. Lo que
# no dispara ninguna regla no propone nada: mejor callado que equivocado.
REGLAS = [
    {
        "palabras": ("bend", "bending", "afinacion", "afinar"),
        "que": "Tocá esa nota en En vivo mirando el medidor: la línea lavanda te "
               "dice si el bend quedó corto o pasado. Y practicá la frase que la "
               "tiene: la devolución mide cada bend en cents.",
        "solapa": "vivo",
    },
    {
        "palabras": ("pista", "base", "groove", "tiempo", "ritmo", "compas", "metronomo", "bpm"),
        "que": "Grabá la sesión sobre la base y al guardar poné el BPM: se mide "
               "cuánto te adelantás o atrasás, y cuánto varía nota a nota.",
        "solapa": "vivo",
    },
    {
        "palabras": ("frase", "frases", "lick", "licks", "melodia"),
        "que": "Grabá la frase como referencia (o importá el audio del profe) y "
               "practicala contra ella: te dice nota por nota qué cambió.",
        "solapa": "frases",
    },
    {
        "palabras": ("posicion", "escala", "pentatonica", "acorde", "notas guia", "nota guia",
                     "tonica", "arpegio"),
        "que": "Mirá esa escala en Teoría: dónde cae en la armónica, la corrida, "
               "las notas guía de cada acorde y qué evitar.",
        "solapa": "teoria",
    },
]

# Para abrir Teoría ya en la posición o la escala de la que habla el recap.
POSICIONES_EN_TEXTO = {
    "primera posicion": 1, "1a posicion": 1, "1.a posicion": 1, "1ª posicion": 1,
    "segunda posicion": 2, "2a posicion": 2, "2.a posicion": 2, "2ª posicion": 2,
    "tercera posicion": 3, "3a posicion": 3, "3.a posicion": 3, "3ª posicion": 3,
    "cuarta posicion": 4, "4a posicion": 4, "4.a posicion": 4, "4ª posicion": 4,
    "quinta posicion": 5, "5a posicion": 5, "5.a posicion": 5, "5ª posicion": 5,
    "12a posicion": 12, "12.a posicion": 12, "12ª posicion": 12, "doceava posicion": 12,
    "duodecima posicion": 12,
}
ESCALAS_EN_TEXTO = {
    "pentatonica mayor": "pentatonica_mayor",
    "pentatonica menor": "pentatonica_menor",
    "blues mayor": "blues_mayor",
    "escala de blues": "blues",
}


def sugerencias(proximos_pasos):
    """
    Para cada próximo paso, qué hacer en la app. Devuelve una lista con un
    diccionario por paso: el texto, para quién, y las propuestas.
    """
    salida = []
    for paso in proximos_pasos:
        texto = _sin_acentos(paso["texto"])
        propuestas = []
        for regla in REGLAS:
            if any(palabra in texto for palabra in regla["palabras"]):
                propuesta = {"que": regla["que"], "solapa": regla["solapa"]}
                if regla["solapa"] == "teoria":
                    propuesta["config"] = _configuracion_en_texto(texto)
                propuestas.append(propuesta)
        salida.append({"para": paso["para"], "texto": paso["texto"], "propuestas": propuestas})
    return salida


def _configuracion_en_texto(texto):
    """La posición y la escala que el texto menciona, si menciona alguna."""
    config = {}
    for frase, numero in POSICIONES_EN_TEXTO.items():
        if frase in texto:
            config["posicion"] = numero
            break
    for frase, clave in ESCALAS_EN_TEXTO.items():
        if frase in texto:
            config["escala"] = clave
            break
    return config


# =============================================================================
# Buscar
# =============================================================================

def buscar(clases, consulta, contexto=70):
    """
    Las clases donde aparece `consulta`, con un pedacito de texto alrededor
    de cada aparición. Sin distinguir mayúsculas ni acentos.
    """
    consulta = _sin_acentos(consulta.strip())
    if not consulta:
        return []
    resultados = []
    for clase in clases:
        plano = _sin_acentos(clase.texto)
        pedazos = []
        desde = 0
        while len(pedazos) < 5:
            donde = plano.find(consulta, desde)
            if donde < 0:
                break
            inicio = max(0, donde - contexto)
            fin = min(len(clase.texto), donde + len(consulta) + contexto)
            pedazos.append(("…" if inicio > 0 else "") + clase.texto[inicio:fin].replace("\n", " ")
                           + ("…" if fin < len(clase.texto) else ""))
            desde = donde + len(consulta)
        if pedazos:
            resultados.append({"archivo": clase.archivo, "fecha": clase.fecha,
                               "titulo": clase.titulo, "pedazos": pedazos})
    resultados.reverse()          # las más nuevas primero
    return resultados


# =============================================================================
# Todo junto, para la solapa
# =============================================================================

def resumen(carpeta=None, cuantas_clases_para_practicar=2):
    """
    Lo que muestra la solapa Aprendizaje.

    `ultima` es la última clase CON recap: la que dice qué estamos viendo.
    `para_practicar` junta los próximos pasos de las últimas clases con
    recap, la más nueva primero, cada uno con sus propuestas.
    """
    if carpeta is None:
        carpeta = carpeta_de_clases()
    clases = listar(carpeta)
    con_recap = [c for c in clases if c.con_recap and not c.error]

    ultima = con_recap[-1] if con_recap else None
    para_practicar = []
    for clase in reversed(con_recap[-cuantas_clases_para_practicar:]):
        for paso in sugerencias(clase.proximos_pasos):
            paso["fecha"] = clase.fecha
            para_practicar.append(paso)

    # La ruta NO va a la pantalla: puede ser el cuaderno personal de alguien
    # y no hay motivo para mostrarla. Solo si es la carpeta por defecto o una
    # configurada en el .env.
    return {
        "origen": "material" if carpeta == CARPETA_POR_DEFECTO else "configurada",
        "existe": os.path.isdir(carpeta),
        "cantidad": len(clases),
        "ultima": ultima.como_diccionario(con_texto=True) if ultima else None,
        "para_practicar": para_practicar,
        "clases": [c.como_diccionario() for c in reversed(clases)],
        "sintesis": sintesis(carpeta),
    }
