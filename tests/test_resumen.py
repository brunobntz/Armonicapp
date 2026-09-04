"""
Tests de armonica/resumen.py y armonica/exportacion.py.

Los eventos se arman a mano, así sabemos exactamente qué tiene que contar cada
estadística.

Cómo correrlos:   python -m pytest tests/test_resumen.py -v
"""

import json

import pytest

from armonica import exportacion, mapeo, resumen as modulo_resumen, ritmo, segmentacion


def evento(tablatura, inicio, duracion=0.4, cents=0.0, en_escala=True):
    return segmentacion.Evento(
        nota=mapeo.tab_a_nota(tablatura, "C"),
        inicio_seg=inicio, duracion_seg=duracion,
        frecuencia_hz=440.0, cents=cents, confianza=0.99,
        ventanas=30, en_escala=en_escala,
    )


def secuencia(tablaturas, paso=0.5):
    return [evento(t, i * paso) for i, t in enumerate(tablaturas)]


# =============================================================================
# Lo básico
# =============================================================================

def test_cuenta_las_notas():
    datos = modulo_resumen.resumir(secuencia(["-5", "6", "-6", "7"]))
    assert datos.cantidad_notas == 4
    assert datos.notas_reconocidas == 4


def test_calcula_la_duracion_de_la_sesion():
    """Del comienzo de la primera nota al final de la última."""
    datos = modulo_resumen.resumir(secuencia(["-5", "6", "-6"], paso=1.0))
    assert datos.duracion_seg == pytest.approx(2.4, abs=0.01)


def test_calcula_las_notas_por_minuto():
    eventos = secuencia(["-5"] * 10, paso=1.0)
    datos = modulo_resumen.resumir(eventos)
    assert datos.notas_por_minuto == pytest.approx(64, abs=2)


def test_sin_eventos_devuelve_un_resumen_vacio_sin_romperse():
    datos = modulo_resumen.resumir([])
    assert datos.cantidad_notas == 0
    assert datos.conteo_por_agujero == []
    assert "No se detecto" in modulo_resumen.como_texto(datos)


def test_mide_la_variacion_de_duracion():
    """
    Si todas las notas duran lo mismo, la variación es cero. Es el indicio de
    un fraseo plano, aunque las notas sean las correctas.
    """
    parejas = [evento("-5", i * 0.5, duracion=0.4) for i in range(10)]
    variadas = [evento("-5", i * 0.5, duracion=0.1 + 0.08 * i) for i in range(10)]

    assert modulo_resumen.resumir(parejas).variacion_duracion < 0.01
    assert modulo_resumen.resumir(variadas).variacion_duracion > 0.3


# =============================================================================
# El conteo por agujero
# =============================================================================

def test_cuenta_cada_agujero_y_los_ordena_de_mas_a_menos():
    eventos = secuencia(["-5", "-5", "-5", "6", "6", "-6"])
    datos = modulo_resumen.resumir(eventos)

    assert datos.conteo_por_agujero[0][0] == "-5"
    assert datos.conteo_por_agujero[0][1] == 3
    assert datos.conteo_por_agujero[1][1] == 2
    assert datos.conteo_por_agujero[2][1] == 1


def test_agrupa_las_notas_por_registro():
    eventos = secuencia(["-2", "-3", "-5", "6", "-6", "7", "-8", "9", "10"])
    zonas = modulo_resumen.resumir(eventos).registros_usados()

    assert zonas["grave (1-3)"] == 2
    assert zonas["medio (4-7)"] == 4
    assert zonas["agudo (8-10)"] == 3


# =============================================================================
# Los pares repetidos: el vocabulario
# =============================================================================

def test_encuentra_los_pares_de_agujeros_mas_repetidos():
    """
    El dato más interesante del resumen: los caminos que la boca ya tiene
    aprendidos. Acá el par ↓4 -> ↓5 aparece tres veces.
    """
    eventos = secuencia(["-4", "-5", "6", "-4", "-5", "7", "-4", "-5"])
    datos = modulo_resumen.resumir(eventos)

    par, cuantas = datos.pares_repetidos[0]
    assert par == ("-4", "-5")
    assert cuantas == 3


def test_los_pares_que_aparecen_una_sola_vez_no_cuentan():
    """Un par único no es un automatismo: es una nota que pasó."""
    eventos = secuencia(["-4", "-5", "6", "7", "-8"])
    assert modulo_resumen.resumir(eventos).pares_repetidos == []


def test_muestra_como_mucho_cinco_pares():
    eventos = secuencia(["-4", "-5"] * 3 + ["6", "7"] * 3 + ["-8", "9"] * 3 +
                        ["-2", "-3"] * 3 + ["4", "5"] * 3 + ["-6", "-7"] * 3)
    assert len(modulo_resumen.resumir(eventos).pares_repetidos) <= 5


def test_con_una_sola_nota_no_hay_pares():
    assert modulo_resumen.resumir(secuencia(["-5"])).pares_repetidos == []


# =============================================================================
# Contra la escala de referencia
# =============================================================================

def test_lista_los_agujeros_de_la_escala_que_no_usaste():
    eventos = secuencia(["-5", "6", "-6"])
    datos = modulo_resumen.resumir(eventos, "C", 12, "blues_mayor")

    sin_usar = datos.agujeros_de_la_escala_sin_usar
    assert sin_usar
    assert "-5" not in sin_usar          # esa si la toco
    assert "7" in sin_usar               # esa no


def test_los_agujeros_sin_usar_salen_ordenados_de_grave_a_agudo():
    """
    Ordenarlos por texto daria "↓1, ↓10, ↓2", que no le sirve a nadie.
    Se ordenan por la nota que suenan.
    """
    datos = modulo_resumen.resumir(secuencia(["-5"]), "C", 12, "blues_mayor")
    midis = [
        mapeo.tab_a_nota(t, "C").midi
        for t in datos.agujeros_de_la_escala_sin_usar
    ]
    assert midis == sorted(midis)


def test_una_nota_ambigua_no_aparece_como_no_usada():
    """
    ESTE TEST EVITA UN REPROCHE FALSO.

    En armónica de Do, el ↑3 y el ↓2 dan la misma nota (Sol4). La
    transcripción siempre la llama ↓2. Si comparáramos por texto, el ↑3
    figuraría como "no usado" aunque hubieras tocado esa nota toda la sesión.
    """
    eventos = secuencia(["-2"] * 5)
    datos = modulo_resumen.resumir(eventos, "C", 12, "blues_mayor")

    assert "3" not in datos.agujeros_de_la_escala_sin_usar
    assert "-2" not in datos.agujeros_de_la_escala_sin_usar


def test_cuenta_las_notas_fuera_de_la_escala():
    eventos = [
        evento("-5", 0.0, en_escala=True),
        evento("-5", 0.5, en_escala=True),
        evento("2", 1.0, en_escala=False),
        evento("2", 1.5, en_escala=False),
    ]
    datos = modulo_resumen.resumir(eventos, "C", 12, "blues_mayor")

    assert datos.porcentaje_fuera_de_escala == pytest.approx(50.0)
    assert datos.fuera_de_escala[0] == ("2", 2)


def test_sin_escala_de_referencia_no_se_reporta_nada_de_eso():
    datos = modulo_resumen.resumir(secuencia(["-5", "6"]))
    assert datos.agujeros_de_la_escala_sin_usar == []
    assert datos.fuera_de_escala == []


# =============================================================================
# El texto
# =============================================================================

def test_el_texto_incluye_las_secciones_principales():
    eventos = secuencia(["-4", "-5", "-4", "-5", "6", "-6", "7"])
    texto = modulo_resumen.como_texto(
        modulo_resumen.resumir(eventos, "C", 12, "blues_mayor")
    )
    for seccion in ["RESUMEN DE LA SESION", "AGUJEROS MAS USADOS", "REGISTROS",
                    "PARES MAS REPETIDOS", "ESCALA DE REFERENCIA"]:
        assert seccion in texto


def test_el_texto_avisa_cuando_el_ritmo_no_es_confiable():
    """
    Si la grilla no explica lo tocado, el resumen tiene que decirlo en vez de
    mostrar una dispersión que no significa nada.
    """
    import random

    generador = random.Random(5)
    eventos = [evento("-5", generador.uniform(0, 30)) for _ in range(40)]
    analisis = ritmo.analizar(eventos, bpm=65, subdivision=3)

    texto = modulo_resumen.como_texto(modulo_resumen.resumir(eventos), analisis)
    assert "No se pudo medir" in texto


def test_el_texto_muestra_el_ritmo_cuando_si_es_confiable():
    paso = ritmo.paso_de_grilla(60, 1)
    eventos = [evento("-5", i * paso) for i in range(20)]
    analisis = ritmo.analizar(eventos, bpm=60, subdivision=1, offset_seg=0.0)

    texto = modulo_resumen.como_texto(modulo_resumen.resumir(eventos), analisis)
    assert "Dispersion" in texto


# =============================================================================
# La exportación
# =============================================================================

def test_guarda_los_cuatro_archivos(tmp_path):
    import numpy as np

    eventos = secuencia(["-4", "-5", "6", "-6"])
    muestras = np.zeros(4410, dtype=np.float32)

    rutas = exportacion.guardar_sesion(
        eventos, "C", 12, "blues_mayor",
        muestras=muestras, frecuencia_muestreo=44100,
        carpeta=str(tmp_path),
    )

    assert set(rutas) == {"tab", "resumen", "eventos", "audio"}
    for ruta in rutas.values():
        assert (tmp_path / ruta.split("\\")[-1].split("/")[-1]).exists()


def test_sin_audio_guarda_los_otros_tres(tmp_path):
    rutas = exportacion.guardar_sesion(
        secuencia(["-4", "-5"]), "C", carpeta=str(tmp_path)
    )
    assert "audio" not in rutas
    assert len(rutas) == 3


def test_el_nombre_lleva_fecha_y_hora_ordenables():
    """
    Con este formato los archivos se ordenan solos alfabéticamente, que resulta
    ser también el orden cronológico.
    """
    from datetime import datetime

    nombre = exportacion.marca_de_tiempo(datetime(2026, 9, 4, 19, 30, 15))
    assert nombre == "2026-09-04_19-30-15"


def test_el_json_tiene_una_entrada_por_nota(tmp_path):
    eventos = secuencia(["-4", "-5", "6"])
    rutas = exportacion.guardar_sesion(eventos, "C", 12, "blues_mayor",
                                       carpeta=str(tmp_path))
    datos = exportacion.leer_sesion(rutas["eventos"])

    assert len(datos["eventos"]) == 3
    primera = datos["eventos"][0]
    assert primera["nota"]["agujero"] == 4
    assert primera["nota"]["direccion"] == "aspirado"
    assert primera["nota"]["nombre"] == "D5"


def test_el_json_guarda_con_que_parametros_se_analizo(tmp_path):
    """
    Sin esto, comparar dos sesiones podría ser comparar dos reglas distintas:
    si entre una y otra cambiamos el umbral de volumen, los números no son
    comparables y hay que poder darse cuenta.
    """
    rutas = exportacion.guardar_sesion(secuencia(["-4", "-5"]), "C",
                                       carpeta=str(tmp_path))
    configuracion = exportacion.leer_sesion(rutas["eventos"])["configuracion"]

    for clave in ["umbral_volumen_rms", "duracion_minima_seg",
                  "correccion_inicio_seg", "tolerancia_cents"]:
        assert clave in configuracion


def test_el_json_guarda_si_el_ritmo_era_confiable(tmp_path):
    """
    El dato más importante del bloque de ritmo. Si dentro de un mes alguien
    compara dispersiones entre sesiones, tiene que poder descartar las que no
    valían.
    """
    import random

    generador = random.Random(9)
    eventos = [evento("-5", generador.uniform(0, 30)) for _ in range(40)]
    analisis = ritmo.analizar(eventos, bpm=65, subdivision=3)

    rutas = exportacion.guardar_sesion(eventos, "C", analisis_ritmico=analisis,
                                       carpeta=str(tmp_path))
    datos = exportacion.leer_sesion(rutas["eventos"])

    assert datos["ritmo"]["confiable"] is False
    assert datos["ritmo"]["ajuste_vs_azar"] > 0.75


def test_sin_analisis_de_ritmo_el_json_lo_deja_en_nulo(tmp_path):
    rutas = exportacion.guardar_sesion(secuencia(["-4", "-5"]), "C",
                                       carpeta=str(tmp_path))
    assert exportacion.leer_sesion(rutas["eventos"])["ritmo"] is None


def test_el_archivo_de_tab_es_legible(tmp_path):
    import io

    eventos = secuencia(["-4", "-5", "6"])
    rutas = exportacion.guardar_sesion(eventos, "C", 12, "blues_mayor",
                                       carpeta=str(tmp_path))
    texto = io.open(rutas["tab"], encoding="utf-8").read()

    assert "Armonica en C" in texto
    assert "12a posicion" in texto
    assert "-4" in texto
    assert "D5" in texto


def test_los_archivos_se_escriben_en_utf8_con_las_flechas(tmp_path):
    """
    Las flechas ↑ ↓ no existen en la codificación vieja de Windows. Si el
    archivo no se escribiera en UTF-8, la exportación se caería o guardaría
    signos de pregunta.
    """
    import io

    rutas = exportacion.guardar_sesion(secuencia(["-4", "5"]), "C",
                                       carpeta=str(tmp_path),
                                       notacion="flechas")
    texto = io.open(rutas["tab"], encoding="utf-8").read()
    assert "↓" in texto
    assert "↑" in texto


def test_listar_sesiones_devuelve_las_mas_nuevas_primero(tmp_path):
    from datetime import datetime

    for dia in (1, 5, 3):
        exportacion.guardar_sesion(
            secuencia(["-4", "-5"]), "C", carpeta=str(tmp_path),
            momento=datetime(2026, 9, dia, 10, 0, 0),
        )

    archivos = exportacion.listar_sesiones(str(tmp_path))
    assert len(archivos) == 3
    assert "2026-09-05" in archivos[0]
    assert "2026-09-01" in archivos[-1]


def test_listar_sesiones_de_una_carpeta_que_no_existe_no_rompe():
    assert exportacion.listar_sesiones("carpeta_que_no_existe_12345") == []


def test_el_json_se_puede_volver_a_leer(tmp_path):
    """Ida y vuelta completa: guardar y recuperar tiene que dar lo mismo."""
    eventos = secuencia(["-4", "-5", "6", "-6"])
    rutas = exportacion.guardar_sesion(eventos, "C", 12, "blues_mayor",
                                       carpeta=str(tmp_path))

    datos = exportacion.leer_sesion(rutas["eventos"])
    assert datos["resumen"]["cantidad_notas"] == 4
    assert datos["configuracion"]["tonalidad"] == "C"
    assert datos["configuracion"]["posicion"] == 12
    assert json.dumps(datos)          # sigue siendo serializable
