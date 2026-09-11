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
import os
import sys

import config
from armonica import (afinador, audio, exportacion, frases, mapeo, menu,
                      microfono, pantalla, posiciones, prioridades,
                      resumen as modulo_resumen, ritmo, segmentacion,
                      tablas, tonalidad as modulo_tonalidad, tono,
                      transcripcion)
from armonica.consola import preparar_consola


def transcribir_archivo(ruta, tonalidad, posicion=None, escala=None,
                        detalle=False):
    """
    Transcribe un .wav y devuelve (eventos, mediciones).

    Es la cadena completa del proyecto, en cinco líneas:
        leer audio -> detectar tono -> mapear a agujeros -> agrupar -> marcar
    """
    resultado = transcripcion.desde_archivo(ruta, tonalidad, posicion, escala)

    return (resultado.eventos, resultado.mediciones,
            resultado.muestras, resultado.frecuencia_muestreo)


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


# =============================================================================
# Modo teoria: consultar una escala sin tocar
# =============================================================================

def modo_teoria(tonalidad, posicion, escala):
    """
    Muestra una escala: qué notas tiene, en qué agujeros, y cuáles piden bend.

    No usa el micrófono. Sirve para estudiar en el atril, o para responder
    "¿dónde está el Lab en 12a?" sin tener que buscarlo en una hoja.
    """
    from armonica import teoria

    if not escala:
        print("Para el modo teoria hace falta elegir una escala.")
        return 1

    resultado = teoria.agujeros_para_escala(tonalidad, posicion, escala)

    print()
    print("=" * 72)
    print(f"  {posiciones.descripcion_completa(tonalidad, posicion, escala)}")
    print("=" * 72)
    print()
    print(f"  Notas de la escala:  {' '.join(resultado.nombres_notas)}")
    print()

    corrida = resultado.desde_la_tonica(octavas=2)
    print(f"LA CORRIDA, dos octavas desde la tonica ({resultado.tonica})")
    print("-" * 72)
    print("  " + "  ".join(nota.como_tab() for nota in corrida))
    print("  " + "  ".join(nota.nombre.ljust(len(nota.como_tab()))
                           for nota in corrida))
    print()

    con_bend = [n for n in resultado.agujeros if n.bend > 0]
    print(f"TODOS LOS AGUJEROS ({len(resultado.agujeros)})")
    print("-" * 72)
    linea = "  "
    for nota in resultado.agujeros:
        marca = "*" if nota.bend > 0 else " "
        pedazo = f"{nota.como_tab()} {nota.nombre}{marca}".ljust(12)
        if len(linea) + len(pedazo) > 78:
            print(linea)
            linea = "  "
        linea += pedazo
    print(linea)

    print()
    if con_bend:
        print(f"  * pide bend ({len(con_bend)} de {len(resultado.agujeros)}): "
              + "  ".join(n.como_tab() for n in con_bend))
        print(f"    los otros {len(resultado.sin_bends())} salen con aire natural.")
    else:
        print("  Ninguno pide bend: la escala entera sale con aire natural.")

    print()
    if resultado.necesita_overblows():
        print("  Notas de la escala que esta armonica NO da (harian falta overblows):")
        print(f"    {' '.join(resultado.faltantes)}")
    else:
        print("  No falta ninguna nota: la escala esta entera en la armonica.")

    sobran, faltan = teoria.comparar_con_tabla_explicita(tonalidad, posicion, escala)
    print()
    if sobran is None:
        print("  (Esta posicion no tiene tabla escrita a mano para comparar.)")
    elif not sobran and not faltan:
        print("  Coincide con la tabla escrita a mano. Conciliado.")
    else:
        print(f"  DIFERENCIA con la tabla escrita a mano: {sobran} / {faltan}")

    _imprimir_acordes(tonalidad, posicion)
    print()

    return 0


# =============================================================================
# Modo afinador: practicar un bend con el medidor a la vista
# =============================================================================

def modo_afinador(tonalidad, objetivo=None):
    """
    Escucha el microfono y va midiendo cada intento sobre una nota.

    Es el modo que cierra el circulo del diagnostico: si el informe dice que el
    bend del 3 te cae 34 cents bajo, aca lo corregis viendo el numero al
    instante en vez de leerlo en un informe media hora despues.
    """
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text

    tabla = mapeo.construir_tabla_inversa(tonalidad)
    practica = afinador.PracticaDeBend(objetivo=objetivo)

    print()
    if objetivo is not None:
        print(f"Practicando el {objetivo.como_tab()} ({objetivo.nombre}) "
              f"en armonica de {tonalidad}.")
        print("Tocá la nota, sostenela, soltá. Repetí.")
    else:
        print(f"Afinador libre, armonica de {tonalidad}.")
    print("Ctrl+C para terminar y ver el resumen.")
    print()

    mediciones = []
    contados = set()
    frecuencia_muestreo = config.FRECUENCIA_MUESTREO

    def dibujar(nota, cents, volumen):
        lineas = []
        if nota is None:
            lineas.append(Text("   ---   ", style="dim"))
            lineas.append(Text(afinador.barra_grande(0.0), style="dim"))
        else:
            color = ("bold green" if abs(cents) <= 10
                     else "bold yellow" if abs(cents) <= 25 else "bold red")
            lineas.append(Text(f"  {nota.como_tab()}   {nota.nombre}", style=color))
            lineas.append(Text(afinador.barra_grande(cents), style=color))
            lineas.append(Text(f"  {cents:+.0f} cents", style=color))

        lineas.append(Text(""))
        if practica.cantidad():
            lineas.append(Text(
                f"  {practica.cantidad()} intentos   "
                f"promedio {practica.promedio():+.0f}   "
                f"dispersion {practica.dispersion():.0f}   "
                f"{practica.porcentaje_de_aciertos():.0f}% dentro de "
                f"{practica.tolerancia_cents:.0f} cents",
                style="dim"))
        else:
            lineas.append(Text("  (todavia no hay intentos)", style="dim"))

        titulo = (f"Practica del {objetivo.como_tab()}" if objetivo
                  else "Afinador")
        from rich.console import Group
        return Panel(Group(*lineas), title=titulo, border_style="blue")

    try:
        with microfono.CapturaMicrofono() as captura:
            frecuencia_muestreo = captura.frecuencia_muestreo
            ultimo_dibujo = -1.0
            nota_actual, cents_actual, volumen_actual = None, 0.0, 0.0

            with Live(dibujar(None, 0.0, 0.0),
                      refresh_per_second=config.REFRESCOS_POR_SEGUNDO) as vivo:

                for instante, ventana in captura.ventanas():
                    volumen_actual = audio.volumen_rms(ventana)

                    if volumen_actual < config.UMBRAL_VOLUMEN_RMS:
                        frecuencia, confianza = None, 0.0
                    else:
                        frecuencia, confianza = tono.detectar_frecuencia(
                            ventana, frecuencia_muestreo)

                    mediciones.append({
                        "tiempo_seg": instante, "frecuencia": frecuencia,
                        "confianza": confianza, "volumen": volumen_actual,
                    })

                    if frecuencia is not None:
                        nota_actual, cents_actual = mapeo.frecuencia_a_nota(
                            frecuencia, tabla_inversa=tabla)

                    if instante - ultimo_dibujo >= 1.0 / config.REFRESCOS_POR_SEGUNDO:
                        ultimo_dibujo = instante

                        # Rehacemos la segmentacion y contamos los intentos
                        # nuevos. Usamos el instante de inicio como identidad:
                        # un evento ya contado no se vuelve a contar.
                        eventos = segmentacion.segmentar(
                            mediciones, tabla,
                            frecuencia_muestreo=frecuencia_muestreo)
                        for evento in eventos:
                            clave = round(evento.inicio_seg, 3)
                            if clave in contados:
                                continue
                            # Solo contamos eventos ya terminados, o sea que no
                            # sean el ultimo: ese todavia puede crecer.
                            if evento is eventos[-1]:
                                continue
                            if practica.registrar(evento):
                                contados.add(clave)

                        vivo.update(dibujar(nota_actual, cents_actual,
                                            volumen_actual))

    except KeyboardInterrupt:
        pass
    except Exception as error:
        print(f"\nSe corto la captura: {error}")
        return 1

    # Al terminar contamos tambien el ultimo evento, que ya no va a crecer.
    eventos = segmentacion.segmentar(mediciones, tabla,
                                     frecuencia_muestreo=frecuencia_muestreo)
    for evento in eventos:
        clave = round(evento.inicio_seg, 3)
        if clave not in contados and practica.registrar(evento):
            contados.add(clave)

    # Si la armonica esta corrida, lo descontamos: eso es del instrumento.
    afinacion, cuantas = segmentacion.estimar_afinacion_armonica(eventos)
    if afinacion is not None:
        practica.afinacion_armonica = afinacion
        for intento in practica.intentos:
            intento.cents -= afinacion
        print()
        print(f"Tu armonica midio {afinacion:+.0f} cents sobre {cuantas} notas")
        print("naturales. Lo que sigue esta medido CONTRA TU ARMONICA.")

    print()
    print(afinador.resumen_en_texto(practica))
    print()
    return 0


def _sin_argumentos(argumentos):
    """
    Si el usuario no pidio ningun modo, va el menu.

    OJO AL AGREGAR MODOS NUEVOS: hay que sumarlos a esta lista. Cuando se
    agrego --acorde y no se lo sumo aca, correr "main.py --acorde Bb7" abria
    el menu y se quedaba esperando que alguien tecleara.
    """
    return not any([argumentos.wav, argumentos.vivo, argumentos.calibrar,
                    argumentos.teoria, argumentos.afinador, argumentos.acorde,
                    argumentos.frases, argumentos.grabar_frase,
                    argumentos.practicar, argumentos.web,
                    argumentos.tramos])


def _desde_el_menu(argumentos):
    """
    Corre el menu y vuelca lo elegido en el mismo objeto de argumentos.

    Asi el resto de main.py no se entera de si vino del menu o de las banderas.
    """
    try:
        eleccion = menu.correr()
    except (KeyboardInterrupt, EOFError):
        print()
        return None

    modo = eleccion.get("modo")
    argumentos.calibrar = modo == "calibrar"
    argumentos.teoria = modo == "teoria"
    argumentos.afinador = modo == "afinador"
    argumentos.vivo = modo == "vivo"

    for clave in ("tonalidad", "posicion", "escala", "wav", "bpm", "subdivision"):
        if clave in eleccion and eleccion[clave] is not None:
            setattr(argumentos, clave, eleccion[clave])

    if modo == "afinador" and eleccion.get("objetivo") is not None:
        argumentos.bend = eleccion["objetivo"].como_tab("guion")

    return argumentos


def _imprimir_acordes(tonalidad, posicion):
    """
    Los tres acordes del blues en esta posicion, con sus notas guia.

    LAS NOTAS GUIA son la 3a y la 7a del acorde, y son el concepto central de
    lo que el profe viene enseniando desde agosto. La tonica y la quinta estan
    en casi todos los acordes y no dicen nada; la 3a dice si es mayor o menor
    y la 7a es la que lo hace dominante. Con esas dos ya se escucha el acorde.

    Por eso el ejercicio del miercoles de tu atril es "una nota por acorde":
    si esa nota es una guia, con una sola nota por compas ya suena la
    progresion entera.
    """
    from armonica import teoria

    progresion = teoria.progresion_de_blues(tonalidad, posicion)

    print()
    print("EL BLUES DE DOCE COMPASES EN ESTA POSICION")
    print("-" * 72)

    fila = "  "
    for compas in progresion:
        fila += f"{compas['acorde'].nombre():<7}"
        if compas["compas"] % 4 == 0:
            print(fila)
            fila = "  "

    print()
    print("LAS NOTAS GUIA (la 3a y la 7a de cada acorde)")
    print("-" * 72)
    print("  Son las dos notas que definen el acorde. Si aterrizas en una de")
    print("  ellas en el tiempo 1 del cambio, con una sola nota por compas ya")
    print("  suena la progresion entera.")
    print()
    print(f"  {'acorde':>7}  {'3a':<18} {'7a':<18} {'tonica':<10}")

    ya_vistos = set()
    for compas in progresion:
        acorde = compas["acorde"]
        if acorde.nombre() in ya_vistos:
            continue
        ya_vistos.add(acorde.nombre())

        guias = acorde.notas_guia()
        tonica = acorde.grados[0]

        def describir(grado):
            facil = grado.el_mas_facil()
            if facil is None:
                return f"{grado.nombre_nota} (no sale)"
            otros = len(grado.agujeros) - 1
            extra = f" (+{otros})" if otros > 0 else ""
            return f"{grado.nombre_nota} = {facil.como_tab()}{extra}"

        print(f"  {acorde.nombre():>7}  "
              f"{describir(guias[0]):<18} {describir(guias[1]):<18} "
              f"{describir(tonica):<10}")

    print()
    print("  El (+n) dice en cuantos lugares mas de la armonica esta esa nota.")

    faltan = []
    for compas in progresion:
        for grado in compas["acorde"].faltantes():
            texto = f"la {grado.nombre_grado} de {compas['acorde'].nombre()} ({grado.nombre_nota})"
            if texto not in faltan:
                faltan.append(texto)
    if faltan:
        print()
        print("  Esta armonica no da: " + ", ".join(faltan) + ".")
        print("  Harian falta overblows, que no estan en V1.")


def _imprimir_arpegio(tonalidad, raiz, tipo):
    """Un acorde suelto, con todos los lugares donde cae cada grado."""
    from armonica import teoria

    acorde = teoria.arpegio(tonalidad, raiz, tipo)

    print()
    print("=" * 72)
    print(f"  ARPEGIO DE {acorde.nombre()}  en armonica de {tonalidad}")
    print("=" * 72)
    print()

    for grado in acorde.grados:
        marca = "  <- nota guia" if grado.es_guia else ""
        if not grado.disponible():
            print(f"  {grado.nombre_grado:>12}  {grado.nombre_nota:<3}  "
                  f"no sale sin overblow{marca}")
            continue
        lugares = "  ".join(nota.como_tab() for nota in grado.agujeros)
        print(f"  {grado.nombre_grado:>12}  {grado.nombre_nota:<3}  {lugares}{marca}")

    print()
    print("  Lo mas facil de cada grado, prefiriendo el registro central:")
    piezas = []
    for grado in acorde.grados:
        facil = grado.el_mas_facil()
        if facil is not None:
            piezas.append(f"{grado.nombre_grado} {facil.como_tab()}")
    print("    " + "   ".join(piezas))
    print()


def _partir_acorde(texto):
    """
    Separa "F7" en ("F", "dominante"), "Bbm" en ("Bb", "menor").

    Los sufijos son los que se usan en cualquier cifrado: nada para mayor,
    "m" para menor, "7" para dominante, "m7", "maj7", "dim7".
    """
    texto = texto.strip()

    sufijos = [
        ("maj7", "mayor7"),
        ("dim7", "disminuido7"),
        ("dim", "disminuido7"),
        ("m7", "menor7"),
        ("7", "dominante"),
        ("m", "menor"),
    ]

    for sufijo, tipo in sufijos:
        if texto.endswith(sufijo) and len(texto) > len(sufijo):
            return texto[:-len(sufijo)], tipo

    return texto, "mayor"


# =============================================================================
# Modo frases: grabar una referencia y practicar contra ella
# =============================================================================

def _escuchar_hasta_ctrl_c(tonalidad, posicion, escala, titulo):
    """
    Escucha el microfono y devuelve (eventos, audio, frecuencia_muestreo).

    Es el nucleo comun de grabar una frase y de practicarla. La diferencia
    entre los dos modos es que se hace DESPUES, no como se escucha.
    """
    tabla = mapeo.construir_tabla_inversa(tonalidad)
    estado = pantalla.EstadoPantalla(tonalidad, posicion, escala)

    print()
    print(titulo)
    print("Ctrl+C cuando termines.")
    print()

    mediciones = []
    audio_grabado = None
    frecuencia_muestreo = config.FRECUENCIA_MUESTREO

    from rich.live import Live

    try:
        with microfono.CapturaMicrofono() as captura:
            frecuencia_muestreo = captura.frecuencia_muestreo
            ultimo_dibujo = -1.0

            with Live(pantalla.armar(estado),
                      refresh_per_second=config.REFRESCOS_POR_SEGUNDO) as vivo:
                for instante, ventana in captura.ventanas():
                    volumen = audio.volumen_rms(ventana)

                    if volumen < config.UMBRAL_VOLUMEN_RMS:
                        frecuencia, confianza = None, 0.0
                    else:
                        frecuencia, confianza = tono.detectar_frecuencia(
                            ventana, frecuencia_muestreo)

                    mediciones.append({
                        "tiempo_seg": instante, "frecuencia": frecuencia,
                        "confianza": confianza, "volumen": volumen,
                    })

                    nota, cents = (None, 0.0)
                    if frecuencia is not None:
                        nota, cents = mapeo.frecuencia_a_nota(
                            frecuencia, tabla_inversa=tabla)
                    estado.actualizar(nota, cents, volumen, instante)

                    if instante - ultimo_dibujo >= 1.0 / config.REFRESCOS_POR_SEGUNDO:
                        ultimo_dibujo = instante
                        eventos = segmentacion.segmentar(
                            mediciones, tabla,
                            frecuencia_muestreo=frecuencia_muestreo)
                        estado.registrar_eventos(eventos)
                        vivo.update(pantalla.armar(estado))

            audio_grabado = captura.audio_grabado()

    except KeyboardInterrupt:
        pass

    eventos = segmentacion.segmentar(mediciones, tabla,
                                     frecuencia_muestreo=frecuencia_muestreo)
    if posicion and escala:
        segmentacion.marcar_escala(eventos, tonalidad, posicion, escala)

    return eventos, audio_grabado, frecuencia_muestreo


def _frase_desde_archivo(argumentos, nombre):
    """
    Arma una frase a partir de un .wav en vez del microfono.

    Sirve para las grabaciones que te manda el profe y para tus propios audios
    ya grabados. Devuelve (eventos, muestras, frecuencia) o None si el audio
    no sirve.

    LOS DOS CONTROLES

    Un audio que viene de afuera puede tener una banda tocando encima, y puede
    ser de otra armonica. Los dos casos dan una frase mal transcrita que queda
    guardada para siempre y arruina cada practica futura. Por eso se revisan
    antes de guardar y no despues.
    """
    print()
    print(f"Leyendo {argumentos.wav} ...")

    try:
        resultado = transcripcion.desde_archivo(
            argumentos.wav, argumentos.tonalidad,
            argumentos.posicion, argumentos.escala,
        )
    except FileNotFoundError:
        print(f"No encontre el archivo {argumentos.wav}")
        return None
    except ValueError as error:
        print(f"No pude leer el audio: {error}")
        return None

    # El recorte va antes de la revision: importa si sirve el pedazo que vas a
    # guardar, no el archivo entero. Una clase con la base sonando entre frase
    # y frase puede no pasar el control aunque el tramo elegido este limpio.
    if argumentos.desde is not None and argumentos.hasta is not None:
        print(f"Recortando de {argumentos.desde:.1f} a {argumentos.hasta:.1f} s ...")
        resultado = transcripcion.recortar(
            resultado, argumentos.desde, argumentos.hasta,
            argumentos.tonalidad, argumentos.posicion, argumentos.escala,
        )
        if not resultado.reconocidas:
            print("\nEn ese pedazo del audio no hay notas.")
            return None

    sirve, motivo, avisos = transcripcion.revisar(resultado, argumentos.tonalidad)

    if not sirve and not argumentos.igual:
        print()
        print(motivo)
        print()
        # No se guarda nada, pero se muestra lo que HABRIA salido. El umbral
        # es una heuristica, no una ley: el que reconoce si esa tablatura es
        # la frase del profe sos vos. Lo unico que la app se asegura es que
        # lo decidas MIRANDO el resultado.
        reconocidas = resultado.reconocidas
        if reconocidas:
            print("Esto es lo que habria transcrito:")
            print()
            print("  " + " ".join(e.como_tab() for e in reconocidas[:24])
                  + (" ..." if len(reconocidas) > 24 else ""))
            print()
            print("Si reconoces la frase, guardala igual agregando  --igual")
            print()
        return None

    if not sirve:
        print()
        print(f"  OJO: guardada salteando el control. {motivo}")

    for aviso in avisos:
        print()
        print(f"  OJO: {aviso}")

    return resultado.eventos, resultado.muestras, resultado.frecuencia_muestreo


def modo_grabar_frase(argumentos):
    """
    Graba una frase y la guarda como referencia para practicar despues.

    La referencia es una GRABACION y no una tablatura escrita, porque la
    tablatura no lleva ritmo. Tu propio atril lo dice: "la tablatura no
    transmite el ritmo preciso". Una grabacion lo trae incluido.
    """
    nombre = argumentos.grabar_frase

    if argumentos.wav:
        resultado = _frase_desde_archivo(argumentos, nombre)
        if resultado is None:
            return 1
        eventos, audio_grabado, frecuencia_muestreo = resultado
    else:
        eventos, audio_grabado, frecuencia_muestreo = _escuchar_hasta_ctrl_c(
            argumentos.tonalidad, argumentos.posicion, argumentos.escala,
            f"Grabando la frase de referencia: {nombre}\nToca la frase como querrias tocarla.",
        )

        reconocidas = [e for e in eventos if e.nota is not None]
        if not reconocidas:
            print()
            print("No se reconocio ninguna nota. La frase no se guardo.")
            print("Corre  python main.py --calibrar  si el microfono no engancha.")
            return 1

    try:
        frase = frases.desde_eventos(
            eventos, nombre, argumentos.tonalidad,
            argumentos.posicion, argumentos.escala,
        )
    except ValueError as error:
        print(f"\n{error}")
        return 1

    ruta = frases.guardar(frase)

    print()
    print("=" * 72)
    print(f"  FRASE GUARDADA: {frase.nombre}")
    print("=" * 72)
    print()
    print(f"  {frase.cantidad} notas en {frase.duracion_seg:.1f} segundos")
    print()
    print(frase.como_texto())
    print()
    print(f"  Archivo: {ruta}")
    print()
    print(f"  Para practicarla:")
    print(f"    python main.py --practicar \"{frase.nombre}\"")
    print()

    # Guardamos tambien el audio, por si despues queres volver a escucharla.
    if audio_grabado is not None and len(audio_grabado):
        ruta_audio = os.path.splitext(ruta)[0] + "_audio.wav"
        audio.escribir_wav(ruta_audio, audio_grabado, frecuencia_muestreo)
        print(f"  El audio quedo en {ruta_audio}")
        print()

    return 0


def modo_practicar_frase(argumentos):
    """Toca contra una frase guardada y compara."""
    frase = frases.buscar(argumentos.practicar)
    if frase is None:
        print(f"No encontre la frase {argumentos.practicar!r}.")
        guardadas = frases.listar()
        if guardadas:
            print("\nLas que tenes guardadas:")
            for nombre, _ in guardadas:
                print(f"  - {nombre}")
        else:
            print("\nTodavia no hay ninguna. Grabá una con:")
            print("  python main.py --grabar-frase \"nombre\"")
        return 1

    print()
    print("=" * 72)
    print(f"  LA FRASE: {frase.nombre}")
    print("=" * 72)
    print()
    print(frase.como_texto())
    print()
    print(f"  {frase.cantidad} notas, {frase.duracion_seg:.1f} segundos, "
          f"armonica en {frase.tonalidad}")

    if argumentos.wav:
        # El intento tambien puede venir de un archivo. Util para comparar dos
        # grabaciones viejas, o la tuya contra la del profe, sin tocar ahora.
        print()
        print(f"Comparando contra {argumentos.wav} ...")
        try:
            resultado = transcripcion.desde_archivo(
                argumentos.wav, frase.tonalidad, frase.posicion, frase.escala)
        except FileNotFoundError:
            print(f"No encontre el archivo {argumentos.wav}")
            return 1
        except ValueError as error:
            print(f"No pude leer el audio: {error}")
            return 1
        if argumentos.desde is not None and argumentos.hasta is not None:
            resultado = transcripcion.recortar(
                resultado, argumentos.desde, argumentos.hasta,
                frase.tonalidad, frase.posicion, frase.escala,
            )
        eventos = resultado.eventos
    else:
        eventos, _, _ = _escuchar_hasta_ctrl_c(
            frase.tonalidad, frase.posicion, frase.escala,
            "Ahora toca vos la misma frase.",
        )

    comparacion = frases.comparar(frase, eventos)

    print()
    print(frases.informe(comparacion))
    print()

    return 0


def modo_tramos(argumentos):
    """
    Muestra en que pedazos de una grabacion larga hay armonica.

    Sirve para las clases: el profesor habla, toca una frase, vuelve a hablar.
    Sin esto, importar la clase entera como frase de referencia da una
    referencia con diez segundos de silencio en el medio.
    """
    try:
        resultado = transcripcion.desde_archivo(
            argumentos.wav, argumentos.tonalidad,
            argumentos.posicion, argumentos.escala,
        )
    except FileNotFoundError:
        print(f"No encontre el archivo {argumentos.wav}")
        return 1
    except ValueError as error:
        print(f"No pude leer el audio: {error}")
        return 1

    tramos = frases.detectar_tramos(resultado.eventos)

    print()
    print("=" * 72)
    print(f"  {argumentos.wav}")
    print("=" * 72)
    print()

    if not tramos:
        print("  No encontre ningun tramo con armonica.")
        print()
        sirve, motivo, _ = transcripcion.revisar(resultado, argumentos.tonalidad)
        if not sirve:
            print(f"  {motivo}")
            print()
        return 1

    tocando = sum(tramo.duracion_seg for tramo in tramos)
    print(f"  {len(tramos)} tramos con armonica, "
          f"{tocando:.0f} s de {resultado.duracion_seg:.0f} "
          f"({tocando / resultado.duracion_seg * 100:.0f}% del audio).")
    print("  El resto es silencio, o alguien hablando, o la base sola.")
    print()

    for tramo in tramos:
        print(f"  {tramo.numero:>2}. {tramo.como_texto()}")
    print()

    print("  Para guardar uno como frase de referencia:")
    mejor = max(tramos, key=lambda tramo: tramo.cantidad)
    print(f'    python main.py --grabar-frase "nombre" --wav {argumentos.wav} \\')
    print(f"        --desde {mejor.desde_seg:.1f} --hasta {mejor.hasta_seg:.1f}")
    print()
    print("  Ojo: la tablatura de arriba sale del analisis del archivo entero.")
    print("  Al recortar, el analisis se rehace sobre ese pedazo solo y puede")
    print("  cambiar una nota o dos. La que vale es la del recorte.")
    print()

    return 0


def modo_listar_frases():
    """Las frases guardadas."""
    guardadas = frases.listar()

    print()
    if not guardadas:
        print("Todavia no hay frases guardadas.")
        print()
        print("Para grabar una:")
        print("  python main.py --grabar-frase \"lick de 3a\" --posicion 3")
        print()
        return 0

    print("FRASES GUARDADAS")
    print("-" * 72)
    for nombre, ruta in guardadas:
        frase = frases.cargar(ruta)
        posicion = f"{frase.posicion}a pos" if frase.posicion else "sin posicion"
        print(f"  {nombre}")
        print(f"      {frase.cantidad} notas, {frase.duracion_seg:.1f} s, "
              f"armonica en {frase.tonalidad}, {posicion}")
        print(f"      {frase.como_texto(por_linea=14).splitlines()[0]}")
    print()
    return 0


def modo_monofonia(ruta):
    """
    Mide si un archivo se puede transcribir, antes de intentarlo.

    YIN solo sabe de una nota por vez. Si le das una banda entera devuelve
    frecuencias con toda seriedad, pero son basura. Este modo pregunta primero.
    """
    try:
        muestras, frecuencia_muestreo = audio.leer_wav(ruta)
    except (ValueError, FileNotFoundError) as error:
        print(f"No pude leer {ruta}: {error}")
        return 1

    if config.NORMALIZAR_ARCHIVOS:
        muestras = audio.normalizar(muestras)

    medidas = tono.medir_monofonia(muestras, frecuencia_muestreo)

    print()
    print(tono.informe_de_monofonia(medidas, f"SE PUEDE TRANSCRIBIR {ruta}?"))
    print()
    print("  deteccion    cuantas ventanas dieron una nota clara")
    print("  estabilidad  cuantas veces dos ventanas seguidas dieron la misma")
    print("  confianza    que tan periodica era la senal")
    print("  fundamental  cuanta energia habia en la frecuencia detectada")
    print()

    if medidas["puntaje"] < 0.55:
        print("  Con varios instrumentos a la vez la transcripcion no sirve.")
        print("  Para probar si separando las pistas mejora:")
        print(f"    python -m herramientas.prueba_demucs \"{ruta}\"")
        print()

    return 0


def modo_que_tono(ruta):
    """
    Deduce con que armonica y en que tono se grabo un archivo.

    Sirve cuando te pasan una grabacion y no sabes que agarrar para tocarla
    encima.
    """
    try:
        muestras, frecuencia_muestreo = audio.leer_wav(ruta)
    except (ValueError, FileNotFoundError) as error:
        print(f"No pude leer {ruta}: {error}")
        return 1

    if config.NORMALIZAR_ARCHIVOS:
        muestras = audio.normalizar(muestras)

    # Antes de deducir nada, chequeamos que el audio sea transcribible.
    # Sobre una banda entera las notas detectadas son basura, y deducir un tono
    # a partir de basura da un tono inventado.
    calidad = tono.medir_monofonia(muestras, frecuencia_muestreo)
    if calidad["puntaje"] < 0.55:
        print()
        print(tono.informe_de_monofonia(calidad, f"NO SE PUEDE ANALIZAR {ruta}"))
        print()
        print("  Las notas que se detectan en este audio no son confiables, asi")
        print("  que deducir un tono a partir de ellas seria inventarlo.")
        print()
        return 1

    # Probamos con las cuatro armonicas y nos quedamos con la transcripcion de
    # la que mejor cubra lo tocado. Con la armonica equivocada muchas notas
    # caerian fuera de su alcance y se perderian.
    mejor = None
    for candidata in tablas.TONALIDADES:
        eventos = segmentacion.segmentar(
            tono.detectar_en_senal(muestras, frecuencia_muestreo),
            mapeo.construir_tabla_inversa(candidata),
            frecuencia_muestreo=frecuencia_muestreo,
        )
        reconocidas = sum(1 for e in eventos if e.nota is not None)
        if mejor is None or reconocidas > mejor[0]:
            mejor = (reconocidas, eventos)

    analisis = modulo_tonalidad.analizar(mejor[1])
    print()
    print(modulo_tonalidad.informe(analisis, ruta))
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
    parser.add_argument("--teoria", action="store_true",
                        help="consulta una escala, sin microfono")
    parser.add_argument("--afinador", action="store_true",
                        help="practica la afinacion de un bend")
    parser.add_argument("--bend", default=None,
                        help="que bend practicar en el afinador (ej: -3'')")
    parser.add_argument("--acorde", default=None,
                        help="muestra el arpegio de un acorde (ej: F7, Bbm, C)")
    parser.add_argument("--grabar-frase", default=None, metavar="NOMBRE",
                        help="graba una frase de referencia (con --wav, la "
                             "importa de un archivo en vez del microfono)")
    parser.add_argument("--practicar", default=None, metavar="NOMBRE",
                        help="practica contra una frase guardada (con --wav, "
                             "compara un archivo en vez del microfono)")
    parser.add_argument("--frases", action="store_true",
                        help="lista las frases guardadas")
    parser.add_argument("--tramos", action="store_true",
                        help="busca en un .wav los tramos donde hay armonica")
    parser.add_argument("--desde", type=float, default=None, metavar="SEG",
                        help="a partir de que segundo del audio recortar")
    parser.add_argument("--hasta", type=float, default=None, metavar="SEG",
                        help="hasta que segundo del audio recortar")
    parser.add_argument("--igual", action="store_true",
                        help="importa la frase aunque no pase la revision "
                             "de monofonia (mirá primero la tablatura)")
    parser.add_argument("--monofonia", action="store_true",
                        help="mide si un .wav se puede transcribir")
    parser.add_argument("--que-tono", action="store_true",
                        help="deduce la armonica y el tono de un .wav")
    parser.add_argument("--web", action="store_true",
                        help="abre la interfaz en el navegador")
    parser.add_argument("--puerto", type=int, default=8000,
                        help="puerto del servidor web (por defecto 8000)")
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

    # Sin ningun argumento arrancamos el menu interactivo, que despues rellena
    # los mismos campos que las banderas. Menu y linea de comandos terminan en
    # el mismo codigo.
    if _sin_argumentos(argumentos):
        argumentos = _desde_el_menu(argumentos)
        if argumentos is None:
            return 0

    if argumentos.web:
        from armonica import servidor
        return servidor.arrancar(argumentos.tonalidad, argumentos.posicion,
                                 argumentos.escala, argumentos.puerto)

    if argumentos.calibrar:
        return _calibrar()

    if argumentos.que_tono:
        if not argumentos.wav:
            print("Para deducir el tono hace falta --wav <archivo>.")
            return 1
        return modo_que_tono(argumentos.wav)

    if argumentos.monofonia:
        if not argumentos.wav:
            print("Para medir la monofonia hace falta --wav <archivo>.")
            return 1
        return modo_monofonia(argumentos.wav)

    if argumentos.tramos:
        if not argumentos.wav:
            print("Para buscar tramos hace falta --wav <archivo>.")
            return 1
        return modo_tramos(argumentos)

    if argumentos.frases:
        return modo_listar_frases()

    if argumentos.grabar_frase:
        return modo_grabar_frase(argumentos)

    if argumentos.practicar:
        return modo_practicar_frase(argumentos)

    if argumentos.acorde:
        raiz, tipo = _partir_acorde(argumentos.acorde)
        try:
            _imprimir_arpegio(argumentos.tonalidad, raiz, tipo)
        except ValueError as error:
            print(error)
            return 1
        return 0

    if argumentos.teoria:
        if argumentos.posicion is None:
            print("Para el modo teoria hace falta --posicion.")
            return 1
        return modo_teoria(argumentos.tonalidad, argumentos.posicion,
                           argumentos.escala)

    if argumentos.afinador:
        objetivo = None
        if argumentos.bend:
            objetivo = mapeo.tab_a_nota(argumentos.bend, argumentos.tonalidad)
        return modo_afinador(argumentos.tonalidad, objetivo)

    if argumentos.vivo:
        return sesion_en_vivo(argumentos)

    if not argumentos.wav:
        print("Elegi un modo: --wav <archivo>, --vivo, --teoria,")
        print("--afinador o --calibrar. O corre sin argumentos para el menu.")
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
    El reporte de ritmo: lo que el profe viene marcando hace ocho meses.

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
