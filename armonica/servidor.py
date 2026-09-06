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
import tempfile
import threading
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import config
from armonica import (audio, exportacion, frases, mapeo, posiciones,
                      prioridades, resumen as modulo_resumen, segmentacion,
                      tablas, teoria, tono, transcripcion)


CARPETA_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# Cada cuánto le mandamos el estado al navegador. Más de quince por segundo no
# lo ve nadie y solo gasta CPU.
REFRESCOS_POR_SEGUNDO = 15

# El tope de un audio subido. Sesenta megas son unos diez minutos de .wav mono
# de 16 bits: muchísimo más que cualquier frase. El límite existe para que un
# archivo equivocado no se lea entero a memoria antes de darnos cuenta.
MAXIMO_SUBIDA_BYTES = 60 * 1024 * 1024

# Lo que se le dice al navegador cuando el archivo no se puede leer. El error
# de audio.leer_wav nombra el archivo, que en la terminal es justo lo que
# queres saber; acá ese archivo es un temporal con nombre inventado y decirlo
# solo confunde. Mismo problema, dos mensajes distintos según quién pregunta.
NO_ES_UN_WAV = (
    "Ese archivo no es un .wav de 16 bits. Si lo grabaste con el teléfono o "
    "con otra app, puede ser un m4a o un mp3: hay que convertirlo a .wav. "
    "En Windows 11, la Grabadora de sonido tiene el formato en su "
    "configuración."
)


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

        # Que microfono usar. None = el predeterminado de Windows, que casi
        # nunca es el que queres: en esta maquina el predeterminado era la
        # camara web, a un metro de distancia, y no se movia nada en pantalla.
        self.dispositivo = config.DISPOSITIVO_ENTRADA

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
        self.error_de_audio = ""

        # El volumen mas alto de los ultimos instantes. El volumen crudo cae a
        # cero entre nota y nota y la barra parpadearia sin parar; el pico se
        # queda un momento arriba y se puede leer de reojo mientras tocas.
        self.pico = 0.0

    # --- Lo que escribe el hilo de audio ---

    def actualizar(self, nota, cents, volumen, segundos, eventos):
        with self._candado:
            if nota is not None:
                self.nota_actual = nota
                self.cents = cents
            self.volumen = volumen
            # El pico baja despacio y sube de golpe, como un vumetro.
            self.pico = max(volumen, self.pico * 0.90)
            self.segundos = segundos
            self.eventos = eventos

    def reiniciar(self):
        with self._candado:
            self.modo = "sesion"
            self.nombre_frase = ""
            self.nota_actual = None
            self.cents = 0.0
            self.volumen = 0.0
            self.pico = 0.0
            self.error_de_audio = ""
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
                "pico": round(self.pico, 4),
                "error_de_audio": self.error_de_audio,
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
        with microfono.CapturaMicrofono(dispositivo=estado.dispositivo) as captura:
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
        # Antes esto solo se imprimia en la terminal, que es justo la ventana
        # que nadie mira cuando esta usando la app. Ahora tambien viaja a la
        # pantalla: un microfono ocupado por otro programa, o desenchufado,
        # se veia identico a "no estoy tocando lo bastante fuerte".
        print(f"  El hilo de audio se corto: {error}")
        estado.error_de_audio = str(error)

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

def _numero(texto):
    """Un decimal que vino en la URL, o None si no vino o vino mal."""
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None


def tramo_como_diccionario(tramo, tabs):
    """
    Un tramo listo para dibujar en la pantalla.

    Los `tabs` NO son los del tramo dentro del analisis completo: son los del
    recorte, o sea exactamente los que se van a guardar si elegis este tramo.

    POR QUE NO SON LOS MISMOS

    El analisis avanza en ventanas de tamano fijo desde el comienzo del
    archivo. Al recortar, esa grilla arranca en otro lado y las ventanas caen
    corridas: una nota que estaba partida en dos se une, o al reves, y un bend
    de paso puede cruzar el umbral de duracion minima en un caso y no en el
    otro. Medido sobre los audios de Leandro, cambia una o dos notas de
    veinte.

    Ninguna de las dos lecturas es la equivocada. Pero si te mostramos una y
    guardamos la otra, elegiste mirando algo que no era. Asi que mostramos la
    que se va a guardar.
    """
    return {
        "numero": tramo.numero,
        "desde_seg": round(tramo.desde_seg, 2),
        "hasta_seg": round(tramo.hasta_seg, 2),
        "duracion_seg": round(tramo.duracion_seg, 1),
        "notas": len(tabs),
        "tab": tabs[:20],
        "hay_mas": len(tabs) > 20,
    }


def comparacion_como_diccionario(comparacion, frase):
    """
    Una Comparacion lista para mandarle al navegador.

    Vive suelta y no adentro del Manejador porque la usan dos caminos
    distintos: practicar en vivo por el microfono y comparar un .wav subido.
    Es exactamente el mismo informe; lo unico que cambia es de donde salieron
    los eventos.
    """
    relativa = comparacion.dispersion_relativa()

    return {
        "nombre": frase.nombre,
        "esperadas": comparacion.notas_esperadas(),
        "aciertos": comparacion.aciertos(),
        "porcentaje": round(comparacion.porcentaje_de_notas()),
        "faltantes": [n.tab for n in comparacion.faltantes],
        "sobrantes": comparacion.sobrantes,
        "cambiadas": [
            {"esperada": a, "tocada": b} for a, b in comparacion.cambiadas
        ],
        "velocidad": round(comparacion.diferencia_de_velocidad()),
        "dispersion_ms": round(comparacion.dispersion_ms()),
        "relativa": round(relativa, 2) if relativa is not None else None,
        "calidad": comparacion.calidad(),
        "notas": [
            {
                "tab": nota_ref.tab,
                "desvio_ms": round(desvio),
                "cents": round(evento.cents - nota_ref.cents),
            }
            for nota_ref, evento, desvio in comparacion.pares
        ],
    }


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
        if self.path == "/api/dispositivos":
            return self._responder_json(self._listar_dispositivos())
        if self.path.startswith("/api/frases/audio"):
            return self._mandar_audio_de_frase(self.path.partition("?")[2])
        if self.path == "/api/resumen":
            return self._responder_json(self._resumen_actual())
        return super().do_GET()

    # --- POST ---

    def do_POST(self):
        # Las rutas que traen un .wav se atienden primero: su cuerpo son bytes
        # de audio, y leerlo como JSON lo consumiria sin poder recuperarlo.
        ruta, _, consulta = self.path.partition("?")

        if ruta == "/api/frases/tramos":
            return self._responder_json(self._tramos_del_audio(consulta))
        if ruta == "/api/frases/importar":
            return self._responder_json(self._importar_frase(consulta))
        if ruta == "/api/frases/intento":
            return self._responder_json(self._intento_de_archivo(consulta))

        cuerpo = self._leer_cuerpo()

        if self.path == "/api/comenzar":
            return self._responder_json(self._comenzar(cuerpo))
        if self.path == "/api/terminar":
            return self._responder_json(self._terminar())
        if self.path == "/api/frases/borrar":
            return self._responder_json(self._borrar_frase(cuerpo))
        if self.path == "/api/configuracion":
            return self._responder_json(self._cambiar_configuracion(cuerpo))
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

    def _leer_audio_subido(self, consulta):
        """
        Lee un audio que subio el navegador.

        Devuelve (nombre, ruta, opciones, error). Las opciones son:
            tonalidad  con que armonica se grabo ESTE archivo
            igual      guardar aunque no pase la revision

        EL NOMBRE VA EN LA URL Y EL AUDIO EN EL CUERPO

        Lo normal para subir un archivo seria multipart/form-data, que mezcla
        campos de texto y archivos en un solo cuerpo. Pero parsear multipart a
        mano es justo donde viven los errores, y no hace falta: mandamos el
        nombre y las opciones en la URL, y los bytes crudos en el cuerpo. Una
        linea de cada lado y nada que parsear.

        El audio va a un archivo temporal porque audio.leer_wav trabaja con
        rutas y no con bytes. El que llama lo borra.
        """
        parametros = urllib.parse.parse_qs(consulta)
        nombre = (parametros.get("nombre", [""])[0] or "").strip()

        opciones = {
            "tonalidad": (parametros.get("tonalidad", [""])[0] or "").strip(),
            "igual": parametros.get("igual", ["0"])[0] == "1",
            # El pedazo a guardar, en segundos desde el principio del audio.
            # Sin esto se guarda el archivo entero.
            "desde": _numero(parametros.get("desde", [""])[0]),
            "hasta": _numero(parametros.get("hasta", [""])[0]),
        }

        largo = int(self.headers.get("Content-Length") or 0)
        if largo <= 0:
            return None, None, opciones, "no llego ningun audio"
        if largo > MAXIMO_SUBIDA_BYTES:
            megas = MAXIMO_SUBIDA_BYTES // (1024 * 1024)
            self.close_connection = True
            return None, None, opciones, f"el archivo pasa los {megas} MB"

        # EL CUERPO SE LEE ANTES DE VALIDAR NADA.
        #
        # Parece al reves: si falta el nombre, para que gastar en leer un
        # archivo que vamos a descartar. Pero el navegador todavia lo esta
        # mandando, y contestarle y cerrar en el medio le corta la conexion:
        # en vez del mensaje "falta el nombre" recibe un error de red. Un test
        # lo agarro justo, y de manera intermitente, que es la peor forma de
        # tener un error.
        datos = self.rfile.read(largo)

        if not nombre:
            return None, None, opciones, "falta el nombre de la frase"

        # La extension del temporal la pone el que sube: si mandaste un .m4a,
        # ffmpeg necesita saberlo para poder convertirlo.
        extension = os.path.splitext(
            (parametros.get("archivo", [""])[0] or "").strip())[1].lower()
        if not extension or len(extension) > 6:
            extension = ".wav"

        temporal = tempfile.NamedTemporaryFile(suffix=extension, delete=False)
        try:
            temporal.write(datos)
        finally:
            temporal.close()

        return nombre, temporal.name, opciones, ""

    # --- Las acciones ---

    def _comenzar(self, peticion=None):
        clase = type(self)
        if clase.estado.escuchando:
            return {"ok": False, "motivo": "ya esta escuchando"}

        peticion = peticion or {}
        modo = peticion.get("modo", "sesion")
        nombre = (peticion.get("nombre") or "").strip()

        if modo == "prueba":
            nombre = ""
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
        if estado.modo == "prueba":
            # Probar el microfono no deja rastro: no es una sesion.
            notas = len([e for e in estado.eventos if e.nota is not None])
            estado.reiniciar()
            return {"ok": True, "modo": "prueba", "notas": notas}

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
        """Compara lo que acabas de tocar contra la frase de referencia."""
        frase = frases.buscar(estado.nombre_frase)
        if frase is None:
            return {"ok": False, "modo": "practicar",
                    "motivo": "la frase ya no esta"}

        return {
            "ok": True,
            "modo": "practicar",
            "comparacion": comparacion_como_diccionario(
                frases.comparar(frase, estado.eventos), frase),
        }

    def _tramos_del_audio(self, consulta):
        """
        Analiza un audio y devuelve los tramos donde hay armonica. NO guarda.

        POR QUE UNA RUTA APARTE, Y POR QUE EL NAVEGADOR SUBE EL ARCHIVO DOS
        VECES

        Podriamos guardarnos el audio analizado en memoria entre el "mostrame
        los tramos" y el "guarda el 2". Seria mas rapido, y traeria un problema
        nuevo por cada cosa que puede pasar en el medio: dos pestanas abiertas,
        el navegador cerrado a mitad de camino, la memoria que crece sola.

        Subirlo de nuevo cuesta unos segundos —seis para un audio de dos
        minutos— y no cuesta ningun estado compartido. A este tamano, esa es
        la cuenta que conviene.
        """
        estado = type(self).estado
        nombre, ruta_temporal, opciones, error = self._leer_audio_subido(consulta)
        if error:
            return {"ok": False, "motivo": error}

        tonalidad = opciones["tonalidad"] or estado.tonalidad
        if tonalidad not in tablas.TONALIDADES:
            os.remove(ruta_temporal)
            return {"ok": False, "motivo": f"no conozco la armonica {tonalidad!r}"}

        try:
            try:
                resultado = transcripcion.desde_archivo(
                    ruta_temporal, tonalidad, estado.posicion, estado.escala)
            except ValueError:
                return {"ok": False, "motivo": NO_ES_UN_WAV}
        finally:
            os.remove(ruta_temporal)

        sirve, motivo, avisos = transcripcion.revisar(resultado, tonalidad)

        # Cada tramo se vuelve a analizar por separado, con el mismo recorte
        # que se usaria al guardarlo. Cuesta unos segundos mas y a cambio lo
        # que ves en la lista es literalmente lo que vas a guardar.
        salida = []
        for tramo in frases.detectar_tramos(resultado.eventos):
            recortado = transcripcion.recortar(
                resultado, tramo.desde_seg, tramo.hasta_seg,
                tonalidad, estado.posicion, estado.escala)
            tabs = [evento.como_tab() for evento in recortado.reconocidas]
            if tabs:
                salida.append(tramo_como_diccionario(tramo, tabs))

        return {
            "ok": True,
            "sirve": sirve,
            "motivo": motivo,
            "avisos": avisos,
            "tonalidad": tonalidad,
            "duracion_seg": round(resultado.duracion_seg, 1),
            "notas": len(resultado.reconocidas),
            "tramos": salida,
        }

    def _importar_frase(self, consulta):
        """
        Guarda como frase de referencia un .wav que subiste.

        Es la puerta de entrada de las grabaciones de Leandro y de tus propios
        audios ya grabados. Antes de guardar nada, revisa que el audio sirva:
        una frase mal transcrita queda guardada para siempre y arruina todas
        las practicas que vengan despues.
        """
        estado = type(self).estado
        nombre, ruta_temporal, opciones, error = self._leer_audio_subido(consulta)
        if error:
            return {"ok": False, "motivo": error}

        # La armonica de ESTE archivo. Vos sabes con cual se grabo; la app no
        # lo puede deducir. Si no la aclaras, se asume la que tenes puesta.
        tonalidad = opciones["tonalidad"] or estado.tonalidad
        if tonalidad not in tablas.TONALIDADES:
            os.remove(ruta_temporal)
            return {"ok": False, "motivo": f"no conozco la armonica {tonalidad!r}"}

        try:
            try:
                resultado = transcripcion.desde_archivo(
                    ruta_temporal, tonalidad, estado.posicion, estado.escala)
            except ValueError:
                return {"ok": False, "motivo": NO_ES_UN_WAV}

            # El recorte va ANTES de la revision: lo que importa es si sirve
            # el pedazo que vas a guardar, y no el archivo entero.
            if opciones["desde"] is not None and opciones["hasta"] is not None:
                resultado = transcripcion.recortar(
                    resultado, opciones["desde"], opciones["hasta"],
                    tonalidad, estado.posicion, estado.escala)
                if not resultado.reconocidas:
                    return {"ok": False,
                            "motivo": "en ese pedazo del audio no hay notas"}

            sirve, motivo, avisos = transcripcion.revisar(resultado, tonalidad)

            # Si no pasa la revision no se guarda nada todavia: se devuelve lo
            # que HABRIA salido y se ofrece guardarlo igual. El umbral de
            # monofonia es una heuristica, no una ley; el que sabe si esa
            # tablatura es la frase que toco Leandro sos vos. Lo unico que la
            # app se asegura es que lo decidas MIRANDO el resultado.
            if not sirve and not opciones["igual"]:
                return {
                    "ok": False,
                    "motivo": motivo,
                    "se_puede_igual": bool(resultado.reconocidas),
                    "vista_previa": [e.como_tab() for e in resultado.reconocidas][:24],
                }

            try:
                frase = frases.desde_eventos(
                    resultado.eventos, nombre, tonalidad,
                    estado.posicion, estado.escala)
            except ValueError as fallo:
                return {"ok": False, "motivo": str(fallo)}

            if not sirve:
                avisos = list(avisos) + ["Guardada salteando el control: " + motivo]
        finally:
            os.remove(ruta_temporal)

        ruta = frases.guardar(frase)

        # El audio queda al lado del JSON. Una frase de Leandro se lee, pero
        # sobre todo se ESCUCHA: sin el audio guardado, la referencia se
        # convierte en una tablatura y perdes justo el ritmo, que es lo que
        # habias venido a buscar.
        audio.escribir_wav(os.path.splitext(ruta)[0] + "_audio.wav",
                           resultado.muestras, resultado.frecuencia_muestreo)

        return {
            "ok": True,
            "avisos": avisos,
            "frase": {
                "nombre": frase.nombre,
                "notas": frase.cantidad,
                "duracion_seg": round(frase.duracion_seg, 1),
                "tonalidad": frase.tonalidad,
                "tab": frase.tablatura(),
            },
        }

    def _intento_de_archivo(self, consulta):
        """
        Compara un .wav subido contra una frase guardada.

        Sirve para cuando ya grabaste el intento con la grabadora de Windows,
        o para comparar dos audios viejos sin volver a tocar.
        """
        nombre, ruta_temporal, _, error = self._leer_audio_subido(consulta)
        if error:
            return {"ok": False, "motivo": error}

        try:
            frase = frases.buscar(nombre)
            if frase is None:
                return {"ok": False, "motivo": f"no encontre la frase {nombre!r}"}

            # El intento se lee con la armonica de la FRASE y no con la que la
            # app tiene puesta: comparar dos tablaturas leidas con armonicas
            # distintas no significaria nada.
            try:
                resultado = transcripcion.desde_archivo(
                    ruta_temporal, frase.tonalidad, frase.posicion, frase.escala)
            except ValueError:
                return {"ok": False, "motivo": NO_ES_UN_WAV}
        finally:
            os.remove(ruta_temporal)

        if not resultado.reconocidas:
            return {"ok": False,
                    "motivo": "no se reconocio ninguna nota en ese audio"}

        return {
            "ok": True,
            "modo": "practicar",
            "comparacion": comparacion_como_diccionario(
                frases.comparar(frase, resultado.eventos), frase),
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
                "hay_audio": os.path.isfile(
                    os.path.splitext(ruta)[0] + "_audio.wav"),
            })
        return {"frases": salida}

    def _borrar_frase(self, peticion):
        nombre = (peticion or {}).get("nombre", "")
        for guardada, ruta in frases.listar():
            if guardada == nombre:
                os.remove(ruta)
                return {"ok": True}
        return {"ok": False, "motivo": "no la encontre"}

    def _listar_dispositivos(self):
        """
        Los microfonos que ve el sistema.

        POR QUE ESTO NO ES UN DETALLE

        En Windows hay siempre media docena de entradas, y la predeterminada
        rara vez es la que queres: en la maquina donde se escribio esto, la
        predeterminada era el microfono de la camara web, a un metro de la
        cara. La app "no andaba" y en realidad estaba escuchando otra cosa.

        Se filtran los duplicados por nombre. Windows lista el mismo microfono
        una vez por cada API de audio (MME, DirectSound, WASAPI, WDM-KS), y
        una lista de veinte entradas con seis nombres repetidos no ayuda a
        nadie a elegir.
        """
        from armonica import microfono

        try:
            entradas = microfono.listar_dispositivos()
        except Exception as error:      # noqa: BLE001
            return {"ok": False, "motivo": str(error), "dispositivos": []}

        vistos = set()
        salida = []
        for numero, nombre, canales in entradas:
            limpio = nombre.strip()
            if limpio.lower() in vistos:
                continue
            vistos.add(limpio.lower())
            salida.append({
                "numero": numero,
                "nombre": limpio,
                "canales": canales,
            })

        return {
            "ok": True,
            "dispositivos": salida,
            "elegido": type(self).estado.dispositivo,
        }

    def _cambiar_configuracion(self, peticion):
        """
        Cambia la armonica, la posicion, la escala o el microfono sin reiniciar.

        No se puede mientras esta escuchando: el hilo de audio ya armo su tabla
        de notas con la armonica anterior, y cambiarla en el medio dejaria la
        primera mitad de la sesion transcrita con una y la segunda con otra.
        """
        clase = type(self)
        estado = clase.estado

        if estado.escuchando:
            return {"ok": False,
                    "motivo": "no se puede cambiar mientras esta escuchando"}

        peticion = peticion or {}

        if "tonalidad" in peticion:
            tonalidad = peticion["tonalidad"]
            if tonalidad not in tablas.TONALIDADES:
                return {"ok": False, "motivo": f"no conozco la armonica {tonalidad!r}"}
            estado.tonalidad = tonalidad

        if "posicion" in peticion:
            posicion = peticion["posicion"]
            if posicion in ("", None):
                estado.posicion = None
            else:
                posicion = int(posicion)
                if posicion not in tablas.POSICIONES_CON_TABLA:
                    return {"ok": False,
                            "motivo": f"todavia no tengo tablas para la {posicion}a"}
                estado.posicion = posicion

        if "escala" in peticion:
            escala = peticion["escala"] or None
            if escala is not None and escala not in tablas.ESCALAS_INTERVALOS:
                return {"ok": False, "motivo": f"no conozco la escala {escala!r}"}
            estado.escala = escala

        if "dispositivo" in peticion:
            valor = peticion["dispositivo"]
            estado.dispositivo = None if valor in ("", None) else int(valor)

        return {"ok": True, "inicio": self._datos_iniciales()}

    def _mandar_audio_de_frase(self, consulta):
        """
        Manda el .wav de una frase para que el navegador lo pueda reproducir.

        Una frase de referencia se lee, pero sobre todo se ESCUCHA: la
        tablatura no lleva el ritmo, y el ritmo es justo lo que estas tratando
        de copiar. Sin esto, el audio estaba guardado en el disco y no habia
        forma de oirlo desde la app.
        """
        parametros = urllib.parse.parse_qs(consulta)
        nombre = (parametros.get("nombre", [""])[0] or "").strip()

        ruta = None
        for guardada, ruta_json in frases.listar():
            if guardada == nombre:
                candidata = os.path.splitext(ruta_json)[0] + "_audio.wav"
                if os.path.isfile(candidata):
                    ruta = candidata
                break

        if ruta is None:
            return self.send_error(404, "esa frase no tiene audio guardado")

        with open(ruta, "rb") as archivo:
            datos = archivo.read()

        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)

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
            "tonalidades": list(tablas.TONALIDADES_DISPONIBLES),
            "posiciones": [
                {"numero": numero,
                 "nombre": tablas.NOMBRES_POSICIONES.get(numero, f"{numero}a")}
                for numero in tablas.POSICIONES_CON_TABLA
            ],
            "escalas": [
                {"clave": clave, "nombre": tablas.NOMBRES_ESCALAS.get(clave, clave)}
                for clave in tablas.ESCALAS_INTERVALOS
            ],
            "umbral_volumen": config.UMBRAL_VOLUMEN_RMS,
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
