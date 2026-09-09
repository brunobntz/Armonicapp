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
import time
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import config
from armonica import (audio, exportacion, frases, mapeo, posiciones,
                      prioridades, resumen as modulo_resumen, ritmo,
                      segmentacion, tablas, teoria, tono, transcripcion)


CARPETA_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# Cada cuánto le mandamos el estado al navegador. Más de quince por segundo no
# lo ve nadie y solo gasta CPU.
REFRESCOS_POR_SEGUNDO = 15

# El tope de un audio subido. Sesenta megas son unos diez minutos de .wav mono
# de 16 bits: muchísimo más que cualquier frase. El límite existe para que un
# archivo equivocado no se lea entero a memoria antes de darnos cuenta.
MAXIMO_SUBIDA_BYTES = 60 * 1024 * 1024

# Cuantas veces seguidas se intenta reabrir el microfono antes de darse por
# vencido, y cuanto se espera entre intento e intento. Ver `escuchar`: con el
# microfono prendido todo el tiempo, que el hilo se muera una vez ya no es un
# final aceptable.
INTENTOS_DE_MICROFONO = 5
ESPERA_ENTRE_INTENTOS = 0.5

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

        # Lo que vos escribis antes de grabar: como se llama y de que se
        # trata. Sin esto, dentro de un mes tenes doce carpetas con fecha y
        # hora y ninguna forma de saber cual era la que valia la pena.
        self.titulo = ""
        self.comentario = ""

        # ESCUCHAR Y GRABAR SON DOS COSAS DISTINTAS
        #
        # `escuchando` es el microfono abierto: la app lo deja prendido todo el
        # tiempo, para que puedas tocar y ver lo que sale sin decidir nada
        # antes. `grabando` es querer que eso quede guardado.
        #
        # Antes eran lo mismo y por eso habia que apretar un boton para que la
        # pantalla mostrara algo. Peor: al probar el microfono desde Ajustes,
        # la app quedaba escuchando en modo "prueba" y los dos botones de la
        # solapa En vivo quedaban muertos, uno porque ya escuchaba y el otro
        # porque no era una sesion.
        self.escuchando = False
        self.grabando = False

        # Lo que el hilo del HTTP le pide al hilo de audio. Son las dos unicas
        # cosas que el hilo de audio no puede decidir solo, porque tiene la
        # captura: arrancar una grabacion limpia y cerrarla.
        self._pedido = None
        self.grabacion_lista = False

        # En que segundo del reloj del microfono empezo la grabacion. El reloj
        # corre desde que se abrio el microfono, asi que sin esto el contador
        # de la pantalla diria "0:14" apenas apretaste Grabar.
        self.inicio_grabacion_seg = 0.0

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

        # Para el filtro del cartel grande. Ver actualizar(): una nota tiene
        # que repetirse antes de mostrarse, y el cartel aguanta los huecos.
        self._candidata = None
        self._veces_seguidas = 0
        self._ultima_nota_seg = None

    # --- Lo que se piden los dos hilos ---

    def pedir(self, que):
        with self._candado:
            self._pedido = que
            if que == "arrancar":
                self.grabacion_lista = False

    def tomar_pedido(self):
        """Devuelve el pedido pendiente y lo borra. Lo llama el hilo de audio."""
        with self._candado:
            pedido = self._pedido
            self._pedido = None
            return pedido

    # --- Lo que escribe el hilo de audio ---

    def actualizar(self, nota, cents, volumen, segundos, eventos):
        """
        Recibe UNA ventana de analisis. Se llama unas ochenta veces por segundo.

        POR QUE EL CARTEL NO MUESTRA CUALQUIER VENTANA

        La tablatura pasa por segmentacion, que descarta lo que dura menos de
        60 ms. El cartel grande no pasaba por ningun filtro: mostraba la ultima
        ventana que dio nota, y ademas NUNCA SE BORRABA. Una sola ventana
        equivocada quedaba en pantalla hasta la siguiente nota, y despues de
        dejar de tocar seguia mostrando la ultima, como si todavia sonara.

        Son dos reglas distintas para dos preguntas distintas:

          para MOSTRAR una nota nueva  tiene que repetirse
                                       VENTANAS_PARA_CONFIRMAR veces seguidas
          para APAGAR el cartel        tienen que pasar
                                       SEGUNDOS_PARA_APAGAR_CARTEL sin nada

        La segunda es mas larga a proposito. Dentro de una nota sostenida hay
        ventanas sueltas sin deteccion —un golpe de aire, un cambio de
        embocadura—; si el cartel se apagara con esas, el agujero desapareceria
        en cada respiracion.
        """
        with self._candado:
            self.volumen = volumen
            # El pico baja despacio y sube de golpe, como un vumetro.
            self.pico = max(volumen, self.pico * 0.90)
            self.segundos = segundos
            self.eventos = eventos

            if nota is None:
                # Ningun tono en esta ventana. El cartel se sostiene hasta que
                # el silencio sea largo de verdad.
                self._candidata = None
                self._veces_seguidas = 0
                if (self._ultima_nota_seg is not None
                        and segundos - self._ultima_nota_seg
                        > config.SEGUNDOS_PARA_APAGAR_CARTEL):
                    self.nota_actual = None
                    self.cents = 0.0
                return

            self._ultima_nota_seg = segundos

            # Comparamos por tablatura y no por objeto: dos Nota iguales son
            # el mismo agujero aunque sean instancias distintas.
            clave = nota.como_tab()
            if clave == self._candidata:
                self._veces_seguidas += 1
            else:
                self._candidata = clave
                self._veces_seguidas = 1

            # La nota que ya esta en el cartel no tiene que reconfirmarse: solo
            # se exige confirmacion para CAMBIARLO.
            ya_esta = (self.nota_actual is not None
                       and self.nota_actual.como_tab() == clave)

            if ya_esta or self._veces_seguidas >= max(
                    1, config.VENTANAS_PARA_CONFIRMAR):
                self.nota_actual = nota
                self.cents = cents

    def reiniciar(self):
        with self._candado:
            self.modo = "sesion"
            self.titulo = ""
            self.comentario = ""
            self.grabando = False
            self.grabacion_lista = False
            self.inicio_grabacion_seg = 0.0
            self.nombre_frase = ""
            self.nota_actual = None
            self.cents = 0.0
            self.volumen = 0.0
            self.pico = 0.0
            self._candidata = None
            self._veces_seguidas = 0
            self._ultima_nota_seg = None
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
                "grabando": self.grabando,
                "modo": self.modo,
                "nombre_frase": self.nombre_frase,
                "titulo": self.titulo,
                "tonalidad": self.tonalidad,
                "posicion": self.posicion,
                "escala": self.escala,
                "volumen": round(self.volumen, 4),
                "pico": round(self.pico, 4),
                "error_de_audio": self.error_de_audio,
                # El contador es de la GRABACION y no del microfono, que
                # viene andando desde que abriste la app.
                "segundos": round(
                    self.segundos - self.inicio_grabacion_seg
                    if self.grabando else self.segundos, 1),
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


# Cuántas columnas de bend hay de cada lado. Salen de la armónica y no de un
# gusto: el bend aspirado más profundo es el del agujero 3, que baja tres
# semitonos, y el soplado más profundo es el del 10, que baja dos.
COLUMNAS_BEND_ASPIRADO = 3
COLUMNAS_BEND_SOPLADO = 2


def diagrama_de_la_armonica(tonalidad, posicion=None, escala=None):
    """
    El mapa de la armónica para dibujar, una fila por agujero.

    POR QUE ASI Y NO EN FILAS DE SOPLADO Y ASPIRADO

    La versión anterior tenía una fila para soplado, otra para aspirado y una
    más por cada nivel de bend. Es la forma en que están escritas las tablas, y
    es la forma equivocada de mirarlas mientras tocás: los tres bends del
    agujero 3 quedaban repartidos en tres filas distintas, cuando son una sola
    cosa —una nota que baja— vista desde tres lugares.

    Acá cada agujero es una fila y sus notas se abren hacia los costados. Para
    el agujero 3 de una armónica en Do, de izquierda a derecha:

        Ab   A   Bb   B  |  3  |  G

    donde Ab es el tercer bend aspirado, B el aspirado sin bend, y G el
    soplado. A la izquierda lo aspirado, y cuanto más lejos del número, más
    profundo el bend; a la derecha lo soplado, con la misma idea.

    Es la disposición que usa Bending Trainer, y no es casualidad que funcione:
    puesto así, un bend es un movimiento hacia AFUERA, y se puede seguir con el
    ojo mientras lo hacés.

    Cada celda trae su `midi` porque la pantalla lo necesita para ubicar la
    línea que marca dónde está tu afinación entre una nota y la siguiente.
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

    por_clave = {}
    for lista in mapeo.todas_las_formas(tonalidad).values():
        for nota in lista:
            por_clave[(nota.agujero, nota.direccion, nota.bend)] = nota

    def celda(agujero, direccion, bend):
        nota = por_clave.get((agujero, direccion, bend))
        if nota is None:
            return None
        return {
            "tab": nota.como_tab(),
            "nombre": nota.nombre,
            "midi": nota.midi,
            "agujero": nota.agujero,
            "direccion": nota.direccion,
            "bend": nota.bend,
            "en_escala": nota.midi in en_escala,
        }

    filas = []
    for agujero in range(1, 11):
        # De afuera hacia adentro: el bend más profundo va más lejos del
        # número. Los huecos se mandan como None a propósito, para que todas
        # las filas tengan la misma cantidad de columnas y la grilla quede
        # alineada: sin eso, el agujero 1 y el 3 no coincidirían.
        aspirados = [
            celda(agujero, mapeo.ASPIRADO, bend)
            for bend in range(COLUMNAS_BEND_ASPIRADO, 0, -1)
        ]
        aspirados.append(celda(agujero, mapeo.ASPIRADO, 0))

        soplados = [celda(agujero, mapeo.SOPLADO, 0)]
        soplados.extend(
            celda(agujero, mapeo.SOPLADO, bend)
            for bend in range(1, COLUMNAS_BEND_SOPLADO + 1)
        )

        filas.append({
            "agujero": agujero,
            "aspirado": aspirados,
            "soplado": soplados,
        })

    return filas


def escuchar(estado, detener):
    """
    Captura el micrófono y va actualizando el estado, hasta que se lo pidan.

    Es el mismo bucle del modo en vivo de la terminal. La única diferencia es
    que en vez de dibujar, deja el resultado en un objeto que otro hilo lee.

    EL MICROFONO QUEDA ENCENDIDO SIEMPRE

    Este hilo arranca cuando arranca el servidor y no para hasta que cerrás la
    app. Podés tocar y ver lo que sale sin apretar nada. Grabar es una decisión
    aparte, y lo único que cambia es qué se guarda en memoria:

        sin grabar   se tira el audio y se recorta la historia a
                     config.SEGUNDOS_EN_PANTALLA
        grabando     se guarda todo, que es lo que después va al disco

    Sin ese recorte, estar sentado con la app abierta sumaría diez megas de
    audio por minuto sin que hayas tocado nada.

    Y SE VUELVE A ABRIR SOLO

    `captura.ventanas()` TERMINA cuando el micrófono deja de entregar audio
    por unos segundos: lo desenchufaste, otro programa lo tomó, el driver
    hipó. Eso existe para que una sesión con el micrófono desconectado no se
    cuelgue para siempre, y está bien.

    Pero con el micrófono prendido todo el tiempo, que el hilo termine ahí es
    un final malísimo: la app deja de escuchar en silencio y no vuelve nunca.
    Apareció así, y cuesta de diagnosticar porque no hay error que mostrar:
    `escuchando` en false y `error_de_audio` vacío.

    Por eso el bucle de afuera lo reabre. Si falla varias veces seguidas se
    rinde, y ahí sí hay algo concreto que decirte en pantalla.
    """
    from armonica import microfono

    tabla = mapeo.construir_tabla_inversa(estado.tonalidad)
    fallos = 0

    while not detener.is_set():
        try:
            _una_vuelta_de_microfono(estado, detener, tabla, microfono)
            fallos = 0
        except Exception as error:      # noqa: BLE001
            # Antes esto solo se imprimia en la terminal, que es justo la
            # ventana que nadie mira cuando está usando la app. Ahora también
            # viaja a la pantalla: un micrófono ocupado por otro programa, o
            # desenchufado, se veía idéntico a "no estoy tocando fuerte".
            print(f"  El hilo de audio se corto: {error}")
            estado.error_de_audio = str(error)
            fallos += 1

        if detener.is_set():
            break

        if fallos >= INTENTOS_DE_MICROFONO:
            if not estado.error_de_audio:
                estado.error_de_audio = (
                    "el microfono dejo de entregar audio y no pude reabrirlo"
                )
            break

        # Si `ventanas()` se agotó sin excepción, no hubo error: el micrófono
        # se quedó callado y volvemos a intentar sin contarlo como falla dura.
        time.sleep(ESPERA_ENTRE_INTENTOS)

    estado.escuchando = False


def _una_vuelta_de_microfono(estado, detener, tabla, microfono):
    """
    Abre el micrófono y analiza hasta que se corte. Lo llama `escuchar`.

    Está separado nada más que para que el bucle de reintentos de arriba se
    lea de un vistazo: acá adentro no hay ninguna decisión sobre reabrir.
    """
    with microfono.CapturaMicrofono(dispositivo=estado.dispositivo) as captura:
        estado.frecuencia_muestreo = captura.frecuencia_muestreo
        estado.escuchando = True
        estado.error_de_audio = ""

        # Los tiempos arrancan de cero en cada apertura, así que la historia
        # anterior no se puede mezclar con la nueva: quedaría una nota de
        # veinte segundos donde hubo un corte.
        mediciones = []
        eventos = []
        ultimo_recalculo = -1.0
        ventanas_en_pantalla = int(
            config.SEGUNDOS_EN_PANTALLA * estado.frecuencia_muestreo
            / config.SALTO_VENTANA
        )

        for instante, ventana in captura.ventanas():
            if detener.is_set():
                return

            # Los pedidos del otro hilo. Son dos y se atienden acá porque
            # este es el hilo que tiene la captura en la mano.
            pedido = estado.tomar_pedido()
            if pedido == "arrancar":
                mediciones = []
                eventos = []
                captura.olvidar_lo_grabado()
                estado.inicio_grabacion_seg = instante
            elif pedido == "cerrar":
                estado.mediciones = list(mediciones)
                estado.audio_grabado = captura.audio_grabado()
                estado.grabacion_lista = True

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

            # Sin grabar solo mostramos: ni el audio ni la historia larga
            # le sirven a nadie, y las dos crecen para siempre.
            if not estado.grabando:
                captura.olvidar_lo_grabado()
                if len(mediciones) > ventanas_en_pantalla * 2:
                    del mediciones[:-ventanas_en_pantalla]


def encender_microfono(clase):
    """
    Arranca el hilo de audio si no esta andando. Idempotente a proposito.

    Lo llaman el arranque del servidor y el cambio de microfono en Ajustes, y
    ninguno de los dos deberia tener que saber si ya habia uno prendido.
    """
    if clase.hilo_audio is not None and clase.hilo_audio.is_alive():
        return False

    clase.estado.error_de_audio = ""
    clase.estado.escuchando = True
    clase.detener = threading.Event()
    clase.hilo_audio = threading.Thread(
        target=escuchar, args=(clase.estado, clase.detener), daemon=True
    )
    clase.hilo_audio.start()
    return True


def apagar_microfono(clase):
    """Corta el hilo de audio y espera a que termine."""
    if clase.detener is not None:
        clase.detener.set()
    if clase.hilo_audio is not None:
        clase.hilo_audio.join(timeout=3.0)
    clase.hilo_audio = None
    clase.detener = None
    clase.estado.escuchando = False


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
            "titulo": datos.get("titulo", ""),
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


class FrasePendiente:
    """
    Una frase grabada o importada que todavia no tiene nombre.

    Vive en memoria entre que terminaste de tocar y que decidis guardarla o
    tirarla. Es UNA sola: grabar otra la reemplaza. No hace falta mas, porque
    la decision se toma en el momento, mirando lo que salio.
    """

    def __init__(self, eventos, muestras, frecuencia_muestreo, tonalidad,
                 posicion, escala, origen, nombre_sugerido="", sirve=True,
                 motivo="", avisos=None):
        self.eventos = eventos
        self.muestras = muestras
        self.frecuencia_muestreo = frecuencia_muestreo
        self.tonalidad = tonalidad
        self.posicion = posicion
        self.escala = escala
        self.origen = origen                    # "microfono" o "archivo"
        self.nombre_sugerido = nombre_sugerido
        self.sirve = sirve
        self.motivo = motivo
        self.avisos = avisos or []

    def como_diccionario(self):
        reconocidas = [e for e in self.eventos if e.nota is not None]
        duracion = 0.0
        if reconocidas:
            duracion = reconocidas[-1].fin_seg - reconocidas[0].inicio_seg
        return {
            "origen": self.origen,
            "nombre_sugerido": self.nombre_sugerido,
            "tonalidad": self.tonalidad,
            "posicion": self.posicion,
            "notas": len(reconocidas),
            "duracion_seg": round(duracion, 1),
            "tab": [e.como_tab() for e in reconocidas],
            "sirve": self.sirve,
            "motivo": self.motivo,
            "avisos": self.avisos,
            "hay_audio": self.muestras is not None and len(self.muestras) > 0,
        }


class SesionPendiente:
    """
    Una sesion grabada que todavia no tiene nombre ni se escribio al disco.

    Es la misma idea que FrasePendiente, y por el mismo motivo: primero ves lo
    que grabaste, despues decidis. Y aca se agrega la pregunta que solo tiene
    sentido DESPUES de tocar: sobre que base estabas, a cuantos BPM. Con eso
    la app puede medir el ritmo, que es lo unico de los tres controles del
    proyecto que la pantalla nunca habia podido hacer.
    """

    def __init__(self, eventos, muestras, frecuencia_muestreo, mediciones,
                 tonalidad, posicion, escala):
        self.eventos = eventos
        self.muestras = muestras
        self.frecuencia_muestreo = frecuencia_muestreo
        self.mediciones = mediciones
        self.tonalidad = tonalidad
        self.posicion = posicion
        self.escala = escala

    def como_diccionario(self):
        reconocidas = [e for e in self.eventos if e.nota is not None]
        duracion = 0.0
        if reconocidas:
            duracion = reconocidas[-1].fin_seg - reconocidas[0].inicio_seg
        tabs = [e.como_tab() for e in reconocidas]
        return {
            "tonalidad": self.tonalidad,
            "posicion": self.posicion,
            "notas": len(reconocidas),
            "duracion_seg": round(duracion, 1),
            "tab": tabs[:48],
            "hay_mas": len(tabs) > 48,
            "hay_audio": self.muestras is not None and len(self.muestras) > 0,
        }


def ritmo_como_diccionario(analisis):
    """
    El analisis ritmico listo para la pantalla.

    Lleva `confiable`, que es lo que decide si los numeros se muestran como
    diagnostico o como "esto no significa nada": ver ritmo.ajuste_vs_azar.
    Sin ese campo la pantalla podria mostrar "dispersion 63 ms" con toda
    seriedad sobre una medicion que no explica lo tocado.
    """
    figura = {1: "negras", 2: "corcheas", 3: "tresillos",
              4: "semicorcheas"}.get(analisis.subdivision,
                                     f"1/{analisis.subdivision}")
    ajuste = analisis.ajuste_vs_azar()
    confiable = analisis.la_grilla_explica_algo()
    return {
        "bpm": analisis.bpm,
        "subdivision": analisis.subdivision,
        "figura": figura,
        "notas_medidas": len(analisis.desvios),
        "dispersion_ms": round(analisis.dispersion_ms()),
        "sesgo_ms": round(analisis.sesgo_ms()),
        "mediana_ms": round(analisis.mediana_ms()),
        "a_tiempo_pct": round(analisis.porcentaje_a_tiempo()),
        "tolerancia_ms": round(config.TOLERANCIA_RITMO_MS),
        "ajuste_vs_azar": round(ajuste, 2) if ajuste is not None else None,
        "confiable": bool(confiable),
        # Las frases de diagnostico SOLO si la grilla explica algo. Si no,
        # seria afirmar cosas sobre una medicion que no significa nada.
        "diagnostico": list(ritmo.diagnostico(analisis)) if confiable else [],
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

    # La frase grabada o importada que todavia no guardaste. Ver
    # FrasePendiente.
    pendiente = None
    sesion_pendiente = None

    # Si la app puede prender el microfono sola. La pone arrancar(), y los
    # tests la dejan en False: ahi el microfono no se abre nunca, que es lo
    # que permite probar todo el servidor sin una placa de sonido.
    audio_automatico = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=CARPETA_WEB, **kwargs)

    def log_message(self, formato, *args):
        """Silencia el registro de cada pedido, que llena la terminal."""

    def end_headers(self):
        """
        Nada se cachea. Nunca.

        POR QUE ESTO ARREGLA UN ERROR DE VERDAD

        Las respuestas JSON ya decian no-store, pero los archivos de la pagina
        —index.html, app.js, estilo.css— los servia SimpleHTTPRequestHandler,
        que solo manda Last-Modified. Sin un Cache-Control, el navegador aplica
        cache HEURISTICA: se guarda el archivo y durante horas ni pregunta si
        cambio.

        El resultado es de los peores que hay: actualizas la app, la abris, y
        seguis usando la version anterior sin ninguna senal. Paso: los botones
        nuevos no aparecian y el viejo, que estaba deshabilitado, "no hacia
        nada".

        Esto corre en tu maquina y los archivos pesan unos kilobytes: no hay
        nada que ganar cacheandolos.
        """
        if not self._puse_cache:
            self._puse_cache = True
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def send_header(self, palabra, valor):
        if palabra.lower() == "cache-control":
            self._puse_cache = True
        super().send_header(palabra, valor)

    _puse_cache = False

    def handle_one_request(self):
        # Cada pedido arranca con la cuenta en cero: el mismo objeto atiende
        # varios pedidos seguidos cuando la conexion se reutiliza.
        self._puse_cache = False
        super().handle_one_request()

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
        if self.path == "/api/frases/pendiente":
            return self._responder_json(self._pendiente_actual())
        if self.path == "/api/sesiones/pendiente":
            return self._responder_json(self._sesion_pendiente_actual())
        if self.path == "/api/listas":
            return self._responder_json({"listas": frases.listar_listas()})
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
        if self.path == "/api/sesiones/guardar":
            return self._responder_json(self._guardar_sesion_pendiente(cuerpo))
        if self.path == "/api/sesiones/descartar":
            return self._responder_json(self._descartar_sesion())
        if self.path == "/api/frases/guardar":
            return self._responder_json(self._guardar_frase_pendiente(cuerpo))
        if self.path == "/api/frases/descartar":
            return self._responder_json(self._descartar_pendiente())
        if self.path == "/api/frases/lista":
            return self._responder_json(self._asignar_a_lista(cuerpo))
        if self.path == "/api/listas/crear":
            return self._responder_json(self._crear_lista(cuerpo))
        if self.path == "/api/listas/renombrar":
            return self._responder_json(self._renombrar_lista(cuerpo))
        if self.path == "/api/listas/borrar":
            return self._responder_json(self._borrar_lista(cuerpo))
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
            # El nombre del archivo, sin extension: es la sugerencia de nombre
            # cuando importas. "lick_de_lean.ogg" -> "lick_de_lean".
            "archivo": os.path.splitext(os.path.basename(
                (parametros.get("archivo", [""])[0] or "").strip()))[0],
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
        """
        Empieza a GRABAR. El microfono ya venia encendido.

        Antes esto tambien prendia el microfono, y por eso habia que apretar un
        boton para que la pantalla mostrara algo. Ahora la app escucha desde
        que la abris y esto solo marca desde donde guardar.
        """
        clase = type(self)
        estado = clase.estado

        if estado.grabando:
            return {"ok": False, "motivo": "ya esta grabando"}

        peticion = peticion or {}
        modo = peticion.get("modo", "sesion")
        nombre = (peticion.get("nombre") or "").strip()

        # Grabar una frase ya no pide nombre: se lo pones al terminar, cuando
        # viste lo que salio. Practicar si, porque hay que saber contra cual.
        if modo == "practicar" and not nombre:
            return {"ok": False, "motivo": "falta el nombre de la frase"}

        if modo == "practicar" and frases.buscar(nombre) is None:
            return {"ok": False, "motivo": f"no encontre la frase {nombre!r}"}

        # Por si el microfono se cayo (lo desenchufaste, otro programa lo tomo).
        if clase.audio_automatico:
            encender_microfono(clase)

        estado.reiniciar()
        estado.modo = modo
        estado.nombre_frase = nombre
        estado.grabando = True
        estado.pedir("arrancar")
        return {"ok": True}

    def _esperar_la_grabacion(self, segundos=2.0):
        """
        Espera a que el hilo de audio deje el audio y las mediciones.

        El hilo de audio es el que tiene la captura, asi que es el unico que
        puede cerrar una grabacion. Este hilo le avisa y espera.

        Si no hay hilo —en los tests, donde nunca se abre el microfono— vuelve
        enseguida y se guarda lo que haya en el estado, que es justamente lo
        que esos tests ponen a mano.
        """
        clase = type(self)
        if clase.hilo_audio is None or not clase.hilo_audio.is_alive():
            return

        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            if clase.estado.grabacion_lista:
                return
            time.sleep(0.02)

    def _terminar(self):
        clase = type(self)
        estado = clase.estado

        estado.grabando = False
        estado.pedir("cerrar")
        self._esperar_la_grabacion()

        # Los tres modos graban igual; lo que cambia es que se hace despues.
        if estado.modo == "frase":
            return self._terminar_grabando_frase(estado)
        if estado.modo == "practicar":
            return self._terminar_practicando(estado)

        return self._terminar_sesion(estado)

    def _terminar_sesion(self, estado):
        """
        Termina la sesion. NO la guarda: la deja pendiente, como las frases.

        Al terminar ves lo que grabaste y recien ahi le pones nombre,
        descripcion y —esto es lo nuevo— el BPM de la base sobre la que
        tocaste. Con el BPM, al guardar se mide el ritmo.
        """
        if not [e for e in estado.eventos if e.nota is not None]:
            return {
                "ok": False,
                "modo": "sesion",
                "motivo": "No se reconoció ninguna nota. Fijate que la barra "
                          "de nivel se mueva cuando tocás.",
            }

        type(self).sesion_pendiente = SesionPendiente(
            eventos=list(estado.eventos),
            muestras=estado.audio_grabado,
            frecuencia_muestreo=estado.frecuencia_muestreo,
            mediciones=list(estado.mediciones),
            tonalidad=estado.tonalidad,
            posicion=estado.posicion,
            escala=estado.escala,
        )
        return {"ok": True, "modo": "sesion",
                "pendiente": type(self).sesion_pendiente.como_diccionario()}

    def _guardar_sesion_pendiente(self, peticion):
        """
        Escribe la sesion pendiente al disco, con nombre, descripcion y BPM.

        EL BPM ES LO QUE ENCIENDE EL RITMO

        ritmo.py existe desde el paso 6 y la pantalla nunca lo pudo usar:
        solo la terminal, con --bpm. Ahora la pregunta se hace donde tiene
        sentido, despues de tocar: "¿sobre que base estabas?". Si contestas,
        se mide; si no, no se inventa nada.
        """
        clase = type(self)
        pendiente = clase.sesion_pendiente
        if pendiente is None:
            return {"ok": False, "motivo": "no hay ninguna sesion para guardar"}

        peticion = peticion or {}
        titulo = (peticion.get("titulo") or "").strip()[:80]
        comentario = (peticion.get("comentario") or "").strip()[:400]

        analisis = None
        bpm = _numero(peticion.get("bpm"))
        if bpm is not None and bpm > 0:
            subdivision = int(_numero(peticion.get("subdivision"))
                              or config.SUBDIVISION_RITMO)
            analisis = ritmo.analizar(pendiente.eventos, bpm, compas=4,
                                      subdivision=subdivision)

        rutas = exportacion.guardar_sesion(
            pendiente.eventos,
            tonalidad=pendiente.tonalidad,
            posicion=pendiente.posicion,
            escala=pendiente.escala,
            muestras=pendiente.muestras,
            frecuencia_muestreo=pendiente.frecuencia_muestreo,
            analisis_ritmico=analisis,
            titulo=titulo,
            comentario=comentario,
        )

        resumen = self._resumen_de(pendiente.eventos, pendiente.tonalidad,
                                   pendiente.posicion, pendiente.escala,
                                   analisis)
        clase.sesion_pendiente = None
        clase.estado.ultimo_guardado = {q: os.path.basename(r)
                                        for q, r in rutas.items()}
        return {
            "ok": True,
            "guardado": clase.estado.ultimo_guardado,
            "resumen": resumen,
            "ritmo": ritmo_como_diccionario(analisis) if analisis else None,
        }

    def _descartar_sesion(self):
        type(self).sesion_pendiente = None
        return {"ok": True}

    def _sesion_pendiente_actual(self):
        pendiente = type(self).sesion_pendiente
        if pendiente is None:
            return {"ok": True, "pendiente": None}
        return {"ok": True, "pendiente": pendiente.como_diccionario()}

    def _terminar_grabando_frase(self, estado):
        """
        Termina de grabar una frase. NO la guarda: la deja pendiente.

        POR QUE EL NOMBRE VA DESPUES Y NO ANTES

        Antes habia que escribir el nombre antes de grabar, y al terminar la
        frase se guardaba sola. Dos problemas. El primero es que no sabes que
        va a salir hasta que lo tocas: capaz te sale mal y la queres tirar, y
        ya tenia nombre. El segundo es que lo unico que confirmaba el guardado
        era una linea de texto chiquita: la primera frase de Bruno se perdio
        sin que se diera cuenta.

        Ahora al terminar aparece lo que se grabo —tablatura, notas, duracion—
        y ahi decidis: le pones nombre, descripcion y lista, y la guardas. O la
        descartas. Lo grabado queda en memoria hasta que elijas.
        """
        reconocidas = [e for e in estado.eventos if e.nota is not None]
        if not reconocidas:
            return {
                "ok": False,
                "modo": "frase",
                "motivo": "No se reconoció ninguna nota. Fijate que la barra "
                          "de nivel se mueva cuando tocás.",
            }

        type(self).pendiente = FrasePendiente(
            eventos=list(estado.eventos),
            muestras=estado.audio_grabado,
            frecuencia_muestreo=estado.frecuencia_muestreo,
            tonalidad=estado.tonalidad,
            posicion=estado.posicion,
            escala=estado.escala,
            origen="microfono",
        )
        return {"ok": True, "modo": "frase",
                "pendiente": type(self).pendiente.como_diccionario()}

    def _guardar_frase_pendiente(self, peticion):
        """
        Guarda la frase que quedo pendiente, con el nombre que le pusiste.

        Si ya hay una frase con ese nombre, no la pisa: avisa. Pisar seria
        perder una grabacion por un nombre repetido, y las frases de Leandro
        no se pueden volver a grabar.
        """
        clase = type(self)
        pendiente = clase.pendiente
        if pendiente is None:
            return {"ok": False, "motivo": "no hay ninguna frase para guardar"}

        peticion = peticion or {}
        nombre = (peticion.get("nombre") or "").strip()[:60]
        if not nombre:
            return {"ok": False, "motivo": "ponele un nombre a la frase"}

        if frases.buscar(nombre) is not None and not peticion.get("reemplazar"):
            return {"ok": False, "motivo": f"ya hay una frase que se llama {nombre!r}",
                    "repetida": True}

        lista = frases.limpiar_nombre_de_lista(peticion.get("lista") or "")

        try:
            frase = frases.desde_eventos(
                pendiente.eventos, nombre, pendiente.tonalidad,
                pendiente.posicion, pendiente.escala,
                comentario=(peticion.get("comentario") or "").strip()[:400],
                lista=lista,
            )
        except ValueError as error:
            return {"ok": False, "motivo": str(error)}

        ruta = frases.guardar(frase)
        if lista:
            frases.crear_lista(lista)

        # El audio queda al lado del JSON. Una frase se lee, pero sobre todo
        # se ESCUCHA: sin el audio, la referencia se convierte en una
        # tablatura y perdes justo el ritmo, que es lo que venias a buscar.
        if pendiente.muestras is not None and len(pendiente.muestras):
            audio.escribir_wav(os.path.splitext(ruta)[0] + "_audio.wav",
                               pendiente.muestras, pendiente.frecuencia_muestreo)

        # Si el control de monofonia habia dicho que no y la guardaste igual,
        # queda dicho: fue tu decision, mirando la tablatura.
        avisos = list(pendiente.avisos)
        if not pendiente.sirve and pendiente.motivo:
            avisos.append("Guardada salteando el control: " + pendiente.motivo)

        clase.pendiente = None
        return {
            "ok": True,
            "avisos": avisos,
            "frase": {
                "nombre": frase.nombre,
                "notas": frase.cantidad,
                "duracion_seg": round(frase.duracion_seg, 1),
                "tonalidad": frase.tonalidad,
                "lista": frase.lista,
                "tab": frase.tablatura(),
            },
        }

    def _descartar_pendiente(self):
        type(self).pendiente = None
        return {"ok": True}

    def _pendiente_actual(self):
        """Lo que hay para guardar, si es que hay algo. Para cuando recargas."""
        pendiente = type(self).pendiente
        if pendiente is None:
            return {"ok": True, "pendiente": None}
        return {"ok": True, "pendiente": pendiente.como_diccionario()}

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
        Transcribe un audio que subiste y lo deja PENDIENTE de guardar.

        Es la puerta de entrada de las grabaciones de Leandro y de tus propios
        audios ya grabados. No guarda nada: devuelve lo que salio —tablatura,
        notas, duracion, y si el audio sirve— y la misma pantalla que para
        una frase grabada con el microfono te deja ponerle nombre y guardarla.

        Antes esta funcion guardaba directo, y tenia un parametro "igual" para
        saltear el control de monofonia. Ya no hace falta: el control se
        muestra como aviso en la vista previa, y el que decide sos vos.
        """
        estado = type(self).estado
        _, ruta_temporal, opciones, error = self._leer_audio_subido(consulta)
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
        finally:
            os.remove(ruta_temporal)

        recortado = opciones["desde"] is not None and opciones["hasta"] is not None
        if recortado and not resultado.reconocidas:
            return {"ok": False, "motivo": "en ese pedazo del audio no hay notas"}

        # La revision va antes de contar notas: si el audio tiene una banda
        # atras, el detector no reconoce nada y el motivo util es ESE, no
        # "ninguna nota".
        sirve, motivo, avisos = transcripcion.revisar(resultado, tonalidad)
        if not resultado.reconocidas:
            return {"ok": False,
                    "motivo": motivo or "en ese audio no se reconoció ninguna nota"}

        type(self).pendiente = FrasePendiente(
            eventos=list(resultado.eventos),
            muestras=resultado.muestras,
            frecuencia_muestreo=resultado.frecuencia_muestreo,
            tonalidad=tonalidad,
            posicion=estado.posicion,
            escala=estado.escala,
            origen="archivo",
            nombre_sugerido=opciones["archivo"],
            sirve=sirve,
            motivo=motivo,
            avisos=list(avisos),
        )
        return {"ok": True, "pendiente": type(self).pendiente.como_diccionario()}

    def _intento_de_archivo(self, consulta):
        """
        Compara un .wav subido contra una frase guardada.

        Sirve para cuando ya grabaste el intento con la grabadora de Windows,
        o para comparar dos audios viejos sin volver a tocar.
        """
        nombre, ruta_temporal, _, error = self._leer_audio_subido(consulta)
        if error:
            return {"ok": False, "motivo": error}
        if not nombre:
            os.remove(ruta_temporal)
            return {"ok": False, "motivo": "contra que frase comparo?"}

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
                "comentario": frase.comentario,
                "lista": frase.lista,
                "tab": frase.tablatura()[:16],
                "hay_audio": os.path.isfile(
                    os.path.splitext(ruta)[0] + "_audio.wav"),
            })
        return {"frases": salida, "listas": frases.listar_listas()}

    def _crear_lista(self, peticion):
        nombre = frases.crear_lista((peticion or {}).get("nombre") or "")
        if not nombre:
            return {"ok": False, "motivo": "ponele un nombre a la lista"}
        return {"ok": True, "nombre": nombre, "listas": frases.listar_listas()}

    def _renombrar_lista(self, peticion):
        peticion = peticion or {}
        viejo = (peticion.get("viejo") or "").strip()
        nuevo = frases.limpiar_nombre_de_lista(peticion.get("nuevo") or "")
        if not viejo or not nuevo:
            return {"ok": False, "motivo": "faltan el nombre viejo o el nuevo"}
        movidas = frases.renombrar_lista(viejo, nuevo)
        return {"ok": True, "nombre": nuevo, "movidas": movidas,
                "listas": frases.listar_listas()}

    def _borrar_lista(self, peticion):
        """Borra la lista. Las frases quedan, sin lista: ordenar no borra."""
        nombre = ((peticion or {}).get("nombre") or "").strip()
        if not nombre:
            return {"ok": False, "motivo": "que lista?"}
        sacadas = frases.borrar_lista(nombre)
        return {"ok": True, "sacadas": sacadas, "listas": frases.listar_listas()}

    def _asignar_a_lista(self, peticion):
        """
        Pone una o varias frases en una lista. Con la lista vacia, las saca.

        Acepta varios nombres de una porque asi se usa: marcas cinco frases
        que son del mismo tema y las mandas juntas.
        """
        peticion = peticion or {}
        nombres = peticion.get("nombres") or []
        if isinstance(nombres, str):
            nombres = [nombres]
        movidas = frases.asignar_a_lista(nombres, peticion.get("lista") or "")
        return {"ok": movidas > 0, "movidas": movidas,
                "listas": frases.listar_listas()}

    def _borrar_frase(self, peticion):
        nombre = (peticion or {}).get("nombre", "")
        for guardada, ruta in frases.listar():
            if guardada == nombre:
                os.remove(ruta)
                # Y su audio, si lo tenia: sin la frase no sirve para nada.
                sobrante = os.path.splitext(ruta)[0] + "_audio.wav"
                if os.path.isfile(sobrante):
                    os.remove(sobrante)
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

        if estado.grabando:
            return {"ok": False,
                    "motivo": "no se puede cambiar mientras esta grabando"}

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

        # El hilo de audio se reinicia SIEMPRE, cambies lo que cambies. Abrio
        # el microfono viejo y no lo va a soltar solo, y ademas armo su tabla
        # de notas una sola vez al arrancar: si cambiaste de armonica y no lo
        # reiniciamos, sigue transcribiendo con la anterior.
        if clase.audio_automatico:
            apagar_microfono(clase)
            encender_microfono(clase)

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
        return self._resumen_de(estado.eventos, estado.tonalidad,
                                estado.posicion, estado.escala, None)

    def _resumen_de(self, eventos, tonalidad, posicion, escala, analisis):
        """
        El resumen de una tanda de eventos. Con `analisis` (el ritmico), las
        prioridades tambien pueden hablar del tiempo.
        """
        if not eventos:
            return {"hay": False}

        datos = modulo_resumen.resumir(eventos, tonalidad, posicion, escala)
        hallazgos, sin_medir = prioridades.analizar(
            eventos, analisis, tonalidad, posicion, escala
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
            "subdivision_ritmo": config.SUBDIVISION_RITMO,
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

    # El microfono se prende solo: podes tocar y ver sin apretar nada.
    Manejador.audio_automatico = True
    encender_microfono(Manejador)

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
