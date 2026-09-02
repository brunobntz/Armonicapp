"""
mapeo.py — Traduce una frecuencia a un agujero de la armónica.

Es la pieza donde la teoría se junta con el micrófono. El detector de tono va a
decir "escucho 466.16 Hz" y este módulo responde "eso es el agujero 3 aspirado
con medio bend, o sea un Sib4".

Cómo funciona, en tres pasos:

  1. La frecuencia se convierte a nota MIDI (eso lo hace notas.py).
  2. Se busca esa nota en una TABLA INVERSA de la armónica: un diccionario que
     va de nota MIDI a agujero. La tabla se arma una sola vez al empezar.
  3. Si la nota no está en la tabla, la armónica no la puede dar y devolvemos
     None. Eso pasa con notas fuera de rango, o con notas que necesitan
     overblow (que no está en V1).

Por qué una tabla inversa y no calcular cada vez: porque se consulta unas 86
veces por segundo mientras tocás. Armarla una vez y consultarla es instantáneo.
Es la misma idea que tener el plan de cuentas cargado en vez de deducirlo cada
vez que registrás un asiento.

Este módulo es Python puro: importa tablas, notas y config, y nada más. Se puede
portar a otro lenguaje sin tocar la lógica.
"""

from dataclasses import dataclass

import config
from armonica import notas, tablas


# Las dos direcciones del aire. Usamos constantes en vez de escribir el texto
# suelto en cada lugar: si en algún momento hay una errata, falla en un lugar
# solo y no en silencio.
SOPLADO = "soplado"
ASPIRADO = "aspirado"


@dataclass(frozen=True)
class Nota:
    """
    Una nota concreta tocada en la armónica: qué agujero, con qué aire, con
    cuánto bend, y qué nota suena.

    Es `frozen=True`, o sea inmutable: una vez creada no se puede modificar.
    Dos ventajas prácticas. Primera, no hay forma de romperla sin querer desde
    otro módulo. Segunda, se puede usar como clave de diccionario y dentro de
    conjuntos, que es justo lo que necesita el resumen de sesión para contar
    cuántas veces tocaste cada agujero.

    Campos:
        agujero      1 a 10
        direccion    SOPLADO o ASPIRADO
        bend         0 = sin bend, 1 = medio tono, 2 = un tono
        midi         la nota MIDI que suena (60 = C4)
        nombre       el nombre legible de esa nota ("Bb4")
    """

    agujero: int
    direccion: str
    bend: int
    midi: int
    nombre: str

    def como_tab(self, notacion=None):
        """
        Devuelve la tablatura de esta nota: "-3'", "4", "8'".

        La notación sale de config.py porque en tu material conviven dos:
        la de guiones que confirmaste ("-4") y la de flechas de tu atril ("↓4").
        Fijate que la nota se guarda como agujero + dirección + bend, nunca como
        texto. El texto se arma recién acá, al mostrarla. Por eso cambiar de
        notación no toca ninguna otra parte de la app.
        """
        if notacion is None:
            notacion = config.NOTACION

        if notacion == "flechas":
            prefijo = "↓" if self.direccion == ASPIRADO else "↑"
        else:
            # La notación de guiones no marca el soplado: "4" ya significa
            # soplado, y solo el aspirado lleva el guión adelante.
            prefijo = "-" if self.direccion == ASPIRADO else ""

        return f"{prefijo}{self.agujero}{config.SIMBOLO_BEND * self.bend}"

    def como_tab_con_nota(self, notacion=None):
        """
        La tablatura con el nombre de la nota al lado: "-3' Bb4".

        Es lo que pediste ver en pantalla y en el archivo de tab: el agujero
        para saber qué hacer con la boca, y la nota para saber qué estás
        tocando musicalmente.
        """
        return f"{self.como_tab(notacion)} {self.nombre}"

    def __str__(self):
        return self.como_tab()


def todas_las_formas(tonalidad):
    """
    Devuelve {nota_midi: [Nota, ...]} con TODAS las maneras de tocar cada nota.

    Recorre los 10 agujeros y, para cada uno, registra el soplado, el aspirado
    y todos los bends que ese agujero permita.

    La mayoría de las notas tiene una sola forma, así que la lista trae un solo
    elemento. La excepción en la afinación Richter es el Sol4 de una armónica en
    Do, que se puede tocar como 2 aspirado o como 3 soplado: ahí la lista trae
    dos.

    Esta función dice la verdad completa, sin elegir. La usa el módulo de teoría
    para mostrarte todos los lugares donde podés tocar una nota de la escala.
    Para transcribir hace falta elegir uno solo, y de eso se encarga
    construir_tabla_inversa().
    """
    if tonalidad not in tablas.TONALIDADES:
        raise ValueError(
            f"No conozco la armonica en {tonalidad!r}. "
            f"Las que hay son: {', '.join(tablas.TONALIDADES)}"
        )

    midi_raiz = tablas.TONALIDADES[tonalidad]
    formas = {}

    def registrar(midi, agujero, direccion, bend):
        nota = Nota(
            agujero=agujero,
            direccion=direccion,
            bend=bend,
            midi=midi,
            nombre=notas.midi_a_nombre(midi),
        )
        formas.setdefault(midi, []).append(nota)

    for agujero in range(1, 11):
        indice = agujero - 1

        # --- Las dos notas naturales del agujero ---
        midi_soplado = midi_raiz + tablas.AFINACION_SOPLADO[indice]
        midi_aspirado = midi_raiz + tablas.AFINACION_ASPIRADO[indice]

        registrar(midi_soplado, agujero, SOPLADO, 0)
        registrar(midi_aspirado, agujero, ASPIRADO, 0)

        # --- Los bends aspirados (agujeros 1 a 6) ---
        # Cada bend baja un semitono más desde la nota aspirada.
        for cantidad in range(1, tablas.BENDS_ASPIRADOS.get(agujero, 0) + 1):
            registrar(midi_aspirado - cantidad, agujero, ASPIRADO, cantidad)

        # --- Los bends soplados (agujeros 8, 9 y 10) ---
        for cantidad in range(1, tablas.BENDS_SOPLADOS.get(agujero, 0) + 1):
            registrar(midi_soplado - cantidad, agujero, SOPLADO, cantidad)

    return formas


def construir_tabla_inversa(tonalidad):
    """
    Arma el diccionario {nota_midi: Nota} que usa la transcripción.

    Es todas_las_formas() con una decisión tomada: cuando una nota se puede
    tocar de dos maneras, elige una.

    Sobre las AMBIGÜEDADES. En una armónica en Do, el Sol4 es tanto el agujero 2
    aspirado como el 3 soplado. Suenan igual, y escuchando el audio no hay forma
    de distinguirlas. Hay que elegir, y la elección está en
    config.PREFERENCIA_AMBIGUEDAD.

    Por defecto preferimos el aspirado, porque el 2 aspirado es la tónica de la
    2a posición y es de lejos el agujero más usado en blues. Si alguna vez
    transcribís melodías de 1a posición, cambiá esa línea a "soplado".

    (En V2 esto se podría resolver mirando qué agujero tocaste justo antes: si
    venís del 1, seguro estás en el 2 aspirado; si venís del 4, probablemente
    sea el 3 soplado. Por ahora, una preferencia fija y documentada.)
    """
    tabla = {}

    for midi, candidatas in todas_las_formas(tonalidad).items():
        tabla[midi] = _elegir_forma(candidatas)

    return tabla


def _elegir_forma(candidatas):
    """
    De varias formas de tocar la misma nota, elige una.

    El guión bajo del nombre es una convención de Python: significa "esta
    función es de uso interno del módulo, no la llames desde afuera".

    Dos reglas, en orden:
      1. Menos bend gana. Una nota natural siempre es más probable que un bend,
         porque es más fácil de tocar.
      2. A igual cantidad de bend, gana la dirección que diga config.
    """
    if len(candidatas) == 1:
        return candidatas[0]

    menor_bend = min(nota.bend for nota in candidatas)
    finalistas = [nota for nota in candidatas if nota.bend == menor_bend]

    for nota in finalistas:
        if nota.direccion == config.PREFERENCIA_AMBIGUEDAD:
            return nota

    return finalistas[0]


def frecuencia_a_nota(frecuencia_hz, tonalidad=None, tabla_inversa=None,
                      tolerancia_cents=None):
    """
    La función principal del módulo: de Hz a agujero.

    Devuelve una tupla (Nota o None, cents).

    Los `cents` son cuán desafinado estabas respecto de la nota "correcta".
    Negativo = bajo, positivo = alto. Ese número se conserva aunque la nota se
    reconozca bien, porque es lo que alimenta el medidor de afinación en
    pantalla. Es especialmente útil en los bends, que son notas continuas y muy
    fáciles de pasar o quedar corto.

    Devuelve (None, cents) en tres casos, todos legítimos:
      - La frecuencia está fuera del rango de la armónica.
      - La nota necesita un overblow (no está en V1).
      - Estás a más cents de distancia que la tolerancia configurada.

    Ese último caso merece explicación. Con la tolerancia por defecto (50 cents)
    nunca se dispara, porque 50 cents es justo el punto medio entre dos notas y
    siempre hay una más cerca. Pero si la bajás a 25 en config.py, la app pasa a
    exigir afinación: un bend a medio hacer deja de contar como nota. Es un modo
    de práctica distinto, más estricto, y por eso el parámetro existe.

    Podés pasar `tonalidad` (y arma la tabla) o `tabla_inversa` ya armada.
    Lo segundo es lo que se usa en tiempo real, para no rearmar la tabla 86
    veces por segundo.
    """
    if tabla_inversa is None:
        if tonalidad is None:
            raise ValueError("Hay que pasar `tonalidad` o `tabla_inversa`")
        tabla_inversa = construir_tabla_inversa(tonalidad)

    if tolerancia_cents is None:
        tolerancia_cents = config.TOLERANCIA_CENTS

    if frecuencia_hz <= 0:
        return None, 0.0

    midi, cents = notas.midi_mas_cercano(frecuencia_hz)

    if abs(cents) > tolerancia_cents:
        return None, cents

    return tabla_inversa.get(midi), cents


def tab_a_nota(tablatura, tonalidad):
    """
    El camino inverso: de texto a Nota. "-3'" -> el Sib4 de una armónica en Do.

    Hace falta porque las tablas de escalas en tablas.py están escritas como
    texto ("-2", "-3'", "4"), que es la forma más legible y más fácil de portar
    a otro lenguaje. Alguien tiene que convertir ese texto en notas concretas, y
    es acá.

    Acepta las dos notaciones: "-4" y "↓4" son lo mismo.

    Lanza ValueError si la tablatura está mal escrita o si pide un bend que ese
    agujero no puede hacer. Preferimos un error ruidoso a una nota silenciosamente
    equivocada: una tabla mal escrita se practica cien veces antes de que alguien
    lo note.
    """
    if tonalidad not in tablas.TONALIDADES:
        raise ValueError(f"No conozco la armonica en {tonalidad!r}")

    texto = tablatura.strip()
    if not texto:
        raise ValueError("Tablatura vacia")

    # 1. La dirección, que viene del primer carácter.
    if texto[0] in ("-", "↓"):
        direccion = ASPIRADO
        texto = texto[1:]
    elif texto[0] == "↑":
        direccion = SOPLADO
        texto = texto[1:]
    else:
        direccion = SOPLADO

    # 2. Los bends, que son los apóstrofos del final.
    bend = 0
    while texto.endswith(config.SIMBOLO_BEND):
        bend += 1
        texto = texto[:-1]

    # 3. Lo que queda tiene que ser el número de agujero.
    if not texto.isdigit():
        raise ValueError(f"Tablatura mal escrita: {tablatura!r}")
    agujero = int(texto)
    if not 1 <= agujero <= 10:
        raise ValueError(f"El agujero {agujero} no existe. Van del 1 al 10.")

    # 4. Verificamos que ese bend sea posible en ese agujero.
    if direccion == ASPIRADO:
        disponibles = tablas.BENDS_ASPIRADOS.get(agujero, 0)
    else:
        disponibles = tablas.BENDS_SOPLADOS.get(agujero, 0)

    if bend > disponibles:
        raise ValueError(
            f"{tablatura!r} pide {bend} bend(s) en el agujero {agujero} "
            f"{direccion}, pero solo hay {disponibles} disponible(s)"
        )

    # 5. Calculamos qué nota suena.
    midi_raiz = tablas.TONALIDADES[tonalidad]
    indice = agujero - 1
    if direccion == ASPIRADO:
        midi = midi_raiz + tablas.AFINACION_ASPIRADO[indice] - bend
    else:
        midi = midi_raiz + tablas.AFINACION_SOPLADO[indice] - bend

    return Nota(
        agujero=agujero,
        direccion=direccion,
        bend=bend,
        midi=midi,
        nombre=notas.midi_a_nombre(midi),
    )


def rango_de_la_armonica(tonalidad):
    """
    Devuelve (midi_mas_grave, midi_mas_agudo) de una armónica.

    Sirve para dos cosas: acotar el rango que el detector de tono tiene que
    mirar (menos rango = menos errores de octava), y avisar en pantalla cuando
    tocaste algo que esa armónica no puede dar.
    """
    tabla = construir_tabla_inversa(tonalidad)
    return min(tabla), max(tabla)


def todas_las_notas(tonalidad):
    """
    Todas las notas que da una armónica, ordenadas de grave a aguda.

    La usa el diagrama de pantalla y el modo teoría.
    """
    tabla = construir_tabla_inversa(tonalidad)
    return [tabla[midi] for midi in sorted(tabla)]


# =============================================================================
# Modo de demostración
# =============================================================================
#
# Este bloque solo se ejecuta si corrés el módulo directamente:
#
#     python -m armonica.mapeo C
#
# Sirve para mirar el mapa completo de una armónica y compararlo con la que
# tenés en la mano. Es la forma más rápida de detectar un error en las tablas.
# El `if __name__ == "__main__"` es la manera estándar en Python de decir
# "esto corre solo si me ejecutás a mí, no si alguien me importa".

if __name__ == "__main__":
    import sys

    from armonica.consola import preparar_consola

    # Sin esto, imprimir una flecha revienta en la consola de Windows.
    preparar_consola()

    tonalidad = sys.argv[1] if len(sys.argv) > 1 else "C"

    print(f"\nArmonica en {tonalidad} - afinacion Richter, 10 agujeros")
    print(f"Notacion: {config.NOTACION}\n")

    encabezado = "        " + "".join(f"{n:>9}" for n in range(1, 11))
    print(encabezado)
    print("        " + "-" * 90)

    for etiqueta, direccion, bends in (
        ("soplado", SOPLADO, 0),
        ("aspirado", ASPIRADO, 0),
        ("bend '", None, 1),
        ("bend ''", None, 2),
    ):
        celdas = []
        for agujero in range(1, 11):
            if bends == 0:
                nota = tab_a_nota(
                    ("-" if direccion == ASPIRADO else "") + str(agujero), tonalidad
                )
                celdas.append(f"{nota.nombre:>9}")
            else:
                # Para las filas de bends probamos las dos direcciones y
                # mostramos la que exista en ese agujero.
                texto = "        ."
                for prefijo in ("-", ""):
                    try:
                        nota = tab_a_nota(
                            f"{prefijo}{agujero}" + config.SIMBOLO_BEND * bends,
                            tonalidad,
                        )
                    except ValueError:
                        continue
                    texto = f"{nota.como_tab() + ' ' + nota.nombre:>9}"
                    break
                celdas.append(texto)
        print(f"{etiqueta:>8}" + "".join(celdas))

    grave, agudo = rango_de_la_armonica(tonalidad)
    print(
        f"\nRango: {notas.midi_a_nombre(grave)} a {notas.midi_a_nombre(agudo)}"
        f"  ({notas.midi_a_frecuencia(grave):.1f} Hz a "
        f"{notas.midi_a_frecuencia(agudo):.1f} Hz)"
    )
    print(f"Notas distintas que da esta armonica: {len(todas_las_notas(tonalidad))}\n")
