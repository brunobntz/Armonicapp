"""
tablas.py — SOLO DATOS. Todo el conocimiento musical de la armónica, en tablas.

Este módulo no tiene lógica: son diccionarios y listas. Es a propósito.

¿Por qué? Porque si algún día querés llevar esta app a JavaScript (web) o a Swift
(iPhone), este archivo se traduce copiando y pegando: son solo números y textos.
Toda la lógica que los usa vive en otros módulos. Este archivo no importa NADA.

Cómo leer las tablas: casi todo está expresado en SEMITONOS DESDE LA RAÍZ de la
armónica, no en notas absolutas. La raíz es la nota del agujero 1 soplado.
Ejemplo: el agujero 4 soplado está a 12 semitonos de la raíz (una octava arriba).
En una armónica en C eso es C5; en una armónica en G, G4. La tabla es la misma.

Esa es la decisión de diseño más importante del archivo: una sola tabla de
afinación sirve para las 12 tonalidades de armónica.
"""

# =============================================================================
# 1. TONALIDADES DE ARMÓNICA
# =============================================================================

# Nota MIDI del agujero 1 SOPLADO para cada tonalidad de armónica diatónica.
# (En MIDI, C4 = 60 = el Do central del piano. Cada unidad es un semitono.)
#
# Las armónicas diatónicas estándar cubren un rango contiguo: la más grave es la
# de G (G3 = 196 Hz) y la más aguda la de F# (F#4). Por eso los números van
# seguidos del 55 al 66. Agregar una tonalidad nueva es agregar UNA línea acá.
#
# Bruno tiene C, G, D y A. Las otras están incluidas porque el dato es el mismo
# y no cuesta nada, pero solo esas cuatro se van a probar con armónica real.
TONALIDADES = {
    "G": 55,   # G3  — la más grave de las estándar
    "Ab": 56,
    "A": 57,   # A3
    "Bb": 58,
    "B": 59,
    "C": 60,   # C4  — la más común, la que casi todos aprenden primero
    "Db": 61,
    "D": 62,   # D4
    "Eb": 63,
    "E": 64,
    "F": 65,
    "F#": 66,  # F#4 — la más aguda de las estándar
}

# Las cuatro que Bruno tiene físicamente. Se usa para sugerir armónicas
# en el modo de detección de tonalidad (paso 9 del plan).
TONALIDADES_DISPONIBLES = ["C", "G", "D", "A"]


# =============================================================================
# 2. AFINACIÓN RICHTER — el mapa de la armónica
# =============================================================================

# Semitonos desde la raíz para cada agujero SOPLADO, del 1 al 10.
# En una armónica en C esto da:  C4 E4 G4 C5 E5 G5 C6 E6 G6 C7
# Fijate el patrón: es un acorde mayor (do-mi-sol) repetido en tres octavas.
# Por eso soplando todos los agujeros a la vez suena un acorde mayor afinado:
# es el truco central del diseño Richter, pensado para acompañar canciones.
AFINACION_SOPLADO = [0, 4, 7, 12, 16, 19, 24, 28, 31, 36]

# Lo mismo para los agujeros ASPIRADOS.
# En una armónica en C:  D4 G4 B4 D5 F5 A5 B5 D6 F6 A6
# Acá el patrón NO es regular, y esa irregularidad es lo que hace difícil
# la armónica y a la vez lo que la hace sonar a blues.
AFINACION_ASPIRADO = [2, 7, 11, 14, 17, 21, 23, 26, 29, 33]

# ¿Por qué los agujeros 1-6 se aspiran para hacer bends y los 8-10 se soplan?
# Un bend baja la nota hacia la otra nota del mismo agujero. Solo se puede bajar
# la nota MÁS AGUDA de las dos hacia la más grave.
#   - Agujeros 1 a 6: el aspirado es más agudo que el soplado -> se dobla aspirando.
#   - Agujeros 7 a 10: el soplado es más agudo que el aspirado -> se dobla soplando.
#   - El agujero 7 tiene las dos notas a un semitono: no hay lugar para doblar.
# Cuántos semitonos podés bajar depende de cuánto espacio hay entre las dos notas.

# Cuántos semitonos se puede bajar cada agujero ASPIRADO.
# Clave = número de agujero, valor = cantidad de bends disponibles.
# Los agujeros que no aparecen (5, 7, 8, 9, 10) no tienen bend aspirado.
BENDS_ASPIRADOS = {
    1: 1,   # Db4 en armónica de C
    2: 2,   # Gb4 y F4
    3: 3,   # Bb4, A4 y Ab4  — los tres que el profe enumeró el 28/07
    4: 1,   # Db5
    6: 1,   # Ab5
}

# Cuántos semitonos se puede bajar cada agujero SOPLADO.
BENDS_SOPLADOS = {
    8: 1,    # Eb6 en armónica de C
    9: 1,    # Gb6
    10: 2,   # B6 y Bb6
}

# Sobre el TERCER BEND DEL 3 (el "-3'''", Ab4 en una armónica de C).
# Al principio quedó afuera porque el pedido original hablaba de medio tono y
# un tono nada más. Fue un error: el profe lo enseña explícitamente el 28/07
# ("1º bend: Bb, 2º bend: A, 3º bend: Ab") y ese Lab es una nota de verdad:
# la tercera menor de Fa, o sea la blue note de la 12a posición, y la tónica
# de la 4a. Sin él, media escala de blues quedaba sin su nota característica
# en el registro grave. Está incluido desde 2026-09-02.
#
# Es el bend más difícil de la armónica, y encima el agujero 3 de tu Crossover
# tiene fuga de aire. Que la app lo muestre no significa que salga fácil: para
# eso está el medidor de cents, que te va a decir cuán cerca del Lab llegaste.

# FUERA DE ALCANCE EN V1 (documentado para no olvidarlo):
#   - El bend del 5 aspirado: es de un cuarto de tono, no llega a semitono.
#     No se puede representar en esta notación.
#   - Los overblows y overdraws (que SUBEN la nota). Requieren otra tabla.
#     Son los que te faltan para el Sib del registro medio (↑6°) y el Mib (↑4°).


# =============================================================================
# 3. POSICIONES — en qué tonalidad estás tocando realmente
# =============================================================================

# Cuántos semitonos hay que sumarle a la tonalidad de la armónica para obtener
# la tonalidad en la que estás tocando.
#
# Ejemplo: armónica en C, 2a posición -> 60 + 7 = 67 -> estás tocando en G.
#
# Los números no son arbitrarios: cada posición es un paso en el círculo de
# quintas. La fórmula es  (posicion - 1) * 7  módulo 12.  La escribimos igual
# como tabla explícita porque es más fácil de leer y de portar, y hay un test
# que verifica que la tabla coincide con la fórmula.
POSICIONES = {
    1: 0,    # straight harp — la tonalidad de la armónica
    2: 7,    # cross harp — la del blues. Armónica en C -> tocás en G
    3: 2,    # slant harp — la menor. Armónica en C -> tocás en D
    4: 9,
    5: 4,
    6: 11,
    7: 6,
    8: 1,
    9: 8,
    10: 3,
    11: 10,
    12: 5,   # armónica en C -> tocás en F
}

# Posiciones que tienen tabla explícita de escalas en agujeros (más abajo).
# Son las seis que Bruno trabaja con el profe. Las otras seis las cubre teoria.py
# por cálculo, sin tabla escrita a mano.
POSICIONES_CON_TABLA = [1, 2, 3, 4, 5, 12]

# Nombres para mostrar en pantalla.
# Nota de vocabulario: el profe usa siempre el ordinal ("4a posicion") y nunca
# dice "cruzada" ni "straight harp". Los apodos en inglés van entre paréntesis
# solo como referencia, porque aparecen en todos los métodos.
NOMBRES_POSICIONES = {
    1: "1a posicion (straight harp)",
    2: "2a posicion (cross harp)",
    3: "3a posicion (slant harp)",
    4: "4a posicion",
    5: "5a posicion",
    6: "6a posicion",
    7: "7a posicion",
    8: "8a posicion",
    9: "9a posicion",
    10: "10a posicion",
    11: "11a posicion",
    12: "12a posicion",
}


# =============================================================================
# 4. ESCALAS — como intervalos (sirven para cualquier tonalidad)
# =============================================================================

# Semitonos desde la tónica de la escala.
# Estos son los ladrillos con los que teoria.py (paso 3) va a poder calcular
# cualquier escala en cualquiera de las 12 posiciones.
ESCALAS_INTERVALOS = {
    # Do Re Mi Sol La — suena alegre, folk, country. Sin semitonos: no puede
    # sonar "mal" sobre un acorde mayor, por eso es la primera que se enseña.
    "pentatonica_mayor": [0, 2, 4, 7, 9],

    # Do Mib Fa Sol Sib — la escala del rock y del blues.
    "pentatonica_menor": [0, 3, 5, 7, 10],

    # La pentatónica menor + la "blue note" (quinta bemol). Esa nota extra es
    # la que da la tensión característica del blues.
    # También se la llama "escala de blues menor" para distinguirla de la de abajo.
    "blues": [0, 3, 5, 6, 7, 10],

    # ESCALA DE BLUES MAYOR: la pentatónica mayor con la tercera menor metida
    # adentro. Los grados son 1, 2, b3, 3, 5, 6.
    #
    # Es la escala que Bruno trabaja en 12a posición con el estudio de Carlos
    # del Junco. La gracia está en que tiene las DOS terceras, la menor y la
    # mayor, pegadas: pasar de una a la otra es el sonido más característico
    # del blues, y es el "sabor" del que habló el profe el 04/08.
    #
    # No es lo mismo que la escala de blues de arriba, aunque las dos se llamen
    # blues. En Fa: esta da F G Ab A C D, la otra da F Ab Bb B C Eb.
    #
    # Se puede pensar de dos maneras, y las dos son la misma escala:
    #   - pentatónica MAYOR de Fa (F G A C D) + el Lab
    #   - pentatónica MENOR de Re (D F G A C) + el Lab, o sea la relativa menor
    # Por eso el profe dice "escala de blues de Re menor sobre el acorde de Fa"
    # y a la vez "el 1 soplado es la 5a": las dos frases describen esto mismo.
    "blues_mayor": [0, 2, 3, 4, 7, 9],
}

# Nombres para mostrar en pantalla.
NOMBRES_ESCALAS = {
    "pentatonica_mayor": "Pentatonica mayor",
    "pentatonica_menor": "Pentatonica menor",
    "blues": "Escala de blues (menor)",
    "blues_mayor": "Escala de blues mayor",
}


# =============================================================================
# 4b. ACORDES — como intervalos, igual que las escalas
# =============================================================================

# Un acorde es un puñado de notas que suenan juntas; un ARPEGIO es ese mismo
# acorde tocado nota por nota. En la armónica siempre tocamos arpegios, porque
# aislamos un agujero por vez.
#
# Se describen igual que las escalas: semitonos desde la raíz del acorde. Por
# eso el mismo motor que calcula escalas calcula arpegios, sin cambiar nada.
ACORDES_INTERVALOS = {
    # Do Mi Sol. El acorde alegre de siempre.
    "mayor": [0, 4, 7],

    # Do Mib Sol. La tercera baja medio tono y cambia el carácter.
    "menor": [0, 3, 7],

    # Do Mi Sol Sib. EL ACORDE DEL BLUES. Es un acorde mayor con la séptima
    # menor encima, y esa combinación es inestable: pide resolver. Todo el
    # blues de doce compases está hecho de estos tres.
    "dominante": [0, 4, 7, 10],

    # Do Mib Sol Sib. El de "Minor Swing" y del blues menor.
    "menor7": [0, 3, 7, 10],

    # Do Mi Sol Si. Suena a bossa, no a blues.
    "mayor7": [0, 4, 7, 11],

    # Do Mib Solb La. El acorde disminuido del compás 7 del blues de dieciséis
    # que trabajaste el 14/04.
    "disminuido7": [0, 3, 6, 9],
}

NOMBRES_ACORDES = {
    "mayor": "mayor",
    "menor": "menor",
    "dominante": "dominante (7)",
    "menor7": "menor 7",
    "mayor7": "mayor 7",
    "disminuido7": "disminuido 7",
}

# Cómo se llama cada intervalo, para poder decir "esta nota es la 7a del acorde"
# en vez de "esta nota está a 10 semitonos".
NOMBRES_GRADOS = {
    0: "tonica",
    1: "9a menor",
    2: "9a",
    3: "3a menor",
    4: "3a mayor",
    5: "4a",
    6: "5a bemol",
    7: "5a",
    8: "5a aumentada",
    9: "6a",
    10: "7a menor",
    11: "7a mayor",
}

# LAS NOTAS GUIA de un acorde dominante son su tercera y su séptima.
#
# Por qué esas dos y no la tónica: la tónica y la quinta no dicen nada, están
# en casi todos los acordes. La tercera dice si es mayor o menor, y la séptima
# es la que lo hace dominante. Tocando esas dos ya se escucha el acorde.
#
# Es el concepto central de lo que el profe te viene enseñando desde agosto:
# aterrizar en una nota guía en el tiempo 1 del cambio.
GRADOS_GUIA = [3, 4, 10, 11]

# El blues de doce compases: qué grado suena en cada compás.
#   I = la tónica, IV = la cuarta (+5 semitonos), V = la quinta (+7)
# Es la progresión de tu base de Band in a Box, la misma del estudio de Carlos
# del Junco: Fa7 Sib7 Fa7 Fa7 Sib7 Sib7 Fa7 Fa7 Do7 Sib7 Fa7 Do7
BLUES_DOCE_COMPASES = ["I", "IV", "I", "I", "IV", "IV",
                       "I", "I", "V", "IV", "I", "V"]

# Cuántos semitonos por encima de la tónica está cada grado de la progresión.
GRADOS_DE_LA_PROGRESION = {"I": 0, "IV": 5, "V": 7}


# =============================================================================
# 5. ESCALAS POR POSICIÓN — tablas explícitas, en agujeros
# =============================================================================

# Acá está el conocimiento práctico: qué agujeros tocar para cada escala en cada
# posición. Están escritas a mano, agujero por agujero, y NO se calculan.
#
# Por qué explícitas y no calculadas: es lo que pediste, y tiene una ventaja real.
# Estas tablas son verificables leyéndolas contra cualquier método de armónica.
# En el paso 3 vamos a escribir teoria.py, que SÍ las calcula, y un test que
# compara las dos. Si difieren, una de las dos tiene un error y lo encontramos.
# Dos fuentes independientes que se validan entre sí.
#
# Notación de la tablatura (la estándar de armónica):
#   "4"     = agujero 4 soplado
#   "-4"    = agujero 4 aspirado (el guión significa aspirar)
#   "-3'"   = agujero 3 aspirado con bend de medio tono
#   "-3''"  = agujero 3 aspirado con bend de un tono
#   "8'"    = agujero 8 soplado con bend de medio tono
#
# Las listas están ordenadas de grave a agudo, y cubren los tres registros de la
# armónica (grave, medio, agudo).
#
# IMPORTANTE: estas tablas NO dependen de la tonalidad de la armónica. En la
# afinación Richter, la 2a posición usa los mismos agujeros en una armónica en C
# que en una en G. Cambia la nota que suena, no el agujero. Por eso una sola
# tabla por (posición, escala) alcanza.
#
# Nota sobre repeticiones: vas a ver "-2" y "3" juntos. En la armónica esas dos
# formas dan exactamente la misma nota (G4 en una armónica en C). Las dos son
# válidas para tocar la escala, así que las dos aparecen.

ESCALAS_POR_POSICION = {
    # -------------------------------------------------------------------------
    # 1a POSICIÓN — la tonalidad de la armónica. Armónica en C -> tocás en C.
    # -------------------------------------------------------------------------
    (1, "pentatonica_mayor"): [
        "1", "-1", "2", "-2", "3", "-3''", "4", "-4", "5",
        "6", "-6", "7", "-8", "8", "9", "-10", "10",
    ],
    (1, "pentatonica_menor"): [
        # OJO: en 1a posición esta escala tiene huecos. Faltan la tercera menor
        # grave y media (Eb4 y Eb5) y la séptima menor media (Bb5): esas notas
        # necesitan overblow, que no está en V1. Por eso casi nadie toca menor
        # en 1a posición. Se muestra igual, con sus huecos, para que se vea.
        "1", "-2''", "-2", "3", "-3'", "4", "-5", "6",
        "7", "8'", "-9", "9", "10''", "10",
    ],
    (1, "blues"): [
        "1", "-2''", "-2'", "-2", "3", "-3'", "4", "-5", "6",
        "7", "8'", "-9", "9'", "9", "10''", "10",
    ],
    (1, "blues_mayor"): [
        # C D Eb E G A — la pentatonica mayor de Do con la tercera menor
        "1", "-1", "2", "-2", "3", "-3''", "4", "-4", "5", "6", "-6", "7", "-8",
        "8'", "8", "9", "-10", "10",
    ],

    # -------------------------------------------------------------------------
    # 2a POSICIÓN — la del blues. Armónica en C -> tocás en G.
    # Es la más usada de todas: la armónica "cae" naturalmente en esta tonalidad.
    # -------------------------------------------------------------------------
    (2, "pentatonica_mayor"): [
        "-1", "2", "-2", "3", "-3''", "-3", "-4", "5",
        "6", "-6", "-7", "-8", "8", "9", "-10", "10'",
    ],
    (2, "pentatonica_menor"): [
        # Esta es LA escala del blues de armónica. Casi todo se puede tocar
        # sin overblows; solo falta Bb5 en el registro medio.
        "1", "-1", "-2''", "-2", "3", "-3'", "4", "-4", "-5",
        "6", "7", "-8", "-9", "9", "10''", "10",
    ],
    (2, "blues"): [
        # La misma que arriba más la blue note (Db en G): "-1'" y "-4'".
        # Los dos son bends ASPIRADOS: en los agujeros 1 al 6 se dobla aspirando.
        # El clásico riff de blues sale de acá: -2 -3' 4 -4' -4 -5 6
        "1", "-1'", "-1", "-2''", "-2", "3", "-3'", "4", "-4'", "-4", "-5",
        "6", "7", "-8", "-9", "9", "10''", "10",
    ],
    (2, "blues_mayor"): [
        # G A Bb B D E — el sonido clasico del blues de 2a: las dos terceras
        # pegadas, "-3'" (Sib) y "-3" (Si). Alternar entre ellas es el "sabor"
        # del que hablo el profe el 04/08.
        "-1", "2", "-2", "3", "-3''", "-3'", "-3", "-4", "5", "6", "-6", "-7",
        "-8", "8", "9", "-10", "10''", "10'",
    ],

    # -------------------------------------------------------------------------
    # 3a POSICIÓN — la menor. Armónica en C -> tocás en D.
    # La favorita para tocar en tono menor sin cambiar de armónica.
    # -------------------------------------------------------------------------
    (3, "pentatonica_mayor"): [
        "-1", "2", "-2'", "-3''", "-3", "-4", "5",
        "-6", "-7", "-8", "8", "9'", "-10", "10'",
    ],
    (3, "pentatonica_menor"): [
        # Muy cómoda: sale casi entera con notas naturales y un solo bend.
        "1", "-1", "-2''", "-2", "3", "-3''", "4", "-4", "-5",
        "6", "-6", "7", "-8", "-9", "9", "-10", "10",
    ],
    (3, "blues"): [
        # La blue note en 3a posición (Ab en una armónica de C) solo se consigue
        # en "-6'", el agujero 6 aspirado con medio bend.
        # En el registro grave sería el tercer bend del 3, que no está en V1,
        # y en el agudo haría falta un overblow. Por eso aparece una sola vez.
        "1", "-1", "-2''", "-2", "3", "-3'''", "-3''", "4", "-4", "-5",
        "6", "-6'", "-6", "7", "-8", "-9", "9", "-10", "10",
    ],
    (3, "blues_mayor"): [
        # D E F Gb A B
        "-1", "2", "-2''", "-2'", "-3''", "-3", "-4", "5", "-5", "-6", "-7",
        "-8", "8", "-9", "9'", "-10", "10'",
    ],

    # -------------------------------------------------------------------------
    # 4a POSICIÓN — la menor relativa de la 1a. Armónica en C -> tocás en A.
    # Es la que usaste para "Minor Swing" (Am) y para el tema del profe.
    # Su tónica es el agujero 3 aspirado con bend de un tono, o sea "-3''":
    # justo el agujero que tenés con fuga de aire.
    # -------------------------------------------------------------------------
    (4, "pentatonica_mayor"): [
        # A B Db E Gb — pide muchos bends, es la menos cómoda de las tres
        # (Gb y Db del registro medio necesitan overblow, fuera de V1)
        "-1'", "2", "-2'", "-3''", "-3", "-4'", "5", "-6", "-7", "8", "9'",
        "-10", "10'",
    ],
    (4, "pentatonica_menor"): [
        # A C D E G — esta sale entera sin overblows y con un solo bend
        "1", "-1", "2", "-2", "3", "-3''", "4", "-4", "5", "6", "-6", "7", "-8",
        "8", "9", "-10", "10",
    ],
    (4, "blues"): [
        # A C D Eb E G — la blue note (Eb) solo aparece arriba, en "8'"
        # (los Eb grave y medio necesitan overblow, fuera de V1)
        "1", "-1", "2", "-2", "3", "-3''", "4", "-4", "5", "6", "-6", "7", "-8",
        "8'", "8", "9", "-10", "10",
    ],
    (4, "blues_mayor"): [
        # A B C Db E Gb
        "1", "-1'", "2", "-2'", "-3''", "-3", "4", "-4'", "5", "-6", "-7", "7",
        "8", "9'", "-10", "10'", "10",
    ],

    # -------------------------------------------------------------------------
    # 5a POSICIÓN — Armónica en C -> tocás en E. La usaste para el E7 de
    # "Minor Swing". Su tónica es el 2 soplado.
    # -------------------------------------------------------------------------
    (5, "pentatonica_mayor"): [
        # E Gb Ab B Db — muy incómoda, casi todo pide bend u overblow
        "-1'", "2", "-2'", "-3'''", "-3", "-4'", "5", "-6'", "-7", "8", "9'", "10'",
    ],
    (5, "pentatonica_menor"): [
        # E G A B D — cómoda, sin overblows
        "-1", "2", "-2", "3", "-3''", "-3", "-4", "5", "6", "-6", "-7", "-8",
        "8", "9", "-10", "10'",
    ],
    (5, "blues"): [
        # E G A Bb B D
        "-1", "2", "-2", "3", "-3''", "-3'", "-3", "-4", "5", "6", "-6", "-7",
        "-8", "8", "9", "-10", "10''", "10'",
    ],
    (5, "blues_mayor"): [
        # E Gb G Ab B Db
        "-1'", "2", "-2'", "-2", "3", "-3'''", "-3", "-4'", "5", "6", "-6'",
        "-7", "8", "9'", "9", "10'",
    ],

    # -------------------------------------------------------------------------
    # 12a POSICIÓN — Armónica en C -> tocás en F. Es lo que estás trabajando
    # ahora, con el estudio de Carlos del Junco sobre el blues en Fa.
    # Su tónica es el 5 aspirado.
    #
    # El dato que hace amable a esta posición: la pentatónica mayor de Fa sale
    # ENTERA del agujero 4 al 10 sin un solo bend. Once notas seguidas de aire
    # natural. Por eso el profe te empuja a la pentatónica y no a la escala
    # mayor completa, que sí pide el Sib (el primer bend del 3, o el overblow
    # del 6).
    # -------------------------------------------------------------------------
    (12, "pentatonica_mayor"): [
        # F G A C D — del "4" en adelante no hay ningún bend
        "1", "-1", "-2''", "-2", "3", "-3''", "4", "-4", "-5", "6", "-6", "7",
        "-8", "-9", "9", "-10", "10",
    ],
    (12, "pentatonica_menor"): [
        # F Ab Bb C Eb — mucho más cara: el Ab del medio es "-6'" y el Bb "-3'"
        # (Eb, Ab y Bb de varios registros necesitan overblow, fuera de V1)
        "1", "-2''", "-3'''", "-3'", "4", "-5", "-6'", "7", "8'", "-9", "10''", "10",
    ],
    (12, "blues"): [
        # F Ab Bb B C Eb — el B (la quinta bemol de Fa) sale sin bend en "-7"
        # y en "-3". Es la nota azul regalada de la 12a posición.
        "1", "-2''", "-3'''", "-3'", "-3", "4", "-5", "-6'", "-7", "7", "8'", "-9",
        "10''", "10'", "10",
    ],
    (12, "blues_mayor"): [
        # F G Ab A C D — ESTA es la que Bruno trabaja con el estudio de Carlos
        # del Junco. Tiene las dos terceras de Fa pegadas: el tercer bend del 3
        # (Lab) y el segundo (La) abajo, y "-6'" (Lab) contra "-6" (La) en el
        # registro central. Pasar de una a la otra es el sonido de la 12a.
        #
        # La corrida de dos octavas desde la tonica sale asi:
        #   -2''  -2  -3'''  -3''  4  -4  -5  6  -6'  -6  7  -8  -9
        "1", "-1", "-2''", "-2", "3", "-3'''", "-3''", "4", "-4", "-5", "6",
        "-6'", "-6", "7", "-8", "-9", "9", "-10", "10",
    ],
}


# =============================================================================
# 6. NOMBRES DE NOTAS
# =============================================================================

# Usamos bemoles y no sostenidos porque en el mundo de la armónica y del blues
# se habla en bemoles: "armónica en Bb", "la tercera bemol", "Eb". La única
# excepción es F#, que es como se vende esa armónica.
# El índice de la lista es la clase de nota (0 = C, 1 = Db, ... 11 = B).
NOMBRES_NOTAS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# Versión con sostenidos, por si alguna vez hace falta mostrarla así.
NOMBRES_NOTAS_SOSTENIDOS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Nota de referencia universal: el La de la orquesta, 440 Hz, es el MIDI 69.
MIDI_LA_REFERENCIA = 69
FRECUENCIA_LA_REFERENCIA = 440.0
