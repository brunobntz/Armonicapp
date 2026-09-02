"""
conftest.py — Configuración común de todos los tests.

`conftest.py` es un nombre especial: pytest lo busca solo, sin que haya que
importarlo desde ningún lado. Lo que definas acá está disponible en todos los
archivos de test de la carpeta.

POR QUÉ EXISTE ESTE ARCHIVO

Al cambiar la notación por defecto a flechas, veintiún tests se rompieron de
golpe. Ninguno tenía un error: todos esperaban ver "-4" y de repente la app
devolvía "↓4".

Eso es una señal, y vale la pena entenderla: **los tests no pueden depender de
una preferencia que el usuario puede cambiar en config.py**. Si dependen, cada
vez que ajustes un parámetro para tocar mejor, media suite se pone en rojo sin
que nada esté realmente mal. Y peor: te acostumbrás a ver rojo y dejás de
prestarle atención.

La solución es fijar la configuración durante los tests. Así los tests miden el
comportamiento del código, no tus gustos.

La notación en sí se prueba aparte, en los tests que la comparan explícitamente
en las dos formas. Esos sí tienen que verificar las flechas.
"""

import pytest

import config


@pytest.fixture(autouse=True)
def notacion_fija(monkeypatch):
    """
    Fija la notación en "guion" durante todos los tests.

    `autouse=True` significa que se aplica sola a cada test, sin que haya que
    pedirla. `monkeypatch` deshace el cambio al terminar cada test, así que la
    configuración real de config.py queda intacta.

    Elegimos "guion" y no "flechas" simplemente porque los guiones son más
    fáciles de leer y de escribir dentro del código de los tests.
    """
    monkeypatch.setattr(config, "NOTACION", "guion")


@pytest.fixture(autouse=True)
def preferencia_fija(monkeypatch):
    """
    Fija también la resolución de ambigüedades, por la misma razón.

    Si algún día cambiás PREFERENCIA_AMBIGUEDAD a "soplado" porque estás
    transcribiendo melodías de 1a posición, los tests tienen que seguir en
    verde. El test que verifica que esa preferencia funciona la cambia a
    propósito, y eso está bien porque es lo que está midiendo.
    """
    monkeypatch.setattr(config, "PREFERENCIA_AMBIGUEDAD", "aspirado")
