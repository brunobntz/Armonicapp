"""
plan.py — El plan de estudio: lo que dice el profe, leído por el coach.

QUÉ ES

La solapa Aprendizaje muestra los apuntes de las clases tal cual. El plan es
lo que sale de leerlos con el coach: qué estamos viendo, qué recomienda el
profe, y con qué parte de la app se trabaja cada cosa. Se arma cuando lo
pedís, se guarda con fecha, y se muestra sin volver a llamar al modelo.

DÓNDE SE GUARDA

En material/_plan.json, la carpeta de la app. NUNCA en la carpeta de clases:
esa puede ser el cuaderno personal de alguien, y clases.py solo la lee.

LO QUE HAY QUE SABER

Para armar el plan, el texto de las últimas clases se le manda al modelo.
Con Ollama se queda en tu máquina; con Claude o ChatGPT, sale. Para los
apuntes de un tercero, esa decisión es de cada uno, y la pantalla lo dice
al lado del botón.
"""

import json
import os
from datetime import datetime

from armonica import clases, coach

CARPETA_POR_DEFECTO = "material"
ARCHIVO = "_plan.json"

# Cuántas clases con recap se le mandan al coach, y cuánto de cada una. Tres
# clases son un mes: lo que se está trabajando ahora. Más atrás está la
# síntesis, que ya lo resume.
CLASES_PARA_EL_PLAN = 3
CARACTERES_POR_CLASE = 6000
CARACTERES_DE_SINTESIS = 4000


def ruta_del_plan(carpeta=None):
    return os.path.join(carpeta or CARPETA_POR_DEFECTO, ARCHIVO)


def cargar(carpeta=None):
    """El plan guardado, o None si no hay."""
    ruta = ruta_del_plan(carpeta)
    if not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, encoding="utf-8") as archivo:
            return json.load(archivo)
    except (OSError, ValueError):
        return None


def guardar(plan, carpeta=None):
    carpeta = carpeta or CARPETA_POR_DEFECTO
    os.makedirs(carpeta, exist_ok=True)
    with open(ruta_del_plan(carpeta), "w", encoding="utf-8") as archivo:
        json.dump(plan, archivo, ensure_ascii=False, indent=1)


def borrar(carpeta=None):
    ruta = ruta_del_plan(carpeta)
    if os.path.isfile(ruta):
        os.remove(ruta)


def armar(carpeta_de_clases=None, carpeta=None, ruta_env=None):
    """
    Arma el plan con el coach y lo guarda. Devuelve el plan.

    Levanta coach.CoachNoDisponible si el coach no está configurado, o si
    no hay clases con recap para leer.
    """
    lista = [c for c in clases.listar(carpeta_de_clases) if c.con_recap and not c.error]
    if not lista:
        raise coach.CoachNoDisponible(
            "No hay apuntes de clase para leer. Dejá los resúmenes en la carpeta de clases.")

    recientes = lista[-CLASES_PARA_EL_PLAN:]
    textos = [{"fecha": c.fecha, "tema": c.tema, "texto": c.texto[:CARACTERES_POR_CLASE]}
              for c in recientes]
    sintesis = clases.sintesis(carpeta_de_clases)[:CARACTERES_DE_SINTESIS]

    crudo = coach.armar_plan(textos, sintesis, ruta_env)
    datos = interpretar(crudo)

    conf = coach.configuracion(ruta_env)
    datos["fecha"] = datetime.now().isoformat(timespec="minutes")
    datos["proveedor"] = conf["proveedor"]
    datos["modelo"] = conf["modelo"]
    datos["clases_usadas"] = [c.fecha for c in recientes]
    guardar(datos, carpeta)
    return datos


def interpretar(texto):
    """
    Lo que devolvió el modelo, como plan.

    Se le pidió JSON con una forma fija. Si vino dentro de un bloque de
    código, se saca; si no es JSON, o le faltan las partes, el texto entero
    queda como `viendo` y el resto vacío: un plan a medias se muestra, un
    error no explica nada.
    """
    limpio = (texto or "").strip()
    if limpio.startswith("```"):
        limpio = limpio.strip("`")
        if limpio.lower().startswith("json"):
            limpio = limpio[4:]
        limpio = limpio.strip()

    try:
        datos = json.loads(limpio)
    except ValueError:
        inicio, fin = limpio.find("{"), limpio.rfind("}")
        try:
            datos = json.loads(limpio[inicio:fin + 1]) if inicio >= 0 < fin else None
        except ValueError:
            datos = None

    if not isinstance(datos, dict):
        return {"viendo": (texto or "").strip(), "recomendaciones": [],
                "frase_del_profe": "", "en_crudo": True}

    recomendaciones = []
    for r in datos.get("recomendaciones") or []:
        if not isinstance(r, dict) or not r.get("que"):
            continue
        solapa = str(r.get("solapa") or "").strip().lower()
        if solapa not in ("vivo", "frases", "teoria", "historial"):
            solapa = ""
        config = r.get("config") if isinstance(r.get("config"), dict) else {}
        recomendaciones.append({
            "que": str(r["que"]).strip(),
            "por_que": str(r.get("por_que") or "").strip(),
            "en_la_app": str(r.get("en_la_app") or "").strip(),
            "solapa": solapa,
            "config": {k: config[k] for k in ("posicion", "escala") if k in config},
        })

    return {
        "viendo": str(datos.get("viendo") or "").strip(),
        "recomendaciones": recomendaciones[:5],
        "frase_del_profe": str(datos.get("frase_del_profe") or "").strip(),
        "en_crudo": False,
    }


def como_contexto(plan):
    """
    El plan en texto corto, para dárselo al coach como contexto cuando
    explica una práctica. Solo lo que dice el profe: ningún número.
    """
    if not plan:
        return ""
    lineas = []
    if plan.get("fecha"):
        lineas.append(f"Plan de estudio armado el {plan['fecha'][:10]}.")
    if plan.get("viendo"):
        lineas.append("Qué estamos viendo: " + plan["viendo"])
    for r in plan.get("recomendaciones") or []:
        lineas.append("- " + r["que"] + (" (" + r["por_que"] + ")" if r.get("por_que") else ""))
    if plan.get("frase_del_profe"):
        lineas.append("El profe: " + plan["frase_del_profe"])
    return "\n".join(lineas)
