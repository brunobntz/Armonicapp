"""
Abre la app sin ventana negra: lo ejecuta el acceso directo de la versión
instalada con pythonw.exe. Todo lo que hace está en armonica/lanzador.py.
"""

import sys

from armonica import lanzador

sys.exit(lanzador.main())
