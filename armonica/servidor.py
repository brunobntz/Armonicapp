"""
servidor.py — La interfaz web, servida desde tu propia máquina.

QUE ES Y QUE NO ES

Es la misma app de siempre con otra pantalla. Python sigue haciendo todo:
capturar el micrófono, detectar el tono, mapear a agujeros, segmentar. El
navegador solo dibuja.

NO es una app web: no hay nada en internet, el servidor corre en tu
computadora y solo vos lo ves.

POR QUE UN NAVEGADOR Y NO LA TERMINAL

Por el medidor de afinación. En la terminal se redibuja doce veces por segundo
y parpadea; en el navegador una aguja se mueve suave y se puede mirar mientras
soplás, que es justamente cuando hace falta.

Y porque el histórico necesita gráficos. Los JSON de cada sesión ya guardan
todo; lo que faltaba era dibujarlos.

SIN DEPENDENCIAS NUEVAS

Todo con la biblioteca estándar de Python. El truco es no usar WebSockets sino
SERVER-SENT EVENTS: una respuesta HTTP común que nunca se cierra, por la que el
servidor va escribiendo líneas. El navegador la lee con `EventSource`, que
viene incluido. Es más simple que un WebSocket y alcanza de sobra, porque acá
los datos van en una sola dirección.

COMO ESTA ARMADO

Dos hilos que comparten un objeto:

    hilo de audio   captura y analiza sin parar, y va dejando el estado
    hilo del HTTP   atiende al navegador y le manda ese estado

El estado se protege con un candado (`threading.Lock`) porque los dos hilos lo
tocan. Es la misma idea que en el callback del micrófono: el que produce no se
frena a esperar al que consume.
"""

import json
import os
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import config
from armonica import (audio, exportacion, frases, mapeo, posiciones,
                      prioridades, resumen as modulo_resumen, segmentacion,
                      tablas, teoria, tono)


CARPETA_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# Cada cuánto le mandamos el estado al navegador. Más de quince por segundo no
# lo ve nadie y solo gasta CPU.
REFRESCOS_POR_SEGUNDO = 15


class EstadoCompartido:
    """
    Lo que el hilo de audio escribe y el hilo del HTTP lee.

    Todo pasa por un candado. Sin él, el navegador podría leer una lista de
    eventos justo en el medio de una actualización y recibir algo a medio
    escribir.
    """

    def __init__(self, tonalidad="C", posicion=None, escala=None):
        self._candado = threading.Lock()

        self.tonalidad = tonalidad
        self.posicion = posicion
        self.escala = escala

        # En que modo esta escuchando. Cambia SOLO lo que pasa al terminar:
        #   "sesion"     -> guarda la sesion en sesiones/
        #   "frase"      -> guarda lo tocado como frase de referencia
        #   "practicar"  -> compara contra una frase guardada
        # Mientras escucha, los tres hacen exactamente lo mismo.
        self.modo = "sesion"
        self.nombre_frase = ""

        self.escuchando = False
        self.nota_actual = None
        self.cents = 0.0
        self.volumen = 0.0
        self.segundos = 0.0
        self.eventos = []
        self.mediciones = []
        self.audio_grabado = None
        self.frecuencia_muestreo = config.FRECUENCIA_MUESTREO
        self.ultimo_guardado = None

    # --- Lo que escribe el hilo de audio ---

    def actualizar(self, nota, cents, volumen, segundos, eventos):
        with self._candado:
            if nota is not None:
                self.nota_actual = nota
                self.cents = cents
            self.volumen = volumen
            self.segundos = segundos
            self.eventos = eventos

    def reiniciar(self):
        with self._candado:
            self.modo = "sesion"
            self.nombre_frase = ""
            self.nota_actual = None
            self.cents = 0.0
            self.volumen = 0.0
            self.segundos = 0.0
            self.eventos = []
            self.mediciones = []
            self.audio_grabado = None
            self.ultimo_guardado = None

    # --- Lo que lee el hilo del HTTP ---

    def como_diccionario(self):
        """El estado que se le manda al navegador en cada refresco."""
        with self._candado:
            nota = self.nota_actual
            eventos = list(self.eventos)

            datos = {
                "escuchando": self.escuchando,
                "modo": self.modo,
                "nombre_frase": self.nombre_frase,
                "tonalidad": self.tonalidad,
                "posicion": self.posicion,
                "escala": self.escala,
                "volumen": round(self.volumen, 4),
                "segundos": round(self.segundos, 1),
                "cents": round(self.cents, 1),
                "cantidad_notas": len(eventos),
                "nota": None,
                "tab": [e.como_tab() for e in eventos[-24:]],
                "ultimo_guardado": self.ultimo_guardado,
            }

            if nota is not None:
                datos["nota"] = {
                    "tab": nota.como_tab(),
                    "nombre": nota.nombre,
                    "agujero": nota.agujero,
                    "direccion": nota.direccion,
                    "bend": nota.bend,
                    "en_escala": self._en_escala(nota),
                }

            return datos

    def _en_escala(self, nota):
        if not (self.posicion and self.escala):
            return None
        return posiciones.nota_en_escala(nota, self.tonalidad, self.posicion,
                                         self.escala)


def diagrama_de_la_armonica(tonalidad, posicion=None, escala=None):
    """
    El mapa de la armónica para dibujar: qué nota da cada agujero y si está
    en la escala de referencia.

    Se calcula una sola vez, cuando el navegador carga la página. No cambia
    mientras tocás.
    """
    en_escala = set()
    if posicion and escala:
        try:
            en_escala = {
                nota.midi
                for nota in teoria.agujeros_para_escala(
                    tonalidad, posicion, escala
                ).agujeros
            }
        except ValueError:
            en_escala = set()

    filas = []
    formas = mapeo.todas_las_formas(tonalidad)
    por_clave = {}
    for lista in formas.values():
        for nota in lista:
            por_clave[(nota.agujero, nota.direccion, nota.bend)] = nota

    definicion = [
        ("soplado", mapeo.SOPLADO, 0),
        ("aspirado", mapeo.ASPIRADO, 0),
        ("bend", None, 1),
        ("bend 2", None, 2),
        ("bend 3", None, 3),
    ]

    for etiqueta, direccion, bend in definicion:
        celdas = []
        hay_alguna = False

        for agujero in range(1, 11):
            nota = None
            if direccion is not None:
                nota = por_clave.get((agujero, direccion, bend))
            else:
                for prueba in (mapeo.ASPIRADO, mapeo.SOPLADO):
                    nota = por_clave.get((agujero, prueba, bend))
                    if nota is not None:
                        break

            if nota is None:
                celdas.append(None)
                continue

            hay_alguna = True
            celdas.append({
                "tab": nota.como_tab(),
                "nombre": nota.nombre,
                "agujero": nota.agujero,
                "direccion": nota.direccion,
                "bend": nota.bend,
                "en_escala": nota.midi in en_escala,
            })

        if hay_alguna:
            filas.append({"etiqueta": etiqueta, "celdas": celdas})

    return filas


# =============================================================================
# El hilo que escucha
# =============================================================================

def escuchar(estado, detener):
    """
    Captura el micrófono y va actualizando el estado, hasta que se lo pidan.

    Es el mismo bucle del modo en vivo de la terminal. La única diferencia es
    que en vez de dibujar, deja el resultado en un objeto que otro hilo lee.
    """
    from armonica import microfono

    tabla = mapeo.construir_tabla_inversa(estado.tonalidad)
    mediciones = []

    try:
        with microfono.CapturaMicrofono() as captura:
            estado.frecuencia_muestreo = captura.frecuencia_muestreo
            ultimo_recalculo = -1.0
            eventos = []

            for instante, ventana in captura.ventanas():
                if detener.is_set():
                    break

                volumen = audio.volumen_rms(ventana)

                if volumen < config.UMBRAL_VOLUMEN_RMS:
                    frecuencia, confianza = None, 0.0
                else:
                    frecuencia, confianza = tono.detectar_frecuencia(
                        ventana, estado.frecuencia_muestreo
                    )

                mediciones.append({
                    "tiempo_seg": instante, "frecuencia": frecuencia,
                    "confianza": confianza, "volumen": volumen,
                })

                nota, cents = (None, 0.0)
                if frecuencia is not None:
                    nota, cents = mapeo.frecuencia_a_nota(
                        frecuencia, tabla_inversa=tabla
                    )

                # La segmentación se rehace unas pocas veces por segundo, no en
                # cada ventana: es lo único caro del bucle.
                if instante - ultimo_recalculo >= 1.0 / REFRESCOS_POR_SEGUNDO:
                    ultimo_recalculo = instante
                    eventos = segmentacion.segmentar(
                        mediciones, tabla,
                        frecuencia_muestreo=estado.frecuencia_muestreo,
                    )
                    if estado.posicion and estado.escala:
                        segmentacion.marcar_escala(
                            eventos, estado.tonalidad, estado.posicion,
                            estado.escala,
                        )

                estado.actualizar(nota, cents, volumen, instante, eventos)

            estado.audio_grabado = captura.audio_grabado()

    except Exception as error:      # noqa: BLE001
        print(f"  El hilo de audio se corto: {error}")

    estado.mediciones = mediciones
    estado.escuchando = False


def guardar(estado):
    """Cierra la sesión y escribe los archivos. Devuelve las rutas."""
    if not estado.eventos:
        return {}

    rutas = exportacion.guardar_sesion(
        estado.eventos,
        tonalidad=estado.tonalidad,
        posicion=estado.posicion,
        escala=estado.escala,
        muestras=estado.audio_grabado,
        frecuencia_muestreo=estado.frecuencia_muestreo,
    )
    estado.ultimo_guardado = {que: os.path.basename(ruta)
                              for que, ruta in rutas.items()}
    return rutas


# =============================================================================
# El histórico
# =============================================================================

def historial(carpeta=None):
    """
    Junta todas las sesiones guardadas para poder graficarlas.

    Es lo que hace que el proyecto sirva a lo largo del tiempo y no solo en el
    momento: los JSON ya guardaban todo, faltaba mirarlos juntos.
    """
    sesiones = []
    bends = {}

    for ruta in reversed(exportacion.listar_sesiones(carpeta)):
        try:
            datos = exportacion.leer_sesion(ruta)
        except (ValueError, KeyError, OSError):
            continue

        resumen = datos.get("resumen", {})
        fecha = datos.get("fecha", "")[:10]

        sesiones.append({
            "archivo": os.path.basename(ruta),
            "fecha": fecha,
            "notas": resumen.get("cantidad_notas", 0),
            "duracion_min": round(resumen.get("duracion_seg", 0) / 60.0, 1),
            "afinacion": resumen.get("afinacion_armonica_cents"),
            "duracion_media_ms": resumen.get("duracion_media_ms", 0),
            "posicion": datos.get("configuracion", {}).get("posicion"),
            "tonalidad": datos.get("configuracion", {}).get("tonalidad", ""),
        })

        # La afinación de cada bend, medida CONTRA la armónica de esa sesión.
        # Sin descontarla estaríamos mezclando cómo estaba afinado el
        # instrumento con cómo se toco.
        afinacion = resumen.get("afinacion_armonica_cents") or 0.0
        por_bend = {}
        for evento in datos.get("eventos", []):
            nota = evento.get("nota")
            if not nota or not nota.get("bend"):
                continue
            por_bend.setdefault(evento["tab"], []).append(
                evento["cents"] - afinacion
            )

        for tab, valores in por_bend.items():
            valores.sort()
            bends.setdefault(tab, []).append({
                "fecha": fecha,
                "archivo": os.path.basename(ruta),
                "cents": round(valores[len(valores) // 2], 1),
                "veces": len(valores),
            })

    # Solo los bends que aparecen en varias sesiones: con una sola no hay
    # tendencia que mirar.
    bends = {tab: puntos for tab, puntos in bends.items() if len(puntos) >= 2}

    return {"sesiones": sesiones, "bends": bends}


# =============================================================================
# El servidor HTTP
# =============================================================================

class Manejador(SimpleHTTPRequestHandler):
    """
    Atiende al navegador.

    Las rutas que empiezan con /api devuelven datos; el resto son los archivos
    de la carpeta web/.
    """

    estado = None
    hilo_audio = None
    detener = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=CARPETA_WEB, **kwargs)

    def log_message(self, formato, *args):
        """Silencia el registro de cada pedido, que llena la terminal."""

    # --- GET ---

    def do_GET(self):
        if self.path == "/api/vivo":
            return self._transmitir_estado()
        if self.path == "/api/inicio":
            return self._responder_json(self._datos_iniciales())
        if self.path == "/api/historial":
            return self._responder_json(historial())
        if self.path == "/api/frases":
            return self._responder_json(self._listar_frases())
        if self.path == "/api/resumen":
            return self._responder_json(self._resumen_actual())
        return super().do_GET()

    # --- POST ---

    def do_POST(self):
        cuerpo = self._leer_cuerpo()

        if self.path == "/api/comenzar":
            return self._responder_json(self._comenzar(cuerpo))
        if self.path == "/api/terminar":
            return self._responder_json(self._terminar())
        if self.path == "/api/frases/borrar":
            return self._responder_json(self._borrar_frase(cuerpo))
        self.send_error(404)

    def _leer_cuerpo(self):
        """Lee el JSON que manda el navegador, si es que manda alguno."""
        largo = int(self.headers.get("Content-Length") or 0)
        if largo <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(largo).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    # --- Las acciones ---

    def _comenzar(self, peticion=None):
        clase = type(self)
        if clase.estado.escuchando:
            return {"ok": False, "motivo": "ya esta escuchando"}

        peticion = peticion or {}
        modo = peticion.get("modo", "sesion")
        nombre = (peticion.get("nombre") or "").strip()

        if modo in ("frase", "practicar") and not nombre:
            return {"ok": False, "motivo": "falta el nombre de la frase"}

        if modo == "practicar" and frases.buscar(nombre) is None:
            return {"ok": False, "motivo": f"no encontre la frase {nombre!r}"}

        clase.estado.reiniciar()
        clase.estado.modo = modo
        clase.estado.nombre_frase = nombre
        clase.estado.escuchando = True
        clase.detener = threading.Event()
        clase.hilo_audio = threading.Thread(
            target=escuchar, args=(clase.estado, clase.detener), daemon=True
        )
        clase.hilo_audio.start()
        return {"ok": True}

    def _terminar(self):
        clase = type(self)
        if clase.detener is not None:
            clase.detener.set()
        if clase.hilo_audio is not None:
            clase.hilo_audio.join(timeout=3.0)

        clase.estado.escuchando = False
        estado = clase.estado

        # Los tres modos escuchan igual; lo que cambia es que se hace despues.
        if estado.modo == "frase":
            return self._terminar_grabando_frase(estado)
        if estado.modo == "practicar":
            return self._terminar_practicando(estado)

        rutas = guardar(estado)
        return {
            "ok": True,
            "modo": "sesion",
            "guardado": {q: os.path.basename(r) for q, r in rutas.items()},
            "resumen": self._resumen_actual(),
        }

    def _terminar_grabando_frase(self, estado):
        """Guarda lo tocado como frase de referencia."""
        try:
            frase = frases.desde_eventos(
                estado.eventos, estado.nombre_frase, estado.tonalidad,
                estado.posicion, estado.escala,
            )
        except ValueError as error:
            return {"ok": False, "modo": "frase", "motivo": str(error)}

        frases.guardar(frase)

        return {
            "ok": True,
            "modo": "frase",
            "frase": {
                "nombre": frase.nombre,
                "notas": frase.cantidad,
                "duracion_seg": round(frase.duracion_seg, 1),
                "tab": frase.tablatura(),
            },
        }

    def _terminar_practicando(self, estado):
        """Compara lo tocado contra la frase de referencia."""
        frase = frases.buscar(estado.nombre_frase)
        if frase is None:
            return {"ok": False, "modo": "practicar",
                    "motivo": "la frase ya no esta"}

        comparacion = frases.comparar(frase, estado.eventos)

        return {
            "ok": True,
            "modo": "practicar",
            "comparacion": {
                "nombre": frase.nombre,
                "esperadas": comparacion.notas_esperadas(),
                "aciertos": comparacion.aciertos(),
                "porcentaje": round(comparacion.porcentaje_de_notas()),
                "faltantes": [n.tab for n in comparacion.faltantes],
                "sobrantes": comparacion.sobrantes,
                "cambiadas": [
                    {"esperada": a, "tocada": b}
                    for a, b in comparacion.cambiadas
                ],
                "velocidad": round(comparacion.diferencia_de_velocidad()),
                "dispersion_ms": round(comparacion.dispersion_ms()),
                "relativa": (round(comparacion.dispersion_relativa(), 2)
                             if comparacion.dispersion_relativa() is not None
                             else None),
                "calidad": comparacion.calidad(),
                "notas": [
                    {
                        "tab": nota_ref.tab,
                        "desvio_ms": round(desvio),
                        "cents": round(evento.cents - nota_ref.cents),
                    }
                    for nota_ref, evento, desvio in comparacion.pares
                ],
            },
        }

    def _listar_frases(self):
        salida = []
        for nombre, ruta in frases.listar():
            frase = frases.cargar(ruta)
            salida.append({
                "nombre": nombre,
                "notas": frase.cantidad,
                "duracion_seg": round(frase.duracion_seg, 1),
                "tonalidad": frase.tonalidad,
                "posicion": frase.posicion,
                "fecha": (frase.fecha or "")[:10],
                "tab": frase.tablatura()[:16],
            })
        return {"frases": salida}

    def _borrar_frase(self, peticion):
        nombre = (peticion or {}).get("nombre", "")
        for guardada, ruta in frases.listar():
            if guardada == nombre:
                os.remove(ruta)
                return {"ok": True}
        return {"ok": False, "motivo": "no la encontre"}

    def _resumen_actual(self):
        estado = type(self).estado
        eventos = estado.eventos
        if not eventos:
            return {"hay": False}

        datos = modulo_resumen.resumir(eventos, estado.tonalidad,
                                       estado.posicion, estado.escala)
        hallazgos, sin_medir = prioridades.analizar(
            eventos, None, estado.tonalidad, estado.posicion, estado.escala
        )

        return {
            "hay": True,
            "notas": datos.cantidad_notas,
            "duracion_seg": round(datos.duracion_seg, 1),
            "afinacion": (round(datos.afinacion_armonica_cents, 1)
                          if datos.afinacion_armonica_cents is not None else None),
            "agujeros": [
                {"tab": tab, "veces": veces}
                for tab, veces, _ in datos.conteo_por_agujero[:10]
            ],
            "pares": [
                {"de": par[0], "a": par[1], "veces": veces}
                for par, veces in datos.pares_repetidos
            ],
            "hallazgos": [
                {"titulo": h.titulo, "evidencia": h.evidencia,
                 "accion": h.accion, "confianza": h.confianza}
                for h in hallazgos[:3]
            ],
            "sin_medir": sin_medir,
        }

    def _datos_iniciales(self):
        estado = type(self).estado
        tono_resultante = ""
        if estado.posicion:
            tono_resultante = posiciones.tonalidad_resultante(
                estado.tonalidad, estado.posicion
            )

        return {
            "tonalidad": estado.tonalidad,
            "posicion": estado.posicion,
            "escala": estado.escala,
            "nombre_escala": tablas.NOMBRES_ESCALAS.get(estado.escala, ""),
            "nombre_posicion": (tablas.NOMBRES_POSICIONES.get(estado.posicion, "")
                                if estado.posicion else ""),
            "tono_resultante": tono_resultante,
            "diagrama": diagrama_de_la_armonica(
                estado.tonalidad, estado.posicion, estado.escala
            ),
            "tolerancia_cents": 10.0,
        }

    # --- Las respuestas ---

    def _responder_json(self, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _transmitir_estado(self):
        """
        La conexión que nunca se cierra.

        El navegador la abre una vez y el servidor le va escribiendo el estado
        quince veces por segundo. Cada mensaje es la palabra "data:", el JSON, y
        dos saltos de línea: ese es todo el protocolo de server-sent events.
        """
        import time

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            while True:
                datos = json.dumps(type(self).estado.como_diccionario(),
                                   ensure_ascii=False)
                self.wfile.write(f"data: {datos}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(1.0 / REFRESCOS_POR_SEGUNDO)
        except (BrokenPipeError, ConnectionResetError):
            # El navegador cerró la pestaña. Es normal, no es un error.
            pass


def arrancar(tonalidad="C", posicion=None, escala=None, puerto=8000,
             abrir_navegador=True):
    """Levanta el servidor y bloquea hasta que lo cortes con Ctrl+C."""
    Manejador.estado = EstadoCompartido(tonalidad, posicion, escala)

    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    direccion = f"http://127.0.0.1:{puerto}"

    print()
    print("=" * 72)
    print(f"  Servidor andando en {direccion}")
    print("=" * 72)
    print()
    if posicion:
        print(f"  {posiciones.descripcion_completa(tonalidad, posicion, escala)}")
    else:
        print(f"  Armonica en {tonalidad}")
    print()
    print("  Solo escucha en tu propia maquina: no hay nada en internet.")
    print("  Ctrl+C para apagarlo.")
    print()

    if abrir_navegador:
        threading.Timer(0.7, lambda: webbrowser.open(direccion)).start()

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Apagando...")
        if Manejador.detener is not None:
            Manejador.detener.set()
        servidor.shutdown()

    return 0
