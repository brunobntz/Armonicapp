"""
main.py — El punto de entrada de la app.

Por ahora tiene un solo modo: transcribir un archivo .wav. El micrófono en vivo
llega en el paso 7, y el menú interactivo en el paso 8.

    python main.py --calibrar
    python main.py --vivo --posicion 12 --escala blues_mayor
    python main.py --wav grabacion.wav --posicion 12 --escala blues_mayor --detalle

TRES MODOS

  --calibrar   Mide el ruido de fondo de tu habitación y te dice qué umbral de
               volumen poner. Es lo primero que conviene correr, sobre todo si
               cambiaste de micrófono o de lugar.

  --vivo       Escucha el micrófono y dibuja la pantalla mientras tocás.
               Ctrl+C termina la sesión y guarda todo en sesiones/.

  --wav        Transcribe un archivo. Es el modo para calibrar y para analizar
               una grabación con calma.

Por qué el modo archivo se construyó primero: con un .wav podés correr la
transcripción cien veces cambiando umbrales en config.py y comparar los
resultados, sin volver a tocar. Cuando llegó el micrófono, el pipeline ya
estaba calibrado.
"""

import argparse
import sys

import config
from armonica import (audio, exportacion, mapeo, microfono, pantalla,
                      posiciones, prioridades, resumen as modulo_resumen,
                      ritmo, segmentacion, tablas, tono)
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


# =============================================================================
# El modo en vivo
# =============================================================================

def _calibrar():
    """
    Mide el ruido de fondo de tu habitación y sugiere el umbral de volumen.

    Es lo primero que conviene correr antes de una sesión, sobre todo si
    cambiaste de micrófono o de lugar. Un umbral mal puesto es la causa número
    uno de que la app no detecte nada o detecte de más.
    """
    print()
    print("MICROFONOS DISPONIBLES")
    print("-" * 72)
    for numero, nombre, canales in microfono.listar_dispositivos():
        marca = "  <- el que usa la app" if numero == config.DISPOSITIVO_ENTRADA else ""
        print(f"  {numero:3}  {nombre[:44]:44} ({canales} can.){marca}")

    print()
    print("Midiendo el ruido de fondo. NO TOQUES NADA durante 3 segundos...")
    mediana, pico = microfono.medir_ruido_de_fondo()

    if mediana is None:
        print("\nNo llego audio. Revisa que el microfono este conectado.")
        return 1

    sugerido = microfono.umbral_sugerido(pico)
    print()
    print(f"  Ruido de fondo: mediana {mediana:.5f}, pico {pico:.5f}")
    print(f"  Umbral actual:  {config.UMBRAL_VOLUMEN_RMS}")
    print()
    print(f"  Poné esto en config.py:   UMBRAL_VOLUMEN_RMS = {sugerido:.4f}")
    print()
    print("  Es tres veces el pico del ruido: alto para que el silencio no")
    print("  cuente como nota, bajo para que una nota floja si.")
    print()
    return 0


def sesion_en_vivo(argumentos):
    """
    Escucha el micrófono y dibuja la pantalla hasta que cortes con Ctrl+C.

    COMO ESTA ARMADO EL BUCLE

    Por cada ventana de audio que llega del micrófono hacemos lo mismo que en
    el modo archivo, pero de a una: medir volumen, detectar el tono, mapearlo a
    un agujero. La diferencia es que la segmentación en notas se rehace sobre
    todas las mediciones acumuladas.

    Eso último es deliberadamente simple y algo derrochador. Segmentar de forma
    incremental sería más eficiente, pero mucho más difícil de leer y de
    verificar, y esto anda de sobra: rehacer la segmentación de una sesión de
    diez minutos lleva milisegundos.

    LA PANTALLA SE REFRESCA APARTE

    El análisis corre 86 veces por segundo y la pantalla solo 12. Si
    redibujáramos en cada ventana, gastaríamos tiempo en dibujos que nadie
    llega a ver, y la pantalla parpadearía.
    """
    from rich.live import Live

    tonalidad = argumentos.tonalidad
    tabla = mapeo.construir_tabla_inversa(tonalidad)
    estado = pantalla.EstadoPantalla(tonalidad, argumentos.posicion,
                                     argumentos.escala)

    print()
    print(posiciones.descripcion_completa(tonalidad, argumentos.posicion,
                                          argumentos.escala)
          if argumentos.posicion else f"Armonica en {tonalidad}")
    print()
    print("Escuchando. Toca cuando quieras; Ctrl+C para terminar y guardar.")
    if argumentos.bpm:
        print("Acordate de los auriculares: si la base entra por el microfono,")
        print("el detector de tono no tiene nada que hacer.")
    print()

    mediciones = []
    eventos = []
    frecuencia_muestreo = config.FRECUENCIA_MUESTREO
    audio_grabado = None
    hubo_descartes = False

    try:
        with microfono.CapturaMicrofono() as captura:
            frecuencia_muestreo = captura.frecuencia_muestreo
            ultimo_dibujo = -1.0

            with Live(pantalla.armar(estado),
                      refresh_per_second=config.REFRESCOS_POR_SEGUNDO,
                      screen=False) as vivo:

                for instante, ventana in captura.ventanas():
                    volumen = audio.volumen_rms(ventana)

                    if volumen < config.UMBRAL_VOLUMEN_RMS:
                        frecuencia, confianza = None, 0.0
                    else:
                        frecuencia, confianza = tono.detectar_frecuencia(
                            ventana, frecuencia_muestreo
                        )

                    mediciones.append({
                        "tiempo_seg": instante,
                        "frecuencia": frecuencia,
                        "confianza": confianza,
                        "volumen": volumen,
                    })

                    nota, cents = (None, 0.0)
                    if frecuencia is not None:
                        nota, cents = mapeo.frecuencia_a_nota(
                            frecuencia, tabla_inversa=tabla
                        )

                    estado.actualizar(nota, cents, volumen, instante)

                    # Redibujar solo cuando corresponde por reloj.
                    if instante - ultimo_dibujo >= 1.0 / config.REFRESCOS_POR_SEGUNDO:
                        ultimo_dibujo = instante
                        eventos = segmentacion.segmentar(
                            mediciones, tabla,
                            frecuencia_muestreo=frecuencia_muestreo,
                        )
                        if argumentos.posicion and argumentos.escala:
                            segmentacion.marcar_escala(
                                eventos, tonalidad, argumentos.posicion,
                                argumentos.escala,
                            )
                        estado.registrar_eventos(eventos)
                        vivo.update(pantalla.armar(estado))

            audio_grabado = captura.audio_grabado()
            hubo_descartes = captura.hubo_descartes()

    except KeyboardInterrupt:
        # Es la forma NORMAL de terminar una sesion, no un error.
        pass
    except Exception as error:
        print(f"\nSe corto la captura: {error}")
        return 1

    print()
    print("Sesion terminada.")

    if hubo_descartes:
        print()
        print("  AVISO: el sistema descarto audio en algun momento, asi que la")
        print("  transcripcion puede tener huecos. Suele pasar si la computadora")
        print("  estaba ocupada con otra cosa.")

    # Rehacemos la segmentacion final sobre todo lo grabado.
    eventos = segmentacion.segmentar(mediciones, tabla,
                                     frecuencia_muestreo=frecuencia_muestreo)
    if argumentos.posicion and argumentos.escala:
        segmentacion.marcar_escala(eventos, tonalidad, argumentos.posicion,
                                   argumentos.escala)

    if not eventos:
        print()
        print("No se detecto ninguna nota.")
        print(f"El umbral de volumen esta en {config.UMBRAL_VOLUMEN_RMS}.")
        print("Corre  python main.py --calibrar  para medir el de tu habitacion.")
        return 0

    print()
    print("TABLATURA")
    print("-" * 72)
    print(segmentacion.como_tablatura(eventos))
    print()

    datos = modulo_resumen.resumir(eventos, tonalidad, argumentos.posicion,
                                   argumentos.escala)

    analisis = None
    if argumentos.bpm:
        subdivision = argumentos.subdivision or config.SUBDIVISION_RITMO
        analisis = ritmo.analizar(eventos, argumentos.bpm,
                                  compas=argumentos.compas,
                                  subdivision=subdivision)

    print(modulo_resumen.como_texto(datos, analisis))

    hallazgos, sin_medir = prioridades.analizar(
        eventos, analisis, tonalidad, argumentos.posicion, argumentos.escala
    )
    print()
    print(prioridades.imprimir(hallazgos, sin_medir))

    # La sesion en vivo SIEMPRE se guarda. Es la diferencia con el modo
    # archivo: ahi el audio ya existe, aca se pierde si no lo escribimos.
    rutas = exportacion.guardar_sesion(
        eventos, tonalidad=tonalidad, posicion=argumentos.posicion,
        escala=argumentos.escala, muestras=audio_grabado,
        frecuencia_muestreo=frecuencia_muestreo, analisis_ritmico=analisis,
    )
    print()
    print("SESION GUARDADA")
    print("-" * 72)
    for que, ruta in rutas.items():
        print(f"  {que:>8}: {ruta}")
    print()
    print("  El .wav te deja volver a analizar esta misma sesion con otros")
    print("  umbrales, sin tener que tocar de nuevo.")
    print()

    return 0


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
    parser.add_argument("--wav", default=None,
                        help="archivo .wav a transcribir")
    parser.add_argument("--vivo", action="store_true",
                        help="escucha el microfono en tiempo real")
    parser.add_argument("--calibrar", action="store_true",
                        help="mide el ruido de fondo y sugiere el umbral")
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
    parser.add_argument("--guardar", action="store_true",
                        help="escribe la sesion en sesiones/ (tab, resumen, json, audio)")
    parser.add_argument("--resumen", action="store_true",
                        help="muestra las estadisticas de la sesion")
    return parser


def main():
    preparar_consola()
    argumentos = crear_parser().parse_args()

    if argumentos.escala and argumentos.posicion is None:
        print("Para usar --escala hay que indicar tambien --posicion.")
        return 1

    if argumentos.calibrar:
        return _calibrar()

    if argumentos.vivo:
        return sesion_en_vivo(argumentos)

    if not argumentos.wav:
        print("Elegi un modo: --wav <archivo>, --vivo o --calibrar.")
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

    analisis = None
    if argumentos.bpm and eventos:
        analisis = _imprimir_ritmo(eventos, argumentos.bpm, argumentos.compas,
                                   argumentos.subdivision, argumentos.detalle)

    if eventos and argumentos.resumen:
        datos = modulo_resumen.resumir(
            eventos, argumentos.tonalidad, argumentos.posicion, argumentos.escala
        )
        print()
        print(modulo_resumen.como_texto(datos, analisis))

    if eventos:
        hallazgos, sin_medir = prioridades.analizar(
            eventos, analisis, argumentos.tonalidad,
            argumentos.posicion, argumentos.escala,
        )
        print()
        print(prioridades.imprimir(hallazgos, sin_medir))
        print()

    if eventos and argumentos.guardar:
        rutas = exportacion.guardar_sesion(
            eventos,
            tonalidad=argumentos.tonalidad,
            posicion=argumentos.posicion,
            escala=argumentos.escala,
            muestras=muestras,
            frecuencia_muestreo=frecuencia_muestreo,
            analisis_ritmico=analisis,
        )
        print("SESION GUARDADA")
        print("-" * 72)
        for que, ruta in rutas.items():
            print(f"  {que:>8}: {ruta}")
        print()

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

    ajuste = analisis.ajuste_vs_azar()
    if ajuste is not None and not analisis.la_grilla_explica_algo():
        print(f"  ATENCION: la grilla no explica lo que tocaste "
              f"(ajuste {ajuste:.2f}, donde 1.00 es azar puro).")
        print("  Los numeros de abajo NO son un diagnostico. Puede ser que el BPM")
        print("  o el compas esten mal, o que el material no sea metrico.")
        print()

    print(f"  {'Dispersion':<14} {analisis.dispersion_ms():6.0f} ms   "
          f"<- el numero a bajar")
    print(f"  {'Promedio':<14} {analisis.sesgo_ms():+6.0f} ms   "
          f"({'te adelantas' if analisis.sesgo_ms() < 0 else 'llegas tarde'})")
    print(f"  {'Mediana':<14} {analisis.mediana_ms():+6.0f} ms")
    print(f"  {'A tiempo':<14} {analisis.porcentaje_a_tiempo():6.0f} %    "
          f"(dentro de {config.TOLERANCIA_RITMO_MS:.0f} ms)")
    print()

    # Las frases de diagnostico SOLO si la grilla explica algo. Si no, seria
    # afirmar cosas sobre una medicion que no significa nada.
    if analisis.la_grilla_explica_algo():
        for frase in ritmo.diagnostico(analisis):
            print(f"  - {frase}")
    else:
        print("  Sin diagnostico de ritmo: ver el aviso de arriba.")

    if detalle:
        print()
        print("NOTA POR NOTA")
        print("-" * 72)
        print(ritmo.linea_de_tiempo(analisis))

    return analisis


if __name__ == "__main__":
    sys.exit(main())
