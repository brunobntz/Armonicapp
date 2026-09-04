"""
tonalidad.py — En qué tono está una grabación, y con qué armónica tocarla.

PARA QUE SIRVE

Te pasan una grabación de armónica y no sabés en qué tono está. Este módulo te
dice el tono, qué armónica agarrar y en qué posición vas a estar tocando.

DOS PREGUNTAS DISTINTAS, DOS METODOS DISTINTOS

  1. QUE ARMONICA se usó. Se resuelve mirando qué notas suenan: una armónica
     diatónica solo puede dar treinta notas de las ochenta y ocho posibles, así
     que el conjunto de notas tocadas delata cuál era. Es un método muy
     confiable, casi un cerrojo.

  2. EN QUE TONO está. Es más difícil, porque la misma armónica sirve para doce
     tonos distintos: eso son las posiciones. Acá hay que mirar cuáles notas se
     usan MAS, no solo cuáles aparecen.

La segunda es la que puede equivocarse, y el módulo lo dice cuando duda.

COMO SE DETECTA EL TONO

Se cuenta cuánto tiempo suena cada una de las doce notas y se compara ese
perfil contra el de cada tonalidad posible. La idea es de Carol Krumhansl, una
psicóloga de la música que en los años ochenta midió con oyentes reales qué tan
"estable" suena cada nota dentro de una tonalidad: la tónica manda, después la
quinta, después la tercera, y las alteraciones casi no aparecen.

Comparar esos perfiles es una correlación, la misma cuenta que usarías para ver
si dos series de números se mueven juntas.

DONDE FALLA, Y HAY QUE DECIRLO

El método fue pensado para música tonal clásica y el blues no lo es del todo.
Un blues en Fa usa el Lab y el Mib, que en Fa mayor no existen, así que el
perfil se parece tanto a Fa mayor como a Re menor. Por eso el módulo devuelve
VARIOS candidatos ordenados, y avisa cuando los primeros están muy parejos.
"""

from dataclasses import dataclass, field

from armonica import mapeo, notas, posiciones, tablas


# Los perfiles de Krumhansl y Kessler (1982). Cada número dice qué tan estable
# suena ese grado dentro de la tonalidad, medido con oyentes reales.
# El índice 0 es la tónica, el 1 la segunda menor, y así.
PERFIL_MAYOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                2.52, 5.19, 2.39, 3.66, 2.29, 2.88]

PERFIL_MENOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


@dataclass
class Candidato:
    """Una tonalidad posible, con qué tan bien explica lo tocado."""

    tonica: str
    modo: str          # "mayor" o "menor"
    puntaje: float     # correlación, de -1 a 1

    def nombre(self):
        return f"{self.tonica} {self.modo}"


@dataclass
class Sugerencia:
    """Una forma de tocar en ese tono: qué armónica y en qué posición."""

    tonalidad_armonica: str
    posicion: int
    tonica: str
    la_tenes: bool = False

    def nombre_posicion(self):
        return tablas.NOMBRES_POSICIONES[self.posicion]


@dataclass
class Analisis:
    """Todo lo que se pudo deducir de una grabación."""

    armonica_probable: str = ""
    cobertura: float = 0.0        # qué proporción de las notas caben en esa armónica
    candidatos: list = field(default_factory=list)
    sugerencias: list = field(default_factory=list)
    sugerencias_alternativas: list = field(default_factory=list)
    notas_usadas: int = 0

    def hay_dudas(self, margen=0.05):
        """
        Si los dos primeros candidatos están muy parejos.

        Cuando pasa, decir "está en Fa" sería fingir una certeza que no hay.
        """
        if len(self.candidatos) < 2:
            return False
        if self.son_relativas():
            return True
        return (self.candidatos[0].puntaje - self.candidatos[1].puntaje) < margen

    def son_relativas(self):
        """
        Si los dos primeros candidatos son una tonalidad y su relativa.

        UN CASO QUE HAY QUE MARCAR SIEMPRE, aunque los puntajes no estén
        parejos. Fa mayor y Re menor tienen EXACTAMENTE las mismas siete notas:
        lo único que las distingue es cuál se siente como el centro, y eso
        depende del acompañamiento, no de las notas.

        Este método no puede resolverlo, y decir "es Re menor" cuando podría
        ser Fa mayor sería afirmar de más. Paso con la grabacion de Bruno, que
        estaba en Fa y el analisis reportaba Re menor.
        """
        if len(self.candidatos) < 2:
            return False

        primero, segundo = self.candidatos[0], self.candidatos[1]
        if primero.modo == segundo.modo:
            return False

        mayor = primero if primero.modo == "mayor" else segundo
        menor = segundo if primero.modo == "mayor" else primero

        # La relativa menor está tres semitonos por debajo de la mayor.
        from armonica import tablas as _tablas
        clase_mayor = _tablas.NOMBRES_NOTAS.index(mayor.tonica)
        clase_menor = _tablas.NOMBRES_NOTAS.index(menor.tonica)
        return (clase_mayor - clase_menor) % 12 == 3


# =============================================================================
# 1. Qué armónica se usó
# =============================================================================

def detectar_armonica(eventos, tonalidades=None):
    """
    Deduce qué armónica se usó, mirando qué notas suenan.

    Devuelve (tonalidad, cobertura). La cobertura es qué proporción del tiempo
    tocado cae en notas que esa armónica puede dar.

    POR QUE FUNCIONA TAN BIEN

    Una armónica diatónica da treinta notas contadas, incluyendo bends. Si
    alguien toca un Fa# y un Sol# en el registro medio, esa armónica en Do
    queda descartada al instante. Con veinte o treinta notas tocadas, casi
    siempre queda una sola candidata en pie.

    Se pesa por DURACION y no por cantidad: una nota larga es más informativa
    que un chirrido de paso.
    """
    if tonalidades is None:
        tonalidades = list(tablas.TONALIDADES)

    reconocidas = [e for e in eventos if e.nota is not None]
    if not reconocidas:
        return "", 0.0

    # Cuánto tiempo suena cada NOTA EXACTA, con su octava.
    #
    # POR QUE CON OCTAVA Y NO SOLO LA CLASE DE NOTA. Porque la octava es
    # información real y la necesitamos. Contando solo clases, la armónica en
    # Do y la de Mib podían dar las mismas seis notas de la grabación de Bruno
    # y quedaban empatadas; la función terminaba eligiendo por orden alfabético
    # y se equivocaba. Mirando las octavas, la de Do cubre el 100% y la de Mib
    # el 94%, y no hay empate que romper.
    tiempo_por_nota = {}
    for evento in reconocidas:
        midi = evento.nota.midi
        tiempo_por_nota[midi] = tiempo_por_nota.get(midi, 0.0) + evento.duracion_seg

    total = sum(tiempo_por_nota.values())
    if total <= 0:
        return "", 0.0

    resultados = []

    for tonalidad in tonalidades:
        # Para cada nota que da esta armónica, con cuántos bends sale.
        bends_por_nota = {}
        for nota in mapeo.todas_las_notas(tonalidad):
            anterior = bends_por_nota.get(nota.midi)
            if anterior is None or nota.bend < anterior:
                bends_por_nota[nota.midi] = nota.bend

        cubierto = sum(
            tiempo for midi, tiempo in tiempo_por_nota.items()
            if midi in bends_por_nota
        )
        cobertura = cubierto / total

        # El costo en BENDS, como desempate. Si dos armónicas cubren lo mismo,
        # gana aquella donde la música sale más fácil: es el criterio con el
        # que un músico elige qué armónica agarrar.
        costo = sum(
            bends_por_nota[midi] * tiempo
            for midi, tiempo in tiempo_por_nota.items()
            if midi in bends_por_nota
        )

        resultados.append((cobertura, -costo / total, tonalidad))

    resultados.sort(reverse=True)
    mejor_cobertura, _, mejor = resultados[0]

    return mejor, mejor_cobertura


# =============================================================================
# 2. En qué tono está
# =============================================================================

def perfil_de_clases(eventos):
    """
    Cuánto tiempo suena cada una de las doce notas, normalizado.

    Devuelve una lista de doce números que suman 1. Es el "resumen" de la
    grabación con el que después se compara cada tonalidad.

    Pesamos por duración: si el Fa suena tres segundos y el Si medio, el Fa
    pesa seis veces más. Contar apariciones trataría igual a una redonda que a
    una nota de paso.
    """
    perfil = [0.0] * 12

    for evento in eventos:
        if evento.nota is None:
            continue
        perfil[evento.nota.midi % 12] += evento.duracion_seg

    total = sum(perfil)
    if total <= 0:
        return perfil

    return [valor / total for valor in perfil]


def detectar_tonalidad(eventos, cuantos=4):
    """
    Los tonos que mejor explican lo tocado, del más probable al menos.

    Prueba las veinticuatro tonalidades posibles (doce mayores y doce menores)
    y las ordena por qué tan bien su perfil se parece al de la grabación.
    """
    perfil = perfil_de_clases(eventos)
    if sum(perfil) <= 0:
        return []

    candidatos = []
    for clase in range(12):
        nombre = notas.nombre_de_clase(clase)
        candidatos.append(Candidato(
            nombre, "mayor", _correlacion(perfil, _rotar(PERFIL_MAYOR, clase))
        ))
        candidatos.append(Candidato(
            nombre, "menor", _correlacion(perfil, _rotar(PERFIL_MENOR, clase))
        ))

    candidatos.sort(key=lambda c: -c.puntaje)
    return candidatos[:cuantos]


def _rotar(perfil, cuanto):
    """Corre un perfil para que su tónica caiga en otra nota."""
    return [perfil[(indice - cuanto) % 12] for indice in range(12)]


def _correlacion(primera, segunda):
    """
    Cuánto se parecen dos series de números, entre -1 y 1.

    Es la correlación de Pearson: se le resta a cada serie su promedio y se ve
    si suben y bajan juntas. Restar el promedio importa, porque si no,
    cualquier par de series con números grandes parecería parecido.
    """
    media_primera = sum(primera) / len(primera)
    media_segunda = sum(segunda) / len(segunda)

    diferencias_primera = [valor - media_primera for valor in primera]
    diferencias_segunda = [valor - media_segunda for valor in segunda]

    numerador = sum(a * b for a, b in zip(diferencias_primera, diferencias_segunda))
    magnitud_primera = sum(a * a for a in diferencias_primera) ** 0.5
    magnitud_segunda = sum(b * b for b in diferencias_segunda) ** 0.5

    if magnitud_primera <= 0 or magnitud_segunda <= 0:
        return 0.0

    return numerador / (magnitud_primera * magnitud_segunda)


# =============================================================================
# 3. Con qué armónica tocarlo
# =============================================================================

def sugerir_armonicas(tonica, disponibles=None, cuantas=5):
    """
    Con qué armónicas se puede tocar en ese tono, y en qué posición.

    Ordena por lo que uno realmente elegiría: primero las armónicas que tenés,
    y dentro de esas, las posiciones más usadas. La 2a antes que la 7a, porque
    es donde la armónica cae naturalmente.
    """
    if disponibles is None:
        disponibles = tablas.TONALIDADES_DISPONIBLES

    sugerencias = []
    for tonalidad in tablas.TONALIDADES:
        for posicion in tablas.POSICIONES:
            if posiciones.tonalidad_resultante(tonalidad, posicion) == tonica:
                sugerencias.append(Sugerencia(
                    tonalidad_armonica=tonalidad,
                    posicion=posicion,
                    tonica=tonica,
                    la_tenes=tonalidad in disponibles,
                ))

    # El orden de preferencia: primero lo que tenés a mano, y dentro de eso,
    # las posiciones que se usan de verdad.
    orden_de_posiciones = {2: 0, 1: 1, 3: 2, 12: 3, 4: 4, 5: 5}

    sugerencias.sort(key=lambda s: (
        not s.la_tenes,
        orden_de_posiciones.get(s.posicion, 10),
        s.posicion,
    ))

    return sugerencias[:cuantas]


def analizar(eventos, disponibles=None):
    """
    El análisis completo: qué armónica, qué tono, y qué agarrar para tocarlo.
    """
    armonica, cobertura = detectar_armonica(eventos)
    candidatos = detectar_tonalidad(eventos)

    analisis = Analisis(
        armonica_probable=armonica,
        cobertura=cobertura,
        candidatos=candidatos,
        notas_usadas=sum(1 for e in eventos if e.nota is not None),
    )

    if candidatos:
        analisis.sugerencias = sugerir_armonicas(candidatos[0].tonica, disponibles)

        # Si los dos primeros son relativas, no podemos elegir entre ellos, así
        # que damos las opciones para los dos. Sería raro mostrar solo uno y
        # dos renglones más arriba haber dicho que no sabemos cuál es.
        if analisis.son_relativas():
            analisis.sugerencias_alternativas = sugerir_armonicas(
                candidatos[1].tonica, disponibles
            )

    return analisis


# =============================================================================
# El informe
# =============================================================================

def informe(analisis, ruta=""):
    """El resultado en texto."""
    lineas = []
    lineas.append("=" * 72)
    lineas.append("  QUE ARMONICA Y EN QUE TONO")
    if ruta:
        lineas.append(f"  {ruta}")
    lineas.append("=" * 72)

    if not analisis.candidatos:
        lineas.append("")
        lineas.append("  No hay notas suficientes para deducir nada.")
        return "\n".join(lineas)

    # --- La armónica: el dato confiable ---
    lineas.append("")
    lineas.append(f"  Notas analizadas: {analisis.notas_usadas}")
    lineas.append("")
    if analisis.cobertura >= 0.98:
        lineas.append(f"  ARMONICA: en {analisis.armonica_probable}")
        lineas.append(f"  Todas las notas tocadas caben en esa armonica.")
    elif analisis.cobertura >= 0.9:
        lineas.append(f"  ARMONICA: probablemente en {analisis.armonica_probable}")
        lineas.append(f"  El {analisis.cobertura * 100:.0f}% de lo tocado cabe ahi. "
                      f"El resto puede ser un overblow o una nota mal detectada.")
    else:
        lineas.append(f"  ARMONICA: dudoso. La que mas se acerca es "
                      f"{analisis.armonica_probable}, pero solo cubre el "
                      f"{analisis.cobertura * 100:.0f}% de lo tocado.")
        lineas.append("  Puede haber varias armonicas en la grabacion, o notas")
        lineas.append("  mal detectadas.")

    # --- El tono: el dato dudoso ---
    lineas.append("")
    primero = analisis.candidatos[0]
    if analisis.son_relativas():
        segundo = analisis.candidatos[1]
        lineas.append(f"  TONO: {primero.nombre()} o {segundo.nombre()}.")
        lineas.append("  Son relativas: tienen EXACTAMENTE las mismas siete notas.")
        lineas.append("  Lo unico que las distingue es cual se siente como centro,")
        lineas.append("  y eso lo define el acompanamiento, no las notas. Este")
        lineas.append("  metodo no puede resolverlo, y no vale la pena fingir que si.")
    elif analisis.hay_dudas():
        segundo = analisis.candidatos[1]
        lineas.append(f"  TONO: dudoso entre {primero.nombre()} y {segundo.nombre()}.")
        lineas.append("  Los dos explican lo tocado casi igual de bien.")
    else:
        lineas.append(f"  TONO: {primero.nombre()}")

    lineas.append("")
    lineas.append("  Los candidatos, del que mejor explica al que menos:")
    for candidato in analisis.candidatos:
        barra = "#" * int(max(0.0, candidato.puntaje) * 30)
        lineas.append(f"    {candidato.nombre():<10} {candidato.puntaje:+.2f}  {barra}")

    # --- Qué agarrar ---
    def listar(titulo, sugerencias):
        lineas.append("")
        lineas.append(f"  {titulo}")
        for sugerencia in sugerencias:
            marca = "" if sugerencia.la_tenes else "   (no la tenes)"
            lineas.append(f"    armonica en {sugerencia.tonalidad_armonica:<3} "
                          f"-> {sugerencia.nombre_posicion()}{marca}")

    if analisis.sugerencias:
        listar(f"PARA TOCAR EN {primero.tonica}:", analisis.sugerencias)

    if analisis.sugerencias_alternativas:
        listar(f"Y SI FUERA {analisis.candidatos[1].tonica}:",
               analisis.sugerencias_alternativas)

    lineas.append("")
    lineas.append("  La armonica se deduce de QUE notas suenan, y es confiable.")
    lineas.append("  El tono se deduce de CUALES se usan mas, y puede fallar:")
    lineas.append("  el metodo esta pensado para musica tonal y el blues no lo es.")

    return "\n".join(lineas)
