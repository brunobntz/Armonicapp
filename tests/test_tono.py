"""
Tests de armonica/tono.py — el detector de tono YIN.

Sin micrófono: todo el audio se genera acá dentro, con frecuencias que
elegimos nosotros. Esa es la gracia, porque sabemos la respuesta correcta y
podemos medir el error exacto del detector.

Cómo correrlos:   python -m pytest tests/test_tono.py -v
"""

import numpy as np
import pytest

import config
from armonica import notas, tono
from herramientas import generar_wav


FS = 44100
TAMANO = 2048


def seno(frecuencia_hz, cantidad=TAMANO, frecuencia_muestreo=FS, amplitud=0.5):
    """Una onda senoidal pura, el caso más fácil posible para el detector."""
    tiempo = np.arange(cantidad) / frecuencia_muestreo
    return amplitud * np.sin(2 * np.pi * frecuencia_hz * tiempo)


def bloque_de_nota(nombre_nota):
    """
    Un bloque tomado del MEDIO de una nota con timbre de armónica.

    Lo sacamos del medio a propósito: los bordes tienen el ataque y la caída,
    donde el volumen cambia y la detección es naturalmente peor.
    """
    frecuencia = notas.midi_a_frecuencia(notas.nombre_a_midi(nombre_nota))
    onda = generar_wav.generar_nota(frecuencia, 0.3)
    medio = len(onda) // 2
    return onda[medio:medio + TAMANO]


def error_en_cents(frecuencia_detectada, nombre_nota):
    """Cuánto se equivocó el detector, medido en cents."""
    return notas.desviacion_cents(
        frecuencia_detectada, notas.nombre_a_midi(nombre_nota)
    )


# =============================================================================
# Lo básico: ondas puras
# =============================================================================

def test_detecta_el_la_de_440():
    """El caso de referencia de todo el sistema."""
    frecuencia, confianza = tono.detectar_frecuencia(seno(440.0), FS)
    assert frecuencia == pytest.approx(440.0, abs=1.0)
    assert confianza > 0.9


def test_detecta_la_nota_mas_grave_que_vamos_a_necesitar():
    """
    G3 = 196 Hz es el agujero 1 soplado de una armónica en Sol, la nota más
    grave de todo el instrumental de Bruno.
    """
    frecuencia, _ = tono.detectar_frecuencia(seno(196.0), FS)
    assert frecuencia == pytest.approx(196.0, abs=1.0)


def test_detecta_la_nota_mas_aguda_que_vamos_a_necesitar():
    """
    C7 = 2093 Hz es el agujero 10 soplado de una armónica en Do.
    Acá la precisión es menor porque el período dura solo 21 muestras, pero
    tiene que seguir cayendo bien dentro del semitono.
    """
    frecuencia, _ = tono.detectar_frecuencia(seno(2093.0), FS)
    assert frecuencia == pytest.approx(2093.0, rel=0.01)


def test_la_precision_alcanza_para_el_medidor_de_afinacion():
    """
    Un semitono son 100 cents. Para que el medidor sirva, el error propio del
    detector tiene que ser mucho menor que lo que queremos medir.

    Exigimos menos de 5 cents en todo el rango. Un oído entrenado empieza a
    notar diferencias alrededor de los 10.
    """
    for nombre in ["G3", "C4", "A4", "C5", "A5", "C6", "A6", "C7"]:
        frecuencia = notas.midi_a_frecuencia(notas.nombre_a_midi(nombre))
        detectada, _ = tono.detectar_frecuencia(seno(frecuencia), FS)
        assert abs(error_en_cents(detectada, nombre)) < 5.0, (
            f"En {nombre} el detector se equivoca demasiado"
        )


# =============================================================================
# LO IMPORTANTE: los armónicos y el error de octava
# =============================================================================

def test_detecta_bien_un_sonido_con_armonicos():
    """
    Una armónica real no produce una onda pura: produce la nota más sus
    armónicos. Este test usa el timbre sintético que imita eso.
    """
    bloque = bloque_de_nota("A4")
    frecuencia, confianza = tono.detectar_frecuencia(bloque, FS)
    assert frecuencia == pytest.approx(440.0, abs=1.0)
    assert confianza > 0.8


def test_no_se_confunde_de_octava_aunque_el_armonico_suene_mas_fuerte():
    """
    ESTE ES EL TEST QUE JUSTIFICA USAR YIN.

    Armamos una señal donde el segundo armónico (880 Hz) suena al DOBLE de
    volumen que la nota fundamental (440 Hz). Un detector basado en la
    transformada de Fourier miraría cuál es la frecuencia más fuerte y
    respondería 880: una octava de más. Es el error clásico de los afinadores
    baratos.

    YIN no mira intensidades: mira cada cuánto se repite la onda. La onda
    completa sigue repitiéndose 440 veces por segundo, así que responde 440.
    """
    tiempo = np.arange(TAMANO) / FS
    senal = (
        0.3 * np.sin(2 * np.pi * 440.0 * tiempo)      # la nota, floja
        + 0.6 * np.sin(2 * np.pi * 880.0 * tiempo)    # el armónico, fuerte
        + 0.2 * np.sin(2 * np.pi * 1320.0 * tiempo)
    )
    frecuencia, _ = tono.detectar_frecuencia(senal, FS)
    assert frecuencia == pytest.approx(440.0, abs=2.0)


def test_tampoco_se_va_una_octava_para_abajo():
    """
    El otro error de octava: reportar 220 en vez de 440. Pasa cuando el
    detector elige un tau que es el doble del período verdadero, porque una
    onda que se repite cada 100 muestras también se repite cada 200.

    Lo evita el paso 3 de YIN, que se queda con el PRIMER mínimo y no con el
    más profundo.
    """
    for frecuencia_real in [220.0, 440.0, 880.0]:
        detectada, _ = tono.detectar_frecuencia(seno(frecuencia_real), FS)
        assert detectada == pytest.approx(frecuencia_real, rel=0.02)


# =============================================================================
# Cuándo tiene que decir "no sé"
# =============================================================================

def test_el_ruido_no_produce_ninguna_nota():
    """
    Ruido blanco: sonido sin frecuencia definida. Si el detector devolviera algo
    acá, la app inventaría notas cada vez que pasa un camión por la calle.
    """
    ruido = generar_wav.generar_ruido(0.1, FS, volumen=0.3)
    frecuencia, _ = tono.detectar_frecuencia(ruido[:TAMANO], FS)
    assert frecuencia is None


def test_el_silencio_no_produce_ninguna_nota():
    frecuencia, confianza = tono.detectar_frecuencia(np.zeros(TAMANO), FS)
    assert frecuencia is None
    assert confianza == 0.0


def test_una_frecuencia_por_debajo_del_rango_se_descarta():
    """
    100 Hz está debajo de cualquier armónica diatónica. Acotar el rango es la
    defensa más efectiva contra los errores de octava.
    """
    frecuencia, _ = tono.detectar_frecuencia(seno(100.0), FS)
    assert frecuencia is None


def test_una_frecuencia_por_encima_del_rango_se_descarta():
    frecuencia, _ = tono.detectar_frecuencia(seno(4000.0), FS)
    assert frecuencia is None


def test_un_bloque_demasiado_corto_no_rompe():
    """
    La ventana tiene que contener al menos dos repeticiones de la nota más
    grave. Si es más corta, devolvemos None en vez de explotar.
    """
    frecuencia, _ = tono.detectar_frecuencia(seno(440.0, cantidad=100), FS)
    assert frecuencia is None


def test_dos_notas_juntas_dan_baja_confianza_o_nada():
    """
    YIN es monofónico: está pensado para una nota por vez. Si tocás dos
    agujeros juntos, la señal deja de ser periódica y el detector lo nota.

    Este test documenta la limitación. También es la razón por la que la base
    de Band in a Box tiene que ir por auriculares: con bajo, batería y piano
    entrando por el micrófono, el detector no tiene nada que hacer.
    """
    tiempo = np.arange(TAMANO) / FS
    # Do y Fa# a la vez, el intervalo más disonante que existe.
    dos_notas = 0.4 * np.sin(2 * np.pi * 261.63 * tiempo) + \
                0.4 * np.sin(2 * np.pi * 369.99 * tiempo)
    frecuencia, confianza = tono.detectar_frecuencia(dos_notas, FS)
    assert frecuencia is None or confianza < 0.95


# =============================================================================
# Los bends: las notas que más importa detectar bien
# =============================================================================

def test_detecta_todos_los_bends_de_la_armonica():
    """
    Los doce bends de una armónica en Do, uno por uno. Son las notas más
    difíciles de tocar y las que más importa que la app reconozca bien.
    """
    from armonica import mapeo

    bends = ["-1'", "-2'", "-2''", "-3'", "-3''", "-3'''", "-4'", "-6'",
             "8'", "9'", "10'", "10''"]

    for tablatura in bends:
        nota = mapeo.tab_a_nota(tablatura, "C")
        bloque = bloque_de_nota(nota.nombre)
        detectada, _ = tono.detectar_frecuencia(bloque, FS)
        assert detectada is not None, f"No detecto {tablatura}"
        error = abs(error_en_cents(detectada, nota.nombre))
        assert error < 10.0, f"En {tablatura} ({nota.nombre}) erro {error:.1f} cents"


def test_distingue_los_tres_bends_del_tres():
    """
    Sib, La y Lab están a un semitono uno del otro. El detector tiene que
    separarlos sin dudar, porque si los confunde la tablatura sale mal.
    """
    resultados = {}
    for nombre in ["Bb4", "A4", "Ab4"]:
        detectada, _ = tono.detectar_frecuencia(bloque_de_nota(nombre), FS)
        resultados[nombre] = detectada

    # Cada uno tiene que estar mucho más cerca de su nota que de las vecinas.
    for nombre, detectada in resultados.items():
        assert abs(error_en_cents(detectada, nombre)) < 10.0

    # Y tienen que salir en orden descendente de frecuencia.
    assert resultados["Bb4"] > resultados["A4"] > resultados["Ab4"]


# =============================================================================
# La señal entera: detectar_en_senal
# =============================================================================

def test_transcribe_la_corrida_de_doceava_completa():
    """
    LA PRUEBA DE FUEGO DEL PASO.

    Genera el audio de la corrida de blues mayor en 12a posición (lo que Bruno
    practica), lo pasa por el detector y verifica que salgan las trece notas,
    en orden, con el agujero correcto.

    Es la cadena entera funcionando: audio -> frecuencia -> nota -> agujero.
    """
    from armonica import mapeo

    corrida = generar_wav.CORRIDA_12A
    muestras, _ = generar_wav.generar_secuencia(corrida, "C")

    tabla = mapeo.construir_tabla_inversa("C")
    mediciones = tono.detectar_en_senal(muestras, FS)

    # Agrupamos ventanas consecutivas que dieron el mismo agujero.
    # (Es una versión simplificada de lo que va a hacer la segmentación.)
    secuencia = []
    for medicion in mediciones:
        if medicion["frecuencia"] is None:
            continue
        nota, _ = mapeo.frecuencia_a_nota(
            medicion["frecuencia"], tabla_inversa=tabla
        )
        if nota is None:
            continue
        tablatura = nota.como_tab("guion")
        if not secuencia or secuencia[-1] != tablatura:
            secuencia.append(tablatura)

    assert secuencia == corrida


def test_las_ventanas_de_silencio_quedan_marcadas_como_tales():
    """
    detectar_en_senal ni siquiera analiza las ventanas por debajo del umbral de
    volumen. Devuelve la medición igual, con frecuencia None, para que la
    segmentación sepa que ahí hubo un silencio y corte la nota.
    """
    muestras, _ = generar_wav.generar_secuencia(
        ["4", "-4"], "C", duracion_nota=0.4, duracion_silencio=0.4
    )
    mediciones = tono.detectar_en_senal(muestras, FS)

    con_nota = [m for m in mediciones if m["frecuencia"] is not None]
    sin_nota = [m for m in mediciones if m["frecuencia"] is None]

    assert len(con_nota) > 0
    assert len(sin_nota) > 0


def test_el_ruido_de_fondo_no_genera_notas_falsas():
    """
    Medio segundo de ruido, tres notas, medio segundo de ruido. En los tramos
    de ruido no puede aparecer ni una sola nota.
    """
    muestras_notas, _ = generar_wav.generar_secuencia(["4", "-4", "5"], "C")
    con_ruido = np.concatenate([
        generar_wav.generar_ruido(0.5, FS),
        muestras_notas,
        generar_wav.generar_ruido(0.5, FS),
    ])

    mediciones = tono.detectar_en_senal(con_ruido, FS)
    fin_notas = 0.5 + len(muestras_notas) / FS

    for medicion in mediciones:
        if medicion["tiempo_seg"] < 0.45 or medicion["tiempo_seg"] > fin_notas:
            assert medicion["frecuencia"] is None, (
                f"Nota falsa en el ruido, a los {medicion['tiempo_seg']:.2f} s"
            )


def test_cada_medicion_trae_los_cuatro_datos():
    muestras, _ = generar_wav.generar_secuencia(["4"], "C")
    medicion = tono.detectar_en_senal(muestras, FS)[10]
    assert set(medicion) == {"tiempo_seg", "frecuencia", "confianza", "volumen"}


def test_los_tiempos_avanzan_de_a_un_salto_de_ventana():
    """
    Cada ventana empieza SALTO_VENTANA muestras después de la anterior.
    A 512 muestras y 44100 Hz son 11.6 milisegundos, o sea 86 mediciones por
    segundo. Esa es la resolución temporal de toda la app, y es la que va a
    limitar la precisión del análisis de ritmo.
    """
    import config

    muestras, _ = generar_wav.generar_secuencia(["4"], "C")
    mediciones = tono.detectar_en_senal(muestras, FS)

    esperado = config.SALTO_VENTANA / FS
    for anterior, siguiente in zip(mediciones, mediciones[1:]):
        paso = siguiente["tiempo_seg"] - anterior["tiempo_seg"]
        assert paso == pytest.approx(esperado)


# =============================================================================
# Las piezas internas de YIN, una por una
# =============================================================================

def test_la_funcion_de_diferencia_toca_fondo_en_el_periodo():
    """
    Paso 1 de YIN. Para una onda de 441 Hz a 44100 Hz de muestreo, el período
    son exactamente 100 muestras. La función de diferencia tiene que dar un
    valor muy bajo justo en tau = 100.
    """
    senal = seno(441.0)
    diferencia = tono._funcion_diferencia(senal, 300)

    # En tau = 100 tiene que ser mucho menor que en un tau cualquiera que no
    # sea múltiplo del período.
    assert diferencia[100] < diferencia[50] / 10
    assert diferencia[100] < diferencia[150] / 10


def test_la_normalizacion_arranca_en_uno():
    """
    Paso 2 de YIN: por definición del paper, d'(0) = 1.
    """
    normalizada = tono._diferencia_media_normalizada(
        tono._funcion_diferencia(seno(441.0), 300)
    )
    assert normalizada[0] == 1.0


def test_la_normalizacion_baja_cerca_de_cero_en_el_periodo():
    """
    Es lo que permite usar un umbral fijo: no importa el volumen ni el
    instrumento, en el período verdadero el valor se acerca a cero.
    """
    normalizada = tono._diferencia_media_normalizada(
        tono._funcion_diferencia(seno(441.0), 300)
    )
    assert normalizada[100] < 0.05


def test_la_interpolacion_afina_entre_muestras():
    """
    Paso 4 de YIN. Elegimos una frecuencia cuyo período NO cae en un número
    entero de muestras: 450 Hz da 98.0 muestras exactas... probemos con 447,
    que da 98.66 muestras.

    Sin interpolación el detector solo podría responder 44100/98 = 450 Hz o
    44100/99 = 445.45 Hz. Con interpolación tiene que acercarse mucho más.
    """
    detectada, _ = tono.detectar_frecuencia(seno(447.0), FS)
    assert detectada == pytest.approx(447.0, abs=0.5)

    # Y confirmamos que ninguno de los dos taus enteros vecinos habría alcanzado
    # esa precisión por sí solo.
    assert abs(44100 / 98 - 447.0) > 2.0
    assert abs(44100 / 99 - 447.0) > 1.0


def test_la_confianza_baja_cuando_la_senal_se_ensucia():
    """
    La confianza tiene que reflejar qué tan limpia estaba la nota. Sirve para
    descartar detecciones flojas más adelante.
    """
    limpia = seno(440.0)
    ruidosa = limpia + generar_wav.generar_ruido(
        TAMANO / FS, FS, volumen=0.25
    )[:TAMANO]

    _, confianza_limpia = tono.detectar_frecuencia(limpia, FS)
    _, confianza_ruidosa = tono.detectar_frecuencia(ruidosa, FS)

    assert confianza_limpia > confianza_ruidosa


def test_un_sonido_muy_agudo_no_se_confunde_con_una_nota_de_la_armonica():
    """
    El caso que motivó el margen de búsqueda del extremo agudo.

    Un tono de 4000 Hz (un silbido, un acople del micrófono) está fuera del
    rango de la armónica. Lo que NO puede pasar es que se reporte como 2000 Hz,
    que sí sería una nota posible. Y eso es exactamente lo que pasaba antes:
    el algoritmo encontraba el doble del período verdadero.

    Ahora buscamos hasta más arriba del rango aceptado, lo encontramos donde
    está, y lo descartamos.
    """
    for frecuencia_alta in [2800.0, 3200.0, 4000.0]:
        detectada, _ = tono.detectar_frecuencia(seno(frecuencia_alta), FS)
        assert detectada is None, (
            f"{frecuencia_alta} Hz deberia descartarse, pero dio {detectada}"
        )


def test_el_limite_del_rango_agudo_sigue_funcionando():
    """
    Ampliar la búsqueda no puede haber roto la detección de las notas agudas
    de verdad. El C7 (2093 Hz) tiene que seguir saliendo bien.
    """
    for nombre in ["A6", "C7"]:
        frecuencia = notas.midi_a_frecuencia(notas.nombre_a_midi(nombre))
        detectada, _ = tono.detectar_frecuencia(seno(frecuencia), FS)
        assert detectada is not None
        assert abs(error_en_cents(detectada, nombre)) < 10.0


# =============================================================================
# El fundamental ausente: dos agujeros sonando juntos
# =============================================================================

def test_dos_agujeros_juntos_no_se_reportan_como_una_nota_grave():
    """
    EL CASO REAL DE LA PRIMERA GRABACION DE BRUNO.

    Al pasar del agujero 6 al 7 sopló los dos juntos por un instante. Eso da
    Sol5 (784 Hz) y Do6 (1046 Hz) sonando a la vez. Como están en relación 3 a
    4, la onda combinada se repite a la frecuencia de un Do4, 261 Hz, aunque
    ese Do no exista en el sonido: es el "fundamental ausente".

    YIN reportaba ese Do4 con confianza 1.00, y aparecía en la tablatura como
    un agujero 1 soplado que nunca tocó.

    La defensa es verificar que en la frecuencia detectada haya energía de
    verdad. Acá no la hay, así que la ventana se descarta.
    """
    tiempo = np.arange(TAMANO) / FS
    dos_agujeros = (
        0.3 * np.sin(2 * np.pi * 784.0 * tiempo)      # Sol5, el 6 soplado
        + 0.5 * np.sin(2 * np.pi * 1046.5 * tiempo)   # Do6, el 7 soplado
        + 0.4 * np.sin(2 * np.pi * 1568.0 * tiempo)   # el 2do armonico del Sol5
    )
    frecuencia, _ = tono.detectar_frecuencia(dos_agujeros, FS)
    assert frecuencia is None or frecuencia > 700


def test_una_nota_sola_si_tiene_energia_en_su_fundamental():
    """La contracara: una nota de verdad no puede quedar descartada."""
    for nombre in ["C4", "A4", "C5", "A5", "C6"]:
        proporcion = tono.proporcion_del_fundamental(
            bloque_de_nota(nombre),
            notas.midi_a_frecuencia(notas.nombre_a_midi(nombre)),
            FS,
        )
        assert proporcion > config_energia_minima(), (
            f"{nombre} tiene poca energia en su fundamental: {proporcion:.3f}"
        )


def config_energia_minima():
    import config
    return config.ENERGIA_FUNDAMENTAL_MINIMA


def test_la_proporcion_del_fundamental_es_alta_para_una_onda_pura():
    """Un seno puro tiene toda su energía en una sola frecuencia."""
    proporcion = tono.proporcion_del_fundamental(seno(440.0), 440.0, FS)
    assert proporcion > 1.0


def test_la_proporcion_del_fundamental_es_casi_cero_donde_no_hay_nada():
    proporcion = tono.proporcion_del_fundamental(seno(440.0), 1234.0, FS)
    assert proporcion < 0.05


def test_el_silencio_da_proporcion_cero_sin_dividir_por_cero():
    assert tono.proporcion_del_fundamental(np.zeros(TAMANO), 440.0, FS) == 0.0


# =============================================================================
# La correccion de octava
#
# YIN recorre los retardos de menor a mayor y se queda con el primero que baja
# del umbral. Si un armonico agudo domina, su retardo —mas corto— aparece
# antes y gana: la nota sale una o dos octavas mas aguda, con confianza alta.
#
# El sintoma en la armonica: tocas el agujero 1 aspirado (Re4) y aparece el 8
# aspirado (Re6), que es exactamente cuatro veces la frecuencia.
# =============================================================================

def armonicos(fundamental_hz, pesos, duracion=0.2, ruido=0.0, semilla=11):
    """Una nota donde nosotros decidimos el peso de cada armonico."""
    cantidad = int(config.FRECUENCIA_MUESTREO * duracion)
    tiempo = np.arange(cantidad) / config.FRECUENCIA_MUESTREO
    onda = np.zeros(cantidad)
    for indice, peso in enumerate(pesos, start=1):
        onda += peso * np.sin(2 * np.pi * fundamental_hz * indice * tiempo)
    onda /= np.max(np.abs(onda))
    if ruido:
        onda += np.random.default_rng(semilla).normal(0, ruido, cantidad)
    return (onda * 0.5)[:config.TAMANO_VENTANA]


def test_un_armonico_dominante_ya_no_sube_dos_octavas():
    """
    EL CASO QUE APARECIO USANDO LA APP.

    Re4 (293.7 Hz) con el cuarto armonico dominante se reportaba como Re6
    (1174.7 Hz) con confianza 0.95. En una armonica en Do eso es tocar el
    agujero 1 aspirado y ver el 8 aspirado.
    """
    re4 = notas.midi_a_frecuencia(62)
    bloque = armonicos(re4, [0.08, 0.10, 0.08, 1.00, 0.10, 0.08, 0.10, 0.60])

    frecuencia, _ = tono.detectar_frecuencia(bloque)

    assert frecuencia == pytest.approx(re4, rel=0.02)


def test_un_segundo_armonico_dominante_tampoco_sube_una_octava():
    do4 = notas.midi_a_frecuencia(60)
    bloque = armonicos(do4, [0.10, 1.00, 0.10, 0.60, 0.05, 0.05, 0.05, 0.30])

    frecuencia, _ = tono.detectar_frecuencia(bloque)

    assert frecuencia == pytest.approx(do4, rel=0.02)


def test_una_nota_aguda_legitima_no_se_baja_dos_octavas():
    """
    LA TRAMPA DE ESTA CORRECCION, Y POR QUE LA REGLA ES "CLARAMENTE MEJOR".

    Una onda que se repite cada T se repite tambien cada 2T y cada 4T, siempre.
    Medido sobre este Do6: el retardo correcto vale 0.001 y sus multiplos 0.002
    y 0.005, los tres "buenos". Una regla que aceptara cualquier multiplo bueno
    bajaria DOS OCTAVAS todas las notas agudas de la armonica.
    """
    do6 = notas.midi_a_frecuencia(84)
    bloque = armonicos(do6, [1.0, 0.45, 0.30, 0.15, 0.08, 0.04, 0.02, 0.01])

    frecuencia, _ = tono.detectar_frecuencia(bloque)

    assert frecuencia == pytest.approx(do6, rel=0.02)


def test_la_correccion_no_toca_un_timbre_normal():
    """En los 31 agujeros de la armonica, con timbre normal, no cambia nada."""
    for midi in range(60, 91):
        esperada = notas.midi_a_frecuencia(midi)
        bloque = armonicos(esperada, [1.0, 0.45, 0.30, 0.15, 0.08])

        frecuencia, _ = tono.detectar_frecuencia(bloque)

        assert frecuencia is not None, f"se perdio la nota midi {midi}"
        assert frecuencia == pytest.approx(esperada, rel=0.02)


def test_la_correccion_no_se_aplica_por_docenas():
    """
    Solo x2 y x4, nunca x3. Y este test existe por un error de verdad.

    Un Re5 tocado sobre una base con un Sol2 de bajo: 587 dividido 3 da 196,
    que es EXACTAMENTE ese bajo, y la senal se repite ahi de verdad. La primera
    version de la correccion "acertaba" y convertia la nota de la armonica en
    la nota del bajo. Rompio un test que ya estaba en la suite.

    Por la razon entre valores no se podian separar: el falso positivo media
    0.504 y un caso legitimo media 0.500. Lo que los separa es el intervalo:
    un x3 es una docena y casi siempre viene de otro instrumento, no de un
    armonico de la propia lengueta.
    """
    # Se prueba la regla directamente y no con una senal fabricada: con una
    # mezcla de armonica mas bajo, YIN encuentra el bajo POR SU CUENTA, sin
    # que la correccion intervenga, y el test no probaria lo que dice probar.
    #
    # La curva se arma a mano: un valle mediocre en tau, uno buenisimo en
    # tau*3 —la trampa— y ninguno en tau*2 ni tau*4.
    tau = 75
    tau_maximo = 300
    curva = np.ones(tau_maximo) * 0.5
    curva[tau] = 0.11
    curva[tau * 2] = 0.40
    curva[tau * 3] = 0.02          # el bajo: mucho mejor, pero es una docena

    corregido = tono._corregir_octava(curva, tau, tau_maximo,
                                      config.UMBRAL_YIN, factor=0.7)

    assert corregido == tau, "corrigio por x3 y no tenia que hacerlo"

    # Y para que se vea que la regla si funciona cuando el valle esta en x2:
    curva[tau * 2] = 0.02
    assert tono._corregir_octava(curva, tau, tau_maximo,
                                 config.UMBRAL_YIN, factor=0.7) == tau * 2


def test_la_correccion_se_puede_apagar():
    """
    Con el factor en cero queda el comportamiento viejo.

    Sirve para poder medir la diferencia, que es como se eligio el valor.
    """
    re4 = notas.midi_a_frecuencia(62)
    bloque = armonicos(re4, [0.08, 0.10, 0.08, 1.00, 0.10, 0.08, 0.10, 0.60])

    tau_maximo = int(config.FRECUENCIA_MUESTREO / config.FRECUENCIA_MINIMA_HZ) + 1
    diferencia = tono._funcion_diferencia(np.asarray(bloque, dtype=np.float64),
                                          tau_maximo)
    curva = tono._diferencia_media_normalizada(diferencia)
    tau = tono._buscar_primer_minimo(curva, config.UMBRAL_YIN, 11, tau_maximo)

    sin_corregir = tono._corregir_octava(curva, tau, tau_maximo,
                                         config.UMBRAL_YIN, factor=0.0)
    corregido = tono._corregir_octava(curva, tau, tau_maximo,
                                      config.UMBRAL_YIN, factor=0.7)

    assert sin_corregir == tau
    assert corregido == pytest.approx(tau * 4, abs=2)


def test_si_la_correccion_no_pasa_las_verificaciones_queda_la_original():
    """
    La correccion nunca puede dejar las cosas peor que no corregir.

    La primera version reemplazaba el periodo y seguia de largo. Medido sobre
    124 notas legitimas, eso PERDIA entre 35 y 56: la correccion las empujaba a
    una frecuencia sin energia, la verificacion del fundamental las rechazaba,
    y la nota salia como "no se" en vez de salir bien.
    """
    for midi in range(72, 91):          # el registro agudo, donde mas pasaba
        esperada = notas.midi_a_frecuencia(midi)
        bloque = armonicos(esperada, [0.5, 1.0, 0.8, 0.6, 0.4, 0.3, 0.2, 0.1],
                           ruido=0.03)

        frecuencia, _ = tono.detectar_frecuencia(bloque)

        assert frecuencia is not None, f"se perdio la nota midi {midi}"
