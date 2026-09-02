"""
Tests de armonica/audio.py — lectura y escritura de .wav, ventanas y volumen.

Sin micrófono. Los archivos se escriben en una carpeta temporal que pytest
crea y borra sola (el parámetro `tmp_path`).

Cómo correrlos:   python -m pytest tests/test_audio.py -v
"""

import numpy as np
import pytest

import config
from armonica import audio


FS = 44100


def seno(frecuencia_hz, duracion_seg=0.5, amplitud=0.5):
    tiempo = np.arange(int(duracion_seg * FS)) / FS
    return (amplitud * np.sin(2 * np.pi * frecuencia_hz * tiempo)).astype(np.float32)


# =============================================================================
# Escribir y volver a leer
# =============================================================================

def test_lo_que_se_escribe_es_lo_que_se_lee(tmp_path):
    """
    La prueba fundamental de cualquier formato: guardar y recuperar tiene que
    devolver lo mismo.

    La tolerancia de 0.0001 existe porque el .wav guarda enteros de 16 bits.
    Al convertir decimales a enteros se pierde un poquito de precisión, igual
    que al redondear pesos a centavos.
    """
    original = seno(440.0)
    ruta = tmp_path / "prueba.wav"

    audio.escribir_wav(ruta, original)
    recuperado, frecuencia_muestreo = audio.leer_wav(ruta)

    assert frecuencia_muestreo == config.FRECUENCIA_MUESTREO
    assert len(recuperado) == len(original)
    assert np.allclose(recuperado, original, atol=1e-4)


def test_el_audio_leido_viene_en_decimales_entre_menos_uno_y_uno(tmp_path):
    """Es el formato interno de toda la app, y conviene fijarlo por escrito."""
    ruta = tmp_path / "prueba.wav"
    audio.escribir_wav(ruta, seno(440.0, amplitud=0.9))
    muestras, _ = audio.leer_wav(ruta)

    assert muestras.dtype == np.float32
    assert muestras.min() >= -1.0
    assert muestras.max() <= 1.0


def test_los_valores_fuera_de_rango_se_recortan_en_vez_de_dar_la_vuelta(tmp_path):
    """
    Si una muestra vale 1.5 y la convertimos sin cuidado, el entero de 16 bits
    se desborda y ese instante suena como un chasquido violento. Recortamos.
    """
    exagerada = np.array([0.0, 2.0, -2.0, 0.5], dtype=np.float32)
    ruta = tmp_path / "prueba.wav"

    audio.escribir_wav(ruta, exagerada)
    muestras, _ = audio.leer_wav(ruta)

    assert muestras[1] == pytest.approx(1.0, abs=1e-4)
    assert muestras[2] == pytest.approx(-1.0, abs=1e-4)


def test_se_puede_guardar_con_otra_frecuencia_de_muestreo(tmp_path):
    ruta = tmp_path / "prueba.wav"
    audio.escribir_wav(ruta, seno(440.0), frecuencia_muestreo=22050)
    _, frecuencia_muestreo = audio.leer_wav(ruta)
    assert frecuencia_muestreo == 22050


def test_un_archivo_estereo_se_convierte_a_mono(tmp_path):
    """
    Las grabaciones del celular suelen ser estéreo. La armónica es una sola
    fuente, así que promediamos los dos canales y seguimos.
    """
    import wave

    izquierdo = np.full(1000, 0.5, dtype=np.float32)
    derecho = np.full(1000, -0.1, dtype=np.float32)
    intercalado = np.empty(2000, dtype=np.float32)
    intercalado[0::2] = izquierdo
    intercalado[1::2] = derecho

    ruta = tmp_path / "estereo.wav"
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(2)
        archivo.setsampwidth(2)
        archivo.setframerate(FS)
        archivo.writeframes((intercalado * 32767).astype(np.int16).tobytes())

    muestras, _ = audio.leer_wav(ruta)

    assert len(muestras) == 1000
    # El promedio de 0.5 y -0.1 es 0.2.
    assert muestras[0] == pytest.approx(0.2, abs=1e-3)


def test_un_wav_que_no_sea_de_dieciseis_bits_da_un_error_claro(tmp_path):
    import wave

    ruta = tmp_path / "ocho_bits.wav"
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(1)          # 8 bits
        archivo.setframerate(FS)
        archivo.writeframes(b"\x80" * 100)

    with pytest.raises(ValueError, match="16 bits"):
        audio.leer_wav(ruta)


# =============================================================================
# Cortar en ventanas
# =============================================================================

def test_las_ventanas_tienen_el_tamano_configurado():
    muestras = seno(440.0, duracion_seg=1.0)
    bloques = audio.cortar_en_bloques(muestras)

    for _, bloque in bloques:
        assert len(bloque) == config.TAMANO_VENTANA


def test_las_ventanas_avanzan_de_a_un_salto():
    muestras = seno(440.0, duracion_seg=1.0)
    bloques = audio.cortar_en_bloques(muestras)

    for (inicio_anterior, _), (inicio_siguiente, _) in zip(bloques, bloques[1:]):
        assert inicio_siguiente - inicio_anterior == config.SALTO_VENTANA


def test_las_ventanas_se_superponen():
    """
    Es a propósito: cada ventana mira 46 ms de audio pero avanzamos solo 12 ms.
    Sin superposición tendríamos 21 mediciones por segundo y se perderían las
    notas rápidas.
    """
    assert config.SALTO_VENTANA < config.TAMANO_VENTANA


def test_una_senal_mas_corta_que_una_ventana_no_da_ningun_bloque():
    """No se puede analizar media ventana. Devolvemos lista vacía, sin romper."""
    corta = seno(440.0, duracion_seg=0.01)
    assert audio.cortar_en_bloques(corta) == []


def test_la_cantidad_de_ventanas_es_la_esperada():
    """
    Un segundo de audio a 44100 Hz, ventanas de 2048 avanzando de a 512:
    entran (44100 - 2048) / 512 + 1 = 83 ventanas.
    """
    muestras = seno(440.0, duracion_seg=1.0)
    bloques = audio.cortar_en_bloques(muestras)
    esperadas = (len(muestras) - config.TAMANO_VENTANA) // config.SALTO_VENTANA + 1
    assert len(bloques) == esperadas


def test_los_bloques_salen_del_lugar_correcto_de_la_senal():
    muestras = np.arange(10000, dtype=np.float32)
    bloques = audio.cortar_en_bloques(muestras)

    inicio, bloque = bloques[3]
    assert bloque[0] == inicio
    assert bloque[-1] == inicio + config.TAMANO_VENTANA - 1


# =============================================================================
# El volumen (RMS)
# =============================================================================

def test_el_silencio_tiene_volumen_cero():
    assert audio.volumen_rms(np.zeros(1000)) == 0.0


def test_el_rms_de_una_senoidal_es_su_amplitud_dividida_raiz_de_dos():
    """
    Es un resultado conocido de la trigonometría: el RMS de una onda senoidal
    vale su amplitud dividida por la raíz de 2, o sea el 70.7%.

    Lo verificamos porque si el RMS estuviera mal calculado, el umbral de
    volumen no significaría nada y toda la calibración sería a ciegas.
    """
    onda = seno(440.0, amplitud=1.0)
    assert audio.volumen_rms(onda) == pytest.approx(1.0 / np.sqrt(2), rel=0.01)


def test_el_rms_no_se_cancela_con_los_valores_negativos():
    """
    La mitad de las muestras de una onda son negativas. Un promedio común daría
    cero. Por eso se elevan al cuadrado antes de promediar.
    """
    onda = seno(440.0, amplitud=0.5)
    assert np.mean(onda) == pytest.approx(0.0, abs=1e-3)   # el promedio común da 0
    assert audio.volumen_rms(onda) > 0.3                   # el RMS, no


def test_mas_amplitud_es_mas_volumen():
    flojo = audio.volumen_rms(seno(440.0, amplitud=0.1))
    fuerte = audio.volumen_rms(seno(440.0, amplitud=0.8))
    assert fuerte > flojo


def test_un_bloque_vacio_no_rompe():
    assert audio.volumen_rms(np.array([])) == 0.0


def test_el_umbral_de_config_separa_bien_el_ruido_de_una_nota():
    """
    Comprueba que el valor por defecto de UMBRAL_VOLUMEN_RMS sea razonable:
    tiene que dejar pasar una nota tocada flojo y frenar el ruido de fondo.

    Si este test falla después de calibrar con el micrófono real, es señal de
    que el umbral quedó demasiado alto o demasiado bajo.
    """
    from herramientas import generar_wav

    nota_floja = seno(440.0, amplitud=0.05)
    ruido = generar_wav.generar_ruido(0.5, FS, volumen=0.002)

    assert audio.volumen_rms(nota_floja) > config.UMBRAL_VOLUMEN_RMS
    assert audio.volumen_rms(ruido) < config.UMBRAL_VOLUMEN_RMS
