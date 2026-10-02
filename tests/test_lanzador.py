"""
Tests de armonica/lanzador.py — abrir la app desde un ícono.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_lanzador.py -v
"""

import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from armonica import lanzador, servidor


def test_los_datos_van_donde_diga_armonica_datos(tmp_path):
    assert lanzador.carpeta_de_datos({"ARMONICA_DATOS": str(tmp_path)}) == str(tmp_path)


def test_sin_la_variable_van_a_documentos(monkeypatch):
    monkeypatch.setattr(lanzador, "carpeta_de_documentos", lambda: os.path.join("D:", "Docs"))
    assert lanzador.carpeta_de_datos({}) == os.path.join("D:", "Docs", "Armonica")


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
