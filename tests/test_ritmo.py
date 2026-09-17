"""
Tests de armonica/ritmo.py — medir si tocás a tiempo.

La estrategia es la misma que en los otros módulos: fabricamos notas en
instantes que elegimos nosotros, así sabemos la respuesta exacta. Si ponemos
una nota 50 ms antes del pulso, el análisis tiene que decir -50.

Cómo correrlos:   python -m pytest tests/test_ritmo.py -v
"""

import pytest

import config
from armonica import mapeo, ritmo, segmentacion


def nota_en(instante_seg, tablatura="-5", duracion=0.3):
    """Un evento en un instante exacto. La nota concreta no importa acá."""
    return segmentacion.Evento(
        nota=mapeo.tab_a_nota(tablatura, "C"),
        inicio_seg=instante_seg,
        duracion_seg=duracion,
        frecuencia_hz=698.46,
        cents=0.0,
        confianza=0.99,
        ventanas=25,
    )


def tocando(desvios_ms, bpm=60, subdivision=1, desde_pulso=0):
    """
    Arma una serie de notas, una por punto de grilla, con los desvíos pedidos.

    `tocando([0, -50, 0, 50])` significa: la primera nota justo en el pulso, la
    segunda 50 ms antes, la tercera justa, la cuarta 50 ms después.
    """
    paso = ritmo.paso_de_grilla(bpm, subdivision)
    return [
        nota_en((desde_pulso + numero) * paso + desvio_ms / 1000.0)
        for numero, desvio_ms in enumerate(desvios_ms)
    ]


# =============================================================================
# La grilla: pulsos y subdivisiones
# =============================================================================

def test_a_sesenta_bpm_cada_pulso_dura_un_segundo():
    """La cuenta más fácil de verificar: 60 pulsos por minuto = 1 por segundo."""
    assert ritmo.duracion_de_pulso(60) == pytest.approx(1.0)


def test_al_doble_de_velocidad_el_pulso_dura_la_mitad():
    assert ritmo.duracion_de_pulso(120) == pytest.approx(0.5)


def test_los_tempos_de_las_clases_de_bruno():
    """Los BPM que aparecen en sus clases, para tenerlos por escrito."""
    assert ritmo.duracion_de_pulso(55) == pytest.approx(1.0909, abs=0.001)
    assert ritmo.duracion_de_pulso(65) == pytest.approx(0.9231, abs=0.001)
    assert ritmo.duracion_de_pulso(110) == pytest.approx(0.5455, abs=0.001)


def test_la_subdivision_parte_el_pulso():
    """A 60 BPM: negras cada 1 s, corcheas cada 0.5 s, tresillos cada 0.333 s."""
    assert ritmo.paso_de_grilla(60, 1) == pytest.approx(1.0)
    assert ritmo.paso_de_grilla(60, 2) == pytest.approx(0.5)
    assert ritmo.paso_de_grilla(60, 3) == pytest.approx(1 / 3, abs=0.001)


def test_un_bpm_invalido_da_error():
    with pytest.raises(ValueError):
        ritmo.duracion_de_pulso(0)
    with pytest.raises(ValueError):
        ritmo.duracion_de_pulso(-30)


# =============================================================================
# El desvío de cada nota
# =============================================================================

def test_tocar_justo_en_el_pulso_da_cero():
    analisis = ritmo.analizar(tocando([0, 0, 0, 0]), bpm=60, subdivision=1,
                              offset_seg=0.0)
    for desvio in analisis.desvios:
        assert desvio.desvio_ms == pytest.approx(0.0, abs=0.5)


def test_adelantarse_da_desvio_negativo():
    """
    La convención: negativo = antes del pulso. Es la que usan los músicos
    cuando dicen "te estás adelantando", que es lo que el profe le marca a Bruno.
    """
    analisis = ritmo.analizar(tocando([-50, -50, -50, -50]), bpm=60,
                              subdivision=1, offset_seg=0.0)
    for desvio in analisis.desvios:
        assert desvio.desvio_ms == pytest.approx(-50.0, abs=0.5)
        assert desvio.se_adelanto


def test_atrasarse_da_desvio_positivo():
    analisis = ritmo.analizar(tocando([40, 40, 40]), bpm=60, subdivision=1,
                              offset_seg=0.0)
    for desvio in analisis.desvios:
        assert desvio.desvio_ms == pytest.approx(40.0, abs=0.5)
        assert not desvio.se_adelanto


def test_cada_nota_se_asigna_al_pulso_mas_cercano():
    """
    Una nota 400 ms después del pulso 1, a 60 BPM, sigue perteneciendo al
    pulso 1. Una 600 ms después ya pertenece al pulso 2, y aparece adelantada.
    """
    analisis = ritmo.analizar([nota_en(0.4), nota_en(1.6)], bpm=60,
                              subdivision=1, offset_seg=0.0)
    assert analisis.desvios[0].indice_pulso == 0
    assert analisis.desvios[0].desvio_ms == pytest.approx(400, abs=1)
    assert analisis.desvios[1].indice_pulso == 2
    assert analisis.desvios[1].desvio_ms == pytest.approx(-400, abs=1)


# =============================================================================
# LAS ESTADISTICAS: sesgo contra dispersión
# =============================================================================

def test_el_sesgo_detecta_que_te_adelantas_siempre():
    analisis = ritmo.analizar(tocando([-60, -55, -65, -58]), bpm=60,
                              subdivision=1, offset_seg=0.0)
    assert analisis.sesgo_ms() == pytest.approx(-59.5, abs=1.0)


def test_la_dispersion_es_baja_cuando_el_desvio_es_constante():
    """
    Adelantarse SIEMPRE 60 ms es un problema, pero es un problema fácil: el
    tiempo es sólido y solo está corrido. Se arregla avisando.
    """
    analisis = ritmo.analizar(tocando([-60, -60, -60, -60]), bpm=60,
                              subdivision=1, offset_seg=0.0)
    assert analisis.dispersion_ms() < 2.0


def test_la_dispersion_delata_lo_que_el_promedio_esconde():
    """
    ESTE ES EL TEST QUE EXPLICA POR QUE MEDIMOS DISPERSION.

    Estas notas caen 80 ms antes y 80 ms después, alternadas. El promedio da
    CERO, como si tocaras perfecto. La dispersión da 80, que es la verdad.

    No es un caso inventado: el registro de Bruno tiene al profe diciendo en
    marzo que se adelanta y en mayo que llega tarde. Las dos cosas son ciertas
    porque el desvío es inestable, y un promedio no lo muestra.
    """
    analisis = ritmo.analizar(tocando([-80, 80, -80, 80]), bpm=60,
                              subdivision=1, offset_seg=0.0)

    assert analisis.sesgo_ms() == pytest.approx(0.0, abs=1.0)
    assert analisis.dispersion_ms() == pytest.approx(80.0, abs=2.0)


def test_el_porcentaje_a_tiempo_cuenta_las_que_entraron():
    """Con tolerancia de 40 ms: dos de cuatro adentro."""
    analisis = ritmo.analizar(tocando([0, 20, 60, 90]), bpm=60, subdivision=1,
                              offset_seg=0.0)
    assert analisis.porcentaje_a_tiempo(40.0) == pytest.approx(50.0)


def test_la_mediana_ignora_una_nota_muy_fuera_de_lugar():
    analisis = ritmo.analizar(tocando([-20, -22, -18, 300]), bpm=120,
                              subdivision=1, offset_seg=0.0)
    assert analisis.mediana_ms() == pytest.approx(-20.0, abs=3.0)


def test_el_peor_desvio_se_identifica():
    analisis = ritmo.analizar(tocando([0, -10, 70, 5]), bpm=60, subdivision=1,
                              offset_seg=0.0)
    assert analisis.peor_desvio().desvio_ms == pytest.approx(70.0, abs=1.0)


def test_sin_notas_no_rompe_nada():
    analisis = ritmo.analizar([], bpm=60)
    assert analisis.desvios == []
    assert analisis.sesgo_ms() == 0.0
    assert analisis.dispersion_ms() == 0.0
    assert analisis.porcentaje_a_tiempo() == 0.0
    assert analisis.peor_desvio() is None


# =============================================================================
# Compases y tiempos
# =============================================================================

def test_las_notas_se_ubican_en_su_compas():
    """A 60 BPM en 4/4, los primeros cuatro segundos son el compás 1."""
    eventos = [nota_en(t) for t in [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]]
    analisis = ritmo.analizar(eventos, bpm=60, compas=4, subdivision=1,
                              offset_seg=0.0)
    assert [d.compas for d in analisis.desvios] == [1, 1, 1, 1, 2, 2]


def test_se_identifica_el_tiempo_dentro_del_compas():
    eventos = [nota_en(t) for t in [0.0, 1.0, 2.0, 3.0, 4.0]]
    analisis = ritmo.analizar(eventos, bpm=60, compas=4, subdivision=1,
                              offset_seg=0.0)
    assert [d.tiempo_del_compas for d in analisis.desvios] == [1, 2, 3, 4, 1]


def test_los_tiempos_del_compas_funcionan_con_subdivision():
    """
    Con corcheas hay ocho puntos por compás, pero los tiempos siguen siendo
    cuatro: las corcheas al medio pertenecen al mismo tiempo que la negra.
    """
    paso = ritmo.paso_de_grilla(60, 2)     # 0.5 s
    eventos = [nota_en(numero * paso) for numero in range(8)]
    analisis = ritmo.analizar(eventos, bpm=60, compas=4, subdivision=2,
                              offset_seg=0.0)
    assert [d.tiempo_del_compas for d in analisis.desvios] == [1, 1, 2, 2, 3, 3, 4, 4]


def test_se_marcan_los_compases_de_cambio_de_acorde():
    """
    En el blues de doce compases el acorde cambia en el 2, 3, 5, 7, 9, 10, 11
    y 12. Poder separarlos importa porque es justo donde el profe dice que Bruno
    reacciona tarde.
    """
    eventos = [nota_en(numero * 4.0) for numero in range(12)]
    analisis = ritmo.analizar(eventos, bpm=60, compas=4, subdivision=1,
                              offset_seg=0.0)
    compases_marcados = [d.compas for d in analisis.desvios if d.es_cambio]
    assert compases_marcados == [2, 3, 5, 7, 9, 10, 11, 12]


def test_los_compases_de_cambio_se_pueden_cambiar():
    eventos = [nota_en(numero * 4.0) for numero in range(6)]
    analisis = ritmo.analizar(eventos, bpm=60, compas=4, subdivision=1,
                              offset_seg=0.0, compases_de_cambio=[1, 4])
    assert [d.compas for d in analisis.desvios if d.es_cambio] == [1, 4]


def test_se_pueden_separar_los_cambios_del_resto():
    eventos = [nota_en(numero * 4.0) for numero in range(12)]
    analisis = ritmo.analizar(eventos, bpm=60, compas=4, subdivision=1,
                              offset_seg=0.0)
    assert len(analisis.en_los_cambios()) == 8
    assert len(analisis.fuera_de_los_cambios()) == 4


def test_se_agrupan_los_desvios_por_tiempo_del_compas():
    """
    Sirve para ver si el problema se concentra en algún lugar del compás.
    Adelantarse solo en el tiempo 1 es distinto de adelantarse siempre.
    """
    eventos = [nota_en(t) for t in [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]]
    analisis = ritmo.analizar(eventos, bpm=60, compas=4, subdivision=1,
                              offset_seg=0.0)
    grupos = analisis.por_tiempo_del_compas()
    assert len(grupos[1]) == 2       # dos notas en el tiempo 1
    assert len(grupos[3]) == 1


# =============================================================================
# Estimar dónde arranca la grilla
# =============================================================================

def test_encuentra_el_offset_cuando_la_grabacion_no_arranca_en_el_pulso():
    """
    EL PROBLEMA QUE RESUELVE ESTA FUNCION.

    Nadie empieza a grabar exactamente en el primer pulso de la base. Si no
    ajustamos dónde cae la grilla, TODAS las notas salen corridas por igual y
    el análisis no vale nada.
    """
    # Notas perfectas, pero la grabación arranca 0.3 s antes del primer pulso.
    eventos = [nota_en(0.3 + numero * 1.0) for numero in range(8)]
    offset = ritmo.estimar_offset(eventos, bpm=60, subdivision=1)
    assert offset == pytest.approx(0.3, abs=0.02)


def test_con_el_offset_estimado_las_notas_quedan_a_tiempo():
    eventos = [nota_en(0.37 + numero * 1.0) for numero in range(8)]
    analisis = ritmo.analizar(eventos, bpm=60, subdivision=1)
    assert abs(analisis.sesgo_ms()) < 20
    assert analisis.dispersion_ms() < 10


def test_el_offset_no_se_deja_arrastrar_por_una_nota_perdida():
    """
    Usa la mediana justamente para esto: una nota muy fuera de lugar no puede
    mover la grilla entera.
    """
    eventos = [nota_en(numero * 1.0) for numero in range(8)]
    eventos.append(nota_en(8.4))          # una nota bien corrida
    offset = ritmo.estimar_offset(eventos, bpm=60, subdivision=1)
    assert offset == pytest.approx(0.0, abs=0.05) or offset > 0.95


def test_sin_eventos_el_offset_es_cero():
    assert ritmo.estimar_offset([], bpm=60) == 0.0


# =============================================================================
# Estimar la velocidad
# =============================================================================

def test_estima_el_bpm_de_una_serie_pareja():
    """
    Notas cada 0.923 segundos son 65 BPM, que es el tempo al que Bruno trabajó
    la frase de Carlos del Junco.
    """
    eventos = [nota_en(numero * (60.0 / 65.0)) for numero in range(16)]
    bpm, _ = ritmo.estimar_bpm(eventos, subdivision=1)
    assert bpm == pytest.approx(65.0, abs=2.0)


def test_no_estima_el_bpm_con_muy_pocas_notas():
    bpm, error = ritmo.estimar_bpm([nota_en(0.0), nota_en(1.0)])
    assert bpm is None
    assert error is None


# =============================================================================
# El diagnóstico en palabras
# =============================================================================

def test_el_diagnostico_felicita_un_tiempo_solido():
    analisis = ritmo.analizar(tocando([0, 5, -5, 3, -2, 4]), bpm=60,
                              subdivision=1, offset_seg=0.0)
    texto = " ".join(ritmo.diagnostico(analisis)).lower()
    assert "solido" in texto


def test_el_diagnostico_avisa_cuando_te_adelantas():
    analisis = ritmo.analizar(tocando([-60, -58, -62, -59]), bpm=60,
                              subdivision=1, offset_seg=0.0)
    texto = " ".join(ritmo.diagnostico(analisis)).lower()
    assert "adelantas" in texto


def test_el_diagnostico_avisa_cuando_llegas_tarde():
    analisis = ritmo.analizar(tocando([55, 58, 52, 60]), bpm=60,
                              subdivision=1, offset_seg=0.0)
    texto = " ".join(ritmo.diagnostico(analisis)).lower()
    assert "tarde" in texto


def test_el_diagnostico_senala_la_inestabilidad_aunque_el_promedio_de_cero():
    """
    El caso importante: promedio cero, dispersión enorme. El diagnóstico no
    puede decir que está todo bien.
    """
    analisis = ritmo.analizar(tocando([-90, 90, -85, 88, -92, 91]), bpm=60,
                              subdivision=1, offset_seg=0.0)
    texto = " ".join(ritmo.diagnostico(analisis)).lower()
    assert "inestable" in texto
    assert "solido" not in texto


def test_el_diagnostico_compara_los_cambios_de_acorde_con_el_resto():
    """
    Notas parejas salvo en los compases de cambio, donde se adelanta mucho.
    El diagnóstico tiene que señalarlo, porque es el patrón exacto que
    el profe le marca desde marzo.
    """
    paso = 4.0    # un compás a 60 BPM en 4/4
    eventos = []
    for numero_compas in range(1, 13):
        desvio = -0.09 if numero_compas in ritmo.COMPASES_DE_CAMBIO_BLUES else 0.0
        eventos.append(nota_en((numero_compas - 1) * paso + desvio))

    analisis = ritmo.analizar(eventos, bpm=60, compas=4, subdivision=1,
                              offset_seg=0.0)
    texto = " ".join(ritmo.diagnostico(analisis)).lower()
    assert "cambio de acorde" in texto
    assert "adelantas mas" in texto


def test_el_diagnostico_sin_notas_no_rompe():
    texto = ritmo.diagnostico(ritmo.analizar([], bpm=60))
    assert len(texto) == 1


# =============================================================================
# El dibujo
# =============================================================================

def test_la_linea_de_tiempo_tiene_una_fila_por_nota():
    analisis = ritmo.analizar(tocando([0, -50, 50]), bpm=60, subdivision=1,
                              offset_seg=0.0)
    filas = [l for l in ritmo.linea_de_tiempo(analisis).splitlines() if "[" in l]
    assert len(filas) == 3


def test_la_linea_de_tiempo_marca_con_equis_las_notas_fuera_de_tiempo():
    analisis = ritmo.analizar(tocando([0, 200]), bpm=60, subdivision=1,
                              offset_seg=0.0)
    filas = [l for l in ritmo.linea_de_tiempo(analisis).splitlines() if "[" in l]
    assert "o" in filas[0]
    assert "X" in filas[1]


def test_la_linea_de_tiempo_sin_notas_no_rompe():
    assert "Sin notas" in ritmo.linea_de_tiempo(ritmo.analizar([], bpm=60))


# =============================================================================
# La precisión alcanza para lo que queremos medir
# =============================================================================

def test_la_resolucion_es_mucho_mejor_que_el_fenomeno_que_medimos():
    """
    El error propio de la app al ubicar el comienzo de una nota es de unos
    6 ms (ver config.CORRECCION_INICIO_SEG). Los desvíos que importan
    musicalmente arrancan en 30 ms.

    Este test verifica que un desvío de 30 ms se distinga con claridad de uno
    de cero, que es lo mínimo que hay que poder hacer.
    """
    justo = ritmo.analizar(tocando([0, 0, 0, 0]), bpm=60, subdivision=1,
                           offset_seg=0.0)
    corrido = ritmo.analizar(tocando([-30, -30, -30, -30]), bpm=60,
                             subdivision=1, offset_seg=0.0)

    assert abs(corrido.sesgo_ms() - justo.sesgo_ms()) == pytest.approx(30, abs=2)


def test_la_tolerancia_por_defecto_es_razonable():
    """
    40 ms es exigente pero alcanzable. Menos de 20 casi nadie lo escucha; más
    de 50 ya suena claramente corrido.
    """
    assert 20 <= config.TOLERANCIA_RITMO_MS <= 60


# =============================================================================
# El ajuste contra el azar: saber cuando NO sabemos
# =============================================================================

def test_notas_perfectas_dan_un_ajuste_muy_bajo():
    """Si tocaste justo sobre la grilla, el ajuste tiene que ser casi cero."""
    analisis = ritmo.analizar(tocando([0, 2, -1, 3, -2, 1]), bpm=60,
                              subdivision=1, offset_seg=0.0)
    assert analisis.ajuste_vs_azar() < 0.05
    assert analisis.la_grilla_explica_algo()


def test_notas_al_azar_dan_un_ajuste_cercano_a_uno():
    """
    ESTE TEST PROTEGE CONTRA EL PEOR ERROR POSIBLE DE LA APP: informar un
    diagnostico de ritmo sobre una medicion que no significa nada.

    Repartimos las notas de forma pareja dentro del espacio entre pulsos, que
    es lo que pasaria si no estuvieran siguiendo ninguna grilla. El ajuste
    tiene que delatarlo.
    """
    import random

    generador = random.Random(7)
    paso_ms = ritmo.paso_de_grilla(60, 1) * 1000
    desvios = [generador.uniform(-paso_ms / 2, paso_ms / 2) for _ in range(60)]

    analisis = ritmo.analizar(tocando(desvios), bpm=60, subdivision=1,
                              offset_seg=0.0)
    assert analisis.ajuste_vs_azar() > 0.75
    assert not analisis.la_grilla_explica_algo()


def test_con_pocas_notas_no_se_arriesga_una_conclusion():
    analisis = ritmo.analizar(tocando([0, 10]), bpm=60, subdivision=1,
                              offset_seg=0.0)
    assert analisis.ajuste_vs_azar() is None
    assert not analisis.la_grilla_explica_algo()


def test_el_ajuste_no_premia_a_las_grillas_mas_densas():
    """
    La trampa que este numero resuelve. Las mismas notas al azar, medidas
    contra grillas cada vez mas densas, dan dispersiones cada vez menores.
    Sin normalizar, pareceria que tocaste mejor solo por cambiar la unidad.
    """
    import random

    generador = random.Random(11)
    eventos = [nota_en(generador.uniform(0, 30)) for _ in range(80)]

    dispersiones = []
    ajustes = []
    for subdivision in (1, 2, 4):
        analisis = ritmo.analizar(eventos, bpm=60, subdivision=subdivision)
        dispersiones.append(analisis.dispersion_ms())
        ajustes.append(analisis.ajuste_vs_azar())

    # La dispersion cruda baja con cada subdivision, y eso enganaria.
    assert dispersiones[0] > dispersiones[1] > dispersiones[2]
    # El ajuste, en cambio, se mantiene alto en las tres.
    assert all(a > 0.7 for a in ajustes)


# =============================================================================
# Sobre una base que no es el blues de doce
# =============================================================================

def test_la_vuelta_puede_no_ser_de_doce_compases():
    """
    Una base de Band-in-a-Box repite su coro, que puede durar cualquier
    cantidad de compases. Con una vuelta de 4 y cambio en el compás 3, el
    compás 7 (el 3 de la segunda vuelta) también es un cambio.
    """
    eventos = [nota_en(compas * 4.0) for compas in range(8)]  # 60 BPM, 4/4: un compás = 4 s
    analisis = ritmo.analizar(eventos, 60, compas=4, subdivision=1, offset_seg=0.0,
                              compases_de_cambio=[3], compases_por_vuelta=4)
    cambios = [d.compas for d in analisis.desvios if d.es_cambio]
    assert cambios == [3, 7]


def test_ajustar_offset_corrige_la_latencia_sin_cambiar_de_compas():
    """
    La app midió que el compás 1 cayó en 1.000 s, pero el micrófono agrega
    40 ms: las notas caen en 1.04, 2.04, 3.04... La fase la ponen las notas;
    el compás, la medición. Y si la medición dijera 5.0 en vez de 1.0, el
    resultado sigue cerca de 5.0: nunca se aleja más de medio paso.
    """
    eventos = [nota_en(1.04 + pulso) for pulso in range(8)]
    assert ritmo.ajustar_offset(1.0, eventos, 60) == pytest.approx(1.04, abs=0.006)
    assert ritmo.ajustar_offset(5.0, eventos, 60) == pytest.approx(5.04, abs=0.006)
    assert ritmo.ajustar_offset(1.0, [], 60) == 1.0
