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
    assert ficha["melodia_midi"] == []


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


def test_la_ficha_no_manda_la_melodia_en_tablatura():
    """La tablatura de una canción es la foto del profe; la melodía de la base
    pasada a agujeros solo la muestra --base en la terminal."""
    melodia = [bandinabox.NotaDeMelodia(0.0, 0.5, 69, 90)]
    base = bandinabox.interpretar(bandinabox.escribir(blues_en_fa(melodia=melodia)))
    ficha = canciones.ficha(base, "C")
    assert ficha["tiene_melodia"] is True
    assert "melodia" not in ficha


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


def test_un_acorde_que_las_tablas_no_tienen_igual_trae_sus_notas_y_sus_guias():
    """
    Un Em7b5 no está en tablas.ACORDES_INTERVALOS, pero su cifrado dice qué
    notas tiene (Mi Sol Sib Re), y de ahí salen la 3a (Sol) y la 7a (Re).
    """
    base = blues_en_fa()
    base.acordes = [bandinabox.Acorde(1, 1, "E", "m7b5", numero_tipo=32)]
    base.compases = 1
    ficha = canciones.ficha(bandinabox.interpretar(bandinabox.escribir(base)), "C")
    acorde = ficha["cifrado"][0]["acordes"][0]
    assert acorde["familia"] is None
    assert acorde["clases"] == [4, 7, 10, 2]
    assert [n["nota"] for n in acorde["notas"]] == ["E", "G", "Bb", "D"]
    assert [n["es_guia"] for n in acorde["notas"]] == [False, True, False, True]
    assert {g["nota"] for g in acorde["guias"]} == {"G", "D"}


def test_cada_nota_del_acorde_trae_su_agujero_mas_comodo():
    """
    F7 en armónica de Do: Fa, La, Do, Mib. El Fa más cómodo es el ↓5 (el
    ↓2'' es un bend); el La, el ↓6 (el ↓3'' es un bend); el Do, el ↑4; el
    Mib solo existe como bend soplado del 8 (↑8').
    """
    base = blues_en_fa()
    base.compases = 1
    ficha = canciones.ficha(bandinabox.interpretar(bandinabox.escribir(base)), "C")
    f7 = ficha["cifrado"][0]["acordes"][0]
    facil = {n["nota"]: n["facil"] for n in f7["notas"]}
    assert facil == {"F": "-5", "A": "-6", "C": "4", "Eb": "8'"}
    grados = {n["nota"]: n["grado"] for n in f7["notas"]}
    assert grados == {"F": "tonica", "A": "3a mayor", "C": "5a", "Eb": "7a menor"}
    fa = next(n for n in f7["notas"] if n["nota"] == "F")
    assert "-2''" in fa["formas"] and "-5" in fa["formas"]


def test_las_notas_a_evitar_son_las_naturales_medio_tono_arriba_de_una_del_acorde():
    """
    Sobre F7 (Fa La Do Mib), medio tono arriba de cada nota: Solb, Sib, Reb
    y Mi. En una armónica en Do, la única natural de esas es el Mi: choca
    con la 7a. Y se dice por qué.
    """
    base = blues_en_fa()
    base.compases = 1
    ficha = canciones.ficha(bandinabox.interpretar(bandinabox.escribir(base)), "C")
    a_evitar = ficha["cifrado"][0]["acordes"][0]["a_evitar"]
    assert {e["nota"] for e in a_evitar} == {"E"}
    assert {e["tab"] for e in a_evitar} == {"2", "5", "8"}
    assert all(e["porque"] == "medio tono arriba de la 7a menor (Eb)" for e in a_evitar)


def test_sin_armonica_no_hay_notas_ni_guias():
    base = blues_en_fa()
    base.compases = 1
    ficha = canciones.ficha(bandinabox.interpretar(bandinabox.escribir(base)), None)
    acorde = ficha["cifrado"][0]["acordes"][0]
    assert acorde["notas"] == [] and acorde["guias"] == [] and acorde["a_evitar"] == []


def test_la_melodia_cruda_viaja_para_el_reproductor():
    melodia = [bandinabox.NotaDeMelodia(2.0, 0.5, 69, 90)]
    base = bandinabox.interpretar(bandinabox.escribir(blues_en_fa(bpm=120, melodia=melodia)))
    ficha = canciones.ficha(base, None)
    assert ficha["melodia_midi"] == [[2.0, 0.5, 69]]


# =============================================================================
# Los hechos de la base
# =============================================================================

def test_los_hechos_del_blues_en_fa():
    """
    F7 Bb7 F7 F7 Bb7 Bb7 F7 F7 C7 Bb7 F7 C7: tres acordes distintos, un
    solo acorde por compás, y las raíces todas en Fa mayor. Cadencias V-I:
    F7 a Bb7 en el 2 y en el 5 (en el blues el I es dominante y resuelve al
    IV una quinta abajo: la regla es esa y la app la aplica sin opinar), y
    C7 a F7 del compás 12 al 1, el turnaround, porque la base da la vuelta.
    """
    base = bandinabox.interpretar(bandinabox.escribir(blues_en_fa()))
    hechos = canciones.hechos_de_la_base(base)
    assert hechos["tonalidad"] == "F mayor"
    assert hechos["acordes_distintos"] == 3
    assert hechos["lista_acordes"] == ["F7", "Bb7", "C7"]
    assert hechos["compases_con_varios"] == 0
    assert [(c["tipo"], c["a"], c["compas"]) for c in hechos["cadencias"]] == [
        ("V-I", "Bb", 2), ("V-I", "Bb", 5), ("V-I", "F", 1)]
    assert hechos["fuera_de_la_tonalidad"] == []
    assert "V-I a Bb en el 2, a Bb en el 5, a F en el 1" in canciones.texto_de_los_hechos(hechos)


def test_un_ii_v_i_y_un_acorde_fuera_de_la_tonalidad():
    """Gm7 C7 FMaj7 es un ii-V-I a Fa; un Eb7 tiene la raíz fuera de Fa mayor."""
    base = blues_en_fa()
    base.acordes = [
        bandinabox.Acorde(1, 1, "G", "m7", numero_tipo=19),
        bandinabox.Acorde(2, 1, "C", "7", numero_tipo=64),
        bandinabox.Acorde(3, 1, "F", "Maj7", numero_tipo=6),
        bandinabox.Acorde(3, 3, "Eb", "7", numero_tipo=64),
    ]
    base.compases = 3
    hechos = canciones.hechos_de_la_base(bandinabox.interpretar(bandinabox.escribir(base)))
    assert hechos["cadencias"] == [{"tipo": "ii-V-I", "a": "F", "compas": 3,
                                    "acordes": "Gm7 C7 FMaj7"}]
    assert hechos["fuera_de_la_tonalidad"] == ["Eb7"]
    assert hechos["compases_con_varios"] == 1
    texto = canciones.texto_de_los_hechos(hechos)
    assert "ii-V-I a F en el compás 3 (Gm7 C7 FMaj7)" in texto
    assert "fuera de la tonalidad: Eb7" in texto


def test_la_ficha_trae_los_hechos(carpeta):
    ficha = canciones.listar(carpeta)[1].como_diccionario("C")["ficha"]
    assert ficha["hechos"]["acordes_distintos"] == 3
