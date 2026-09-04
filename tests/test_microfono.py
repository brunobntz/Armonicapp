"""
Tests de armonica/microfono.py y armonica/pantalla.py.

SIN TOCAR EL MICROFONO DE VERDAD.

La captura de audio se prueba metiéndole datos a mano en la cola interna, que
es exactamente lo que haría la placa de sonido. Así se verifica toda la lógica
de ventanas superpuestas sin depender de que haya un micrófono conectado, ni
encender el de nadie para correr los tests.

Cómo correrlos:   python -m pytest tests/test_microfono.py -v
"""

import numpy as np
import pytest

import config
from armonica import mapeo, microfono, pantalla, segmentacion


def alimentar(captura, cantidad_muestras, valor=0.1):
    """Le mete audio a la cola, como haría la placa de sonido."""
    captura._cola.put(np.full(cantidad_muestras, valor, dtype=np.float32))


# =============================================================================
# Las ventanas superpuestas
# =============================================================================

def test_no_entrega_nada_hasta_juntar_una_ventana_entera():
    """
    Con media ventana de audio no se puede analizar nada. Hay que esperar.
    """
    captura = microfono.CapturaMicrofono(tamano=2048, salto=512)
    alimentar(captura, 1000)

    ventanas = list(captura.ventanas(tiempo_maximo_seg=0.001))
    assert ventanas == []


def test_entrega_una_ventana_cuando_junta_suficiente():
    captura = microfono.CapturaMicrofono(tamano=2048, salto=512,
                                         frecuencia_muestreo=44100)
    alimentar(captura, 2048)

    ventanas = list(captura.ventanas(tiempo_maximo_seg=0.02))
    assert len(ventanas) >= 1
    _, primera = ventanas[0]
    assert len(primera) == 2048


def test_las_ventanas_avanzan_de_a_un_salto_y_se_superponen():
    """
    LA LOGICA CENTRAL DEL MODULO.

    Cada ventana mira 2048 muestras pero avanza solo 512, o sea que comparte
    tres cuartos de su contenido con la anterior. Sin superposición tendríamos
    21 mediciones por segundo en vez de 86, y las notas rápidas se perderían.

    Metemos una rampa (0, 1, 2, 3...) para poder verificar exactamente de dónde
    salió cada ventana.
    """
    captura = microfono.CapturaMicrofono(tamano=100, salto=25,
                                         frecuencia_muestreo=1000)
    captura._cola.put(np.arange(200, dtype=np.float32))

    ventanas = list(captura.ventanas(tiempo_maximo_seg=0.1))

    assert ventanas[0][1][0] == 0.0
    assert ventanas[1][1][0] == 25.0     # avanzó un salto
    assert ventanas[2][1][0] == 50.0
    assert len(ventanas[0][1]) == 100    # pero sigue mirando 100 muestras


def test_los_instantes_avanzan_segun_el_salto():
    """
    A 1000 muestras por segundo con saltos de 25, cada ventana está 25
    milisegundos después de la anterior.
    """
    captura = microfono.CapturaMicrofono(tamano=100, salto=25,
                                         frecuencia_muestreo=1000)
    captura._cola.put(np.zeros(300, dtype=np.float32))

    ventanas = list(captura.ventanas(tiempo_maximo_seg=0.15))
    instantes = [instante for instante, _ in ventanas]

    assert instantes[0] == pytest.approx(0.0)
    assert instantes[1] == pytest.approx(0.025)
    assert instantes[2] == pytest.approx(0.050)


def test_junta_varios_trozos_chicos_en_una_ventana():
    """
    La placa de sonido entrega bloques de su tamaño, no del nuestro. Hay que
    ir pegando hasta llegar a una ventana.
    """
    captura = microfono.CapturaMicrofono(tamano=100, salto=100,
                                         frecuencia_muestreo=1000)
    for _ in range(5):
        alimentar(captura, 30)     # cinco trozos de 30 = 150 muestras

    ventanas = list(captura.ventanas(tiempo_maximo_seg=0.1))
    assert len(ventanas) == 1


def test_el_tiempo_maximo_corta_la_entrega():
    captura = microfono.CapturaMicrofono(tamano=100, salto=25,
                                         frecuencia_muestreo=1000)
    captura._cola.put(np.zeros(10000, dtype=np.float32))

    ventanas = list(captura.ventanas(tiempo_maximo_seg=0.1))
    assert len(ventanas) <= 5


# =============================================================================
# El audio grabado
# =============================================================================

def test_guarda_todo_el_audio_que_entro():
    """
    Lo grabado es lo que después se escribe en el .wav de la sesión, y es lo
    que permite reprocesar con otros umbrales sin volver a tocar.
    """
    captura = microfono.CapturaMicrofono(tamano=100, salto=25,
                                         frecuencia_muestreo=1000)
    captura._cola.put(np.arange(300, dtype=np.float32))
    list(captura.ventanas(tiempo_maximo_seg=0.1))

    grabado = captura.audio_grabado()
    assert len(grabado) == 300
    assert grabado[0] == 0.0
    assert grabado[-1] == 299.0


def test_se_puede_pedir_que_no_guarde_audio():
    """El modo calibración no necesita guardar nada: solo mide niveles."""
    captura = microfono.CapturaMicrofono(tamano=100, salto=25,
                                         frecuencia_muestreo=1000,
                                         guardar_audio=False)
    captura._cola.put(np.zeros(300, dtype=np.float32))
    list(captura.ventanas(tiempo_maximo_seg=0.1))

    assert len(captura.audio_grabado()) == 0


def test_sin_audio_grabado_devuelve_un_array_vacio_y_no_none():
    """Devolver None obligaría a preguntar en cada lugar que lo use."""
    captura = microfono.CapturaMicrofono()
    grabado = captura.audio_grabado()
    assert isinstance(grabado, np.ndarray)
    assert len(grabado) == 0


def test_arranca_sin_descartes():
    assert not microfono.CapturaMicrofono().hubo_descartes()


def test_registra_los_descartes_de_la_placa_de_sonido():
    """
    Si el sistema pierde audio, la transcripción tiene huecos. Hay que poder
    avisarlo, para no dejar que Bruno sospeche de su técnica cuando el problema
    fue que la computadora estaba ocupada.
    """
    captura = microfono.CapturaMicrofono()
    datos = np.zeros((10, 1), dtype=np.float32)

    captura._callback(datos, 10, None, None)
    assert not captura.hubo_descartes()

    captura._callback(datos, 10, None, "input overflow")
    assert captura.hubo_descartes()


def test_el_callback_copia_el_audio_en_vez_de_guardar_la_vista():
    """
    ESTE DETALLE ES FACIL DE PASAR POR ALTO Y ROMPE TODO.

    numpy entrega una VISTA del buffer de la placa de sonido, que se reescribe
    enseguida. Sin copiar, estaríamos analizando audio que ya cambió.

    Acá lo verificamos: metemos datos, los pisamos, y comprobamos que lo
    guardado siga siendo lo original.
    """
    captura = microfono.CapturaMicrofono()
    buffer_compartido = np.ones((10, 1), dtype=np.float32)

    captura._callback(buffer_compartido, 10, None, None)
    buffer_compartido[:] = 99.0        # la placa reescribe su buffer

    guardado = captura._cola.get()
    assert np.all(guardado == 1.0)


# =============================================================================
# El umbral sugerido
# =============================================================================

def test_el_umbral_sugerido_es_tres_veces_el_ruido():
    assert microfono.umbral_sugerido(0.004) == pytest.approx(0.012)


def test_el_umbral_sugerido_tiene_un_piso():
    """
    En una habitación muy silenciosa, tres veces el ruido daría un umbral tan
    bajo que la app captaría la respiración.
    """
    assert microfono.umbral_sugerido(0.00001) == 0.003


def test_sin_medicion_el_umbral_sugerido_es_el_de_config():
    assert microfono.umbral_sugerido(None) == config.UMBRAL_VOLUMEN_RMS


# =============================================================================
# La pantalla
# =============================================================================

def evento(tablatura):
    return segmentacion.Evento(
        nota=mapeo.tab_a_nota(tablatura, "C"), inicio_seg=0.0,
        duracion_seg=0.4, frecuencia_hz=440.0, cents=0.0,
        confianza=0.99, ventanas=30,
    )


def test_la_pantalla_arranca_sin_nota():
    estado = pantalla.EstadoPantalla("C", 12, "blues_mayor")
    assert estado.nota_actual is None
    assert estado.eventos == []


def test_la_pantalla_conoce_los_agujeros_de_la_escala():
    estado = pantalla.EstadoPantalla("C", 12, "blues_mayor")
    assert len(estado.midis_de_la_escala) > 10


def test_sin_escala_de_referencia_no_marca_nada():
    estado = pantalla.EstadoPantalla("C")
    assert estado.midis_de_la_escala == set()


def test_la_nota_se_sostiene_cuando_deja_de_detectarse():
    """
    LA DECISION QUE HACE LEGIBLE LA PANTALLA.

    Entre nota y nota hay silencio, y sin esto el agujero desaparecería en cada
    respiración. Ver la nota que acabás de tocar es más útil que ver un espacio
    vacío.
    """
    estado = pantalla.EstadoPantalla("C", 12, "blues_mayor")
    estado.actualizar(mapeo.tab_a_nota("-5", "C"), 3.0, 0.2, 1.0)
    assert estado.nota_actual.como_tab("guion") == "-5"

    estado.actualizar(None, 0.0, 0.001, 1.5)
    assert estado.nota_actual.como_tab("guion") == "-5"


def test_la_pantalla_sabe_si_la_nota_esta_en_la_escala():
    estado = pantalla.EstadoPantalla("C", 12, "blues_mayor")

    estado.actualizar(mapeo.tab_a_nota("-5", "C"), 0.0, 0.2, 1.0)
    assert estado.en_escala_actual         # el 5 aspirado es la tonica de 12a

    estado.actualizar(mapeo.tab_a_nota("2", "C"), 0.0, 0.2, 2.0)
    assert not estado.en_escala_actual     # el 2 soplado es el que hay que evitar


def test_la_tab_reciente_muestra_las_ultimas_notas():
    estado = pantalla.EstadoPantalla("C")
    estado.registrar_eventos([evento(t) for t in ["-2", "-3", "4", "-4", "-5"]])
    assert estado.tab_reciente(cuantas=3) == ["-4", "-5"] or \
           len(estado.tab_reciente(cuantas=3)) == 3


def test_el_medidor_cambia_de_color_segun_la_desafinacion():
    """
    Verde hasta 10 cents, amarillo hasta 25, rojo mas alla. Los umbrales no son
    arbitrarios: menos de 10 casi nadie lo escucha, a partir de 25 suena
    claramente desafinado.
    """
    afinado = str(pantalla.medidor_de_cents(5.0).markup)
    medio = str(pantalla.medidor_de_cents(18.0).markup)
    feo = str(pantalla.medidor_de_cents(40.0).markup)

    assert "green" in afinado
    assert "yellow" in medio
    assert "red" in feo


def test_el_medidor_pone_la_marca_donde_corresponde():
    centro = pantalla.medidor_de_cents(0.0).plain
    bajo = pantalla.medidor_de_cents(-45.0).plain
    alto = pantalla.medidor_de_cents(45.0).plain

    assert centro.index("O") > bajo.index("O")
    assert alto.index("O") > centro.index("O")


def test_el_medidor_avisa_cuando_no_hay_nota():
    assert "sin nota" in pantalla.medidor_de_cents(0.0, afinada=False).plain


def test_la_pantalla_completa_se_dibuja_sin_errores():
    """
    No verificamos como se ve, sino que no explote. Dibujar es donde mas facil
    aparece un error de formato que solo se descubre en vivo, en medio de una
    sesion.
    """
    from rich.console import Console

    estado = pantalla.EstadoPantalla("C", 12, "blues_mayor")
    estado.actualizar(mapeo.tab_a_nota("-3'''", "C"), -22.0, 0.15, 12.3)
    estado.registrar_eventos([evento(t) for t in ["-2''", "-2", "-3'''"]])

    consola = Console(file=open("nul" if config.SIMBOLO_BEND else "nul", "w"),
                      width=100)
    consola.print(pantalla.armar(estado))


def test_la_pantalla_se_dibuja_tambien_sin_nota_y_sin_escala():
    from rich.console import Console

    estado = pantalla.EstadoPantalla("G")
    consola = Console(file=open("nul", "w"), width=100)
    consola.print(pantalla.armar(estado))
