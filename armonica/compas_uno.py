"""
compas_uno.py — En qué segundo de un audio exportado arranca el compás 1.

Band-in-a-Box exporta la base con compases de conteo adelante: dos por
defecto, marcados con golpes de baqueta. Recién después entra la banda. Para
que el cifrado siga al audio hay que saber dónde cae ese primer compás, y el
archivo no lo dice.

Lo que sí se escucha es que los golpes de baqueta NO TIENEN GRAVES y la
banda sí: el bajo entra con el compás 1. Así que se mira la energía por
debajo de 200 Hz a lo largo del tiempo y se busca el primer instante en que
aparece. Medido sobre una exportación real a 65 BPM: los golpes caen en 0,
1,85, 3,69, 4,62 y 6,46 s (el "1, 2, 1-2-3-4" del conteo), sin graves, y el
bajo entra en 7,38 s, que son exactamente dos compases.

Como el conteo es siempre una cantidad entera de compases, el instante
encontrado se redondea al compás más cercano si está lo bastante cerca; si
no, se devuelve tal cual y se avisa que es aproximado. Y si hay graves
desde el principio, el audio no tiene conteo: el compás 1 es el segundo 0.
"""

from dataclasses import dataclass

import numpy as np

FRECUENCIA_DE_CORTE_HZ = 200.0
VENTANA_SEG = 0.01
# La energía de graves a partir de la cual "hay bajo", como fracción de la
# mediana de la energía de graves de todo el audio. Medido en la exportación
# real: los golpes de baqueta llegan al 15-20 % de la mediana (algo de grave
# tienen), la banda al 100-200 %.
FRACCION_DE_LA_MEDIANA = 0.5
# Y tiene que SOSTENERSE: un golpe de baqueta dura 30 ms y una nota de bajo
# no baja de doscientos. Es lo que separa las dos cosas cuando el golpe es
# fuerte.
DURACION_SOSTENIDA_SEG = 0.2
# Si el instante está a menos de este pedazo de compás de un múltiplo entero,
# se redondea: el conteo es de compases enteros.
TOLERANCIA_EN_COMPASES = 0.15
DURACION_MAXIMA_SEG = 120.0


@dataclass
class Resultado:
    segundos: float          # dónde cae el compás 1
    redondeado: bool         # si cayó cerca de un número entero de compases
    compases_de_conteo: float
    instante_crudo: float    # dónde aparecieron los graves, sin redondear


def detectar(muestras, frecuencia_muestreo, bpm, pulsos_por_compas=4):
    """
    Busca el compás 1 en las muestras (mono, entre -1 y 1). Devuelve un
    Resultado, o None si el audio está vacío o no se puede decidir.
    """
    if len(muestras) == 0 or bpm <= 0:
        return None

    # Solo el principio: el conteo nunca dura dos minutos.
    limite = int(min(len(muestras), DURACION_MAXIMA_SEG * frecuencia_muestreo))
    senal = np.asarray(muestras[:limite], dtype=np.float64)

    # Un pasabajos simple de primer orden, aplicado ida y vuelta para que no
    # corra el tiempo: alcanza para separar el bajo de las baquetas.
    graves = _pasabajos(senal, frecuencia_muestreo, FRECUENCIA_DE_CORTE_HZ)

    ventana = max(1, int(frecuencia_muestreo * VENTANA_SEG))
    cantidad = len(graves) // ventana
    if cantidad == 0:
        return None
    energia = np.sqrt(np.mean(graves[:cantidad * ventana].reshape(-1, ventana) ** 2, axis=1))

    referencia = float(np.median(energia))
    if referencia <= 0:
        return None
    umbral = referencia * FRACCION_DE_LA_MEDIANA
    sostenido = max(1, int(DURACION_SOSTENIDA_SEG / VENTANA_SEG))
    # El primer instante desde el cual los graves se quedan arriba del
    # umbral durante `sostenido` ventanas seguidas.
    arriba = (energia > umbral).astype(np.int32)
    if len(arriba) < sostenido:
        return None
    seguidas = np.convolve(arriba, np.ones(sostenido, dtype=np.int32), mode="valid")
    indices = np.where(seguidas == sostenido)[0]
    if len(indices) == 0:
        return None
    crudo = float(indices[0] * VENTANA_SEG)

    compas_seg = 60.0 / bpm * pulsos_por_compas
    compases = crudo / compas_seg
    entero = round(compases)
    if abs(compases - entero) <= TOLERANCIA_EN_COMPASES:
        return Resultado(segundos=round(entero * compas_seg, 3), redondeado=True,
                         compases_de_conteo=float(entero), instante_crudo=round(crudo, 3))
    return Resultado(segundos=round(crudo, 3), redondeado=False,
                     compases_de_conteo=round(compases, 2), instante_crudo=round(crudo, 3))


def desde_archivo(ruta, bpm, pulsos_por_compas=4):
    """
    Lo mismo, leyendo un archivo. Un .wav se lee directo; otro formato se
    convierte con ffmpeg si está (ver transcripcion.leer_cualquier_audio).
    Devuelve None si no se pudo leer.
    """
    from armonica import transcripcion
    try:
        muestras, frecuencia_muestreo = transcripcion.leer_cualquier_audio(ruta)
    except (ValueError, OSError, RuntimeError):
        return None
    return detectar(muestras, frecuencia_muestreo, bpm, pulsos_por_compas)


def _pasabajos(senal, frecuencia_muestreo, corte_hz):
    """Filtro RC de primer orden, ida y vuelta (fase cero)."""
    alfa = (2 * np.pi * corte_hz / frecuencia_muestreo)
    alfa = alfa / (1 + alfa)

    def una_pasada(x):
        salida = np.empty_like(x)
        acumulado = 0.0
        for i in range(len(x)):
            acumulado += alfa * (x[i] - acumulado)
            salida[i] = acumulado
        return salida

    # El bucle en Python es lento sobre millones de muestras: se decima
    # primero a 2 kHz, que sobra para mirar por debajo de 200 Hz.
    factor = max(1, int(frecuencia_muestreo // 2000))
    if factor > 1:
        senal = senal[:len(senal) // factor * factor].reshape(-1, factor).mean(axis=1)
        alfa = (2 * np.pi * corte_hz / (frecuencia_muestreo / factor))
        alfa = alfa / (1 + alfa)
    filtrada = una_pasada(una_pasada(senal)[::-1])[::-1]
    return np.repeat(filtrada, factor)[:len(senal) * factor] if factor > 1 else filtrada
