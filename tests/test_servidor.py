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
import urllib.error
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
    servidor.Manejador.pendiente = None
    servidor.Manejador.sesion_pendiente = None
    servidor.Manejador.ultimo_intento = None

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


def test_la_lista_trae_la_tablatura_entera_aunque_sea_larga(
        servidor_andando, carpeta_de_frases):
    """
    Antes iban 16 notas y un "…". Una frase de Lean de 23 notas se cortaba
    a la mitad y no habia forma de leerla desde la lista, que es justo donde
    uno la busca.
    """
    tabs = ["-2", "4", "-4", "-5", "6", "-6", "6", "-5"] * 5     # 40 notas
    frases.guardar(frases.desde_eventos(eventos_de(tabs), "larga", "C", 12, "blues"))

    frase = traer_json(servidor_andando, "/api/frases")["frases"][0]

    assert frase["notas"] == 40
    assert frase["tab"] == tabs


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
# El camino de las grabaciones del profe y de los audios que Bruno ya tiene
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

        # Con un microfono de verdad, que se acaben las ventanas significa que
        # dejo de entregar audio, y `escuchar` lo REABRE. Con este falso eso
        # seria un bucle infinito: cortamos aca.
        detener.set()

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


def test_los_archivos_de_la_pagina_no_se_cachean(servidor_andando):
    """
    UN ERROR QUE NO SE VE Y CONFUNDE MUCHISIMO.

    Las respuestas JSON ya decian no-store, pero index.html, app.js y
    estilo.css los servia SimpleHTTPRequestHandler, que solo manda
    Last-Modified. Sin Cache-Control, el navegador aplica cache HEURISTICA: se
    guarda el archivo y durante horas ni pregunta si cambio.

    El resultado: actualizas la app, la abris, y seguis usando la version
    anterior sin ninguna senal de que eso esta pasando. Botones nuevos que no
    aparecen, botones viejos que "no hacen nada".
    """
    for archivo in ("/", "/app.js", "/estilo.css"):
        with urllib.request.urlopen(servidor_andando + archivo, timeout=5) as r:
            cache = r.headers.get("Cache-Control", "")
        assert "no-store" in cache, f"{archivo} se puede cachear: {cache!r}"


def test_las_respuestas_json_tampoco_se_cachean(servidor_andando):
    with urllib.request.urlopen(servidor_andando + "/api/inicio", timeout=5) as r:
        assert "no-store" in r.headers.get("Cache-Control", "")
        # Y una sola vez: la cabecera no se manda duplicada.
        assert len(r.headers.get_all("Cache-Control") or []) == 1


def test_si_el_microfono_se_cae_se_vuelve_a_abrir():
    """
    EL ERROR MAS DIFICIL DE VER DE TODOS.

    captura.ventanas() TERMINA cuando el microfono deja de entregar audio por
    unos segundos. Eso existe para que una sesion con el microfono
    desconectado no se cuelgue, y esta bien.

    Pero con el microfono prendido todo el tiempo, que el hilo termine ahi
    deja la app sorda para siempre y SIN NINGUN ERROR QUE MOSTRAR: escuchando
    en false y error_de_audio vacio. Aparecio asi, probando en el navegador.
    """
    from armonica import microfono

    aperturas = []
    detener = threading.Event()

    def abrir(**kwargs):
        aperturas.append(1)
        if len(aperturas) >= 3:
            detener.set()
        return CapturaFalsa(ventanas_de_silencio(3))

    estado = servidor.EstadoCompartido("C")
    anterior = microfono.CapturaMicrofono
    servidor.ESPERA_ENTRE_INTENTOS = 0.0
    microfono.CapturaMicrofono = abrir
    try:
        servidor.escuchar(estado, detener)
    finally:
        microfono.CapturaMicrofono = anterior
        servidor.ESPERA_ENTRE_INTENTOS = 0.5

    assert len(aperturas) == 3, "tendria que haber reabierto el microfono"
    assert estado.error_de_audio == ""      # agotarse no es un error


def test_si_el_microfono_falla_siempre_se_rinde_y_lo_dice():
    """
    Reintentar para siempre seria peor: la app giraria en silencio.

    Despues de unos intentos se rinde y deja un motivo en el estado, que es lo
    que la pantalla muestra arriba de la barra de nivel.
    """
    from armonica import microfono

    intentos = []

    def abrir_rompiendo(**kwargs):
        intentos.append(1)
        raise OSError("el microfono esta ocupado por otro programa")

    estado = servidor.EstadoCompartido("C")
    anterior = microfono.CapturaMicrofono
    servidor.ESPERA_ENTRE_INTENTOS = 0.0
    microfono.CapturaMicrofono = abrir_rompiendo
    try:
        servidor.escuchar(estado, threading.Event())
    finally:
        microfono.CapturaMicrofono = anterior
        servidor.ESPERA_ENTRE_INTENTOS = 0.5

    assert len(intentos) == servidor.INTENTOS_DE_MICROFONO
    assert "ocupado" in estado.error_de_audio
    assert estado.escuchando is False


# =============================================================================
# Grabar o importar deja una frase PENDIENTE; el nombre se pone al guardar
#
# Antes habia que escribir el nombre antes de grabar, y al terminar se
# guardaba sola. No sabias que iba a salir hasta tocarlo, y lo unico que
# confirmaba el guardado era una linea de texto: la primera frase de Bruno se
# perdio sin que se diera cuenta. Ahora al terminar ves lo que salio y ahi
# decidis.
# =============================================================================

def importar_y_guardar(base, nombre, datos, **extras):
    """El camino completo de importar, en dos pasos, como lo hace la web."""
    previa = subir(base, "/api/frases/importar", "", datos, **extras)
    assert previa["ok"] is True, previa
    guardada = mandar(base, "/api/frases/guardar", {"nombre": nombre})
    assert guardada["ok"] is True, guardada
    return previa, guardada


def test_grabar_una_frase_ya_no_pide_nombre(servidor_andando):
    """El nombre va despues, cuando viste lo que salio."""
    respuesta = mandar(servidor_andando, "/api/comenzar", {"modo": "frase"})

    assert respuesta["ok"] is True
    assert servidor.Manejador.estado.grabando is True
    servidor.Manejador.estado.reiniciar()


def test_practicar_si_pide_nombre(servidor_andando):
    """Para practicar hay que saber contra cual: ahi el nombre sigue yendo antes."""
    respuesta = mandar(servidor_andando, "/api/comenzar", {"modo": "practicar"})
    assert respuesta["ok"] is False
    assert "nombre" in respuesta["motivo"]


def test_terminar_grabando_no_guarda_deja_pendiente(servidor_andando,
                                                    carpeta_de_frases):
    preparar("frase", "", eventos_de(["-2", "-3''", "4", "-4"]))

    respuesta = mandar(servidor_andando, "/api/terminar")

    assert respuesta["ok"] is True
    assert respuesta["modo"] == "frase"
    pendiente = respuesta["pendiente"]
    assert pendiente["notas"] == 4
    assert pendiente["tab"] == ["-2", "-3''", "4", "-4"]
    assert pendiente["origen"] == "microfono"
    assert frases.listar() == []                     # todavia no hay nada


def test_terminar_sin_notas_no_deja_pendiente(servidor_andando, carpeta_de_frases):
    preparar("frase", "", [])

    respuesta = mandar(servidor_andando, "/api/terminar")

    assert respuesta["ok"] is False
    assert "ninguna nota" in respuesta["motivo"]
    assert traer_json(servidor_andando, "/api/frases/pendiente")["pendiente"] is None


def test_guardar_la_pendiente_con_nombre_descripcion_y_lista(servidor_andando,
                                                             carpeta_de_frases):
    preparar("frase", "", eventos_de(["-2", "-3''", "4"]))
    mandar(servidor_andando, "/api/terminar")

    respuesta = mandar(servidor_andando, "/api/frases/guardar", {
        "nombre": "turnaround de la clase",
        "comentario": "el que cierra la vuelta, con el bend del 3",
        "lista": "turnarounds",
    })

    assert respuesta["ok"] is True
    assert respuesta["frase"]["nombre"] == "turnaround de la clase"
    assert respuesta["frase"]["lista"] == "turnarounds"

    guardada = frases.buscar("turnaround de la clase")
    assert guardada.cantidad == 3
    assert guardada.comentario == "el que cierra la vuelta, con el bend del 3"
    assert guardada.lista == "turnarounds"

    # La lista se creo sola: elegirla ya es querer que exista.
    assert [l["nombre"] for l in frases.listar_listas()] == ["turnarounds"]

    # Y la pendiente se consumio.
    assert traer_json(servidor_andando, "/api/frases/pendiente")["pendiente"] is None


def test_guardar_sin_nombre_se_rechaza(servidor_andando, carpeta_de_frases):
    preparar("frase", "", eventos_de(["4", "-4"]))
    mandar(servidor_andando, "/api/terminar")

    respuesta = mandar(servidor_andando, "/api/frases/guardar", {"nombre": "  "})

    assert respuesta["ok"] is False
    assert "nombre" in respuesta["motivo"]
    assert frases.listar() == []
    # La pendiente sigue ahi: no se pierde por un nombre vacio.
    assert traer_json(servidor_andando, "/api/frases/pendiente")["pendiente"] is not None


def test_guardar_sin_nada_pendiente(servidor_andando, carpeta_de_frases):
    respuesta = mandar(servidor_andando, "/api/frases/guardar", {"nombre": "x"})
    assert respuesta["ok"] is False


def test_descartar_la_pendiente(servidor_andando, carpeta_de_frases):
    preparar("frase", "", eventos_de(["4", "-4"]))
    mandar(servidor_andando, "/api/terminar")

    mandar(servidor_andando, "/api/frases/descartar")

    assert traer_json(servidor_andando, "/api/frases/pendiente")["pendiente"] is None
    assert frases.listar() == []


def test_un_nombre_repetido_no_pisa_la_frase_que_habia(servidor_andando,
                                                       carpeta_de_frases):
    """
    Pisar seria perder una grabacion por un nombre repetido, y las frases del
    profe no se pueden volver a grabar. Se avisa, y si queres pisarla lo
    decis explicitamente.
    """
    frases.guardar(frases.desde_eventos(eventos_de(["4", "-4"]), "la misma"))

    preparar("frase", "", eventos_de(["-2", "-3''", "4"]))
    mandar(servidor_andando, "/api/terminar")

    respuesta = mandar(servidor_andando, "/api/frases/guardar", {"nombre": "la misma"})
    assert respuesta["ok"] is False
    assert respuesta["repetida"] is True
    assert frases.buscar("la misma").cantidad == 2          # intacta

    respuesta = mandar(servidor_andando, "/api/frases/guardar",
                       {"nombre": "la misma", "reemplazar": True})
    assert respuesta["ok"] is True
    assert frases.buscar("la misma").cantidad == 3


def test_la_pendiente_se_puede_volver_a_pedir(servidor_andando, carpeta_de_frases):
    """Si recargas la pagina antes de guardar, lo grabado no se perdio."""
    preparar("frase", "", eventos_de(["4", "-4", "-5"]))
    mandar(servidor_andando, "/api/terminar")

    datos = traer_json(servidor_andando, "/api/frases/pendiente")

    assert datos["pendiente"]["tab"] == ["4", "-4", "-5"]


# --- Importar sigue el mismo camino -----------------------------------------

def test_importar_deja_pendiente_y_no_guarda(servidor_andando, carpeta_de_frases):
    respuesta = subir(servidor_andando, "/api/frases/importar", "",
                      wav_de(["-2", "4", "-4", "-5"]), archivo="lick_de_lean.wav")

    assert respuesta["ok"] is True
    pendiente = respuesta["pendiente"]
    assert pendiente["notas"] == 4
    assert pendiente["tab"] == ["-2", "4", "-4", "-5"]
    assert pendiente["origen"] == "archivo"
    assert pendiente["nombre_sugerido"] == "lick_de_lean"
    assert pendiente["sirve"] is True
    assert frases.listar() == []


def test_importar_y_guardar_deja_el_audio_al_lado(servidor_andando,
                                                  carpeta_de_frases):
    """
    Una frase del profe se lee, pero sobre todo se ESCUCHA.

    Sin el audio guardado, la referencia se degrada a una tablatura y perdes
    justo el ritmo, que es lo unico que la tablatura no sabe transmitir.
    """
    importar_y_guardar(servidor_andando, "con audio", wav_de(["4", "-4", "-5"]))

    guardados = sorted(os.listdir(carpeta_de_frases))
    assert "con_audio.json" in guardados
    assert "con_audio_audio.wav" in guardados


def test_un_audio_con_banda_no_deja_nada_que_guardar(servidor_andando,
                                                     carpeta_de_frases):
    """
    EL CONTROL QUE MAS IMPORTA DE TODA LA SOLAPA.

    Con una banda atras el detector no reconoce ni una nota: no hay tablatura
    que mostrar ni nada que decidir. Y el motivo tiene que ser ESE, no un
    generico "ninguna nota": la revision va antes de contar.
    """
    respuesta = subir(servidor_andando, "/api/frases/importar", "",
                      wav_polifonico())

    assert respuesta["ok"] is False
    assert "monofon" in respuesta["motivo"]
    assert traer_json(servidor_andando, "/api/frases/pendiente")["pendiente"] is None


def test_un_audio_mudo_no_deja_nada_que_guardar(servidor_andando, carpeta_de_frases):
    import numpy

    mudo = bytes_de_wav(numpy.zeros(44100, dtype=numpy.float32))
    respuesta = subir(servidor_andando, "/api/frases/importar", "", mudo)

    assert respuesta["ok"] is False
    assert traer_json(servidor_andando, "/api/frases/pendiente")["pendiente"] is None


def test_cuando_el_control_duda_igual_se_ve_la_tablatura(
        servidor_andando, carpeta_de_frases, umbral_imposible):
    """
    El umbral de monofonia es una heuristica, no una ley.

    Antes se rechazaba y habia un parametro para forzar. Ahora la vista previa
    muestra la tablatura Y el motivo, y el que decide sos vos, mirando. Si la
    guardas, queda dicho que fue saltando el control.
    """
    respuesta = subir(servidor_andando, "/api/frases/importar", "",
                      wav_de(["-2", "4", "-4"]))

    assert respuesta["ok"] is True
    pendiente = respuesta["pendiente"]
    assert pendiente["sirve"] is False
    assert pendiente["motivo"]
    assert pendiente["tab"] == ["-2", "4", "-4"]
    assert frases.listar() == []

    guardada = mandar(servidor_andando, "/api/frases/guardar", {"nombre": "dudosa"})
    assert guardada["ok"] is True
    assert any("salteando" in aviso for aviso in guardada["avisos"])
    assert frases.buscar("dudosa") is not None


def test_importar_usa_la_armonica_que_le_decis(servidor_andando, carpeta_de_frases):
    """
    El mismo audio, importado como armonica en Do y como armonica en La.

    Son dos tablaturas distintas para el mismo sonido, y las dos son correctas
    segun con que armonica se haya tocado. Este dato lo pone el que sube el
    archivo porque es el unico que lo sabe.
    """
    audio_grabado = wav_de(["4", "-4", "-5"])

    como_do, _ = importar_y_guardar(servidor_andando, "en do", audio_grabado,
                                    tonalidad="C")
    como_la, _ = importar_y_guardar(servidor_andando, "en la", audio_grabado,
                                    tonalidad="A")

    assert como_do["pendiente"]["tonalidad"] == "C"
    assert como_la["pendiente"]["tonalidad"] == "A"
    assert como_do["pendiente"]["tab"] != como_la["pendiente"]["tab"]
    assert frases.buscar("en la").tonalidad == "A"


def test_sin_decir_nada_se_usa_la_armonica_de_la_sesion(servidor_andando,
                                                        carpeta_de_frases):
    respuesta = subir(servidor_andando, "/api/frases/importar", "",
                      wav_de(["4", "-4"]))
    assert respuesta["pendiente"]["tonalidad"] == "C"


def test_comparar_un_wav_contra_una_frase_guardada(servidor_andando,
                                                   carpeta_de_frases):
    """
    El intento tambien puede venir de un archivo.

    Sirve cuando ya grabaste con la grabadora de Windows, y para comparar dos
    audios viejos sin volver a tocar.
    """
    importar_y_guardar(servidor_andando, "escala corta",
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


def test_un_intento_sin_decir_contra_que_frase(servidor_andando, carpeta_de_frases):
    respuesta = subir(servidor_andando, "/api/frases/intento", "",
                      wav_de(["4", "-4"]))
    assert respuesta["ok"] is False


def test_la_vista_previa_del_tramo_es_lo_que_se_va_a_guardar(
        servidor_andando, carpeta_de_frases):
    """
    El tab que muestra la lista de tramos sale del MISMO recorte que se usa
    al importar. Si mostraramos el tab del analisis del archivo entero,
    elegirias mirando una cosa y se guardaria otra: la grilla de ventanas
    arranca en otro lado al recortar y cambia una nota o dos.
    """
    datos = clase_de_prueba([["-2", "4", "-4"], ["-5", "6", "-6"]])

    lista = subir(servidor_andando, "/api/frases/tramos", "", datos)
    segundo = lista["tramos"][1]

    previa = subir(servidor_andando, "/api/frases/importar", "", datos,
                   desde=segundo["desde_seg"], hasta=segundo["hasta_seg"])
    assert previa["pendiente"]["tab"] == segundo["tab"]

    guardada = mandar(servidor_andando, "/api/frases/guardar", {"nombre": "el segundo"})
    assert guardada["frase"]["tab"] == segundo["tab"]


def test_importar_un_tramo_guarda_solo_ese_pedazo(servidor_andando,
                                                  carpeta_de_frases):
    datos = clase_de_prueba([["-2", "4", "-4"], ["-5", "6", "-6"]])
    lista = subir(servidor_andando, "/api/frases/tramos", "", datos)
    segundo = lista["tramos"][1]

    subir(servidor_andando, "/api/frases/importar", "", datos,
          desde=segundo["desde_seg"], hasta=segundo["hasta_seg"])
    mandar(servidor_andando, "/api/frases/guardar", {"nombre": "solo el segundo"})

    frase = frases.buscar("solo el segundo")
    assert frase.tablatura() == ["-5", "6", "-6"]
    # Y los tiempos arrancan en cero, no en el segundo 4 del archivo original.
    assert frase.notas[0].inicio_seg < 0.01


def test_importar_un_pedazo_sin_notas_avisa(servidor_andando, carpeta_de_frases):
    datos = clase_de_prueba([["-2", "4", "-4"], ["-5", "6", "-6"]])

    respuesta = subir(servidor_andando, "/api/frases/importar", "", datos,
                      desde=2.4, hasta=2.9)

    assert respuesta["ok"] is False
    assert "no hay notas" in respuesta["motivo"]


def test_sin_recorte_se_importa_el_audio_entero(servidor_andando, carpeta_de_frases):
    datos = clase_de_prueba([["-2", "4", "-4"], ["-5", "6", "-6"]])
    respuesta = subir(servidor_andando, "/api/frases/importar", "", datos)
    assert respuesta["pendiente"]["notas"] == 6


def test_el_audio_de_una_frase_se_puede_bajar(servidor_andando, carpeta_de_frases):
    importar_y_guardar(servidor_andando, "para escuchar", wav_de(["-2", "4", "-4"]))

    codigo, cuerpo = traer(servidor_andando, "/api/frases/audio?nombre=para%20escuchar")

    assert codigo == 200
    assert cuerpo[:4] == b"RIFF"
    assert len(cuerpo) > 1000


def test_la_lista_dice_cuales_frases_tienen_audio(servidor_andando, carpeta_de_frases):
    importar_y_guardar(servidor_andando, "con audio", wav_de(["-2", "4", "-4"]))
    datos = traer_json(servidor_andando, "/api/frases")
    assert datos["frases"][0]["hay_audio"] is True


def test_borrar_una_frase_borra_tambien_su_audio(servidor_andando, carpeta_de_frases):
    importar_y_guardar(servidor_andando, "efimera", wav_de(["4", "-4"]))
    assert "efimera_audio.wav" in os.listdir(carpeta_de_frases)

    mandar(servidor_andando, "/api/frases/borrar", {"nombre": "efimera"})

    assert "efimera_audio.wav" not in os.listdir(carpeta_de_frases)


# =============================================================================
# Las listas de reproduccion
# =============================================================================

def frase_de_prueba(nombre, lista=""):
    return frases.guardar(frases.desde_eventos(
        eventos_de(["4", "-4"]), nombre, lista=lista))


def test_una_lista_se_puede_crear_vacia(servidor_andando, carpeta_de_frases):
    """
    Es la diferencia con las "bolsas" que hubo un dia: una lista existe
    aunque no tenga frases. Podes crear "clase del martes" antes de grabar la
    primera.
    """
    respuesta = mandar(servidor_andando, "/api/listas/crear",
                       {"nombre": "  clase del   martes "})

    assert respuesta["ok"] is True
    assert respuesta["nombre"] == "clase del martes"
    assert respuesta["listas"] == [{"nombre": "clase del martes", "frases": 0}]


def test_la_lista_de_frases_trae_las_listas_con_su_cuenta(servidor_andando,
                                                          carpeta_de_frases):
    frase_de_prueba("una", "turnarounds")
    frase_de_prueba("dos", "turnarounds")
    frase_de_prueba("tres", "para calentar")
    frase_de_prueba("cuatro")

    datos = traer_json(servidor_andando, "/api/frases")

    assert len(datos["frases"]) == 4
    # Ordenadas por nombre cuando no estan en el archivo de listas.
    assert datos["listas"] == [{"nombre": "para calentar", "frases": 1},
                               {"nombre": "turnarounds", "frases": 2}]
    assert [f for f in datos["frases"] if not f["lista"]][0]["nombre"] == "cuatro"


def test_las_listas_del_archivo_van_primero_en_su_orden(servidor_andando,
                                                        carpeta_de_frases):
    mandar(servidor_andando, "/api/listas/crear", {"nombre": "zeta"})
    mandar(servidor_andando, "/api/listas/crear", {"nombre": "alfa"})
    frase_de_prueba("suelta", "por la terminal")

    listas = traer_json(servidor_andando, "/api/listas")["listas"]

    assert [l["nombre"] for l in listas] == ["zeta", "alfa", "por la terminal"]


def test_mandar_varias_frases_a_una_lista_de_una_vez(servidor_andando,
                                                     carpeta_de_frases):
    """Marcas cinco frases del mismo tema y las mandas juntas."""
    for nombre in ("una", "dos", "tres"):
        frase_de_prueba(nombre)

    respuesta = mandar(servidor_andando, "/api/frases/lista",
                       {"nombres": ["una", "tres"], "lista": "turnarounds"})

    assert respuesta["ok"] is True
    assert respuesta["movidas"] == 2
    assert frases.buscar("una").lista == "turnarounds"
    assert frases.buscar("dos").lista == ""
    assert frases.buscar("tres").lista == "turnarounds"


def test_sacar_una_frase_de_su_lista(servidor_andando, carpeta_de_frases):
    frase_de_prueba("una", "turnarounds")
    mandar(servidor_andando, "/api/frases/lista", {"nombres": ["una"], "lista": ""})
    assert frases.buscar("una").lista == ""


def test_renombrar_una_lista_arrastra_sus_frases(servidor_andando,
                                                 carpeta_de_frases):
    frase_de_prueba("una", "turnaround")
    frase_de_prueba("dos", "turnaround")
    frase_de_prueba("tres", "otra")

    respuesta = mandar(servidor_andando, "/api/listas/renombrar",
                       {"viejo": "turnaround", "nuevo": "turnarounds"})

    assert respuesta["ok"] is True
    assert respuesta["movidas"] == 2
    assert frases.buscar("una").lista == "turnarounds"
    assert frases.buscar("tres").lista == "otra"
    assert "turnaround" not in [l["nombre"] for l in frases.listar_listas()]


def test_borrar_una_lista_no_borra_sus_frases(servidor_andando, carpeta_de_frases):
    """Borrar una lista es ordenar, y ordenar no puede hacer desaparecer una grabacion."""
    frase_de_prueba("una", "efimera")
    frase_de_prueba("dos", "efimera")

    respuesta = mandar(servidor_andando, "/api/listas/borrar", {"nombre": "efimera"})

    assert respuesta["ok"] is True
    assert respuesta["sacadas"] == 2
    assert frases.buscar("una") is not None
    assert frases.buscar("una").lista == ""
    assert frases.listar_listas() == []


def test_la_lista_sobrevive_a_guardar_y_volver_a_leer(tmp_path):
    frase = frases.desde_eventos(eventos_de(["4"]), "una", comentario="algo",
                                 lista="turnarounds")
    leida = frases.cargar(frases.guardar(frase, str(tmp_path)))
    assert leida.lista == "turnarounds"
    assert leida.comentario == "algo"


def test_una_frase_guardada_con_bolsa_se_lee_como_lista(tmp_path):
    """"bolsa" fue el nombre del campo durante un dia. Lo que se guardo asi no se pierde."""
    import json as modulo_json

    ruta = tmp_path / "vieja.json"
    ruta.write_text(modulo_json.dumps({
        "version": 1, "nombre": "vieja", "tonalidad": "C", "bolsa": "turnarounds",
        "notas": [{"tab": "4", "inicio_seg": 0.0, "duracion_seg": 0.3}],
    }), encoding="utf-8")

    assert frases.cargar(str(ruta)).lista == "turnarounds"


def test_el_archivo_de_listas_no_se_confunde_con_una_frase(carpeta_de_frases):
    """_listas.json vive en la misma carpeta y NO es una frase."""
    frases.crear_lista("turnarounds")
    frase_de_prueba("una")

    assert [nombre for nombre, _ in frases.listar()] == ["una"]


# =============================================================================
# Fase 2: la sesion tambien queda pendiente, y el BPM enciende el ritmo
#
# ritmo.py existe desde el paso 6 y la pantalla nunca lo pudo usar: solo la
# terminal, con --bpm. La pregunta "sobre que base estabas" se hace donde tiene
# sentido, despues de tocar. Si contestas, se mide; si no, no se inventa nada.
# =============================================================================

def eventos_metricos(tabs, bpm, subdivision=2, desvio_ms=0.0):
    """Notas que caen EXACTAMENTE sobre la grilla de un BPM, mas un desvio fijo."""
    paso = 60.0 / bpm / subdivision
    return [
        segmentacion.Evento(
            nota=mapeo.tab_a_nota(tab, "C"),
            inicio_seg=0.5 + i * paso + desvio_ms / 1000.0,
            duracion_seg=paso * 0.8, frecuencia_hz=440.0, cents=0.0,
            confianza=0.95, ventanas=20,
        )
        for i, tab in enumerate(tabs)
    ]


def terminar_sesion_con(base, eventos):
    """Deja una sesion pendiente con esas notas, como si las hubieras tocado."""
    preparar("sesion", "", eventos)
    return mandar(base, "/api/terminar")


def test_terminar_una_sesion_no_guarda_deja_pendiente(servidor_andando, tmp_path,
                                                      monkeypatch):
    monkeypatch.setattr(exportacion, "CARPETA_POR_DEFECTO", str(tmp_path))

    respuesta = terminar_sesion_con(servidor_andando, eventos_de(["-2", "4", "-4"]))

    assert respuesta["ok"] is True
    assert respuesta["modo"] == "sesion"
    assert respuesta["pendiente"]["notas"] == 3
    assert respuesta["pendiente"]["tab"] == ["-2", "4", "-4"]
    assert os.listdir(str(tmp_path)) == []                   # nada en el disco


def test_terminar_una_sesion_sin_notas_no_deja_pendiente(servidor_andando):
    respuesta = terminar_sesion_con(servidor_andando, [])
    assert respuesta["ok"] is False
    assert traer_json(servidor_andando, "/api/sesiones/pendiente")["pendiente"] is None


def test_guardar_la_sesion_con_titulo_y_descripcion(servidor_andando, tmp_path,
                                                    monkeypatch):
    """
    Sin esto, dentro de un mes tenes doce carpetas con fecha y hora y ninguna
    forma de saber cual era la que valia la pena. El titulo va DESPUES de la
    fecha en el nombre del archivo: los archivos se siguen ordenando solos.
    """
    monkeypatch.setattr(exportacion, "CARPETA_POR_DEFECTO", str(tmp_path))
    terminar_sesion_con(servidor_andando, eventos_de(["-2", "4", "-4", "-5"]))

    respuesta = mandar(servidor_andando, "/api/sesiones/guardar", {
        "titulo": "Escala 12a ida y vuelta",
        "comentario": "probando el bend del 3 sobre la base de Sol",
    })

    assert respuesta["ok"] is True
    assert respuesta["ritmo"] is None                        # sin BPM no se inventa
    assert respuesta["resumen"]["notas"] == 4

    guardados = sorted(os.listdir(str(tmp_path)))
    assert any("_escala-12a-ida-y-vuelta_tab.txt" in n for n in guardados)
    tab = next(n for n in guardados if n.endswith("_tab.txt"))
    with open(os.path.join(str(tmp_path), tab), encoding="utf-8") as archivo:
        texto = archivo.read()
    assert "Escala 12a ida y vuelta" in texto
    assert "probando el bend del 3" in texto

    # Y la pendiente se consumio.
    assert traer_json(servidor_andando, "/api/sesiones/pendiente")["pendiente"] is None


def test_una_sesion_sin_titulo_se_guarda_igual(servidor_andando, tmp_path,
                                               monkeypatch):
    """Los campos son opcionales: no pueden frenarte cuando queres guardar y ya."""
    monkeypatch.setattr(exportacion, "CARPETA_POR_DEFECTO", str(tmp_path))
    terminar_sesion_con(servidor_andando, eventos_de(["4", "-4"]))

    respuesta = mandar(servidor_andando, "/api/sesiones/guardar", {})

    assert respuesta["ok"] is True
    assert any(n.endswith("_tab.txt") for n in os.listdir(str(tmp_path)))


def test_guardar_sin_nada_pendiente(servidor_andando):
    respuesta = mandar(servidor_andando, "/api/sesiones/guardar", {"titulo": "x"})
    assert respuesta["ok"] is False


def test_descartar_la_sesion(servidor_andando, tmp_path, monkeypatch):
    monkeypatch.setattr(exportacion, "CARPETA_POR_DEFECTO", str(tmp_path))
    terminar_sesion_con(servidor_andando, eventos_de(["4", "-4"]))

    mandar(servidor_andando, "/api/sesiones/descartar")

    assert traer_json(servidor_andando, "/api/sesiones/pendiente")["pendiente"] is None
    assert os.listdir(str(tmp_path)) == []


def test_con_bpm_se_mide_el_ritmo(servidor_andando, tmp_path, monkeypatch):
    """
    LO QUE ENCIENDE ESTA FASE.

    Notas que caen exactamente sobre la grilla de 80 BPM en corcheas, todas
    12 ms tarde. Dispersion cero y la grilla explica lo tocado.

    Y el promedio da CERO, no 12, a proposito: el analisis busca la grilla
    que mejor explica lo que tocaste, asi que un atraso constante no es un
    desvio, es donde esta tu grilla. Lo que se mide es cuanto te moves
    respecto de vos mismo. Fue una premisa equivocada del primer test.
    """
    monkeypatch.setattr(exportacion, "CARPETA_POR_DEFECTO", str(tmp_path))
    terminar_sesion_con(servidor_andando, eventos_metricos(
        ["-2", "4", "-4", "-5", "6", "-6", "6", "-5"], bpm=80, desvio_ms=12))

    respuesta = mandar(servidor_andando, "/api/sesiones/guardar",
                       {"bpm": 80, "subdivision": 2})

    assert respuesta["ok"] is True
    ritmo_web = respuesta["ritmo"]
    assert ritmo_web["bpm"] == 80
    assert ritmo_web["figura"] == "corcheas"
    assert ritmo_web["notas_medidas"] == 8
    assert ritmo_web["dispersion_ms"] == 0
    assert ritmo_web["sesgo_ms"] == 0
    assert ritmo_web["confiable"] is True
    assert ritmo_web["a_tiempo_pct"] == 100

    # Y el analisis quedo en el JSON de la sesion, para comparar despues.
    import json as modulo_json
    eventos_json = next(n for n in os.listdir(str(tmp_path)) if n.endswith("_eventos.json"))
    with open(os.path.join(str(tmp_path), eventos_json), encoding="utf-8") as archivo:
        datos = modulo_json.load(archivo)
    assert datos["ritmo"] is not None


def test_si_la_grilla_no_explica_lo_tocado_no_hay_diagnostico(servidor_andando,
                                                              tmp_path, monkeypatch):
    """
    EL CONTROL DE HONESTIDAD DEL RITMO, EN LA PANTALLA.

    Las mismas notas medidas contra un BPM que no tiene nada que ver: la
    dispersion da un numero, pero `confiable` dice que no explica nada y el
    diagnostico va vacio. Sin esto la pantalla mostraria "dispersion 63 ms"
    con toda seriedad sobre una medicion sin sentido.
    """
    monkeypatch.setattr(exportacion, "CARPETA_POR_DEFECTO", str(tmp_path))
    import random
    azar = random.Random(7)
    sueltos = [
        segmentacion.Evento(
            nota=mapeo.tab_a_nota(tab, "C"), inicio_seg=0.5 + i * 0.4 + azar.uniform(-0.2, 0.2),
            duracion_seg=0.2, frecuencia_hz=440.0, cents=0.0, confianza=0.9, ventanas=15)
        for i, tab in enumerate(["-2", "4", "-4", "-5", "6", "-6", "6", "-5", "4", "-4", "-2", "4"])
    ]
    terminar_sesion_con(servidor_andando, sueltos)

    respuesta = mandar(servidor_andando, "/api/sesiones/guardar",
                       {"bpm": 173, "subdivision": 4})

    ritmo_web = respuesta["ritmo"]
    assert ritmo_web["confiable"] is False
    assert ritmo_web["diagnostico"] == []
    assert ritmo_web["ajuste_vs_azar"] is not None


def test_sin_bpm_no_hay_bloque_de_ritmo(servidor_andando, tmp_path, monkeypatch):
    monkeypatch.setattr(exportacion, "CARPETA_POR_DEFECTO", str(tmp_path))
    terminar_sesion_con(servidor_andando, eventos_metricos(["-2", "4", "-4", "-5"], bpm=80))

    respuesta = mandar(servidor_andando, "/api/sesiones/guardar", {"bpm": None})

    assert respuesta["ok"] is True
    assert respuesta["ritmo"] is None


def test_la_subdivision_por_defecto_viaja_al_navegador(servidor_andando):
    datos = traer_json(servidor_andando, "/api/inicio")
    assert datos["subdivision_ritmo"] == config.SUBDIVISION_RITMO


def test_el_historial_trae_el_titulo_de_cada_sesion(tmp_path):
    exportacion.guardar_sesion(eventos_de(["4", "-4"]), carpeta=str(tmp_path),
                               titulo="Bloque T2")
    exportacion.guardar_sesion(eventos_de(["4", "-4"]), carpeta=str(tmp_path))

    sesiones = servidor.historial(str(tmp_path))["sesiones"]

    assert sorted(s["titulo"] for s in sesiones) == ["", "Bloque T2"]


# =============================================================================
# La devolucion y el audio del intento, desde la pantalla
# =============================================================================

def test_la_comparacion_trae_la_devolucion(servidor_andando, carpeta_de_frases):
    frases.guardar(frases.desde_eventos(
        eventos_de(["-2", "-3''", "4", "-4"]), "con devolucion", "C", 2, None))
    preparar("practicar", "con devolucion", eventos_de(["-2", "-3''", "4", "-4"]))

    comparacion = mandar(servidor_andando, "/api/terminar")["comparacion"]

    devolucion = comparacion["devolucion"]
    assert devolucion["notas"]["porcentaje"] == 100
    assert devolucion["consejos"]
    assert comparacion["referencia_con_audio"] is False    # se guardo sin audio
    assert comparacion["intento_con_audio"] is False        # y se practico sin microfono


def test_el_audio_del_intento_se_puede_escuchar(servidor_andando, carpeta_de_frases):
    """
    Lo que tocaste al practicar queda en memoria para escucharlo al lado de
    la referencia. Es la unica forma de OIR la diferencia de ritmo que los
    numeros describen.
    """
    frases.guardar(frases.desde_eventos(eventos_de(["-2", "4", "-4"]), "para oir"))
    estado = preparar("practicar", "para oir", eventos_de(["-2", "4", "-4"]))
    estado.audio_grabado = generar_wav.generar_nota(440.0, 0.5, 44100)
    estado.frecuencia_muestreo = 44100

    comparacion = mandar(servidor_andando, "/api/terminar")["comparacion"]
    assert comparacion["intento_con_audio"] is True

    codigo, cuerpo = traer(servidor_andando, "/api/frases/intento/audio")
    assert codigo == 200
    assert cuerpo[:4] == b"RIFF"
    assert len(cuerpo) > 44 + 44100 * 0.5 * 2 - 10       # medio segundo de 16 bits


def test_sin_intento_el_audio_da_404(servidor_andando):
    servidor.Manejador.ultimo_intento = None
    with pytest.raises(urllib.error.HTTPError) as error:
        traer(servidor_andando, "/api/frases/intento/audio")
    assert error.value.code == 404
