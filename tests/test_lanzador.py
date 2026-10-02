"""
Tests de armonica/lanzador.py — abrir la app desde un ícono.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_lanzador.py -v
"""

import os
import socket
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from armonica import lanzador, servidor


def test_los_datos_van_donde_diga_armonica_datos(tmp_path):
    assert lanzador.carpeta_de_datos({"ARMONICA_DATOS": str(tmp_path)}) == str(tmp_path)


def test_una_ruta_relativa_se_vuelve_absoluta(tmp_path, monkeypatch):
    """La app hace os.chdir a la carpeta de datos: una ruta relativa se perdería."""
    monkeypatch.chdir(tmp_path)     # monkeypatch vuelve a la carpeta de antes al final
    assert lanzador.carpeta_de_datos({"ARMONICA_DATOS": "prueba"}) == str(tmp_path / "prueba")


def test_sin_la_variable_van_a_documentos(tmp_path, monkeypatch):
    monkeypatch.setattr(lanzador, "carpeta_de_documentos", lambda: str(tmp_path / "Docs"))
    assert lanzador.carpeta_de_datos({}) == str(tmp_path / "Docs" / "Armonica")


@pytest.mark.skipif(sys.platform != "win32", reason="Documentos se le pregunta a Windows")
def test_windows_dice_donde_esta_documentos():
    assert os.path.isdir(lanzador.carpeta_de_documentos())


def test_preparar_la_carpeta_crea_lo_que_falta(tmp_path):
    lanzador.preparar_carpeta(str(tmp_path))
    for nombre in ("frases", "sesiones", "canciones", "apuntes", "material"):
        assert (tmp_path / nombre).is_dir()


def test_el_registro_largo_se_recorta(tmp_path):
    ruta = tmp_path / "registro.txt"
    ruta.write_bytes(b"a" * 1200 + b"z" * 300)
    lanzador.recortar_registro(str(ruta), maximo=1000, conservar=300)
    assert ruta.read_bytes() == b"z" * 300

    ruta.write_bytes(b"corto")
    lanzador.recortar_registro(str(ruta), maximo=1000, conservar=300)
    assert ruta.read_bytes() == b"corto"


def test_el_entorno_apunta_a_la_carpeta_de_datos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)     # monkeypatch vuelve a esta carpeta al final
    datos = tmp_path / "datos"
    datos.mkdir()
    programa = tmp_path / "programa"
    (programa / "ffmpeg").mkdir(parents=True)
    entorno = {"PATH": "C:\\otro"}

    lanzador.preparar_entorno(str(datos), str(programa), entorno)

    assert os.getcwd() == str(datos)
    assert entorno["CARPETA_CANCIONES"] == os.path.join(str(datos), "canciones")
    assert entorno["CARPETA_CLASES"] == os.path.join(str(datos), "apuntes")
    assert entorno["PATH"] == os.path.join(str(programa), "ffmpeg") + os.pathsep + "C:\\otro"


def test_sin_ffmpeg_al_lado_el_path_no_cambia(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entorno = {"PATH": "C:\\otro"}
    lanzador.preparar_entorno(str(tmp_path), str(tmp_path / "programa"), entorno)
    assert entorno["PATH"] == "C:\\otro"


def test_encuentra_una_app_ya_abierta():
    servidor.Manejador.estado = servidor.EstadoCompartido("C", None, None)
    abierta = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Manejador)
    threading.Thread(target=abierta.serve_forever, daemon=True).start()
    libre = socket.socket()
    libre.bind(("127.0.0.1", 0))
    puerto_libre = libre.getsockname()[1]
    libre.close()
    try:
        puerto = abierta.server_address[1]
        assert lanzador.buscar_instancia([puerto_libre, puerto]) == puerto
        assert lanzador.buscar_instancia([puerto_libre]) is None
    finally:
        abierta.shutdown()
        abierta.server_close()


def _puertos_cerrados(cuantos):
    """Puertos de localhost donde no escucha nadie."""
    sockets = []
    for _ in range(cuantos):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        sockets.append(s)
    puertos = [s.getsockname()[1] for s in sockets]
    for s in sockets:
        s.close()
    return puertos


def test_los_puertos_cerrados_no_suman_espera():
    # En Windows cada puerto cerrado de localhost cuesta todo el timeout: probados
    # uno por uno, los 11 puertos de la app tardan ~5,5 s en cada arranque en frio.
    # Probados a la vez, tarda lo de uno solo.
    puertos = _puertos_cerrados(11)
    inicio = time.monotonic()
    assert lanzador.buscar_instancia(puertos, espera=0.5) is None
    assert time.monotonic() - inicio < 1.5


def test_si_contestan_dos_gana_el_puerto_mas_bajo():
    servidor.Manejador.estado = servidor.EstadoCompartido("C", None, None)
    abiertas = [ThreadingHTTPServer(("127.0.0.1", 0), servidor.Manejador) for _ in range(2)]
    for abierta in abiertas:
        threading.Thread(target=abierta.serve_forever, daemon=True).start()
    try:
        puertos = sorted(abierta.server_address[1] for abierta in abiertas)
        # Al revés: el orden en que se pasan no decide, el numero de puerto si.
        assert lanzador.buscar_instancia(list(reversed(puertos))) == puertos[0]
    finally:
        for abierta in abiertas:
            abierta.shutdown()
            abierta.server_close()


def test_otro_programa_en_el_puerto_no_es_la_app(tmp_path):
    otro = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        lambda *a, **k: SimpleHTTPRequestHandler(*a, directory=str(tmp_path), **k))
    threading.Thread(target=otro.serve_forever, daemon=True).start()
    try:
        assert lanzador.buscar_instancia([otro.server_address[1]]) is None
    finally:
        otro.shutdown()
        otro.server_close()


def test_algo_que_no_habla_http_en_el_puerto_no_es_la_app():
    # Un programa que acepta la conexion y contesta cualquier cosa menos HTTP:
    # el escaneo lo salta, no se cae.
    ajeno = socket.socket()
    ajeno.bind(("127.0.0.1", 0))
    ajeno.listen()
    ajeno.settimeout(5)

    def atender():
        try:
            while True:
                conexion, _ = ajeno.accept()
                with conexion:
                    conexion.settimeout(5)
                    conexion.recv(4096)     # lee el pedido: si no, Windows corta con un reset
                    conexion.sendall(b"hola, no soy HTTP\r\n")
        except OSError:
            pass    # el socket se cerro: se termino la prueba

    threading.Thread(target=atender, daemon=True).start()
    try:
        assert lanzador.buscar_instancia([ajeno.getsockname()[1]]) is None
    finally:
        ajeno.close()


def test_una_respuesta_que_no_es_un_objeto_no_es_la_app():
    class ConLista(BaseHTTPRequestHandler):
        def do_GET(self):
            cuerpo = b"[1, 2]"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *args):
            pass

    otro = ThreadingHTTPServer(("127.0.0.1", 0), ConLista)
    threading.Thread(target=otro.serve_forever, daemon=True).start()
    try:
        assert lanzador.buscar_instancia([otro.server_address[1]]) is None
    finally:
        otro.shutdown()
        otro.server_close()


@pytest.mark.skipif(sys.platform != "win32", reason="el turno es un mutex de Windows")
def test_el_turno_es_de_uno_solo():
    import ctypes
    nombre = f"Local\\Armonica-prueba-{uuid.uuid4()}"
    primero, manija_1 = lanzador.tomar_el_turno(nombre)
    segundo, manija_2 = lanzador.tomar_el_turno(nombre)
    try:
        assert primero is True
        assert segundo is False
    finally:
        ctypes.windll.kernel32.CloseHandle(manija_1)
        ctypes.windll.kernel32.CloseHandle(manija_2)


def test_esperar_a_la_app_que_esta_arrancando():
    respuestas = iter([None, None, 8003])
    assert lanzador.esperar_instancia(espera=5, cada=0, buscar=lambda: next(respuestas)) == 8003
    assert lanzador.esperar_instancia(espera=0.05, cada=0.01, buscar=lambda: None) is None


def test_sin_navegador_para_la_prueba_de_humo(monkeypatch):
    abiertas = []
    monkeypatch.setattr(lanzador.webbrowser, "open", abiertas.append)
    assert lanzador.abrir_el_navegador(8001, {"ARMONICA_SIN_NAVEGADOR": "1"}) is False
    assert abiertas == []
    assert lanzador.abrir_el_navegador(8001, {}) is True
    assert abiertas == ["http://127.0.0.1:8001"]
