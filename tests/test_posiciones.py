"""
Tests de armonica/posiciones.py — tonalidad por posición y pertenencia a escalas.

Sin audio, sin micrófono. Todo teoría verificable contra cualquier método de
armónica o contra el círculo de quintas.

Cómo correrlos:   python -m pytest tests/test_posiciones.py -v
"""

import pytest

from armonica import mapeo, posiciones, tablas


# =============================================================================
# tonalidad_resultante — en qué tono estás tocando
# =============================================================================

def test_primera_posicion_es_la_tonalidad_de_la_armonica():
    """En 1a posición tocás en el tono de la armónica. Es la definición."""
    for tonalidad in tablas.TONALIDADES_DISPONIBLES:
        assert posiciones.tonalidad_resultante(tonalidad, 1) == tonalidad


def test_las_posiciones_de_la_armonica_en_do():
    """
    Los casos que hay que saber de memoria si tocás con una armónica en Do.
    Son los que aparecen en tus clases.
    """
    assert posiciones.tonalidad_resultante("C", 1) == "C"
    assert posiciones.tonalidad_resultante("C", 2) == "G"    # blues, la más usada
    assert posiciones.tonalidad_resultante("C", 3) == "D"    # Re menor
    assert posiciones.tonalidad_resultante("C", 4) == "A"    # La menor, Minor Swing
    assert posiciones.tonalidad_resultante("C", 5) == "E"    # E7, Minor Swing
    assert posiciones.tonalidad_resultante("C", 12) == "F"   # lo que estudiás ahora


def test_la_armonica_en_re_en_segunda_posicion_toca_en_la():
    """
    Es el caso de tu primera clase, la del 21/01: armónica en Re, 2a posición,
    notas del acorde de La. Verificado contra el círculo de quintas.
    """
    assert posiciones.tonalidad_resultante("D", 2) == "A"


def test_las_otras_armonicas_de_bruno():
    assert posiciones.tonalidad_resultante("G", 2) == "D"
    assert posiciones.tonalidad_resultante("A", 2) == "E"
    assert posiciones.tonalidad_resultante("A", 3) == "B"
    assert posiciones.tonalidad_resultante("G", 12) == "C"


def test_la_doceava_baja_una_quinta_o_sube_una_cuarta():
    """
    La 12a posición es el paso hacia atrás en el círculo de quintas. Por eso
    agrega un bemol en vez de un sostenido, que es justo como te lo explicó
    el profe: Do -> Fa agrega Sib.
    """
    assert posiciones.tonalidad_resultante("C", 12) == "F"
    assert posiciones.tonalidad_resultante("G", 12) == "C"
    assert posiciones.tonalidad_resultante("D", 12) == "G"
    assert posiciones.tonalidad_resultante("A", 12) == "D"


def test_dar_la_vuelta_por_las_doce_posiciones_recorre_las_doce_tonalidades():
    """
    Si las posiciones son el círculo de quintas, recorrer las doce tiene que
    darte las doce tonalidades sin repetir ninguna. Es una comprobación fuerte
    de que la tabla de posiciones está bien.
    """
    tonos = {posiciones.tonalidad_resultante("C", p) for p in range(1, 13)}
    assert len(tonos) == 12


def test_una_posicion_que_no_existe_da_error():
    with pytest.raises(ValueError):
        posiciones.tonalidad_resultante("C", 13)
    with pytest.raises(ValueError):
        posiciones.tonalidad_resultante("C", 0)


def test_una_armonica_que_no_existe_da_error():
    with pytest.raises(ValueError):
        posiciones.tonalidad_resultante("H", 2)


# =============================================================================
# Nombres y descripciones para mostrar
# =============================================================================

def test_las_tres_primeras_posiciones_tienen_apodo():
    assert "cross harp" in posiciones.nombre_de_posicion(2)
    assert "straight harp" in posiciones.nombre_de_posicion(1)


def test_la_descripcion_completa_dice_todo_lo_necesario():
    """Es la línea que va arriba de la pantalla durante la sesión."""
    texto = posiciones.descripcion_completa("C", 2, "blues")
    assert "Armonica en C" in texto
    assert "2a posicion" in texto
    assert "tocas en G" in texto
    assert "blues" in texto.lower()


def test_la_descripcion_funciona_sin_escala():
    texto = posiciones.descripcion_completa("C", 12)
    assert "tocas en F" in texto


# =============================================================================
# Qué posiciones tienen tabla escrita a mano
# =============================================================================

def test_las_seis_posiciones_de_bruno_tienen_tabla():
    """Las que trabaja con el profe: 1a, 2a, 3a, 4a, 5a y 12a."""
    for posicion in (1, 2, 3, 4, 5, 12):
        assert posiciones.tiene_tabla_explicita(posicion)


def test_las_otras_posiciones_no_tienen_tabla_y_esta_bien():
    """No es un error: las cubre teoria.py por cálculo."""
    for posicion in (6, 7, 8, 9, 10, 11):
        assert not posiciones.tiene_tabla_explicita(posicion)


def test_pedir_una_escala_sin_tabla_da_un_error_que_explica_que_hacer():
    with pytest.raises(ValueError, match="teoria"):
        posiciones.agujeros_de_escala(7, "blues")


# =============================================================================
# agujeros_de_escala — la tabla explícita
# =============================================================================

def test_la_escala_de_blues_de_segunda_tiene_los_agujeros_del_riff_clasico():
    """
    El riff que todo el mundo aprende primero: ↓2 ↓3' ↑4 ↓4' ↓4 ↓5 ↑6.
    Todos tienen que estar en la escala de blues de 2a posición.
    """
    escala = posiciones.agujeros_de_escala(2, "blues")
    for tablatura in ["-2", "-3'", "4", "-4'", "-4", "-5", "6"]:
        assert tablatura in escala


def test_el_turnaround_del_catorce_de_abril_mezcla_escala_y_notas_del_acorde():
    """
    El turnaround de blues que trabajaste el 14/04, en 2a posición:
    2 aspirado, 3 aspirado, 2 soplado, 2 aspirado, 1 aspirado con bend,
    1 aspirado, 5 aspirado, 6 soplado.

    Este test documenta algo que importa para entender la pantalla de la app:
    UN TURNAROUND DE VERDAD NO ENTRA ENTERO EN LA ESCALA DE BLUES, y eso no
    tiene nada de malo.

    Casi todo el turnaround sí está en la escala. Pero el ↓3 es Si, la tercera
    MAYOR de Sol, y la escala de blues tiene la tercera menor (Sib, el ↓3').
    El Si no está "mal": es una nota del acorde de Sol7 (Sol Si Re Fa) y es
    justamente la alternancia entre tercera mayor y menor la que suena a blues.
    Es el mismo "sabor" del que habló el profe el 04/08.

    Conclusión para la app: cuando la pantalla marque una nota en amarillo por
    estar fuera de la escala, eso es información, no un reproche. Por eso el
    resumen va a contar las notas fuera de escala como dato y no como error.
    """
    escala = posiciones.agujeros_de_escala(2, "blues")

    # La mayor parte del turnaround está en la escala de blues.
    for tablatura in ["-2", "-1'", "-1", "-5", "6"]:
        assert tablatura in escala, f"{tablatura} deberia estar en la escala de blues de 2a"

    # El ↓3 no. Es la tercera mayor, nota del acorde y no de la escala.
    assert "-3" not in escala
    assert mapeo.tab_a_nota("-3", "C").nombre == "B4"

    # Y su vecino de medio tono, el ↓3', sí está: es la tercera menor.
    assert "-3'" in escala
    assert mapeo.tab_a_nota("-3'", "C").nombre == "Bb4"


def test_la_melodia_de_saint_james_esta_en_la_escala_de_blues_de_tercera():
    """
    La melodía del 26/05: bend del 6, 5 aspirado, 6 soplado, 6 aspirado.
    El bend del 6 (↓6') es el Lab, la única blue note de Re en toda la armónica.
    """
    escala = posiciones.agujeros_de_escala(3, "blues")
    for tablatura in ["-6'", "-5", "6", "-6"]:
        assert tablatura in escala


def test_las_escalas_vienen_ordenadas_de_grave_a_agudo():
    """
    Importa para la pantalla y para el modo teoría: querés leerlas como se
    tocan, de izquierda a derecha de la armónica.
    """
    for (posicion, escala) in tablas.ESCALAS_POR_POSICION:
        lista = posiciones.agujeros_de_escala(posicion, escala)
        midis = [mapeo.tab_a_nota(t, "C").midi for t in lista]
        assert midis == sorted(midis), (
            f"La escala {escala} de la {posicion}a no esta ordenada"
        )


def test_modificar_la_lista_devuelta_no_rompe_la_tabla_original():
    """
    agujeros_de_escala devuelve una COPIA. Si devolviera la lista original,
    cualquiera podría vaciarla sin querer y romperla para todo el programa.
    """
    primera = posiciones.agujeros_de_escala(2, "blues")
    primera.clear()
    segunda = posiciones.agujeros_de_escala(2, "blues")
    assert len(segunda) > 0


# =============================================================================
# notas_de_escala — la escala con las notas que suenan
# =============================================================================

def test_notas_de_escala_trae_agujero_y_nota():
    lista = posiciones.notas_de_escala("C", 12, "pentatonica_mayor")
    primera = lista[0]
    assert hasattr(primera, "agujero")
    assert hasattr(primera, "nombre")


def test_los_mismos_agujeros_suenan_distinto_en_cada_armonica():
    """
    La propiedad central de las posiciones: los agujeros no cambian, las notas sí.
    La escala de blues de 2a usa los mismos agujeros en Do que en Sol.
    """
    en_do = posiciones.notas_de_escala("C", 2, "blues")
    en_sol = posiciones.notas_de_escala("G", 2, "blues")

    agujeros_do = [(n.agujero, n.direccion, n.bend) for n in en_do]
    agujeros_sol = [(n.agujero, n.direccion, n.bend) for n in en_sol]
    assert agujeros_do == agujeros_sol

    # Pero las notas son otras.
    assert [n.nombre for n in en_do] != [n.nombre for n in en_sol]


# =============================================================================
# nota_en_escala — la pregunta que hace la pantalla en cada nota
# =============================================================================

def test_una_nota_de_la_escala_esta_en_la_escala():
    nota = mapeo.tab_a_nota("-2", "C")     # Sol4, la tónica de 2a posición
    assert posiciones.nota_en_escala(nota, "C", 2, "blues")


def test_una_nota_fuera_de_la_escala_no_esta():
    """
    El ↑2 es Mi4. En la escala de blues de Sol no hay Mi, así que la pantalla
    lo tiene que marcar en amarillo.
    """
    nota = mapeo.tab_a_nota("2", "C")
    assert not posiciones.nota_en_escala(nota, "C", 2, "blues")


def test_la_pertenencia_no_mira_la_octava():
    """
    Si el Do está en la escala, está en todos los registros. Es correcto
    musicalmente y evita depender de hasta dónde llega cada tabla.
    """
    grave = mapeo.tab_a_nota("1", "C")     # C4
    agudo = mapeo.tab_a_nota("10", "C")    # C7
    assert posiciones.nota_en_escala(grave, "C", 2, "blues")
    assert posiciones.nota_en_escala(agudo, "C", 2, "blues")


def test_nota_none_no_rompe_nada():
    """
    El mapeo devuelve None cuando no reconoció la nota. La pantalla va a llamar
    a esta función igual, y no puede explotar.
    """
    assert posiciones.nota_en_escala(None, "C", 2, "blues") is False


def test_el_dos_soplado_no_esta_en_la_doceava_y_por_eso_el_profe_dice_que_lo_evites():
    """
    En la clase del 25/08 el profe dijo "evitar el ↑2" tocando el blues en Fa.
    El ↑2 es Mi, la séptima mayor de Fa, que choca con el Mib del acorde de Fa7.
    La app tiene que marcarlo como fuera de escala, sin que nadie se lo diga.
    """
    nota = mapeo.tab_a_nota("2", "C")
    assert nota.nombre == "E4"
    assert not posiciones.nota_en_escala(nota, "C", 12, "pentatonica_mayor")
    assert not posiciones.nota_en_escala(nota, "C", 12, "blues")


def test_el_cinco_aspirado_es_la_tonica_de_la_doceava():
    """
    Tu atril dice que el ↓5 es la tónica en 12a, y que hay que vibrarlo sin
    bajar el tono. Verificado: el 5 aspirado de una armónica en Do es Fa.
    """
    nota = mapeo.tab_a_nota("-5", "C")
    assert nota.nombre == "F5"
    assert posiciones.tonalidad_resultante("C", 12) == "F"
    assert posiciones.nota_en_escala(nota, "C", 12, "pentatonica_mayor")


def test_el_siete_aspirado_es_la_blue_note_de_la_doceava_y_sale_sin_bend():
    """
    El "regalo" de la 12a posición según tu atril: el ↓7 es Si, la quinta bemol
    de Fa, y sale sin ningún bend.
    """
    nota = mapeo.tab_a_nota("-7", "C")
    assert nota.nombre == "B5"
    assert nota.bend == 0
    assert posiciones.nota_en_escala(nota, "C", 12, "blues")


# =============================================================================
# nombres_de_escala — las notas en abstracto
# =============================================================================

def test_la_pentatonica_mayor_de_la_doceava_en_do_es_fa_sol_la_do_re():
    assert posiciones.nombres_de_escala("C", 12, "pentatonica_mayor") == [
        "F", "G", "A", "C", "D"
    ]


def test_la_pentatonica_menor_de_segunda_en_do_es_sol_sib_do_re_fa():
    assert posiciones.nombres_de_escala("C", 2, "pentatonica_menor") == [
        "G", "Bb", "C", "D", "F"
    ]


def test_la_escala_de_blues_de_segunda_agrega_la_quinta_bemol():
    """La blue note de Sol es Reb."""
    menor = posiciones.nombres_de_escala("C", 2, "pentatonica_menor")
    blues = posiciones.nombres_de_escala("C", 2, "blues")
    assert set(blues) - set(menor) == {"Db"}


def test_la_pentatonica_de_re_menor_y_la_de_fa_mayor_son_las_mismas_notas():
    """
    La respuesta a tu pregunta abierta del 25/08. Tocar Re menor sobre Fa y
    tocar la pentatónica de Fa son lo mismo: cinco notas idénticas.
    Por eso las dos frases del recap eran ciertas a la vez.
    """
    re_menor = posiciones.nombres_de_escala("C", 3, "pentatonica_menor")
    fa_mayor = posiciones.nombres_de_escala("C", 12, "pentatonica_mayor")
    assert set(re_menor) == set(fa_mayor) == {"D", "F", "G", "A", "C"}
