"""
Tests de armonica/prioridades.py — qué atacar primero.

Lo que más importa verificar acá no es que encuentre problemas, sino que
SE CALLE cuando el dato no alcanza. Un diagnóstico inventado es peor que
ninguno, porque te manda a practicar la cosa equivocada.

Cómo correrlos:   python -m pytest tests/test_prioridades.py -v
"""

import random

from armonica import mapeo, prioridades, ritmo, segmentacion


def evento(tablatura, cents=0.0, inicio=0.0, duracion=0.4):
    return segmentacion.Evento(
        nota=mapeo.tab_a_nota(tablatura, "C"),
        inicio_seg=inicio, duracion_seg=duracion,
        frecuencia_hz=440.0, cents=cents, confianza=0.99, ventanas=30,
    )


def sesion(pares, naturales=8):
    """Los bends que se piden, más notas naturales afinadas de referencia."""
    eventos = [evento("-5", 0.0, i * 0.5) for i in range(naturales)]
    for tablatura, cents in pares:
        eventos.append(evento(tablatura, cents, len(eventos) * 0.5))
    return eventos


# =============================================================================
# Los bends
# =============================================================================

def test_detecta_un_bend_consistentemente_corto():
    hallazgos, _ = prioridades.analizar(
        sesion([("-3''", 35.0), ("-3''", 33.0), ("-3''", 37.0)])
    )
    assert hallazgos
    assert "-3''" in hallazgos[0].titulo
    assert "corto" in hallazgos[0].titulo


def test_detecta_un_bend_consistentemente_pasado():
    hallazgos, _ = prioridades.analizar(
        sesion([("-3''", -35.0), ("-3''", -33.0), ("-3''", -37.0)])
    )
    assert "pasas" in hallazgos[0].titulo


def test_distingue_un_habito_de_una_falta_de_control():
    """
    LA DISTINCION CENTRAL DEL MODULO.

    Un bend que siempre cae 35 cents corto es un hábito: se recalibra en diez
    repeticiones. Uno que cae en cualquier lado es falta de control y lleva
    semanas. La acción sugerida tiene que ser distinta.
    """
    habito = prioridades.analizar(
        sesion([("-3''", 35.0), ("-3''", 34.0), ("-3''", 36.0)])
    )[0][0]
    descontrol = prioridades.analizar(
        sesion([("-3''", 60.0), ("-3''", -5.0), ("-3''", 35.0)])
    )[0][0]

    assert "siempre lo mismo" in habito.titulo
    assert "recalibrar" in habito.accion

    assert "cualquier lado" in descontrol.titulo
    assert "control" in descontrol.accion


def test_un_bend_bien_afinado_no_genera_hallazgo():
    hallazgos, _ = prioridades.analizar(
        sesion([("-3''", 5.0), ("-3''", -3.0), ("-3''", 8.0)])
    )
    assert not any("-3''" in h.titulo for h in hallazgos)


def test_un_bend_que_aparece_una_sola_vez_no_alcanza():
    """Una golondrina no hace verano: con una aparición no se concluye nada."""
    hallazgos, _ = prioridades.analizar(sesion([("-3''", 45.0)]))
    assert not any("-3''" in h.titulo for h in hallazgos)


def test_sin_notas_naturales_no_se_juzgan_los_bends():
    """
    Sin notas naturales no se puede saber cómo está afinada la armónica, y sin
    eso cualquier medición de bend mezcla el instrumento con el músico.
    """
    eventos = [evento("-3''", 40.0, i * 0.5) for i in range(4)]
    hallazgos, sin_medir = prioridades.analizar(eventos)

    assert not any("-3''" in h.titulo for h in hallazgos)
    assert any("afinacion" in texto.lower() for texto in sin_medir)


# =============================================================================
# El ritmo: callarse cuando la medición no vale
# =============================================================================

def test_no_diagnostica_ritmo_si_la_grilla_no_explica_nada():
    """
    EL TEST MAS IMPORTANTE DEL ARCHIVO.

    Notas repartidas al azar. La app NO puede decir "tu tiempo esta inestable":
    tiene que decir que no pudo medirlo, y por qué.

    Es exactamente lo que pasó con las dos grabaciones de la frase de Carlos
    del Junco: los números salían con toda seriedad sobre una medición que no
    significaba nada.
    """
    generador = random.Random(3)
    eventos = [evento("-5", 0.0, generador.uniform(0, 30)) for _ in range(50)]
    analisis = ritmo.analizar(eventos, bpm=65, subdivision=3)

    hallazgos, sin_medir = prioridades.analizar(eventos, analisis)

    assert not any("tiempo" in h.titulo.lower() for h in hallazgos)
    assert any("RITMO" in texto for texto in sin_medir)
    assert any("azar" in texto for texto in sin_medir)


def test_si_diagnostica_ritmo_cuando_la_grilla_explica():
    """La contracara: con notas que siguen la grilla pero corridas, sí opina."""
    paso = ritmo.paso_de_grilla(60, 1)
    eventos = [evento("-5", 0.0, i * paso - 0.055) for i in range(20)]
    analisis = ritmo.analizar(eventos, bpm=60, subdivision=1, offset_seg=0.0)

    hallazgos, _ = prioridades.analizar(eventos, analisis)
    assert any("adelant" in h.titulo for h in hallazgos)


def test_sin_analisis_de_ritmo_no_dice_nada_del_tema():
    hallazgos, sin_medir = prioridades.analizar(
        sesion([("-3''", 35.0), ("-3''", 34.0)]), None
    )
    assert not any("ritmo" in t.lower() for t in sin_medir)


# =============================================================================
# Orden y presentación
# =============================================================================

def test_los_hallazgos_vienen_ordenados_por_importancia():
    hallazgos, _ = prioridades.analizar(
        sesion([("-3''", 45.0), ("-3''", 44.0), ("-3''", 46.0),
                ("-6'", 25.0), ("-6'", 24.0), ("-6'", 26.0)])
    )
    assert len(hallazgos) >= 2
    for anterior, siguiente in zip(hallazgos, hallazgos[1:]):
        assert anterior.peso >= siguiente.peso


def test_el_texto_muestra_pocos_hallazgos():
    """Una lista de diez cosas para arreglar no se ataca: se ignora."""
    hallazgos, sin_medir = prioridades.analizar(
        sesion([("-3''", 45.0), ("-3''", 44.0),
                ("-6'", 40.0), ("-6'", 41.0),
                ("-2''", -38.0), ("-2''", -39.0),
                ("-1'", 35.0), ("-1'", 36.0)])
    )
    texto = prioridades.imprimir(hallazgos, sin_medir, cuantos=2)

    assert texto.count("Que hacer:") == 2
    if len(hallazgos) > 2:
        assert "mas, menos importantes" in texto


def test_el_texto_avisa_cuando_no_hay_nada_para_corregir():
    eventos = [evento("-5", 2.0, i * 0.5) for i in range(10)]
    hallazgos, sin_medir = prioridades.analizar(eventos)
    assert "No aparecio nada" in prioridades.imprimir(hallazgos, sin_medir)


def test_el_texto_lista_lo_que_no_se_pudo_medir():
    eventos = [evento("-3''", 40.0, i * 0.5) for i in range(4)]
    hallazgos, sin_medir = prioridades.analizar(eventos)
    assert "NO SE PUDO MEDIR" in prioridades.imprimir(hallazgos, sin_medir)


def test_cada_hallazgo_trae_evidencia_y_accion():
    """Un hallazgo sin números que lo sostengan y sin qué hacer no sirve."""
    hallazgos, _ = prioridades.analizar(
        sesion([("-3''", 45.0), ("-3''", 44.0), ("-3''", 46.0)])
    )
    for hallazgo in hallazgos:
        assert hallazgo.evidencia
        assert hallazgo.accion
        assert hallazgo.confianza in ("alta", "media", "baja")
