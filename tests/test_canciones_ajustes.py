"""
Tests de armonica/canciones_ajustes.py — qué audio es la base y dónde cae el
compás 1, por canción.

Cómo correrlos:   python -m pytest tests/test_canciones_ajustes.py -v
"""

import json
import os

import pytest

from armonica import bandinabox, canciones, canciones_ajustes
from tests.test_bandinabox import blues_en_fa


def test_sin_archivo_no_hay_ajustes(tmp_path):
    assert canciones_ajustes.cargar(str(tmp_path)) == {}


def test_guardar_y_volver_a_leer(tmp_path):
    quedo = canciones_ajustes.guardar("Georgia", {"audio": "base.wav", "compas1_seg": 7.3846},
                                      str(tmp_path))
    assert quedo == {"audio": "base.wav", "compas1_seg": 7.385}
    assert canciones_ajustes.cargar(str(tmp_path)) == {"Georgia": quedo}
    with open(os.path.join(str(tmp_path), "_canciones.json"), encoding="utf-8") as archivo:
        assert json.load(archivo)["Georgia"]["audio"] == "base.wav"


def test_guardar_pisa_solo_lo_que_viene(tmp_path):
    canciones_ajustes.guardar("Georgia", {"audio": "base.wav", "compas1_seg": 7.4}, str(tmp_path))
    quedo = canciones_ajustes.guardar("Georgia", {"compas1_seg": 3.7}, str(tmp_path))
    assert quedo == {"audio": "base.wav", "compas1_seg": 3.7}


def test_un_compas_uno_borrado_vuelve_al_valor_por_defecto(tmp_path):
    canciones_ajustes.guardar("Georgia", {"compas1_seg": 7.4}, str(tmp_path))
    quedo = canciones_ajustes.guardar("Georgia", {"compas1_seg": None}, str(tmp_path))
    assert quedo["compas1_seg"] is None


@pytest.mark.parametrize("valor", ["hola", -1])
def test_un_compas_uno_invalido_se_rechaza(tmp_path, valor):
    with pytest.raises(ValueError):
        canciones_ajustes.guardar("Georgia", {"compas1_seg": valor}, str(tmp_path))


def test_sin_nombre_no_se_guarda(tmp_path):
    with pytest.raises(ValueError):
        canciones_ajustes.guardar("  ", {"audio": "x"}, str(tmp_path))


def test_un_archivo_roto_no_rompe(tmp_path):
    (tmp_path / "_canciones.json").write_text("{esto no es json", encoding="utf-8")
    assert canciones_ajustes.cargar(str(tmp_path)) == {}


def test_el_compas_uno_por_defecto_son_dos_compases_de_conteo():
    """A 65 BPM en 4/4, dos compases son 7,385 s: lo medido en una exportación real."""
    base = bandinabox.interpretar(bandinabox.escribir(blues_en_fa(bpm=65)))
    assert canciones_ajustes.compas1_por_defecto(base) == pytest.approx(7.385, abs=0.001)
    assert canciones_ajustes.compas1_por_defecto(None) is None


def test_los_ajustes_de_una_cancion_traen_los_valores_por_defecto(tmp_path):
    carpeta = tmp_path / "Georgia"
    carpeta.mkdir()
    (carpeta / "georgia.mgu").write_bytes(bandinabox.escribir(blues_en_fa(bpm=120)))
    (carpeta / "con el profe.m4a").write_bytes(b"")
    (carpeta / "base.wav").write_bytes(b"")
    cancion = canciones.leer_carpeta(str(carpeta))

    # Sin nada guardado: el primer audio (en orden alfabético) y dos compases.
    ajustes = canciones_ajustes.de_la_cancion(cancion, {})
    assert ajustes == {"audio": "base.wav", "compas1_seg": 4.0, "compas1_medido": False,
                       "compas1_origen": "supuesto"}

    # Con algo guardado, manda lo guardado.
    guardados = {"Georgia": {"audio": "con el profe.m4a", "compas1_seg": 3.5}}
    ajustes = canciones_ajustes.de_la_cancion(cancion, guardados)
    assert ajustes == {"audio": "con el profe.m4a", "compas1_seg": 3.5, "compas1_medido": True,
                       "compas1_origen": "marcado"}

    # Si lo midio la app en el audio, lo dice.
    guardados = {"Georgia": {"compas1_seg": 4.0, "compas1_origen": "audio"}}
    assert canciones_ajustes.de_la_cancion(cancion, guardados)["compas1_origen"] == "audio"

    # Un audio guardado que ya no está en la carpeta no se propone.
    guardados = {"Georgia": {"audio": "borrado.m4a"}}
    assert canciones_ajustes.de_la_cancion(cancion, guardados)["audio"] == "base.wav"
