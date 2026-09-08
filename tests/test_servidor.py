"""
Tests de armonica/servidor.py — la interfaz web.

SIN ABRIR EL MICROFONO. Se levanta un servidor de verdad en un puerto libre,
se le hacen pedidos HTTP reales, y se verifica lo que contesta. El hilo de
audio no se arranca nunca: eso se prueba aparte, en test_microfono.py.

Cómo correrlos:   python -m pytest tests/test_servidor.py -v
"""

import json
import os
import tempfile
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import config
from armonica import (audio, exportacion, frases, mapeo, segmentacion,
                      servidor)
from herramientas import generar_wav


# =============================================================================
# El servidor de prueba
# =============================================================================

@pytest.fixture
def servidor_andando():
    """
    Levanta el servidor en un puerto que elige el sistema, y lo apaga al final.

    El puerto 0 significa "el que esté libre": así dos tests en paralelo no
    chocan, y tampoco molestamos si tenés la app abierta en el 8000.
    """
    servidor.Manejador.estado = servidor.EstadoCompartido("C", 12, "blues_mayor")
    servidor.Manejador.hilo_audio = None
    servidor.Manejador.detener = None

    instancia = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Manejador)
    puerto = instancia.server_address[1]

    hilo = threading.Thread(target=instancia.serve_forever, daemon=True)
    hilo.start()

    yield f"http://127.0.0.1:{puerto}"

    instancia.shutdown()
    instancia.server_close()


def traer(base, ruta):
    with urllib.request.urlopen(base + ruta, timeout=5) as respuesta:
        return respuesta.status, respuesta.read()


def traer_json(base, ruta):
    _, cuerpo = traer(base, ruta)
    return json.loads(cuerpo)


def mandar(base, ruta, cuerpo=None):
    """Un POST con cuerpo JSON, igual que el que manda el navegador."""
    datos = json.dumps(cuerpo or {}).encode("utf-8")
    pedido = urllib.request.Request(
        base + ruta, data=datos, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(pedido, timeout=5) as respuesta:
        return json.loads(respuesta.read())


# =============================================================================
# Los archivos de la página
# =============================================================================

def test_sirve_la_pagina(servidor_andando):
    codigo, cuerpo = traer(servidor_andando, "/")
    assert codigo == 200
    assert b"<title>" in cuerpo


def test_sirve_el_estilo_y_el_javascript(servidor_andando):
    """Si estos no llegan, la página se ve como texto plano sin funcionar."""
    for archivo in ("/estilo.css", "/app.js"):
        codigo, cuerpo = traer(servidor_andando, archivo)
        assert codigo == 200
        assert len(cuerpo) > 100


def test_los_archivos_de_la_web_existen_en_el_disco():
    """Un test barato que atrapa un archivo renombrado o borrado."""
    for archivo in ("index.html", "estilo.css", "app.js"):
        assert os.path.exists(os.path.join(servidor.CARPETA_WEB, archivo))


# =============================================================================
# Los datos iniciales
# =============================================================================

def test_los_datos_iniciales_traen_la_configuracion(servidor_andando):
    datos = traer_json(servidor_andando, "/api/inicio")

    assert datos["tonalidad"] == "C"
    assert datos["posicion"] == 12
    assert datos["tono_resultante"] == "F"
    assert "12a posicion" in datos["nombre_posicion"]


def celdas_de(filas):
    """Todas las celdas del atril, sin los huecos."""
    return [celda
            for fila in filas
            for celda in fila["aspirado"] + fila["soplado"]
            if celda]


def test_los_datos_iniciales_traen_el_diagrama(servidor_andando):
    """
    Una fila por agujero, y TODAS con la misma cantidad de columnas.

    Lo segundo no es un detalle de dibujo: si las filas no coincidieran, un
    bend dejaria de leerse como un movimiento horizontal, que es lo unico que
    esta disposicion aporta sobre la anterior.
    """
    datos = traer_json(servidor_andando, "/api/inicio")
    diagrama = datos["diagrama"]

    assert len(diagrama) == 10
    assert [fila["agujero"] for fila in diagrama] == list(range(1, 11))
    for fila in diagrama:
        assert len(fila["aspirado"]) == servidor.COLUMNAS_BEND_ASPIRADO + 1
        assert len(fila["soplado"]) == servidor.COLUMNAS_BEND_SOPLADO + 1


def test_el_atril_pone_los_bends_hacia_afuera():
    """
    El agujero 3 es el que tiene los tres bends, y son la prueba del orden:
    cuanto mas lejos del numero, mas profundo el bend.
    """
    filas = servidor.diagrama_de_la_armonica("C")
    tercero = next(f for f in filas if f["agujero"] == 3)

    tabs = [celda["tab"] if celda else None for celda in tercero["aspirado"]]
    assert tabs == ["-3" + "'" * 3, "-3''", "-3'", "-3"]

    # Y las notas bajan de a un semitono hacia la izquierda.
    # El -3 de una armonica en Do es un Si4 (midi 71), y los bends bajan de
    # a un semitono: Sib, La, Lab.
    midis = [celda["midi"] for celda in tercero["aspirado"]]
    assert midis == [68, 69, 70, 71]

    assert tercero["soplado"][0]["tab"] == "3"


def test_el_atril_pone_los_bends_soplados_del_otro_lado():
    """En el 10 los bends son soplados y van hacia la derecha."""
    filas = servidor.diagrama_de_la_armonica("C")
    decimo = next(f for f in filas if f["agujero"] == 10)

    tabs = [celda["tab"] if celda else None for celda in decimo["soplado"]]
    assert tabs == ["10", "10'", "10''"]

    midis = [celda["midi"] for celda in decimo["soplado"]]
    assert midis == [96, 95, 94]          # bajan hacia afuera, como el 3


def test_el_diagrama_marca_los_agujeros_de_la_escala(servidor_andando):
    """
    Es lo que se pinta de verde en la pantalla. Sin esto, el diagrama sería
    solo un mapa y no una ayuda.
    """
    datos = traer_json(servidor_andando, "/api/inicio")
    en_escala = [c for c in celdas_de(datos["diagrama"]) if c["en_escala"]]
    assert len(en_escala) > 10


def test_el_diagrama_deja_huecos_donde_no_hay_nota():
    """
    El agujero 5 no tiene ningun bend, y ahi van celdas vacias.

    Se mandan como None y no se omiten: son las que mantienen alineadas las
    diez filas.
    """
    filas = servidor.diagrama_de_la_armonica("C")
    quinto = next(f for f in filas if f["agujero"] == 5)

    assert quinto["aspirado"][:3] == [None, None, None]
    assert quinto["aspirado"][3]["tab"] == "-5"
    assert quinto["soplado"][1:] == [None, None]


def test_el_diagrama_funciona_sin_escala_de_referencia():
    filas = servidor.diagrama_de_la_armonica("C")
    assert filas
    assert not any(celda["en_escala"] for celda in celdas_de(filas))


def test_el_diagrama_funciona_con_otra_armonica():
    filas = servidor.diagrama_de_la_armonica("G", 2, "blues")
    assert filas[0]["soplado"][0]["nombre"] == "G3"


# =============================================================================
# El estado en vivo
# =============================================================================

def test_el_estado_arranca_vacio():
    estado = servidor.EstadoCompartido("C", 12, "blues_mayor")
    datos = estado.como_diccionario()

    assert datos["escuchando"] is False
    assert datos["nota"] is None
    assert datos["cantidad_notas"] == 0


def sostener(estado, tab, cents=0.0, desde=1.0, ventanas=None,
             tonalidad="C"):
    """
    Toca la misma nota varias ventanas seguidas, como al sostenerla.

    El cartel grande exige que una nota se repita antes de mostrarla: una sola
    ventana no alcanza, y ese es justamente el punto. Los tests que solo
    quieren "que haya una nota en pantalla" pasan por aca.
    """
    if ventanas is None:
        ventanas = config.VENTANAS_PARA_CONFIRMAR
    nota = mapeo.tab_a_nota(tab, tonalidad) if tab else None
    for numero in range(ventanas):
        estado.actualizar(nota, cents, 0.2, desde + numero * 0.012, [])


def test_el_estado_guarda_la_nota_que_llega():
    estado = servidor.EstadoCompartido("C", 12, "blues_mayor")

    sostener(estado, "-5", cents=-8.0, desde=3.5)
    datos = estado.como_diccionario()

    assert datos["nota"]["nombre"] == "F5"
    assert datos["cents"] == pytest.approx(-8.0)


def test_una_sola_ventana_no_alcanza_para_mostrar_una_nota():
    """
    EL FILTRO DEL CARTEL GRANDE.

    La tablatura pasa por segmentacion, que descarta lo que dura menos de
    60 ms. El cartel no pasaba por ningun filtro: mostraba la ultima ventana
    que dio nota, ochenta y seis veces por segundo. Una sola ventana
    equivocada —un ataque, un cambio de nota, un golpe de aire— se veia como
    un cambio de nota en la pantalla.
    """
    estado = servidor.EstadoCompartido("C")

    estado.actualizar(mapeo.tab_a_nota("-5", "C"), 0.0, 0.2, 1.0, [])
    assert estado.como_diccionario()["nota"] is None

    estado.actualizar(mapeo.tab_a_nota("-5", "C"), 0.0, 0.2, 1.01, [])
    estado.actualizar(mapeo.tab_a_nota("-5", "C"), 0.0, 0.2, 1.02, [])
    assert estado.como_diccionario()["nota"]["nombre"] == "F5"


def test_una_ventana_suelta_no_cambia_la_nota_que_ya_se_muestra():
    """El caso concreto: tocas el 1 y aparece el 8 por una sola ventana."""
    estado = servidor.EstadoCompartido("C")
    sostener(estado, "-1", desde=1.0)
    assert estado.como_diccionario()["nota"]["nombre"] == "D4"

    # Una ventana equivocada en el medio: el ↓8 es el ↓1 por cuatro.
    estado.actualizar(mapeo.tab_a_nota("-8", "C"), 0.0, 0.2, 1.05, [])

    assert estado.como_diccionario()["nota"]["nombre"] == "D4"


def test_una_nota_que_de_verdad_cambia_se_muestra():
    """El filtro no puede tragarse los cambios reales."""
    estado = servidor.EstadoCompartido("C")
    sostener(estado, "-1", desde=1.0)

    sostener(estado, "-4", desde=1.2)

    assert estado.como_diccionario()["nota"]["nombre"] == "D5"


def test_el_estado_sostiene_la_nota_cuando_deja_de_llegar():
    """
    Igual que en la terminal: dentro de una nota sostenida hay ventanas
    sueltas sin deteccion, y sin esto el agujero desapareceria en cada
    respiracion.
    """
    estado = servidor.EstadoCompartido("C")
    sostener(estado, "-5", desde=1.0)

    estado.actualizar(None, 0.0, 0.001, 1.1, [])
    estado.actualizar(None, 0.0, 0.001, 1.2, [])

    assert estado.como_diccionario()["nota"]["nombre"] == "F5"


def test_el_cartel_se_apaga_cuando_el_silencio_es_largo():
    """
    Antes la nota quedaba en pantalla para siempre: dejabas de tocar, te ibas,
    y la pantalla seguia mostrando el ultimo agujero como si sonara.

    El umbral para apagar es mas largo que el de confirmar, a proposito: son
    dos preguntas distintas y se resuelven con dos numeros distintos.
    """
    estado = servidor.EstadoCompartido("C")
    sostener(estado, "-5", desde=1.0)

    estado.actualizar(None, 0.0, 0.0,
                      1.0 + config.SEGUNDOS_PARA_APAGAR_CARTEL + 0.2, [])

    assert estado.como_diccionario()["nota"] is None
    assert estado.como_diccionario()["cents"] == 0.0


def test_el_estado_dice_si_la_nota_esta_en_la_escala():
    estado = servidor.EstadoCompartido("C", 12, "blues_mayor")

    sostener(estado, "-5", desde=1.0)
    assert estado.como_diccionario()["nota"]["en_escala"] is True

    sostener(estado, "2", desde=2.0)
    assert estado.como_diccionario()["nota"]["en_escala"] is False


def test_sin_escala_de_referencia_no_dice_ni_si_ni_no():
    """None, no False: sin escala elegida la pregunta no tiene sentido."""
    estado = servidor.EstadoCompartido("C")
    sostener(estado, "-5", desde=1.0)
    assert estado.como_diccionario()["nota"]["en_escala"] is None


def test_reiniciar_limpia_todo():
    estado = servidor.EstadoCompartido("C")
    estado.actualizar(mapeo.tab_a_nota("-5", "C"), 5.0, 0.3, 9.0, [])
    estado.reiniciar()

    datos = estado.como_diccionario()
    assert datos["nota"] is None
    assert datos["segundos"] == 0.0


def test_la_transmision_manda_eventos_con_el_formato_correcto(servidor_andando):
    """
    Server-sent events: cada mensaje es la palabra "data:", el JSON, y dos
    saltos de linea. Ese es todo el protocolo, y por eso no hace falta
    ninguna biblioteca.
    """
    import http.client
    from urllib.parse import urlparse

    partes = urlparse(servidor_andando)
    conexion = http.client.HTTPConnection(partes.hostname, partes.port, timeout=5)
    conexion.request("GET", "/api/vivo")
    respuesta = conexion.getresponse()

    assert respuesta.status == 200
    assert "text/event-stream" in respuesta.getheader("Content-Type")

    linea = respuesta.fp.readline().decode("utf-8")
    assert linea.startswith("data: ")
    assert json.loads(linea[6:])["escuchando"] is False

    conexion.close()


# =============================================================================
# El historial
# =============================================================================

def test_el_historial_lee_las_sesiones_guardadas(tmp_path):
    eventos = [
        segmentacion.Evento(
            nota=mapeo.tab_a_nota(tab, "C"), inicio_seg=i * 0.5,
            duracion_seg=0.4, frecuencia_hz=440.0, cents=cents,
            confianza=0.99, ventanas=30,
        )
        for i, (tab, cents) in enumerate([
            ("-5", 15.0), ("6", 14.0), ("-6", 16.0), ("7", 15.0),
            ("-3''", -20.0),
        ])
    ]
    exportacion.guardar_sesion(eventos, "C", 12, "blues_mayor",
                               carpeta=str(tmp_path))

    datos = servidor.historial(str(tmp_path))
    assert len(datos["sesiones"]) == 1
    assert datos["sesiones"][0]["notas"] == 5
    assert datos["sesiones"][0]["tonalidad"] == "C"


def test_el_historial_sigue_cada_bend_a_lo_largo_de_las_sesiones(tmp_path):
    """
    LO QUE HACE QUE EL PROYECTO SIRVA EN EL TIEMPO.

    Los JSON ya guardaban todo; faltaba mirarlos juntos. Un bend que aparece
    en varias sesiones es una tendencia, y eso es lo que dice si la practica
    esta funcionando.
    """
    from datetime import datetime

    for dia, cents_del_bend in [(1, -40.0), (2, -25.0), (3, -8.0)]:
        eventos = [
            segmentacion.Evento(
                nota=mapeo.tab_a_nota(tab, "C"), inicio_seg=i * 0.5,
                duracion_seg=0.4, frecuencia_hz=440.0, cents=cents,
                confianza=0.99, ventanas=30,
            )
            for i, (tab, cents) in enumerate([
                ("-5", 0.0), ("6", 0.0), ("-6", 0.0), ("7", 0.0),
                ("-3''", cents_del_bend),
            ])
        ]
        exportacion.guardar_sesion(
            eventos, "C", 12, "blues_mayor", carpeta=str(tmp_path),
            momento=datetime(2026, 9, dia, 10, 0, 0),
        )

    datos = servidor.historial(str(tmp_path))
    puntos = datos["bends"]["-3''"]

    assert len(puntos) == 3
    # Y se ve la mejora: de 40 cents abajo a 8.
    assert puntos[0]["cents"] == pytest.approx(-40.0, abs=1)
    assert puntos[-1]["cents"] == pytest.approx(-8.0, abs=1)


def test_los_bends_del_historial_descuentan_la_afinacion_de_la_armonica(tmp_path):
    """
    Sin descontarla estariamos mezclando como esta afinado el instrumento con
    como se toco, que es justo lo que el resto de la app se cuida de no hacer.
    """
    eventos = [
        segmentacion.Evento(
            nota=mapeo.tab_a_nota(tab, "C"), inicio_seg=i * 0.5,
            duracion_seg=0.4, frecuencia_hz=440.0, cents=cents,
            confianza=0.99, ventanas=30,
        )
        # Cuatro naturales a +15 (la armonica esta alta) y un bend a +15
        # tambien: contra la armonica, ese bend esta perfecto.
        for i, (tab, cents) in enumerate([
            ("-5", 15.0), ("6", 15.0), ("-6", 15.0), ("7", 15.0),
            ("-3''", 15.0),
        ])
    ]
    from datetime import datetime
    for dia in (1, 2):
        exportacion.guardar_sesion(
            eventos, "C", 12, "blues_mayor", carpeta=str(tmp_path),
            momento=datetime(2026, 9, dia, 10, 0, 0),
        )

    puntos = servidor.historial(str(tmp_path))["bends"]["-3''"]
    assert puntos[0]["cents"] == pytest.approx(0.0, abs=1)


def test_un_bend_que_aparece_una_sola_vez_no_es_una_tendencia(tmp_path):
    eventos = [
        segmentacion.Evento(
            nota=mapeo.tab_a_nota(tab, "C"), inicio_seg=i * 0.5,
            duracion_seg=0.4, frecuencia_hz=440.0, cents=0.0,
            confianza=0.99, ventanas=30,
        )
        for i, tab in enumerate(["-5", "6", "-6", "7", "-3''"])
    ]
    exportacion.guardar_sesion(eventos, "C", 12, "blues_mayor",
                               carpeta=str(tmp_path))

    assert servidor.historial(str(tmp_path))["bends"] == {}


def test_el_historial_de_una_carpeta_vacia_no_rompe(tmp_path):
    datos = servidor.historial(str(tmp_path))
    assert datos["sesiones"] == []
    assert datos["bends"] == {}


def test_el_historial_responde_por_http(servidor_andando):
    datos = traer_json(servidor_andando, "/api/historial")
    assert "sesiones" in datos
    assert "bends" in datos


# =============================================================================
# El resumen
# =============================================================================

def test_el_resumen_sin_notas_lo_dice(servidor_andando):
    datos = traer_json(servidor_andando, "/api/resumen")
    assert datos["hay"] is False


def test_el_resumen_con_notas_trae_los_hallazgos(servidor_andando):
    estado = servidor.Manejador.estado
    estado.eventos = [
        segmentacion.Evento(
            nota=mapeo.tab_a_nota(tab, "C"), inicio_seg=i * 0.5,
            duracion_seg=0.4, frecuencia_hz=440.0, cents=cents,
            confianza=0.99, ventanas=30,
        )
        for i, (tab, cents) in enumerate([
            ("-5", 0.0), ("6", 0.0), ("-6", 0.0), ("7", 0.0),
            ("-3''", -35.0), ("-3''", -34.0), ("-3''", -36.0),
        ])
    ]

    datos = traer_json(servidor_andando, "/api/resumen")
    assert datos["hay"] is True
    assert datos["notas"] == 7
    assert datos["hallazgos"]
    assert "-3''" in datos["hallazgos"][0]["titulo"]


# =============================================================================
# Las frases
#
# El modo "repeti esta frase" desde la web. Los tres modos (sesion, frase,
# practicar) escuchan exactamente igual: lo unico que cambia es que hace el
# servidor al terminar. Por eso los tests arman el estado a mano y llaman a
# terminar, sin abrir nunca el microfono.
# =============================================================================

@pytest.fixture
def carpeta_de_frases(tmp_path, monkeypatch):
    """Las frases van a una carpeta temporal y no a la tuya de verdad."""
    monkeypatch.setattr(frases, "CARPETA_POR_DEFECTO", str(tmp_path))
    return str(tmp_path)


def eventos_de(tabs, separacion=0.5, tonalidad="C", cents=0.0):
    """Una tanda de eventos parejos, uno cada `separacion` segundos."""
    return [
        segmentacion.Evento(
            nota=mapeo.tab_a_nota(tab, tonalidad), inicio_seg=i * separacion,
            duracion_seg=separacion * 0.8, frecuencia_hz=440.0, cents=cents,
            confianza=0.99, ventanas=30,
        )
        for i, tab in enumerate(tabs)
    ]


def preparar(modo, nombre, eventos):
    """Deja el estado como si acabaras de tocar, sin haber tocado."""
    estado = servidor.Manejador.estado
    estado.modo = modo
    estado.nombre_frase = nombre
    estado.eventos = eventos
    estado.escuchando = True
    return estado


def test_grabar_una_frase_pide_el_nombre(servidor_andando):
    """Sin nombre no hay archivo donde guardarla. Se rechaza antes de escuchar."""
    respuesta = mandar(servidor_andando, "/api/comenzar", {"modo": "frase"})
    assert respuesta["ok"] is False
    assert "nombre" in respuesta["motivo"]
    assert servidor.Manejador.estado.escuchando is False


def test_practicar_una_frase_que_no_existe_se_rechaza(
        servidor_andando, carpeta_de_frases):
    """
    Mejor avisar ahora que dejarte tocar treinta segundos para nada.

    Este es el motivo por el que la validacion esta en _comenzar y no en
    _terminar: si falla al final, ya perdiste lo que tocaste.
    """
    respuesta = mandar(servidor_andando, "/api/comenzar",
                       {"modo": "practicar", "nombre": "la que no existe"})
    assert respuesta["ok"] is False
    assert "no encontre" in respuesta["motivo"]
    assert servidor.Manejador.estado.escuchando is False


def test_terminar_grabando_guarda_la_frase(servidor_andando, carpeta_de_frases):
    preparar("frase", "lick de segunda", eventos_de(["-2", "-3''", "4", "-4"]))

    respuesta = mandar(servidor_andando, "/api/terminar")

    assert respuesta["ok"] is True
    assert respuesta["modo"] == "frase"
    assert respuesta["frase"]["notas"] == 4
    assert respuesta["frase"]["tab"][0] == "-2"

    guardada = frases.buscar("lick de segunda")
    assert guardada is not None
    assert guardada.cantidad == 4


def test_una_frase_sin_notas_no_se_guarda(servidor_andando, carpeta_de_frases):
    """Si el microfono no engancho nada, no se guarda una frase vacia."""
    preparar("frase", "la que no sono", [])

    respuesta = mandar(servidor_andando, "/api/terminar")

    assert respuesta["ok"] is False
    assert frases.listar() == []


def test_terminar_practicando_compara_contra_la_frase(
        servidor_andando, carpeta_de_frases):
    """
    La misma frase tocada un 20% mas lento tiene que dar 100% de aciertos.

    Tocar mas lento es una decision, no un error: el porcentaje mide las
    NOTAS, y la velocidad se informa aparte.
    """
    referencia = frases.desde_eventos(
        eventos_de(["-2", "-3''", "4", "-4"]), "escala corta", "C", 2, None)
    frases.guardar(referencia)

    preparar("practicar", "escala corta",
             eventos_de(["-2", "-3''", "4", "-4"], separacion=0.6))

    respuesta = mandar(servidor_andando, "/api/terminar")

    assert respuesta["ok"] is True
    assert respuesta["modo"] == "practicar"
    comparacion = respuesta["comparacion"]
    assert comparacion["esperadas"] == 4
    assert comparacion["porcentaje"] == 100
    assert comparacion["velocidad"] == 20     # 20% mas lento
    assert comparacion["faltantes"] == []
    assert len(comparacion["notas"]) == 4


def test_practicando_marca_la_nota_que_erraste(
        servidor_andando, carpeta_de_frases):
    referencia = frases.desde_eventos(eventos_de(["-2", "4", "-4"]), "tres notas")
    frases.guardar(referencia)

    preparar("practicar", "tres notas", eventos_de(["-2", "5", "-4"]))

    comparacion = mandar(servidor_andando, "/api/terminar")["comparacion"]

    assert comparacion["cambiadas"] == [{"esperada": "4", "tocada": "5"}]
    assert comparacion["porcentaje"] < 100


def test_la_lista_de_frases_trae_los_datos_para_la_pantalla(
        servidor_andando, carpeta_de_frases):
    frases.guardar(frases.desde_eventos(
        eventos_de(["-2", "-3''", "4"]), "lick uno", "C", 2, "blues"))

    datos = traer_json(servidor_andando, "/api/frases")

    assert len(datos["frases"]) == 1
    frase = datos["frases"][0]
    assert frase["nombre"] == "lick uno"
    assert frase["notas"] == 3
    assert frase["tonalidad"] == "C"
    assert frase["posicion"] == 2
    assert frase["tab"] == ["-2", "-3''", "4"]


def test_borrar_una_frase_la_saca_de_la_lista(servidor_andando, carpeta_de_frases):
    frases.guardar(frases.desde_eventos(eventos_de(["-2", "4"]), "descartable"))
    assert len(frases.listar()) == 1

    respuesta = mandar(servidor_andando, "/api/frases/borrar",
                       {"nombre": "descartable"})

    assert respuesta["ok"] is True
    assert frases.listar() == []


def test_borrar_una_frase_que_no_esta_no_rompe(servidor_andando, carpeta_de_frases):
    respuesta = mandar(servidor_andando, "/api/frases/borrar", {"nombre": "fantasma"})
    assert respuesta["ok"] is False


def test_el_estado_en_vivo_dice_en_que_modo_esta():
    """
    La pantalla dibuja los botones a partir del estado del servidor.

    Sin esto, dos pestanas abiertas mostrarian cosas distintas: una creeria
    que esta grabando una frase y la otra que hay una sesion andando.
    """
    estado = servidor.EstadoCompartido("C", 12, "blues_mayor")
    assert estado.como_diccionario()["modo"] == "sesion"

    estado.modo = "practicar"
    estado.nombre_frase = "lick uno"
    datos = estado.como_diccionario()
    assert datos["modo"] == "practicar"
    assert datos["nombre_frase"] == "lick uno"

    estado.reiniciar()
    assert estado.como_diccionario()["modo"] == "sesion"


# =============================================================================
# Subir un .wav
#
# El camino de las grabaciones de Leandro y de los audios que Bruno ya tiene
# grabados. El nombre va en la URL y los bytes crudos en el cuerpo.
# =============================================================================

def bytes_de_wav(muestras):
    """Los bytes de un .wav con esas muestras, listos para subir."""
    descriptor, ruta = tempfile.mkstemp(suffix=".wav")
    os.close(descriptor)
    try:
        audio.escribir_wav(ruta, muestras)
        with open(ruta, "rb") as archivo:
            return archivo.read()
    finally:
        os.remove(ruta)


def wav_de(tabs, tonalidad="C", duracion_nota=0.45):
    """Un .wav con esas notas, en memoria."""
    muestras, _ = generar_wav.generar_secuencia(
        tabs, tonalidad, duracion_nota=duracion_nota)
    return bytes_de_wav(muestras)


def subir(base, ruta, nombre, datos, **opciones):
    """Un POST con el nombre y las opciones en la URL, y el audio en el cuerpo."""
    consulta = "?nombre=" + urllib.parse.quote(nombre)
    for clave, valor in opciones.items():
        consulta += "&" + clave + "=" + urllib.parse.quote(str(valor))

    pedido = urllib.request.Request(
        base + ruta + consulta, data=datos, method="POST",
        headers={"Content-Type": "application/octet-stream"},
    )
    with urllib.request.urlopen(pedido, timeout=90) as respuesta:
        return json.loads(respuesta.read())


def wav_polifonico():
    """Cuatro notas sonando juntas: lo que un detector monofonico no resuelve."""
    return bytes_de_wav(sum(
        generar_wav.generar_nota(frecuencia, 3.0, volumen=0.25)
        for frecuencia in (196.0, 246.94, 293.66, 392.0)
    ))


def test_importar_un_wav_lo_guarda_como_frase(servidor_andando, carpeta_de_frases):
    respuesta = subir(servidor_andando, "/api/frases/importar",
                      "lick de lean", wav_de(["-2", "4", "-4", "-5"]))

    assert respuesta["ok"] is True
    assert respuesta["frase"]["notas"] == 4
    assert respuesta["frase"]["tab"] == ["-2", "4", "-4", "-5"]
    assert respuesta["avisos"] == []

    guardada = frases.buscar("lick de lean")
    assert guardada is not None
    assert guardada.cantidad == 4


def test_el_audio_importado_queda_al_lado_de_la_frase(
        servidor_andando, carpeta_de_frases):
    """
    Una frase de Leandro se lee, pero sobre todo se ESCUCHA.

    Sin el audio guardado, la referencia se degrada a una tablatura y perdes
    justo el ritmo, que es lo unico que la tablatura no sabe transmitir.
    """
    subir(servidor_andando, "/api/frases/importar", "con audio",
          wav_de(["4", "-4", "-5"]))

    guardados = sorted(os.listdir(carpeta_de_frases))
    assert "con_audio.json" in guardados
    assert "con_audio_audio.wav" in guardados


def test_importar_sin_nombre_se_rechaza(servidor_andando, carpeta_de_frases):
    respuesta = subir(servidor_andando, "/api/frases/importar", "  ",
                      wav_de(["4", "-4"]))
    assert respuesta["ok"] is False
    assert "nombre" in respuesta["motivo"]
    assert frases.listar() == []


def test_un_audio_con_banda_no_se_guarda_como_frase(
        servidor_andando, carpeta_de_frases):
    """
    EL CONTROL QUE MAS IMPORTA DE TODA LA SOLAPA.

    Si se guardara una frase transcrita de un audio polifonico, quedaria ahi
    para siempre y todas las practicas contra ella medirian contra notas
    inventadas. Mejor no guardar nada y decir por que.
    """
    respuesta = subir(servidor_andando, "/api/frases/importar",
                      "la base entera", wav_polifonico())

    assert respuesta["ok"] is False
    assert "monofon" in respuesta["motivo"]
    assert frases.listar() == []


def test_un_archivo_que_no_es_wav_da_un_error_claro(
        servidor_andando, carpeta_de_frases):
    """
    Un m4a o un mp3 renombrado. Pasa seguido, y no tiene que romper nada.

    El mensaje NO nombra el archivo, aunque el error original si lo haga: acá
    ese archivo es un temporal con nombre inventado, y decirlo solo confunde.
    En la terminal, en cambio, el nombre es justo lo que queres saber.
    """
    respuesta = subir(servidor_andando, "/api/frases/importar",
                      "no es un wav", b"esto no es audio de ninguna manera")

    assert respuesta["ok"] is False
    assert "m4a" in respuesta["motivo"]
    assert "Temp" not in respuesta["motivo"]
    assert frases.listar() == []


def test_comparar_un_wav_contra_una_frase_guardada(
        servidor_andando, carpeta_de_frases):
    """
    El intento tambien puede venir de un archivo.

    Sirve cuando ya grabaste con la grabadora de Windows, y para comparar dos
    audios viejos sin volver a tocar.
    """
    subir(servidor_andando, "/api/frases/importar", "escala corta",
          wav_de(["-2", "4", "-4", "-5"]))

    respuesta = subir(servidor_andando, "/api/frases/intento", "escala corta",
                      wav_de(["-2", "4", "-4", "-5"], duracion_nota=0.55))

    assert respuesta["ok"] is True
    comparacion = respuesta["comparacion"]
    assert comparacion["esperadas"] == 4
    assert comparacion["porcentaje"] == 100
    # Mismo audio, 22% mas lento. Eso es una decision y no un error.
    assert comparacion["velocidad"] > 15
    assert comparacion["calidad"] == "muy parecida"


def test_comparar_contra_una_frase_que_no_existe(servidor_andando, carpeta_de_frases):
    respuesta = subir(servidor_andando, "/api/frases/intento", "fantasma",
                      wav_de(["4", "-4"]))
    assert respuesta["ok"] is False
    assert "no encontre" in respuesta["motivo"]


def test_el_audio_subido_no_queda_tirado_en_el_disco(
        servidor_andando, carpeta_de_frases, tmp_path, monkeypatch):
    """
    El .wav va a un archivo temporal porque audio.leer_wav trabaja con rutas.

    Si no se borrara, cada importacion dejaria un archivo para siempre. Se
    apunta el temporal a una carpeta vacia y se cuenta lo que queda.
    """
    temporales = tmp_path / "temporales"
    temporales.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temporales))

    subir(servidor_andando, "/api/frases/importar", "una", wav_de(["4", "-4"]))
    subir(servidor_andando, "/api/frases/intento", "una", wav_de(["4", "-4"]))
    subir(servidor_andando, "/api/frases/importar", "con banda", b"no es un wav")

    assert os.listdir(str(temporales)) == []


# =============================================================================
# Con que armonica se grabo el archivo
#
# La app NO lo puede deducir (ver tests/test_transcripcion.py), pero Bruno si
# lo sabe. Por eso se manda como dato y no se adivina.
# =============================================================================

def test_los_datos_iniciales_traen_las_armonicas_disponibles(servidor_andando):
    """El selector de la web se llena con esto."""
    datos = traer_json(servidor_andando, "/api/inicio")
    assert "C" in datos["tonalidades"]
    assert datos["tonalidad"] in datos["tonalidades"]


def test_importar_usa_la_armonica_que_le_decis(servidor_andando, carpeta_de_frases):
    """
    El mismo audio, importado como armonica en Do y como armonica en La.

    Son dos tablaturas distintas para el mismo sonido, y las dos son correctas
    segun con que armonica se haya tocado. Este dato lo pone el que sube el
    archivo porque es el unico que lo sabe.
    """
    audio_grabado = wav_de(["4", "-4", "-5"])

    como_do = subir(servidor_andando, "/api/frases/importar", "en do",
                    audio_grabado, tonalidad="C")
    como_la = subir(servidor_andando, "/api/frases/importar", "en la",
                    audio_grabado, tonalidad="A")

    assert como_do["frase"]["tonalidad"] == "C"
    assert como_la["frase"]["tonalidad"] == "A"
    assert como_do["frase"]["tab"] != como_la["frase"]["tab"]

    # Y la frase guardada se acuerda, asi que el intento se lee igual que ella.
    assert frases.buscar("en la").tonalidad == "A"


def test_sin_decir_nada_se_usa_la_armonica_de_la_sesion(
        servidor_andando, carpeta_de_frases):
    respuesta = subir(servidor_andando, "/api/frases/importar", "por defecto",
                      wav_de(["4", "-4"]))
    assert respuesta["frase"]["tonalidad"] == "C"


def test_una_armonica_que_no_existe_se_rechaza(servidor_andando, carpeta_de_frases):
    respuesta = subir(servidor_andando, "/api/frases/importar", "rara",
                      wav_de(["4", "-4"]), tonalidad="H")
    assert respuesta["ok"] is False
    assert "H" in respuesta["motivo"]
    assert frases.listar() == []


# =============================================================================
# La salida de emergencia
# =============================================================================

@pytest.fixture
def umbral_imposible(monkeypatch):
    """
    Hace que hasta una grabacion perfecta no pase el control.

    POR QUE SE FUERZA EL UMBRAL EN VEZ DE FABRICAR UN AUDIO DUDOSO

    Porque el audio dudoso casi no existe. Midiendo una melodia con una base
    encima, el puntaje de monofonia va de 0.83 (transcribe bien) a 0.00 sin
    escalones: cuando el control falla, ya no quedaba ninguna nota que
    rescatar. La zona intermedia que esta salida de emergencia atiende —una
    grabacion real con ruido de sala, reverb o vibrato— no se puede fabricar
    con senos.

    Asi que se prueba la LOGICA, que es lo que este proyecto controla: que al
    rechazar devuelva la tablatura, y que con `igual` la guarde avisando.
    """
    monkeypatch.setattr(servidor.transcripcion, "MONOFONIA_MINIMA", 0.99)


def test_cuando_rechaza_muestra_lo_que_habria_transcrito(
        servidor_andando, carpeta_de_frases, umbral_imposible):
    """
    El umbral de monofonia es una heuristica, no una ley.

    Rechazar sin mostrar nada obliga a creerle a la app. Mostrando la
    tablatura, el que decide es el unico que puede: el que sabe cual era la
    frase. Lo unico que se garantiza es que la decision se tome MIRANDO.
    """
    respuesta = subir(servidor_andando, "/api/frases/importar",
                      "dudosa", wav_de(["-2", "4", "-4"]))

    assert respuesta["ok"] is False
    assert respuesta["se_puede_igual"] is True
    assert respuesta["vista_previa"] == ["-2", "4", "-4"]
    assert frases.listar() == []


def test_con_igual_la_guarda_pero_deja_dicho_que_la_salteo(
        servidor_andando, carpeta_de_frases, umbral_imposible):
    respuesta = subir(servidor_andando, "/api/frases/importar",
                      "la guardo igual", wav_de(["-2", "4", "-4"]), igual="1")

    assert respuesta["ok"] is True
    assert any("salteando" in aviso for aviso in respuesta["avisos"])
    assert frases.buscar("la guardo igual") is not None


def test_una_base_encima_no_ofrece_guardarla_igual(
        servidor_andando, carpeta_de_frases):
    """
    El caso real: un audio con la base sonando atras.

    No hay nada que ofrecer, y no es por prudencia: para cuando el control
    falla, el detector ya no reconocio ni una nota. Este test documenta que la
    salida de emergencia NO sirve para rescatar una grabacion con banda.
    """
    respuesta = subir(servidor_andando, "/api/frases/importar",
                      "con la base", wav_polifonico())

    assert respuesta["ok"] is False
    assert "monofon" in respuesta["motivo"]
    assert respuesta["se_puede_igual"] is False
    assert respuesta["vista_previa"] == []


def test_un_audio_mudo_no_ofrece_guardarlo_igual(servidor_andando, carpeta_de_frases):
    """
    No hay nada que decidir: no hay ni una nota.

    La salida de emergencia solo tiene sentido cuando hay una tablatura que
    mirar. Ofrecer "guardala igual" sobre cero notas seria ofrecer guardar
    una frase vacia.
    """
    import numpy

    mudo = bytes_de_wav(numpy.zeros(44100, dtype=numpy.float32))
    respuesta = subir(servidor_andando, "/api/frases/importar", "silencio", mudo)

    assert respuesta["ok"] is False
    assert respuesta.get("se_puede_igual") is False


# =============================================================================
# Los tramos: elegir que pedazo de una grabacion larga guardar
# =============================================================================

def clase_de_prueba(bloques, silencio_entre=2.5):
    """Un audio con forma de clase: frases separadas por silencios largos."""
    import numpy as np

    partes = []
    for numero, tablaturas in enumerate(bloques):
        if numero:
            partes.append(generar_wav.generar_silencio(silencio_entre))
        muestras, _ = generar_wav.generar_secuencia(
            tablaturas, "C", duracion_nota=0.4, duracion_silencio=0.12)
        partes.append(muestras)
    return bytes_de_wav(np.concatenate(partes))


def test_los_tramos_se_listan_sin_guardar_nada(servidor_andando, carpeta_de_frases):
    """
    /api/frases/tramos solo mira. Es la primera mitad del flujo de la web:
    primero te muestro donde hay armonica, despues elegis.
    """
    datos = clase_de_prueba([["-2", "4", "-4"], ["-5", "6", "-6"], ["4", "-4", "-5"]])

    respuesta = subir(servidor_andando, "/api/frases/tramos", "la clase", datos)

    assert respuesta["ok"] is True
    assert len(respuesta["tramos"]) == 3
    assert respuesta["tramos"][0]["numero"] == 1
    assert respuesta["tramos"][0]["tab"] == ["-2", "4", "-4"]
    assert respuesta["tramos"][1]["desde_seg"] > respuesta["tramos"][0]["hasta_seg"]

    # Lo importante: no guardo nada.
    assert frases.listar() == []


def test_la_vista_previa_del_tramo_es_lo_que_se_va_a_guardar(
        servidor_andando, carpeta_de_frases):
    """
    El tab que muestra la lista sale del MISMO recorte que se usa al guardar.

    Si mostraramos el tab del analisis del archivo entero, elegirias mirando
    una cosa y se guardaria otra: la grilla de ventanas arranca en otro lado
    al recortar y cambia una nota o dos.
    """
    datos = clase_de_prueba([["-2", "4", "-4"], ["-5", "6", "-6"]])

    lista = subir(servidor_andando, "/api/frases/tramos", "la clase", datos)
    segundo = lista["tramos"][1]

    guardada = subir(servidor_andando, "/api/frases/importar", "el segundo",
                     datos, desde=segundo["desde_seg"],
                     hasta=segundo["hasta_seg"])

    assert guardada["ok"] is True
    assert guardada["frase"]["tab"] == segundo["tab"]


def test_importar_un_tramo_guarda_solo_ese_pedazo(
        servidor_andando, carpeta_de_frases):
    datos = clase_de_prueba([["-2", "4", "-4"], ["-5", "6", "-6"]])
    lista = subir(servidor_andando, "/api/frases/tramos", "la clase", datos)
    segundo = lista["tramos"][1]

    respuesta = subir(servidor_andando, "/api/frases/importar", "solo el segundo",
                      datos, desde=segundo["desde_seg"],
                      hasta=segundo["hasta_seg"])

    assert respuesta["ok"] is True
    assert respuesta["frase"]["tab"] == ["-5", "6", "-6"]

    frase = frases.buscar("solo el segundo")
    assert frase.cantidad == 3
    # Y los tiempos arrancan en cero, no en el segundo 4 del archivo original.
    assert frase.notas[0].inicio_seg < 0.01


def test_importar_un_pedazo_sin_notas_avisa(servidor_andando, carpeta_de_frases):
    datos = clase_de_prueba([["-2", "4", "-4"], ["-5", "6", "-6"]])

    respuesta = subir(servidor_andando, "/api/frases/importar", "el silencio",
                      datos, desde=2.4, hasta=2.9)

    assert respuesta["ok"] is False
    assert "no hay notas" in respuesta["motivo"]
    assert frases.listar() == []


def test_sin_recorte_se_guarda_el_audio_entero(servidor_andando, carpeta_de_frases):
    """Sin desde/hasta nada cambia: es el camino de siempre."""
    datos = clase_de_prueba([["-2", "4", "-4"], ["-5", "6", "-6"]])

    respuesta = subir(servidor_andando, "/api/frases/importar", "todo", datos)

    assert respuesta["ok"] is True
    assert respuesta["frase"]["notas"] == 6


# =============================================================================
# Los ajustes: elegir microfono y configuracion desde la app
# =============================================================================

def test_los_datos_iniciales_traen_las_opciones_de_los_selectores(servidor_andando):
    """
    La pantalla no sabe que armonicas, posiciones ni escalas existen: se las
    manda Python. Si un dia agregas una escala en tablas.py, aparece sola en
    el selector sin tocar el javascript.
    """
    datos = traer_json(servidor_andando, "/api/inicio")

    assert "C" in datos["tonalidades"]
    assert any(p["numero"] == 12 for p in datos["posiciones"])
    assert any(e["clave"] == "blues_mayor" for e in datos["escalas"])
    assert datos["umbral_volumen"] > 0


def test_cambiar_la_armonica_rehace_el_diagrama(servidor_andando):
    """
    El diagrama se dibuja en Python, asi que cambiar de armonica tiene que
    devolverlo entero: la pantalla no sabe que nota da cada agujero.
    """
    antes = traer_json(servidor_andando, "/api/inicio")
    assert antes["diagrama"][0]["soplado"][0]["nombre"] == "C4"

    respuesta = mandar(servidor_andando, "/api/configuracion", {"tonalidad": "A"})

    assert respuesta["ok"] is True
    assert respuesta["inicio"]["tonalidad"] == "A"
    assert respuesta["inicio"]["diagrama"][0]["soplado"][0]["nombre"] == "A3"


def test_cambiar_la_posicion_cambia_el_tono_que_suena(servidor_andando):
    respuesta = mandar(servidor_andando, "/api/configuracion", {"posicion": 2})

    assert respuesta["ok"] is True
    # Armonica en Do, 2a posicion: suena en Sol.
    assert respuesta["inicio"]["tono_resultante"] == "G"


def test_no_se_puede_configurar_una_armonica_que_no_existe(servidor_andando):
    respuesta = mandar(servidor_andando, "/api/configuracion", {"tonalidad": "H"})

    assert respuesta["ok"] is False
    assert servidor.Manejador.estado.tonalidad == "C"


def test_no_se_puede_configurar_una_posicion_sin_tabla(servidor_andando):
    """
    Las escalas por posicion estan escritas a mano y no estan las doce.
    Aceptar la 7a dejaria el diagrama sin poder marcar ninguna escala.
    """
    respuesta = mandar(servidor_andando, "/api/configuracion", {"posicion": 7})

    assert respuesta["ok"] is False
    assert "tablas" in respuesta["motivo"]


def test_se_puede_cambiar_la_configuracion_mientras_escucha(servidor_andando):
    """
    Escuchar no bloquea nada: el microfono esta prendido todo el tiempo.

    Antes esto estaba prohibido, y con razon: escuchar y grabar eran lo mismo.
    Ahora son dos cosas distintas y cambiar de armonica mientras mirabas la
    pantalla, sin estar grabando nada, no rompe nada.
    """
    respuesta = mandar(servidor_andando, "/api/configuracion",
                       {"tonalidad": "A"})

    assert respuesta["ok"] is True
    assert servidor.Manejador.estado.tonalidad == "A"


def test_no_se_puede_cambiar_la_configuracion_mientras_graba(servidor_andando):
    """
    Grabando si esta prohibido, y por el mismo motivo de siempre: el hilo de
    audio armo su tabla de notas con la armonica anterior, y cambiarla en el
    medio dejaria media sesion transcrita con una y media con otra, sin
    ninguna senal de que paso.
    """
    servidor.Manejador.estado.grabando = True
    try:
        respuesta = mandar(servidor_andando, "/api/configuracion",
                           {"tonalidad": "A"})
    finally:
        servidor.Manejador.estado.grabando = False

    assert respuesta["ok"] is False
    assert servidor.Manejador.estado.tonalidad == "C"


def test_se_puede_elegir_el_microfono(servidor_andando):
    respuesta = mandar(servidor_andando, "/api/configuracion", {"dispositivo": 3})

    assert respuesta["ok"] is True
    assert servidor.Manejador.estado.dispositivo == 3

    # Y volver al predeterminado del sistema.
    mandar(servidor_andando, "/api/configuracion", {"dispositivo": None})
    assert servidor.Manejador.estado.dispositivo is None


def test_el_estado_en_vivo_trae_el_pico_y_el_error_de_audio():
    """
    Los dos datos que hacen falta para contestar "¿me esta escuchando?".

    Sin el pico, un microfono equivocado y una armonica tocada bajito se ven
    identicos: la pantalla quieta. Sin el error, un microfono ocupado por otro
    programa tambien.
    """
    estado = servidor.EstadoCompartido("C", 12, "blues_mayor")
    datos = estado.como_diccionario()

    assert datos["pico"] == 0.0
    assert datos["error_de_audio"] == ""

    estado.actualizar(None, 0.0, 0.4, 1.0, [])
    assert estado.como_diccionario()["pico"] == 0.4


def test_el_pico_baja_despacio_y_sube_de_golpe():
    """
    Es un vumetro, no un termometro.

    El volumen crudo cae a cero entre nota y nota: una barra que lo siguiera
    parpadearia quince veces por segundo y no se podria leer de reojo mientras
    tocas.
    """
    estado = servidor.EstadoCompartido()

    estado.actualizar(None, 0.0, 0.8, 1.0, [])
    assert estado.como_diccionario()["pico"] == 0.8

    # Silencio: el pico baja, pero no de golpe.
    for _ in range(3):
        estado.actualizar(None, 0.0, 0.0, 1.0, [])
    pico = estado.como_diccionario()["pico"]
    assert 0.4 < pico < 0.8

    # Y un golpe fuerte lo sube al instante.
    estado.actualizar(None, 0.0, 0.95, 1.0, [])
    assert estado.como_diccionario()["pico"] == 0.95


# =============================================================================
# Escuchar la frase guardada
# =============================================================================

def test_el_audio_de_una_frase_se_puede_bajar(servidor_andando, carpeta_de_frases):
    """
    Una frase de referencia se lee, pero sobre todo se ESCUCHA: la tablatura
    no lleva el ritmo, y el ritmo es justo lo que estas tratando de copiar.
    """
    subir(servidor_andando, "/api/frases/importar", "para escuchar",
          wav_de(["-2", "4", "-4"]))

    codigo, cuerpo = traer(
        servidor_andando, "/api/frases/audio?nombre=para%20escuchar")

    assert codigo == 200
    assert cuerpo[:4] == b"RIFF"
    assert len(cuerpo) > 1000


def test_la_lista_dice_cuales_frases_tienen_audio(servidor_andando, carpeta_de_frases):
    subir(servidor_andando, "/api/frases/importar", "con audio",
          wav_de(["-2", "4", "-4"]))

    datos = traer_json(servidor_andando, "/api/frases")

    assert datos["frases"][0]["hay_audio"] is True


def test_pedir_el_audio_de_una_frase_que_no_esta(servidor_andando, carpeta_de_frases):
    try:
        traer(servidor_andando, "/api/frases/audio?nombre=fantasma")
        assert False, "tendria que haber dado 404"
    except urllib.error.HTTPError as fallo:
        assert fallo.code == 404


# =============================================================================
# El microfono queda prendido: escuchar y grabar son dos cosas distintas
#
# Estos tests usan un microfono FALSO. Es la unica manera de probar el bucle
# de audio entero —los pedidos entre hilos, el recorte de memoria, que se
# guarde solo lo grabado— sin una placa de sonido y sin tocar nada.
# =============================================================================

class CapturaFalsa:
    """
    Un microfono de mentira que entrega las ventanas que le pongamos.

    Imita la interfaz de microfono.CapturaMicrofono: entra y sale como
    contexto, entrega ventanas con su instante, y va guardando lo que "entro"
    para poder devolverlo al final.
    """

    def __init__(self, ventanas, frecuencia_muestreo=44100):
        self.frecuencia_muestreo = frecuencia_muestreo
        self._ventanas = ventanas
        self._grabado = []
        self.olvidos = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def ventanas(self):
        import config as configuracion

        salto = configuracion.SALTO_VENTANA / self.frecuencia_muestreo
        for numero, ventana in enumerate(self._ventanas):
            self._grabado.append(ventana)
            yield numero * salto, ventana

    def audio_grabado(self):
        import numpy as np

        if not self._grabado:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._grabado)

    def olvidar_lo_grabado(self):
        self._grabado = []
        self.olvidos += 1


def correr_el_hilo(estado, ventanas, guion=None):
    """
    Corre `escuchar` de punta a punta con un microfono falso.

    `guion` es un diccionario {numero_de_ventana: funcion} para poder apretar
    Grabar y Terminar en el medio del bucle, que es cuando pasan de verdad.
    """
    import numpy as np
    from armonica import microfono

    captura = CapturaFalsa(ventanas)
    detener = threading.Event()
    guion = guion or {}

    ventanas_originales = captura.ventanas

    def ventanas_con_guion():
        for numero, (instante, ventana) in enumerate(ventanas_originales()):
            if numero in guion:
                guion[numero]()
            yield instante, ventana

    captura.ventanas = ventanas_con_guion

    anterior = microfono.CapturaMicrofono
    microfono.CapturaMicrofono = lambda **kwargs: captura
    try:
        servidor.escuchar(estado, detener)
    finally:
        microfono.CapturaMicrofono = anterior

    return captura


def ventanas_de_silencio(cuantas):
    import numpy as np
    import config as configuracion

    return [np.zeros(configuracion.TAMANO_VENTANA, dtype=np.float32)
            for _ in range(cuantas)]


def test_sin_grabar_el_audio_no_se_acumula():
    """
    EL MOTIVO POR EL QUE ESTO IMPORTA.

    El microfono queda prendido todo el tiempo que la app esta abierta. Sin
    tirar lo que entra, estar sentado sin tocar suma diez megas por minuto, y
    a la media hora la app se comio la memoria de la maquina.
    """
    estado = servidor.EstadoCompartido("C")
    captura = correr_el_hilo(estado, ventanas_de_silencio(40))

    assert estado.grabando is False
    assert captura.olvidos > 30          # tira lo grabado en cada ventana
    assert len(captura.audio_grabado()) == 0


def test_grabando_si_se_acumula():
    estado = servidor.EstadoCompartido("C")
    estado.grabando = True

    captura = correr_el_hilo(estado, ventanas_de_silencio(20))

    assert captura.olvidos == 0
    assert len(captura.audio_grabado()) > 0


def test_apretar_grabar_tira_lo_de_antes():
    """
    Lo que se guarda arranca cuando apretaste Grabar, no cuando abriste la app.

    Sin esto, darle a Terminar y guardar despues de veinte minutos con la app
    abierta guardaria los veinte minutos.
    """
    import config as configuracion

    estado = servidor.EstadoCompartido("C")

    def apretar_grabar():
        estado.grabando = True
        estado.pedir("arrancar")

    captura = correr_el_hilo(
        estado, ventanas_de_silencio(30), guion={20: apretar_grabar})

    # Solo las diez ventanas de despues del pedido.
    esperado = 10 * configuracion.TAMANO_VENTANA
    assert len(captura.audio_grabado()) == pytest.approx(esperado, rel=0.2)


def test_al_terminar_el_hilo_deja_el_audio_y_las_mediciones():
    """
    El hilo de audio es el unico que puede cerrar una grabacion: es el que
    tiene la captura. El hilo del HTTP se lo pide y espera.
    """
    estado = servidor.EstadoCompartido("C")

    def apretar_grabar():
        estado.grabando = True
        estado.pedir("arrancar")

    def apretar_terminar():
        estado.grabando = False
        estado.pedir("cerrar")

    correr_el_hilo(estado, ventanas_de_silencio(40),
                   guion={10: apretar_grabar, 30: apretar_terminar})

    assert estado.grabacion_lista is True
    assert estado.audio_grabado is not None
    assert len(estado.audio_grabado) > 0
    assert estado.mediciones


def test_sin_grabar_la_historia_se_recorta():
    """
    La tablatura de lo ultimo que tocaste se sigue mostrando, pero acotada.

    Se guardan config.SEGUNDOS_EN_PANTALLA y no mas: el resto no lo mira nadie
    y crece para siempre.
    """
    import config as configuracion

    estado = servidor.EstadoCompartido("C")
    ventanas_en_pantalla = int(
        configuracion.SEGUNDOS_EN_PANTALLA * 44100 / configuracion.SALTO_VENTANA
    )

    correr_el_hilo(estado, ventanas_de_silencio(ventanas_en_pantalla * 3))

    # El hilo deja de recortar recien al pasar el doble del tope.
    assert len(estado.eventos) == 0        # era silencio: no hay notas
    assert estado.escuchando is False      # el bucle termino


def test_el_estado_en_vivo_distingue_escuchar_de_grabar():
    """
    Son dos banderas distintas y la pantalla necesita las dos.

    Cuando eran una sola, probar el microfono desde Ajustes dejaba la app
    "escuchando" en modo prueba y los dos botones de la solapa En vivo
    quedaban muertos: uno porque ya escuchaba y el otro porque no era una
    sesion. Es el error que hizo falta este cambio.
    """
    estado = servidor.EstadoCompartido("C")
    datos = estado.como_diccionario()

    assert datos["escuchando"] is False
    assert datos["grabando"] is False

    estado.escuchando = True
    assert estado.como_diccionario()["escuchando"] is True
    assert estado.como_diccionario()["grabando"] is False


def test_los_pedidos_se_toman_una_sola_vez():
    estado = servidor.EstadoCompartido("C")

    assert estado.tomar_pedido() is None

    estado.pedir("arrancar")
    assert estado.tomar_pedido() == "arrancar"
    assert estado.tomar_pedido() is None
