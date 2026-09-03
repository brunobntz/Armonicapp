"""
main.py — El punto de entrada de la app.

Por ahora tiene un solo modo: transcribir un archivo .wav. El micrófono en vivo
llega en el paso 7, y el menú interactivo en el paso 8.

    python main.py --wav audio_prueba/corrida_12a.wav
    python main.py --wav grabacion.wav --tonalidad C --posicion 12 --escala blues_mayor
    python main.py --wav grabacion.wav --detalle

Trabajar primero con archivos y recién después con el micrófono es a propósito.
Con un archivo podés correr la transcripción cien veces cambiando umbrales en
config.py y comparar los resultados, sin volver a tocar. Cuando llegue el
micrófono, el pipeline ya va a estar calibrado.
"""

import argparse
import sys

import config
from armonica import audio, mapeo, posiciones, ritmo, segmentacion, tablas, tono
from armonica.consola import preparar_consola


def transcribir_archivo(ruta, tonalidad, posicion=None, escala=None,
                        detalle=False):
    """
    Transcribe un .wav y devuelve (eventos, mediciones).

    Es la cadena completa del proyecto, en cinco líneas:
        leer audio -> detectar tono -> mapear a agujeros -> agrupar -> marcar
    """
    muestras, frecuencia_muestreo = audio.leer_wav(ruta)

    # Normalizar antes de analizar. Sin esto, una grabación con poco volumen
    # se descarta entera como si fuera silencio. Ver config.NORMALIZAR_ARCHIVOS.
    if config.NORMALIZAR_ARCHIVOS:
        muestras = audio.normalizar(muestras)

    mediciones = tono.detectar_en_senal(muestras, frecuencia_muestreo)

    tabla = mapeo.construir_tabla_inversa(tonalidad)
    eventos = segmentacion.segmentar(mediciones, tabla,
                                     frecuencia_muestreo=frecuencia_muestreo)

    if posicion is not None and escala:
        segmentacion.marcar_escala(eventos, tonalidad, posicion, escala)

    return eventos, mediciones, muestras, frecuencia_muestreo


def imprimir_resultado(eventos, mediciones, muestras, frecuencia_muestreo,
                       ruta, tonalidad, posicion, escala, detalle):
    """Muestra la transcripción en pantalla."""
    duracion = len(muestras) / frecuencia_muestreo
    con_tono = sum(1 for m in mediciones if m["frecuencia"] is not None)

    print(f"\n{'=' * 72}")
    print(f"  {ruta}")
    print(f"  {duracion:.2f} segundos, {frecuencia_muestreo} Hz")
    if posicion is not None:
        print(f"  {posiciones.descripcion_completa(tonalidad, posicion, escala)}")
    else:
        print(f"  Armonica en {tonalidad}")
    print(f"{'=' * 72}\n")

    print(f"Ventanas analizadas: {len(mediciones)}, con tono: {con_tono}")
    print(f"{segmentacion.resumen_corto(eventos)}\n")

    if not eventos:
        print("No se detecto ninguna nota.")
        print("\nSi grabaste algo y no aparece nada, probá bajar")
        print(f"UMBRAL_VOLUMEN_RMS en config.py (ahora vale {config.UMBRAL_VOLUMEN_RMS}).")
        return

    print("TABLATURA")
    print("-" * 72)
    print(segmentacion.como_tablatura(eventos))
    print()
    print(segmentacion.como_tablatura(eventos, con_notas=True, por_linea=8))
    print()

    if detalle:
        _imprimir_detalle(eventos, posicion, escala)


def _imprimir_detalle(eventos, posicion, escala):
    """
    Una fila por nota, con tiempos, duración y afinación.

    Es lo que más sirve para calibrar: si ves notas de 40 ms que no tocaste,
    subí DURACION_MINIMA_SEG; si una nota tuya aparece partida en dos, subí
    VENTANAS_SILENCIO_TOLERADAS.
    """
    print("DETALLE POR NOTA")
    print("-" * 72)

    encabezado = (
        f"{'#':>3} {'inicio':>8} {'dur ms':>7} {'agujero':>8} {'nota':>6} "
        f"{'Hz':>8} {'cents':>7} {'conf':>5}"
    )
    if escala:
        encabezado += "  escala"
    print(encabezado)
    print("-" * 72)

    for numero, evento in enumerate(eventos, start=1):
        linea = (
            f"{numero:3} {evento.inicio_seg:8.3f} {evento.duracion_seg * 1000:7.0f} "
            f"{evento.como_tab():>8} "
            f"{(evento.nota.nombre if evento.nota else '?'):>6} "
            f"{evento.frecuencia_hz:8.2f} {evento.cents:+7.1f} "
            f"{evento.confianza:5.2f}"
        )
        if escala:
            linea += f"  {'si' if evento.en_escala else 'NO':>6}"
        if not evento.esta_afinada():
            linea += "  <- desafinada"
        print(linea)

    print()
    _imprimir_afinacion(eventos)


def _imprimir_afinacion(eventos):
    """
    Cuán afinado tocaste cada agujero, con foco en los bends.

    Primero calcula la afinación de la armónica usando solo las notas naturales,
    y después mide los bends CONTRA ESA REFERENCIA. Sin ese paso estaríamos
    mezclando dos cosas distintas: cómo está afinado el instrumento y cómo
    tocaste vos.
    """
    afinacion, cuantas = segmentacion.estimar_afinacion_armonica(eventos)

    print("AFINACION")
    print("-" * 72)

    if afinacion is None:
        print(f"  No hay suficientes notas naturales ({cuantas}) para estimar")
        print("  la afinacion de la armonica. Se muestra todo contra La = 440.")
    else:
        equivalente = segmentacion.afinacion_equivalente_hz(afinacion)
        print(f"  Tu armonica esta {afinacion:+.0f} cents respecto de La = 440 Hz,")
        print(f"  o sea afinada como si La fuera {equivalente:.0f} Hz.")
        print(f"  (Medido sobre {cuantas} notas naturales, que las da la lengueta")
        print("  y no dependen de como soples.)")
        print()
        print("  Lo que sigue mide CONTRA TU ARMONICA, no contra el estandar.")

    por_agujero = {}
    for evento in eventos:
        if evento.nota is None:
            continue
        relativo = segmentacion.cents_relativos(evento, afinacion)
        por_agujero.setdefault(evento.como_tab(), []).append(relativo)

    bends = {k: v for k, v in por_agujero.items() if "'" in k}
    if not bends:
        return

    print()
    print(f"{'bend':>8} {'veces':>6} {'cents':>7}   {'medidor':<27}")

    for tablatura, lista in sorted(bends.items(), key=lambda x: -abs(sum(x[1]) / len(x[1]))):
        promedio = sum(lista) / len(lista)
        aviso = ""
        if promedio < -20:
            aviso = "  te pasas de bend"
        elif promedio > 20:
            aviso = "  te falta bend"
        print(f"{tablatura:>8} {len(lista):6} {promedio:+7.0f}   "
              f"{_barra_de_cents(promedio)}{aviso}")

    print()
    print("  El medidor va de -50 a +50 cents. El | del medio es la nota justa.")
    print("  A la izquierda bajaste de mas; a la derecha te quedaste corto.")


def _barra_de_cents(cents, ancho=25):
    """
    Dibuja un medidor de afinación de texto:  [-----|--o------]

    Es el adelanto en papel del medidor que va a estar en vivo en el paso 7.
    """
    medio = ancho // 2
    posicion = int(medio + (cents / 50.0) * medio)
    posicion = max(0, min(ancho - 1, posicion))

    casillas = ["-"] * ancho
    casillas[medio] = "|"
    casillas[posicion] = "o"
    return "[" + "".join(casillas) + "]"


def crear_parser():
    parser = argparse.ArgumentParser(
        description="Transcribe armonica a tablatura.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python main.py --wav audio_prueba/corrida_12a.wav\n"
            "  python main.py --wav mi_grabacion.wav --posicion 12 "
            "--escala blues_mayor --detalle\n"
        ),
    )
    parser.add_argument("--wav", required=True,
                        help="archivo .wav a transcribir")
    parser.add_argument("--tonalidad", default="C",
                        choices=sorted(tablas.TONALIDADES),
                        help="tonalidad de la armonica (por defecto C)")
    parser.add_argument("--posicion", type=int, default=None,
                        choices=range(1, 13), metavar="1-12",
                        help="posicion en la que estas tocando")
    parser.add_argument("--escala", default=None,
                        choices=sorted(tablas.ESCALAS_INTERVALOS),
                        help="escala de referencia")
    parser.add_argument("--detalle", action="store_true",
                        help="muestra una fila por nota, con tiempos y afinacion")
    parser.add_argument("--bpm", type=float, default=None,
                        help="velocidad de la base, para analizar el ritmo")
    parser.add_argument("--subdivision", type=int, default=None,
                        help="1=negras 2=corcheas 3=tresillos (por defecto, config)")
    parser.add_argument("--compas", type=int, default=4,
                        help="pulsos por compas (4 para un 4/4)")
    parser.add_argument("--estimar-bpm", action="store_true",
                        help="intenta adivinar la velocidad de la base")
    return parser


def main():
    preparar_consola()
    argumentos = crear_parser().parse_args()

    if argumentos.escala and argumentos.posicion is None:
        print("Para usar --escala hay que indicar tambien --posicion.")
        return 1

    try:
        resultado = transcribir_archivo(
            argumentos.wav,
            argumentos.tonalidad,
            argumentos.posicion,
            argumentos.escala,
            argumentos.detalle,
        )
    except FileNotFoundError:
        print(f"No encontre el archivo {argumentos.wav}")
        return 1
    except ValueError as error:
        print(f"No pude leer el audio: {error}")
        return 1

    eventos, mediciones, muestras, frecuencia_muestreo = resultado
    imprimir_resultado(
        eventos, mediciones, muestras, frecuencia_muestreo,
        argumentos.wav, argumentos.tonalidad,
        argumentos.posicion, argumentos.escala, argumentos.detalle,
    )

    if argumentos.estimar_bpm and argumentos.bpm is None:
        argumentos.bpm = _estimar_y_avisar(eventos, argumentos.subdivision)

    if argumentos.bpm and eventos:
        _imprimir_ritmo(eventos, argumentos.bpm, argumentos.compas,
                        argumentos.subdivision, argumentos.detalle)

    return 0


def _estimar_y_avisar(eventos, subdivision):
    """Estima el BPM y avisa que hay que mirarlo con desconfianza."""
    if subdivision is None:
        subdivision = config.SUBDIVISION_RITMO

    bpm, error = ritmo.estimar_bpm(eventos, subdivision=subdivision)
    if bpm is None:
        print()
        print("No hay notas suficientes para estimar la velocidad.")
        return None

    print()
    print(f"Velocidad estimada: {bpm:.0f} BPM")
    print("  Ojo: estimar el tempo desde las notas es poco confiable. Si tocaste")
    print("  parejo, el doble y la mitad explican lo mismo. Cuando sepas el BPM")
    print("  de tu base, pasalo con --bpm y confia en ese.")
    return bpm


def _imprimir_ritmo(eventos, bpm, compas, subdivision, detalle):
    """
    El reporte de ritmo: lo que Leandro viene marcando hace ocho meses.

    Va al final del informe a propósito, pero es lo que hay que leer primero.
    """
    if subdivision is None:
        subdivision = config.SUBDIVISION_RITMO

    analisis = ritmo.analizar(eventos, bpm, compas=compas, subdivision=subdivision)

    figura = {1: "negras", 2: "corcheas", 3: "tresillos",
              4: "semicorcheas"}.get(subdivision, f"1/{subdivision}")

    print()
    print("=" * 72)
    print("  RITMO")
    print("=" * 72)
    print(f"  Base a {bpm:.0f} BPM, compas de {compas}, midiendo contra {figura}.")
    print(f"  Cada pulso dura {analisis.duracion_pulso_seg * 1000:.0f} ms; "
          f"la grilla tiene un punto cada "
          f"{ritmo.paso_de_grilla(bpm, subdivision) * 1000:.0f} ms.")
    print()

    print(f"  {'Dispersion':<14} {analisis.dispersion_ms():6.0f} ms   "
          f"<- el numero a bajar")
    print(f"  {'Promedio':<14} {analisis.sesgo_ms():+6.0f} ms   "
          f"({'te adelantas' if analisis.sesgo_ms() < 0 else 'llegas tarde'})")
    print(f"  {'Mediana':<14} {analisis.mediana_ms():+6.0f} ms")
    print(f"  {'A tiempo':<14} {analisis.porcentaje_a_tiempo():6.0f} %    "
          f"(dentro de {config.TOLERANCIA_RITMO_MS:.0f} ms)")
    print()

    for frase in ritmo.diagnostico(analisis):
        print(f"  - {frase}")

    if detalle:
        print()
        print("NOTA POR NOTA")
        print("-" * 72)
        print(ritmo.linea_de_tiempo(analisis))


if __name__ == "__main__":
    sys.exit(main())
