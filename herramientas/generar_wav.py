"""
generar_wav.py — Fabrica audios de prueba sin necesidad de tocar la armónica.

POR QUÉ EXISTE

Para probar el detector de tono hace falta audio donde sepamos con exactitud
qué nota suena en qué momento. Una grabación real no sirve para eso: si el
detector dice 442 Hz, no hay forma de saber si el detector se equivocó o si
tocaste un poco alto.

Acá generamos el sonido a partir de una tablatura. Como nosotros elegimos la
frecuencia, sabemos la respuesta exacta y podemos medir el error del detector.

CÓMO SE IMITA UNA ARMÓNICA

Una onda senoidal pura suena a pitido de test de audición, y además es
demasiado fácil para el detector: cualquier algoritmo la resuelve. Una armónica
real produce la nota MÁS una serie de armónicos, que son múltiplos de esa
frecuencia, y con volumen decreciente.

Los agregamos a propósito, porque los armónicos son justamente lo que hace
fallar a los detectores ingenuos: a veces el segundo armónico suena más fuerte
que la nota, y el detector reporta una octava de más. Si YIN acierta con
armónicos presentes, va a andar con la armónica de verdad.

También ponemos un ataque y una caída suaves. Un sonido que arranca de golpe
produce un chasquido que ensucia las primeras ventanas.

CÓMO SE USA

    python -m herramientas.generar_wav

Genera todos los archivos de prueba en audio_prueba/.
"""

import os
import sys

import numpy as np

# Permite correr este archivo directamente desde la raíz del proyecto.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from armonica import audio, mapeo, notas


# Volumen relativo de cada armónico, empezando por la nota fundamental.
# Estos valores imitan de forma gruesa el timbre de una lengüeta: la
# fundamental manda, y los armónicos van cayendo. El tercer valor es alto a
# propósito, para que el detector tenga que trabajar.
ARMONICOS = [1.0, 0.45, 0.30, 0.15, 0.08]

# Cuánto dura el ataque y la caída de cada nota, en segundos.
SUAVIZADO_SEG = 0.015


def generar_nota(frecuencia_hz, duracion_seg, frecuencia_muestreo=None,
                 volumen=0.4):
    """
    Genera una nota con timbre parecido al de una armónica.

    `volumen` va de 0 a 1. Usamos 0.4 por defecto para dejar margen: al sumar
    cinco armónicos el resultado podría pasarse de 1.0 y saturar.
    """
    if frecuencia_muestreo is None:
        frecuencia_muestreo = config.FRECUENCIA_MUESTREO

    cantidad = int(duracion_seg * frecuencia_muestreo)
    tiempo = np.arange(cantidad) / frecuencia_muestreo

    onda = np.zeros(cantidad)
    for numero, amplitud in enumerate(ARMONICOS, start=1):
        frecuencia_armonico = frecuencia_hz * numero
        # Los armónicos por encima de la mitad de la frecuencia de muestreo no
        # se pueden representar y aparecerían como frecuencias falsas más
        # graves. Es el fenómeno de "aliasing"; simplemente los salteamos.
        if frecuencia_armonico >= frecuencia_muestreo / 2:
            continue
        onda += amplitud * np.sin(2 * np.pi * frecuencia_armonico * tiempo)

    # Normalizamos y aplicamos el volumen pedido.
    if np.max(np.abs(onda)) > 0:
        onda = onda / np.max(np.abs(onda)) * volumen

    return _suavizar_bordes(onda, frecuencia_muestreo)


def generar_silencio(duracion_seg, frecuencia_muestreo=None):
    """Silencio puro. Sirve para separar notas y para probar la segmentación."""
    if frecuencia_muestreo is None:
        frecuencia_muestreo = config.FRECUENCIA_MUESTREO
    return np.zeros(int(duracion_seg * frecuencia_muestreo))


def generar_ruido(duracion_seg, frecuencia_muestreo=None, volumen=0.05):
    """
    Ruido blanco: sonido sin ninguna frecuencia definida.

    Imita el ruido de fondo de una habitación. El detector tiene que responder
    None acá: si devuelve una nota, tenemos un problema.
    """
    if frecuencia_muestreo is None:
        frecuencia_muestreo = config.FRECUENCIA_MUESTREO
    generador = np.random.default_rng(seed=42)   # semilla fija: siempre igual
    cantidad = int(duracion_seg * frecuencia_muestreo)
    return generador.normal(0, volumen, cantidad)


def generar_secuencia(tablaturas, tonalidad, duracion_nota=0.5,
                      duracion_silencio=0.15, frecuencia_muestreo=None):
    """
    Convierte una lista de tablaturas en audio.

    Ejemplo: generar_secuencia(["-2", "-3'", "4"], "C") produce el audio de
    tocar esas tres notas en una armónica en Do, con un silencio entre cada una.

    Devuelve (muestras, referencia), donde `referencia` es la lista de lo que
    debería detectarse: cada elemento dice qué tablatura, qué nota, qué
    frecuencia exacta, y en qué segundo empieza y termina. Es la respuesta
    correcta contra la cual comparar.
    """
    if frecuencia_muestreo is None:
        frecuencia_muestreo = config.FRECUENCIA_MUESTREO

    partes = []
    referencia = []
    tiempo_actual = 0.0

    for tablatura in tablaturas:
        nota = mapeo.tab_a_nota(tablatura, tonalidad)
        frecuencia = notas.midi_a_frecuencia(nota.midi)

        partes.append(generar_nota(frecuencia, duracion_nota, frecuencia_muestreo))
        referencia.append({
            "tablatura": nota.como_tab(),
            "nota": nota.nombre,
            "frecuencia": frecuencia,
            "inicio_seg": tiempo_actual,
            "fin_seg": tiempo_actual + duracion_nota,
        })
        tiempo_actual += duracion_nota

        if duracion_silencio > 0:
            partes.append(generar_silencio(duracion_silencio, frecuencia_muestreo))
            tiempo_actual += duracion_silencio

    return np.concatenate(partes), referencia


def _suavizar_bordes(onda, frecuencia_muestreo):
    """
    Sube el volumen al principio y lo baja al final, de a poco.

    Sin esto, la onda arranca y termina de golpe, y ese corte abrupto suena
    como un chasquido. El chasquido contiene todas las frecuencias a la vez y
    confunde al detector justo en el borde de la nota.
    """
    cantidad_suavizado = int(SUAVIZADO_SEG * frecuencia_muestreo)
    if cantidad_suavizado * 2 >= len(onda):
        return onda

    rampa = np.linspace(0.0, 1.0, cantidad_suavizado)
    onda = onda.copy()
    onda[:cantidad_suavizado] *= rampa
    onda[-cantidad_suavizado:] *= rampa[::-1]
    return onda


# =============================================================================
# Los archivos de prueba
# =============================================================================

# La corrida de dos octavas de la escala de blues mayor en 12a posición: lo que
# Bruno practica con el estudio de Carlos del Junco. Es el mejor material de
# prueba posible, porque incluye los tres bends del 3, el bend del 6 y notas
# naturales en los tres registros.
CORRIDA_12A = [
    "-2''", "-2", "-3'''", "-3''", "4", "-4",
    "-5", "6", "-6'", "-6", "7", "-8", "-9",
]

# El riff de blues más común de la 2a posición.
RIFF_2A = ["-2", "-3'", "4", "-4'", "-4", "-5", "6"]

# Notas naturales sueltas, de grave a agudo, para verificar el rango completo.
RANGO_COMPLETO = ["1", "-1", "2", "-2", "3", "-3", "4", "-4", "5", "-5",
                  "6", "-6", "7", "-7", "8", "-8", "9", "-9", "10", "-10"]

# Solo los bends, que son las notas más difíciles de detectar bien.
SOLO_BENDS = ["-1'", "-2'", "-2''", "-3'", "-3''", "-3'''", "-4'", "-6'",
              "8'", "9'", "10'", "10''"]


ARCHIVOS = [
    ("corrida_12a.wav", CORRIDA_12A, "C", "Corrida de blues mayor en 12a posicion"),
    ("riff_2a.wav", RIFF_2A, "C", "Riff de blues en 2a posicion"),
    ("rango_completo.wav", RANGO_COMPLETO, "C", "Las 20 notas naturales"),
    ("solo_bends.wav", SOLO_BENDS, "C", "Los doce bends de la armonica"),
    ("corrida_12a_en_sol.wav", CORRIDA_12A, "G", "La misma corrida en armonica de Sol"),
]


def generar_todos(carpeta="audio_prueba"):
    """Genera todos los archivos de prueba y devuelve lo que hizo."""
    os.makedirs(carpeta, exist_ok=True)
    generados = []

    for nombre, tablaturas, tonalidad, descripcion in ARCHIVOS:
        muestras, referencia = generar_secuencia(tablaturas, tonalidad)
        ruta = os.path.join(carpeta, nombre)
        audio.escribir_wav(ruta, muestras)
        generados.append({
            "ruta": ruta,
            "descripcion": descripcion,
            "tonalidad": tonalidad,
            "notas": len(referencia),
            "duracion": len(muestras) / config.FRECUENCIA_MUESTREO,
            "referencia": referencia,
        })

    # Uno más, con ruido de fondo antes y después, para probar los umbrales.
    muestras, _ = generar_secuencia(["4", "-4", "5"], "C")
    con_ruido = np.concatenate([
        generar_ruido(0.5),
        muestras,
        generar_ruido(0.5),
    ])
    ruta = os.path.join(carpeta, "con_ruido_de_fondo.wav")
    audio.escribir_wav(ruta, con_ruido)
    generados.append({
        "ruta": ruta,
        "descripcion": "Tres notas con ruido de fondo antes y despues",
        "tonalidad": "C",
        "notas": 3,
        "duracion": len(con_ruido) / config.FRECUENCIA_MUESTREO,
        "referencia": [],
    })

    return generados


if __name__ == "__main__":
    from armonica.consola import preparar_consola

    preparar_consola()

    print("\nGenerando audios de prueba...\n")
    for info in generar_todos():
        print(f"  {info['ruta']}")
        print(f"      {info['descripcion']}")
        print(f"      armonica en {info['tonalidad']}, {info['notas']} notas, "
              f"{info['duracion']:.1f} segundos")
        if info["referencia"]:
            tabs = " ".join(r["tablatura"] for r in info["referencia"])
            print(f"      {tabs}")
        print()

    print("Para probarlos:")
    print("  python -m armonica.tono audio_prueba/corrida_12a.wav C\n")
