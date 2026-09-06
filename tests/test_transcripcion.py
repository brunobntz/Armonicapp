"""
Tests de armonica/transcripcion.py — la cadena de un .wav a notas tocadas.

SIN MICROFONO. El audio se fabrica con herramientas/generar_wav.py, así que
sabemos exactamente qué notas tiene que salir y podemos medir el error.

Cómo correrlos:   python -m pytest tests/test_transcripcion.py -v
"""

import os

import numpy as np
import pytest

import config
from armonica import audio, transcripcion
from herramientas import generar_wav


def escribir(tmp_path, tablaturas, tonalidad="C", duracion_nota=0.45,
             volumen=None):
    """Fabrica un .wav con esas notas y devuelve su ruta."""
    muestras, _ = generar_wav.generar_secuencia(
        tablaturas, tonalidad, duracion_nota=duracion_nota)
    if volumen is not None:
        muestras = muestras * volumen
    ruta = tmp_path / "prueba.wav"
    audio.escribir_wav(ruta, muestras)
    return str(ruta)


# =============================================================================
# La cadena completa
# =============================================================================

def test_transcribe_un_archivo_a_las_notas_que_tenia(tmp_path):
    ruta = escribir(tmp_path, ["-2", "-3''", "4", "-4"])

    resultado = transcripcion.desde_archivo(ruta, "C")

    assert [e.como_tab() for e in resultado.reconocidas] == ["-2", "-3''", "4", "-4"]


def test_trae_todo_lo_que_hace_falta_para_seguir_trabajando(tmp_path):
    """
    Devuelve las muestras y la frecuencia, no solo los eventos.

    Las necesitan los dos que la usan: el modo --wav para guardar la sesión
    con su audio, y el servidor para dejar el audio al lado de la frase.
    """
    ruta = escribir(tmp_path, ["4", "-4"])

    resultado = transcripcion.desde_archivo(ruta, "C")

    assert resultado.muestras is not None
    assert resultado.frecuencia_muestreo == config.FRECUENCIA_MUESTREO
    assert resultado.mediciones
    assert resultado.duracion_seg > 1.0


def test_marca_la_escala_cuando_se_le_dice_cual(tmp_path):
    ruta = escribir(tmp_path, ["4", "-4"])

    sin_escala = transcripcion.desde_archivo(ruta, "C")
    con_escala = transcripcion.desde_archivo(ruta, "C", 1, "pentatonica_mayor")

    assert all(e.en_escala is False for e in sin_escala.eventos)
    assert any(e.en_escala for e in con_escala.reconocidas)


def test_un_audio_bajito_se_normaliza_antes_de_analizar(tmp_path):
    """
    El caso de la primera grabación de este proyecto: pico 0.03 y una sola
    nota detectada en 18 segundos. Sin normalizar, todo esto sería silencio.
    """
    ruta = escribir(tmp_path, ["4", "-4", "-5", "6"], volumen=0.04)

    resultado = transcripcion.desde_archivo(ruta, "C")

    assert len(resultado.reconocidas) == 4


# =============================================================================
# La cobertura: ¿es esta la armónica que dijiste?
# =============================================================================

def test_la_cobertura_es_uno_cuando_todo_cae_en_la_armonica(tmp_path):
    ruta = escribir(tmp_path, ["-2", "4", "-4", "6"])

    resultado = transcripcion.desde_archivo(ruta, "C")

    assert resultado.cobertura == pytest.approx(1.0, abs=0.01)


def test_la_cobertura_baja_cuando_el_audio_se_va_de_rango(tmp_path):
    """
    El registro grave de una armónica en Sol, leído como si fuera en Do.

    Esas notas están por debajo del agujero 1 de una armónica en Do: no
    existen ahí. La mitad de lo tocado se pierde, y este número lo dice.
    """
    ruta = escribir(tmp_path, ["1", "-1", "2", "-2", "3", "-3"], tonalidad="G")

    resultado = transcripcion.desde_archivo(ruta, "C")

    assert resultado.cobertura < transcripcion.COBERTURA_MINIMA


def test_la_cobertura_no_detecta_la_armonica_equivocada(tmp_path):
    """
    ESTE TEST DOCUMENTA UN LIMITE, NO UN LOGRO.

    Lo mismo tocado en una armónica en La, en el registro medio, leído como si
    fuera en Do: la cobertura da 1.0 y no se queja de nada. No es una falla
    del control: es que una armónica en Do, con bends, alcanza casi todas las
    notas del registro medio. Esas notas SON tocables en Do; lo que cambia es
    la tablatura.

    Está escrito para que nadie —incluido el que escribió el módulo— crea que
    esta cobertura sirve para adivinar de qué armónica es una grabación. Para
    eso está --que-tono, que compara las cuatro armónicas entre sí.
    """
    ruta = escribir(tmp_path, ["-2", "4", "-4", "6"], tonalidad="A")

    resultado = transcripcion.desde_archivo(ruta, "C")

    assert resultado.cobertura == pytest.approx(1.0, abs=0.01)


# =============================================================================
# La revisión, que es la que decide si el audio sirve
# =============================================================================

def test_un_audio_limpio_pasa_la_revision(tmp_path):
    ruta = escribir(tmp_path, ["-2", "4", "-4", "6"])
    resultado = transcripcion.desde_archivo(ruta, "C")

    sirve, motivo, avisos = transcripcion.revisar(resultado, "C")

    assert sirve is True
    assert motivo == ""
    assert avisos == []


def test_un_audio_mudo_dice_que_esta_mudo(tmp_path):
    """
    El silencio también da puntaje de monofonía 0, igual que una banda.

    Son dos problemas distintos y merecen dos mensajes distintos: decirle "no
    parece una armónica sola" a un archivo mudo manda a buscar el error donde
    no está.
    """
    ruta = tmp_path / "callado.wav"
    audio.escribir_wav(ruta, np.zeros(config.FRECUENCIA_MUESTREO, dtype=np.float32))
    resultado = transcripcion.desde_archivo(str(ruta), "C")

    sirve, motivo, _ = transcripcion.revisar(resultado, "C")

    assert sirve is False
    assert "umbral de volumen" in motivo
    assert "monofon" not in motivo


def test_un_audio_con_varias_notas_a_la_vez_se_rechaza(tmp_path):
    """
    LA REVISION MAS IMPORTANTE.

    Si Bruno sube un tema con banda, YIN devuelve frecuencias con toda
    seriedad y saldría una frase de referencia inventada, que después arruina
    cada práctica contra ella. Es el mismo control que hace --que-tono.

    Acá el "tema con banda" son cuatro notas sonando juntas, que es justo lo
    que un detector monofónico no puede resolver.
    """
    juntas = sum(
        generar_wav.generar_nota(frecuencia, 3.0, volumen=0.25)
        for frecuencia in (196.0, 246.94, 293.66, 392.0)
    )
    ruta = tmp_path / "banda.wav"
    audio.escribir_wav(ruta, juntas)
    resultado = transcripcion.desde_archivo(str(ruta), "C")

    sirve, motivo, _ = transcripcion.revisar(resultado, "C")

    assert sirve is False
    assert "monofon" in motivo


def test_un_audio_fuera_de_rango_avisa_pero_deja_seguir(tmp_path):
    """
    La diferencia entre un motivo y un aviso.

    Un audio polifónico da notas INVENTADAS: no hay nada que hacer con eso.
    Un audio que se va de rango da notas reales a las que les falta un pedazo.
    Se avisa, y el que decide sos vos: puede que la grabación sea de otra
    armónica, o puede que sea un ruido grave al principio.
    """
    ruta = escribir(tmp_path, ["1", "-1", "2", "-2", "3", "-3"], tonalidad="G")
    resultado = transcripcion.desde_archivo(ruta, "C")

    sirve, motivo, avisos = transcripcion.revisar(resultado, "C")

    assert sirve is True
    assert motivo == ""
    assert avisos
    assert "--que-tono" in avisos[0]


# =============================================================================
# Los audios que no son .wav
#
# WhatsApp manda .opus, el iPhone manda .m4a. Ninguno de los dos se puede leer
# con la biblioteca estandar: hace falta ffmpeg, que no viene con Windows.
# =============================================================================

def test_un_wav_no_pasa_por_ffmpeg(tmp_path, monkeypatch):
    """
    El camino normal no llama a ffmpeg ni una vez.

    Importa: si un .wav pasara por la conversion, la app dejaria de funcionar
    en una maquina sin ffmpeg, que es la mayoria de las maquinas con Windows.
    """
    llamadas = []
    monkeypatch.setattr(audio, "convertir_a_wav",
                        lambda *a, **k: llamadas.append(a))

    ruta = escribir(tmp_path, ["4", "-4"])
    muestras, frecuencia = transcripcion.leer_cualquier_audio(ruta)

    assert llamadas == []
    assert len(muestras) > 0
    assert frecuencia == config.FRECUENCIA_MUESTREO


def test_un_m4a_se_convierte_antes_de_leerlo(tmp_path, monkeypatch):
    """
    Se verifica que se llame a la conversion, no que ffmpeg funcione.

    Probar ffmpeg de verdad significaria exigirlo instalado para correr los
    tests, y estos tests tienen que andar en cualquier máquina. Lo que este
    proyecto controla es la decisión de convertir; que ffmpeg decodifique AAC
    es problema de ffmpeg.
    """
    real = escribir(tmp_path, ["4", "-4", "-5"])
    disfrazado = tmp_path / "de_whatsapp.m4a"
    disfrazado.write_bytes(b"finjo ser un m4a")

    def convertir_falso(origen, destino, frecuencia_muestreo=None):
        with open(real, "rb") as entrada, open(destino, "wb") as salida:
            salida.write(entrada.read())
        return str(destino)

    monkeypatch.setattr(audio, "convertir_a_wav", convertir_falso)

    muestras, _ = transcripcion.leer_cualquier_audio(str(disfrazado))

    assert len(muestras) > 0


def test_sin_ffmpeg_el_error_dice_como_instalarlo(tmp_path, monkeypatch):
    """
    ffmpeg no viene con Windows, así que este es el caso más probable de todos.

    Un "FileNotFoundError: ffmpeg" no le sirve a nadie; el comando para
    instalarlo, sí.
    """
    monkeypatch.setattr(audio, "hay_ffmpeg", lambda: False)
    origen = tmp_path / "audio_de_lean.m4a"
    origen.write_bytes(b"lo que sea")

    with pytest.raises(ValueError) as fallo:
        audio.convertir_a_wav(str(origen), str(tmp_path / "salida.wav"))

    assert "winget install ffmpeg" in str(fallo.value)
    assert "audio_de_lean.m4a" in str(fallo.value)


def test_la_conversion_no_deja_temporales(tmp_path, monkeypatch):
    """El .wav convertido es de paso: si no se borrara, se acumularian."""
    temporales = tmp_path / "temporales"
    temporales.mkdir()
    monkeypatch.setattr(transcripcion.tempfile, "tempdir", str(temporales))

    disfrazado = tmp_path / "roto.mp3"
    disfrazado.write_bytes(b"no se puede convertir")
    monkeypatch.setattr(audio, "hay_ffmpeg", lambda: False)

    with pytest.raises(ValueError):
        transcripcion.leer_cualquier_audio(str(disfrazado))

    assert os.listdir(str(temporales)) == []


def test_una_base_bajita_pasa_el_control_y_igual_pierde_notas(tmp_path):
    """
    EL LIMITE MAS IMPORTANTE DE TODOS, Y EL MENOS INTUITIVO.

    "Si la armonica es el sonido preponderante, ¿por que no la puedo tomar?"
    Porque el control de monofonia no es lo que se rompe primero: se rompe la
    transcripcion, y antes.

    Con la base al 20% del volumen de la melodia, el puntaje de monofonia da
    0.83 y pasa el control con comodidad. Pero de las cinco notas tocadas solo
    se reconocen las tres ultimas: las dos primeras se pierden y NADIE AVISA,
    porque segmentar descarta las ventanas que no mapean en vez de marcarlas.

    O sea que el rango peligroso no es el que la app rechaza —ahi no queda
    ninguna nota que rescatar— sino el que ACEPTA con una base bajita. Por eso
    la recomendacion es grabar la armonica sola y no "que se escuche fuerte".
    """
    melodia, _ = generar_wav.generar_secuencia(
        ["-2", "4", "-4", "-5", "6"], "C", duracion_nota=0.45)
    base = sum(
        generar_wav.generar_nota(frecuencia, len(melodia) / 44100.0, volumen=0.2 / 3)
        for frecuencia in (98.0, 146.83, 196.0)
    )

    ruta = tmp_path / "con_base.wav"
    audio.escribir_wav(ruta, melodia + base[:len(melodia)])
    resultado = transcripcion.desde_archivo(str(ruta), "C")

    sirve, _, _ = transcripcion.revisar(resultado, "C")

    assert sirve is True                                   # el control la deja pasar
    assert [e.como_tab() for e in resultado.reconocidas] == ["-4", "-5", "6"]
    assert len(resultado.reconocidas) < 5                  # y perdio notas igual
