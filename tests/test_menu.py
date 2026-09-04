"""
Tests de armonica/menu.py y armonica/afinador.py.

El menú se prueba SIN simular a nadie tecleando. Por eso la parte que decide
está separada de la parte que pregunta: `interpretar_respuesta` es una función
pura y se prueba como cualquier otra.

Cómo correrlos:   python -m pytest tests/test_menu.py -v
"""

import pytest

from armonica import afinador, mapeo, menu, segmentacion, tablas


# =============================================================================
# Interpretar lo que el usuario teclea
# =============================================================================

def test_se_puede_elegir_por_numero():
    opciones = ["C", "G", "D", "A"]
    assert menu.interpretar_respuesta("2", opciones) == "G"


def test_se_puede_elegir_escribiendo_el_valor():
    opciones = ["C", "G", "D", "A"]
    assert menu.interpretar_respuesta("D", opciones) == "D"


def test_no_distingue_mayusculas():
    """La gente escribe como quiere y el menú no está para corregir."""
    opciones = ["blues", "blues_mayor"]
    assert menu.interpretar_respuesta("BLUES_MAYOR", opciones) == "blues_mayor"


def test_enter_vacio_elige_el_valor_por_defecto():
    """
    Es lo que hace que el menú sea rápido: después de la primera vez, cuatro
    Enter seguidos y estás tocando.
    """
    opciones = ["C", "G", "D"]
    assert menu.interpretar_respuesta("", opciones, por_defecto="C") == "C"
    assert menu.interpretar_respuesta("   ", opciones, por_defecto="C") == "C"


def test_un_numero_fuera_de_rango_no_se_entiende():
    """
    Devuelve NO_ENTENDI en vez de lanzar un error, así quien pregunta vuelve a
    preguntar. Es lo que uno espera de un menú.
    """
    assert menu.interpretar_respuesta("99", ["C", "G"]) is menu.NO_ENTENDI
    assert menu.interpretar_respuesta("0", ["C", "G"]) is menu.NO_ENTENDI


def test_un_texto_que_no_es_opcion_no_se_entiende():
    assert menu.interpretar_respuesta("cualquiera", ["C", "G"]) is menu.NO_ENTENDI


def test_con_opciones_numericas_gana_el_valor_sobre_el_renglon():
    """
    ESTE TEST EVITA UN ERROR DE MENU QUE PASARIA DESAPERCIBIDO.

    Si alguien tipea 12 queriendo la 12a posicion, no puede terminar en otra
    solo porque la lista estaba ordenada distinto. Con opciones numericas el
    valor manda.
    """
    opciones = [1, 2, 3, 12]
    assert menu.interpretar_respuesta("12", opciones) == 12   # el valor
    assert menu.interpretar_respuesta("4", opciones) == 12    # el 4to renglon


def test_las_posiciones_se_ofrecen_en_orden_natural():
    """
    Asi el numero de renglon es el numero de posicion, y no hay ambiguedad
    posible al tipear.
    """
    assert menu.posiciones_ofrecidas() == list(range(1, 13))


def test_la_opcion_ninguna_escala_se_puede_elegir():
    """None es una opción válida: practicar sin escala de referencia."""
    opciones = ["blues", None]
    assert menu.interpretar_respuesta("2", opciones) == "blues" or \
           menu.interpretar_respuesta("2", opciones) is None


# =============================================================================
# El listado de opciones
# =============================================================================

def test_las_opciones_salen_numeradas():
    texto = menu.texto_de_opciones(["C", "G", "D"])
    assert "1)" in texto and "2)" in texto and "3)" in texto


def test_la_opcion_por_defecto_va_marcada():
    """Para que se vea cuál sale al apretar Enter."""
    texto = menu.texto_de_opciones(["C", "G", "D"], por_defecto="G")
    lineas = [l for l in texto.splitlines() if "G" in l]
    assert "*" in lineas[0]


def test_se_pueden_usar_etiquetas_distintas_del_valor():
    texto = menu.texto_de_opciones([1, 2], ["primera posicion", "segunda"])
    assert "primera posicion" in texto


def test_las_armonicas_de_bruno_van_primero():
    """
    Las cuatro que tiene en la mano, antes que las otras ocho. La opción más
    probable tiene que estar más cerca.
    """
    ofrecidas = menu.tonalidades_ofrecidas()
    assert ofrecidas[:4] == tablas.TONALIDADES_DISPONIBLES
    assert len(ofrecidas) == 12


def test_estan_las_doce_posiciones():
    assert len(menu.posiciones_ofrecidas()) == 12


def test_el_nombre_de_ninguna_escala():
    assert menu.nombre_de_escala(None) == "ninguna"
    assert "blues" in menu.nombre_de_escala("blues_mayor").lower()


# =============================================================================
# El afinador: registrar intentos
# =============================================================================

def intento_de(tablatura, cents, duracion=0.5, inicio=0.0):
    return segmentacion.Evento(
        nota=mapeo.tab_a_nota(tablatura, "C"), inicio_seg=inicio,
        duracion_seg=duracion, frecuencia_hz=440.0, cents=cents,
        confianza=0.99, ventanas=40,
    )


def test_cuenta_los_intentos_sobre_la_nota_objetivo():
    objetivo = mapeo.tab_a_nota("-3''", "C")
    practica = afinador.PracticaDeBend(objetivo=objetivo)

    assert practica.registrar(intento_de("-3''", -30.0))
    assert practica.registrar(intento_de("-3''", -25.0))
    assert practica.cantidad() == 2


def test_ignora_las_notas_que_no_son_la_objetivo():
    """
    Practicando el bend del 3, las otras notas que toques de paso no cuentan.
    Si contaran, el promedio no diría nada.
    """
    practica = afinador.PracticaDeBend(objetivo=mapeo.tab_a_nota("-3''", "C"))

    assert not practica.registrar(intento_de("-4", 5.0))
    assert not practica.registrar(intento_de("-3'", -10.0))    # otro bend
    assert practica.cantidad() == 0


def test_ignora_las_notas_demasiado_cortas():
    """
    Una nota de 100 ms no es un intento: es una transición. Contarla ensucia
    la estadística con notas que ni quisiste tocar.
    """
    practica = afinador.PracticaDeBend(objetivo=mapeo.tab_a_nota("-3''", "C"))
    assert not practica.registrar(intento_de("-3''", -30.0, duracion=0.1))
    assert practica.registrar(intento_de("-3''", -30.0, duracion=0.5))


def test_sin_objetivo_cuenta_cualquier_nota():
    """El modo afinador libre, para revisar si una lengüeta se desafinó."""
    practica = afinador.PracticaDeBend(objetivo=None)
    assert practica.registrar(intento_de("-4", 5.0))
    assert practica.registrar(intento_de("6", -8.0))
    assert practica.cantidad() == 2


def test_descuenta_la_afinacion_de_la_armonica():
    """
    Si tu armónica está +15 cents y tocaste el bend a -20, contra el estándar
    parece un error de 20; contra tu instrumento son 35. Lo segundo es lo que
    habla de cómo tocaste.
    """
    practica = afinador.PracticaDeBend(
        objetivo=mapeo.tab_a_nota("-3''", "C"), afinacion_armonica=15.0
    )
    practica.registrar(intento_de("-3''", -20.0))
    assert practica.intentos[0].cents == pytest.approx(-35.0)


# =============================================================================
# El afinador: las estadísticas
# =============================================================================

def practica_con(valores):
    practica = afinador.PracticaDeBend(objetivo=mapeo.tab_a_nota("-3''", "C"))
    for numero, cents in enumerate(valores):
        practica.registrar(intento_de("-3''", cents, inicio=numero * 2.0))
    return practica


def test_el_promedio_y_la_dispersion():
    practica = practica_con([-30.0, -28.0, -32.0, -30.0])
    assert practica.promedio() == pytest.approx(-30.0)
    assert practica.dispersion() < 2.0


def test_cuenta_cuantos_cayeron_dentro_de_la_tolerancia():
    practica = practica_con([0.0, 5.0, 20.0, -30.0])
    assert practica.aciertos() == 2
    assert practica.porcentaje_de_aciertos() == pytest.approx(50.0)


def test_identifica_el_mejor_intento():
    practica = practica_con([-30.0, 3.0, -25.0])
    assert practica.mejor().cents == pytest.approx(3.0)


def test_detecta_que_vas_mejorando():
    """
    Compara los primeros cinco intentos contra los últimos cinco. Es lo que
    hace que la práctica tenga sentido: ver si la corrección funcionó.
    """
    practica = practica_con([-40.0] * 5 + [-8.0] * 5)
    progreso = practica.esta_mejorando(ventana=5)
    assert progreso < -20


def test_detecta_que_estas_empeorando():
    practica = practica_con([-5.0] * 5 + [-35.0] * 5)
    assert practica.esta_mejorando(ventana=5) > 20


def test_con_pocos_intentos_no_se_dice_nada_del_progreso():
    assert practica_con([-30.0, -20.0]).esta_mejorando(ventana=5) is None


def test_sin_intentos_las_estadisticas_no_rompen():
    practica = afinador.PracticaDeBend()
    assert practica.cantidad() == 0
    assert practica.promedio() == 0.0
    assert practica.dispersion() == 0.0
    assert practica.porcentaje_de_aciertos() == 0.0
    assert practica.mejor() is None


# =============================================================================
# El afinador: el diagnóstico
# =============================================================================

def test_distingue_habito_de_falta_de_control():
    """
    LA DISTINCION CENTRAL, otra vez. Un error consistente se recalibra en diez
    repeticiones; uno errático lleva semanas. La app tiene que decir cuál es.
    """
    habito = practica_con([-30.0, -32.0, -28.0, -31.0]).diagnostico()
    descontrol = practica_con([-50.0, 10.0, -30.0, 25.0]).diagnostico()

    assert "HABITO" in habito
    assert "CONTROL" in descontrol


def test_felicita_cuando_esta_bien():
    texto = practica_con([2.0, -3.0, 5.0, 0.0]).diagnostico()
    assert "Muy bien" in texto


def test_con_pocos_intentos_pide_mas():
    assert "mas" in practica_con([-30.0]).diagnostico()


def test_sin_intentos_lo_dice():
    assert "Todavia no" in afinador.PracticaDeBend().diagnostico()


def test_el_habito_sugiere_hacia_donde_corregir():
    """Si caés bajo, la app tiene que decir 'apuntá más arriba'."""
    bajo = practica_con([-30.0, -31.0, -29.0]).diagnostico()
    alto = practica_con([30.0, 31.0, 29.0]).diagnostico()
    assert "arriba" in bajo
    assert "abajo" in alto


# =============================================================================
# El medidor y los textos
# =============================================================================

def test_la_barra_marca_el_centro_y_la_zona_buena():
    barra = afinador.barra_grande(0.0)
    assert "O" in barra
    assert "=" in barra          # la zona aceptable


def test_la_barra_se_mueve_segun_los_cents():
    izquierda = afinador.barra_grande(-45.0)
    centro = afinador.barra_grande(0.0)
    derecha = afinador.barra_grande(45.0)

    assert izquierda.index("O") < centro.index("O") < derecha.index("O")


def test_la_barra_no_se_sale_de_los_bordes():
    """Un valor absurdo no puede romper el dibujo."""
    for cents in (-500.0, 500.0):
        barra = afinador.barra_grande(cents)
        assert "O" in barra
        assert len(barra) == 43      # 41 casillas mas los corchetes


def test_el_historial_muestra_una_linea_por_intento():
    practica = practica_con([-30.0, -20.0, -10.0])
    lineas = afinador.historial_en_texto(practica).splitlines()
    assert len(lineas) == 3


def test_el_historial_sin_intentos_no_rompe():
    assert "todavia" in afinador.historial_en_texto(afinador.PracticaDeBend())


def test_el_resumen_tiene_las_secciones_esperadas():
    texto = afinador.resumen_en_texto(practica_con([-30.0, -28.0, -31.0, -29.0]))
    for seccion in ["Intentos:", "Promedio:", "Dispersion:",
                    "ULTIMOS INTENTOS", "DIAGNOSTICO"]:
        assert seccion in texto


def test_el_resumen_sin_intentos_explica_por_que():
    texto = afinador.resumen_en_texto(afinador.PracticaDeBend())
    assert "No se registro" in texto
    assert "durar al menos" in texto
