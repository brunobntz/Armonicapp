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


def test_los_datos_iniciales_traen_el_diagrama(servidor_andando):
    datos = traer_json(servidor_andando, "/api/inicio")
    diagrama = datos["diagrama"]

    assert len(diagrama) >= 3          # soplado, aspirado y al menos un bend
    for fila in diagrama:
        assert len(fila["celdas"]) == 10


def test_el_diagrama_marca_los_agujeros_de_la_escala(servidor_andando):
    """
    Es lo que se pinta de verde en la pantalla. Sin esto, el diagrama sería
    solo un mapa y no una ayuda.
    """
    datos = traer_json(servidor_andando, "/api/inicio")
    en_escala = [
        celda for fila in datos["diagrama"] for celda in fila["celdas"]
        if celda and celda["en_escala"]
    ]
    assert len(en_escala) > 10


def test_el_diagrama_deja_huecos_donde_no_hay_nota():
    """El agujero 5 no tiene bend, y ahí la celda va vacía."""
    filas = servidor.diagrama_de_la_armonica("C")
    fila_de_bends = next(f for f in filas if f["etiqueta"] == "bend")
    assert fila_de_bends["celdas"][4] is None      # el agujero 5


def test_el_diagrama_funciona_sin_escala_de_referencia():
    filas = servidor.diagrama_de_la_armonica("C")
    assert filas
    assert not any(celda["en_escala"]
                   for fila in filas for celda in fila["celdas"] if celda)


def test_el_diagrama_funciona_con_otra_armonica():
    filas = servidor.diagrama_de_la_armonica("G", 2, "blues")
    primera = filas[0]["celdas"][0]
    assert primera["nombre"] == "G3"


# =============================================================================
# El estado en vivo
# =============================================================================

def test_el_estado_arranca_vacio():
    estado = servidor.EstadoCompartido("C", 12, "blues_mayor")
    datos = estado.como_diccionario()

    assert datos["escuchando"] is False
    assert datos["nota"] is None
    assert datos["cantidad_notas"] == 0


def test_el_estado_guarda_la_nota_que_llega():
    estado = servidor.EstadoCompartido("C", 12, "blues_mayor")
    nota = mapeo.tab_a_nota("-5", "C")

    estado.actualizar(nota, -8.0, 0.2, 3.5, [])
    datos = estado.como_diccionario()

    assert datos["nota"]["nombre"] == "F5"
    assert datos["cents"] == pytest.approx(-8.0)
    assert datos["segundos"] == pytest.approx(3.5)


def test_el_estado_sostiene_la_nota_cuando_deja_de_llegar():
    """
    Igual que en la terminal: entre nota y nota hay silencio, y sin esto el
    agujero desapareceria en cada respiracion.
    """
    estado = servidor.EstadoCompartido("C")
    estado.actualizar(mapeo.tab_a_nota("-5", "C"), 0.0, 0.2, 1.0, [])
    estado.actualizar(None, 0.0, 0.001, 1.5, [])

    assert estado.como_diccionario()["nota"]["nombre"] == "F5"


def test_el_estado_dice_si_la_nota_esta_en_la_escala():
    estado = servidor.EstadoCompartido("C", 12, "blues_mayor")

    estado.actualizar(mapeo.tab_a_nota("-5", "C"), 0.0, 0.2, 1.0, [])
    assert estado.como_diccionario()["nota"]["en_escala"] is True

    estado.actualizar(mapeo.tab_a_nota("2", "C"), 0.0, 0.2, 2.0, [])
    assert estado.como_diccionario()["nota"]["en_escala"] is False


def test_sin_escala_de_referencia_no_dice_ni_si_ni_no():
    """None, no False: sin escala elegida la pregunta no tiene sentido."""
    estado = servidor.EstadoCompartido("C")
    estado.actualizar(mapeo.tab_a_nota("-5", "C"), 0.0, 0.2, 1.0, [])
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
