"""
teoria.py — Calcula escalas para cualquier posición y cualquier armónica.

LA DIFERENCIA CON posiciones.py

Los dos módulos responden la misma pregunta: qué agujeros forman una escala.
Pero la responden de maneras opuestas, y eso es a propósito.

    posiciones.py  LEE una tabla escrita a mano. Solo sabe de seis posiciones.
    teoria.py      CALCULA desde cero. Sabe de las doce.

Tener las dos parece redundante. No lo es: cada una tapa el agujero de la otra.

    - Las tablas escritas a mano se pueden verificar leyéndolas contra un método
      de armónica, y son las que Leandro te enseñó. Pero pueden tener erratas
      (de hecho tenían tres) y escribir 36 tablas a mano sería inviable.
    - El cálculo nunca tiene erratas de tipeo y cubre todo. Pero si la fórmula
      está mal, se equivoca en las 36 de la misma manera y nadie lo nota.

La solución es tenerlas a las dos y compararlas. Hay un test que verifica que
el cálculo coincida con las tablas en las seis posiciones que tienen las dos.
Si algún día difieren, una está mal y lo vamos a saber. Es el mismo principio
de una conciliación bancaria: dos registros independientes que tienen que dar
lo mismo.

CÓMO CALCULA

En tres pasos, sin misterio:
    1. La tónica de la escala = tonalidad de la armónica + semitonos de la posición.
    2. Las notas de la escala = tónica + los intervalos de la escala.
    3. Los agujeros = buscar en la armónica todas las formas de tocar esas notas.

El paso 3 también nos dice qué notas de la escala la armónica NO puede dar sin
overblow. Eso es tan importante como lo que sí puede: es la razón por la que
Leandro te empuja a la pentatónica mayor en 12a y no a la escala mayor completa.

Python puro: importa tablas, notas y mapeo. Nada de audio ni de pantalla.
"""

from dataclasses import dataclass, field

from armonica import mapeo, notas, tablas


@dataclass
class EscalaEnArmonica:
    """
    El resultado de calcular una escala: todo lo que hay que saber para tocarla.

    Campos:
        tonalidad_armonica  "C"
        posicion            12
        escala              "pentatonica_mayor"
        tonica              "F"  — la tónica de la escala resultante
        nombres_notas       ["F", "G", "A", "C", "D"]
        agujeros            [Nota, ...] todas las formas de tocarla, de grave a agudo
        faltantes           [Nota-que-no-existe...] las que pedirían overblow
    """

    tonalidad_armonica: str
    posicion: int
    escala: str
    tonica: str
    nombres_notas: list = field(default_factory=list)
    agujeros: list = field(default_factory=list)
    faltantes: list = field(default_factory=list)

    def tablaturas(self, notacion=None):
        """Los agujeros como lista de texto: ['↓5', '6', '↓6', ...]."""
        return [nota.como_tab(notacion) for nota in self.agujeros]

    def sin_bends(self):
        """
        Solo los agujeros que salen con aire natural, sin ningún bend.

        Es la información más útil para empezar a tocar una posición nueva: te
        dice cuánto de la escala tenés gratis antes de pelear una técnica.
        """
        return [nota for nota in self.agujeros if nota.bend == 0]

    def cantidad_de_bends(self):
        """Cuántos de los agujeros de la escala piden bend."""
        return sum(1 for nota in self.agujeros if nota.bend > 0)

    def necesita_overblows(self):
        """¿Hay notas de esta escala que la armónica no puede dar en V1?"""
        return len(self.faltantes) > 0


def agujeros_para_escala(tonalidad_armonica, posicion, escala):
    """
    Calcula una escala en una armónica y una posición. Devuelve EscalaEnArmonica.

    Funciona para las DOCE posiciones y las doce tonalidades de armónica, sin
    necesidad de ninguna tabla escrita a mano.
    """
    if tonalidad_armonica not in tablas.TONALIDADES:
        raise ValueError(
            f"No conozco la armonica en {tonalidad_armonica!r}. "
            f"Las que hay son: {', '.join(tablas.TONALIDADES)}"
        )
    if posicion not in tablas.POSICIONES:
        raise ValueError(f"La posicion {posicion!r} no existe. Van de la 1 a la 12.")
    if escala not in tablas.ESCALAS_INTERVALOS:
        raise ValueError(
            f"No conozco la escala {escala!r}. "
            f"Las que hay son: {', '.join(tablas.ESCALAS_INTERVALOS)}"
        )

    # --- Paso 1: la tónica de la escala ---
    clase_armonica = tablas.TONALIDADES[tonalidad_armonica] % 12
    clase_tonica = (clase_armonica + tablas.POSICIONES[posicion]) % 12

    # --- Paso 2: las notas de la escala, como clases (sin octava) ---
    intervalos = tablas.ESCALAS_INTERVALOS[escala]
    clases_escala = {(clase_tonica + i) % 12 for i in intervalos}
    nombres = [notas.nombre_de_clase((clase_tonica + i) % 12) for i in intervalos]

    # --- Paso 3: dónde caen esas notas en esta armónica ---
    formas = mapeo.todas_las_formas(tonalidad_armonica)

    agujeros = []
    for midi in sorted(formas):
        if midi % 12 in clases_escala:
            # Puede haber más de una forma de tocar la misma nota (el caso del
            # Sol4 en armónica de Do). Las mostramos todas: en el modo teoría
            # querés ver todas tus opciones, no una elegida por la app.
            agujeros.extend(formas[midi])

    # --- Y las que faltan: notas de la escala que la armónica no da ---
    # Solo miramos dentro del rango de la armónica. Que no llegue a un Fa dos
    # octavas más abajo no es una carencia, es que ahí no llega el instrumento.
    faltantes = []
    for midi in range(min(formas), max(formas) + 1):
        if midi % 12 in clases_escala and midi not in formas:
            faltantes.append(notas.midi_a_nombre(midi))

    return EscalaEnArmonica(
        tonalidad_armonica=tonalidad_armonica,
        posicion=posicion,
        escala=escala,
        tonica=notas.nombre_de_clase(clase_tonica),
        nombres_notas=nombres,
        agujeros=agujeros,
        faltantes=faltantes,
    )


def notas_de_escala(tonica, escala):
    """
    Las notas de una escala, en abstracto, sin armónica de por medio.

    Ejemplo: ("F", "pentatonica_mayor") -> ["F", "G", "A", "C", "D"]

    Es pura teoría musical. Sirve para el modo teoría y para responder
    preguntas como "qué notas tiene la pentatónica de Fa".
    """
    if escala not in tablas.ESCALAS_INTERVALOS:
        raise ValueError(f"No conozco la escala {escala!r}")

    if tonica not in tablas.NOMBRES_NOTAS and tonica not in tablas.NOMBRES_NOTAS_SOSTENIDOS:
        raise ValueError(f"No reconozco la nota {tonica!r}")

    if tonica in tablas.NOMBRES_NOTAS:
        clase_tonica = tablas.NOMBRES_NOTAS.index(tonica)
    else:
        clase_tonica = tablas.NOMBRES_NOTAS_SOSTENIDOS.index(tonica)

    return [
        notas.nombre_de_clase((clase_tonica + i) % 12)
        for i in tablas.ESCALAS_INTERVALOS[escala]
    ]


def comparar_con_tabla_explicita(tonalidad_armonica, posicion, escala):
    """
    Compara lo calculado contra la tabla escrita a mano. Devuelve la diferencia.

    Es la conciliación entre los dos módulos, y la usa el test más importante
    del paso. Devuelve una tupla (solo_en_calculo, solo_en_tabla): dos listas
    de tablaturas. Si las dos vienen vacías, coinciden perfectamente.

    Devuelve (None, None) si esa posición no tiene tabla explícita, que no es un
    error sino simplemente que no hay nada que conciliar.
    """
    clave = (posicion, escala)
    if clave not in tablas.ESCALAS_POR_POSICION:
        return None, None

    calculada = agujeros_para_escala(tonalidad_armonica, posicion, escala)

    # Comparamos con la notación de guiones, que es la que usan las tablas.
    del_calculo = {nota.como_tab("guion") for nota in calculada.agujeros}
    de_la_tabla = set(tablas.ESCALAS_POR_POSICION[clave])

    return sorted(del_calculo - de_la_tabla), sorted(de_la_tabla - del_calculo)


def posiciones_utiles(tonalidad_armonica, escala, maximo_bends=2):
    """
    Ordena las doce posiciones de más cómoda a menos, para una escala dada.

    "Cómoda" quiere decir: cuántas notas de la escala salen sin bend, y cuántas
    no salen para nada sin overblow.

    Es la respuesta calculada a la pregunta "¿en qué posición me conviene tocar
    esto?". Para la pentatónica mayor en una armónica en Do, la 12a tiene que
    aparecer arriba de todo: es exactamente el argumento de Leandro sobre por
    qué la 12a es amable.

    Devuelve una lista de diccionarios, la más cómoda primero.
    """
    resultados = []

    for posicion in sorted(tablas.POSICIONES):
        calculada = agujeros_para_escala(tonalidad_armonica, posicion, escala)
        naturales = len(calculada.sin_bends())

        resultados.append({
            "posicion": posicion,
            "tonica": calculada.tonica,
            "agujeros_sin_bend": naturales,
            "agujeros_con_bend": calculada.cantidad_de_bends(),
            "notas_imposibles": len(calculada.faltantes),
        })

    # Ordenamos: primero las que menos notas imposibles tienen, y entre esas,
    # las que más agujeros naturales ofrecen.
    resultados.sort(key=lambda r: (r["notas_imposibles"], -r["agujeros_sin_bend"]))
    return resultados


# =============================================================================
# Modo de demostración
# =============================================================================
#
#     python -m armonica.teoria C 12 pentatonica_mayor
#
# Es el adelanto del "modo teoría" del paso 8: consultar una escala sin tocar.

if __name__ == "__main__":
    import sys

    from armonica.consola import preparar_consola

    preparar_consola()

    tonalidad = sys.argv[1] if len(sys.argv) > 1 else "C"
    numero_posicion = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    nombre_escala = sys.argv[3] if len(sys.argv) > 3 else "pentatonica_mayor"

    resultado = agujeros_para_escala(tonalidad, numero_posicion, nombre_escala)

    print(f"\nArmonica en {resultado.tonalidad_armonica}, "
          f"{tablas.NOMBRES_POSICIONES[resultado.posicion]}")
    print(f"Tocas en: {resultado.tonica}")
    print(f"Escala:   {tablas.NOMBRES_ESCALAS[resultado.escala]} de {resultado.tonica}")
    print(f"Notas:    {' '.join(resultado.nombres_notas)}\n")

    con_bend = [nota for nota in resultado.agujeros if nota.bend > 0]

    # La lista completa. Los que piden bend van marcados con un asterisco, para
    # que se vea de un golpe cuáles son los caros. Antes esta lista iba seguida
    # de otra con los agujeros naturales, y era fácil confundir la segunda con
    # la escala entera: ahora hay UNA sola lista y el detalle va debajo.
    print(f"LA ESCALA COMPLETA ({len(resultado.agujeros)} agujeros):")
    linea = "  "
    for nota in resultado.agujeros:
        marca = "*" if nota.bend > 0 else " "
        pedazo = f"{nota.como_tab()} {nota.nombre}{marca}".ljust(12)
        if len(linea) + len(pedazo) > 78:
            print(linea)
            linea = "  "
        linea += pedazo
    print(linea)

    if con_bend:
        print(f"\n  * pide bend ({len(con_bend)} de {len(resultado.agujeros)}): "
              + "  ".join(nota.como_tab() for nota in con_bend))
        print(f"    los otros {len(resultado.sin_bends())} salen con aire natural.")
    else:
        print("\n  Ninguno pide bend: la escala entera sale con aire natural.")

    if resultado.necesita_overblows():
        print("\nNotas de la escala que esta armonica NO da (harian falta overblows):")
        print(f"  {' '.join(resultado.faltantes)}")
    else:
        print("\nNo falta ninguna nota: la escala esta entera en la armonica.")

    sobran, faltan = comparar_con_tabla_explicita(
        tonalidad, numero_posicion, nombre_escala
    )
    if sobran is None:
        print("\n(Esta posicion no tiene tabla escrita a mano para comparar.)\n")
    elif not sobran and not faltan:
        print("\nCoincide con la tabla escrita a mano. Conciliado.\n")
    else:
        print(f"\nDIFERENCIA con la tabla escrita a mano:")
        print(f"  solo en el calculo: {sobran}")
        print(f"  solo en la tabla:   {faltan}\n")
