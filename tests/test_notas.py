"""
Tests de armonica/notas.py — conversiones entre Hz, MIDI y nombres de nota.

Todo con números fijos, sin micrófono. Estos tests corren en milisegundos y
tienen que pasar SIEMPRE: si alguno falla, algo básico se rompió.

Cómo correrlos:   python -m pytest tests/test_notas.py -v
"""

import math

import pytest

from armonica import notas


# =============================================================================
# midi_a_frecuencia — de número de nota a Hz
# =============================================================================

def test_el_la_de_referencia_son_440_hz():
    """El MIDI 69 es A4 = 440 Hz. Es la referencia de todo el sistema."""
    assert notas.midi_a_frecuencia(69) == pytest.approx(440.0)


def test_una_octava_arriba_es_el_doble_de_frecuencia():
    """Subir 12 semitonos duplica la frecuencia. Es la definición de octava."""
    assert notas.midi_a_frecuencia(81) == pytest.approx(880.0)


def test_una_octava_abajo_es_la_mitad_de_frecuencia():
    assert notas.midi_a_frecuencia(57) == pytest.approx(220.0)


def test_el_do_central_es_261_63_hz():
    """C4 = MIDI 60. Es el agujero 1 soplado de una armónica en C."""
    assert notas.midi_a_frecuencia(60) == pytest.approx(261.63, abs=0.01)


def test_el_sol_grave_de_la_armonica_en_g():
    """G3 = MIDI 55 = 196 Hz. La nota más grave que vamos a tener que detectar."""
    assert notas.midi_a_frecuencia(55) == pytest.approx(196.0, abs=0.01)


def test_acepta_midi_con_decimales():
    """
    Medio semitono arriba del La tiene que caer entre 440 y el siguiente semitono.
    Esto es lo que pasa cuando un bend está a mitad de camino.
    """
    frecuencia = notas.midi_a_frecuencia(69.5)
    assert 440.0 < frecuencia < notas.midi_a_frecuencia(70)


# =============================================================================
# frecuencia_a_midi — de Hz a número de nota
# =============================================================================

def test_440_hz_da_midi_69():
    assert notas.frecuencia_a_midi(440.0) == pytest.approx(69.0)


def test_ida_y_vuelta_no_pierde_informacion():
    """
    Convertir a Hz y volver tiene que devolver el número original.
    Probamos todo el rango útil de la armónica, del MIDI 55 al 96.
    """
    for midi_original in range(55, 97):
        frecuencia = notas.midi_a_frecuencia(midi_original)
        midi_recuperado = notas.frecuencia_a_midi(frecuencia)
        assert midi_recuperado == pytest.approx(midi_original)


def test_frecuencia_cero_o_negativa_da_error():
    """No existe el logaritmo de cero. Mejor un error claro que un NaN silencioso."""
    with pytest.raises(ValueError):
        notas.frecuencia_a_midi(0.0)
    with pytest.raises(ValueError):
        notas.frecuencia_a_midi(-100.0)


# =============================================================================
# midi_a_nombre — de número a nombre legible
# =============================================================================

def test_nombres_de_las_notas_clave():
    assert notas.midi_a_nombre(60) == "C4"    # Do central
    assert notas.midi_a_nombre(69) == "A4"    # La de referencia
    assert notas.midi_a_nombre(55) == "G3"    # armónica en G, agujero 1 soplado
    assert notas.midi_a_nombre(96) == "C7"    # armónica en C, agujero 10 soplado


def test_por_defecto_usa_bemoles():
    """En armónica y blues se habla en bemoles: Bb, Eb, Db."""
    assert notas.midi_a_nombre(70) == "Bb4"
    assert notas.midi_a_nombre(61) == "Db4"
    assert notas.midi_a_nombre(63) == "Eb4"


def test_puede_usar_sostenidos_si_se_lo_pide():
    assert notas.midi_a_nombre(70, usar_sostenidos=True) == "A#4"
    assert notas.midi_a_nombre(61, usar_sostenidos=True) == "C#4"


def test_redondea_los_decimales_al_semitono_mas_cercano():
    """69.4 sigue siendo un La; 69.6 ya es el Sib de arriba."""
    assert notas.midi_a_nombre(69.4) == "A4"
    assert notas.midi_a_nombre(69.6) == "Bb4"


def test_el_cambio_de_octava_ocurre_en_el_do():
    """
    La octava cambia entre B y C, no en cualquier lado.
    Es un error clásico equivocarse acá por uno.
    """
    assert notas.midi_a_nombre(59) == "B3"
    assert notas.midi_a_nombre(60) == "C4"
    assert notas.midi_a_nombre(71) == "B4"
    assert notas.midi_a_nombre(72) == "C5"


# =============================================================================
# nombre_a_midi — de nombre a número
# =============================================================================

def test_nombre_a_midi_casos_conocidos():
    assert notas.nombre_a_midi("C4") == 60
    assert notas.nombre_a_midi("A4") == 69
    assert notas.nombre_a_midi("G3") == 55
    assert notas.nombre_a_midi("C7") == 96


def test_nombre_a_midi_acepta_bemoles_y_sostenidos_por_igual():
    """Db4 y C#4 son la misma tecla del piano, tienen que dar el mismo número."""
    assert notas.nombre_a_midi("Db4") == notas.nombre_a_midi("C#4") == 61
    assert notas.nombre_a_midi("Bb4") == notas.nombre_a_midi("A#4") == 70


def test_nombre_a_midi_es_el_inverso_de_midi_a_nombre():
    for midi_original in range(55, 97):
        nombre = notas.midi_a_nombre(midi_original)
        assert notas.nombre_a_midi(nombre) == midi_original


def test_nombre_a_midi_rechaza_texto_invalido():
    with pytest.raises(ValueError):
        notas.nombre_a_midi("H4")      # no existe la nota H en esta notación
    with pytest.raises(ValueError):
        notas.nombre_a_midi("C")       # falta la octava
    with pytest.raises(ValueError):
        notas.nombre_a_midi("Cx")      # la octava no es un número


# =============================================================================
# desviacion_cents — el corazón del medidor de afinación
# =============================================================================

def test_afinacion_perfecta_da_cero_cents():
    assert notas.desviacion_cents(440.0, 69) == pytest.approx(0.0, abs=0.001)


def test_un_semitono_completo_son_cien_cents():
    """Tocar un Sib cuando apuntabas a un La son exactamente +100 cents."""
    frecuencia_sib = notas.midi_a_frecuencia(70)
    assert notas.desviacion_cents(frecuencia_sib, 69) == pytest.approx(100.0)


def test_estar_bajo_da_cents_negativos():
    """Signo negativo = te falta subir. Es la convención de todos los afinadores."""
    frecuencia_sol_sostenido = notas.midi_a_frecuencia(68)
    assert notas.desviacion_cents(frecuencia_sol_sostenido, 69) == pytest.approx(-100.0)


def test_medio_semitono_son_cincuenta_cents():
    """El punto exacto entre dos notas. Es nuestro umbral de decisión."""
    frecuencia_intermedia = notas.midi_a_frecuencia(69.5)
    assert notas.desviacion_cents(frecuencia_intermedia, 69) == pytest.approx(50.0)


def test_los_cents_son_proporcionales_no_absolutos():
    """
    La misma cantidad de cents en notas distintas significa proporciones
    distintas de Hz. Este test documenta esa propiedad, que es la razón por la
    que usamos cents y no Hz para medir afinación.
    """
    cents_grave = notas.desviacion_cents(notas.midi_a_frecuencia(55.2), 55)
    cents_agudo = notas.desviacion_cents(notas.midi_a_frecuencia(90.2), 90)
    assert cents_grave == pytest.approx(cents_agudo)


# =============================================================================
# midi_mas_cercano — la función que usa el resto de la app
# =============================================================================

def test_midi_mas_cercano_con_afinacion_perfecta():
    midi, cents = notas.midi_mas_cercano(440.0)
    assert midi == 69
    assert cents == pytest.approx(0.0, abs=0.001)


def test_midi_mas_cercano_detecta_que_estas_alto():
    """452 Hz es un La bastante desafinado hacia arriba."""
    midi, cents = notas.midi_mas_cercano(452.0)
    assert midi == 69
    assert 40 < cents < 50


def test_midi_mas_cercano_salta_a_la_nota_siguiente_pasados_los_50_cents():
    """
    Justo arriba de la mitad entre dos notas, la nota más cercana ya es la otra.
    Verifica que el redondeo funciona en el borde.
    """
    frecuencia_apenas_arriba_del_medio = notas.midi_a_frecuencia(69.51)
    midi, cents = notas.midi_mas_cercano(frecuencia_apenas_arriba_del_medio)
    assert midi == 70
    assert cents < 0     # ahora estamos por debajo del Sib


def test_midi_mas_cercano_nunca_devuelve_mas_de_50_cents():
    """
    Por definición, la nota más cercana está siempre a 50 cents o menos.
    Probamos con muchas frecuencias intermedias para asegurarlo.
    """
    for paso in range(0, 100):
        midi_fraccionario = 60 + paso / 10.0
        frecuencia = notas.midi_a_frecuencia(midi_fraccionario)
        _, cents = notas.midi_mas_cercano(frecuencia)
        assert abs(cents) <= 50.001


# =============================================================================
# clase_de_nota y nombre_de_clase — trabajar sin octavas
# =============================================================================

def test_la_clase_de_nota_ignora_la_octava():
    """Todos los Do dan clase 0, sin importar en qué octava estén."""
    assert notas.clase_de_nota(60) == 0
    assert notas.clase_de_nota(72) == 0
    assert notas.clase_de_nota(96) == 0


def test_clases_de_las_doce_notas():
    assert notas.clase_de_nota(60) == 0     # C
    assert notas.clase_de_nota(67) == 7     # G
    assert notas.clase_de_nota(71) == 11    # B


def test_nombre_de_clase_sin_octava():
    assert notas.nombre_de_clase(0) == "C"
    assert notas.nombre_de_clase(7) == "G"
    assert notas.nombre_de_clase(10) == "Bb"


def test_nombre_de_clase_da_la_vuelta_pasado_el_doce():
    """La clase 12 es otra vez C. Sirve para sumar intervalos sin cuidarse."""
    assert notas.nombre_de_clase(12) == "C"
    assert notas.nombre_de_clase(19) == "G"
