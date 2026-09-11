"""
posiciones.py — En qué tonalidad estás tocando, y qué agujeros forman la escala.

QUÉ ES UNA POSICIÓN

Una armónica diatónica está afinada en una tonalidad, pero se puede tocar en
otras. La "posición" es cuál de esas tonalidades estás usando.

Con una armónica en Do:
    1a posición  -> tocás en Do    (la tonalidad de la armónica)
    2a posición  -> tocás en Sol   (la del blues)
    3a posición  -> tocás en Re    (la menor)
    4a posición  -> tocás en La menor
    5a posición  -> tocás en Mi
    12a posición -> tocás en Fa    (la que estás estudiando)

No es magia ni un truco: es que la escala de Sol usa casi las mismas notas que
la de Do, y las que sobran salen con bends. Cada posición es un paso en el
círculo de quintas, que es exactamente lo que te explicó el profe el 28/07.

QUÉ HACE ESTE MÓDULO

Dos cosas, sobre las tablas ESCRITAS A MANO de tablas.py:
    - Calcular en qué tonalidad estás (tonalidad_resultante).
    - Decir qué agujeros forman una escala, y si un agujero pertenece a ella.

Solo sabe de las seis posiciones que tienen tabla explícita: 1a, 2a, 3a, 4a, 5a
y 12a. Para las otras seis está teoria.py, que las calcula.

Python puro: importa tablas, notas y mapeo. Nada de audio ni de pantalla.
"""

from armonica import mapeo, notas, tablas


def tonalidad_resultante(tonalidad_armonica, posicion):
    """
    En qué tonalidad estás tocando. ("C", 2) -> "G".

    La cuenta es una suma de semitonos y una vuelta al llegar a doce:
    la armónica en Do empieza en la clase 0, la 2a posición suma 7, y la clase 7
    es Sol.

    Devuelve solo el nombre de la nota, sin octava, porque una tonalidad es una
    nota en abstracto: "estás tocando en Sol", no "en el Sol de la cuarta octava".
    """
    _verificar_posicion(posicion)

    if tonalidad_armonica not in tablas.TONALIDADES:
        raise ValueError(
            f"No conozco la armonica en {tonalidad_armonica!r}. "
            f"Las que hay son: {', '.join(tablas.TONALIDADES)}"
        )

    clase_armonica = tablas.TONALIDADES[tonalidad_armonica] % 12
    clase_resultante = (clase_armonica + tablas.POSICIONES[posicion]) % 12

    return notas.nombre_de_clase(clase_resultante)


def nombre_de_posicion(posicion):
    """El nombre para mostrar en pantalla: 2 -> '2a posicion (cross harp)'."""
    _verificar_posicion(posicion)
    return tablas.NOMBRES_POSICIONES[posicion]


def descripcion_completa(tonalidad_armonica, posicion, escala=None):
    """
    Una línea lista para mostrar al empezar una sesión.

    Ejemplo: "Armonica en C, 2a posicion (cross harp) -> tocas en G. Escala de blues"

    Es lo que va a aparecer arriba de todo en la pantalla en vivo, para que no
    te olvides de en qué estás.
    """
    tono = tonalidad_resultante(tonalidad_armonica, posicion)
    texto = (
        f"Armonica en {tonalidad_armonica}, {nombre_de_posicion(posicion)} "
        f"-> tocas en {tono}"
    )
    if escala:
        texto += f". {tablas.NOMBRES_ESCALAS.get(escala, escala)}"
    return texto


def tiene_tabla_explicita(posicion):
    """
    Dice si esta posición tiene tabla escrita a mano.

    Las seis que Bruno trabaja con el profe la tienen. Las otras las calcula
    teoria.py. Sirve para que la app sepa a cuál de los dos módulos preguntarle.
    """
    return posicion in tablas.POSICIONES_CON_TABLA


def agujeros_de_escala(posicion, escala):
    """
    Los agujeros que forman una escala, como lista de tablaturas.

    Ejemplo: (2, "blues") -> ["1", "-1'", "-1", "-2''", "-2", "3", "-3'", ...]

    Vienen ordenados de grave a agudo y cubren los tres registros.

    IMPORTANTE: esta lista NO depende de la tonalidad de la armónica. En la
    afinación Richter, la escala de blues de 2a posición usa los mismos agujeros
    en una armónica en Do que en una en Sol. Cambia la nota que suena, no el
    agujero. Es la propiedad que hace que valga la pena aprender por posiciones
    y no por tonalidades, y es lo que el profe llama memorizar patrones
    repetibles de agujero.
    """
    _verificar_posicion(posicion)

    if escala not in tablas.ESCALAS_INTERVALOS:
        raise ValueError(
            f"No conozco la escala {escala!r}. "
            f"Las que hay son: {', '.join(tablas.ESCALAS_INTERVALOS)}"
        )

    clave = (posicion, escala)
    if clave not in tablas.ESCALAS_POR_POSICION:
        raise ValueError(
            f"No hay tabla explicita de {escala} para la {posicion}a posicion. "
            f"Las posiciones con tabla son: {tablas.POSICIONES_CON_TABLA}. "
            f"Para las otras, usa teoria.agujeros_para_escala()."
        )

    # Devolvemos una copia de la lista. Si devolviéramos la original, quien la
    # reciba podría modificarla sin querer y estaría corrompiendo la tabla para
    # todo el resto del programa.
    return list(tablas.ESCALAS_POR_POSICION[clave])


def notas_de_escala(tonalidad_armonica, posicion, escala):
    """
    Lo mismo que agujeros_de_escala, pero como objetos Nota.

    O sea con el agujero Y la nota que suena. Es lo que necesita la pantalla
    para mostrar "↓5 F5" en vez de solo "↓5".
    """
    tablaturas = agujeros_de_escala(posicion, escala)
    return [mapeo.tab_a_nota(t, tonalidad_armonica) for t in tablaturas]


def nota_en_escala(nota, tonalidad_armonica, posicion, escala):
    """
    ¿La nota que acabo de tocar pertenece a la escala de referencia?

    Es la pregunta que la pantalla hace en cada nota, para decidir si pintarla
    de verde o de amarillo.

    Compara por CLASE DE NOTA, ignorando la octava. Si la escala tiene un Fa,
    cualquier Fa está en la escala, en el registro que sea. Eso es lo correcto
    musicalmente y además evita un problema práctico: las tablas no siempre
    llegan hasta el agujero 10 en todos los registros.

    Acepta None (que es lo que devuelve el mapeo cuando no reconoció la nota) y
    en ese caso responde False, sin romperse.
    """
    if nota is None:
        return False

    clases = clases_de_escala(tonalidad_armonica, posicion, escala)
    return (nota.midi % 12) in clases


def clases_de_escala(tonalidad_armonica, posicion, escala):
    """
    Las clases de nota (0 a 11) que forman la escala.

    Se calcula desde los intervalos, no desde la tabla de agujeros. Son dos
    caminos al mismo lugar, y el test de teoria.py verifica que coincidan.
    """
    _verificar_posicion(posicion)

    if escala not in tablas.ESCALAS_INTERVALOS:
        raise ValueError(f"No conozco la escala {escala!r}")

    clase_armonica = tablas.TONALIDADES[tonalidad_armonica] % 12
    clase_tonica = (clase_armonica + tablas.POSICIONES[posicion]) % 12

    return {
        (clase_tonica + intervalo) % 12
        for intervalo in tablas.ESCALAS_INTERVALOS[escala]
    }


def nombres_de_escala(tonalidad_armonica, posicion, escala):
    """
    Los nombres de las notas de la escala, en orden desde la tónica.

    Ejemplo: ("C", 12, "pentatonica_mayor") -> ["F", "G", "A", "C", "D"]

    Es lo que muestra el modo teoría cuando le preguntás qué notas tiene una
    escala, sin hablar todavía de agujeros.
    """
    _verificar_posicion(posicion)

    clase_armonica = tablas.TONALIDADES[tonalidad_armonica] % 12
    clase_tonica = (clase_armonica + tablas.POSICIONES[posicion]) % 12

    return [
        notas.nombre_de_clase((clase_tonica + intervalo) % 12)
        for intervalo in tablas.ESCALAS_INTERVALOS[escala]
    ]


def _verificar_posicion(posicion):
    """Un chequeo que se repite en varias funciones, escrito una sola vez."""
    if posicion not in tablas.POSICIONES:
        raise ValueError(
            f"La posicion {posicion!r} no existe. Van de la 1 a la 12."
        )
