"""
exportacion.py — Guarda una sesión en disco.

QUE SE GUARDA Y POR QUE CADA COSA

Cuatro archivos por sesión, todos con la fecha y hora en el nombre:

    ..._tab.txt        La tablatura, para leerla o llevarla a la clase.
    ..._resumen.txt    Las estadísticas y qué atacar primero.
    ..._eventos.json   Cada nota con todos sus datos, en formato de máquina.
    ..._audio.wav      El audio crudo de la sesión.

Los dos primeros son para vos. Los dos últimos son para poder volver atrás.

EL JSON es el que permite comparar sesiones dentro de un mes y ver si el bend
del 3 mejoró. El texto se lee lindo pero no se puede procesar; el JSON sí.

EL AUDIO es el que permite REPROCESAR sin volver a tocar. Cuando ajustemos un
umbral en config.py, poder correr la transcripción otra vez sobre la misma
sesión y comparar el resultado vale muchísimo. Sin el audio, cada cambio de
parámetro obligaría a grabar de nuevo.

Todo se escribe en UTF-8 y explícito, porque los archivos llevan flechas (↑ ↓)
y en Windows el valor por defecto no las soporta.
"""

import io
import json
import os
from datetime import datetime

import config
from armonica import audio as modulo_audio
from armonica import prioridades, resumen as modulo_resumen, segmentacion


CARPETA_POR_DEFECTO = "sesiones"


def marca_de_tiempo(momento=None):
    """
    El nombre base de una sesión: 2026-09-04_19-30-15

    Con este formato los archivos se ordenan solos alfabéticamente, que resulta
    ser también el orden cronológico. Es la misma razón por la que las fechas
    se escriben así en contabilidad.
    """
    if momento is None:
        momento = datetime.now()
    return momento.strftime("%Y-%m-%d_%H-%M-%S")


def guardar_sesion(eventos, tonalidad="C", posicion=None, escala=None,
                   muestras=None, frecuencia_muestreo=None,
                   analisis_ritmico=None, carpeta=None, momento=None,
                   notacion=None):
    """
    Escribe los cuatro archivos y devuelve un diccionario con las rutas.

    `muestras` es opcional: si no le pasás audio, no guarda el .wav y los otros
    tres archivos se escriben igual.
    """
    if carpeta is None:
        carpeta = CARPETA_POR_DEFECTO

    os.makedirs(carpeta, exist_ok=True)
    base = os.path.join(carpeta, marca_de_tiempo(momento))

    datos = modulo_resumen.resumir(eventos, tonalidad, posicion, escala)
    hallazgos, sin_medir = prioridades.analizar(
        eventos, analisis_ritmico, tonalidad, posicion, escala
    )

    rutas = {}

    # --- La tablatura ---
    rutas["tab"] = base + "_tab.txt"
    _escribir(rutas["tab"], _texto_de_tab(eventos, datos, notacion))

    # --- El resumen ---
    rutas["resumen"] = base + "_resumen.txt"
    _escribir(rutas["resumen"], "\n".join([
        modulo_resumen.como_texto(datos, analisis_ritmico),
        "",
        prioridades.imprimir(hallazgos, sin_medir),
        "",
    ]))

    # --- Los eventos en JSON ---
    rutas["eventos"] = base + "_eventos.json"
    _escribir(rutas["eventos"], json.dumps(
        _sesion_a_diccionario(eventos, datos, tonalidad, posicion, escala,
                              analisis_ritmico, notacion),
        indent=2, ensure_ascii=False,
    ))

    # --- El audio ---
    if muestras is not None and len(muestras) > 0:
        rutas["audio"] = base + "_audio.wav"
        modulo_audio.escribir_wav(rutas["audio"], muestras, frecuencia_muestreo)

    return rutas


def _escribir(ruta, texto):
    """
    Escribe un archivo de texto en UTF-8, con saltos de línea de Windows.

    El `newline=""` más el `\\r\\n` explícito hacen que el archivo se vea bien
    tanto en el Bloc de notas como en cualquier editor moderno.
    """
    with io.open(ruta, "w", encoding="utf-8", newline="") as archivo:
        archivo.write(texto.replace("\n", "\r\n"))


def _texto_de_tab(eventos, datos, notacion):
    """El archivo de tablatura: encabezado corto y después la tab."""
    lineas = []
    lineas.append(f"Armonica en {datos.tonalidad}")
    if datos.posicion:
        lineas.append(f"{datos.posicion}a posicion, tocando en {datos.tonalidad_resultante}")
    if datos.escala:
        lineas.append(f"Escala de referencia: {datos.escala}")
    lineas.append(f"{datos.cantidad_notas} notas, "
                  f"{datos.duracion_seg:.0f} segundos")
    lineas.append("")
    lineas.append("-" * 60)
    lineas.append("")
    lineas.append(segmentacion.como_tablatura(eventos, notacion))
    lineas.append("")
    lineas.append("-" * 60)
    lineas.append("")
    lineas.append("Con el nombre de cada nota:")
    lineas.append("")
    lineas.append(segmentacion.como_tablatura(eventos, notacion,
                                              con_notas=True, por_linea=8))
    lineas.append("")
    return "\n".join(lineas)


def _sesion_a_diccionario(eventos, datos, tonalidad, posicion, escala,
                          analisis_ritmico, notacion):
    """
    Arma la estructura que va al JSON.

    Guardamos MAS de lo que se muestra en pantalla, a propósito. El JSON es
    para la máquina y para el futuro: si dentro de tres meses queremos comparar
    la afinación del bend del 3 entre sesiones, el dato tiene que estar.
    """
    return {
        "version": 1,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "configuracion": {
            "tonalidad": tonalidad,
            "posicion": posicion,
            "escala": escala,
            "tonalidad_resultante": datos.tonalidad_resultante,
            "notacion": notacion or config.NOTACION,
            # Los parámetros con los que se analizó. Sin esto, comparar dos
            # sesiones podría ser comparar dos reglas distintas.
            "umbral_volumen_rms": config.UMBRAL_VOLUMEN_RMS,
            "duracion_minima_seg": config.DURACION_MINIMA_SEG,
            "correccion_inicio_seg": config.CORRECCION_INICIO_SEG,
            "tolerancia_cents": config.TOLERANCIA_CENTS,
        },
        "resumen": {
            "duracion_seg": round(datos.duracion_seg, 3),
            "cantidad_notas": datos.cantidad_notas,
            "notas_reconocidas": datos.notas_reconocidas,
            "notas_por_minuto": round(datos.notas_por_minuto, 1),
            "duracion_media_ms": round(datos.duracion_media_ms, 1),
            "variacion_duracion": round(datos.variacion_duracion, 3),
            "afinacion_armonica_cents": (
                round(datos.afinacion_armonica_cents, 1)
                if datos.afinacion_armonica_cents is not None else None
            ),
            "porcentaje_fuera_de_escala": round(datos.porcentaje_fuera_de_escala, 1),
            "conteo_por_agujero": [
                {"tab": tablatura, "veces": cuantas}
                for tablatura, cuantas, _ in datos.conteo_por_agujero
            ],
            "agujeros_de_la_escala_sin_usar": datos.agujeros_de_la_escala_sin_usar,
            "pares_repetidos": [
                {"de": par[0], "a": par[1], "veces": cuantas}
                for par, cuantas in datos.pares_repetidos
            ],
        },
        "ritmo": _ritmo_a_diccionario(analisis_ritmico),
        "eventos": [_evento_a_diccionario(e, notacion) for e in eventos],
    }


def _evento_a_diccionario(evento, notacion):
    """Una nota, con todo lo que sabemos de ella."""
    datos = {
        "tab": evento.como_tab(notacion),
        "inicio_seg": round(evento.inicio_seg, 3),
        "duracion_seg": round(evento.duracion_seg, 3),
        "frecuencia_hz": round(evento.frecuencia_hz, 2),
        "cents": round(evento.cents, 1),
        "confianza": round(evento.confianza, 3),
        "ventanas": evento.ventanas,
        "en_escala": evento.en_escala,
    }

    if evento.nota is None:
        datos["nota"] = None
    else:
        datos["nota"] = {
            "agujero": evento.nota.agujero,
            "direccion": evento.nota.direccion,
            "bend": evento.nota.bend,
            "nombre": evento.nota.nombre,
            "midi": evento.nota.midi,
        }

    return datos


def _ritmo_a_diccionario(analisis):
    """
    El análisis rítmico, incluida la advertencia de si es confiable.

    Guardar `confiable` es imprescindible: si dentro de un mes alguien compara
    dispersiones entre sesiones, tiene que poder descartar las que no valían.
    """
    if analisis is None:
        return None

    ajuste = analisis.ajuste_vs_azar()

    return {
        "bpm": analisis.bpm,
        "compas": analisis.compas,
        "subdivision": analisis.subdivision,
        "offset_seg": round(analisis.offset_seg, 4),
        "confiable": analisis.la_grilla_explica_algo(),
        "ajuste_vs_azar": round(ajuste, 3) if ajuste is not None else None,
        "dispersion_ms": round(analisis.dispersion_ms(), 1),
        "sesgo_ms": round(analisis.sesgo_ms(), 1),
        "mediana_ms": round(analisis.mediana_ms(), 1),
        "porcentaje_a_tiempo": round(analisis.porcentaje_a_tiempo(), 1),
        "desvios_ms": [round(d.desvio_ms, 1) for d in analisis.desvios],
    }


# =============================================================================
# Leer sesiones guardadas
# =============================================================================

def listar_sesiones(carpeta=None):
    """Los archivos de eventos que hay guardados, del más nuevo al más viejo."""
    if carpeta is None:
        carpeta = CARPETA_POR_DEFECTO

    if not os.path.isdir(carpeta):
        return []

    archivos = [
        os.path.join(carpeta, nombre)
        for nombre in os.listdir(carpeta)
        if nombre.endswith("_eventos.json")
    ]
    return sorted(archivos, reverse=True)


def leer_sesion(ruta):
    """Lee un JSON de sesión y devuelve el diccionario."""
    with io.open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)
