"""
Tests de armonica/canciones.py e imagenes.py — las carpetas de canciones.

Las carpetas se fabrican en un directorio temporal, con una base escrita con
bandinabox.escribir() y archivos vacíos con las extensiones que importan.

Cómo correrlos:   python -m pytest tests/test_canciones.py -v
"""

import inspect
import os
import re

import pytest

from armonica import bandinabox, canciones, imagenes
from tests.test_bandinabox import blues_en_fa


@pytest.fixture
def carpeta(tmp_path):
    georgia = tmp_path / "Georgia On My Mind"
    georgia.mkdir()
    (georgia / "georgia.MGU").write_bytes(bandinabox.escribir(blues_en_fa(bpm=65)))
    (georgia / "base de guitarra.m4a").write_bytes(b"")
    (georgia / "guitarra + armonica.m4a").write_bytes(b"")
    (georgia / "tablatura.HEIC").write_bytes(b"")
    (georgia / "letra.txt").write_text("Georgia, Georgia", encoding="utf-8")
    (georgia / "Thumbs.db").write_bytes(b"")

    sin_base = tmp_path / "Aunque a nadie ya le importe"
    sin_base.mkdir()
    (sin_base / "solo armonica.mp3").write_bytes(b"")
    (sin_base / "tab.jpg").write_bytes(b"")

    (tmp_path / "_cache").mkdir()
    (tmp_path / "suelto.mp3").write_bytes(b"")
    return str(tmp_path)


# =============================================================================
# La garantía más importante: este módulo NO ESCRIBE en la carpeta
# =============================================================================

def test_el_modulo_de_canciones_no_tiene_ninguna_apertura_en_modo_escritura():
    """
    La carpeta de canciones es material del profe. Igual que la de clases,
    se lee y no se toca. Mismo test que en test_clases.py.
    """
    fuente = inspect.getsource(canciones)
    for apertura in re.findall(r"open\(([^)]*)\)", fuente):
        assert not re.search(r"""["'][wax]""", apertura), \
            f"el modulo de canciones no puede escribir: open({apertura})"
    for marca in ("os.remove", "os.rename", "os.unlink", "shutil", "makedirs",
                  "write_text", "write_bytes", "rmtree", "os.rmdir", ".save("):
        assert marca not in fuente, f"el modulo de canciones no puede escribir: aparece {marca!r}"


def test_los_jpg_de_las_fotos_van_a_la_cache_y_no_a_la_carpeta(tmp_path, monkeypatch):
    """
    imagenes.py sí escribe, pero solo en su caché. Se verifica que el destino
    que calcula está en la caché y no al lado de la foto.
    """
    foto = tmp_path / "cancion" / "tab.HEIC"
    foto.parent.mkdir()
    foto.write_bytes(b"")
    cache = tmp_path / "_cache"

    monkeypatch.setattr(imagenes, "hay_soporte_heic", lambda: True)
    convertida = {}

    class ImagenFalsa:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def convert(self, _): return self
        def thumbnail(self, _): pass
        def save(self, destino, *_, **__):
            convertida["destino"] = destino
            open(destino, "wb").close()

    import sys, types
    pil = types.ModuleType("PIL")
    pil.Image = types.SimpleNamespace(open=lambda _: ImagenFalsa())
    monkeypatch.setitem(sys.modules, "PIL", pil)
    monkeypatch.setitem(sys.modules, "pillow_heif",
                        types.SimpleNamespace(register_heif_opener=lambda: None))

    destino = imagenes.como_jpg(str(foto), str(cache))
    assert os.path.dirname(destino) == str(cache)
    assert destino.endswith(".jpg")
    assert sorted(os.listdir(foto.parent)) == ["tab.HEIC"]

    # La segunda vez no convierte: ya está.
    convertida.clear()
    assert imagenes.como_jpg(str(foto), str(cache)) == destino
    assert convertida == {}


def test_sin_pillow_heif_el_error_dice_como_instalarlo(tmp_path, monkeypatch):
    monkeypatch.setattr(imagenes, "hay_soporte_heic", lambda: False)
    foto = tmp_path / "tab.HEIC"
    foto.write_bytes(b"")
    with pytest.raises(RuntimeError) as fallo:
        imagenes.como_jpg(str(foto), str(tmp_path / "_cache"))
    assert "pip install pillow-heif" in str(fallo.value)


def test_un_jpg_no_se_convierte():
    assert imagenes.como_jpg("foto.jpg") == "foto.jpg"


# =============================================================================
# Listar
# =============================================================================

def test_una_cancion_por_subcarpeta_y_nada_mas(carpeta):
    lista = canciones.listar(carpeta)
    assert [c.nombre for c in lista] == ["Aunque a nadie ya le importe", "Georgia On My Mind"]


def test_cada_archivo_va_a_su_lugar(carpeta):
    georgia = canciones.listar(carpeta)[1]
    assert georgia.archivo_base == "georgia.MGU"
    assert georgia.audios == ["base de guitarra.m4a", "guitarra + armonica.m4a"]
    assert georgia.imagenes == ["tablatura.HEIC"]
    assert georgia.documentos == ["letra.txt"]
    assert georgia.base is not None and georgia.base.bpm == 65
    assert georgia.error_base == ""


def test_una_cancion_sin_base_tambien_vale(carpeta):
    cancion = canciones.listar(carpeta)[0]
    assert cancion.base is None
    assert cancion.archivo_base == ""
    assert cancion.audios == ["solo armonica.mp3"]
    assert cancion.imagenes == ["tab.jpg"]
    assert cancion.como_diccionario("C")["ficha"] is None


def test_una_base_rota_no_rompe_la_lista(tmp_path):
    rota = tmp_path / "Rota"
    rota.mkdir()
    (rota / "rota.sgu").write_bytes(b"RIFF" * 10)
    cancion = canciones.listar(str(tmp_path))[0]
    assert cancion.base is None
    assert "Band-in-a-Box" in cancion.error_base


def test_dos_bases_usa_la_primera_y_avisa(tmp_path):
    doble = tmp_path / "Doble"
    doble.mkdir()
    (doble / "a.sgu").write_bytes(bandinabox.escribir(blues_en_fa(bpm=80)))
    (doble / "b.sgu").write_bytes(bandinabox.escribir(blues_en_fa(bpm=90)))
    cancion = canciones.listar(str(tmp_path))[0]
    assert cancion.base.bpm == 80
    assert any("2 bases" in aviso for aviso in cancion.base.avisos)


def test_una_carpeta_que_no_existe_da_una_lista_vacia():
    assert canciones.listar("no/existe") == []


def test_por_defecto_lee_de_material_canciones(tmp_path, monkeypatch):
    monkeypatch.delenv("CARPETA_CANCIONES", raising=False)
    assert canciones.carpeta_de_canciones(str(tmp_path / "no.env")) == \
        os.path.join("material", "canciones")


def test_el_env_puede_apuntar_a_otra_carpeta(tmp_path, monkeypatch):
    monkeypatch.delenv("CARPETA_CANCIONES", raising=False)
    env = tmp_path / ".env"
    env.write_text("CARPETA_CANCIONES=D:\\musica\\canciones\n", encoding="utf-8")
    assert canciones.carpeta_de_canciones(str(env)) == "D:\\musica\\canciones"


# =============================================================================
# Pedir un archivo sin salir de la carpeta
# =============================================================================

def test_la_ruta_de_un_archivo_queda_adentro_de_la_carpeta(carpeta):
    ruta = canciones.ruta_de_archivo("Georgia On My Mind", "base de guitarra.m4a", carpeta)
    assert ruta and ruta.startswith(os.path.abspath(carpeta))


@pytest.mark.parametrize("cancion, nombre", [
    ("..", "suelto.mp3"),
    ("Georgia On My Mind", "../suelto.mp3"),
    ("Georgia On My Mind", "..\\suelto.mp3"),
    ("", "tablatura.HEIC"),
    ("Georgia On My Mind", ""),
    ("Georgia On My Mind", "no-existe.m4a"),
    (".", "suelto.mp3"),
])
def test_los_pedidos_raros_se_rechazan(carpeta, cancion, nombre):
    assert canciones.ruta_de_archivo(cancion, nombre, carpeta) is None


# =============================================================================
# La ficha
# =============================================================================

def test_la_ficha_trae_el_cifrado_compas_por_compas(carpeta):
    ficha = canciones.listar(carpeta)[1].como_diccionario("C")["ficha"]
    assert (ficha["tonalidad"], ficha["bpm"], ficha["subdivision"]) == ("F", 65, 3)
    assert ficha["compases"] == 12
    bb7 = ficha["cifrado"][1]["acordes"]
    assert len(bb7) == 1
    assert (bb7[0]["tiempo"], bb7[0]["nombre"], bb7[0]["familia"]) == (1, "Bb7", "dominante")
    assert ficha["compases_de_cambio"] == [2, 3, 5, 7, 9, 10, 11, 12]
    assert ficha["tiene_melodia"] is False
    assert ficha["melodia"] is None


def test_la_melodia_sale_en_la_tablatura_de_la_armonica_elegida():
    """
    A 120 BPM en 4/4 cada compás dura dos segundos. Un Si4 (MIDI 71) en una
    armónica en Do es el 3 aspirado; un Do4 (60) es el 1 soplado; un Si3
    (59) queda por debajo del 1 soplado: esa armónica no lo tiene y queda
    como "·".
    """
    melodia = [bandinabox.NotaDeMelodia(0.0, 0.5, 71, 90),
               bandinabox.NotaDeMelodia(0.5, 0.5, 60, 90),
               bandinabox.NotaDeMelodia(2.0, 0.5, 59, 90)]
    base = bandinabox.interpretar(bandinabox.escribir(blues_en_fa(bpm=120, melodia=melodia)))
    resultado = canciones.melodia_en_tablatura(base, "C")
    assert resultado["compases"] == [{"compas": 1, "tabs": ["-3", "1"]},
                                     {"compas": 2, "tabs": ["·"]}]
    assert resultado["fuera"] == 1
    assert resultado["notas"] == 3


def test_sin_armonica_la_ficha_no_pasa_la_melodia():
    melodia = [bandinabox.NotaDeMelodia(0.0, 0.5, 69, 90)]
    base = bandinabox.interpretar(bandinabox.escribir(blues_en_fa(melodia=melodia)))
    ficha = canciones.ficha(base, None)
    assert ficha["tiene_melodia"] is True
    assert ficha["melodia"] is None


def test_cada_acorde_de_la_ficha_trae_sus_notas_y_sus_guias(carpeta):
    """
    El reproductor necesita las clases de nota de cada acorde; el diagrama,
    los agujeros de la 3a y la 7a. Para un F7 en armónica de Do, la 3a (La)
    está en el ↓3'' y en el ↑6... hay varias formas: alcanza con que todas
    sean La o Mib y que cada una diga qué grado es.
    """
    ficha = canciones.listar(carpeta)[1].como_diccionario("C")["ficha"]
    f7 = ficha["cifrado"][0]["acordes"][0]
    assert f7["nombre"] == "F7"
    assert f7["clases"] == [5, 9, 0, 3]       # Fa La Do Mib
    assert f7["bajo"] == 5
    assert f7["guias"], "un dominante tiene notas guia"
    assert {g["nota"] for g in f7["guias"]} == {"A", "Eb"}
    assert {g["grado"] for g in f7["guias"]} == {"3a mayor", "7a menor"}
    assert all(set(g) >= {"agujero", "direccion", "bend", "tab"} for g in f7["guias"])


def test_un_acorde_que_la_app_no_calcula_tiene_notas_pero_no_guias():
    base = blues_en_fa()
    base.acordes = [bandinabox.Acorde(1, 1, "E", "m7b5", numero_tipo=32)]
    base.compases = 1
    ficha = canciones.ficha(bandinabox.interpretar(bandinabox.escribir(base)), "C")
    acorde = ficha["cifrado"][0]["acordes"][0]
    assert acorde["clases"] == [4, 7, 10, 2]
    assert acorde["guias"] == []


def test_la_melodia_cruda_viaja_para_el_reproductor():
    melodia = [bandinabox.NotaDeMelodia(2.0, 0.5, 69, 90)]
    base = bandinabox.interpretar(bandinabox.escribir(blues_en_fa(bpm=120, melodia=melodia)))
    ficha = canciones.ficha(base, None)
    assert ficha["melodia_midi"] == [[2.0, 0.5, 69]]
