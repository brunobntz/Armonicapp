"""
teoria.py — Calcula escalas para cualquier posición y cualquier armónica.

LA DIFERENCIA CON posiciones.py

Los dos módulos responden la misma pregunta: qué agujeros forman una escala.
Pero la responden de maneras opuestas, y eso es a propósito.

    posiciones.py  LEE una tabla escrita a mano. Solo sabe de seis posiciones.
    teoria.py      CALCULA desde cero. Sabe de las doce.

Tener las dos parece redundante. No lo es: cada una tapa el agujero de la otra.

    - Las tablas escritas a mano se pueden verificar leyéndolas contra un método
      de armónica, y son las que el profe te enseñó. Pero pueden tener erratas
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
el profe te empuja a la pentatónica mayor en 12a y no a la escala mayor completa.

Python puro: importa tablas, notas y mapeo. Nada de audio ni de pantalla.
"""

from dataclasses import dataclass, field

from armonica import mapeo, notas, posiciones, tablas


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

    def desde_la_tonica(self, octavas=2, sin_repetir_nota=True):
        """
        La escala como se estudia: arrancando en la tónica y subiendo.

        Es distinto de `agujeros`, que trae todo lo que la armónica puede dar
        ordenado de grave a agudo. Esa lista empieza en el agujero más grave que
        pertenezca a la escala, que casi nunca es la tónica.

        Ejemplo en 12a posición con armónica de Do: `agujeros` empieza en el
        ↑1 (Do), porque el Do es la quinta de Fa y es la nota más grave de la
        escala que la armónica alcanza. Pero la corrida que practicás empieza en
        el ↓2'' (Fa), que es la tónica. Eso es lo que devuelve esta función.

        `sin_repetir_nota` saca los duplicados: cuando una nota se puede tocar de
        dos formas (el Sol4 en armónica de Do), deja una sola, para que la
        corrida se lea como una escala y no como una lista de opciones.

        `octavas` corta la corrida después de esa cantidad de octavas desde la
        tónica. Con 2 sale lo que suele entrar en una hoja de estudio.
        """
        if not self.agujeros:
            return []

        clase_tonica = self.agujeros[0].midi % 12
        for nota in self.agujeros:
            if notas.nombre_de_clase(nota.midi % 12) == self.tonica:
                clase_tonica = nota.midi % 12
                break

        # Buscamos la tónica más grave que la armónica alcance.
        primera = None
        for nota in self.agujeros:
            if nota.midi % 12 == clase_tonica:
                primera = nota
                break
        if primera is None:
            return list(self.agujeros)

        limite = primera.midi + 12 * octavas
        corrida = [
            nota for nota in self.agujeros
            if primera.midi <= nota.midi <= limite
        ]

        if sin_repetir_nota:
            vistas = set()
            unicas = []
            for nota in corrida:
                if nota.midi not in vistas:
                    vistas.add(nota.midi)
                    unicas.append(nota)
            corrida = unicas

        return corrida

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
    aparecer arriba de todo: es exactamente el argumento del profe sobre por
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
# ACORDES Y ARPEGIOS
# =============================================================================

@dataclass
class GradoDelAcorde:
    """
    Un grado de un acorde y dónde cae en la armónica.

    Campos:
        intervalo     semitonos desde la raíz del acorde (0, 4, 7, 10...)
        nombre_grado  "tonica", "3a mayor", "7a menor"...
        nombre_nota   "A", "Eb"
        agujeros      todas las formas de tocarlo, de grave a agudo
        es_guia       si es la 3a o la 7a, o sea si define el acorde
    """

    intervalo: int
    nombre_grado: str
    nombre_nota: str
    agujeros: list = field(default_factory=list)
    es_guia: bool = False

    def disponible(self):
        return len(self.agujeros) > 0

    def sin_bends(self):
        return [nota for nota in self.agujeros if nota.bend == 0]

    def el_mas_facil(self):
        """
        El agujero más cómodo para tocar este grado.

        Es la respuesta a "¿por dónde agarro esta nota?" cuando estás tocando y
        no tenés tiempo de pensar. Dos criterios, en orden:

        1. MENOS BENDS. Una nota natural sale sola; un bend hay que encontrarlo.

        2. MAS CERCA DEL REGISTRO CENTRAL. Entre dos agujeros igual de fáciles,
           gana el más cercano al 5 y el 6.

        El segundo criterio parece un detalle y no lo es. Al principio la
        función devolvía el agujero más GRAVE, y para el Re de Sib7 proponía el
        ↓1 en vez del ↓4. Los dos dan la nota, pero el registro grave cuesta
        aislarlo, suena flojo y es donde están los bends difíciles. Tu propio
        atril de 12a llama al registro central "la octava que no pide nada".
        """
        if not self.agujeros:
            return None

        # 5.5 es el centro entre el agujero 5 y el 6.
        return min(self.agujeros,
                   key=lambda nota: (nota.bend, abs(nota.agujero - 5.5)))


@dataclass
class ArpegioEnArmonica:
    """Un acorde, y dónde caen todas sus notas en tu armónica."""

    tonalidad_armonica: str
    raiz: str
    tipo: str
    grados: list = field(default_factory=list)

    def nombre(self):
        """Como se escribe el acorde: "F7", "Am", "Bb7"."""
        sufijos = {"mayor": "", "menor": "m", "dominante": "7",
                   "menor7": "m7", "mayor7": "maj7", "disminuido7": "dim7"}
        return f"{self.raiz}{sufijos.get(self.tipo, self.tipo)}"

    def notas_guia(self):
        """La 3a y la 7a: las dos notas que definen el acorde."""
        return [grado for grado in self.grados if grado.es_guia]

    def faltantes(self):
        """Los grados que esta armónica no puede dar sin overblow."""
        return [grado for grado in self.grados if not grado.disponible()]


def arpegio(tonalidad_armonica, raiz, tipo="dominante"):
    """
    Calcula dónde caen las notas de un acorde en tu armónica.

    `raiz` es el nombre de la nota fundamental del acorde ("F", "Bb").
    `tipo` es una clave de tablas.ACORDES_INTERVALOS.

    Es el mismo motor que calcula escalas: un acorde también es una lista de
    intervalos. La diferencia está en lo que se muestra, porque acá importa
    QUE GRADO es cada nota, y no solo que pertenezca.
    """
    if tonalidad_armonica not in tablas.TONALIDADES:
        raise ValueError(f"No conozco la armonica en {tonalidad_armonica!r}")
    if tipo not in tablas.ACORDES_INTERVALOS:
        raise ValueError(
            f"No conozco el acorde {tipo!r}. "
            f"Los que hay son: {', '.join(tablas.ACORDES_INTERVALOS)}"
        )

    clase_raiz = _clase_de_nombre(raiz)
    formas = mapeo.todas_las_formas(tonalidad_armonica)

    grados = []
    for intervalo in tablas.ACORDES_INTERVALOS[tipo]:
        clase = (clase_raiz + intervalo) % 12

        agujeros = []
        for midi in sorted(formas):
            if midi % 12 == clase:
                agujeros.extend(formas[midi])

        grados.append(GradoDelAcorde(
            intervalo=intervalo,
            nombre_grado=tablas.NOMBRES_GRADOS.get(intervalo, f"{intervalo} semitonos"),
            nombre_nota=notas.nombre_de_clase(clase),
            agujeros=agujeros,
            es_guia=intervalo in tablas.GRADOS_GUIA,
        ))

    return ArpegioEnArmonica(
        tonalidad_armonica=tonalidad_armonica, raiz=raiz, tipo=tipo,
        grados=grados,
    )


def progresion_de_blues(tonalidad_armonica, posicion, tipo="dominante"):
    """
    Los doce compases del blues en la posición que elijas.

    Devuelve una lista de doce diccionarios, uno por compás, con el grado
    (I, IV, V), el nombre del acorde y su arpegio ya calculado.

    Es la progresión de tu base de Band in a Box y la del estudio de Carlos
    del Junco. En 12a posición con armónica de Do da Fa7, Sib7 y Do7.
    """
    tonica = posiciones.tonalidad_resultante(tonalidad_armonica, posicion)
    clase_tonica = _clase_de_nombre(tonica)

    # Calculamos los tres acordes una sola vez y después los repartimos.
    acordes = {}
    for grado, semitonos in tablas.GRADOS_DE_LA_PROGRESION.items():
        raiz = notas.nombre_de_clase((clase_tonica + semitonos) % 12)
        acordes[grado] = arpegio(tonalidad_armonica, raiz, tipo)

    compases = []
    for numero, grado in enumerate(tablas.BLUES_DOCE_COMPASES, start=1):
        compases.append({
            "compas": numero,
            "grado": grado,
            "acorde": acordes[grado],
            "cambia": numero == 1 or grado != tablas.BLUES_DOCE_COMPASES[numero - 2],
        })

    return compases


def _clase_de_nombre(nombre):
    """De "Bb" a 10. Acepta bemoles y sostenidos."""
    if nombre in tablas.NOMBRES_NOTAS:
        return tablas.NOMBRES_NOTAS.index(nombre)
    if nombre in tablas.NOMBRES_NOTAS_SOSTENIDOS:
        return tablas.NOMBRES_NOTAS_SOSTENIDOS.index(nombre)
    raise ValueError(f"No reconozco la nota {nombre!r}")

# =============================================================================
# QUÉ EVITAR
# =============================================================================

def notas_a_evitar(tonalidad_armonica, posicion, tipo="dominante"):
    """
    Por cada acorde del blues, los agujeros NATURALES que conviene no pisar.

    LA REGLA: sobre un acorde dominante, la nota a evitar es la 7ª MAYOR de
    ese acorde. El acorde tiene la 7ª menor (el Mib de Fa7), y la 7ª mayor
    (el Mi) está a medio tono: sonando juntas se pelean, y no como la blue
    note, que se pelea a propósito. Es la regla detrás de "evitá el ↑2 en el
    blues en Fa" que apareció en clase: el ↑2 de una armónica en Do es Mi, la
    7ª mayor de Fa.

    Solo se listan los agujeros SIN bend. Un bend no se toca por accidente:
    lo que hay que saber es qué nota natural, de las que salen solas, te
    saca del acorde.

    Devuelve una lista con un diccionario por acorde distinto de la
    progresión: nombre del acorde, la nota, y las Notas (agujeros) a evitar.
    """
    progresion = progresion_de_blues(tonalidad_armonica, posicion, tipo)
    formas = mapeo.todas_las_formas(tonalidad_armonica)

    salida = []
    vistos = set()
    for compas in progresion:
        acorde = compas["acorde"]
        if acorde.nombre() in vistos:
            continue
        vistos.add(acorde.nombre())

        clase_raiz = _clase_de_nombre(acorde.raiz)
        clase_evitar = (clase_raiz + 11) % 12          # la 7ª mayor

        agujeros = [
            nota
            for midi in sorted(formas)
            if midi % 12 == clase_evitar
            for nota in formas[midi]
            if nota.bend == 0
        ]

        salida.append({
            "acorde": acorde.nombre(),
            "grado": compas["grado"],
            "nota": notas.nombre_de_clase(clase_evitar),
            "agujeros": agujeros,
            "por_que": (f"es la 7ª mayor, y choca con la 7ª menor "
                        f"({acorde.grados[3].nombre_nota}) que tiene el acorde"),
        })

    return salida


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

    # PRIMERO la corrida desde la tónica, que es como se estudia y como la
    # escribe el profe en las hojas. Va arriba porque es lo que uno busca.
    corrida = resultado.desde_la_tonica(octavas=2)
    print(f"LA CORRIDA, dos octavas desde la tonica ({resultado.tonica}):")
    print("  " + "  ".join(nota.como_tab() for nota in corrida))
    print("  " + "  ".join(nota.nombre.ljust(len(nota.como_tab())) for nota in corrida))

    con_bend = [nota for nota in resultado.agujeros if nota.bend > 0]

    # DESPUÉS el inventario completo, que incluye los otros registros y las dos
    # formas de tocar una nota ambigua. Los que piden bend van con asterisco.
    print(f"\nTODOS LOS AGUJEROS DE LA ESCALA EN LA ARMONICA ({len(resultado.agujeros)}):")
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


# =============================================================================
# El círculo de quintas, por posiciones
# =============================================================================

# El modo que resulta en cada posición cuando se toca la escala mayor de la
# armónica desde otra tónica. Las posiciones 7 a 11 caen fuera de la escala
# de la armónica: no tienen un modo diatónico, y se dejan vacías a propósito.
MODOS_POR_POSICION = {
    1: "jónico (straight harp)",
    2: "mixolidio (cross harp)",
    3: "dórico",
    4: "eólico",
    5: "frigio",
    6: "locrio",
    12: "lidio",
}


def circulo_de_quintas(tonalidad_armonica):
    """
    Las doce posiciones de una armónica, en orden, con el tono en que se toca
    en cada una y su relativa menor. Es el círculo de quintas leído desde la
    armónica: cada posición es un paso de quinta, y por eso el mismo dibujo
    sirve para cualquier armónica, girado.
    """
    if tonalidad_armonica not in tablas.TONALIDADES:
        raise ValueError(f"No conozco la armonica en {tonalidad_armonica!r}")
    clase_armonica = tablas.TONALIDADES[tonalidad_armonica] % 12
    sectores = []
    for posicion in sorted(tablas.POSICIONES):
        desplazamiento = tablas.POSICIONES[posicion]
        clase_tono = (clase_armonica + desplazamiento) % 12
        sectores.append({
            "posicion": posicion,
            "nombre": tablas.NOMBRES_POSICIONES[posicion],
            "desplazamiento": desplazamiento,
            "tono": notas.nombre_de_clase(clase_tono),
            "relativa_menor": notas.nombre_de_clase((clase_tono - 3) % 12) + "m",
            "modo": MODOS_POR_POSICION.get(posicion, ""),
            "con_tabla": posicion in tablas.POSICIONES_CON_TABLA,
        })
    return sectores


def armonica_para(tono_cancion, posicion):
    """
    Qué armónica hace falta para tocar una canción en ese tono en esa
    posición: la del tono, bajada el desplazamiento de la posición. Una
    canción en Sol en 2a posición pide armónica en Do; en 12a, en Re.
    """
    if posicion not in tablas.POSICIONES:
        raise ValueError(f"La posicion {posicion} no existe")
    clase = (_clase_de_nombre(tono_cancion) - tablas.POSICIONES[posicion]) % 12
    return nombre_de_armonica(clase)


def nombre_de_armonica(clase):
    """El nombre de la armónica de esa clase, como figura en tablas.TONALIDADES."""
    for nombre, midi in tablas.TONALIDADES.items():
        if midi % 12 == clase % 12:
            return nombre
    return notas.nombre_de_clase(clase)


def circulo_para_cancion(tono_cancion):
    """
    Las doce posiciones para una canción en ese tono: qué armónica pide cada
    una, y si es de las que el usuario tiene (tablas.TONALIDADES_DISPONIBLES).
    """
    _clase_de_nombre(tono_cancion)  # valida el nombre
    sectores = []
    for posicion in sorted(tablas.POSICIONES):
        armonica = armonica_para(tono_cancion, posicion)
        sectores.append({
            "posicion": posicion,
            "nombre": tablas.NOMBRES_POSICIONES[posicion],
            "desplazamiento": tablas.POSICIONES[posicion],
            "armonica": armonica,
            "la_tenes": armonica in tablas.TONALIDADES_DISPONIBLES,
            "modo": MODOS_POR_POSICION.get(posicion, ""),
            "con_tabla": posicion in tablas.POSICIONES_CON_TABLA,
        })
    return sectores
