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
    El argumento pedagógico del profe del 04/08, verificado por cálculo:
    la pentatónica mayor de Fa no necesita ninguna nota que la armónica no dé.
    """
    resultado = teoria.agujeros_para_escala("C", 12, "pentatonica_mayor")
    assert not resultado.necesita_overblows()
    assert resultado.faltantes == []


def test_la_escala_mayor_completa_de_fa_si_pide_el_si_bemol():
    """
    La contracara, y la razón por la que el profe te empuja a la pentatónica:
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
    La regla que el profe dio el 19/05, verificada: la tónica de la 4a posición
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
    Es lo que dice el profe y lo que dice tu atril: la 12a es una posición
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


# =============================================================================
# La escala de blues MAYOR — la del estudio de Carlos del Junco
# =============================================================================

def test_la_escala_de_blues_mayor_es_la_pentatonica_mayor_mas_la_tercera_menor():
    """
    Los grados son 1, 2, b3, 3, 5, 6. La gracia es que tiene las DOS terceras
    pegadas, y pasar de una a la otra es el sonido caracteristico del blues.
    """
    mayor = set(tablas.ESCALAS_INTERVALOS["pentatonica_mayor"])
    blues_mayor = set(tablas.ESCALAS_INTERVALOS["blues_mayor"])
    assert mayor.issubset(blues_mayor)
    assert blues_mayor - mayor == {3}      # la tercera menor


def test_no_es_la_misma_escala_que_la_de_blues_menor():
    """
    Las dos se llaman blues y son distintas. En Fa:
        blues mayor -> F G Ab A C D
        blues        -> F Ab Bb B C Eb
    Solo comparten la tonica, la tercera menor y la quinta.
    """
    en_fa_mayor = teoria.notas_de_escala("F", "blues_mayor")
    en_fa_menor = teoria.notas_de_escala("F", "blues")
    assert en_fa_mayor == ["F", "G", "Ab", "A", "C", "D"]
    assert en_fa_menor == ["F", "Ab", "Bb", "B", "C", "Eb"]
    assert en_fa_mayor != en_fa_menor


def test_la_corrida_de_blues_mayor_en_doceava_es_la_que_toca_bruno():
    """
    ESTE TEST FIJA LA DIGITACION QUE BRUNO PRACTICA.

    Es la corrida de dos octavas del estudio de Carlos del Junco en 12a
    posicion, tal como la escribio el 02/09, verificada nota por nota contra
    la afinacion de la armonica.

    La unica diferencia con lo que el escribio es el "-6" (La5): en su version
    salta del "-6'" (Lab5) directo al "7" (Do6). La app lo incluye porque es
    nota de la escala; que la toque o no es decision suya.
    """
    resultado = teoria.agujeros_para_escala("C", 12, "blues_mayor")
    corrida = [nota.como_tab("guion") for nota in resultado.desde_la_tonica(octavas=2)]

    assert corrida == [
        "-2''", "-2", "-3'''", "-3''", "4", "-4",
        "-5", "6", "-6'", "-6", "7", "-8", "-9",
    ]

    nombres = [nota.nombre for nota in resultado.desde_la_tonica(octavas=2)]
    assert nombres == [
        "F4", "G4", "Ab4", "A4", "C5", "D5",
        "F5", "G5", "Ab5", "A5", "C6", "D6", "F6",
    ]


def test_la_corrida_arranca_en_la_tonica_no_en_el_agujero_mas_grave():
    """
    La diferencia entre las dos vistas. El inventario completo empieza en el
    "1" (Do4), porque el Do es la quinta de Fa y es la nota mas grave de la
    escala que la armonica alcanza. La corrida empieza en el "-2''" (Fa4),
    que es la tonica y es donde arranca cualquier hoja de estudio.
    """
    resultado = teoria.agujeros_para_escala("C", 12, "blues_mayor")
    assert resultado.agujeros[0].como_tab("guion") == "1"
    assert resultado.agujeros[0].nombre == "C4"
    assert resultado.desde_la_tonica()[0].como_tab("guion") == "-2''"
    assert resultado.desde_la_tonica()[0].nombre == "F4"


def test_la_corrida_no_repite_la_misma_nota_dos_veces():
    """
    El Sol4 se puede tocar como "-2" o como "3". En el inventario aparecen las
    dos opciones; en la corrida, una sola, para que se lea como una escala.
    """
    resultado = teoria.agujeros_para_escala("C", 12, "blues_mayor")
    midis = [nota.midi for nota in resultado.desde_la_tonica()]
    assert len(midis) == len(set(midis))

    inventario = [nota.como_tab("guion") for nota in resultado.agujeros]
    assert "-2" in inventario and "3" in inventario


def test_las_dos_terceras_de_la_doceava_estan_en_los_mismos_agujeros():
    """
    El movimiento central de la 12a: Lab contra La. Abajo son los bends del 3
    (tercero y segundo), en el registro central son el bend del 6 y el 6 pelado.
    """
    resultado = teoria.agujeros_para_escala("C", 12, "blues_mayor")
    tabs = resultado.tablaturas("guion")
    for tablatura in ["-3'''", "-3''", "-6'", "-6"]:
        assert tablatura in tabs


def test_el_bend_del_ocho_no_pertenece_a_la_escala_de_blues_mayor():
    """
    El "8'" es Mib, la septima menor de Fa. Esta en la escala de blues MENOR,
    no en la mayor. Por eso no aparece en la corrida de Carlos del Junco.
    """
    resultado_mayor = teoria.agujeros_para_escala("C", 12, "blues_mayor")
    resultado_menor = teoria.agujeros_para_escala("C", 12, "blues")
    assert "8'" not in resultado_mayor.tablaturas("guion")
    assert "8'" in resultado_menor.tablaturas("guion")


def test_la_corrida_se_puede_pedir_de_una_sola_octava():
    resultado = teoria.agujeros_para_escala("C", 12, "blues_mayor")
    una = resultado.desde_la_tonica(octavas=1)
    dos = resultado.desde_la_tonica(octavas=2)
    assert len(una) < len(dos)
    assert una[0].nombre == "F4"
    assert una[-1].nombre == "F5"


# =============================================================================
# Qué evitar
# =============================================================================

def test_sobre_fa7_en_doce_se_evita_el_mi():
    """
    LA REGLA DE LA CLASE DEL 25/08, CALCULADA.

    "Evitá el ↑2 tocando el blues en Fa": el ↑2 de una armónica en Do es Mi,
    la 7ª mayor de Fa7, y choca con el Mib del acorde. El cálculo tiene que
    dar exactamente eso, y también los otros Mi naturales (↑5, ↑8).
    """
    evitar = teoria.notas_a_evitar("C", 12)
    fa7 = next(e for e in evitar if e["acorde"] == "F7")

    assert fa7["nota"] == "E"
    assert [n.como_tab("guion") for n in fa7["agujeros"]] == ["2", "5", "8"]
    assert "7ª mayor" in fa7["por_que"]


def test_solo_los_agujeros_sin_bend_cuentan_como_a_evitar():
    """
    Sobre Sib7 la nota a evitar es La. En armónica en Do el La4 solo sale con
    bend (-3''): no se lista, porque un bend no se toca por accidente. Quedan
    los La naturales: -6 y -10.
    """
    evitar = teoria.notas_a_evitar("C", 12)
    sib7 = next(e for e in evitar if e["acorde"] == "Bb7")

    assert sib7["nota"] == "A"
    assert [n.como_tab("guion") for n in sib7["agujeros"]] == ["-6", "-10"]


def test_un_acorde_por_grado_sin_repetir():
    evitar = teoria.notas_a_evitar("C", 12)
    assert [e["acorde"] for e in evitar] == ["F7", "Bb7", "C7"]
    assert [e["grado"] for e in evitar] == ["I", "IV", "V"]


# =============================================================================
# El círculo de quintas
# =============================================================================

def test_el_circulo_de_una_armonica_en_do():
    """
    Lo que dice cualquier rueda de posiciones: en Do, 1a es Do, 2a Sol, 3a
    Re, 4a La, 5a Mi, 6a Si, 12a Fa. Y la relativa menor de cada uno.
    """
    sectores = teoria.circulo_de_quintas("C")
    por_posicion = {s["posicion"]: s for s in sectores}
    assert [s["posicion"] for s in sectores] == list(range(1, 13))
    assert {p: por_posicion[p]["tono"] for p in (1, 2, 3, 4, 5, 6, 12)} == {
        1: "C", 2: "G", 3: "D", 4: "A", 5: "E", 6: "B", 12: "F"}
    assert por_posicion[1]["relativa_menor"] == "Am"
    assert por_posicion[2]["relativa_menor"] == "Em"
    assert por_posicion[12]["relativa_menor"] == "Dm"
    assert por_posicion[2]["modo"].startswith("mixolidio")
    assert por_posicion[3]["modo"] == "dórico"
    assert por_posicion[8]["modo"] == ""
    assert por_posicion[12]["con_tabla"] is True and por_posicion[7]["con_tabla"] is False


def test_el_circulo_es_el_mismo_dibujo_girado():
    """Cada posición es una quinta más: las tonalidades de la 2a a la 12a van de quinta en quinta."""
    for armonica in ("C", "G", "D", "A"):
        sectores = teoria.circulo_de_quintas(armonica)
        clases = [tablas.NOMBRES_NOTAS.index(s["tono"]) for s in sectores]
        for anterior, siguiente in zip(clases, clases[1:]):
            assert (siguiente - anterior) % 12 == 7


def test_que_armonica_para_una_cancion():
    """Una canción en Sol: en 2a pide armónica en Do; en 12a, en Re; en 1a, en Sol."""
    assert teoria.armonica_para("G", 2) == "C"
    assert teoria.armonica_para("G", 12) == "D"
    assert teoria.armonica_para("G", 1) == "G"
    assert teoria.armonica_para("F", 12) == "C"
    assert teoria.armonica_para("B", 2) == "E"
    assert teoria.armonica_para("C", 7) == "F#"     # se nombra como la armónica, no como Solb


def test_el_circulo_para_una_cancion_dice_que_armonicas_tenes():
    sectores = {s["posicion"]: s for s in teoria.circulo_para_cancion("F")}
    assert sectores[12]["armonica"] == "C" and sectores[12]["la_tenes"] is True
    assert sectores[2]["armonica"] == "Bb" and sectores[2]["la_tenes"] is False


def test_una_armonica_desconocida_en_el_circulo():
    with pytest.raises(ValueError):
        teoria.circulo_de_quintas("H")
