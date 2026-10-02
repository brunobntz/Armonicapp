"""
version.py — Qué versión de la app es esta.

Sale del archivo VERSION de la raíz, que es lo único que hay que cambiar al
sacar una nueva: lo lee la pantalla (Ajustes), /api/hola y el armado del
instalador para el nombre del .exe. En la versión instalada VERSION queda al
lado de la carpeta armonica\\, igual que en el repo.
"""

import os

RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")


def version():
    try:
        with open(RUTA, encoding="utf-8") as archivo:
            return archivo.read().strip()
    except OSError:
        return "sin versión"
