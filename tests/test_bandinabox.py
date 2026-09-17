"""
Tests de armonica/bandinabox.py — leer una base de Band-in-a-Box.

El archivo real con el que se verificó el formato ("Georgia On My Mind" a
65 BPM, exportado por Band-in-a-Box) vive en audio_prueba/, que no se sube al
repo. Por eso casi todos los tests fabrican una base con `escribir()`, que
usa el mismo formato, y la vuelven a leer. El único test que abre el archivo
real se saltea si no está.

Cómo correrlos:   python -m pytest tests/test_bandinabox.py -v
"""

import os

import pytest

from armonica import bandinabox


def blues_en_fa(bpm=100, estilo="Blues Shuffle", melodia=()):
    """
    Un blues de doce compases en Fa, un acorde por compás, como la base de
    Band-in-a-Box que se usa en las clases: F7 Bb7 F7 F7 Bb7 Bb7 F7 F7 C7 Bb7
    F7 C7.
    """
    raices = ["F", "Bb", "F", "F", "Bb", "Bb", "F", "F", "C", "Bb", "F", "C"]
    acordes = [bandinabox.Acorde(compas=n, tiempo=1, raiz=r, tipo="7", numero_tipo=64)
               for n, r in enumerate(raices, 1)]
    return bandinabox.Base(
        titulo="Blues en Fa", tonalidad="F", modo="mayor", bpm=bpm,
        pulsos_por_compas=4, con_swing=True, estilo=estilo, compases=12,
        acordes=acordes, melodia=list(melodia),
        coro_desde=1, coro_hasta=12, vueltas=3,
    )


def ida_y_vuelta(base):
    return bandinabox.interpretar(bandinabox.escribir(base))


# =============================================================================
# Lo básico: título, tono, tempo, compás
# =============================================================================

def test_lee_titulo_tono_y_tempo():
    base = ida_y_vuelta(blues_en_fa(bpm=100))
    assert base.titulo == "Blues en Fa"
    assert base.tonalidad == "F"
    assert base.modo == "mayor"
    assert base.bpm == 100


def test_el_tempo_de_dos_bytes():
    """
    El tempo va en dos bytes. Con uno solo, un tempo de 300 se leería como
    44. No es un caso real de armónica, pero es el que rompe la lectura.
    """
    base = ida_y_vuelta(blues_en_fa(bpm=300))
    assert base.bpm == 300


def test_el_compas_y_el_swing_salen_del_estilo():
    """
    El archivo no dice "4/4" ni "con swing" en ningún lado: lo dice el número
    de estilo. Y eso decide contra qué figura se mide el ritmo después.
    """
    shuffle = ida_y_vuelta(blues_en_fa(estilo="Blues Shuffle"))
    assert shuffle.pulsos_por_compas == 4
    assert shuffle.con_swing
    assert shuffle.subdivision == 3

    recto = ida_y_vuelta(blues_en_fa(estilo="Blues Straight"))
    assert not recto.con_swing
    assert recto.subdivision == 2

    vals = ida_y_vuelta(blues_en_fa(estilo="Waltz"))
    assert vals.pulsos_por_compas == 3


def test_tono_menor():
    base = blues_en_fa()
    base.tonalidad, base.modo = "D", "menor"
    leida = ida_y_vuelta(base)
    assert (leida.tonalidad, leida.modo) == ("D", "menor")


def test_un_estilo_desconocido_avisa_y_asume_cuatro_cuartos():
    datos = bytearray(bandinabox.escribir(blues_en_fa()))
    indice_estilo = 2 + len("Blues en Fa") + 2
    datos[indice_estilo] = 200
    base = bandinabox.interpretar(bytes(datos))
    assert base.pulsos_por_compas == 4
    assert any("estilo 200" in aviso for aviso in base.avisos)


# =============================================================================
# Los acordes
# =============================================================================

def test_los_acordes_caen_en_su_compas():
    base = ida_y_vuelta(blues_en_fa())
    assert base.compases == 12
    assert [a.nombre() for a in base.acordes] == [
        "F7", "Bb7", "F7", "F7", "Bb7", "Bb7", "F7", "F7", "C7", "Bb7", "F7", "C7",
    ]
    assert [a.compas for a in base.acordes] == list(range(1, 13))
    assert all(a.tiempo == 1 for a in base.acordes)


def test_dos_acordes_en_un_compas():
    """Compás 2 de "Georgia": Em7b5 en el tiempo 1 y A7 en el tiempo 3."""
    base = blues_en_fa()
    base.acordes = [
        bandinabox.Acorde(1, 1, "F", "Maj7", numero_tipo=6),
        bandinabox.Acorde(2, 1, "E", "m7b5", numero_tipo=32),
        bandinabox.Acorde(2, 3, "A", "7", numero_tipo=64),
    ]
    base.compases = 2
    leida = ida_y_vuelta(base)
    assert [(a.compas, a.tiempo, a.nombre()) for a in leida.acordes] == [
        (1, 1, "FMaj7"), (2, 1, "Em7b5"), (2, 3, "A7"),
    ]
    assert leida.cifrado() == ["FMaj7", "Em7b5 A7"]


def test_el_bajo_va_mezclado_con_la_raiz():
    """
    Un Dm/C# se guarda en un solo byte: la raíz más 18 por cada semitono que
    el bajo está por encima. Es lo más raro del formato y lo que primero se
    lee mal.
    """
    base = blues_en_fa()
    base.acordes = [bandinabox.Acorde(1, 1, "D", "m", bajo="C#", numero_tipo=16),
                    bandinabox.Acorde(2, 1, "G", "", bajo="B", numero_tipo=1)]
    base.compases = 2
    leida = ida_y_vuelta(base)
    assert [a.nombre() for a in leida.acordes] == ["Dm/C#", "G/B"]


def test_un_tipo_desconocido_se_ve_y_avisa():
    """Mejor un "?150" en pantalla que un acorde inventado."""
    base = blues_en_fa()
    base.acordes[0] = bandinabox.Acorde(1, 1, "F", "", numero_tipo=150)
    leida = ida_y_vuelta(base)
    assert leida.acordes[0].nombre() == "F?150"
    assert leida.acordes[0].familia() is None
    assert any("150" in aviso for aviso in leida.avisos)


def test_la_familia_es_lo_que_la_app_sabe_calcular():
    """
    Un D9 o un C7#5 tienen 3a mayor y 7a menor: para las notas guía son
    dominantes. Un Em7b5 no es ninguno de los acordes de tablas.py, y la app
    no opina.
    """
    assert bandinabox.Acorde(1, 1, "D", "9", numero_tipo=70).familia() == "dominante"
    assert bandinabox.Acorde(1, 1, "C", "7#5", numero_tipo=99).familia() == "dominante"
    assert bandinabox.Acorde(1, 1, "F", "Maj7", numero_tipo=6).familia() == "mayor7"
    assert bandinabox.Acorde(1, 1, "D", "m", numero_tipo=16).familia() == "menor"
    assert bandinabox.Acorde(1, 1, "E", "m7b5", numero_tipo=32).familia() is None


def test_todas_las_familias_apuntan_a_tipos_que_existen():
    from armonica import tablas
    for familia in bandinabox.FAMILIA_POR_TIPO.values():
        assert familia in tablas.ACORDES_INTERVALOS
    for numero in bandinabox.FAMILIA_POR_TIPO:
        assert numero in bandinabox.TIPOS, f"el tipo {numero} tiene familia pero no nombre"


def test_que_acorde_suena_en_cada_instante():
    base = ida_y_vuelta(blues_en_fa(bpm=120))  # medio segundo por pulso
    assert base.acorde_en(1).nombre() == "F7"
    assert base.acorde_en(2, 3).nombre() == "Bb7"     # sigue el del tiempo 1
    assert base.acorde_en_segundo(0.0).nombre() == "F7"
    assert base.acorde_en_segundo(1.9).nombre() == "F7"
    assert base.acorde_en_segundo(2.0).nombre() == "Bb7"
    assert base.acorde_en_segundo(16.0).nombre() == "C7"  # compás 9


def test_los_compases_de_cambio_coinciden_con_los_del_blues():
    """
    ritmo.py tiene escritos a mano los compases donde cambia el acorde en un
    blues de doce. Leídos de una base, tienen que dar lo mismo: son las dos
    fuentes que se validan entre sí, como en todo el proyecto.
    """
    from armonica import ritmo
    base = ida_y_vuelta(blues_en_fa())
    assert base.compases_de_cambio() == sorted(ritmo.COMPASES_DE_CAMBIO_BLUES)


def test_el_cifrado_repite_con_porcentaje():
    base = blues_en_fa()
    base.acordes = [bandinabox.Acorde(1, 1, "F", "7", numero_tipo=64),
                    bandinabox.Acorde(3, 1, "Bb", "7", numero_tipo=64)]
    base.compases = 3
    assert ida_y_vuelta(base).cifrado() == ["F7", "%", "Bb7"]


def test_el_coro():
    base = ida_y_vuelta(blues_en_fa())
    assert (base.coro_desde, base.coro_hasta, base.vueltas) == (1, 12, 3)


# =============================================================================
# La melodía
# =============================================================================

def test_la_melodia_sale_en_segundos_segun_el_tempo():
    """
    Los ticks son 120 por negra y la melodía arranca después de un compás de
    conteo. A 120 BPM, la negra dura medio segundo: una nota en el tiempo 1
    del compás 2 empieza en el segundo 2.
    """
    melodia = [bandinabox.NotaDeMelodia(inicio_seg=2.0, duracion_seg=0.5, midi=69, velocidad=90),
               bandinabox.NotaDeMelodia(inicio_seg=2.5, duracion_seg=0.25, midi=72, velocidad=80)]
    base = ida_y_vuelta(blues_en_fa(bpm=120, melodia=melodia))
    assert len(base.melodia) == 2
    assert base.melodia[0].midi == 69
    assert base.melodia[0].inicio_seg == pytest.approx(2.0)
    assert base.melodia[0].duracion_seg == pytest.approx(0.5)
    assert base.melodia[1].inicio_seg == pytest.approx(2.5)


def test_sin_melodia_la_lista_esta_vacia():
    assert ida_y_vuelta(blues_en_fa()).melodia == []


# =============================================================================
# Lo que no es una base
# =============================================================================

def test_un_wav_no_es_una_base():
    with pytest.raises(ValueError, match="Band-in-a-Box"):
        bandinabox.interpretar(b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 20)


def test_un_archivo_cortado_no_revienta_con_index_error():
    datos = bandinabox.escribir(blues_en_fa())
    with pytest.raises(ValueError):
        bandinabox.interpretar(datos[:30])


def test_es_base_por_la_extension():
    assert bandinabox.es_base("georgia.MGU")
    assert bandinabox.es_base("blues.sgu")
    assert not bandinabox.es_base("blues.wav")


# =============================================================================
# El archivo real, si está
# =============================================================================

ARCHIVO_REAL = os.path.join("audio_prueba", "Georgia On My Mind-65bpm.MGU")


@pytest.mark.skipif(not os.path.exists(ARCHIVO_REAL), reason="hace falta la base real en audio_prueba/")
def test_la_base_real_de_georgia():
    """
    Lo que se verificó a mano contra el cifrado conocido de "Georgia On My
    Mind" en Fa: los primeros cuatro compases y el tempo de la exportación.
    """
    base = bandinabox.leer(ARCHIVO_REAL)
    assert base.titulo == "Georgia On My Mind"
    assert (base.tonalidad, base.modo, base.bpm) == ("F", "mayor", 65)
    assert base.estilo == "Jazz Swing" and base.subdivision == 3
    assert base.cifrado()[:4] == ["FMaj7", "Em7b5 A7", "Dm Dm/C#", "G/B Bbm7 Eb7"]
    assert (base.coro_desde, base.coro_hasta, base.vueltas) == (1, 32, 3)
    assert len(base.melodia) > 500
    assert base.avisos == []


# =============================================================================
# Qué notas tiene cada acorde, para que el reproductor lo toque
# =============================================================================

@pytest.mark.parametrize("tipo, esperado", [
    ("", [0, 4, 7]),            # F
    ("Maj", [0, 4, 7]),
    ("m", [0, 3, 7]),           # Dm
    ("7", [0, 4, 7, 10]),       # A7
    ("Maj7", [0, 4, 7, 11]),    # FMaj7
    ("m7", [0, 3, 7, 10]),      # Gm7
    ("m7b5", [0, 3, 6, 10]),    # Em7b5
    ("dim", [0, 3, 6]),
    ("dim7", [0, 3, 6, 9]),
    ("9", [0, 4, 7, 10]),       # D9: la 9a se deja afuera a proposito
    ("13", [0, 4, 7, 10]),
    ("7#5", [0, 4, 8, 10]),     # C7#5
    ("7b5", [0, 4, 6, 10]),
    ("7b9", [0, 4, 7, 10]),
    ("6", [0, 4, 7, 9]),        # F6
    ("69", [0, 4, 7, 9]),       # F69
    ("m6", [0, 3, 7, 9]),       # Gm6
    ("+", [0, 4, 8]),
    ("mMaj7", [0, 3, 7, 11]),
    ("7sus", [0, 5, 7, 10]),
    ("sus4", [0, 5, 7]),
    ("sus2", [0, 2, 7]),
    ("add9", [0, 4, 7]),
    ("madd9", [0, 3, 7]),
    ("5", [0, 7]),
    ("Maj9(no 3)", [0, 7, 11]),
    ("?150", [0, 7]),           # desconocido: raiz y quinta, que nunca chocan
])
def test_las_notas_de_cada_tipo_de_acorde(tipo, esperado):
    assert bandinabox.intervalos_del_tipo(tipo) == esperado


def test_todos_los_tipos_conocidos_dan_un_acorde_tocable():
    for tipo in bandinabox.TIPOS.values():
        intervalos = bandinabox.intervalos_del_tipo(tipo)
        assert intervalos[0] == 0
        assert 2 <= len(intervalos) <= 4, tipo
        assert intervalos == sorted(intervalos), tipo


def test_las_clases_de_nota_del_acorde_y_su_bajo():
    acorde = bandinabox.Acorde(1, 1, "D", "m", bajo="C#", numero_tipo=16)
    assert acorde.clases() == [2, 5, 9]     # Re Fa La
    assert acorde.clase_bajo() == 1          # Do#
    assert bandinabox.Acorde(1, 1, "F", "7", numero_tipo=64).clase_bajo() == 5
