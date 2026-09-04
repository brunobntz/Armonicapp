"""
menu.py — El menú interactivo con el que arranca la app.

POR QUE EXISTE

La app tiene ocho banderas de línea de comandos. Para usarla todos los días eso
es fricción: hay que acordarse de los nombres, del orden, de qué valores acepta
cada una. El menú te pregunta lo que hace falta y ya.

Las banderas siguen existiendo, y siguen siendo el camino cuando querés repetir
exactamente el mismo análisis o automatizar algo. El menú es para el uso normal.

COMO ESTA ARMADO

La parte que DECIDE está separada de la parte que PREGUNTA:

    interpretar_respuesta()   pura, sin input(), se puede probar con tests
    preguntar()               la envoltura que habla con la terminal

Es la misma separación de siempre en este proyecto. Sin ella, probar el menú
requeriría simular a alguien tecleando, que es incómodo y frágil.

TODAS LAS PREGUNTAS TIENEN UN VALOR POR DEFECTO

Se elige apretando Enter. Después de la primera vez vas a estar apretando Enter
cuatro veces seguidas, y eso está bien: la opción más común tiene que ser la
más rápida.
"""

import config
from armonica import posiciones, tablas


# El orden en que se ofrecen las armónicas: primero las que Bruno tiene.
def tonalidades_ofrecidas():
    disponibles = list(tablas.TONALIDADES_DISPONIBLES)
    resto = [t for t in tablas.TONALIDADES if t not in disponibles]
    return disponibles + resto


def posiciones_ofrecidas():
    """
    Las doce posiciones, en su orden natural.

    NO las reordenamos poniendo primero las que Bruno estudia, aunque seria
    tentador. Motivo: si la 12a apareciera en el sexto renglon, tipear "12"
    seria ambiguo (la posicion 12 o el renglon 12?) y el menu elegiria mal.
    Manteniendo el orden, el numero de renglon ES el numero de posicion y no
    hay forma de equivocarse. Las que estudia se marcan con un texto.
    """
    return sorted(tablas.POSICIONES)


MODOS = [
    ("vivo", "Tocar con la pantalla en vivo"),
    ("afinador", "Practicar la afinacion de un bend"),
    ("teoria", "Consultar una escala, sin tocar"),
    ("archivo", "Transcribir una grabacion .wav"),
    ("calibrar", "Medir el ruido de fondo y ajustar el umbral"),
]


# =============================================================================
# La parte que decide (pura, testeable)
# =============================================================================

# Un valor propio para "no entendi lo que tecleaste".
#
# POR QUE NO ALCANZA CON None. Porque None ES una opcion valida: es "ninguna
# escala de referencia". Si usaramos None para las dos cosas, elegir "ninguna"
# haria que el menu creyera que no entendio y volviera a preguntar para
# siempre. Paso exactamente eso la primera vez que se probo el menu.
NO_ENTENDI = object()


def interpretar_respuesta(texto, opciones, por_defecto=None):
    """
    Convierte lo que el usuario tecleó en una de las opciones.

    Acepta tres formas de contestar, porque la gente escribe distinto:
      - el número de la lista        ("3")
      - el valor tal cual            ("blues_mayor")
      - Enter vacío                  -> el valor por defecto

    Devuelve la opción elegida, o NO_ENTENDI. No lanza error: devolver un valor
    deja que quien pregunta vuelva a preguntar, que es lo que uno espera de un
    menú.
    """
    texto = (texto or "").strip()

    if not texto:
        return por_defecto

    if texto.isdigit():
        numero = int(texto)

        # Con opciones NUMERICAS (las posiciones), el valor gana sobre el
        # numero de renglon. Si alguien tipea 12 queriendo la 12a posicion, no
        # puede terminar en la 11a porque la lista estaba en otro orden.
        if numero in opciones:
            return numero

        indice = numero - 1
        if 0 <= indice < len(opciones):
            return opciones[indice]
        return NO_ENTENDI

    # Comparación sin distinguir mayúsculas, salvo para las tonalidades donde
    # "C" y "c" son lo mismo pero "Bb" tiene que seguir siendo Bb.
    for opcion in opciones:
        if str(opcion).lower() == texto.lower():
            return opcion

    return NO_ENTENDI


def texto_de_opciones(opciones, etiquetas=None, por_defecto=None, columnas=4):
    """
    Arma el listado numerado de opciones, en varias columnas si son muchas.

    Marca la opción por defecto con un asterisco, para que se vea cuál sale al
    apretar Enter.
    """
    piezas = []
    for numero, opcion in enumerate(opciones, start=1):
        etiqueta = etiquetas[numero - 1] if etiquetas else str(opcion)
        marca = " *" if opcion == por_defecto else ""
        piezas.append(f"{numero:2}) {etiqueta}{marca}")

    if etiquetas or len(opciones) <= columnas:
        return "\n".join("  " + pieza for pieza in piezas)

    lineas = []
    for comienzo in range(0, len(piezas), columnas):
        fila = piezas[comienzo:comienzo + columnas]
        lineas.append("  " + "".join(f"{pieza:<16}" for pieza in fila).rstrip())
    return "\n".join(lineas)


def nombre_de_escala(clave):
    """El nombre lindo de una escala, o 'ninguna'."""
    if clave is None:
        return "ninguna"
    return tablas.NOMBRES_ESCALAS.get(clave, clave)


# =============================================================================
# La parte que pregunta (habla con la terminal)
# =============================================================================

def preguntar(titulo, opciones, etiquetas=None, por_defecto=None, columnas=4):
    """Muestra las opciones y devuelve la elegida. Insiste hasta entenderse."""
    print()
    print(titulo)
    print(texto_de_opciones(opciones, etiquetas, por_defecto, columnas))

    while True:
        sufijo = f" [{por_defecto}]" if por_defecto is not None else ""
        respuesta = input(f"  Elegi{sufijo}: ")
        elegida = interpretar_respuesta(respuesta, opciones, por_defecto)

        if elegida is not NO_ENTENDI:
            return elegida

        print("  No entendi. Pone el numero o el nombre.")


def preguntar_numero(titulo, por_defecto=None, minimo=None, maximo=None):
    """Pide un número, con valor por defecto y rango opcional."""
    while True:
        sufijo = f" [{por_defecto}]" if por_defecto is not None else ""
        respuesta = input(f"  {titulo}{sufijo}: ").strip()

        if not respuesta:
            return por_defecto

        try:
            valor = float(respuesta)
        except ValueError:
            print("  Tiene que ser un numero.")
            continue

        if minimo is not None and valor < minimo:
            print(f"  Tiene que ser {minimo} o mas.")
            continue
        if maximo is not None and valor > maximo:
            print(f"  Tiene que ser {maximo} o menos.")
            continue

        return valor


def preguntar_texto(titulo, por_defecto=""):
    sufijo = f" [{por_defecto}]" if por_defecto else ""
    respuesta = input(f"  {titulo}{sufijo}: ").strip()
    return respuesta or por_defecto


def preguntar_si_no(titulo, por_defecto=True):
    marca = "S/n" if por_defecto else "s/N"
    while True:
        respuesta = input(f"  {titulo} [{marca}]: ").strip().lower()
        if not respuesta:
            return por_defecto
        if respuesta in ("s", "si", "sí", "y", "yes"):
            return True
        if respuesta in ("n", "no"):
            return False
        print("  Contesta s o n.")


# =============================================================================
# El menú completo
# =============================================================================

def encabezado():
    print()
    print("=" * 72)
    print("  ARMONICA -> TABLATURA")
    print("=" * 72)


def elegir_modo():
    claves = [clave for clave, _ in MODOS]
    etiquetas = [descripcion for _, descripcion in MODOS]
    return preguntar("Que queres hacer?", claves, etiquetas, por_defecto="vivo")


def elegir_armonica():
    return preguntar("Que armonica tenes en la mano?",
                     tonalidades_ofrecidas(), por_defecto="C", columnas=6)


def elegir_posicion(tonalidad):
    opciones = posiciones_ofrecidas()
    etiquetas = []
    for numero in opciones:
        tono = posiciones.tonalidad_resultante(tonalidad, numero)
        marca = "" if numero in tablas.POSICIONES_CON_TABLA else "   (sin tabla escrita)"
        etiquetas.append(
            f"{tablas.NOMBRES_POSICIONES[numero]}  ->  tocas en {tono}{marca}"
        )
    return preguntar("En que posicion vas a tocar?", opciones, etiquetas,
                     por_defecto=2)


def elegir_escala():
    opciones = list(tablas.ESCALAS_INTERVALOS) + [None]
    etiquetas = [nombre_de_escala(clave) for clave in opciones]
    return preguntar("Que escala de referencia?", opciones, etiquetas,
                     por_defecto="blues")


def elegir_bpm():
    """
    Pregunta el BPM de la base, si es que hay una.

    Insiste en que lo sepa de verdad: estimarlo desde las notas es poco
    confiable, y sin un BPM correcto el analisis de ritmo no significa nada.
    """
    if not preguntar_si_no("Vas a tocar sobre una base?", por_defecto=False):
        return None, None

    print()
    print("  El BPM tiene que ser el de tu base, no una estimacion.")
    print("  En Band in a Box lo ves arriba a la derecha.")
    bpm = preguntar_numero("BPM", por_defecto=65, minimo=30, maximo=250)

    print()
    print("  Contra que figura medir el tiempo:")
    print("    1) negras          (una nota por pulso)")
    print("    2) corcheas        (dos por pulso, rectas)")
    print("    3) tresillos       (el swing del blues, estilos sw8)")
    print("    4) semicorcheas")
    subdivision = int(preguntar_numero("Subdivision",
                                       por_defecto=config.SUBDIVISION_RITMO,
                                       minimo=1, maximo=8))
    return bpm, subdivision


def elegir_bend_a_practicar(tonalidad):
    """
    Qué nota practicar en el modo afinador.

    Ofrece los bends de la armónica, que son las notas que de verdad se
    desafinan: una nota natural la da la lengüeta y sale sola.
    """
    from armonica import mapeo

    bends = []
    for agujero, cuantos in sorted(tablas.BENDS_ASPIRADOS.items()):
        for cantidad in range(1, cuantos + 1):
            bends.append("-" + str(agujero) + config.SIMBOLO_BEND * cantidad)
    for agujero, cuantos in sorted(tablas.BENDS_SOPLADOS.items()):
        for cantidad in range(1, cuantos + 1):
            bends.append(str(agujero) + config.SIMBOLO_BEND * cantidad)

    opciones = bends + [None]
    etiquetas = []
    for tablatura in bends:
        nota = mapeo.tab_a_nota(tablatura, tonalidad)
        etiquetas.append(f"{nota.como_tab()}  ({nota.nombre})")
    etiquetas.append("cualquiera (afinador libre)")

    elegida = preguntar("Que bend queres practicar?", opciones, etiquetas,
                        por_defecto="-3" + config.SIMBOLO_BEND * 2)

    if elegida is None:
        return None
    return mapeo.tab_a_nota(elegida, tonalidad)


def correr():
    """
    El menú completo. Devuelve un diccionario con lo elegido.

    main.py lo traduce a los mismos argumentos que aceptan las banderas, así
    que el menú y la línea de comandos terminan en el mismo código.
    """
    encabezado()

    eleccion = {"modo": elegir_modo()}

    if eleccion["modo"] == "calibrar":
        return eleccion

    eleccion["tonalidad"] = elegir_armonica()

    if eleccion["modo"] == "afinador":
        eleccion["objetivo"] = elegir_bend_a_practicar(eleccion["tonalidad"])
        return eleccion

    eleccion["posicion"] = elegir_posicion(eleccion["tonalidad"])
    eleccion["escala"] = elegir_escala()

    if eleccion["modo"] == "teoria":
        return eleccion

    if eleccion["modo"] == "archivo":
        eleccion["wav"] = preguntar_texto("Ruta del .wav")

    eleccion["bpm"], eleccion["subdivision"] = elegir_bpm()

    print()
    print("  " + posiciones.descripcion_completa(
        eleccion["tonalidad"], eleccion["posicion"], eleccion["escala"]
    ))

    return eleccion
