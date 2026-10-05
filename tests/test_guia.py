"""
Tests de la guía (armonica/web/guia.html): que esté entera, que no tenga
jerga y que la app la enlace. Que cada imagen exista lo prueba
test_cada_imagen_de_la_guia_existe_y_no_es_enorme, que se agrega con las
capturas.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_guia.py -v
"""

import os
from html.parser import HTMLParser

from tests.test_textos import INDEX, JERGA, TextoVisible

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIA = os.path.join(RAIZ, "armonica", "web", "guia.html")

CAPITULOS = ("instalar", "primeros-pasos", "en-vivo", "frases", "canciones", "aprendizaje",
             "teoria", "historial", "coach", "cerrar", "si-algo-no-anda", "version-nueva")

# Además de la jerga de la app: lo que el profe no tiene por qué leer. "API"
# no está: es el nombre que le dan a la clave en los sitios donde se saca.
JERGA_DE_LA_GUIA = JERGA + ("LLM_", "127.0.0.1", "localhost", "pythonw", "servidor", "puerto")


class Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.enlaces = []

    def handle_starttag(self, etiqueta, atributos):
        propios = dict(atributos)
        if propios.get("id"):
            self.ids.append(propios["id"])
        if etiqueta == "a":
            self.enlaces.append(propios)


def leer(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        return archivo.read()


def test_la_guia_tiene_todos_los_capitulos_en_orden():
    lector = Ids()
    lector.feed(leer(GUIA))
    encontrados = [id_ for id_ in lector.ids if id_ in CAPITULOS]
    assert encontrados == list(CAPITULOS)
    assert "bandinabox" in lector.ids


def test_el_indice_lleva_a_cada_capitulo():
    lector = Ids()
    lector.feed(leer(GUIA))
    destinos = {enlace.get("href") for enlace in lector.enlaces}
    for capitulo in CAPITULOS:
        assert f"#{capitulo}" in destinos, f"el índice no lleva a {capitulo}"


def test_la_guia_no_tiene_jerga():
    lector = TextoVisible()
    lector.feed(leer(GUIA))
    visible = " ".join(lector.textos)
    for palabra in JERGA_DE_LA_GUIA:
        assert palabra not in visible, f"{palabra!r} aparece en la guía"


def test_la_app_enlaza_la_guia_en_otra_pestana():
    """
    Un <a> y no una solapa: las solapas son botones con data-panel, y
    configurarSolapas() escondería todos los paneles si hubiera una sin él.
    """
    lector = Ids()
    lector.feed(leer(INDEX))
    guia = [enlace for enlace in lector.enlaces if enlace.get("href") == "guia.html"]
    assert len(guia) == 1
    assert guia[0].get("target") == "_blank"
    assert "solapa" not in (guia[0].get("class") or "").split()
