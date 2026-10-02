"""
Tests de armonica/ajustes.py — lo que se elige en Ajustes, guardado para la
próxima vez.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_ajustes.py -v
"""

import json
import types

import pytest

from armonica import ajustes


def test_sin_archivo_no_hay_ajustes(tmp_path):
    assert ajustes.cargar(str(tmp_path / "ajustes.json")) == {}


def test_guardar_y_volver_a_leer(tmp_path):
    ruta = str(tmp_path / "ajustes.json")
    elegidos = {"microfono": "Micrófono (USB Audio)", "umbral": 0.0042,
                "tonalidad": "A", "posicion": 2, "escala": "blues_mayor",
                "primeros_pasos": True}
    assert ajustes.guardar(elegidos, ruta) == elegidos
    assert ajustes.cargar(ruta) == elegidos
    with open(ruta, encoding="utf-8") as archivo:
        assert json.load(archivo)["microfono"] == "Micrófono (USB Audio)"


def test_guardar_pisa_solo_lo_que_viene(tmp_path):
    ruta = str(tmp_path / "ajustes.json")
    ajustes.guardar({"tonalidad": "A", "umbral": 0.004}, ruta)
    assert ajustes.guardar({"umbral": 0.006}, ruta) == {"tonalidad": "A", "umbral": 0.006}


@pytest.mark.parametrize("clave, valor", [
    ("tonalidad", "H"), ("posicion", 7), ("posicion", True), ("umbral", 0),
    ("umbral", "alto"), ("escala", "inventada"), ("primeros_pasos", "si"),
    ("microfono", 3), ("otra_cosa", 1), ("tonalidad", ["C"]), ("escala", {}),
])
def test_un_ajuste_invalido_no_se_guarda(tmp_path, clave, valor):
    ruta = str(tmp_path / "ajustes.json")
    with pytest.raises(ValueError):
        ajustes.guardar({clave: valor}, ruta)
    assert ajustes.cargar(ruta) == {}


def test_lo_invalido_en_el_archivo_se_ignora(tmp_path):
    """Un archivo editado a mano, o de otra versión, no rompe el arranque."""
    ruta = tmp_path / "ajustes.json"
    ruta.write_text(json.dumps({"tonalidad": "H", "umbral": 0.004, "vieja": 1}), encoding="utf-8")
    assert ajustes.cargar(str(ruta)) == {"umbral": 0.004}


def test_un_archivo_roto_no_rompe(tmp_path):
    ruta = tmp_path / "ajustes.json"
    ruta.write_text("{esto no es json", encoding="utf-8")
    assert ajustes.cargar(str(ruta)) == {}


def test_lo_invalido_por_tipo_en_el_archivo_se_ignora(tmp_path):
    """Valores que son listas o dicts no rompen cargar(), se filtran."""
    ruta = tmp_path / "ajustes.json"
    ruta.write_text(json.dumps({"tonalidad": ["C"], "escala": {"a": 1}, "umbral": 0.004}), encoding="utf-8")
    assert ajustes.cargar(str(ruta)) == {"umbral": 0.004}


def test_la_linea_de_comandos_le_gana_a_lo_guardado_y_lo_guardado_a_la_fabrica():
    assert ajustes.valores_de_arranque({}) == {"tonalidad": "C", "posicion": None, "escala": None}
    guardados = {"tonalidad": "A", "posicion": 2}
    assert ajustes.valores_de_arranque(guardados) == {"tonalidad": "A", "posicion": 2, "escala": None}
    assert ajustes.valores_de_arranque(guardados, tonalidad="D") == \
        {"tonalidad": "D", "posicion": 2, "escala": None}


def test_el_umbral_guardado_pisa_el_de_config():
    falso = types.SimpleNamespace(UMBRAL_VOLUMEN_RMS=0.01)
    ajustes.aplicar_a_config({}, falso)
    assert falso.UMBRAL_VOLUMEN_RMS == 0.01
    ajustes.aplicar_a_config({"umbral": 0.004}, falso)
    assert falso.UMBRAL_VOLUMEN_RMS == 0.004


def test_el_microfono_se_busca_por_nombre():
    """Windows repite el nombre una vez por API de audio: vale el primero."""
    entradas = [(0, "Asignador de sonido Microsoft - Input", 2),
                (1, "Micrófono (USB Audio)", 1),
                (7, "Micrófono (USB Audio)", 1)]
    assert ajustes.resolver_microfono(" micrófono (usb audio) ", entradas) == 1
    assert ajustes.resolver_microfono("Cámara", entradas) is None
    assert ajustes.resolver_microfono("", entradas) is None
