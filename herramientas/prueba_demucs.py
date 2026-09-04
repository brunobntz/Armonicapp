"""
prueba_demucs.py — ¿Se puede sacar la tablatura de un tema con banda?

QUE ES ESTO

Una prueba de concepto, no una función terminada. La idea es contestar con
evidencia una pregunta concreta: si separamos un tema en pistas y nos quedamos
con la que tiene la armónica, ¿alcanza para transcribirla?

POR QUE HAY DUDAS FUNDADAS

El detector de tono es monofónico: sabe de una nota por vez. Un tema entero,
con bajo, batería, guitarra y voz, es lo contrario de eso.

Demucs separa el audio en pistas. Pero NO tiene una pista de armónica: separa
en batería, bajo, voz y "otros". La armónica cae en "otros" junto con la
guitarra, el piano y los vientos. O sea que después de separar seguimos
teniendo varios instrumentos mezclados, solo que menos.

Con audio sintético ya medimos que sacar el bajo no alcanza: una guitarra
tocando un acorde sostenido, sola, ya vuelve la señal intransciribible. Esta
herramienta sirve para ver si en un tema REAL, durante el solo de armónica,
la cosa mejora lo suficiente.

COMO SE USA

    python -m herramientas.prueba_demucs tema.wav
    python -m herramientas.prueba_demucs tema.wav --solo-medir

Con `--solo-medir` no separa nada: solo mide qué tan transcribible es el
archivo tal cual. Eso no necesita instalar Demucs y sirve para tener el punto
de partida.

QUE HACE FALTA INSTALAR

Demucs trae PyTorch, que son unos dos gigas. Conviene ponerlo en un entorno
APARTE para no ensuciar el de la app:

    python -m venv .venv-demucs
    .\\.venv-demucs\\Scripts\\Activate.ps1
    pip install demucs

Y después correr esta herramienta desde ese entorno.
"""

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from armonica import audio, mapeo, segmentacion, tono
from armonica.consola import preparar_consola


# El modelo de seis pistas separa además guitarra y piano, que es justo lo que
# más nos conviene: cuanto menos quede mezclado con la armónica, mejor.
MODELO = "htdemucs_6s"

# Las pistas que ese modelo produce. La armónica va a caer en "other".
PISTAS = ["drums", "bass", "vocals", "guitar", "piano", "other"]

# Por debajo de este puntaje la transcripción no sirve. Ver
# tono.medir_monofonia para de dónde sale el número.
PUNTAJE_MINIMO_UTIL = 0.55


def demucs_instalado():
    """Si Demucs está disponible en este entorno."""
    try:
        import demucs  # noqa: F401
        return True
    except ImportError:
        return False


def instrucciones_de_instalacion():
    return "\n".join([
        "Demucs no esta instalado en este entorno.",
        "",
        "Trae PyTorch, que son unos 2 GB. Conviene ponerlo APARTE para no",
        "ensuciar el entorno de la app:",
        "",
        "    python -m venv .venv-demucs",
        "    .\\.venv-demucs\\Scripts\\Activate.ps1",
        "    pip install demucs",
        "",
        "Y despues correr esta herramienta desde ese entorno.",
        "",
        "Mientras tanto podes usar  --solo-medir  para ver que tan",
        "transcribible es el archivo sin separar nada.",
    ])


def separar(ruta, carpeta_salida="separado"):
    """
    Corre Demucs sobre un archivo y devuelve las rutas de las pistas.

    Llama al programa por línea de comandos en vez de importar su API, porque
    la línea de comandos es lo que su documentación garantiza estable.
    """
    os.makedirs(carpeta_salida, exist_ok=True)

    comando = [
        sys.executable, "-m", "demucs",
        "-n", MODELO,
        "-o", carpeta_salida,
        str(ruta),
    ]

    print(f"  Separando con {MODELO}. Esto tarda varios minutos en CPU...")
    resultado = subprocess.run(comando, capture_output=True, text=True)

    if resultado.returncode != 0:
        print("  Demucs fallo:")
        print(resultado.stderr[-2000:])
        return {}

    nombre = os.path.splitext(os.path.basename(ruta))[0]
    carpeta = os.path.join(carpeta_salida, MODELO, nombre)

    encontradas = {}
    for pista in PISTAS:
        candidato = os.path.join(carpeta, pista + ".wav")
        if os.path.exists(candidato):
            encontradas[pista] = candidato

    return encontradas


def medir(ruta, titulo):
    """Mide qué tan transcribible es un archivo y lo imprime."""
    try:
        muestras, frecuencia_muestreo = audio.leer_wav(ruta)
    except (ValueError, FileNotFoundError) as error:
        print(f"  No pude leer {ruta}: {error}")
        return None

    if config.NORMALIZAR_ARCHIVOS:
        muestras = audio.normalizar(muestras)

    medidas = tono.medir_monofonia(muestras, frecuencia_muestreo)
    print(tono.informe_de_monofonia(medidas, titulo))
    print()
    return medidas


def transcribir(ruta, tonalidad):
    """Transcribe una pista, para ver con los ojos qué tan mal o bien salió."""
    muestras, frecuencia_muestreo = audio.leer_wav(ruta)
    if config.NORMALIZAR_ARCHIVOS:
        muestras = audio.normalizar(muestras)

    tabla = mapeo.construir_tabla_inversa(tonalidad)
    eventos = segmentacion.segmentar(
        tono.detectar_en_senal(muestras, frecuencia_muestreo),
        tabla, frecuencia_muestreo=frecuencia_muestreo,
    )
    return eventos


def main():
    preparar_consola()

    parser = argparse.ArgumentParser(
        description="Prueba si se puede transcribir un tema con banda."
    )
    parser.add_argument("archivo", help="el .wav del tema")
    parser.add_argument("--solo-medir", action="store_true",
                        help="no separa nada, solo mide el archivo tal cual")
    parser.add_argument("--tonalidad", default="C",
                        help="tonalidad de la armonica, para la transcripcion")
    argumentos = parser.parse_args()

    print()
    print("=" * 72)
    print("  PRUEBA: se puede sacar la tablatura de un tema con banda?")
    print("=" * 72)
    print()

    original = medir(argumentos.archivo, "EL TEMA ENTERO, sin separar")
    if original is None:
        return 1

    if argumentos.solo_medir:
        _conclusion_parcial(original)
        return 0

    if not demucs_instalado():
        print(instrucciones_de_instalacion())
        print()
        _conclusion_parcial(original)
        return 1

    pistas = separar(argumentos.archivo)
    if not pistas:
        print("  No se generaron pistas. Nada que medir.")
        return 1

    print()
    print("=" * 72)
    print("  CADA PISTA POR SEPARADO")
    print("=" * 72)
    print()

    resultados = {}
    for pista, ruta in pistas.items():
        medidas = medir(ruta, f"Pista: {pista}")
        if medidas is not None:
            resultados[pista] = medidas

    if not resultados:
        return 1

    mejor = max(resultados, key=lambda p: resultados[p]["puntaje"])
    puntaje_mejor = resultados[mejor]["puntaje"]

    print("=" * 72)
    print("  CONCLUSION")
    print("=" * 72)
    print()
    print(f"  Sin separar:       {original['puntaje']:.2f}")
    print(f"  La mejor pista:    {puntaje_mejor:.2f}  ({mejor})")
    print(f"  Mejora:            {puntaje_mejor - original['puntaje']:+.2f}")
    print()

    if puntaje_mejor >= PUNTAJE_MINIMO_UTIL:
        print("  SIRVE. La pista separada alcanza para transcribir, aunque con")
        print("  errores. Vale la pena seguir por este camino.")
        print()
        eventos = transcribir(pistas[mejor], argumentos.tonalidad)
        print(f"  Transcripcion de la pista '{mejor}' ({len(eventos)} notas):")
        print()
        print(segmentacion.como_tablatura(eventos))
    else:
        print("  NO ALCANZA. Ni la mejor pista llega al minimo para transcribir.")
        print()
        print("  Era el resultado esperado: Demucs no tiene una pista de")
        print("  armonica. La separa junto con la guitarra, el piano y los")
        print("  vientos, y eso sigue siendo polifonico.")
        print()
        print("  Para que esto funcione haria falta un separador entrenado")
        print("  especificamente para armonica, que no existe, o un detector")
        print("  de tono polifonico, que es otro proyecto entero.")

    print()
    return 0


def _conclusion_parcial(medidas):
    print("-" * 72)
    if medidas["puntaje"] >= PUNTAJE_MINIMO_UTIL:
        print("  Este audio ya es bastante monofonico: probá transcribirlo")
        print("  directo con main.py --wav, sin separar nada.")
    else:
        print("  Este audio es polifonico. Transcribirlo tal cual no va a dar")
        print("  nada util. Corré esta herramienta sin --solo-medir para")
        print("  probar si separandolo mejora.")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
