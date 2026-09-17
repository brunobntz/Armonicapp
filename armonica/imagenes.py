"""
imagenes.py — Mostrar en el navegador una foto que el navegador no sabe abrir.

Las fotos del iPhone vienen en .HEIC, y ningún navegador las muestra. Para
verlas en la app hay que convertirlas a JPG, y eso necesita dos bibliotecas
que no vienen con Python: Pillow, y pillow-heif, que le enseña a Pillow a
leer HEIC. Son OPCIONALES, como pypdf para los apuntes en PDF: sin ellas
la app anda igual, y en el lugar de la foto dice cómo instalarlas.

Los JPG van a una caché aparte, material/_cache/, y NUNCA a la carpeta de
la canción: esa carpeta es del usuario y la app solo la lee. El nombre del
JPG sale de la ruta y de la fecha del original, así una foto reemplazada por
otra con el mismo nombre se vuelve a convertir sola.
"""

import hashlib
import os

CARPETA_CACHE = os.path.join("material", "_cache")
EXTENSIONES_HEIC = (".heic", ".heif")
COMO_INSTALAR = "pip install pillow-heif"


def es_heic(ruta):
    return str(ruta).lower().endswith(EXTENSIONES_HEIC)


def hay_soporte_heic():
    """Si están las dos bibliotecas que hacen falta para leer un .HEIC."""
    try:
        import pillow_heif  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    return True


def como_jpg(ruta, carpeta_cache=None, lado_maximo=2000):
    """
    La ruta de un JPG que el navegador puede mostrar.

    Si la foto ya es JPG o PNG, es ella misma. Si es HEIC, se convierte una
    vez a la caché y las próximas veces se devuelve la que ya está. Se achica
    a `lado_maximo` píxeles del lado más largo: una foto de iPhone de 12
    megapíxeles pesa 3 MB y en pantalla no hace falta ni la mitad.

    Levanta RuntimeError, con el comando para instalar, si faltan las
    bibliotecas.
    """
    if not es_heic(ruta):
        return ruta
    if not hay_soporte_heic():
        raise RuntimeError(
            "Para mostrar una foto .HEIC hacen falta dos bibliotecas que no "
            f"vienen con Python. Se instalan una sola vez con:  {COMO_INSTALAR}"
        )

    carpeta_cache = carpeta_cache or CARPETA_CACHE
    destino = os.path.join(carpeta_cache, _nombre_en_cache(ruta))
    if os.path.isfile(destino):
        return destino

    import pillow_heif
    from PIL import Image
    pillow_heif.register_heif_opener()

    os.makedirs(carpeta_cache, exist_ok=True)
    with Image.open(ruta) as imagen:
        imagen = imagen.convert("RGB")
        imagen.thumbnail((lado_maximo, lado_maximo))
        imagen.save(destino, "JPEG", quality=88)
    return destino


def _nombre_en_cache(ruta):
    ruta = os.path.abspath(ruta)
    huella = hashlib.sha1(f"{ruta}|{os.path.getmtime(ruta)}".encode("utf-8")).hexdigest()[:16]
    return f"{os.path.splitext(os.path.basename(ruta))[0]}-{huella}.jpg"
