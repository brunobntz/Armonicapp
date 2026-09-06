"""
audio.py — Entrada y salida de audio.

Por ahora solo maneja archivos .wav. El micrófono llega en el paso 7, y va a
entregar los datos EXACTAMENTE en el mismo formato, así que todo lo que
construyamos sobre archivos va a funcionar en vivo sin cambios.

Esa es la decisión de diseño del módulo: una sola forma de representar el audio,
venga de donde venga.

EL FORMATO INTERNO

Todo el audio dentro de la app es un array de numpy de números decimales
(float32) entre -1.0 y +1.0, en mono. Cada número es una MUESTRA: qué tan
desplazada estaba la membrana del micrófono en ese instante. A 44100 muestras
por segundo, un segundo de audio son 44100 números.

Los archivos .wav guardan enteros de 16 bits (de -32768 a 32767), así que al
leer dividimos por 32768 y al escribir multiplicamos. Trabajamos con decimales
adentro porque las cuentas del detector de tono se hacen con decimales, y
convertir una sola vez al principio es más simple que convertir en cada cálculo.
"""

import wave

import numpy as np

import config


# Los .wav de 16 bits guardan enteros hasta 32767. Es la constante de conversión
# entre ese mundo y el nuestro, que va de -1.0 a 1.0.
ESCALA_16_BITS = 32768.0


def leer_wav(ruta):
    """
    Lee un archivo .wav y devuelve (muestras, frecuencia_de_muestreo).

    Las muestras vienen como array de numpy en float32, mono, entre -1 y 1.
    Si el archivo es estéreo, promedia los dos canales: la armónica es una sola
    fuente de sonido y no ganamos nada manteniendo dos.

    Solo acepta 16 bits por muestra, que es lo que graba cualquier celular y lo
    que produce nuestro generador de audios de prueba. Si algún día hace falta
    otro formato, este es el lugar.
    """
    # wave.Error no hereda de ValueError, asi que sin esto un archivo que no
    # sea .wav —un mp3 o un m4a renombrado, que es lo que pasa cuando la
    # grabadora del teléfono guarda en otro formato— sube como una excepción
    # que nadie atrapa. Se traduce acá, una vez, para todos los que llaman.
    try:
        archivo_abierto = wave.open(str(ruta), "rb")
    except wave.Error as error:
        raise ValueError(
            f"El archivo {ruta} no es un .wav valido ({error}). "
            f"Si lo grabaste con el telefono, puede ser un m4a o un mp3 con "
            f"otro nombre: hay que convertirlo a .wav de 16 bits."
        )

    with archivo_abierto as archivo:
        canales = archivo.getnchannels()
        bytes_por_muestra = archivo.getsampwidth()
        frecuencia_muestreo = archivo.getframerate()
        cantidad = archivo.getnframes()

        if bytes_por_muestra != 2:
            raise ValueError(
                f"El archivo {ruta} tiene {bytes_por_muestra * 8} bits por muestra. "
                f"Esta app solo lee .wav de 16 bits."
            )

        crudo = archivo.readframes(cantidad)

    # Los bytes del archivo se interpretan como enteros de 16 bits con signo.
    enteros = np.frombuffer(crudo, dtype=np.int16)

    # Si es estéreo, los canales vienen intercalados: izq, der, izq, der...
    # Los separamos en dos columnas y promediamos.
    if canales > 1:
        enteros = enteros.reshape(-1, canales).mean(axis=1)

    muestras = enteros.astype(np.float32) / ESCALA_16_BITS
    return muestras, frecuencia_muestreo


def escribir_wav(ruta, muestras, frecuencia_muestreo=None):
    """
    Guarda un array de muestras como archivo .wav mono de 16 bits.

    Lo usa el generador de audios de prueba, y en el paso 7 lo va a usar la
    sesión en vivo para guardar lo que tocaste. Poder reprocesar el audio de
    una sesión con otros umbrales, sin volver a tocar, vale mucho al calibrar.

    Recorta los valores fuera de rango en vez de dejarlos dar la vuelta. Si una
    muestra vale 1.2 y la convertimos sin recortar, el entero se desborda y ese
    instante suena como un chasquido violento.
    """
    if frecuencia_muestreo is None:
        frecuencia_muestreo = config.FRECUENCIA_MUESTREO

    muestras = np.asarray(muestras, dtype=np.float32)
    muestras = np.clip(muestras, -1.0, 1.0)

    # 32767 y no 32768: el entero positivo más grande de 16 bits es uno menos
    # que el negativo más chico.
    enteros = (muestras * (ESCALA_16_BITS - 1)).astype(np.int16)

    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(frecuencia_muestreo)
        archivo.writeframes(enteros.tobytes())


def cortar_en_bloques(muestras, tamano=None, salto=None):
    """
    Parte una señal larga en ventanas superpuestas, que es como la analizamos.

    Devuelve una lista de (indice_de_inicio, bloque).

    ¿Por qué superpuestas? El detector de tono necesita una ventana de unos 46
    milisegundos para reconocer una nota grave. Pero si avanzáramos de a 46 ms
    tendríamos solo 21 mediciones por segundo, y notas rápidas se perderían
    entre medio. Avanzando de a 12 ms conseguimos 86 mediciones por segundo,
    cada una mirando 46 ms de audio. Las ventanas se pisan, y está bien:
    es el compromiso clásico entre ver bien la nota y verla a tiempo.

    Los dos valores están en config.py como TAMANO_VENTANA y SALTO_VENTANA.
    """
    if tamano is None:
        tamano = config.TAMANO_VENTANA
    if salto is None:
        salto = config.SALTO_VENTANA

    muestras = np.asarray(muestras)
    bloques = []

    inicio = 0
    while inicio + tamano <= len(muestras):
        bloques.append((inicio, muestras[inicio:inicio + tamano]))
        inicio += salto

    return bloques


def volumen_rms(bloque):
    """
    El volumen de un bloque, medido como RMS (raíz de la media de los cuadrados).

    Es el promedio "honesto" del volumen. No se puede promediar las muestras
    directamente porque la mitad son positivas y la mitad negativas: darían
    cero. Elevando al cuadrado primero, todo queda positivo; sacando la raíz al
    final, el resultado vuelve a estar en la misma escala que las muestras.

    Devuelve un número entre 0.0 (silencio absoluto) y 1.0 (saturado).
    Se compara contra config.UMBRAL_VOLUMEN_RMS para decidir si hay algo o no.
    """
    bloque = np.asarray(bloque, dtype=np.float64)
    if bloque.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(bloque ** 2)))


def normalizar(muestras, pico=None):
    """
    Sube (o baja) toda la señal para que su pico llegue a un valor conocido.

    POR QUÉ HACE FALTA. La ganancia del micrófono cambia todo. Dos grabaciones
    de lo mismo, una con el micrófono cerca y otra lejos, dan volúmenes muy
    distintos. Si el umbral de volumen es un número fijo, sirve para una y no
    para la otra.

    Normalizar resuelve eso: multiplica toda la señal por un número para que el
    pico quede siempre en el mismo lugar. No agrega ni saca información, igual
    que expresar un balance en miles en vez de en unidades.

    Devuelve la señal sin tocar si es puro silencio, para no dividir por cero.
    """
    if pico is None:
        pico = config.PICO_NORMALIZACION

    muestras = np.asarray(muestras, dtype=np.float32)
    maximo = float(np.max(np.abs(muestras))) if muestras.size else 0.0

    if maximo < 1e-9:
        return muestras

    return muestras * (pico / maximo)
