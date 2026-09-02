"""
Tests de armonica/segmentacion.py — de ventanas sueltas a notas tocadas.

Hay dos clases de test acá:

  - Los que arman las mediciones A MANO, con listas escritas en el test. Sirven
    para probar la lógica de agrupamiento en casos exactos y controlados.
  - Los de punta a punta, que generan audio real, lo pasan por el detector y
    verifican la transcripción completa.

Cómo correrlos:   python -m pytest tests/test_segmentacion.py -v
"""

import pytest

import config
from armonica import mapeo, notas, segmentacion
from herramientas import generar_wav


FS = 44100
SALTO_SEG = config.SALTO_VENTANA / FS
TABLA_C = mapeo.construir_tabla_inversa("C")


def mediciones_de(secuencia, confianza=0.98):
    """
    Arma una lista de mediciones a partir de nombres de nota.

    Cada elemento de `secuencia` es un nombre de nota ("C5") o None para una
    ventana de silencio. Cada uno representa UNA ventana.

    Escribir los tests así los hace legibles: se ve de un vistazo qué "tocó"
    el músico imaginario, ventana por ventana.
    """
    lista = []
    for indice, nombre in enumerate(secuencia):
        if nombre is None:
            frecuencia = None
        else:
            frecuencia = notas.midi_a_frecuencia(notas.nombre_a_midi(nombre))
        lista.append({
            "tiempo_seg": indice * SALTO_SEG,
            "frecuencia": frecuencia,
            "confianza": confianza if frecuencia else 0.0,
            "volumen": 0.2 if frecuencia else 0.001,
        })
    return lista


def segmentar(secuencia, **extra):
    """Atajo: de una secuencia de nombres de nota a eventos."""
    extra.setdefault("correccion_inicio", 0.0)   # sin corrección, para tests exactos
    return segmentacion.segmentar(mediciones_de(secuencia), TABLA_C, **extra)


# =============================================================================
# Lo esencial: agrupar ventanas iguales
# =============================================================================

def test_muchas_ventanas_iguales_dan_una_sola_nota():
    """
    El trabajo central del módulo. Veinte ventanas diciendo lo mismo son una
    nota, no veinte.
    """
    eventos = segmentar(["C5"] * 20)
    assert len(eventos) == 1
    assert eventos[0].como_tab("guion") == "4"
    assert eventos[0].ventanas == 20


def test_dos_notas_distintas_dan_dos_eventos():
    eventos = segmentar(["C5"] * 20 + ["D5"] * 20)
    assert len(eventos) == 2
    assert [e.como_tab("guion") for e in eventos] == ["4", "-4"]


def test_el_silencio_separa_dos_veces_la_misma_nota():
    """
    Tocar el 4 soplado, callar, y volver a tocarlo son DOS notas. Si no
    cortáramos en el silencio, saldría una sola nota larguísima.
    """
    eventos = segmentar(["C5"] * 15 + [None] * 15 + ["C5"] * 15)
    assert len(eventos) == 2
    assert all(e.como_tab("guion") == "4" for e in eventos)


def test_los_tiempos_y_las_duraciones_son_correctos():
    eventos = segmentar(["C5"] * 10 + [None] * 10 + ["D5"] * 10)

    assert eventos[0].inicio_seg == pytest.approx(0.0)
    assert eventos[0].duracion_seg == pytest.approx(10 * SALTO_SEG, abs=0.001)

    # La segunda nota arranca en la ventana 20.
    assert eventos[1].inicio_seg == pytest.approx(20 * SALTO_SEG, abs=0.001)


def test_fin_seg_es_inicio_mas_duracion():
    evento = segmentar(["C5"] * 10)[0]
    assert evento.fin_seg == pytest.approx(evento.inicio_seg + evento.duracion_seg)


def test_sin_mediciones_no_hay_eventos():
    assert segmentacion.segmentar([], TABLA_C) == []


def test_puro_silencio_no_da_ninguna_nota():
    assert segmentar([None] * 50) == []


# =============================================================================
# Filtro 1: los huecos tolerados
# =============================================================================

def test_una_ventana_dudosa_no_parte_la_nota_en_dos():
    """
    ESTE ES EL FILTRO QUE MÁS SE NOTA EN LA PRÁCTICA.

    Tocás una nota larga y en el medio hay una ventana donde el detector dudó:
    un golpe de aire, un instante de transición. Sin tolerancia, esa nota
    aparecería partida en dos, y el resumen contaría el doble de notas de las
    que tocaste.
    """
    eventos = segmentar(["C5"] * 10 + [None] + ["C5"] * 10)
    assert len(eventos) == 1
    # Las 20 ventanas buenas cuentan; la dudosa del medio no aporta valores.
    assert eventos[0].ventanas == 20


def test_tolera_hasta_el_limite_configurado():
    """Tres huecos seguidos se toleran; cuatro ya cortan la nota."""
    eventos = segmentar(["C5"] * 10 + [None] * 3 + ["C5"] * 10, huecos_tolerados=3)
    assert len(eventos) == 1

    eventos = segmentar(["C5"] * 10 + [None] * 4 + ["C5"] * 10, huecos_tolerados=3)
    assert len(eventos) == 2


def test_una_nota_intrusa_breve_no_corta_la_nota():
    """
    Al hacer un bend, la armónica pasa por frecuencias intermedias. El detector
    puede reportar por una ventana la nota de al lado. Con tolerancia, esa
    ventana intrusa se absorbe y la nota sigue siendo una sola.
    """
    eventos = segmentar(["D5"] * 10 + ["C5"] + ["D5"] * 10, huecos_tolerados=3)
    assert len(eventos) == 1
    assert eventos[0].como_tab("guion") == "-4"


def test_si_la_nota_nueva_persiste_si_se_corta():
    """
    La contracara: si la otra nota se queda, es porque de verdad cambiaste de
    agujero, y hay que abrir un evento nuevo.
    """
    eventos = segmentar(["D5"] * 10 + ["C5"] * 10, huecos_tolerados=3)
    assert len(eventos) == 2
    assert [e.como_tab("guion") for e in eventos] == ["-4", "4"]


def test_la_ventana_del_hueco_puede_arrancar_la_nota_siguiente():
    """
    Después de cerrar una nota volvemos a mirar desde la última ventana que
    coincidió, no desde el final del hueco. Si no, perderíamos el comienzo de
    la nota siguiente.
    """
    eventos = segmentar(["C5"] * 10 + ["D5"] * 20, huecos_tolerados=3)
    assert len(eventos) == 2
    # La segunda nota tiene que conservar sus 20 ventanas, no 16.
    assert eventos[1].ventanas == 20


# =============================================================================
# Filtro 2: la duración mínima
# =============================================================================

def test_las_notas_demasiado_cortas_se_descartan():
    """
    Dos ventanas son 23 milisegundos. Con el umbral por defecto de 60 ms eso se
    descarta: es una nota fantasma de transición, no algo que quisiste tocar.
    """
    eventos = segmentar(["C5"] * 2 + [None] * 10 + ["D5"] * 20)
    assert len(eventos) == 1
    assert eventos[0].como_tab("guion") == "-4"


def test_el_umbral_de_duracion_se_puede_bajar_para_frases_rapidas():
    eventos = segmentar(["C5"] * 2 + [None] * 10 + ["D5"] * 20,
                        duracion_minima=0.01)
    assert len(eventos) == 2


def test_subir_el_umbral_descarta_mas_notas():
    eventos = segmentar(["C5"] * 10 + [None] * 5 + ["D5"] * 40,
                        duracion_minima=0.3)
    assert len(eventos) == 1
    assert eventos[0].como_tab("guion") == "-4"


# =============================================================================
# Los datos de cada evento
# =============================================================================

def test_la_frecuencia_del_evento_es_la_mediana_de_sus_ventanas():
    """
    Usamos mediana y no promedio para que una sola medición disparatada no
    arruine el dato. Acá metemos una ventana con un valor absurdo y verificamos
    que la frecuencia del evento no se mueva.
    """
    lista = mediciones_de(["A4"] * 21)
    lista[10]["frecuencia"] = 441.5      # una medición apenas desviada
    eventos = segmentacion.segmentar(lista, TABLA_C, correccion_inicio=0.0)

    assert len(eventos) == 1
    assert eventos[0].frecuencia_hz == pytest.approx(440.0, abs=0.1)


def test_los_cents_reflejan_la_desafinacion():
    """
    Si tocás un bend 30 cents bajo, el evento tiene que decirlo. Es lo que
    alimenta el reporte de afinación y, en el paso 7, el medidor en vivo.
    """
    frecuencia_baja = notas.midi_a_frecuencia(70 - 0.30)    # 30 cents bajo el Sib
    lista = mediciones_de(["Bb4"] * 20)
    for medicion in lista:
        medicion["frecuencia"] = frecuencia_baja

    eventos = segmentacion.segmentar(lista, TABLA_C, correccion_inicio=0.0)
    assert eventos[0].como_tab("guion") == "-3'"
    assert eventos[0].cents == pytest.approx(-30.0, abs=1.0)


def test_esta_afinada_distingue_una_nota_buena_de_una_desviada():
    afinado = segmentacion.Evento(None, 0, 0.5, 440, 5.0, 1.0, 20)
    desviado = segmentacion.Evento(None, 0, 0.5, 440, -35.0, 1.0, 20)
    assert afinado.esta_afinada()
    assert not desviado.esta_afinada()


def test_la_confianza_del_evento_es_el_promedio_de_sus_ventanas():
    lista = mediciones_de(["C5"] * 20, confianza=0.85)
    eventos = segmentacion.segmentar(lista, TABLA_C, correccion_inicio=0.0)
    assert eventos[0].confianza == pytest.approx(0.85)


def test_una_nota_que_la_armonica_no_da_no_genera_evento():
    """
    Mib5 solo sale con overblow, que no está en V1. El mapeo devuelve None y la
    segmentación no abre ningún evento: preferimos no transcribir antes que
    transcribir mal.
    """
    assert segmentar(["Eb5"] * 20) == []


# =============================================================================
# marcar_escala
# =============================================================================

def test_marcar_escala_completa_el_campo():
    eventos = segmentar(["F5"] * 20 + [None] * 5 + ["E4"] * 20)
    segmentacion.marcar_escala(eventos, "C", 12, "blues_mayor")

    # El 5 aspirado (Fa) es la tónica de la 12a: está en la escala.
    assert eventos[0].en_escala is True
    # El 2 soplado (Mi) es el que Leandro te dijo que evites: no está.
    assert eventos[1].en_escala is False


def test_sin_marcar_escala_el_campo_arranca_en_falso():
    eventos = segmentar(["F5"] * 20)
    assert eventos[0].en_escala is False


def test_la_misma_transcripcion_se_puede_marcar_contra_otra_escala():
    """
    Por eso marcar_escala está separado de segmentar: podés transcribir una vez
    y después comparar contra distintas escalas sin recalcular nada.
    """
    eventos = segmentar(["B4"] * 20)     # el 3 aspirado, Si

    segmentacion.marcar_escala(eventos, "C", 12, "blues")
    assert eventos[0].en_escala is True          # el Si es la 5a bemol de Fa

    segmentacion.marcar_escala(eventos, "C", 12, "blues_mayor")
    assert eventos[0].en_escala is False         # en la mayor no está


# =============================================================================
# Salida en texto
# =============================================================================

def test_la_tablatura_sale_con_flechas():
    eventos = segmentar(["C5"] * 20 + [None] * 5 + ["D5"] * 20)
    assert segmentacion.como_tablatura(eventos, notacion="flechas") == "↑4 ↓4"


def test_la_tablatura_puede_llevar_el_nombre_de_la_nota():
    eventos = segmentar(["C5"] * 20 + [None] * 5 + ["D5"] * 20)
    texto = segmentacion.como_tablatura(eventos, notacion="guion", con_notas=True)
    assert "4 C5" in texto
    assert "-4 D5" in texto


def test_la_tablatura_se_corta_en_varias_lineas():
    eventos = segmentar((["C5"] * 10 + [None] * 5) * 6)
    texto = segmentacion.como_tablatura(eventos, por_linea=2)
    assert len(texto.splitlines()) == 3


def test_la_tablatura_de_una_lista_vacia_es_vacia():
    assert segmentacion.como_tablatura([]) == ""


def test_el_resumen_corto_dice_cuantas_notas_y_cuanto_duro():
    eventos = segmentar(["C5"] * 20 + [None] * 5 + ["D5"] * 20)
    texto = segmentacion.resumen_corto(eventos)
    assert "2 notas" in texto


def test_el_resumen_corto_avisa_cuando_no_hay_nada():
    assert "No se detecto" in segmentacion.resumen_corto([])


# =============================================================================
# De punta a punta: audio real generado
# =============================================================================

def test_transcribe_la_corrida_de_doceava_con_audio_generado():
    """
    LA PRUEBA DE FUEGO DEL PASO.

    Genera el audio de la corrida que Bruno practica, lo pasa por toda la
    cadena y verifica que salgan las trece notas exactas.
    """
    from armonica import tono

    muestras, referencia = generar_wav.generar_secuencia(
        generar_wav.CORRIDA_12A, "C"
    )
    mediciones = tono.detectar_en_senal(muestras, FS)
    eventos = segmentacion.segmentar(mediciones, TABLA_C)

    assert len(eventos) == len(referencia)
    detectadas = [e.como_tab("guion") for e in eventos]
    assert detectadas == generar_wav.CORRIDA_12A


def test_los_inicios_caen_donde_deben():
    """
    Verifica la corrección de config.CORRECCION_INICIO_SEG.

    Sin ella, cada nota aparece unos 30 milisegundos antes de lo real, porque
    la ventana que la reconoce arrancó antes de que la nota sonara. Eso
    importa muchísimo para el análisis de ritmo: los desvíos que queremos medir
    rondan los 70 ms, y un sesgo de 30 sería casi la mitad de la señal.

    Salteamos la primera nota, que es un caso especial: arranca en el segundo
    cero de la grabación y no puede empezar antes.
    """
    from armonica import tono

    muestras, referencia = generar_wav.generar_secuencia(
        generar_wav.CORRIDA_12A, "C"
    )
    eventos = segmentacion.segmentar(
        tono.detectar_en_senal(muestras, FS), TABLA_C
    )

    for evento, esperado in list(zip(eventos, referencia))[1:]:
        error_ms = abs(evento.inicio_seg - esperado["inicio_seg"]) * 1000
        assert error_ms < 15.0, (
            f"{esperado['tablatura']} empieza {error_ms:.0f} ms fuera de lugar"
        )


def test_las_duraciones_se_parecen_a_las_reales():
    """Las notas generadas duran 500 ms. Toleramos 50 ms de error."""
    from armonica import tono

    muestras, _ = generar_wav.generar_secuencia(
        generar_wav.CORRIDA_12A, "C", duracion_nota=0.5
    )
    eventos = segmentacion.segmentar(
        tono.detectar_en_senal(muestras, FS), TABLA_C
    )

    for evento in eventos:
        assert abs(evento.duracion_seg - 0.5) < 0.05


def test_transcribe_los_doce_bends():
    """
    Los bends son las notas más difíciles, incluido el tercer bend del 3.
    Tienen que salir los doce, en orden.
    """
    from armonica import tono

    muestras, _ = generar_wav.generar_secuencia(generar_wav.SOLO_BENDS, "C")
    eventos = segmentacion.segmentar(
        tono.detectar_en_senal(muestras, FS), TABLA_C
    )
    assert [e.como_tab("guion") for e in eventos] == generar_wav.SOLO_BENDS


def test_el_ruido_de_fondo_no_genera_notas():
    """
    Medio segundo de ruido, tres notas, medio segundo de ruido.
    Tienen que salir exactamente tres eventos.
    """
    import numpy as np

    from armonica import tono

    notas_muestras, _ = generar_wav.generar_secuencia(["4", "-4", "5"], "C")
    con_ruido = np.concatenate([
        generar_wav.generar_ruido(0.5, FS),
        notas_muestras,
        generar_wav.generar_ruido(0.5, FS),
    ])

    eventos = segmentacion.segmentar(
        tono.detectar_en_senal(con_ruido, FS), TABLA_C
    )
    assert [e.como_tab("guion") for e in eventos] == ["4", "-4", "5"]


def test_funciona_igual_con_otra_armonica():
    """
    La misma corrida en una armónica en Sol da los mismos AGUJEROS, aunque las
    notas que suenan sean otras. Es la propiedad de las posiciones, verificada
    ahora con audio de verdad.
    """
    from armonica import tono

    muestras, _ = generar_wav.generar_secuencia(generar_wav.CORRIDA_12A, "G")
    eventos = segmentacion.segmentar(
        tono.detectar_en_senal(muestras, FS),
        mapeo.construir_tabla_inversa("G"),
    )
    assert [e.como_tab("guion") for e in eventos] == generar_wav.CORRIDA_12A


# =============================================================================
# La afinación de la armónica
# =============================================================================

def evento_con(tablatura, cents):
    """Un evento armado a mano, para probar los cálculos de afinación."""
    nota = mapeo.tab_a_nota(tablatura, "C")
    return segmentacion.Evento(nota, 0.0, 0.5, 440.0, cents, 0.99, 20)


def test_la_afinacion_se_estima_solo_con_las_notas_naturales():
    """
    Las notas sin bend las da la lengüeta y no dependen de cómo soples: son la
    referencia honesta de cómo está afinado el instrumento.

    Los bends no cuentan, porque ahí el desvío es tuyo y no del instrumento.
    """
    eventos = [
        evento_con("4", 20.0), evento_con("-4", 18.0),
        evento_con("-5", 22.0), evento_con("6", 20.0),
        evento_con("-3'", -40.0),      # un bend muy desafinado
        evento_con("-3''", -35.0),     # y otro
    ]
    afinacion, cuantas = segmentacion.estimar_afinacion_armonica(eventos)

    assert cuantas == 4                       # solo las cuatro naturales
    assert afinacion == pytest.approx(20.0, abs=1.0)


def test_sin_suficientes_notas_naturales_no_se_estima_nada():
    """Preferimos decir "no sé" antes que estimar con dos notas."""
    afinacion, cuantas = segmentacion.estimar_afinacion_armonica(
        [evento_con("4", 20.0), evento_con("-4", 18.0)]
    )
    assert afinacion is None
    assert cuantas == 2


def test_la_afinacion_usa_la_mediana_y_no_se_arruina_con_una_nota_mala():
    eventos = [evento_con(t, c) for t, c in
               [("4", 20.0), ("-4", 19.0), ("-5", 21.0), ("6", 20.0),
                ("7", -45.0)]]     # una nota tocada pésimo
    afinacion, _ = segmentacion.estimar_afinacion_armonica(eventos)
    assert afinacion == pytest.approx(20.0, abs=1.0)


def test_la_afinacion_equivalente_en_hz():
    """
    Los fabricantes hablan en Hz, no en cents. Una armónica +16 cents es una
    armónica afinada con La = 444 Hz, que es lo que entrega Hohner.
    """
    assert segmentacion.afinacion_equivalente_hz(0.0) == pytest.approx(440.0)
    assert segmentacion.afinacion_equivalente_hz(16.0) == pytest.approx(444.0, abs=0.5)
    assert segmentacion.afinacion_equivalente_hz(-100.0) == pytest.approx(415.3, abs=0.5)


def test_los_cents_relativos_descuentan_la_afinacion_del_instrumento():
    """
    EL CALCULO QUE SEPARA AL MUSICO DEL INSTRUMENTO.

    Si la armónica está +16 cents y tocaste un bend a -18, contra el estándar
    parece un error chico. Contra tu propia armónica son 34 cents de más: casi
    un tercio de semitono.
    """
    evento = evento_con("-3'", -18.0)
    assert segmentacion.cents_relativos(evento, 16.0) == pytest.approx(-34.0)


def test_sin_afinacion_estimada_los_cents_relativos_son_los_absolutos():
    evento = evento_con("-3'", -18.0)
    assert segmentacion.cents_relativos(evento, None) == pytest.approx(-18.0)
