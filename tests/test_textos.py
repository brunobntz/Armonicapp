"""
Tests de los textos que ve el usuario de la versión instalada.

El profe no tiene terminal, ni .env, ni sabe qué es material/: nada de eso
puede aparecer en pantalla. Lo que es solo para Bruno va adentro de un
elemento con la clase solo-desarrollo, que la versión instalada oculta.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_textos.py -v
"""

import os
from html.parser import HTMLParser

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(RAIZ, "armonica", "web", "index.html")
JERGA = (".env", "CARPETA_", "material/", "pip install", "python main.py", "winget")


class TextoVisible(HTMLParser):
    """Junta el texto que no está adentro de un elemento solo-desarrollo."""

    VACIOS = {"br", "img", "input", "meta", "link", "hr", "source"}

    def __init__(self):
        super().__init__()
        self.pila = []      # (etiqueta, oculto)
        self.textos = []

    def handle_starttag(self, etiqueta, atributos):
        if etiqueta in self.VACIOS:
            return
        clases = (dict(atributos).get("class") or "").split()
        afuera = self.pila[-1][1] if self.pila else False
        self.pila.append((etiqueta, afuera or "solo-desarrollo" in clases
                          or etiqueta in ("script", "style")))

    def handle_endtag(self, etiqueta):
        for i in range(len(self.pila) - 1, -1, -1):
            if self.pila[i][0] == etiqueta:
                del self.pila[i:]
                return

    def handle_data(self, datos):
        if not (self.pila and self.pila[-1][1]):
            self.textos.append(datos)


def test_la_pagina_instalada_no_muestra_jerga():
    with open(INDEX, encoding="utf-8") as archivo:
        html = archivo.read()
    lector = TextoVisible()
    lector.feed(html)
    visible = " ".join(lector.textos)
    for palabra in JERGA:
        assert palabra not in visible, f"{palabra!r} se ve en la versión instalada"


def test_ningun_aviso_manda_a_la_terminal():
    for ruta in (os.path.join(RAIZ, "armonica", "web", "app.js"),
                 os.path.join(RAIZ, "armonica", "transcripcion.py")):
        with open(ruta, encoding="utf-8") as archivo:
            assert "python main.py" not in archivo.read(), ruta
