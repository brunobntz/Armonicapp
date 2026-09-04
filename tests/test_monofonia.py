"""
Tests de tono.medir_monofonia — ¿este audio se puede transcribir?

Es la misma familia de tests que ritmo.ajuste_vs_azar: verificar que la app
sepa cuándo NO tiene que confiar en sus propios números.

Todo el audio se fabrica acá, así que sabemos qué respuesta corresponde.

Cómo correrlos:   python -m pytest tests/test_monofonia.py -v
"""

import numpy as np
import pytest

from armonica import audio, tono
from herramientas import generar_wav


FS = 44100


def melodia(tablaturas=None, tonalidad="C"):
    """Una melodía de armónica sola: el caso que sí se puede transcribir."""
    if tablaturas is None:
        tablaturas = ["4", "-4", "-5", "6", "-6", "7"]
    muestras, _ = generar_wav.generar_secuencia(tablaturas, tonalidad)
    return audio.normalizar(muestras)


def acorde_sostenido(frecuencias, duracion_seg=3.0, amplitud=0.3):
    """Varias notas sonando juntas y sostenidas, como una guitarra rasgueando."""
    tiempo = np.arange(int(duracion_seg * FS)) / FS
    onda = np.zeros(len(tiempo))
    for frecuencia in frecuencias:
        onda += amplitud * np.sin(2 * np.pi * frecuencia * tiempo)
    return audio.normalizar(onda)


# =============================================================================
# Lo que sí se puede transcribir
# =============================================================================

def test_una_melodia_sola_da_puntaje_alto():
    medidas = tono.medir_monofonia(melodia(), FS)
    assert medidas["puntaje"] > 0.75
    assert "se puede transcribir" in medidas["veredicto"]


def test_una_melodia_sola_tiene_deteccion_y_estabilidad_altas():
    medidas = tono.medir_monofonia(melodia(), FS)
    assert medidas["deteccion"] > 0.8
    assert medidas["estabilidad"] > 0.9
    assert medidas["confianza"] > 0.9


def test_funciona_igual_con_otra_armonica():
    medidas = tono.medir_monofonia(melodia(tonalidad="G"), FS)
    assert medidas["puntaje"] > 0.75


def test_una_melodia_con_bends_sigue_siendo_transcribible():
    """Los bends son notas continuas, pero siguen siendo una sola nota por vez."""
    medidas = tono.medir_monofonia(
        melodia(["-2''", "-3'''", "-3''", "-6'", "8'"]), FS
    )
    assert medidas["puntaje"] > 0.7


# =============================================================================
# Lo que NO se puede transcribir
# =============================================================================

def test_varios_instrumentos_juntos_dan_puntaje_bajo():
    """
    EL TEST QUE JUSTIFICA QUE ESTA FUNCION EXISTA.

    Armónica, bajo y guitarra a la vez. YIN devolvería frecuencias con toda
    seriedad, pero serían basura. La medida tiene que delatarlo ANTES de que
    alguien lea esa transcripción como si fuera cierta.
    """
    melodia_sola = melodia()
    tiempo = np.arange(len(melodia_sola)) / FS

    bajo = 0.5 * np.sin(2 * np.pi * 98 * tiempo) + \
           0.3 * np.sin(2 * np.pi * 196 * tiempo)
    guitarra = 0.25 * (np.sin(2 * np.pi * 261 * tiempo)
                       + np.sin(2 * np.pi * 329 * tiempo)
                       + np.sin(2 * np.pi * 392 * tiempo))

    medidas = tono.medir_monofonia(audio.normalizar(melodia_sola + bajo + guitarra), FS)
    assert medidas["puntaje"] < 0.35
    assert "no tiene sentido" in medidas["veredicto"]


def test_sacar_el_bajo_no_alcanza():
    """
    LA CONCLUSION MAS IMPORTANTE DE LA PRUEBA DE DEMUCS.

    Demucs separa en bateria, bajo, voz y "otros". La armónica cae en "otros"
    junto con la guitarra y el piano. Este test muestra que aunque saquemos el
    bajo, una guitarra sosteniendo un acorde alcanza para arruinar la
    transcripción.

    Es la evidencia que dice que separar no va a ser suficiente.
    """
    melodia_sola = melodia()
    tiempo = np.arange(len(melodia_sola)) / FS
    guitarra = 0.25 * (np.sin(2 * np.pi * 261 * tiempo)
                       + np.sin(2 * np.pi * 329 * tiempo)
                       + np.sin(2 * np.pi * 392 * tiempo))

    medidas = tono.medir_monofonia(audio.normalizar(melodia_sola + guitarra), FS)
    assert medidas["puntaje"] < 0.55


def test_un_acorde_solo_no_es_transcribible():
    medidas = tono.medir_monofonia(acorde_sostenido([261.6, 329.6, 392.0]), FS)
    assert medidas["puntaje"] < 0.55


def test_el_ruido_no_es_transcribible():
    ruido = generar_wav.generar_ruido(3.0, FS, volumen=0.3)
    medidas = tono.medir_monofonia(ruido, FS)
    assert medidas["puntaje"] < 0.35


# =============================================================================
# Los casos borde
# =============================================================================

def test_el_silencio_avisa_que_no_hay_datos():
    medidas = tono.medir_monofonia(np.zeros(FS), FS)
    assert medidas["veredicto"] == "sin datos"
    assert "umbral de volumen" in medidas["explicacion"]


def test_un_audio_muy_corto_avisa_que_no_hay_datos():
    medidas = tono.medir_monofonia(np.zeros(100), FS)
    assert medidas["veredicto"] == "sin datos"


def test_todas_las_medidas_estan_entre_cero_y_uno():
    """Salvo `fundamental`, que puede pasar de 1 en una onda pura."""
    medidas = tono.medir_monofonia(melodia(), FS)
    for clave in ("deteccion", "estabilidad", "confianza", "puntaje"):
        assert 0.0 <= medidas[clave] <= 1.0


# =============================================================================
# La estabilidad, que es la medida más informativa
# =============================================================================

def test_la_estabilidad_es_alta_en_notas_sostenidas():
    """Una nota larga ocupa decenas de ventanas iguales."""
    medidas = tono.medir_monofonia(melodia(["4"]), FS)
    assert medidas["estabilidad"] > 0.95


def test_la_estabilidad_tolera_el_vibrato():
    """
    Comparamos "la misma nota" con medio semitono de tolerancia, no frecuencia
    exacta. Un vibrato es expresión, no inestabilidad.
    """
    tiempo = np.arange(int(3.0 * FS)) / FS
    # Un La con vibrato de 5 Hz y medio semitono de profundidad.
    frecuencia = 440.0 * (2 ** (0.25 * np.sin(2 * np.pi * 5 * tiempo) / 12))
    fase = np.cumsum(2 * np.pi * frecuencia / FS)
    onda = audio.normalizar(0.5 * np.sin(fase))

    medidas = tono.medir_monofonia(onda, FS)
    assert medidas["estabilidad"] > 0.8


# =============================================================================
# El informe en texto
# =============================================================================

def test_el_informe_muestra_las_cuatro_medidas():
    texto = tono.informe_de_monofonia(tono.medir_monofonia(melodia(), FS))
    for clave in ("deteccion", "estabilidad", "confianza", "fundamental"):
        assert clave in texto
    assert "PUNTAJE" in texto


def test_el_informe_lleva_titulo_si_se_lo_pide():
    texto = tono.informe_de_monofonia(
        tono.medir_monofonia(melodia(), FS), "Mi tema"
    )
    assert texto.startswith("Mi tema")


def test_el_informe_sin_datos_explica_por_que():
    texto = tono.informe_de_monofonia(tono.medir_monofonia(np.zeros(FS), FS))
    assert "umbral" in texto


# =============================================================================
# La herramienta de Demucs
# =============================================================================

def test_la_herramienta_avisa_si_demucs_no_esta_instalado():
    """
    No queremos que explote con un ImportError: tiene que explicar qué instalar
    y avisar que son dos gigas.
    """
    from herramientas import prueba_demucs

    texto = prueba_demucs.instrucciones_de_instalacion()
    assert "pip install demucs" in texto
    assert "2 GB" in texto
    assert "--solo-medir" in texto


def test_la_herramienta_sabe_si_demucs_esta_o_no():
    from herramientas import prueba_demucs

    assert isinstance(prueba_demucs.demucs_instalado(), bool)


def test_el_umbral_de_utilidad_es_coherente_con_los_veredictos():
    """
    El umbral que usa la herramienta para decir "sirve" tiene que caer en el
    mismo lugar donde tono.py empieza a decir que se puede transcribir.
    """
    from herramientas import prueba_demucs

    assert "errores" in tono._veredicto(prueba_demucs.PUNTAJE_MINIMO_UTIL)
    assert "no va a servir" in tono._veredicto(
        prueba_demucs.PUNTAJE_MINIMO_UTIL - 0.05
    )
