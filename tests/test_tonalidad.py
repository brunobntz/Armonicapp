"""
Tests de armonica/tonalidad.py — qué armónica y en qué tono.

Los eventos se arman a mano con notas conocidas, así sabemos qué tiene que
deducir el módulo.

Cómo correrlos:   python -m pytest tests/test_tonalidad.py -v
"""

import pytest

from armonica import mapeo, segmentacion, tonalidad


def evento(tablatura, tonalidad_armonica="C", duracion=0.5, inicio=0.0):
    return segmentacion.Evento(
        nota=mapeo.tab_a_nota(tablatura, tonalidad_armonica),
        inicio_seg=inicio, duracion_seg=duracion, frecuencia_hz=440.0,
        cents=0.0, confianza=0.99, ventanas=40,
    )


def tocando(tablaturas, tonalidad_armonica="C", duraciones=None):
    """Una serie de eventos. `duraciones` permite pesar unas notas más que otras."""
    lista = []
    for numero, tablatura in enumerate(tablaturas):
        duracion = duraciones[numero] if duraciones else 0.5
        lista.append(evento(tablatura, tonalidad_armonica, duracion, numero * 0.6))
    return lista


# =============================================================================
# Qué armónica se usó
# =============================================================================

CORRIDA_12A = ["-2''", "-2", "-3'''", "-3''", "4", "-4", "-5", "6",
               "-6'", "-6", "7", "-8", "-9"]


def test_deduce_la_armonica_de_las_notas_tocadas():
    """
    Es el dato confiable del módulo. Una armónica diatónica da treinta notas
    contadas, así que el conjunto de lo tocado la delata.

    Usamos la corrida completa de 12a posición, con sus bends, porque incluye
    notas que solo una armónica en Do da cómodas. Ver el test de abajo sobre
    por qué un puñado de notas no alcanza.
    """
    armonica, cobertura = tonalidad.detectar_armonica(tocando(CORRIDA_12A))

    assert armonica == "C"
    assert cobertura == pytest.approx(1.0)


def test_con_pocas_notas_varias_armonicas_encajan_igual():
    """
    UNA LIMITACION REAL, QUE CONVIENE TENER POR ESCRITO.

    Estas nueve notas (Fa Sol La Do Re Fa Sol La Do) caben enteras en una
    armónica en Do Y en una en Fa. En la de Fa salen con menos bends, así que
    el método elige esa, y no se equivoca: con esa información es la respuesta
    razonable.

    La moraleja es que hacen falta suficientes notas, y sobre todo bends, para
    que la deducción sea concluyente. Con una escala corta y sin bends difíciles
    varias armónicas explican lo mismo.
    """
    eventos = tocando(["-2''", "-2", "-3''", "4", "-4", "-5", "6", "-6", "7"])

    _, cobertura_do = tonalidad.detectar_armonica(eventos, tonalidades=["C"])
    _, cobertura_fa = tonalidad.detectar_armonica(eventos, tonalidades=["F"])

    assert cobertura_do == pytest.approx(1.0)
    assert cobertura_fa == pytest.approx(1.0)


def test_deduce_bien_con_otra_armonica():
    eventos = tocando(["1", "-1", "2", "-2", "4", "-4", "-5", "6"], "G")
    armonica, cobertura = tonalidad.detectar_armonica(eventos)

    assert armonica == "G"
    assert cobertura == pytest.approx(1.0)


def test_usa_las_octavas_y_no_solo_las_clases_de_nota():
    """
    EL ERROR QUE ESTE TEST EVITA.

    Contando solo qué notas suenan sin mirar la octava, la armónica en Do y la
    de Mib podían dar las mismas seis notas de la grabación de Bruno y quedaban
    empatadas. La función terminaba eligiendo por orden alfabético y decía Mib.

    Mirando las octavas, la de Do cubre el 100% y la de Mib el 94%: no hay
    empate que romper.
    """
    # La corrida de 12a posicion que Bruno practica, en armonica de Do.
    eventos = tocando(["-2''", "-2", "-3'''", "-3''", "4", "-4", "-5", "6",
                       "-6'", "-6", "7", "-8", "-9"])

    armonica, cobertura = tonalidad.detectar_armonica(eventos)
    assert armonica == "C"
    assert cobertura == pytest.approx(1.0)

    # Y la de Mib, que era la que ganaba antes, cubre menos.
    _, cobertura_mib = tonalidad.detectar_armonica(eventos, tonalidades=["Eb"])
    assert cobertura_mib < 1.0


def test_pesa_por_duracion_y_no_por_cantidad():
    """
    Una nota larga es más informativa que un chirrido de paso. Acá una nota
    larga en el rango de la armónica pesa más que varias cortas fuera.
    """
    largas = tocando(["4", "-4", "-5"], duraciones=[3.0, 3.0, 3.0])
    _, cobertura = tonalidad.detectar_armonica(largas)
    assert cobertura == pytest.approx(1.0)


def test_sin_notas_no_deduce_nada():
    armonica, cobertura = tonalidad.detectar_armonica([])
    assert armonica == ""
    assert cobertura == 0.0


# =============================================================================
# El perfil de notas
# =============================================================================

def test_el_perfil_tiene_doce_valores_que_suman_uno():
    perfil = tonalidad.perfil_de_clases(tocando(["4", "-4", "-5", "6"]))
    assert len(perfil) == 12
    assert sum(perfil) == pytest.approx(1.0)


def test_el_perfil_pesa_por_duracion():
    """Si el Do suena tres veces más que el Re, tiene que pesar tres veces más."""
    eventos = tocando(["4", "-4"], duraciones=[3.0, 1.0])
    perfil = tonalidad.perfil_de_clases(eventos)

    assert perfil[0] == pytest.approx(0.75)     # Do
    assert perfil[2] == pytest.approx(0.25)     # Re


def test_el_perfil_de_una_lista_vacia_es_todo_ceros():
    assert sum(tonalidad.perfil_de_clases([])) == 0.0


# =============================================================================
# En qué tono está
# =============================================================================

def test_reconoce_una_escala_de_do_mayor():
    """
    Tocando la escala de Do con la tónica sostenida, Do mayor tiene que quedar
    primero.
    """
    eventos = tocando(
        ["4", "-4", "5", "-5", "6", "-6", "-7", "7", "4"],
        duraciones=[2.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 2.0],
    )
    candidatos = tonalidad.detectar_tonalidad(eventos)
    assert candidatos[0].tonica == "C"


def test_devuelve_varios_candidatos_ordenados():
    candidatos = tonalidad.detectar_tonalidad(tocando(["4", "-4", "5", "6"]))
    assert len(candidatos) >= 2
    for anterior, siguiente in zip(candidatos, candidatos[1:]):
        assert anterior.puntaje >= siguiente.puntaje


def test_sin_notas_no_hay_candidatos():
    assert tonalidad.detectar_tonalidad([]) == []


def test_la_correlacion_de_una_serie_consigo_misma_es_uno():
    valores = [1.0, 5.0, 2.0, 8.0, 3.0]
    assert tonalidad._correlacion(valores, valores) == pytest.approx(1.0)


def test_la_correlacion_de_series_opuestas_es_menos_uno():
    assert tonalidad._correlacion([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)


def test_la_correlacion_no_rompe_con_una_serie_plana():
    assert tonalidad._correlacion([1, 1, 1], [1, 2, 3]) == 0.0


# =============================================================================
# LA HONESTIDAD: cuando no se puede saber
# =============================================================================

def test_avisa_cuando_los_dos_primeros_son_relativas():
    """
    EL CASO MAS IMPORTANTE DEL MODULO.

    Fa mayor y Re menor tienen EXACTAMENTE las mismas siete notas. Lo único que
    las distingue es cuál se siente como el centro, y eso lo define el
    acompañamiento, no las notas. Este método no puede resolverlo.

    Le pasó con la grabación real de Bruno: él estaba en Fa y el análisis
    reportaba Re menor con toda seguridad.
    """
    analisis = tonalidad.Analisis(candidatos=[
        tonalidad.Candidato("D", "menor", 0.80),
        tonalidad.Candidato("F", "mayor", 0.71),
    ])
    assert analisis.son_relativas()
    assert analisis.hay_dudas()


def test_no_marca_como_relativas_a_dos_tonalidades_cualesquiera():
    analisis = tonalidad.Analisis(candidatos=[
        tonalidad.Candidato("C", "mayor", 0.80),
        tonalidad.Candidato("F", "menor", 0.40),
    ])
    assert not analisis.son_relativas()


def test_dos_del_mismo_modo_no_son_relativas():
    analisis = tonalidad.Analisis(candidatos=[
        tonalidad.Candidato("C", "mayor", 0.80),
        tonalidad.Candidato("G", "mayor", 0.75),
    ])
    assert not analisis.son_relativas()


def test_avisa_cuando_los_puntajes_estan_muy_parejos():
    analisis = tonalidad.Analisis(candidatos=[
        tonalidad.Candidato("C", "mayor", 0.70),
        tonalidad.Candidato("G", "mayor", 0.69),
    ])
    assert analisis.hay_dudas()


def test_no_avisa_cuando_hay_un_ganador_claro():
    analisis = tonalidad.Analisis(candidatos=[
        tonalidad.Candidato("C", "mayor", 0.90),
        tonalidad.Candidato("G", "mayor", 0.40),
    ])
    assert not analisis.hay_dudas()


# =============================================================================
# Qué armónica agarrar
# =============================================================================

def test_sugiere_las_armonicas_para_un_tono():
    sugerencias = tonalidad.sugerir_armonicas("G")
    assert sugerencias
    assert all(s.tonica == "G" for s in sugerencias)


def test_la_segunda_posicion_va_primero():
    """
    Es donde la armónica cae naturalmente y es lo que uno elegiría. Para tocar
    en Sol, lo primero que sugiere tiene que ser la armónica en Do.
    """
    primera = tonalidad.sugerir_armonicas("G")[0]
    assert primera.tonalidad_armonica == "C"
    assert primera.posicion == 2


def test_las_armonicas_que_tenes_van_antes_que_las_otras():
    sugerencias = tonalidad.sugerir_armonicas("Db", disponibles=["C", "G", "D", "A"])
    tenidas = [s.la_tenes for s in sugerencias]
    # Las que tiene van primero: una vez que aparece un False no vuelve a True.
    assert tenidas == sorted(tenidas, reverse=True)


def test_marca_cuales_no_tenes():
    sugerencias = tonalidad.sugerir_armonicas("B", disponibles=["C"])
    assert any(not s.la_tenes for s in sugerencias)


def test_cada_sugerencia_da_el_tono_pedido():
    """Verificación cruzada contra posiciones.py."""
    from armonica import posiciones

    for tonica in ["C", "G", "F", "Bb", "E"]:
        for sugerencia in tonalidad.sugerir_armonicas(tonica, cuantas=8):
            assert posiciones.tonalidad_resultante(
                sugerencia.tonalidad_armonica, sugerencia.posicion
            ) == tonica


# =============================================================================
# El análisis completo
# =============================================================================

def test_el_analisis_junta_todo():
    analisis = tonalidad.analizar(tocando(CORRIDA_12A))

    assert analisis.armonica_probable == "C"
    assert analisis.candidatos
    assert analisis.sugerencias
    assert analisis.notas_usadas == len(CORRIDA_12A)


def test_cuando_son_relativas_sugiere_para_las_dos():
    """
    Sería raro decir "no sé si es Fa o Re menor" y después mostrar las opciones
    de una sola.
    """
    analisis = tonalidad.Analisis(candidatos=[
        tonalidad.Candidato("D", "menor", 0.80),
        tonalidad.Candidato("F", "mayor", 0.71),
    ])
    analisis.sugerencias = tonalidad.sugerir_armonicas("D")
    analisis.sugerencias_alternativas = tonalidad.sugerir_armonicas("F")

    assert analisis.sugerencias[0].tonica == "D"
    assert analisis.sugerencias_alternativas[0].tonica == "F"


# =============================================================================
# El informe
# =============================================================================

def test_el_informe_tiene_las_secciones():
    eventos = tocando(["-2''", "-2", "-3''", "4", "-4", "-5", "6", "-6", "7"])
    texto = tonalidad.informe(tonalidad.analizar(eventos))

    assert "ARMONICA" in texto
    assert "TONO" in texto
    assert "PARA TOCAR EN" in texto


def test_el_informe_avisa_que_el_tono_puede_fallar():
    """
    La advertencia va SIEMPRE, no solo cuando hay dudas. El método es el que es
    y el usuario tiene que saberlo.
    """
    eventos = tocando(["4", "-4", "-5", "6"])
    texto = tonalidad.informe(tonalidad.analizar(eventos))
    assert "puede fallar" in texto


def test_el_informe_sin_notas_lo_dice():
    texto = tonalidad.informe(tonalidad.analizar([]))
    assert "No hay notas suficientes" in texto
