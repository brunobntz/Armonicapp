"""
coach.py — El coach: un modelo de lenguaje que explica lo que la app midió.

QUÉ HACE Y QUÉ NO

La app mide: notas, cents, milisegundos, escalas, acordes. Eso no lo toca
nadie. El coach recibe ESOS números ya calculados y los explica como lo haría
un profe que te escuchó una vez: qué importa, por qué, y qué probar. Nunca
mide nada, nunca inventa un número, y si no tiene datos lo dice.

Es OPCIONAL. Sin clave, o sin el paquete instalado, la app anda exactamente
igual que antes y en Ajustes dice cómo activarlo. La clave es tuya y se queda
en tu máquina: va en un archivo .env que git ignora.

CÓMO SE ACTIVA

    pip install anthropic
    copiar .env.ejemplo a .env y poner la clave

Usa la API de Claude con el SDK oficial. Para conectar otro proveedor hay
que reemplazar UNA función, _pedir(): todo lo demás —los prompts, las rutas,
la pantalla— no sabe con quién habla.

El audio nunca sale de tu máquina. Al coach le llegan números y texto.
"""

import json
import os

# El modelo por defecto. Se puede cambiar en el .env con LLM_MODELO.
MODELO_POR_DEFECTO = "claude-opus-5"

# Las respuestas son cortas a propósito: dos o tres párrafos que se leen con
# la armónica en la mano. Este tope es un seguro, no un objetivo.
MAXIMO_DE_TOKENS = 1500

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
    La clave y el modelo, del .env o del entorno. Devuelve (clave, modelo).

    La variable de entorno ANTHROPIC_API_KEY también sirve, porque es la que
    el SDK lee solo: si ya la tenés puesta por otra cosa, no hace falta el
    .env.
    """
    env = leer_env(ruta_env)
    clave = (env.get("LLM_CLAVE") or env.get("ANTHROPIC_API_KEY")
             or os.environ.get("LLM_CLAVE") or os.environ.get("ANTHROPIC_API_KEY") or "")
    modelo = env.get("LLM_MODELO") or os.environ.get("LLM_MODELO") or MODELO_POR_DEFECTO
    return clave.strip(), modelo.strip()


def estado(ruta_env=None):
    """
    Si el coach puede contestar, y si no, por qué. Para la solapa Ajustes.

    Devuelve {"disponible": bool, "motivo": str, "modelo": str}.
    """
    clave, modelo = configuracion(ruta_env)
    if not clave:
        return {"disponible": False, "modelo": modelo,
                "motivo": "Falta la clave. Copiá .env.ejemplo a .env y poné la tuya en LLM_CLAVE."}
    try:
        import anthropic  # noqa: F401  — solo para saber si está
    except ImportError:
        return {"disponible": False, "modelo": modelo,
                "motivo": "Falta el paquete: pip install anthropic"}
    return {"disponible": True, "modelo": modelo, "motivo": ""}


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


def prompt_de_devolucion(comparacion):
    """
    El pedido para explicar una práctica. `comparacion` es el diccionario que
    el servidor ya le manda al navegador: los tres números, los consejos y
    el detalle nota por nota.
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
    }
    return (
        "El alumno acaba de tocar una frase de referencia y la app la comparó "
        "con el original. Estos son los datos medidos, en JSON:\n\n"
        + json.dumps(datos, ensure_ascii=False, indent=1) +
        "\n\nExplicale cómo le salió y qué trabajar primero. Los consejos de "
        "`resumen.consejos` ya están priorizados por la app: apoyate en ellos, "
        "agregá el porqué musical, y no los contradigas."
    )


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


# =============================================================================
# Las dos preguntas
# =============================================================================

def explicar_devolucion(comparacion, ruta_env=None):
    """Una devolución en palabras, a partir de la comparación ya medida."""
    return _pedir(SISTEMA, prompt_de_devolucion(comparacion), ruta_env)


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
    Manda un pedido al modelo y devuelve el texto de la respuesta.

    Para usar otro proveedor, reemplazá esta función: recibe el prompt de
    sistema y el del usuario, devuelve texto, y levanta CoachNoDisponible
    con un motivo legible cuando no puede.
    """
    clave, modelo = configuracion(ruta_env)
    if not clave:
        raise CoachNoDisponible(estado(ruta_env)["motivo"])

    try:
        import anthropic
    except ImportError:
        raise CoachNoDisponible("Falta el paquete: pip install anthropic")

    cliente = anthropic.Anthropic(api_key=clave, timeout=60.0, max_retries=1)

    try:
        respuesta = cliente.messages.create(
            model=modelo,
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
        raise CoachNoDisponible(f"No existe el modelo {modelo!r}. Revisá LLM_MODELO en el .env.")
    except anthropic.RateLimitError:
        raise CoachNoDisponible("El servicio está saturado. Probá en un minuto.")
    except anthropic.APIStatusError as error:
        raise CoachNoDisponible(f"El servicio contestó con un error ({error.status_code}).")
    except anthropic.APIConnectionError:
        raise CoachNoDisponible("No hay conexión con el servicio. ¿Estás sin internet?")

    if respuesta.stop_reason == "refusal":
        raise CoachNoDisponible("El modelo no quiso contestar esto.")

    texto = "".join(bloque.text for bloque in respuesta.content if bloque.type == "text")
    if not texto.strip():
        raise CoachNoDisponible("El modelo devolvió una respuesta vacía.")
    return texto.strip()
