"""
Tests de los tramos — encontrar las frases dentro de una grabación larga.

POR QUE EXISTE ESTE ARCHIVO

Los audios que manda un profesor no son frases: son clases. Habla, toca una
frase, vuelve a hablar. Medido sobre dos audios reales del profe, la armónica
ocupa el 64% y el 41% del archivo, repartida en 8 y en 10 tramos.

Acá el audio se fabrica con silencios en el medio, así que sabemos exactamente
cuántos tramos tiene que encontrar.

Cómo correrlos:   python -m pytest tests/test_tramos.py -v
"""

import numpy as np
import pytest

import config
from armonica import audio, frases, transcripcion
from herramientas import generar_wav


def clase(bloques, silencio_entre=2.5, tonalidad="C", duracion_nota=0.4):
    """
    Fabrica un audio con forma de clase: frases separadas por silencios.

    `bloques` es una lista de listas de tablaturas. Entre bloque y bloque va
    un silencio largo, que es donde el profesor estaría hablando.
    """
    partes = []
    for numero, tablaturas in enumerate(bloques):
        if numero:
            partes.append(generar_wav.generar_silencio(silencio_entre))
        muestras, _ = generar_wav.generar_secuencia(
            tablaturas, tonalidad, duracion_nota=duracion_nota,
            duracion_silencio=0.12)
        partes.append(muestras)
    return np.concatenate(partes)


def escribir(tmp_path, muestras, nombre="clase.wav"):
    ruta = tmp_path / nombre
    audio.escribir_wav(ruta, muestras)
    return str(ruta)


def transcribir(tmp_path, bloques, **extras):
    ruta = escribir(tmp_path, clase(bloques, **extras))
    return transcripcion.desde_archivo(ruta, "C"), ruta


# =============================================================================
# Encontrar los tramos
# =============================================================================

def test_una_frase_sola_es_un_solo_tramo(tmp_path):
    resultado, _ = transcribir(tmp_path, [["-2", "4", "-4", "-5"]])

    tramos = frases.detectar_tramos(resultado.eventos)

    assert len(tramos) == 1
    assert tramos[0].cantidad == 4
    assert tramos[0].tablatura() == ["-2", "4", "-4", "-5"]


def test_tres_frases_separadas_son_tres_tramos(tmp_path):
    """El caso de la clase: toca, habla, toca, habla, toca."""
    resultado, _ = transcribir(tmp_path, [
        ["-2", "4", "-4"],
        ["-5", "6", "-6"],
        ["4", "-4", "-5", "6"],
    ])

    tramos = frases.detectar_tramos(resultado.eventos)

    assert len(tramos) == 3
    assert [t.cantidad for t in tramos] == [3, 3, 4]
    assert tramos[0].tablatura() == ["-2", "4", "-4"]
    assert tramos[2].tablatura() == ["4", "-4", "-5", "6"]


def test_los_tramos_saben_cuando_empiezan_y_cuando_terminan(tmp_path):
    resultado, _ = transcribir(tmp_path, [["-2", "4", "-4"], ["-5", "6", "-6"]])

    primero, segundo = frases.detectar_tramos(resultado.eventos)

    # El primero arranca casi en cero; el segundo, después del silencio.
    assert primero.desde_seg < 0.2
    assert segundo.desde_seg > primero.hasta_seg + 2.0
    assert primero.duracion_seg == pytest.approx(1.5, abs=0.3)


def test_el_silencio_dentro_de_una_frase_no_la_parte(tmp_path):
    """
    Entre nota y nota hay silencio, y no por eso son frases distintas.

    Es la razón por la que el umbral es un segundo y medio y no medio
    segundo: tiene que ser más largo que cualquier silencio DENTRO de una
    frase tocada, y más corto que cualquier explicación hablada.
    """
    resultado, _ = transcribir(
        tmp_path, [["-2", "4", "-4", "-5", "6"]], duracion_nota=0.35)

    tramos = frases.detectar_tramos(resultado.eventos)

    assert len(tramos) == 1
    assert tramos[0].cantidad == 5


def test_los_tramos_de_una_nota_suelta_se_descartan(tmp_path):
    """
    No se descartan por ser errores: una nota suelta puede ser real.

    Se descartan porque no son una frase, y ofrecerlas solo hace ruido en la
    lista. En los audios del profe esto sacó 6 tramos de 16.
    """
    resultado, _ = transcribir(tmp_path, [
        ["-2", "4", "-4", "-5"],
        ["6"],
        ["4", "-4", "-5", "6"],
    ])

    tramos = frases.detectar_tramos(resultado.eventos)

    assert len(tramos) == 2
    # Y quedan numerados 1 y 2, no 1 y 3: los números son los de la pantalla.
    assert [t.numero for t in tramos] == [1, 2]


def test_un_audio_sin_notas_no_tiene_tramos():
    assert frases.detectar_tramos([]) == []


def test_el_umbral_del_hueco_se_puede_ajustar(tmp_path):
    """Con un umbral más chico que el silencio, se parte donde no hay que."""
    resultado, _ = transcribir(tmp_path, [["-2", "4", "-4", "-5", "6", "-6"]],
                               duracion_nota=0.35)

    normal = frases.detectar_tramos(resultado.eventos)
    picado = frases.detectar_tramos(resultado.eventos, hueco_seg=0.01,
                                    minimo_notas=1)

    assert len(normal) == 1
    assert len(picado) == 6      # cada nota queda sola


# =============================================================================
# Recortar
# =============================================================================

def test_recortar_deja_solo_las_notas_de_ese_pedazo(tmp_path):
    resultado, _ = transcribir(tmp_path, [
        ["-2", "4", "-4"],
        ["-5", "6", "-6"],
    ])
    segundo = frases.detectar_tramos(resultado.eventos)[1]

    recortado = transcripcion.recortar(
        resultado, segundo.desde_seg, segundo.hasta_seg, "C")

    assert [e.como_tab() for e in recortado.reconocidas] == ["-5", "6", "-6"]


def test_recortar_achica_tambien_el_audio(tmp_path):
    """
    Se recortan las MUESTRAS y no los eventos.

    Filtrar los eventos sería más barato y dejaría la revisión de monofonía
    midiendo el archivo entero, que es justo lo que no queremos: una clase con
    la base sonando mientras el profesor habla puede no pasar el control
    aunque el tramo elegido esté limpio.

    Medido sobre el audio real del profe, recortar el tramo más largo subió
    la monofonía de 0.76 a 0.80 y la detección de 0.38 a 0.56.
    """
    resultado, _ = transcribir(tmp_path, [
        ["-2", "4", "-4"],
        ["-5", "6", "-6"],
    ])
    segundo = frases.detectar_tramos(resultado.eventos)[1]

    recortado = transcripcion.recortar(
        resultado, segundo.desde_seg, segundo.hasta_seg, "C")

    assert recortado.duracion_seg < resultado.duracion_seg / 2
    assert recortado.duracion_seg == pytest.approx(segundo.duracion_seg,
                                                   abs=0.5)


def test_las_notas_del_recorte_arrancan_en_cero(tmp_path):
    """
    Una frase guardada tiene tiempos relativos a su primera nota.

    Sin esto, una frase recortada del minuto 1:05 quedaría con la primera nota
    en el segundo 65, y al compararla contra tu intento —que arranca en cero—
    daría un desfase de un minuto.
    """
    resultado, _ = transcribir(tmp_path, [
        ["-2", "4", "-4"],
        ["-5", "6", "-6"],
    ])
    segundo = frases.detectar_tramos(resultado.eventos)[1]

    recortado = transcripcion.recortar(
        resultado, segundo.desde_seg, segundo.hasta_seg, "C")
    frase = frases.desde_eventos(recortado.eventos, "el segundo tramo")

    assert frase.notas[0].inicio_seg == pytest.approx(0.0, abs=0.01)
    assert frase.duracion_seg < 3.0


def test_recortar_un_pedazo_vacio_no_rompe(tmp_path):
    """Elegir un rango donde no hay nada: devuelve vacío, no revienta."""
    resultado, _ = transcribir(tmp_path, [["-2", "4", "-4"], ["-5", "6"]])

    recortado = transcripcion.recortar(resultado, 2.4, 2.9, "C")

    assert recortado.reconocidas == []


def test_recortar_fuera_del_audio_no_rompe(tmp_path):
    resultado, _ = transcribir(tmp_path, [["-2", "4", "-4"]])

    recortado = transcripcion.recortar(resultado, 500.0, 600.0, "C")

    assert recortado.reconocidas == []
    assert recortado.duracion_seg == 0.0
