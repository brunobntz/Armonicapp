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

TRES PROVEEDORES, UNA SOLA FORMA DE HABLARLES

    claude   la API de Claude, con el SDK oficial. Es el de por defecto.
             Pide una clave y `pip install anthropic`. Cuesta centavos.
    ollama   un modelo LOCAL, corriendo en tu propia máquina con Ollama.
             No pide clave ni paquete ni internet. Pide una placa de video
             decente para que conteste en segundos y no en minutos.
    openai   la API de ChatGPT, para quien ya tiene una clave de ahí.
             Sin paquete: se le habla por HTTP con la biblioteca estándar.

Los prompts, las rutas y la pantalla no saben cuál está puesto. Solo lo sabe
_pedir(), que reparte. Agregar un cuarto proveedor es agregar una función.

El audio nunca sale de tu máquina, con ninguno de los tres. Al coach le
llegan números y texto.
"""

import json
import os
import urllib.error
import urllib.request

PROVEEDORES = ("claude", "ollama", "openai")
PROVEEDOR_POR_DEFECTO = "claude"

# El modelo de cada proveedor si no se elige otro con LLM_MODELO.
#
# Para Ollama va un modelo de 7 mil millones de parámetros: entra entero en
# una placa de 8 GB y contesta en pocos segundos. Qwen 2.5 habla bien
# castellano; llama3.1:8b es la alternativa. Uno más grande (14B) ya no
# entra en 8 GB y pasa a contestar en minutos.
MODELOS_POR_DEFECTO = {
    "claude": "claude-opus-5",
    "ollama": "qwen2.5:7b",
    "openai": "gpt-4o-mini",
}

URLS_POR_DEFECTO = {
    "ollama": "http://localhost:11434",
    "openai": "https://api.openai.com/v1",
}

# Las respuestas son cortas a propósito: dos o tres párrafos que se leen con
# la armónica en la mano. Este tope es un seguro, no un objetivo.
MAXIMO_DE_TOKENS = 1500

# Un modelo local puede tardar: la primera respuesta carga el modelo en la
# placa (diez o veinte segundos) y sin placa cada respuesta es lenta.
SEGUNDOS_DE_ESPERA = {"claude": 60, "ollama": 240, "openai": 60}

ARCHIVO_ENV = ".env"


class CoachNoDisponible(Exception):
    """El coach no puede contestar: sin clave, sin paquete, o sin red."""


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

    if conf["proveedor"] == "claude":
        if not conf["clave"]:
            return dict(base, disponible=False,
                        motivo="Falta la clave. Copiá .env.ejemplo a .env y poné la tuya en LLM_CLAVE.")
        try:
            import anthropic  # noqa: F401  — solo para saber si está
        except ImportError:
            return dict(base, disponible=False, motivo="Falta el paquete: pip install anthropic")
        return dict(base, disponible=True, motivo="")

    if conf["proveedor"] == "openai":
        if not conf["clave"]:
            return dict(base, disponible=False,
                        motivo="Falta la clave de OpenAI. Ponela en LLM_CLAVE en el .env.")
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
        "acordes_del_blues": teoria.get("acordes"),
        "evitar": teoria.get("evitar"),
        "posiciones_utiles": teoria.get("posiciones_utiles"),
    }
    return (
        "El alumno está mirando la solapa de teoría de la app. Esto es lo que "
        "tiene en pantalla, calculado por la app, en JSON:\n\n"
        + json.dumps(datos, ensure_ascii=False, indent=1) +
        "\n\nSu pregunta es:\n\n" + pregunta.strip() +
        "\n\nContestá apoyándote en esos datos. Si la pregunta se va de lo que "
        "hay en pantalla, contestá igual como profe, pero avisá que eso no "
        "está calculado por la app."
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
    raise CoachNoDisponible(estado(ruta_env)["motivo"])


def _pedir_a_claude(conf, sistema, usuario):
    """La API de Claude, con el SDK oficial."""
    if not conf["clave"]:
        raise CoachNoDisponible(
            "Falta la clave. Copiá .env.ejemplo a .env y poné la tuya en LLM_CLAVE.")
    try:
        import anthropic
    except ImportError:
        raise CoachNoDisponible("Falta el paquete: pip install anthropic")

    cliente = anthropic.Anthropic(api_key=conf["clave"],
                                  timeout=float(SEGUNDOS_DE_ESPERA["claude"]), max_retries=1)
    try:
        respuesta = cliente.messages.create(
            model=conf["modelo"],
            max_tokens=MAXIMO_DE_TOKENS,
            system=sistema,
            # Poco esfuerzo alcanza: no hay nada que deducir, solo explicar
            # números que ya están. Y es más barato y más rápido.
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": usuario}],
        )
    except anthropic.AuthenticationError:
        raise CoachNoDisponible("La clave no es válida. Revisá LLM_CLAVE en el .env.")
    except anthropic.NotFoundError:
        raise CoachNoDisponible(f"No existe el modelo {conf['modelo']!r}. Revisá LLM_MODELO en el .env.")
    except anthropic.RateLimitError:
        raise CoachNoDisponible("El servicio está saturado. Probá en un minuto.")
    except anthropic.APIStatusError as error:
        raise CoachNoDisponible(f"El servicio contestó con un error ({error.status_code}).")
    except anthropic.APIConnectionError:
        raise CoachNoDisponible("No hay conexión con el servicio. ¿Estás sin internet?")

    if respuesta.stop_reason == "refusal":
        raise CoachNoDisponible("El modelo no quiso contestar esto.")

    texto = "".join(bloque.text for bloque in respuesta.content if bloque.type == "text")
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
    """
    if not conf["clave"]:
        raise CoachNoDisponible("Falta la clave de OpenAI. Ponela en LLM_CLAVE en el .env.")
    cuerpo = {
        "model": conf["modelo"],
        "max_tokens": MAXIMO_DE_TOKENS,
        "messages": [{"role": "system", "content": sistema},
                     {"role": "user", "content": usuario}],
    }
    cabeceras = {"Authorization": "Bearer " + conf["clave"]}
    try:
        respuesta = _http_json(conf["url"] + "/chat/completions", cuerpo, cabeceras,
                               segundos=SEGUNDOS_DE_ESPERA["openai"])
    except CoachNoDisponible as error:
        texto = str(error)
        if "401" in texto:
            raise CoachNoDisponible("La clave de OpenAI no es válida. Revisá LLM_CLAVE en el .env.")
        if "404" in texto:
            raise CoachNoDisponible(f"No existe el modelo {conf['modelo']!r}. Revisá LLM_MODELO en el .env.")
        if "429" in texto:
            raise CoachNoDisponible("El servicio está saturado o sin crédito. Probá en un minuto.")
        raise
    opciones = (respuesta or {}).get("choices") or [{}]
    return _texto_o_error(((opciones[0].get("message") or {}).get("content") or ""))


def _texto_o_error(texto):
    texto = (texto or "").strip()
    if not texto:
        raise CoachNoDisponible("El modelo devolvió una respuesta vacía.")
    return texto


def _http_json(url, cuerpo, cabeceras, segundos):
    """
    Un pedido HTTP con JSON de ida y de vuelta. GET si `cuerpo` es None.

    Es la única función que toca la red para Ollama y OpenAI; los tests la
    reemplazan. Traduce cada fallo a un CoachNoDisponible con el código o
    la palabra "conexión", que las funciones de arriba usan para dar un
    motivo entendible.
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
        raise CoachNoDisponible(f"El servicio contestó con un error ({error.code}).")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise CoachNoDisponible(f"No hay conexión con el servicio ({error}).")
    except ValueError:
        raise CoachNoDisponible("El servicio contestó algo que no es JSON.")
