"""
Tests de armonica/sobre_la_base.py — qué tocaste sobre cada acorde.

La base es el blues en Fa de test_bandinabox a 120 BPM: medio segundo por
pulso, dos segundos por compás. Las notas se ponen a mano en instantes
conocidos, en armónica de Do.

Cómo correrlos:   python -m pytest tests/test_sobre_la_base.py -v
"""

from armonica import bandinabox, mapeo, segmentacion, sobre_la_base
from tests.test_bandinabox import blues_en_fa


def nota_en(instante, tablatura):
    return segmentacion.Evento(
        nota=mapeo.tab_a_nota(tablatura, "C"), inicio_seg=instante, duracion_seg=0.3,
        frecuencia_hz=440.0, cents=0.0, confianza=0.99, ventanas=25,
    )


def base_a_120():
    return bandinabox.interpretar(bandinabox.escribir(blues_en_fa(bpm=120)))


# En armónica de Do: -3'' es La (la 3a de F7), -3 es Si (no está en F7),
# -4 es Re (la 3a de Bb7), 4 es Do (la 5a de F7), -2 es Sol.
EVENTOS = [
    nota_en(0.0, "-3''"),   # compás 1, tiempo 1, F7: la 3a -> guia
    nota_en(0.5, "-3"),     # compás 1, tiempo 2, F7: Si -> fuera
    nota_en(2.0, "-4"),     # compás 2, tiempo 1, Bb7: la 3a -> guia en un cambio
    nota_en(4.1, "4"),      # compás 3, tiempo 1, F7: la 5a, del acorde pero no guia
]


def test_cada_nota_cae_en_su_compas_y_su_acorde():
    notas = sobre_la_base.colocar(EVENTOS, base_a_120(), 120, 0.0)
    assert [(n.compas, n.tiempo, n.acorde) for n in notas] == [
        (1, 1, "F7"), (1, 2, "F7"), (2, 1, "Bb7"), (3, 1, "F7"),
    ]
    assert [n.en_el_acorde for n in notas] == [True, False, True, True]
    assert [n.es_guia for n in notas] == [True, False, True, False]
    assert [n.grado for n in notas] == ["3a mayor", "5a bemol", "3a mayor", "5a"]


def test_el_resumen_cuenta_sin_opinar():
    evaluacion = sobre_la_base.evaluar(EVENTOS, base_a_120(), 120, 0.0, "Blues")
    assert evaluacion["notas"] == 4
    assert evaluacion["en_el_acorde"] == 3
    assert evaluacion["porcentaje_en_el_acorde"] == 75
    # Los compases 2 y 3 son cambios (Bb7 y vuelta a F7). En el 2 la primera
    # nota fue una guia en el tiempo 1; en el 3 fue la 5a.
    assert evaluacion["cambios_con_nota"] == 2
    assert evaluacion["aterrizajes_en_guia"] == 1
    assert [c["compas"] for c in evaluacion["por_compas"]] == [1, 2, 3]
    assert evaluacion["por_compas"][1]["es_cambio"] is True
    assert evaluacion["por_compas"][1]["notas"][0]["tab"] == "-4"


def test_el_offset_corre_todo():
    """Si el compás 1 cayó en el segundo 2 de la grabación, lo anterior es conteo."""
    evaluacion = sobre_la_base.evaluar(EVENTOS, base_a_120(), 120, 2.0)
    assert evaluacion["notas"] == 2
    assert [c["compas"] for c in evaluacion["por_compas"]] == [1, 2]
    assert evaluacion["por_compas"][0]["notas"][0]["acorde"] == "F7"


def test_un_tempo_mas_lento_cambia_donde_cae_cada_nota():
    """A 60 BPM el compás dura 4 s: las cuatro notas caen en los compases 1 y 2."""
    evaluacion = sobre_la_base.evaluar(EVENTOS, base_a_120(), 60, 0.0)
    assert [c["compas"] for c in evaluacion["por_compas"]] == [1, 2]


def test_la_base_repite_el_coro():
    """El blues tiene 12 compases: el compás 13 vuelve a ser el 1, con F7."""
    evento = nota_en(24.0, "-3''")  # compás 13 a 120 BPM
    notas = sobre_la_base.colocar([evento], base_a_120(), 120, 0.0)
    assert (notas[0].compas, notas[0].compas_en_la_vuelta, notas[0].acorde) == (13, 1, "F7")


def test_con_pocas_notas_no_hay_porcentaje():
    evaluacion = sobre_la_base.evaluar(EVENTOS[:2], base_a_120(), 120, 0.0)
    assert evaluacion["suficiente"] is False
    assert evaluacion["porcentaje_en_el_acorde"] is None
    assert "muy pocas" in sobre_la_base.como_texto(evaluacion)


def test_las_notas_sin_reconocer_no_cuentan():
    sin_nota = segmentacion.Evento(nota=None, inicio_seg=0.2, duracion_seg=0.2,
                                   frecuencia_hz=0.0, cents=0.0, confianza=0.0, ventanas=3)
    notas = sobre_la_base.colocar([sin_nota] + EVENTOS, base_a_120(), 120, 0.0)
    assert len(notas) == 4


def test_el_texto_del_resumen():
    texto = sobre_la_base.como_texto(sobre_la_base.evaluar(EVENTOS, base_a_120(), 120, 0.0, "Blues"))
    assert "3 de 4 notas" in texto
    assert "1 de 2 veces" in texto
    assert "-3''(guia)" in texto and "-3(fuera)" in texto and "4(5a)" in texto
