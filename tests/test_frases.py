"""
Tests de armonica/frases.py — grabar una frase y practicar contra ella.

Las frases y los intentos se arman a mano, con tiempos que elegimos nosotros.
Así podemos meter un error de 100 ms a propósito y verificar que el informe
diga exactamente 100 ms.

Cómo correrlos:   python -m pytest tests/test_frases.py -v
"""

import pytest

from armonica import frases, mapeo, segmentacion


def evento(tablatura, inicio, duracion=0.3, cents=0.0):
    return segmentacion.Evento(
        nota=mapeo.tab_a_nota(tablatura, "C"), inicio_seg=inicio,
        duracion_seg=duracion, frecuencia_hz=440.0, cents=cents,
        confianza=0.99, ventanas=25,
    )


def eventos_de(tablaturas, paso=0.5, desde=0.0, desvios_ms=None):
    """
    Arma una serie de eventos parejos, con desvíos opcionales por nota.

    `desvios_ms` permite meter errores de tiempo a propósito, para verificar
    que el informe los detecte con el valor exacto.
    """
    lista = []
    for numero, tablatura in enumerate(tablaturas):
        corrimiento = 0.0
        if desvios_ms and numero < len(desvios_ms):
            corrimiento = desvios_ms[numero] / 1000.0
        lista.append(evento(tablatura, desde + numero * paso + corrimiento))
    return lista


def frase_de(tablaturas, paso=0.5, nombre="prueba"):
    return frases.desde_eventos(eventos_de(tablaturas, paso), nombre, "C", 12,
                                "blues_mayor")


# =============================================================================
# Crear una frase
# =============================================================================

def test_una_frase_guarda_las_notas_y_sus_tiempos():
    frase = frase_de(["-4", "-5", "6"], paso=0.5)
    assert frase.cantidad == 3
    assert frase.tablatura() == ["-4", "-5", "6"]


def test_los_tiempos_se_guardan_relativos_al_comienzo():
    """
    Así no importa cuánto silencio hubo antes de que empezaras a tocar: la
    frase arranca en cero siempre.
    """
    tarde = frases.desde_eventos(
        eventos_de(["-4", "-5", "6"], paso=0.5, desde=12.7), "tarde", "C"
    )
    temprano = frase_de(["-4", "-5", "6"], paso=0.5)

    assert tarde.notas[0].inicio_seg == pytest.approx(0.0)
    assert [n.inicio_seg for n in tarde.notas] == \
           pytest.approx([n.inicio_seg for n in temprano.notas])


def test_una_frase_sin_notas_reconocidas_da_error():
    """Preferimos un error claro a guardar una frase vacía que después falla."""
    with pytest.raises(ValueError):
        frases.desde_eventos([], "vacia", "C")


def test_la_duracion_de_la_frase():
    frase = frase_de(["-4", "-5", "6"], paso=0.5)
    # Tres notas cada 0.5 s, la última dura 0.3: total 1.3 s.
    assert frase.duracion_seg == pytest.approx(1.3, abs=0.01)


# =============================================================================
# La comparación: las notas
# =============================================================================

def test_tocar_la_frase_igual_da_todo_bien():
    frase = frase_de(["-4", "-5", "6", "-6"])
    comparacion = frases.comparar(frase, eventos_de(["-4", "-5", "6", "-6"]))

    assert comparacion.aciertos() == 4
    assert comparacion.porcentaje_de_notas() == pytest.approx(100.0)
    assert comparacion.faltantes == []
    assert comparacion.sobrantes == []


def test_detecta_una_nota_que_te_comiste():
    frase = frase_de(["-4", "-5", "6", "-6"])
    comparacion = frases.comparar(frase, eventos_de(["-4", "6", "-6"]))

    assert len(comparacion.faltantes) == 1
    assert comparacion.faltantes[0].tab == "-5"


def test_detecta_una_nota_que_agregaste():
    frase = frase_de(["-4", "-5", "6"])
    comparacion = frases.comparar(frase, eventos_de(["-4", "-5", "7", "6"]))

    assert "7" in comparacion.sobrantes


def test_detecta_una_nota_cambiada_por_otra():
    frase = frase_de(["-4", "-5", "6"])
    comparacion = frases.comparar(frase, eventos_de(["-4", "-3", "6"]))

    assert comparacion.cambiadas
    esperada, tocada = comparacion.cambiadas[0]
    assert esperada == "-5"
    assert tocada == "-3"


def test_una_nota_de_mas_en_el_medio_no_descoloca_el_resto():
    """
    POR QUE SE USA UN ALINEADOR Y NO UNA COMPARACION UNO A UNO.

    Si metés una nota extra en el medio, comparar posición por posición diría
    que todo lo que viene después está mal. El alineador encuentra los tramos
    iguales y solo marca la nota que sobra.
    """
    frase = frase_de(["-4", "-5", "6", "-6", "7"])
    comparacion = frases.comparar(
        frase, eventos_de(["-4", "-5", "-2", "6", "-6", "7"])
    )
    assert comparacion.aciertos() == 5
    assert comparacion.sobrantes == ["-2"]


def test_sin_notas_reconocidas_todo_queda_como_faltante():
    frase = frase_de(["-4", "-5", "6"])
    comparacion = frases.comparar(frase, [])
    assert len(comparacion.faltantes) == 3
    assert comparacion.aciertos() == 0


# =============================================================================
# La comparación: la velocidad global
# =============================================================================

def test_tocar_la_frase_mas_rapido_no_cuenta_como_error_de_tiempo():
    """
    EL PROBLEMA CENTRAL DEL MODULO.

    La misma frase tocada un 20% más rápido tiene TODAS las notas corridas. Si
    no separáramos la velocidad, el informe reportaría veinte errores de tiempo
    cuando en realidad la tocaste bien, solo que más ligero.
    """
    frase = frase_de(["-4", "-5", "6", "-6", "7", "-8"], paso=0.5)
    mas_rapido = eventos_de(["-4", "-5", "6", "-6", "7", "-8"], paso=0.4)

    comparacion = frases.comparar(frase, mas_rapido)

    assert comparacion.velocidad == pytest.approx(0.8, abs=0.02)
    assert comparacion.diferencia_de_velocidad() == pytest.approx(-20.0, abs=2.0)
    # Y una vez sacada la velocidad, no queda ningun desvio.
    assert comparacion.dispersion_ms() < 5.0


def test_tocar_la_frase_mas_lento_se_reporta_como_tal():
    frase = frase_de(["-4", "-5", "6", "-6", "7"], paso=0.5)
    mas_lento = eventos_de(["-4", "-5", "6", "-6", "7"], paso=0.6)

    comparacion = frases.comparar(frase, mas_lento)
    assert comparacion.diferencia_de_velocidad() == pytest.approx(20.0, abs=2.0)


def test_empezar_mas_tarde_no_cuenta_como_error():
    """El desfase global lo absorbe la ordenada de la recta."""
    frase = frase_de(["-4", "-5", "6", "-6"], paso=0.5)
    mas_tarde = eventos_de(["-4", "-5", "6", "-6"], paso=0.5, desde=3.0)

    comparacion = frases.comparar(frase, mas_tarde)
    assert comparacion.dispersion_ms() < 5.0


# =============================================================================
# La comparación: los desvíos locales
# =============================================================================

def test_detecta_una_nota_que_llego_tarde():
    """
    Todas parejas menos una, que entra 200 ms después. Ese desvío tiene que
    aparecer y las demás no.
    """
    frase = frase_de(["-4", "-5", "6", "-6", "7", "-8", "9"], paso=0.5)
    intento = eventos_de(["-4", "-5", "6", "-6", "7", "-8", "9"], paso=0.5,
                         desvios_ms=[0, 0, 0, 200, 0, 0, 0])

    comparacion = frases.comparar(frase, intento)
    peor = comparacion.peor_desvio()

    assert peor[0].tab == "-6"
    assert peor[2] == pytest.approx(200.0, abs=25.0)


def test_detecta_una_nota_que_se_adelanto():
    frase = frase_de(["-4", "-5", "6", "-6", "7", "-8", "9"], paso=0.5)
    intento = eventos_de(["-4", "-5", "6", "-6", "7", "-8", "9"], paso=0.5,
                         desvios_ms=[0, 0, -180, 0, 0, 0, 0])

    peor = frases.comparar(frase, intento).peor_desvio()
    assert peor[0].tab == "6"
    assert peor[2] < -100


def test_una_nota_muy_descolgada_no_arrastra_al_resto():
    """
    POR QUE EL AJUSTE ES ROBUSTO Y NO POR MINIMOS CUADRADOS.

    Comparando dos tomas reales de Bruno, en la segunda hizo una pausa larga
    antes de arrancar y esa nota quedó 900 ms corrida. Con mínimos cuadrados
    la recta se inclinaba para acomodarla, y todas las demás aparecían con un
    desvío que no tenían.

    Con la mediana de las pendientes, una nota descolgada no mueve la recta.
    """
    frase = frase_de(["-4", "-5", "6", "-6", "7", "-8", "9", "-9"], paso=0.5)
    intento = eventos_de(["-4", "-5", "6", "-6", "7", "-8", "9", "-9"], paso=0.5,
                         desvios_ms=[900, 0, 0, 0, 0, 0, 0, 0])

    comparacion = frases.comparar(frase, intento)
    desvios = comparacion.desvios_ms()

    # La primera nota sale muy corrida...
    assert abs(desvios[0]) > 500
    # ...y todas las demas quedan practicamente en cero.
    assert all(abs(d) < 60 for d in desvios[1:])


def test_la_velocidad_no_se_deja_llevar_a_un_valor_absurdo():
    """Si las dos interpretaciones no tienen nada que ver, no corregimos nada."""
    frase = frase_de(["-4", "-5"], paso=0.5)
    comparacion = frases.comparar(frase, eventos_de(["-4", "-5"], paso=0.5))
    assert 0.25 <= comparacion.velocidad <= 4.0


# =============================================================================
# Poner los milisegundos en contexto
# =============================================================================

def test_el_espaciado_tipico_es_el_de_la_frase():
    frase = frase_de(["-4", "-5", "6", "-6"], paso=0.5)
    comparacion = frases.comparar(frase, eventos_de(["-4", "-5", "6", "-6"]))
    assert comparacion.espaciado_tipico_ms() == pytest.approx(500.0, abs=5)


def test_la_dispersion_relativa_pone_los_milisegundos_en_escala():
    """
    CINCUENTA MILISEGUNDOS NO SIGNIFICAN LO MISMO SIEMPRE.

    Son muchísimo en una frase de corcheas rápidas y son nada en una de
    redondas. Por eso el informe divide la dispersión por el espacio que hay
    entre nota y nota.
    """
    rapida = frase_de(["-4", "-5", "6", "-6", "7"], paso=0.2)
    lenta = frase_de(["-4", "-5", "6", "-6", "7"], paso=2.0)

    desvios = [0, 100, -100, 100, -100]
    comp_rapida = frases.comparar(rapida, eventos_de(
        ["-4", "-5", "6", "-6", "7"], paso=0.2, desvios_ms=desvios))
    comp_lenta = frases.comparar(lenta, eventos_de(
        ["-4", "-5", "6", "-6", "7"], paso=2.0, desvios_ms=desvios))

    # La misma cantidad de milisegundos de error...
    assert comp_rapida.dispersion_ms() == pytest.approx(
        comp_lenta.dispersion_ms(), rel=0.3)
    # ...pero en la frase rapida es muchisimo mas grave.
    assert comp_rapida.dispersion_relativa() > comp_lenta.dispersion_relativa() * 5


def test_el_veredicto_en_palabras():
    frase = frase_de(["-4", "-5", "6", "-6", "7", "-8"], paso=0.5)

    igual = frases.comparar(frase, eventos_de(
        ["-4", "-5", "6", "-6", "7", "-8"], paso=0.5))
    distinta = frases.comparar(frase, eventos_de(
        ["-4", "-5", "6", "-6", "7", "-8"], paso=0.5,
        desvios_ms=[0, 350, -350, 350, -350, 350]))

    assert igual.calidad() == "muy parecida"
    assert distinta.calidad() in ("reconocible pero distinta", "distinta")


# =============================================================================
# El informe
# =============================================================================

def test_el_informe_tiene_las_secciones_principales():
    frase = frase_de(["-4", "-5", "6", "-6"])
    texto = frases.informe(frases.comparar(frase, eventos_de(["-4", "-5", "6"])))

    assert "FRASE:" in texto
    assert "Notas de la frase" in texto
    assert "Velocidad" in texto
    assert "NOTA POR NOTA" in texto


def test_el_informe_avisa_que_la_velocidad_no_es_un_error():
    frase = frase_de(["-4", "-5", "6", "-6", "7"], paso=0.5)
    texto = frases.informe(frases.comparar(
        frase, eventos_de(["-4", "-5", "6", "-6", "7"], paso=0.4)))

    assert "MAS RAPIDO" in texto
    assert "no es un error" in texto


def test_el_informe_marca_las_diferencias_de_afinacion():
    """
    Si el mismo bend te salió 40 cents más bajo que en la referencia, eso
    tiene que aparecer: es exactamente el problema que las grabaciones de
    Bruno mostraron en el bend del 3.
    """
    frase = frases.desde_eventos(
        [evento("-3''", 0.0, cents=0.0), evento("-4", 0.5), evento("-5", 1.0)],
        "con bend", "C",
    )
    intento = [evento("-3''", 0.0, cents=-40.0), evento("-4", 0.5),
               evento("-5", 1.0)]

    texto = frases.informe(frases.comparar(frase, intento))
    assert "40 cents mas bajo" in texto


def test_el_informe_sin_nada_reconocido_lo_dice():
    frase = frase_de(["-4", "-5"])
    texto = frases.informe(frases.comparar(frase, []))
    assert "No se reconocio" in texto


# =============================================================================
# Guardar y cargar
# =============================================================================

def test_guardar_y_volver_a_cargar_da_lo_mismo(tmp_path):
    frase = frase_de(["-4", "-5", "6", "-3''"], nombre="Lick de 3a")
    ruta = frases.guardar(frase, str(tmp_path))
    recuperada = frases.cargar(ruta)

    assert recuperada.nombre == "Lick de 3a"
    assert recuperada.tablatura() == frase.tablatura()
    assert recuperada.tonalidad == "C"
    assert recuperada.posicion == 12
    assert [n.inicio_seg for n in recuperada.notas] == \
           pytest.approx([n.inicio_seg for n in frase.notas])


def test_el_nombre_del_archivo_es_seguro(tmp_path):
    """Un nombre con espacios y acentos no puede romper el guardado."""
    frase = frase_de(["-4"], nombre="Lick de 3a / vuelta 2!")
    ruta = frases.guardar(frase, str(tmp_path))
    assert ruta.endswith(".json")
    assert frases.cargar(ruta).nombre == "Lick de 3a / vuelta 2!"


def test_listar_devuelve_las_frases_guardadas(tmp_path):
    frases.guardar(frase_de(["-4"], nombre="primera"), str(tmp_path))
    frases.guardar(frase_de(["-5"], nombre="segunda"), str(tmp_path))

    nombres = [nombre for nombre, _ in frases.listar(str(tmp_path))]
    assert set(nombres) == {"primera", "segunda"}


def test_listar_una_carpeta_que_no_existe_no_rompe():
    assert frases.listar("carpeta_que_no_existe_98765") == []


def test_buscar_una_frase_por_su_nombre(tmp_path):
    frases.guardar(frase_de(["-4", "-5"], nombre="Carlos vuelta A"), str(tmp_path))

    encontrada = frases.buscar("Carlos vuelta A", str(tmp_path))
    assert encontrada is not None
    assert encontrada.cantidad == 2


def test_buscar_una_frase_que_no_existe_devuelve_none(tmp_path):
    assert frases.buscar("no existe", str(tmp_path)) is None


# =============================================================================
# La devolución: qué hacer con lo que salió
# =============================================================================

def test_tocarla_igual_da_una_devolucion_sin_reproches():
    frase = frase_de(["-2", "-3''", "4", "-4", "-5", "6"])
    devolucion = frases.devolucion(frases.comparar(frase, eventos_de(
        ["-2", "-3''", "4", "-4", "-5", "6"])))

    assert devolucion["notas"] == {"aciertos": 6, "esperadas": 6, "porcentaje": 100}
    assert devolucion["afinacion"]["medida"] is True
    assert devolucion["afinacion"]["bends_fuera"] == []
    assert devolucion["tiempo"]["medido"] is True
    assert devolucion["tiempo"]["a_tiempo"] == 6
    assert len(devolucion["consejos"]) == 1
    assert "muy parecida" in devolucion["consejos"][0]


def test_un_bend_corto_se_dice_con_esas_palabras():
    """
    El -3'' tocado 35 cents ALTO es un bend que se quedó corto: no bajaste
    lo suficiente. Es el error más común de los bends, y la devolución lo
    tiene que llamar por su nombre y decir cuánto.
    """
    frase = frase_de(["-2", "-3''", "4", "-3''", "-4"])
    intento = eventos_de(["-2", "-3''", "4", "-3''", "-4"])
    for evento in intento:
        if evento.como_tab() == "-3''":
            evento.cents = 35.0

    devolucion = frases.devolucion(frases.comparar(frase, intento))

    assert devolucion["afinacion"]["bends_fuera"] == [
        {"tab": "-3''", "cents": 35, "veces": 2}]
    consejo = devolucion["consejos"][0]
    assert "-3''" in consejo and "35 cents" in consejo and "corto" in consejo


def test_un_bend_pasado_se_distingue_del_corto():
    frase = frase_de(["-2", "-3'", "4", "-4"])
    intento = eventos_de(["-2", "-3'", "4", "-4"])
    intento[1].cents = -30.0

    consejo = frases.devolucion(frases.comparar(frase, intento))["consejos"][0]
    assert "-3'" in consejo and "pas" in consejo


def test_una_nota_natural_desafinada_no_es_culpa_tuya():
    """Solo los bends cuentan: una nota natural desafinada es la lengüeta."""
    frase = frase_de(["-2", "4", "-4", "5"])
    intento = eventos_de(["-2", "4", "-4", "5"])
    intento[1].cents = 40.0

    devolucion = frases.devolucion(frases.comparar(frase, intento))
    assert devolucion["afinacion"]["bends_fuera"] == []


def test_con_pocas_notas_coincidentes_no_se_opina():
    """
    Dos notas de ocho no son una muestra. La devolución dice eso y qué
    faltó, y NO habla de ritmo ni de afinación.
    """
    frase = frase_de(["-2", "-3''", "4", "-4", "-5", "6", "-6", "6"])
    devolucion = frases.devolucion(frases.comparar(frase, eventos_de(["-2", "-3''"])))

    assert devolucion["afinacion"]["medida"] is False
    assert devolucion["tiempo"]["medido"] is False
    assert len(devolucion["consejos"]) == 1
    assert "muy pocas" in devolucion["consejos"][0]
    assert "Te faltaron" in devolucion["consejos"][0]


def test_el_bend_cambiado_de_profundidad_se_explica_como_bend_corto():
    """Tocar -3' donde iba -3'' no es "otra nota": es el mismo bend, corto."""
    frase = frase_de(["-2", "-3''", "4", "-4", "-5", "6"])
    intento = eventos_de(["-2", "-3'", "4", "-4", "5", "7"])   # 3 de 6 bien

    consejo = frases.devolucion(frases.comparar(frase, intento))["consejos"][0]
    assert consejo.startswith("Primero las notas")
    assert "Bends cortos: -3'' te salió -3'" in consejo


def test_el_ritmo_que_cambio_senala_la_nota_mas_corrida():
    frase = frase_de(["-4", "-5", "6", "-6", "7", "-8", "9"], paso=0.5)
    intento = eventos_de(["-4", "-5", "6", "-6", "7", "-8", "9"], paso=0.5,
                         desvios_ms=[0, 0, 0, 200, 0, 0, 0])

    devolucion = frases.devolucion(frases.comparar(frase, intento))

    assert devolucion["tiempo"]["peor"]["tab"] == "-6"
    assert any("-6" in c and "ms" in c for c in devolucion["consejos"])


def test_la_velocidad_va_ultima_y_avisa_que_no_es_un_error():
    frase = frase_de(["-2", "-3''", "4", "-4", "-5", "6"], paso=0.5)
    intento = eventos_de(["-2", "-3''", "4", "-4", "-5", "6"], paso=0.6)   # 20% mas lento

    devolucion = frases.devolucion(frases.comparar(frase, intento))

    assert devolucion["tiempo"]["velocidad_pct"] == 20
    ultimo = devolucion["consejos"][-1]
    assert "20% más lento" in ultimo and "No es un error" in ultimo


def test_nunca_mas_de_tres_consejos():
    """
    Todo mal a la vez: pocas notas bien, dos bends desafinados, ritmo
    distinto y mucho mas lento. Aun asi, tres consejos: mas no se leen.
    """
    frase = frase_de(["-2", "-3''", "-3'", "4", "-4", "-3''", "-3'", "5", "6", "-6"], paso=0.5)
    intento = eventos_de(["-2", "-3''", "-3'", "4", "-4", "-3''", "-3'", "5", "7", "-7"], paso=0.7,
                         desvios_ms=[0, 150, -150, 0, 200, -150, 150, 0, 0, 0])
    for evento in intento:
        if evento.como_tab() == "-3''":
            evento.cents = 40.0
        if evento.como_tab() == "-3'":
            evento.cents = -35.0

    devolucion = frases.devolucion(frases.comparar(frase, intento))
    assert 1 <= len(devolucion["consejos"]) <= 3
