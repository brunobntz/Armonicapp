"""
consola.py — Un arreglo chico pero necesario para la terminal de Windows.

EL PROBLEMA

Windows viene de una época anterior a Unicode. Por defecto, la consola de
PowerShell escribe usando una tabla de caracteres vieja llamada cp1252, que
tiene 256 símbolos y NO incluye las flechas ↑ ↓.

Si le pedís a Python que imprima una flecha en esa consola, el programa no
muestra un cuadradito ni un signo de pregunta: se cae con un error feo,
UnicodeEncodeError, y perdés todo lo que estabas haciendo.

Como decidimos usar flechas para la tablatura (↑4, ↓4', ↓3''), esto nos afecta
en cada línea que imprimimos. Hay que resolverlo una vez, bien, y olvidarse.

LA SOLUCIÓN

Le decimos a Python que escriba la salida en UTF-8, que es la codificación
moderna y tiene todos los símbolos. `sys.stdout.reconfigure()` existe desde
Python 3.7 justamente para esto.

`errors="replace"` es un cinturón de seguridad: si aun así apareciera un
carácter imposible de mostrar, imprime un "?" en vez de tirar el programa
abajo. Que la app se caiga en medio de una sesión de práctica por un símbolo
sería absurdo.

CÓMO SE USA

Cualquier archivo que imprima cosas llama a preparar_consola() al empezar.
Es una función explícita y no algo que pase solo al importar el paquete: los
efectos ocultos son difíciles de entender cuando algo falla.

SI IGUAL SE VEN MAL LAS FLECHAS

El problema pasa a ser la fuente de la terminal, no Python. En Windows
Terminal (el que viene con Windows 11) andan bien. En la consola vieja
(cmd.exe) puede que no. En ese caso, poné NOTACION = "guion" en config.py y
listo: la app funciona igual, solo cambia cómo se ve.
"""

import sys


def preparar_consola():
    """
    Deja la salida de la terminal lista para imprimir flechas y acentos.

    Se puede llamar varias veces sin problema. Si algo sale mal (por ejemplo
    porque la salida está redirigida a un archivo) no hace nada y sigue: es una
    mejora, no un requisito para que la app funcione.
    """
    for flujo in (sys.stdout, sys.stderr):
        # Algunos entornos reemplazan sys.stdout por objetos que no tienen
        # reconfigure(). Preguntamos antes de llamar.
        if hasattr(flujo, "reconfigure"):
            try:
                flujo.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                # No pudimos. No es grave: seguimos con lo que haya.
                pass
