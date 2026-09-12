"""
icono.py — Dibuja el icono de la app: una armónica. Sin bibliotecas.

    python -m herramientas.icono

Genera dos archivos:

    Armonica.ico           el icono del acceso directo del escritorio
    armonica/web/icono.png el favicon de la pestaña del navegador

POR QUE A MANO

Podríamos usar Pillow, pero el proyecto no lo tiene y no vale la pena
agregar una dependencia para un dibujo. Un PNG es una cabecera, filas de
píxeles comprimidas con zlib, y una suma de control: todo está en la
biblioteca estándar. Y un .ico moderno puede llevar un PNG adentro.

EL DIBUJO

Una placa oscura con las esquinas redondeadas (el fondo), y encima una
armónica en cobre —el color del soplado en la app— con sus diez agujeros.
Se dibuja al doble de tamaño y se reduce promediando de a cuatro píxeles,
que es la forma barata de que los bordes no salgan dentados.
"""

import os
import struct
import zlib

# Los colores de la app, para que el icono sea de la misma familia.
FONDO = (28, 26, 24)          # --panel
COBRE = (224, 164, 88)        # --cobre
COBRE_OSCURO = (184, 130, 63)
AGUJERO = (19, 18, 17)        # --fondo
LAVANDA = (185, 166, 255)     # --aguja

TAMANO = 256
SUPERMUESTREO = 2


def _dentro_de_rectangulo_redondeado(x, y, x0, y0, x1, y1, radio):
    """Si el punto cae dentro de un rectángulo con esquinas redondeadas."""
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    # Los cuatro círculos de las esquinas: si el punto está en la zona de
    # una esquina, tiene que estar dentro de su círculo.
    cx = x0 + radio if x < x0 + radio else (x1 - radio if x > x1 - radio else x)
    cy = y0 + radio if y < y0 + radio else (y1 - radio if y > y1 - radio else y)
    return (x - cx) ** 2 + (y - cy) ** 2 <= radio ** 2


def pintar_pixel(x, y, escala):
    """El color RGBA de un punto del lienzo, en coordenadas de 256."""
    x, y = x / escala, y / escala

    # 1. La placa de fondo
    if not _dentro_de_rectangulo_redondeado(x, y, 8, 8, 248, 248, 52):
        return (0, 0, 0, 0)
    color = FONDO

    # 2. El cuerpo de la armónica: un rectángulo horizontal en cobre
    if _dentro_de_rectangulo_redondeado(x, y, 28, 84, 228, 172, 18):
        # La tapa de arriba un poco más clara y la de abajo más oscura, como
        # las dos placas metálicas de una armónica de verdad.
        color = COBRE if y < 128 else COBRE_OSCURO

        # 3. Los diez agujeros, en la franja del medio
        if 114 <= y <= 142:
            ancho_agujero = 12
            paso = 19.2
            for numero in range(10):
                izquierda = 38 + numero * paso
                if izquierda <= x <= izquierda + ancho_agujero:
                    color = AGUJERO
                    break

    # 4. Una línea lavanda finita abajo: la aguja de afinación de la app
    if 196 <= y <= 202 and 60 <= x <= 196:
        color = LAVANDA

    return color + (255,)


def dibujar():
    """Devuelve las filas RGBA del icono, ya reducidas al tamaño final."""
    grande = TAMANO * SUPERMUESTREO
    lienzo = [[pintar_pixel(x, y, SUPERMUESTREO) for x in range(grande)]
              for y in range(grande)]

    filas = []
    for y in range(TAMANO):
        fila = bytearray()
        for x in range(TAMANO):
            # El promedio de los cuatro píxeles que caen en este.
            muestras = [lienzo[y * 2 + dy][x * 2 + dx] for dy in (0, 1) for dx in (0, 1)]
            for canal in range(4):
                fila.append(sum(m[canal] for m in muestras) // 4)
        filas.append(bytes(fila))
    return filas


def como_png(filas):
    """Arma un PNG RGBA de 8 bits a partir de filas de bytes."""
    def pedazo(tipo, datos):
        cuerpo = tipo + datos
        return (struct.pack(">I", len(datos)) + cuerpo
                + struct.pack(">I", zlib.crc32(cuerpo) & 0xFFFFFFFF))

    alto = len(filas)
    ancho = len(filas[0]) // 4
    cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0)
    # Cada fila lleva adelante un byte que dice qué filtro usa: 0 = ninguno.
    crudo = b"".join(b"\x00" + fila for fila in filas)
    return (b"\x89PNG\r\n\x1a\n"
            + pedazo(b"IHDR", cabecera)
            + pedazo(b"IDAT", zlib.compress(crudo, 9))
            + pedazo(b"IEND", b""))


def como_ico(png):
    """Un .ico con un solo PNG adentro. 0 en ancho y alto significa 256."""
    cabecera = struct.pack("<HHH", 0, 1, 1)
    entrada = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 6 + 16)
    return cabecera + entrada + png


def generar(carpeta=None):
    if carpeta is None:
        carpeta = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    png = como_png(dibujar())

    ruta_ico = os.path.join(carpeta, "Armonica.ico")
    ruta_png = os.path.join(carpeta, "armonica", "web", "icono.png")
    with open(ruta_ico, "wb") as archivo:
        archivo.write(como_ico(png))
    with open(ruta_png, "wb") as archivo:
        archivo.write(png)
    return ruta_ico, ruta_png


if __name__ == "__main__":
    for ruta in generar():
        print("escrito", ruta, os.path.getsize(ruta), "bytes")
