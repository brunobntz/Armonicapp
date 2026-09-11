"""
Tests de armonica/mapeo.py — de frecuencia a agujero de la armónica.

Todo con frecuencias fijas, sin micrófono. Los valores en Hz son los reales de
cada nota: 440 Hz es el La de la orquesta, 261.63 Hz el Do central.

Cómo correrlos:   python -m pytest tests/test_mapeo.py -v
"""

import pytest

import config
from armonica import mapeo, notas, tablas
from armonica.mapeo import ASPIRADO, SOPLADO


# Armamos las tablas una sola vez para todos los tests del archivo.
TABLA_C = mapeo.construir_tabla_inversa("C")
TABLA_G = mapeo.construir_tabla_inversa("G")
TABLA_D = mapeo.construir_tabla_inversa("D")
TABLA_A = mapeo.construir_tabla_inversa("A")


def hz(nombre_nota):
    """Atajo para los tests: 'Bb4' -> 466.16 Hz. Hace los tests legibles."""
    return notas.midi_a_frecuencia(notas.nombre_a_midi(nombre_nota))


# =============================================================================
# Notas naturales en armónica de Do — los casos que hay que saber de memoria
# =============================================================================

def test_do_central_es_el_agujero_uno_soplado():
    """261.63 Hz en una armónica en Do es el agujero 1 soplado."""
    nota, cents = mapeo.frecuencia_a_nota(261.63, tabla_inversa=TABLA_C)
    assert nota.agujero == 1
    assert nota.direccion == SOPLADO
    assert nota.bend == 0
    assert nota.nombre == "C4"
    assert nota.como_tab() == "1"
    assert abs(cents) < 5


def test_el_cuatro_soplado_es_una_octava_arriba():
    nota, _ = mapeo.frecuencia_a_nota(523.25, tabla_inversa=TABLA_C)
    assert nota.como_tab() == "4"
    assert nota.nombre == "C5"


def test_el_tres_aspirado_es_si():
    """493.88 Hz = B4. En armónica de Do es el 3 aspirado, sin bend."""
    nota, _ = mapeo.frecuencia_a_nota(493.88, tabla_inversa=TABLA_C)
    assert nota.agujero == 3
    assert nota.direccion == ASPIRADO
    assert nota.bend == 0
    assert nota.como_tab() == "-3"


def test_el_cinco_aspirado_es_fa():
    """El 5 aspirado es la tónica de la 12a posición, que es lo que estudia Bruno."""
    nota, _ = mapeo.frecuencia_a_nota(hz("F5"), tabla_inversa=TABLA_C)
    assert nota.como_tab() == "-5"
    assert nota.nombre == "F5"


def test_el_diez_soplado_es_la_nota_mas_aguda():
    nota, _ = mapeo.frecuencia_a_nota(2093.0, tabla_inversa=TABLA_C)
    assert nota.como_tab() == "10"
    assert nota.nombre == "C7"


# =============================================================================
# BENDS — el corazón del paso, y donde más fácil se cometen errores
# =============================================================================

def test_bend_de_medio_tono_en_el_tres_aspirado():
    """
    466.16 Hz = Sib4. Es el primer bend del 3 aspirado.
    El profe lo llama "1º bend: Bb". Es la 4ª de Fa en 12a posición.
    """
    nota, _ = mapeo.frecuencia_a_nota(466.16, tabla_inversa=TABLA_C)
    assert nota.agujero == 3
    assert nota.direccion == ASPIRADO
    assert nota.bend == 1
    assert nota.nombre == "Bb4"
    assert nota.como_tab() == "-3'"


def test_bend_de_un_tono_en_el_tres_aspirado():
    """
    440 Hz = La4. Es el segundo bend del 3, y es la tónica de la 4a posición.
    Justo el agujero que tenés con fuga de aire.
    """
    nota, _ = mapeo.frecuencia_a_nota(440.0, tabla_inversa=TABLA_C)
    assert nota.agujero == 3
    assert nota.bend == 2
    assert nota.nombre == "A4"
    assert nota.como_tab() == "-3''"


def test_bend_del_seis_aspirado_es_la_bemol():
    """
    El "-6'" es Lab. Es la nota guía del acorde de Sib en el blues en Fa, la
    que el profe subrayó el 11/08 y confirmó el 18/08. Y es la única blue note
    de la escala de blues en 3a posición.
    """
    nota, _ = mapeo.frecuencia_a_nota(hz("Ab5"), tabla_inversa=TABLA_C)
    assert nota.como_tab() == "-6'"
    assert nota.nombre == "Ab5"


def test_bend_del_uno_aspirado_es_re_bemol():
    """
    El "-1'" es Reb, la quinta bemol de Sol: la blue note de la 2a posición.
    Aparece en el turnaround de blues del 14/04.
    """
    nota, _ = mapeo.frecuencia_a_nota(hz("Db4"), tabla_inversa=TABLA_C)
    assert nota.como_tab() == "-1'"


def test_bend_soplado_del_ocho():
    """
    El "8'" es Mib6, la 7ª de Fa7. Es la nota que el recap del 25/08 anotó mal
    como "8 aspirado": el 8 aspirado es Re, no Mib.
    """
    nota, _ = mapeo.frecuencia_a_nota(hz("Eb6"), tabla_inversa=TABLA_C)
    assert nota.agujero == 8
    assert nota.direccion == SOPLADO
    assert nota.bend == 1
    assert nota.como_tab() == "8'"


def test_el_ocho_aspirado_es_re_no_mi_bemol():
    """
    La otra mitad del mismo asunto, fijada por escrito para que no se pierda.
    """
    nota, _ = mapeo.frecuencia_a_nota(hz("D6"), tabla_inversa=TABLA_C)
    assert nota.como_tab() == "-8"
    assert nota.nombre == "D6"


def test_los_dos_bends_soplados_del_diez():
    """El 10 tiene dos bends: B6 y Bb6."""
    nota_uno, _ = mapeo.frecuencia_a_nota(hz("B6"), tabla_inversa=TABLA_C)
    nota_dos, _ = mapeo.frecuencia_a_nota(hz("Bb6"), tabla_inversa=TABLA_C)
    assert nota_uno.como_tab() == "10'"
    assert nota_dos.como_tab() == "10''"


def test_los_tres_bends_del_tres_segun_leandro():
    """
    El recap del 28/07 lista los bends del 3: 1º Bb, 2º A, 3º Ab.
    Los tres tienen que dar exactamente eso.

    El tercero se incorporó el 02/09. Antes la app devolvía None para el Lab
    grave, que es la blue note de la 12a posición y la tónica de la 4a: sin él
    faltaba una nota importante de verdad, no un adorno.
    """
    primero, _ = mapeo.frecuencia_a_nota(hz("Bb4"), tabla_inversa=TABLA_C)
    segundo, _ = mapeo.frecuencia_a_nota(hz("A4"), tabla_inversa=TABLA_C)
    tercero, _ = mapeo.frecuencia_a_nota(hz("Ab4"), tabla_inversa=TABLA_C)

    assert primero.como_tab() == "-3'"
    assert segundo.como_tab() == "-3''"
    assert tercero.como_tab() == "-3'''"
    assert tercero.nombre == "Ab4"


# =============================================================================
# AMBIGÜEDADES — la única nota que se puede tocar de dos formas
# =============================================================================

def test_el_sol_cuatro_es_ambiguo_y_gana_el_aspirado():
    """
    En armónica de Do, Sol4 es el 2 aspirado Y el 3 soplado. Suenan igual.
    Por defecto elegimos el aspirado, porque el 2 aspirado es la tónica de la
    2a posición y es el agujero más usado del blues.
    """
    nota, _ = mapeo.frecuencia_a_nota(392.0, tabla_inversa=TABLA_C)
    assert nota.agujero == 2
    assert nota.direccion == ASPIRADO
    assert nota.como_tab() == "-2"


def test_la_preferencia_de_ambiguedad_se_puede_cambiar(monkeypatch):
    """
    Si cambiás config.PREFERENCIA_AMBIGUEDAD a "soplado", el mismo Sol4 pasa a
    ser el 3 soplado. Útil si transcribís melodías de 1a posición.

    `monkeypatch` es una herramienta de pytest para cambiar una variable solo
    durante este test y dejarla como estaba al terminar.
    """
    monkeypatch.setattr(config, "PREFERENCIA_AMBIGUEDAD", SOPLADO)
    tabla = mapeo.construir_tabla_inversa("C")
    nota, _ = mapeo.frecuencia_a_nota(392.0, tabla_inversa=tabla)
    assert nota.agujero == 3
    assert nota.direccion == SOPLADO


def test_esa_es_la_unica_ambiguedad_de_la_armonica():
    """
    Verifica que en toda la armónica haya exactamente una nota alcanzable de
    dos formas. Si algún día se agregan overblows van a aparecer muchas más, y
    este test va a avisar que hay que repensar la resolución de ambigüedades.
    """
    apariciones = {}
    for agujero in range(1, 11):
        indice = agujero - 1
        sop = tablas.AFINACION_SOPLADO[indice]
        asp = tablas.AFINACION_ASPIRADO[indice]
        apariciones.setdefault(sop, []).append(f"{agujero} soplado")
        apariciones.setdefault(asp, []).append(f"{agujero} aspirado")
        for n in range(1, tablas.BENDS_ASPIRADOS.get(agujero, 0) + 1):
            apariciones.setdefault(asp - n, []).append(f"{agujero} aspirado bend {n}")
        for n in range(1, tablas.BENDS_SOPLADOS.get(agujero, 0) + 1):
            apariciones.setdefault(sop - n, []).append(f"{agujero} soplado bend {n}")

    repetidas = {st: formas for st, formas in apariciones.items() if len(formas) > 1}
    assert len(repetidas) == 1
    assert repetidas[7] == ["2 aspirado", "3 soplado"]


# =============================================================================
# Notas que la armónica NO puede dar
# =============================================================================

def test_una_frecuencia_demasiado_grave_no_da_nota():
    """100 Hz está muy por debajo de cualquier armónica diatónica."""
    nota, _ = mapeo.frecuencia_a_nota(100.0, tabla_inversa=TABLA_C)
    assert nota is None


def test_una_frecuencia_demasiado_aguda_no_da_nota():
    nota, _ = mapeo.frecuencia_a_nota(5000.0, tabla_inversa=TABLA_C)
    assert nota is None


def test_las_notas_que_piden_overblow_dan_none():
    """
    Mib5 y Sib5 existen en la armónica de Do solo con overblow (del 4 y del 6).
    Como los overblows no están en V1, devolvemos None.

    Es justo el error del recap del 28/07, que anotaba "6 overblow (La)" cuando
    el La sale del 6 aspirado y el overblow del 6 da Sib.
    """
    assert mapeo.frecuencia_a_nota(hz("Eb5"), tabla_inversa=TABLA_C)[0] is None
    assert mapeo.frecuencia_a_nota(hz("Bb5"), tabla_inversa=TABLA_C)[0] is None


def test_el_la_del_registro_central_es_el_seis_aspirado_no_un_overblow():
    """
    La contracara del test anterior, y la corrección concreta al recap:
    el La5 sale del 6 aspirado, sin ninguna técnica especial.
    """
    nota, _ = mapeo.frecuencia_a_nota(hz("A5"), tabla_inversa=TABLA_C)
    assert nota.como_tab() == "-6"


def test_frecuencia_cero_o_negativa_no_rompe():
    """El detector de tono puede devolver basura. No queremos que explote."""
    assert mapeo.frecuencia_a_nota(0.0, tabla_inversa=TABLA_C)[0] is None
    assert mapeo.frecuencia_a_nota(-50.0, tabla_inversa=TABLA_C)[0] is None


# =============================================================================
# Afinación: los cents y la tolerancia
# =============================================================================

def test_una_nota_afinada_da_cero_cents():
    _, cents = mapeo.frecuencia_a_nota(440.0, tabla_inversa=TABLA_C)
    assert abs(cents) < 1


def test_reconoce_la_nota_aunque_estes_algo_desafinado():
    """
    452 Hz es un La 46 cents alto. Con la tolerancia por defecto (50) sigue
    siendo un La, y el medidor te avisa que estás alto.
    """
    nota, cents = mapeo.frecuencia_a_nota(452.0, tabla_inversa=TABLA_C)
    assert nota.como_tab() == "-3''"
    assert 40 < cents < 50


def test_con_tolerancia_estricta_una_nota_desafinada_no_cuenta():
    """
    Bajando la tolerancia a 25 cents, la app pasa a exigir afinación.
    Es un modo de práctica distinto, útil justamente para los bends.
    """
    nota, cents = mapeo.frecuencia_a_nota(
        452.0, tabla_inversa=TABLA_C, tolerancia_cents=25.0
    )
    assert nota is None
    assert 40 < cents < 50      # el dato de cuán desafinado estabas se conserva


def test_el_signo_de_los_cents_dice_para_donde_corregir():
    """Negativo = te falta subir. Es la convención de todos los afinadores."""
    _, cents_bajo = mapeo.frecuencia_a_nota(435.0, tabla_inversa=TABLA_C)
    _, cents_alto = mapeo.frecuencia_a_nota(445.0, tabla_inversa=TABLA_C)
    assert cents_bajo < 0
    assert cents_alto > 0


# =============================================================================
# Las otras tres armónicas de Bruno: G, D y A
# =============================================================================

def test_armonica_en_sol():
    """El 1 soplado de una armónica en Sol es G3 = 196 Hz, la nota más grave."""
    nota, _ = mapeo.frecuencia_a_nota(196.0, tabla_inversa=TABLA_G)
    assert nota.como_tab() == "1"
    assert nota.nombre == "G3"


def test_armonica_en_re():
    nota, _ = mapeo.frecuencia_a_nota(hz("D4"), tabla_inversa=TABLA_D)
    assert nota.como_tab() == "1"
    assert nota.nombre == "D4"


def test_armonica_en_la():
    nota, _ = mapeo.frecuencia_a_nota(220.0, tabla_inversa=TABLA_A)
    assert nota.como_tab() == "1"
    assert nota.nombre == "A3"


def test_el_mismo_agujero_da_notas_distintas_en_cada_armonica():
    """
    La idea central del diseño: el agujero es el mismo, la nota cambia.
    El 2 aspirado es Sol en la de Do, Re en la de Sol, La en la de Re.
    """
    assert mapeo.tab_a_nota("-2", "C").nombre == "G4"
    assert mapeo.tab_a_nota("-2", "G").nombre == "D4"
    assert mapeo.tab_a_nota("-2", "D").nombre == "A4"
    assert mapeo.tab_a_nota("-2", "A").nombre == "E4"


def test_una_tonalidad_que_no_existe_da_error():
    with pytest.raises(ValueError):
        mapeo.construir_tabla_inversa("H")


# =============================================================================
# La notación: guiones y flechas
# =============================================================================

def test_notacion_de_guiones():
    nota = mapeo.tab_a_nota("-3'", "C")
    assert nota.como_tab(notacion="guion") == "-3'"


def test_notacion_de_flechas():
    """La de tu atril: flecha abajo para aspirado, arriba para soplado."""
    aspirada = mapeo.tab_a_nota("-3'", "C")
    soplada = mapeo.tab_a_nota("4", "C")
    assert aspirada.como_tab(notacion="flechas") == "↓3'"
    assert soplada.como_tab(notacion="flechas") == "↑4"


def test_la_tab_con_nota_muestra_las_dos_cosas():
    """Es lo que va a aparecer en pantalla y en el archivo de tab."""
    nota = mapeo.tab_a_nota("-4", "C")
    assert nota.como_tab_con_nota() == "-4 D5"


# =============================================================================
# tab_a_nota — el camino inverso, de texto a nota
# =============================================================================

def test_tab_a_nota_casos_basicos():
    assert mapeo.tab_a_nota("4", "C").nombre == "C5"
    assert mapeo.tab_a_nota("-4", "C").nombre == "D5"
    assert mapeo.tab_a_nota("-3''", "C").nombre == "A4"
    assert mapeo.tab_a_nota("8'", "C").nombre == "Eb6"


def test_tab_a_nota_acepta_flechas():
    assert mapeo.tab_a_nota("↓4", "C").nombre == mapeo.tab_a_nota("-4", "C").nombre
    assert mapeo.tab_a_nota("↑4", "C").nombre == mapeo.tab_a_nota("4", "C").nombre


def test_ida_y_vuelta_entre_texto_y_nota():
    """Convertir a nota y volver a texto tiene que devolver lo mismo."""
    for tablatura in ["1", "-1", "-1'", "4", "-4", "-3'", "-3''", "8'", "10''", "-10"]:
        nota = mapeo.tab_a_nota(tablatura, "C")
        assert nota.como_tab() == tablatura


def test_tab_a_nota_rechaza_bends_imposibles():
    """
    El 5 aspirado no tiene bend, y ningún agujero llega a cuatro.
    Preferimos un error ruidoso a una nota mal calculada en silencio.
    """
    with pytest.raises(ValueError):
        mapeo.tab_a_nota("-5'", "C")
    with pytest.raises(ValueError):
        mapeo.tab_a_nota("-3''''", "C")
    with pytest.raises(ValueError):
        mapeo.tab_a_nota("-2'''", "C")     # el 2 llega hasta dos bends


def test_tab_a_nota_rechaza_texto_invalido():
    with pytest.raises(ValueError):
        mapeo.tab_a_nota("-11", "C")     # no existe el agujero 11
    with pytest.raises(ValueError):
        mapeo.tab_a_nota("x", "C")
    with pytest.raises(ValueError):
        mapeo.tab_a_nota("", "C")


# =============================================================================
# Integración: las tablas de escalas contra el mapeo
# =============================================================================

def test_todas_las_escalas_dan_notas_que_pertenecen_a_la_escala():
    """
    EL TEST MÁS IMPORTANTE DEL ARCHIVO.

    Recorre las dieciocho tablas de escalas de tablas.py, convierte cada
    tablatura en una nota concreta, y verifica que esa nota pertenezca de verdad
    a la escala que dice ser.

    Es la validación cruzada de la que veníamos hablando: las tablas están
    escritas a mano, y esto las contrasta contra el cálculo. Si alguien anota
    un agujero de más o de menos, salta acá.

    Además lo corre para las cuatro armónicas, lo que prueba de paso que las
    tablas son independientes de la tonalidad: los mismos agujeros forman la
    escala en una armónica en Do que en una en Sol.
    """
    problemas = []

    for tonalidad in tablas.TONALIDADES_DISPONIBLES:
        midi_raiz = tablas.TONALIDADES[tonalidad]

        for (posicion, escala), lista in tablas.ESCALAS_POR_POSICION.items():
            clase_tonica = (midi_raiz + tablas.POSICIONES[posicion]) % 12
            clases_validas = {
                (clase_tonica + i) % 12 for i in tablas.ESCALAS_INTERVALOS[escala]
            }

            for tablatura in lista:
                nota = mapeo.tab_a_nota(tablatura, tonalidad)
                if nota.midi % 12 not in clases_validas:
                    problemas.append(
                        f"  armonica en {tonalidad}, {posicion}a {escala}: "
                        f"{tablatura} da {nota.nombre}, que no pertenece a la escala"
                    )

    assert not problemas, "Notas fuera de escala en las tablas:\n" + "\n".join(problemas)


def test_ninguna_escala_pide_una_nota_que_la_armonica_no_da():
    """
    Toda tablatura de las tablas de escalas tiene que poder tocarse de verdad.
    Ya lo verifica tab_a_nota lanzando error, así que este test se limita a
    recorrerlas todas y confirmar que ninguna explota.
    """
    for (posicion, escala), lista in tablas.ESCALAS_POR_POSICION.items():
        for tablatura in lista:
            nota = mapeo.tab_a_nota(tablatura, "C")
            assert 1 <= nota.agujero <= 10


def test_la_pentatonica_de_doceava_en_do_da_las_notas_de_fa():
    """
    Lo que estudiás ahora, verificado nota por nota: la pentatónica mayor de la
    12a posición en armónica de Do tiene que dar exactamente Fa, Sol, La, Do, Re.
    """
    lista = tablas.ESCALAS_POR_POSICION[(12, "pentatonica_mayor")]
    nombres_sin_octava = {
        notas.nombre_de_clase(mapeo.tab_a_nota(t, "C").midi % 12) for t in lista
    }
    assert nombres_sin_octava == {"F", "G", "A", "C", "D"}


def test_la_digitacion_correcta_de_la_pentatonica_de_doceava():
    """
    La corrección concreta al recap del 28/07. La digitación del registro
    central es 5 aspirado, 6 soplado, 6 aspirado, 7 soplado, 8 aspirado.
    Ningún overblow.
    """
    digitacion = ["-5", "6", "-6", "7", "-8"]
    nombres = [mapeo.tab_a_nota(t, "C").nombre for t in digitacion]
    assert nombres == ["F5", "G5", "A5", "C6", "D6"]


# =============================================================================
# Utilidades
# =============================================================================

def test_el_rango_de_la_armonica_en_do():
    """De C4 (agujero 1 soplado) a C7 (agujero 10 soplado)."""
    grave, agudo = mapeo.rango_de_la_armonica("C")
    assert notas.midi_a_nombre(grave) == "C4"
    assert notas.midi_a_nombre(agudo) == "C7"


def test_todas_las_notas_vienen_ordenadas_de_grave_a_aguda():
    lista = mapeo.todas_las_notas("C")
    assert lista[0].nombre == "C4"
    assert lista[-1].nombre == "C7"
    for anterior, siguiente in zip(lista, lista[1:]):
        assert anterior.midi < siguiente.midi


def test_la_nota_se_puede_usar_como_clave_de_diccionario():
    """
    Hace falta para el resumen de sesión, que cuenta cuántas veces tocaste cada
    agujero. Funciona porque Nota es `frozen=True`.
    """
    conteo = {}
    for tablatura in ["-2", "-2", "4", "-3'"]:
        nota = mapeo.tab_a_nota(tablatura, "C")
        conteo[nota] = conteo.get(nota, 0) + 1

    assert conteo[mapeo.tab_a_nota("-2", "C")] == 2
    assert len(conteo) == 3
