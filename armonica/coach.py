"""
coach.py — El coach: un modelo de lenguaje que explica lo que la app midió.

QUÉ HACE Y QUÉ NO

La app mide: notas, cents, milisegundos, escalas, acordes. Eso no lo toca
nadie. El coach recibe ESOS números ya calculados y los explica como lo haría
un profe que te escuchó una vez: qué importa, por qué, y qué probar. Nunca
mide nada, nunca inventa un número, y si no tiene datos lo dice.

Es OPCIONAL. Sin configurar, la app anda exactamente igual que antes y en
Ajustes dice cómo activarlo. La configuración va en un archivo .env que git
ignora: la clave es tuya y se queda en tu máquina.

CUATRO PROVEEDORES, UNA SOLA FORMA DE HABLARLES

    claude   la API de Claude (Anthropic). Es el de por defecto. Pide una
             clave. Cuesta centavos.
    ollama   un modelo LOCAL, corriendo en tu propia máquina con Ollama.
             No pide clave ni paquete ni internet. Pide una placa de video
             decente para que conteste en segundos y no en minutos.
    openai   la API de ChatGPT, para quien ya tiene una clave de ahí.
    gemini   la API de Gemini (Google). La clave de Google AI Studio es
             gratis, con un tope por día.

A los cuatro se les habla por HTTP con la biblioteca estándar, sin
paquetes: la versión instalada no los trae, y sumarlos agregaría
bibliotecas compiladas sin firma que Windows puede bloquear.

Los prompts, las rutas y la pantalla no saben cuál está puesto. Solo lo sabe
_pedir(), que reparte. Agregar otro proveedor es agregar una función.

El audio nunca sale de tu máquina, con ninguno de los cuatro. Al coach le
llegan números y texto.
"""

import json
import os
import urllib.error
import urllib.request

PROVEEDORES = ("claude", "ollama", "openai", "gemini")
PROVEEDOR_POR_DEFECTO = "claude"

# Los que piden clave (Ollama no: corre en la máquina).
PROVEEDORES_CON_CLAVE = ("claude", "openai", "gemini")

# Cómo se llama cada uno en pantalla.
NOMBRES = {"claude": "Claude", "ollama": "Ollama", "openai": "ChatGPT", "gemini": "Gemini"}

# El modelo de cada proveedor si no se elige otro con LLM_MODELO. Vigentes
# al 2026-10-04: la versión instalada no se actualiza sola, así que si uno
# se retira, el coach dice que hace falta una versión nueva de la app.
#
# Para Ollama va un modelo de 7 mil millones de parámetros: entra entero en
# una placa de 8 GB y contesta en pocos segundos. Qwen 2.5 habla bien
# castellano; llama3.1:8b es la alternativa. Uno más grande (14B) ya no
# entra en 8 GB y pasa a contestar en minutos. De ChatGPT y Gemini, los
# más baratos: alcanzan para explicar números ya medidos.
MODELOS_POR_DEFECTO = {
    "claude": "claude-opus-5-5",
    "ollama": "qwen2.5:7b",
    "openai": "gpt-6-luna",
    "gemini": "gemini-3.5-flash-lite",
}

URLS_POR_DEFECTO = {
    "claude": "https://api.anthropic.com/v1",
    "ollama": "http://localhost:11434",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}

# Las respuestas son cortas a propósito: dos o tres párrafos que se leen con
# la armónica en la mano. Este tope es un seguro, no un objetivo. Es el de
# Ollama, que no piensa antes de contestar.
MAXIMO_DE_TOKENS = 1500

# Los modelos de Claude, ChatGPT y Gemini piensan antes de contestar, y lo
# que piensan cuenta dentro del tope: con 1500 una respuesta podría cortarse
# antes de empezar. Este deja lugar para las dos cosas; la respuesta sigue
# siendo corta porque así lo pide SISTEMA.
MAXIMO_DE_TOKENS_CON_PENSAMIENTO = 8000

# La versión de la API de mensajes de Claude: va en cada pedido.
VERSION_DE_LA_API_DE_CLAUDE = "2023-06-01"

# Un modelo local puede tardar: la primera respuesta carga el modelo en la
# placa (diez o veinte segundos) y sin placa cada respuesta es lenta.
SEGUNDOS_DE_ESPERA = {"claude": 90, "ollama": 240, "openai": 90, "gemini": 90}

ARCHIVO_ENV = ".env"

# Si los motivos que hablan de la clave mandan a Ajustes (la versión
# instalada, que no tiene .env) o al .env (Bruno). Lo pone
# servidor.arrancar().
CLAVE_EN_AJUSTES = False


class CoachNoDisponible(Exception):
    """
    El coach no puede contestar: sin clave, sin red, o el servicio dijo que no.

    Si lo levantó _http_json ante un error HTTP, lleva además `codigo` (el
    número que contestó el servicio) y `detalle` (el cuerpo de esa respuesta).
    Si lo levantó porque no pudo conectarse (sin red, o se acabó el tiempo),
    lleva `sin_conexion = True`: su texto trae el detalle técnico del error
    del sistema, que sirve para el registro pero no para mostrarle a nadie.
    """


# =============================================================================
# La configuración: el .env
# =============================================================================

def leer_env(ruta=None):
    """
    Lee un archivo .env como un diccionario. Sin dependencias.

    El formato es CLAVE=valor, una por línea. Se ignoran las líneas vacías y
    las que empiezan con #. Las comillas alrededor del valor se sacan, para
    que dé lo mismo escribir LLM_CLAVE=abc que LLM_CLAVE="abc".
    """
    if ruta is None:
        ruta = ARCHIVO_ENV
    valores = {}
    if not os.path.isfile(ruta):
        return valores
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, _, valor = linea.partition("=")
            valor = valor.strip()
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
                valor = valor[1:-1]
            valores[clave.strip()] = valor
    return valores


def configuracion(ruta_env=None):
    """
    Qué proveedor, con qué clave, qué modelo y en qué dirección.

    Devuelve un diccionario {"proveedor", "clave", "modelo", "url"}. Lee el
    .env primero y las variables de entorno después. La variable
    ANTHROPIC_API_KEY también sirve como clave, porque es la que el SDK de
    Claude lee solo: si ya la tenés puesta por otra cosa, no hace falta más.
    """
    env = leer_env(ruta_env)

    def valor(nombre, *alternativas):
        for candidato in (nombre,) + alternativas:
            if env.get(candidato):
                return env[candidato].strip()
        for candidato in (nombre,) + alternativas:
            if os.environ.get(candidato):
                return os.environ[candidato].strip()
        return ""

    proveedor = (valor("LLM_PROVEEDOR") or PROVEEDOR_POR_DEFECTO).lower()
    return {
        "proveedor": proveedor,
        "clave": valor("LLM_CLAVE", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"),
        "modelo": valor("LLM_MODELO") or MODELOS_POR_DEFECTO.get(proveedor, ""),
        "url": (valor("LLM_URL") or URLS_POR_DEFECTO.get(proveedor, "")).rstrip("/"),
    }


def _motivo_de_la_clave(cual, proveedor="claude"):
    """
    Qué decir cuando falta la clave ("falta") o no es válida ("invalida").
    A Bruno lo manda al .env; al profe, a Ajustes.
    """
    if CLAVE_EN_AJUSTES:
        return {"falta": "Falta la clave. Pegala en Ajustes, en El coach.",
                "invalida": "La clave no es válida. Revisala en Ajustes, en El coach."}[cual]
    if cual == "falta":
        if proveedor == "claude":
            return "Falta la clave. Copiá .env.ejemplo a .env y poné la tuya en LLM_CLAVE."
        return f"Falta la clave de {NOMBRES[proveedor]}. Ponela en LLM_CLAVE en el .env."
    return f"La clave de {NOMBRES[proveedor]} no es válida. Revisá LLM_CLAVE en el .env."


def estado(ruta_env=None):
    """
    Si el coach puede contestar, y si no, por qué. Para la solapa Ajustes.

    Devuelve {"disponible": bool, "motivo": str, "proveedor": str, "modelo": str}.
    Con Ollama, además pregunta si el servidor local está corriendo: es lo
    primero que falla y lo que menos se ve.
    """
    conf = configuracion(ruta_env)
    base = {"proveedor": conf["proveedor"], "modelo": conf["modelo"]}

    if conf["proveedor"] not in PROVEEDORES:
        return dict(base, disponible=False,
                    motivo=f"No conozco el proveedor {conf['proveedor']!r}. "
                           f"En el .env, LLM_PROVEEDOR puede ser: {', '.join(PROVEEDORES)}.")

    if conf["proveedor"] in PROVEEDORES_CON_CLAVE:
        if not conf["clave"]:
            return dict(base, disponible=False,
                        motivo=_motivo_de_la_clave("falta", conf["proveedor"]))
        return dict(base, disponible=True, motivo="")

    # ollama: sin clave ni paquete, pero el servidor tiene que estar andando.
    try:
        modelos = _http_json(conf["url"] + "/api/tags", None, {}, segundos=2)
    except CoachNoDisponible:
        return dict(base, disponible=False,
                    motivo=f"Ollama no está corriendo en {conf['url']}. "
                           f"Abrilo (o corré `ollama serve`) y recargá esta solapa.")
    nombres = [m.get("name", "") for m in (modelos or {}).get("models", [])]
    if not any(n == conf["modelo"] or n.split(":")[0] == conf["modelo"].split(":")[0]
               for n in nombres):
        return dict(base, disponible=False,
                    motivo=f"Ollama está corriendo pero no tiene el modelo {conf['modelo']!r}. "
                           f"Bajalo con: ollama pull {conf['modelo']}")
    return dict(base, disponible=True, motivo="")


# =============================================================================
# Los prompts
# =============================================================================

# Quién es el coach. Va igual en todas las preguntas: es lo que hace que las
# respuestas suenen a la misma persona.
SISTEMA = """Sos un profesor de armónica diatónica que acompaña a un alumno adulto.
Hablás en español rioplatense, de vos, cercano y directo, sin adornos.

REGLAS QUE NO SE NEGOCIAN
- Trabajás SOLO con los datos que te pasan. La app ya midió todo: notas,
  cents, milisegundos, escalas, acordes. Vos explicás qué significan y qué
  hacer con eso. No inventes números, notas ni agujeros que no estén en los
  datos. Si algo no está medido, decí que no está medido.
- Sé breve: dos o tres párrafos cortos, que se lean con la armónica en la
  mano. Sin listas largas, sin títulos, sin negritas.
- Priorizá: una cosa para trabajar ahora, no diez. Si todo salió bien,
  decilo y proponé el paso siguiente.
- La notación de tablatura: un número es soplado (o con flecha ↑), un guion
  o flecha ↓ delante es aspirado, y cada apóstrofe es un semitono de bend.
  Un bend que sale "alto" es un bend corto (no bajaste lo suficiente); uno
  que sale "bajo" es un bend pasado.
- Tocar más lento o más rápido que la referencia no es un error: es una
  decisión. No lo corrijas salvo que el alumno pregunte por eso."""


def prompt_de_devolucion(comparacion, contexto=""):
    """
    El pedido para explicar una práctica. `comparacion` es el diccionario que
    el servidor ya le manda al navegador: los tres números, los consejos y
    el detalle nota por nota.

    `contexto` es el plan de estudio vigente, en texto: lo que el profe
    viene marcando. Sirve para conectar la práctica con eso ("el bend del 2
    es justo lo que se trabajó en la última clase"). Es contexto, no datos:
    los números siguen siendo solo los medidos.
    """
    devolucion = comparacion.get("devolucion", {})
    datos = {
        "frase": comparacion.get("nombre"),
        "resumen": devolucion,
        "nota_por_nota": comparacion.get("notas", [])[:40],
        "faltantes": comparacion.get("faltantes", []),
        "sobrantes": comparacion.get("sobrantes", []),
        "cambiadas": comparacion.get("cambiadas", []),
        "velocidad_pct": comparacion.get("velocidad"),
        # Los intentos anteriores contra esta misma frase, medidos por la
        # app: son datos, y permiten decir "el bend del 3 viene mejorando".
        "progreso": comparacion.get("progreso"),
        "intentos_anteriores": comparacion.get("intentos", [])[:-1],
    }
    prompt = (
        "El alumno acaba de tocar una frase de referencia y la app la comparó "
        "con el original. Estos son los datos medidos, en JSON:\n\n"
        + json.dumps(datos, ensure_ascii=False, indent=1) +
        "\n\nExplicale cómo le salió y qué trabajar primero. Los consejos de "
        "`resumen.consejos` ya están priorizados por la app: apoyate en ellos, "
        "agregá el porqué musical, y no los contradigas. Si hay intentos "
        "anteriores, decí cómo viene respecto de ellos, con los números que están."
    )
    if contexto:
        prompt += (
            "\n\nPara que lo conectes con lo que el profe viene marcando, este es "
            "el plan de estudio vigente. Es contexto: no saques números de acá.\n\n"
            + contexto
        )
    return prompt


# Lo que la app sabe hacer, para que el coach pueda decir CON QUE se
# trabaja cada recomendacion del profe. Una linea por cosa; las claves de
# solapa son las que usa la pantalla.
CATALOGO_DE_LA_APP = """\
- solapa "vivo": el medidor de afinación en tiempo real (cents), el diagrama
  de la armónica con la escala marcada y la línea que muestra un bend a
  medio hacer, y grabar una sesión; al guardarla con el BPM de la base se
  mide el ritmo (cuánto te adelantás o atrasás, dispersión nota a nota).
- solapa "frases": grabar una frase de referencia o importar el audio del
  profe, practicarla y recibir una devolución: notas acertadas, afinación
  de cada bend en cents, tiempo nota por nota, y escuchar las dos seguidas.
- solapa "teoria": para una armónica, posición y escala: dónde cae la
  escala en la armónica, la corrida desde la tónica, el blues de doce
  compases con las notas guía (3ª y 7ª) de cada acorde y por dónde agarrarlas,
  qué notas evitar sobre cada acorde, y en qué posición conviene la escala.
  Acepta config: {"posicion": 1-12, "escala": "pentatonica_mayor" |
  "pentatonica_menor" | "blues" | "blues_mayor"}.
- solapa "historial": cómo viene cada bend sesión por sesión."""


def prompt_de_plan(clases_recientes, sintesis):
    """
    El pedido para armar el plan de estudio a partir de los apuntes.

    `clases_recientes` es una lista de {"fecha", "tema", "texto"}, de la
    más vieja a la más nueva. `sintesis` es el texto de la capa editable,
    si hay. Se pide JSON con una forma fija, que plan.interpretar() lee.
    """
    partes = ["Estos son los apuntes de las últimas clases del alumno, de la más "
              "vieja a la más nueva. Son resúmenes que manda el profesor:\n"]
    for clase in clases_recientes:
        partes.append(f"=== Clase del {clase['fecha']} — {clase['tema'] or 'sin tema'} ===\n"
                      f"{clase['texto']}\n")
    if sintesis:
        partes.append("=== La síntesis que el alumno lleva de todas las clases (puede "
                      "estar desactualizada respecto de las de arriba) ===\n" + sintesis + "\n")
    partes.append("=== Lo que la app sabe hacer ===\n" + CATALOGO_DE_LA_APP + "\n")
    partes.append(
        "Armá el plan de estudio de esta semana. Contestá SOLO con un JSON con "
        "esta forma exacta, sin texto antes ni después:\n\n"
        '{\n'
        ' "viendo": "dos o tres oraciones: qué se está trabajando ahora, según la última clase",\n'
        ' "recomendaciones": [\n'
        '  {"que": "una cosa concreta para practicar, en imperativo y de vos",\n'
        '   "por_que": "el motivo musical, en una oración",\n'
        '   "en_la_app": "cómo se trabaja con la app, en una oración",\n'
        '   "solapa": "vivo" | "frases" | "teoria" | "historial",\n'
        '   "config": {"posicion": 12, "escala": "blues_mayor"}   (solo si solapa es teoria y aplica)\n'
        '  }\n'
        ' ],\n'
        ' "frase_del_profe": "una frase textual del profe, de los apuntes, para tener presente"\n'
        '}\n\n'
        "Entre tres y cinco recomendaciones, de la más importante a la menos. Lo que "
        "el profe pidió explícitamente en \"Próximos pasos\" va primero. Solo cosas "
        "que estén en los apuntes: no inventes ejercicios que el profe no dio.\n\n"
        "NO INDIQUES NÚMEROS DE AGUJERO POR TU CUENTA. Nombrá las notas (Mib, Lab, "
        "el bend del 2) y copiá los agujeros solo si el apunte los trae textualmente. "
        "Dónde cae cada nota en la armónica lo calcula la app en Teoría, y lo calcula "
        "bien; un agujero equivocado en el plan es peor que ninguno."
    )
    return "\n".join(partes)


def armar_plan(clases_recientes, sintesis, ruta_env=None):
    """El texto (JSON, si el modelo hizo caso) del plan de estudio."""
    return _pedir(SISTEMA, prompt_de_plan(clases_recientes, sintesis), ruta_env)


def prompt_de_teoria(teoria, pregunta):
    """
    El pedido para una pregunta sobre la solapa Teoría. `teoria` es el
    diccionario de /api/teoria: la escala, la corrida, los acordes, qué
    evitar, y las fuentes.
    """
    datos = {
        "armonica": teoria.get("tonalidad"),
        "posicion": teoria.get("nombre_posicion"),
        "tono": teoria.get("tono"),
        "escala": teoria.get("nombre_escala"),
        "notas_de_la_escala": teoria.get("notas"),
        "tonica": teoria.get("tonica"),
        "corrida": [n.get("tab") + " " + n.get("nombre", "") for n in teoria.get("corrida", [])],
        # Que acorde va en cada compas. Sin esto, "la 3ra del compas 5" era
        # imposible de contestar: los acordes iban sueltos y cada modelo
        # elegia uno distinto. La pantalla lo muestra; el coach tambien lo
        # tiene que ver.
        "doce_compases": [f"compas {c.get('compas')}: {c.get('acorde')} ({c.get('grado')})"
                          for c in teoria.get("progresion", [])],
        "acordes_del_blues": teoria.get("acordes"),
        "evitar": teoria.get("evitar"),
        "posiciones_utiles": teoria.get("posiciones_utiles"),
    }
    return (
        "El alumno está mirando la solapa de teoría de la app. Esto es lo que "
        "tiene en pantalla, calculado por la app, en JSON:\n\n"
        + json.dumps(datos, ensure_ascii=False, indent=1) +
        "\n\nSu pregunta es:\n\n" + pregunta.strip() +
        "\n\nContestá apoyándote en esos datos. Cada nota que nombres, decila "
        "como se toca en la armónica: la nota, el agujero y si es soplado o "
        "aspirado, con la tab entre paréntesis, por ejemplo \"D, 4 aspirado "
        "(↓4)\". Nunca por octava como \"F4\" o \"G4\": eso no le dice al "
        "alumno qué agujero tocar. Cuando el alumno dice \"la 3ra\", \"la 5ta\" "
        "o \"la 7ma\" habla de un grado del acorde, no de una posición de la "
        "armónica: el alumno ya está en la "
        + str(teoria.get("nombre_posicion") or "posición de la pantalla") +
        " y no la cambia, así que no le digas que se ponga en otra. Si la "
        "pregunta se va de lo que hay en pantalla, contestá igual como profe, "
        "pero avisá que eso no está calculado por la app."
    )


def prompt_de_base(nombre, ficha, tonalidad_armonica):
    """
    El pedido para explicar la base de una canción: el cifrado compás por
    compás y los hechos que la app ya contó (cadencias, acordes fuera de la
    tonalidad). El coach interpreta: la forma, cómo pensar cada acorde,
    dónde apuntar las notas guía. No agrega acordes que no estén.
    """
    cifrado = [
        f"{compas['compas']}: " + " ".join(a["nombre"] for a in compas["acordes"])
        for compas in ficha.get("cifrado", []) if compas["acordes"]
    ]
    datos = {
        "cancion": nombre,
        "tonalidad": ficha.get("tonalidad"),
        "modo": ficha.get("modo"),
        "bpm": ficha.get("bpm"),
        "compas": f"{ficha.get('pulsos_por_compas')}/4",
        "con_swing": ficha.get("con_swing"),
        "coro": f"del compás {ficha.get('coro_desde')} al {ficha.get('coro_hasta')}",
        "armonica_del_alumno": tonalidad_armonica,
        "hechos_contados_por_la_app": ficha.get("hechos"),
        "cifrado": cifrado,
    }
    return (
        "El alumno va a practicar sobre esta base de Band-in-a-Box. Esto es lo "
        "que la app leyó del archivo, en JSON:\n\n"
        + json.dumps(datos, ensure_ascii=False, indent=1) +
        "\n\nExplicale la base como un profe antes de tocarla: qué forma tiene, "
        "cómo se agrupan los acordes (las cadencias que la app encontró y las "
        "que veas vos), cómo pensar los acordes que se salen de la tonalidad, "
        "y en qué compases conviene apuntar a las notas guía. Trabajá solo con "
        "los acordes del cifrado: no agregues ni cambies ninguno. Dos o tres "
        "párrafos cortos, sin listas ni títulos."
    )


# =============================================================================
# Las preguntas
# =============================================================================

def explicar_devolucion(comparacion, ruta_env=None, contexto=""):
    """Una devolución en palabras, a partir de la comparación ya medida."""
    return _pedir(SISTEMA, prompt_de_devolucion(comparacion, contexto), ruta_env)


def explicar_base(nombre, ficha, tonalidad_armonica, ruta_env=None):
    """La explicación de una base de Band-in-a-Box, a partir de su cifrado."""
    return _pedir(SISTEMA, prompt_de_base(nombre, ficha, tonalidad_armonica), ruta_env)


def preguntar_teoria(teoria, pregunta, ruta_env=None):
    """Una respuesta a una pregunta libre sobre lo que muestra Teoría."""
    if not (pregunta or "").strip():
        raise CoachNoDisponible("Escribí una pregunta primero.")
    return _pedir(SISTEMA, prompt_de_teoria(teoria, pregunta), ruta_env)


# =============================================================================
# La llamada. Es LO ÚNICO que sabe con quién habla.
# =============================================================================

def _pedir(sistema, usuario, ruta_env=None):
    """
    Manda un pedido al proveedor configurado y devuelve el texto.

    Recibe el prompt de sistema y el del usuario, devuelve texto, y levanta
    CoachNoDisponible con un motivo legible cuando no puede. Los tests la
    reemplazan por una función falsa: nunca tocan la red.
    """
    conf = configuracion(ruta_env)
    proveedor = conf["proveedor"]

    if proveedor == "claude":
        return _pedir_a_claude(conf, sistema, usuario)
    if proveedor == "ollama":
        return _pedir_a_ollama(conf, sistema, usuario)
    if proveedor == "openai":
        return _pedir_a_openai(conf, sistema, usuario)
    if proveedor == "gemini":
        return _pedir_a_gemini(conf, sistema, usuario)
    raise CoachNoDisponible(estado(ruta_env)["motivo"])


def _motivo_del_error(error, conf):
    """
    El motivo de un error HTTP de Claude, ChatGPT o Gemini, o None si no hay
    uno mejor que "El servicio contestó con un error (N)".
    """
    codigo = getattr(error, "codigo", None)
    detalle = getattr(error, "detalle", "") or ""
    # Gemini contesta 400, y no 401, a una clave que no es válida: se
    # reconoce por el motivo que viene en el cuerpo.
    if codigo == 401 or (codigo == 400 and "API_KEY_INVALID" in detalle):
        return _motivo_de_la_clave("invalida", conf["proveedor"])
    if codigo == 402:
        return "La cuenta de esa clave no tiene crédito."
    if codigo == 403:
        return "Esa clave no tiene permiso para usar el modelo."
    if codigo == 404:
        if CLAVE_EN_AJUSTES:
            return f"No existe el modelo {conf['modelo']!r}: hace falta una versión nueva de la app."
        return f"No existe el modelo {conf['modelo']!r}. Revisá LLM_MODELO en el .env."
    if codigo in (429, 529):
        return "El servicio está saturado, o la clave llegó a su tope de uso. Probá en un rato."
    return None


def _pedir_por_http(conf, url, cuerpo, cabeceras):
    """
    _http_json para un proveedor con clave, con los errores ya traducidos.
    Lo que contestó el servicio queda en el registro: en la instalada es lo
    único que Bruno puede mirar si el coach del profe no anda.
    """
    try:
        return _http_json(url, cuerpo, cabeceras,
                          segundos=SEGUNDOS_DE_ESPERA[conf["proveedor"]]) or {}
    except CoachNoDisponible as error:
        if getattr(error, "sin_conexion", False):
            # El texto crudo ("getaddrinfo failed", "Errno 11001"...) va al
            # registro; a la pantalla, una frase que entienda cualquiera.
            print(f"  El coach ({NOMBRES[conf['proveedor']]}) no pudo conectarse: {error}")
            raise CoachNoDisponible("No hay conexión con el servicio. ¿Estás sin internet?")
        if getattr(error, "codigo", None):
            print(f"  El coach ({NOMBRES[conf['proveedor']]}) contestó {error.codigo}: "
                  f"{(getattr(error, 'detalle', '') or '')[:300]}")
        motivo = _motivo_del_error(error, conf)
        if motivo:
            raise CoachNoDisponible(motivo)
        raise


def _pedir_a_claude(conf, sistema, usuario):
    """La API de Claude, por HTTP."""
    if not conf["clave"]:
        raise CoachNoDisponible(_motivo_de_la_clave("falta", "claude"))
    cuerpo = {
        "model": conf["modelo"],
        "max_tokens": MAXIMO_DE_TOKENS_CON_PENSAMIENTO,
        "system": sistema,
        # Poco esfuerzo alcanza: no hay nada que deducir, solo explicar
        # números que ya están. Y es más barato y más rápido.
        "output_config": {"effort": "low"},
        "messages": [{"role": "user", "content": usuario}],
    }
    cabeceras = {"x-api-key": conf["clave"], "anthropic-version": VERSION_DE_LA_API_DE_CLAUDE}
    respuesta = _pedir_por_http(conf, conf["url"] + "/messages", cuerpo, cabeceras)
    if respuesta.get("stop_reason") == "refusal":
        raise CoachNoDisponible("El modelo no quiso contestar esto.")
    # El contenido es una lista de bloques: lo que pensó (vacío) y el texto.
    texto = "".join(bloque.get("text", "") for bloque in respuesta.get("content") or []
                    if isinstance(bloque, dict) and bloque.get("type") == "text")
    return _texto_o_error(texto)


def _pedir_a_ollama(conf, sistema, usuario):
    """
    Un modelo local, por la API de chat de Ollama. Sin clave ni paquete.

    `stream: false` para recibir la respuesta entera de una. `num_predict`
    es el tope de tokens, el equivalente de max_tokens.
    """
    cuerpo = {
        "model": conf["modelo"],
        "stream": False,
        "messages": [{"role": "system", "content": sistema},
                     {"role": "user", "content": usuario}],
        "options": {"num_predict": MAXIMO_DE_TOKENS, "temperature": 0.4},
    }
    try:
        respuesta = _http_json(conf["url"] + "/api/chat", cuerpo, {},
                               segundos=SEGUNDOS_DE_ESPERA["ollama"])
    except CoachNoDisponible as error:
        texto = str(error)
        if "404" in texto:
            raise CoachNoDisponible(
                f"Ollama no tiene el modelo {conf['modelo']!r}. Bajalo con: ollama pull {conf['modelo']}")
        if "conexión" in texto:
            raise CoachNoDisponible(
                f"Ollama no está corriendo en {conf['url']}. Abrilo (o corré `ollama serve`).")
        raise
    return _texto_o_error(((respuesta or {}).get("message") or {}).get("content", ""))


def _pedir_a_openai(conf, sistema, usuario):
    """
    La API de ChatGPT (o cualquiera compatible: LM Studio, etc., cambiando
    LLM_URL). Por HTTP con la biblioteca estándar, sin paquete.

    Los modelos de ahora piensan antes de contestar: el tope va en
    max_completion_tokens (max_tokens lo rechazan) e incluye lo que piensan.
    """
    if not conf["clave"]:
        raise CoachNoDisponible(_motivo_de_la_clave("falta", "openai"))
    cuerpo = {
        "model": conf["modelo"],
        "max_completion_tokens": MAXIMO_DE_TOKENS_CON_PENSAMIENTO,
        # Poco esfuerzo alcanza, como con Claude: solo explica números.
        "reasoning_effort": "low",
        "messages": [{"role": "system", "content": sistema},
                     {"role": "user", "content": usuario}],
    }
    respuesta = _pedir_por_http(conf, conf["url"] + "/chat/completions", cuerpo,
                                {"Authorization": "Bearer " + conf["clave"]})
    opciones = respuesta.get("choices") or [{}]
    return _texto_o_error(((opciones[0].get("message") or {}).get("content") or ""))


def _pedir_a_gemini(conf, sistema, usuario):
    """
    La API de Gemini (Google), por su forma propia: generateContent con la
    clave en x-goog-api-key. No por su versión compatible con OpenAI: ahí
    la clave va en Authorization: Bearer, que puede rechazar las claves
    nuevas de Google (empiezan con "AQ."). Así andan las nuevas y las
    viejas ("AIza").
    """
    if not conf["clave"]:
        raise CoachNoDisponible(_motivo_de_la_clave("falta", "gemini"))
    cuerpo = {
        "system_instruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user", "parts": [{"text": usuario}]}],
        "generationConfig": {
            # Incluye lo que el modelo piensa antes de contestar.
            "maxOutputTokens": MAXIMO_DE_TOKENS_CON_PENSAMIENTO,
            # Poco, como con los otros. Es el campo de los modelos Gemini 3;
            # uno 2.5 puesto en LLM_MODELO lo rechazaría.
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    url = f"{conf['url']}/models/{conf['modelo']}:generateContent"
    respuesta = _pedir_por_http(conf, url, cuerpo, {"x-goog-api-key": conf["clave"]})
    candidatos = respuesta.get("candidates") or []
    if not candidatos:
        if (respuesta.get("promptFeedback") or {}).get("blockReason"):
            raise CoachNoDisponible("El modelo no quiso contestar esto.")
        raise CoachNoDisponible("El modelo devolvió una respuesta vacía.")
    if candidatos[0].get("finishReason") == "SAFETY":
        raise CoachNoDisponible("El modelo no quiso contestar esto.")
    partes = (candidatos[0].get("content") or {}).get("parts") or []
    # Las partes marcadas "thought" son lo que pensó: no van.
    texto = "".join(parte.get("text", "") for parte in partes
                    if isinstance(parte, dict) and not parte.get("thought"))
    return _texto_o_error(texto)


def _texto_o_error(texto):
    texto = (texto or "").strip()
    if not texto:
        raise CoachNoDisponible("El modelo devolvió una respuesta vacía.")
    return texto


def _http_json(url, cuerpo, cabeceras, segundos):
    """
    Un pedido HTTP con JSON de ida y de vuelta. GET si `cuerpo` es None.

    Es la única función que toca la red para Claude, Ollama, OpenAI y
    Gemini; los tests la reemplazan. Traduce cada fallo a un
    CoachNoDisponible con el código o la palabra "conexión", que las
    funciones de arriba usan para dar un motivo entendible.
    """
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    pedido = urllib.request.Request(url, data=datos, method="GET" if datos is None else "POST")
    pedido.add_header("Content-Type", "application/json")
    for nombre, valor in cabeceras.items():
        pedido.add_header(nombre, valor)
    try:
        with urllib.request.urlopen(pedido, timeout=segundos) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # El código y el cuerpo van aparte: quien llama elige el motivo sin
        # buscar números en el texto, y Gemini dice en el cuerpo si lo que
        # falló es la clave.
        falla = CoachNoDisponible(f"El servicio contestó con un error ({error.code}).")
        falla.codigo = error.code
        try:
            falla.detalle = error.read().decode("utf-8", "replace")[:2000]
        except (OSError, AttributeError, ValueError):
            falla.detalle = ""
        raise falla
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        # Se marca aparte, como al HTTPError: quien llama no busca la palabra
        # "conexión" en el texto para saber que fue esto.
        falla = CoachNoDisponible(f"No hay conexión con el servicio ({error}).")
        falla.sin_conexion = True
        raise falla
    except ValueError:
        raise CoachNoDisponible("El servicio contestó algo que no es JSON.")
