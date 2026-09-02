"""
Tests de armonica/teoria.py — escalas calculadas para las doce posiciones.

El test más importante de todo el proyecto está acá: la conciliación entre las
tablas escritas a mano y el cálculo. Son dos fuentes independientes que tienen
que dar lo mismo, como una conciliación bancaria.

Cómo correrlos:   python -m pytest tests/test_teoria.py -v
"""

import pytest

from armonica import posiciones, tablas, teoria


# =============================================================================
# LA CONCILIACIÓN — el test que justifica que existan los dos módulos
# =============================================================================

def test_el_calculo_coincide_con_todas_las_tablas_escritas_a_mano():
    """
    ESTE ES EL TEST CENTRAL DEL PASO.

    Recorre las dieciocho tablas escritas a mano y las compara, agujero por
    agujero, contra lo que calcula teoria.py desde los intervalos.

    Las dos fuentes son independientes:
      - Las tablas salen de leer métodos de armónica y de las clases.
      - El cálculo sale de la afinación Richter y de los intervalos de cada escala.

    Si difieren, una de las dos está mal. Cuando escribimos las tablas, tres
    erratas aparecieron justamente así.

    Lo corre para las cuatro armónicas de Bruno, lo que además demuestra que las
    tablas son independientes de la tonalidad.
    """
    problemas = []

    for tonalidad in tablas.TONALIDADES_DISPONIBLES:
        for (posicion, escala) in tablas.ESCALAS_POR_POSICION:
            sobran, faltan = teoria.comparar_con_tabla_explicita(
                tonalidad, posicion, escala
            )
            if sobran:
                problemas.append(
                    f"  armonica en {tonalidad}, {posicion}a {escala}: "
                    f"el calculo encuentra {sobran} que la tabla no tiene"
                )
            if faltan:
                problemas.append(
                    f"  armonica en {tonalidad}, {posicion}a {escala}: "
                    f"la tabla tiene {faltan} que el calculo no encuentra"
                )

    assert not problemas, (
        "Las tablas escritas a mano y el calculo no concilian:\n" + "\n".join(problemas)
    )


def test_comparar_devuelve_none_si_no_hay_tabla_para_comparar():
    """No es un error: la 7a posición simplemente no tiene tabla escrita."""
    sobran, faltan = teoria.comparar_con_tabla_explicita("C", 7, "blues")
    assert sobran is None
    assert faltan is None


# =============================================================================
# El cálculo funciona para las doce posiciones
# =============================================================================

def test_calcula_las_doce_posiciones_sin_romperse():
    for posicion in range(1, 13):
        for escala in tablas.ESCALAS_INTERVALOS:
            resultado = teoria.agujeros_para_escala("C", posicion, escala)
            assert len(resultado.agujeros) > 0


def test_calcula_las_doce_armonicas():
    for tonalidad in tablas.TONALIDADES:
        resultado = teoria.agujeros_para_escala(tonalidad, 2, "blues")
        assert len(resultado.agujeros) > 0


def test_la_tonica_calculada_coincide_con_posiciones_py():
    """Los dos módulos tienen que estar de acuerdo en la tonalidad resultante."""
    for tonalidad in tablas.TONALIDADES_DISPONIBLES:
        for posicion in range(1, 13):
            resultado = teoria.agujeros_para_escala(tonalidad, posicion, "blues")
            assert resultado.tonica == posiciones.tonalidad_resultante(tonalidad, posicion)


def test_los_agujeros_vienen_ordenados_de_grave_a_agudo():
    resultado = teoria.agujeros_para_escala("C", 12, "pentatonica_mayor")
    midis = [nota.midi for nota in resultado.agujeros]
    assert midis == sorted(midis)


def test_todo_agujero_calculado_pertenece_de_verdad_a_la_escala():
    """
    Verificación directa: cada nota que el cálculo propone tiene que ser una
    nota de la escala. Corre sobre las doce posiciones y las tres escalas.
    """
    for posicion in range(1, 13):
        for escala in tablas.ESCALAS_INTERVALOS:
            resultado = teoria.agujeros_para_escala("C", posicion, escala)
            clases_validas = posiciones.clases_de_escala("C", posicion, escala)
            for nota in resultado.agujeros:
                assert nota.midi % 12 in clases_validas


def test_entradas_invalidas_dan_error_claro():
    with pytest.raises(ValueError):
        teoria.agujeros_para_escala("H", 2, "blues")
    with pytest.raises(ValueError):
        teoria.agujeros_para_escala("C", 13, "blues")
    with pytest.raises(ValueError):
        teoria.agujeros_para_escala("C", 2, "dorica")


# =============================================================================
# La 12a posición — lo que Bruno estudia ahora
# =============================================================================

def test_la_pentatonica_de_doceava_sale_entera_sin_overblows():
    """
    El argumento pedagógico de Leandro del 04/08, verificado por cálculo:
    la pentatónica mayor de Fa no necesita ninguna nota que la armónica no dé.
    """
    resultado = teoria.agujeros_para_escala("C", 12, "pentatonica_mayor")
    assert not resultado.necesita_overblows()
    assert resultado.faltantes == []


def test_la_escala_mayor_completa_de_fa_si_pide_el_si_bemol():
    """
    La contracara, y la razón por la que Leandro te empuja a la pentatónica:
    la escala mayor completa incluye Sib, que en el registro central solo sale
    con overblow del 6.

    Como no tenemos la escala mayor completa en las tablas, lo verificamos por
    la vía de la pentatónica MENOR de 12a, que también incluye el Sib.
    """
    resultado = teoria.agujeros_para_escala("C", 12, "pentatonica_menor")
    assert resultado.necesita_overblows()
    assert "Bb5" in resultado.faltantes


def test_las_notas_que_faltan_en_la_pentatonica_menor_de_doceava():
    """
    Las notas que la armónica en Do no puede dar para esta escala.
    Fijadas por escrito porque explican por qué la 12a menor es incómoda.

    El Lab grave (Ab4) salió de esta lista el 02/09, al incorporar el tercer
    bend del 3. Es la pregunta que tenías abierta desde el 21/08: el Lab grave
    existe y sale del bend más difícil de la armónica; el bend del 6 da la
    misma nota una octava arriba, en un agujero que sí responde.
    """
    resultado = teoria.agujeros_para_escala("C", 12, "pentatonica_menor")
    assert resultado.faltantes == ["Eb4", "Eb5", "Bb5", "Ab6"]
    assert "Ab4" not in resultado.faltantes


def test_del_agujero_cuatro_para_arriba_la_pentatonica_de_doceava_no_pide_bends():
    """
    El hecho que hace amable a la 12a, y que tu atril describe como "la octava
    que no pide nada". Once notas seguidas de aire natural.
    """
    resultado = teoria.agujeros_para_escala("C", 12, "pentatonica_mayor")
    del_cuatro_arriba = [n for n in resultado.agujeros if n.agujero >= 4]
    assert len(del_cuatro_arriba) == 11
    assert all(nota.bend == 0 for nota in del_cuatro_arriba)


def test_la_doceava_da_quince_agujeros_naturales_de_diecisiete():
    """Solo dos de los diecisiete piden bend, y los dos están en el registro grave."""
    resultado = teoria.agujeros_para_escala("C", 12, "pentatonica_mayor")
    assert len(resultado.agujeros) == 17
    assert len(resultado.sin_bends()) == 15
    assert resultado.cantidad_de_bends() == 2


def test_la_blue_note_de_la_doceava_sale_sin_bend():
    """El ↓7 (Si) es la quinta bemol de Fa. Tu atril lo llama "un regalo"."""
    resultado = teoria.agujeros_para_escala("C", 12, "blues")
    tablaturas = resultado.tablaturas("guion")
    assert "-7" in tablaturas
    assert "-3" in tablaturas


# =============================================================================
# La 4a posición — la del bend del 3, el agujero con fuga
# =============================================================================

def test_la_tonica_de_cuarta_posicion_es_el_bend_de_un_tono_del_tres():
    """
    La regla que Leandro dio el 19/05, verificada: la tónica de la 4a posición
    es el 3 aspirado con segundo bend.

    Es la razón por la que la fuga de aire del agujero 3 te complica medio
    repertorio: es la tónica de una posición entera.
    """
    resultado = teoria.agujeros_para_escala("C", 4, "pentatonica_menor")
    assert resultado.tonica == "A"

    # El ↓3'' tiene que estar entre los agujeros de la escala, y ser un La.
    bend_del_tres = [
        n for n in resultado.agujeros
        if n.agujero == 3 and n.bend == 2
    ]
    assert len(bend_del_tres) == 1
    assert bend_del_tres[0].nombre == "A4"


def test_la_tonica_de_tercera_posicion_es_el_cuatro_aspirado():
    """La otra regla de la misma clase, también correcta."""
    resultado = teoria.agujeros_para_escala("C", 3, "pentatonica_menor")
    assert resultado.tonica == "D"
    cuatro_aspirado = [
        n for n in resultado.agujeros
        if n.agujero == 4 and n.bend == 0 and n.direccion == "aspirado"
    ]
    assert len(cuatro_aspirado) == 1
    assert cuatro_aspirado[0].nombre == "D5"


def test_el_dos_soplado_es_la_tonica_de_quinta_no_de_segunda():
    """
    La corrección al recap del 19/05, que decía "acorde V (2a posición): la
    tónica es el 2 soplado". El agujero es el correcto para el V de un menor,
    pero corresponde a la 5a posición: el 2 soplado de una armónica en Do es
    Mi, y la 5a posición en Do es Mi.
    """
    quinta = teoria.agujeros_para_escala("C", 5, "pentatonica_menor")
    assert quinta.tonica == "E"

    segunda = teoria.agujeros_para_escala("C", 2, "pentatonica_menor")
    assert segunda.tonica == "G"


# =============================================================================
# notas_de_escala — teoría pura, sin armónica
# =============================================================================

def test_notas_de_escala_sin_armonica():
    assert teoria.notas_de_escala("F", "pentatonica_mayor") == ["F", "G", "A", "C", "D"]
    assert teoria.notas_de_escala("G", "pentatonica_menor") == ["G", "Bb", "C", "D", "F"]


def test_la_escala_de_blues_de_fa():
    assert teoria.notas_de_escala("F", "blues") == ["F", "Ab", "Bb", "B", "C", "Eb"]


def test_notas_de_escala_acepta_sostenidos():
    assert teoria.notas_de_escala("C#", "pentatonica_mayor")[0] == "Db"


def test_notas_de_escala_rechaza_lo_que_no_es_nota():
    with pytest.raises(ValueError):
        teoria.notas_de_escala("H", "blues")
    with pytest.raises(ValueError):
        teoria.notas_de_escala("C", "lidia")


# =============================================================================
# posiciones_utiles — qué posición conviene para cada escala
# =============================================================================

def test_posiciones_utiles_devuelve_las_doce_ordenadas():
    ranking = teoria.posiciones_utiles("C", "pentatonica_mayor")
    assert len(ranking) == 12
    # La primera tiene que ser al menos tan cómoda como la última.
    assert ranking[0]["notas_imposibles"] <= ranking[-1]["notas_imposibles"]


def test_la_mejor_posicion_para_la_pentatonica_mayor_no_pide_overblows():
    ranking = teoria.posiciones_utiles("C", "pentatonica_mayor")
    assert ranking[0]["notas_imposibles"] == 0


def test_la_doceava_esta_entre_las_comodas_para_pentatonica_mayor():
    """
    Es lo que dice Leandro y lo que dice tu atril: la 12a es una posición
    amable para la pentatónica mayor. El cálculo lo confirma sin saber nada
    de tus clases.
    """
    ranking = teoria.posiciones_utiles("C", "pentatonica_mayor")
    doceava = next(r for r in ranking if r["posicion"] == 12)
    assert doceava["notas_imposibles"] == 0
    assert doceava["agujeros_sin_bend"] >= 15


def test_la_segunda_posicion_es_comoda_para_la_escala_de_blues():
    """
    Por algo el blues se toca en 2a. Casi toda la escala sale, y solo falta
    una nota en un registro.
    """
    ranking = teoria.posiciones_utiles("C", "blues")
    segunda = next(r for r in ranking if r["posicion"] == 2)
    assert segunda["notas_imposibles"] <= 2


# =============================================================================
# La estructura del resultado
# =============================================================================

def test_tablaturas_respeta_la_notacion_pedida():
    resultado = teoria.agujeros_para_escala("C", 12, "pentatonica_mayor")
    con_guion = resultado.tablaturas("guion")
    con_flechas = resultado.tablaturas("flechas")

    assert "-5" in con_guion
    assert "↓5" in con_flechas
    assert len(con_guion) == len(con_flechas)


def test_muestra_las_dos_formas_de_tocar_una_nota_ambigua():
    """
    A diferencia de la transcripción, que tiene que elegir una, el modo teoría
    muestra todas las opciones: si el Sol se puede tocar de dos maneras, querés
    verlas a las dos.
    """
    resultado = teoria.agujeros_para_escala("C", 2, "pentatonica_menor")
    tablaturas = resultado.tablaturas("guion")
    assert "-2" in tablaturas
    assert "3" in tablaturas
