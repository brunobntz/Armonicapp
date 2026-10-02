"""
Tests de main.py — lo que no es de ningún módulo: cómo se arranca.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_main.py -v
"""

import main


def test_para_la_web_solo_cuenta_lo_escrito():
    """
    El "C" por defecto de --tonalidad no puede pisar la armónica elegida en
    Ajustes: solo cuenta lo que se escribió.
    """
    assert main._explicitos_para_la_web(["--web"]) == \
        {"tonalidad": None, "posicion": None, "escala": None}
    assert main._explicitos_para_la_web(["--web", "--tonalidad", "A", "--posicion", "2"]) == \
        {"tonalidad": "A", "posicion": 2, "escala": None}
