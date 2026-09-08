"""
microfono.py — Escucha el micrófono en tiempo real.

Está separado de audio.py a propósito. audio.py maneja archivos y no depende
de nada externo; este módulo necesita sounddevice y la placa de sonido. Si
algún día llevás la app a otro lado, este es el archivo que hay que reescribir
y el resto queda igual.

POR QUE ES MAS COMPLICADO QUE LEER UN ARCHIVO

El micrófono no espera. La placa de sonido llama a una función nuestra cada vez
que junta unos milisegundos de audio, y esa llamada ocurre en un hilo aparte
con prioridad de tiempo real. Si esa función tarda, el sistema descarta audio
y aparecen huecos en la grabación.

Por eso el callback hace UNA sola cosa: copiar los datos a una cola y volver.
Nada de detectar tonos ni dibujar pantallas ahí adentro. El trabajo pesado
ocurre después, en el hilo principal, leyendo de esa cola.

Es la misma idea que anotar los movimientos primero y conciliar después: el que
registra no puede frenarse a analizar.

LAS VENTANAS SUPERPUESTAS

El micrófono entrega bloques de tamaño fijo, pero nosotros necesitamos ventanas
de 2048 muestras que avanzan de a 512. O sea que cada ventana comparte tres
cuartos de su contenido con la anterior.

Para eso guardamos un buffer: vamos pegando lo que llega y, cada vez que hay
suficiente, cortamos una ventana y avanzamos el buffer un salto.
"""

import queue

import numpy as np

import config
from armonica import audio


def listar_dispositivos():
    """
    Los micrófonos disponibles, como lista de (numero, nombre, canales).

    Se usa para poner el número correcto en config.DISPOSITIVO_ENTRADA cuando
    hay varios, que en Windows es siempre.
    """
    import sounddevice

    entradas = []
    for numero, info in enumerate(sounddevice.query_devices()):
        if info["max_input_channels"] > 0:
            entradas.append((numero, info["name"], info["max_input_channels"]))
    return entradas


class CapturaMicrofono:
    """
    Escucha el micrófono y entrega ventanas listas para analizar.

    Se usa como contexto, para que el micrófono se cierre siempre, aunque el
    programa falle o lo cortes con Ctrl+C:

        with CapturaMicrofono() as captura:
            for instante, ventana in captura.ventanas():
                ...analizar la ventana...
    """

    def __init__(self, frecuencia_muestreo=None, dispositivo=None,
                 tamano=None, salto=None, guardar_audio=True):
        self.frecuencia_muestreo = frecuencia_muestreo or config.FRECUENCIA_MUESTREO
        self.dispositivo = (dispositivo if dispositivo is not None
                            else config.DISPOSITIVO_ENTRADA)
        self.tamano = tamano or config.TAMANO_VENTANA
        self.salto = salto or config.SALTO_VENTANA
        self.guardar_audio = guardar_audio

        self._cola = queue.Queue()
        self._flujo = None
        self._buffer = np.zeros(0, dtype=np.float32)
        self._grabado = []
        self._descartes = 0

    # --- Abrir y cerrar el micrófono ---

    def __enter__(self):
        import sounddevice

        self._flujo = sounddevice.InputStream(
            samplerate=self.frecuencia_muestreo,
            device=self.dispositivo,
            channels=1,
            dtype="float32",
            blocksize=self.salto,
            callback=self._callback,
        )
        self._flujo.start()
        return self

    def __exit__(self, *_):
        if self._flujo is not None:
            self._flujo.stop()
            self._flujo.close()
            self._flujo = None
        return False

    def _callback(self, datos, cantidad, tiempo, estado):
        """
        Lo llama la placa de sonido, en otro hilo. Tiene que ser instantáneo.

        `estado` avisa si el sistema descartó audio. Lo contamos para poder
        decirlo al final: si hubo descartes, la transcripción tiene huecos, y
        conviene saberlo en vez de sospechar de la propia técnica.
        """
        if estado:
            self._descartes += 1

        # El .copy() es imprescindible: numpy nos entrega una VISTA de un buffer
        # que la placa de sonido va a reescribir enseguida. Sin copiar,
        # estaríamos analizando audio que para entonces ya cambió.
        self._cola.put(datos[:, 0].copy())

    # --- La entrega de ventanas ---

    def ventanas(self, tiempo_maximo_seg=None, esperas_vacias_maximas=5):
        """
        Generador que va entregando (instante_en_segundos, muestras).

        Produce ventanas indefinidamente hasta que cortes con Ctrl+C, o hasta
        que se cumpla `tiempo_maximo_seg` si se lo pedís.

        SOBRE `esperas_vacias_maximas`

        Si el micrófono deja de mandar audio (se desconectó, o el programa que
        lo tenía tomado lo soltó), este bucle se quedaría girando para siempre
        esperando datos que no llegan. Después de cinco segundos sin nada,
        cortamos y devolvemos el control.

        Sin esto, una sesión con el micrófono desconectado se cuelga y hay que
        matar el proceso. Apareció corriendo los tests: alimentábamos la cola
        con una cantidad fija de audio y el generador nunca terminaba.
        """
        muestras_entregadas = 0
        esperas_vacias = 0

        while True:
            if tiempo_maximo_seg is not None:
                if muestras_entregadas / self.frecuencia_muestreo >= tiempo_maximo_seg:
                    return

            try:
                trozo = self._cola.get(timeout=1.0)
                esperas_vacias = 0
            except queue.Empty:
                esperas_vacias += 1
                if esperas_vacias >= esperas_vacias_maximas:
                    return
                continue

            if self.guardar_audio:
                self._grabado.append(trozo)

            self._buffer = np.concatenate([self._buffer, trozo])

            # Mientras haya material para una ventana entera, la entregamos y
            # avanzamos el buffer un salto.
            while len(self._buffer) >= self.tamano:
                # El límite se verifica acá adentro, por VENTANA entregada, y
                # no una vez por trozo recibido. Si llegara un trozo grande de
                # una vez, chequear afuera dejaría pasar todo el trozo entero
                # antes de frenar.
                if tiempo_maximo_seg is not None:
                    if muestras_entregadas / self.frecuencia_muestreo >= tiempo_maximo_seg:
                        return

                ventana = self._buffer[:self.tamano].copy()
                instante = muestras_entregadas / self.frecuencia_muestreo

                self._buffer = self._buffer[self.salto:]
                muestras_entregadas += self.salto

                yield instante, ventana

    # --- Lo grabado ---

    def audio_grabado(self):
        """Todo lo que entró por el micrófono, para guardarlo al terminar."""
        if not self._grabado:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._grabado)

    def olvidar_lo_grabado(self):
        """
        Tira lo que se venia guardando y arranca de cero.

        Hace falta porque el micrófono queda encendido todo el tiempo que la
        app está abierta. Sin esto, estar sentado sin tocar suma diez megas de
        audio por minuto, y lo que se guardara al final sería todo lo que pasó
        desde que abriste la app y no lo que quisiste grabar.
        """
        self._grabado = []

    def hubo_descartes(self):
        """Si el sistema perdió audio en algún momento."""
        return self._descartes > 0


def medir_ruido_de_fondo(segundos=3.0, dispositivo=None):
    """
    Escucha sin que toques nada y devuelve (mediana, pico) del ruido.

    Es la calibración más importante de todas: el umbral de volumen tiene que
    quedar por encima del ruido de tu habitación y por debajo de tu nota más
    floja. Medirlo es mucho mejor que adivinarlo.
    """
    niveles = []
    with CapturaMicrofono(dispositivo=dispositivo, guardar_audio=False) as captura:
        for _, ventana in captura.ventanas(tiempo_maximo_seg=segundos):
            niveles.append(audio.volumen_rms(ventana))

    if not niveles:
        return None, None

    niveles.sort()
    return niveles[len(niveles) // 2], niveles[-1]


def umbral_sugerido(pico_de_ruido):
    """
    Un umbral de volumen razonable a partir del ruido medido.

    Tres veces el pico del ruido: alto para que el silencio no cuente como
    nota, bajo para que una nota floja sí. El piso de 0.003 evita que en una
    habitación muy silenciosa quede tan bajo que capte la respiración.
    """
    if pico_de_ruido is None:
        return config.UMBRAL_VOLUMEN_RMS
    return max(0.003, pico_de_ruido * 3)


# =============================================================================
# Modo de demostración
# =============================================================================
#
#     python -m armonica.microfono
#
# Lista los micrófonos y mide el ruido de fondo. Es lo primero que conviene
# correr antes de una sesión en vivo.

if __name__ == "__main__":
    from armonica.consola import preparar_consola

    preparar_consola()

    print("\nMICROFONOS DISPONIBLES")
    print("-" * 64)
    for numero, nombre, canales in listar_dispositivos():
        marca = "  <- el que usa la app" if numero == config.DISPOSITIVO_ENTRADA else ""
        print(f"  {numero:3}  {nombre[:44]:44} ({canales} can.){marca}")

    if config.DISPOSITIVO_ENTRADA is None:
        print("\n  config.DISPOSITIVO_ENTRADA = None: se usa el predeterminado de")
        print("  Windows. Si queres otro, pone su numero en config.py.")

    print("\nMIDIENDO EL RUIDO DE FONDO (3 segundos, no toques nada)...")
    mediana, pico = medir_ruido_de_fondo()

    if mediana is None:
        print("\n  No llego audio. Revisa que el microfono este conectado.\n")
    else:
        print(f"\n  Ruido de fondo: mediana {mediana:.5f}, pico {pico:.5f}")
        print(f"  Umbral actual en config.py: {config.UMBRAL_VOLUMEN_RMS}")
        print(f"\n  Sugerencia:  UMBRAL_VOLUMEN_RMS = {umbral_sugerido(pico):.4f}")
        print("  (tres veces el pico del ruido: alto para que el silencio no")
        print("  cuente como nota, bajo para que una nota floja si)\n")
