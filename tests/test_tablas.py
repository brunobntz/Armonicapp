"""
Tests de armonica/tablas.py — coherencia interna de las tablas musicales.

tablas.py son datos escritos a mano, y los datos escritos a mano tienen erratas.
Estos tests no verifican teoría musical avanzada (eso llega en el paso 3, cuando
teoria.py calcule las escalas y las comparemos con las tablas explícitas).
Acá verificamos que las tablas sean estructuralmente sanas: los tamaños correctos,
sin duplicados, y que los bends declarados sean FÍSICAMENTE POSIBLES en la armónica.

Ese último punto es el más valioso: atrapa el error de decir que un agujero se
puede doblar más de lo que la distancia entre sus dos lengüetas permite.

Cómo correrlos:   python -m pytest tests/test_tablas.py -v
"""

import re

import pytest

from armonica import tablas


# =============================================================================
# Afinación Richter — el mapa físico de la armónica
# =============================================================================

def test_la_armonica_tiene_diez_agujeros():
    assert len(tablas.AFINACION_SOPLADO) == 10
    assert len(tablas.AFINACION_ASPIRADO) == 10


def test_las_notas_suben_de_izquierda_a_derecha():
    """
    En una armónica, el agujero 1 es el más grave y el 10 el más agudo,
    tanto soplando como aspirando. Si esto falla, hay un número mal copiado.
    """
    for i in range(9):
        assert tablas.AFINACION_SOPLADO[i] < tablas.AFINACION_SOPLADO[i + 1]
        assert tablas.AFINACION_ASPIRADO[i] < tablas.AFINACION_ASPIRADO[i + 1]


def test_el_agujero_uno_soplado_es_la_raiz():
    """Toda la tabla se mide desde ahí, así que tiene que valer 0 por definición."""
    assert tablas.AFINACION_SOPLADO[0] == 0


def test_los_soplados_forman_un_acorde_mayor_en_tres_octavas():
    """
    El diseño Richter apila el acorde mayor (tónica, tercera, quinta) tres veces.
    En clases de nota: 0, 4, 7 repetido. Es lo que permite soplar varios agujeros
    juntos y que suene un acorde afinado.
    """
    clases = [semitono % 12 for semitono in tablas.AFINACION_SOPLADO]
    assert clases == [0, 4, 7, 0, 4, 7, 0, 4, 7, 0]


def test_la_armonica_abarca_tres_octavas():
    """Del agujero 1 soplado al 10 soplado hay exactamente 36 semitonos."""
    assert tablas.AFINACION_SOPLADO[9] - tablas.AFINACION_SOPLADO[0] == 36


# =============================================================================
# Bends — que sean físicamente posibles
# =============================================================================

def test_los_bends_aspirados_estan_en_agujeros_donde_el_aspirado_es_mas_agudo():
    """
    Solo se puede bajar la nota más aguda del agujero hacia la más grave.
    Si un agujero tiene bend aspirado, su aspirado tiene que ser MÁS AGUDO
    que su soplado. Esto es física de la lengüeta, no convención.
    """
    for agujero in tablas.BENDS_ASPIRADOS:
        indice = agujero - 1
        soplado = tablas.AFINACION_SOPLADO[indice]
        aspirado = tablas.AFINACION_ASPIRADO[indice]
        assert aspirado > soplado, (
            f"El agujero {agujero} declara bends aspirados, pero su aspirado "
            f"({aspirado}) no es más agudo que su soplado ({soplado})"
        )


def test_los_bends_soplados_estan_en_agujeros_donde_el_soplado_es_mas_agudo():
    """La misma regla, al revés: es el caso de los agujeros 8, 9 y 10."""
    for agujero in tablas.BENDS_SOPLADOS:
        indice = agujero - 1
        soplado = tablas.AFINACION_SOPLADO[indice]
        aspirado = tablas.AFINACION_ASPIRADO[indice]
        assert soplado > aspirado, (
            f"El agujero {agujero} declara bends soplados, pero su soplado "
            f"({soplado}) no es más agudo que su aspirado ({aspirado})"
        )


def test_ningun_bend_llega_a_la_otra_nota_del_agujero():
    """
    ESTE ES EL TEST IMPORTANTE. Un bend baja la nota HACIA la otra lengüeta del
    mismo agujero, pero nunca la alcanza: se queda al menos un semitono antes.
    Entonces la cantidad de bends siempre es menor que la distancia entre las
    dos notas del agujero.

    Ejemplo: el agujero 3 en C tiene soplado G4 y aspirado B4. Hay 4 semitonos
    de distancia, así que como mucho puede tener 3 bends. Si alguien escribiera
    4, este test lo atrapa.
    """
    for agujero, cantidad_bends in tablas.BENDS_ASPIRADOS.items():
        indice = agujero - 1
        distancia = tablas.AFINACION_ASPIRADO[indice] - tablas.AFINACION_SOPLADO[indice]
        assert cantidad_bends < distancia, (
            f"El agujero {agujero} aspirado declara {cantidad_bends} bends, pero "
            f"solo hay {distancia} semitonos hasta el soplado. Como máximo "
            f"{distancia - 1} bends."
        )

    for agujero, cantidad_bends in tablas.BENDS_SOPLADOS.items():
        indice = agujero - 1
        distancia = tablas.AFINACION_SOPLADO[indice] - tablas.AFINACION_ASPIRADO[indice]
        assert cantidad_bends < distancia, (
            f"El agujero {agujero} soplado declara {cantidad_bends} bends, pero "
            f"solo hay {distancia} semitonos hasta el aspirado."
        )


def test_el_agujero_cinco_y_el_siete_no_tienen_bend():
    """
    Casos conocidos que conviene fijar por escrito:
      - El 5 tiene soplado y aspirado a 1 semitono: no entra ningún bend.
      - El 7 también está a 1 semitono, en el otro sentido.
    (El 5 tiene un bend de cuarto de tono en la vida real, pero no es un
    semitono y no se puede escribir en tablatura.)
    """
    assert 5 not in tablas.BENDS_ASPIRADOS
    assert 7 not in tablas.BENDS_ASPIRADOS
    assert 5 not in tablas.BENDS_SOPLADOS
    assert 7 not in tablas.BENDS_SOPLADOS


def test_todos_los_agujeros_con_bend_estan_entre_uno_y_diez():
    for agujero in list(tablas.BENDS_ASPIRADOS) + list(tablas.BENDS_SOPLADOS):
        assert 1 <= agujero <= 10


def test_los_bends_llegan_hasta_tono_y_medio():
    """
    Como máximo se baja un tono y medio: son los tres bends del agujero 3.

    Ese tercer bend (el Lab en una armónica de Do) se incorporó el 02/09. Al
    principio estaba afuera y era un error: Leandro lo enseña, y es la blue
    note de la 12a posición en el registro grave.

    Ningún otro agujero llega a tres. Es una particularidad del 3, que tiene
    cuatro semitonos entre su soplado y su aspirado.
    """
    todos = list(tablas.BENDS_ASPIRADOS.values()) + list(tablas.BENDS_SOPLADOS.values())
    assert all(1 <= cantidad <= 3 for cantidad in todos)
    assert tablas.BENDS_ASPIRADOS[3] == 3
    assert max(c for a, c in tablas.BENDS_ASPIRADOS.items() if a != 3) == 2


# =============================================================================
# Tonalidades de armónica
# =============================================================================

def test_estan_las_doce_tonalidades():
    assert len(tablas.TONALIDADES) == 12


def test_las_cuatro_armonicas_de_bruno_estan_en_la_tabla():
    """C, G, D y A son las que hay para probar en vivo."""
    for tonalidad in tablas.TONALIDADES_DISPONIBLES:
        assert tonalidad in tablas.TONALIDADES


def test_la_armonica_en_c_arranca_en_el_do_central():
    assert tablas.TONALIDADES["C"] == 60


def test_la_de_g_es_la_mas_grave_y_la_de_fa_sostenido_la_mas_aguda():
    """
    Las armónicas diatónicas estándar cubren un rango contiguo de un año...
    perdón, de una octava justa: de G3 a F#4. Sirve para acotar el rango de
    frecuencias que el detector de tono tiene que cubrir.
    """
    valores = list(tablas.TONALIDADES.values())
    assert min(valores) == tablas.TONALIDADES["G"] == 55
    assert max(valores) == tablas.TONALIDADES["F#"] == 66
    # Y no hay huecos: son 12 semitonos seguidos.
    assert sorted(valores) == list(range(55, 67))


# =============================================================================
# Posiciones
# =============================================================================

def test_estan_las_doce_posiciones():
    assert sorted(tablas.POSICIONES.keys()) == list(range(1, 13))


def test_las_posiciones_siguen_el_circulo_de_quintas():
    """
    Cada posición es una quinta justa (7 semitonos) más arriba que la anterior,
    dando la vuelta al llegar a la octava.

    Este test compara la tabla escrita a mano contra la fórmula. Es el mismo
    truco que vamos a usar en el paso 3 con las escalas: dos fuentes
    independientes que se validan entre sí. Si la tabla tuviera una errata,
    acá saltaría.
    """
    for numero_posicion, semitonos in tablas.POSICIONES.items():
        esperado = ((numero_posicion - 1) * 7) % 12
        assert semitonos == esperado, (
            f"La posicion {numero_posicion} dice {semitonos} semitonos, "
            f"pero el circulo de quintas da {esperado}"
        )


def test_las_tres_posiciones_principales():
    """Los casos que hay que saber de memoria, fijados por escrito."""
    assert tablas.POSICIONES[1] == 0    # armónica en C -> tocás en C
    assert tablas.POSICIONES[2] == 7    # armónica en C -> tocás en G
    assert tablas.POSICIONES[3] == 2    # armónica en C -> tocás en D


def test_toda_posicion_tiene_nombre_para_mostrar():
    for numero_posicion in tablas.POSICIONES:
        assert numero_posicion in tablas.NOMBRES_POSICIONES
        assert tablas.NOMBRES_POSICIONES[numero_posicion]


# =============================================================================
# Escalas por intervalos
# =============================================================================

def test_las_escalas_empiezan_en_la_tonica():
    """El primer grado de cualquier escala es la tónica: 0 semitonos."""
    for intervalos in tablas.ESCALAS_INTERVALOS.values():
        assert intervalos[0] == 0


def test_las_escalas_estan_ordenadas_y_sin_repetir():
    for nombre, intervalos in tablas.ESCALAS_INTERVALOS.items():
        assert intervalos == sorted(intervalos), f"{nombre} no está ordenada"
        assert len(intervalos) == len(set(intervalos)), f"{nombre} tiene notas repetidas"


def test_las_escalas_caben_en_una_octava():
    """Los intervalos van de 0 a 11. El 12 sería otra vez la tónica."""
    for intervalos in tablas.ESCALAS_INTERVALOS.values():
        assert all(0 <= i <= 11 for i in intervalos)


def test_las_pentatonicas_tienen_cinco_notas():
    """Penta = cinco. Si tienen otra cantidad, algo está mal."""
    assert len(tablas.ESCALAS_INTERVALOS["pentatonica_mayor"]) == 5
    assert len(tablas.ESCALAS_INTERVALOS["pentatonica_menor"]) == 5


def test_la_escala_de_blues_es_la_pentatonica_menor_mas_la_blue_note():
    """
    La escala de blues es exactamente la pentatónica menor con una nota extra:
    la quinta bemol (6 semitonos), que es la que da la tensión característica.
    """
    menor = set(tablas.ESCALAS_INTERVALOS["pentatonica_menor"])
    blues = set(tablas.ESCALAS_INTERVALOS["blues"])
    assert menor.issubset(blues)
    assert blues - menor == {6}


def test_toda_escala_tiene_nombre_para_mostrar():
    for nombre in tablas.ESCALAS_INTERVALOS:
        assert nombre in tablas.NOMBRES_ESCALAS


# =============================================================================
# Escalas por posición — las tablas explícitas en agujeros
# =============================================================================

# Una tablatura válida es: un guión opcional (aspirado), un número de agujero
# del 1 al 10, y cero, uno o dos apóstrofos (los bends).
PATRON_TABLATURA = re.compile(r"^-?(10|[1-9])'{0,3}$")


def test_hay_tabla_para_cada_posicion_estudiada_y_cada_escala():
    """
    Las seis posiciones que Bruno trabaja con Leandro (1a, 2a, 3a, 4a, 5a y 12a)
    por tres escalas = dieciocho tablas.

    Las otras seis posiciones no tienen tabla explícita a propósito: las cubre
    teoria.py por cálculo, en el paso 3.
    """
    for posicion in tablas.POSICIONES_CON_TABLA:
        for escala in tablas.ESCALAS_INTERVALOS:
            assert (posicion, escala) in tablas.ESCALAS_POR_POSICION, (
                f"Falta la tabla de {escala} en la posicion {posicion}"
            )
    esperadas = len(tablas.POSICIONES_CON_TABLA) * len(tablas.ESCALAS_INTERVALOS)
    assert len(tablas.ESCALAS_POR_POSICION) == esperadas


def test_la_pentatonica_mayor_de_doceava_no_pide_bends_del_cuatro_para_arriba():
    """
    El hecho que hace amable a la 12a posición, y la razón por la que Leandro
    empuja la pentatónica y no la escala mayor completa: del agujero 4 al 10
    la escala sale entera con aire natural, sin un solo bend.

    Lo fijamos por escrito porque es el argumento pedagógico central de lo que
    Bruno está estudiando ahora.
    """
    escala = tablas.ESCALAS_POR_POSICION[(12, "pentatonica_mayor")]
    del_cuatro_para_arriba = [
        tab for tab in escala if int(tab.strip("-'")) >= 4
    ]
    assert len(del_cuatro_para_arriba) == 11
    assert all("'" not in tab for tab in del_cuatro_para_arriba)


def test_todas_las_tablaturas_estan_bien_escritas():
    """
    Atrapa erratas del tipo "-11", "4'''" o "x". Es el test que más veces salva
    de un error tonto al escribir tablas a mano.
    """
    for clave, tablatura_lista in tablas.ESCALAS_POR_POSICION.items():
        for tablatura in tablatura_lista:
            assert PATRON_TABLATURA.match(tablatura), (
                f"La tablatura {tablatura!r} de {clave} está mal escrita"
            )


def test_ninguna_escala_repite_agujeros():
    for clave, tablatura_lista in tablas.ESCALAS_POR_POSICION.items():
        assert len(tablatura_lista) == len(set(tablatura_lista)), (
            f"La escala {clave} tiene agujeros repetidos"
        )


def test_ninguna_escala_esta_vacia():
    for clave, tablatura_lista in tablas.ESCALAS_POR_POSICION.items():
        assert len(tablatura_lista) >= 5, f"La escala {clave} tiene muy pocas notas"


def test_los_bends_de_las_escalas_existen_de_verdad():
    """
    Si una tabla de escala dice "-3''", el agujero 3 aspirado tiene que tener
    al menos 2 bends declarados en BENDS_ASPIRADOS. Este test conecta las dos
    tablas y atrapa el error de pedir un bend que la armónica no puede hacer.

    Un detalle de cómo está escrito: en vez de cortar en el primer error,
    juntamos TODOS los problemas en una lista y recién al final fallamos.
    Es más trabajo, pero cuando revisás nueve tablas escritas a mano querés ver
    los cinco errores de una vez, no descubrirlos de a uno corriendo el test
    cinco veces. (Nos pasó exactamente eso al escribir estas tablas.)
    """
    problemas = []

    for clave, tablatura_lista in tablas.ESCALAS_POR_POSICION.items():
        for tablatura in tablatura_lista:
            cantidad_bends = tablatura.count("'")
            if cantidad_bends == 0:
                continue

            es_aspirado = tablatura.startswith("-")
            agujero = int(tablatura.strip("-'"))

            if es_aspirado:
                disponibles = tablas.BENDS_ASPIRADOS.get(agujero, 0)
                direccion = "aspirado"
            else:
                disponibles = tablas.BENDS_SOPLADOS.get(agujero, 0)
                direccion = "soplado"

            if cantidad_bends > disponibles:
                problemas.append(
                    f"  {clave} pide {tablatura!r}: {cantidad_bends} bend(s) en el "
                    f"agujero {agujero} {direccion}, pero hay {disponibles} disponible(s)"
                )

    assert not problemas, "Bends imposibles en las tablas:\n" + "\n".join(problemas)


def test_la_pentatonica_menor_de_segunda_posicion_tiene_las_notas_clave():
    """
    La escala más importante de toda la armónica de blues. Fijamos por escrito
    los agujeros que cualquier método de armónica lista para el registro medio:
    el 2 aspirado (tónica), el 3 aspirado con medio bend (tercera menor),
    el 4 soplado, el 4 aspirado, el 5 aspirado y el 6 soplado.
    """
    escala = tablas.ESCALAS_POR_POSICION[(2, "pentatonica_menor")]
    for tablatura in ["-2", "-3'", "4", "-4", "-5", "6"]:
        assert tablatura in escala, f"Falta {tablatura} en la pentatonica menor de 2a"


def test_la_escala_de_blues_de_segunda_posicion_agrega_la_blue_note():
    """
    Respecto de la pentatónica menor, la de blues suma exactamente la blue note.
    En 2a posición esa nota se consigue en "-1'" y en "-4'", los dos aspirados.
    """
    menor = set(tablas.ESCALAS_POR_POSICION[(2, "pentatonica_menor")])
    blues = set(tablas.ESCALAS_POR_POSICION[(2, "blues")])
    assert menor.issubset(blues)
    assert blues - menor == {"-1'", "-4'"}


# =============================================================================
# Nombres de notas
# =============================================================================

def test_hay_doce_nombres_de_nota():
    assert len(tablas.NOMBRES_NOTAS) == 12
    assert len(tablas.NOMBRES_NOTAS_SOSTENIDOS) == 12


def test_las_dos_listas_de_nombres_coinciden_en_las_teclas_blancas():
    """
    C, D, E, F, G, A y B se escriben igual con bemoles o con sostenidos.
    Solo cambian las cinco notas alteradas.
    """
    for clase in (0, 2, 4, 5, 7, 9, 11):
        assert tablas.NOMBRES_NOTAS[clase] == tablas.NOMBRES_NOTAS_SOSTENIDOS[clase]
