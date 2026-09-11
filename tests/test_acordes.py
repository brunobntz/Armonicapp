"""
Tests de los acordes y arpegios de armonica/teoria.py.

Varios de estos tests comparan el cálculo contra la tabla de notas guía del
atril de 12ª que Bruno escribió a mano. Es la misma conciliación de siempre:
dos fuentes independientes que tienen que dar lo mismo.

Cómo correrlos:   python -m pytest tests/test_acordes.py -v
"""

import pytest

from armonica import tablas, teoria


def facil(acorde, intervalo):
    """El agujero más cómodo para un grado del acorde, como texto."""
    for grado in acorde.grados:
        if grado.intervalo == intervalo:
            nota = grado.el_mas_facil()
            return nota.como_tab("guion") if nota else None
    return None


# =============================================================================
# Las tablas de acordes
# =============================================================================

def test_los_acordes_empiezan_en_la_tonica():
    for intervalos in tablas.ACORDES_INTERVALOS.values():
        assert intervalos[0] == 0


def test_el_acorde_dominante_es_mayor_mas_septima_menor():
    """
    EL ACORDE DEL BLUES. Es un acorde mayor con la séptima menor encima, y esa
    combinación es lo que le da la inestabilidad característica.
    """
    mayor = set(tablas.ACORDES_INTERVALOS["mayor"])
    dominante = set(tablas.ACORDES_INTERVALOS["dominante"])
    assert mayor.issubset(dominante)
    assert dominante - mayor == {10}


def test_la_diferencia_entre_mayor_y_menor_es_la_tercera():
    mayor = tablas.ACORDES_INTERVALOS["mayor"]
    menor = tablas.ACORDES_INTERVALOS["menor"]
    assert mayor[1] == 4 and menor[1] == 3
    assert mayor[0] == menor[0] and mayor[2] == menor[2]


def test_las_notas_guia_son_la_tercera_y_la_septima():
    """
    Y NO la tónica ni la quinta. Esas dos están en casi todos los acordes y no
    distinguen nada; la 3a dice si es mayor o menor y la 7a es la que lo hace
    dominante.
    """
    assert set(tablas.GRADOS_GUIA) == {3, 4, 10, 11}
    assert 0 not in tablas.GRADOS_GUIA      # la tonica no es guia
    assert 7 not in tablas.GRADOS_GUIA      # la quinta tampoco


def test_el_blues_de_doce_compases_es_el_de_la_base_de_bruno():
    """
    I IV I I | IV IV I I | V IV I V
    Es la progresión de su archivo de Band in a Box y la del estudio de Carlos
    del Junco.
    """
    assert tablas.BLUES_DOCE_COMPASES == [
        "I", "IV", "I", "I", "IV", "IV", "I", "I", "V", "IV", "I", "V"
    ]
    assert len(tablas.BLUES_DOCE_COMPASES) == 12


def test_todo_acorde_tiene_nombre_para_mostrar():
    for clave in tablas.ACORDES_INTERVALOS:
        assert clave in tablas.NOMBRES_ACORDES


# =============================================================================
# El arpegio en la armónica
# =============================================================================

def test_un_arpegio_dominante_tiene_cuatro_grados():
    acorde = teoria.arpegio("C", "F", "dominante")
    assert len(acorde.grados) == 4
    assert [g.nombre_nota for g in acorde.grados] == ["F", "A", "C", "Eb"]


def test_los_grados_llevan_su_nombre():
    acorde = teoria.arpegio("C", "F", "dominante")
    nombres = [g.nombre_grado for g in acorde.grados]
    assert nombres == ["tonica", "3a mayor", "5a", "7a menor"]


def test_el_nombre_del_acorde_se_escribe_como_un_cifrado():
    assert teoria.arpegio("C", "F", "dominante").nombre() == "F7"
    assert teoria.arpegio("C", "A", "menor").nombre() == "Am"
    assert teoria.arpegio("C", "Bb", "mayor").nombre() == "Bb"
    assert teoria.arpegio("C", "D", "menor7").nombre() == "Dm7"


def test_se_identifican_las_notas_guia_del_acorde():
    acorde = teoria.arpegio("C", "F", "dominante")
    guias = acorde.notas_guia()
    assert len(guias) == 2
    assert [g.nombre_nota for g in guias] == ["A", "Eb"]


def test_un_arpegio_de_una_armonica_que_no_existe_da_error():
    with pytest.raises(ValueError):
        teoria.arpegio("H", "F", "dominante")


def test_un_tipo_de_acorde_que_no_existe_da_error():
    with pytest.raises(ValueError):
        teoria.arpegio("C", "F", "aumentado")


def test_una_raiz_que_no_es_nota_da_error():
    with pytest.raises(ValueError):
        teoria.arpegio("C", "H", "mayor")


def test_la_raiz_se_puede_escribir_con_sostenidos():
    assert teoria.arpegio("C", "C#", "mayor").grados[0].nombre_nota == "Db"


# =============================================================================
# LA CONCILIACION contra el atril de 12a que escribió Bruno
# =============================================================================

def test_las_notas_guia_del_blues_en_fa_coinciden_con_el_atril():
    """
    EL TEST QUE VALIDA TODO EL MODULO.

    El atril de 12a que Bruno escribió a mano el 21/08 tiene esta tabla:

        Acorde | 3a              | 7a
        F7     | La = 6 aspirado | Mib = 1 o 4 overblow, u 8 soplado bendeado
        Bb7    | Re = 8 o 4 aspirado | Lab = 6 aspirado bendeado
        C7     | Mi = 5 o 8 soplado  | Sib = 6 overblow, 3 bend o 10 bend

    El calculo tiene que dar lo mismo, salvo los overblows que no estan en V1.
    """
    fa = teoria.arpegio("C", "F", "dominante")
    sib = teoria.arpegio("C", "Bb", "dominante")
    do = teoria.arpegio("C", "C", "dominante")

    assert facil(fa, 4) == "-6"          # La, la 3a de F7
    assert facil(fa, 10) == "8'"         # Mib, la 7a de F7

    assert facil(sib, 4) == "-4"         # Re, la 3a de Bb7
    assert facil(sib, 10) == "-6'"       # Lab, la 7a de Bb7

    assert facil(do, 4) == "5"           # Mi, la 3a de C7
    assert facil(do, 10) == "-3'"        # Sib, la 7a de C7


def test_el_lab_del_seis_bendeado_es_la_septima_de_sib():
    """
    La nota guía que el profe subrayó el 11/08 y confirmó el 18/08, y que Bruno
    tenía anotada como confirmada en su registro.
    """
    sib = teoria.arpegio("C", "Bb", "dominante")
    septima = [g for g in sib.grados if g.intervalo == 10][0]
    assert septima.nombre_nota == "Ab"
    assert septima.el_mas_facil().como_tab("guion") == "-6'"


def test_prefiere_el_registro_central_y_no_el_grave():
    """
    LA CORRECCION QUE HIZO COINCIDIR EL CALCULO CON EL ATRIL.

    El Re de Sib7 esta en el 1, el 4 y el 8 aspirados. La primera version de la
    funcion elegia el mas grave, o sea el 1, porque ordenaba por numero de
    agujero. Pero el registro grave cuesta aislarlo y suena flojo: el atril de
    Bruno llama al registro central "la octava que no pide nada".

    Ahora gana el mas cercano al centro de la armonica.
    """
    sib = teoria.arpegio("C", "Bb", "dominante")
    tercera = [g for g in sib.grados if g.intervalo == 4][0]

    disponibles = [n.como_tab("guion") for n in tercera.agujeros]
    assert "-1" in disponibles and "-4" in disponibles and "-8" in disponibles
    assert tercera.el_mas_facil().como_tab("guion") == "-4"


def test_una_nota_natural_le_gana_a_un_bend():
    """El primer criterio: lo que sale con aire natural va antes que un bend."""
    do = teoria.arpegio("C", "C", "dominante")
    tonica = do.grados[0]
    assert tonica.el_mas_facil().bend == 0


# =============================================================================
# Lo que la armónica no puede dar
# =============================================================================

def test_se_reportan_los_grados_que_no_salen():
    """
    En armónica de Do, la 7a de Sol7 es Fa y sale; pero hay acordes cuyos
    grados no existen sin overblow. Hay que decirlo en vez de callarlo.
    """
    for raiz in tablas.NOMBRES_NOTAS:
        acorde = teoria.arpegio("C", raiz, "dominante")
        for grado in acorde.faltantes():
            assert not grado.disponible()


def test_el_arpegio_de_fa_sale_entero_en_armonica_de_do():
    acorde = teoria.arpegio("C", "F", "dominante")
    assert acorde.faltantes() == []


def test_sin_bends_devuelve_solo_los_naturales():
    acorde = teoria.arpegio("C", "F", "dominante")
    for grado in acorde.grados:
        for nota in grado.sin_bends():
            assert nota.bend == 0


# =============================================================================
# La progresión de doce compases
# =============================================================================

def test_la_progresion_tiene_doce_compases():
    progresion = teoria.progresion_de_blues("C", 12)
    assert len(progresion) == 12
    assert [c["compas"] for c in progresion] == list(range(1, 13))


def test_la_progresion_en_doceava_con_armonica_de_do_da_fa_sib_do():
    """
    Es exactamente lo que muestra la pantalla de Band in a Box de Bruno:
    F7 Bb7 F7 F7 | Bb7 Bb7 F7 F7 | C7 Bb7 F7 C7
    """
    nombres = [c["acorde"].nombre() for c in teoria.progresion_de_blues("C", 12)]
    assert nombres == ["F7", "Bb7", "F7", "F7", "Bb7", "Bb7",
                       "F7", "F7", "C7", "Bb7", "F7", "C7"]


def test_la_progresion_en_segunda_posicion_da_sol_do_re():
    nombres = [c["acorde"].nombre() for c in teoria.progresion_de_blues("C", 2)]
    assert nombres[0] == "G7"
    assert set(nombres) == {"G7", "C7", "D7"}


def test_se_marcan_los_compases_donde_cambia_el_acorde():
    """
    Los mismos que usa el análisis de ritmo para separar los cambios del resto.
    En el blues de doce: el 1, 2, 3, 5, 7, 9, 10, 11 y 12.
    """
    progresion = teoria.progresion_de_blues("C", 12)
    cambian = [c["compas"] for c in progresion if c["cambia"]]
    assert cambian == [1, 2, 3, 5, 7, 9, 10, 11, 12]


def test_los_compases_de_cambio_coinciden_con_los_del_analisis_de_ritmo():
    """
    CONCILIACION ENTRE DOS MODULOS.

    ritmo.py tiene la lista de compases de cambio escrita a mano para poder
    separar esos momentos del resto. teoria.py la deduce de la progresión.
    Las dos tienen que decir lo mismo, o el análisis estaría mirando compases
    equivocados.
    """
    from armonica import ritmo

    progresion = teoria.progresion_de_blues("C", 12)
    # El compás 1 no es un "cambio" para el análisis: es el comienzo.
    calculados = [c["compas"] for c in progresion if c["cambia"] and c["compas"] > 1]

    assert calculados == ritmo.COMPASES_DE_CAMBIO_BLUES


def test_la_progresion_funciona_en_las_doce_posiciones():
    for posicion in range(1, 13):
        progresion = teoria.progresion_de_blues("C", posicion)
        assert len(progresion) == 12
        assert all(c["acorde"].grados for c in progresion)


def test_la_progresion_funciona_con_las_cuatro_armonicas_de_bruno():
    for tonalidad in tablas.TONALIDADES_DISPONIBLES:
        progresion = teoria.progresion_de_blues(tonalidad, 2)
        # En 2a posicion el I es siempre una quinta arriba de la armonica.
        from armonica import posiciones
        esperado = posiciones.tonalidad_resultante(tonalidad, 2)
        assert progresion[0]["acorde"].raiz == esperado
