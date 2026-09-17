"""
Tests de armonica/compas_uno.py — dónde arranca el compás 1 de un audio
exportado.

El audio se fabrica: golpes cortos y agudos (las baquetas del conteo) y
después un bajo grave (la banda). El módulo tiene que encontrar dónde entra
el bajo.

Cómo correrlos:   python -m pytest tests/test_compas_uno.py -v
"""

import numpy as np
import pytest

from armonica import audio, compas_uno

FS = 22050


def golpe(instante, senal, duracion=0.03, frecuencia=3000.0):
    """Un golpe de baqueta: un tono agudo muy corto, sin graves."""
    desde = int(instante * FS)
    n = int(duracion * FS)
    t = np.arange(n) / FS
    senal[desde:desde + n] += 0.6 * np.sin(2 * np.pi * frecuencia * t) * np.exp(-t * 80)


def banda(desde_seg, senal):
    """La banda: un bajo a 55 Hz desde ese instante hasta el final."""
    desde = int(desde_seg * FS)
    t = np.arange(len(senal) - desde) / FS
    senal[desde:] += 0.5 * np.sin(2 * np.pi * 55.0 * t) + 0.2 * np.sin(2 * np.pi * 440.0 * t)


def exportacion(bpm=120, compases_de_conteo=2, pulsos=4, duracion=12.0):
    """Como exporta Band-in-a-Box: conteo con baquetas y despues la banda."""
    senal = np.zeros(int(duracion * FS))
    pulso = 60.0 / bpm
    for numero in range(compases_de_conteo * pulsos):
        golpe(numero * pulso, senal)
    banda(compases_de_conteo * pulsos * pulso, senal)
    return senal


def test_encuentra_el_compas_uno_despues_de_dos_compases_de_conteo():
    """A 120 BPM en 4/4, dos compases son 4 segundos."""
    resultado = compas_uno.detectar(exportacion(bpm=120, compases_de_conteo=2), FS, 120, 4)
    assert resultado is not None
    assert resultado.segundos == pytest.approx(4.0, abs=0.02)
    assert resultado.redondeado is True
    assert resultado.compases_de_conteo == 2


def test_un_compas_de_conteo_tambien():
    resultado = compas_uno.detectar(exportacion(bpm=90, compases_de_conteo=1), FS, 90, 4)
    assert resultado.segundos == pytest.approx(60.0 / 90 * 4, abs=0.02)
    assert resultado.compases_de_conteo == 1


def test_sin_conteo_el_compas_uno_es_el_segundo_cero():
    """Graves desde el principio: no hay conteo."""
    resultado = compas_uno.detectar(exportacion(compases_de_conteo=0), FS, 120, 4)
    assert resultado.segundos == 0.0
    assert resultado.compases_de_conteo == 0


def test_si_no_cae_en_compases_enteros_se_devuelve_crudo_y_se_avisa():
    """
    Un audio grabado con el teléfono, donde la banda entra a los 2,7 s a
    120 BPM (1,35 compases): no es un conteo entero, y no se inventa uno.
    """
    senal = np.zeros(int(10 * FS))
    banda(2.7, senal)
    resultado = compas_uno.detectar(senal, FS, 120, 4)
    assert resultado.redondeado is False
    assert resultado.segundos == pytest.approx(2.7, abs=0.02)


def test_el_silencio_no_da_nada():
    assert compas_uno.detectar(np.zeros(FS), FS, 120, 4) is None
    assert compas_uno.detectar(np.zeros(0), FS, 120, 4) is None


def test_desde_un_archivo_wav(tmp_path):
    ruta = str(tmp_path / "base.wav")
    audio.escribir_wav(ruta, exportacion(bpm=100, compases_de_conteo=2).astype(np.float32),
                       frecuencia_muestreo=FS)
    resultado = compas_uno.desde_archivo(ruta, 100, 4)
    assert resultado.segundos == pytest.approx(60.0 / 100 * 8, abs=0.02)


def test_un_archivo_que_no_se_puede_leer_da_none(tmp_path):
    ruta = tmp_path / "roto.wav"
    ruta.write_bytes(b"no soy un wav")
    assert compas_uno.desde_archivo(str(ruta), 100, 4) is None
