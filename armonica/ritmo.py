"""
ritmo.py — Mide si tocás a tiempo, y de qué manera te desviás.

POR QUÉ ESTE MODULO ES EL MAS IMPORTANTE DE LA APP

El registro de ocho meses de clases de Bruno dice siempre lo mismo:

    "El principal desafio de Bruno es el ritmo, no la precision de las notas,
     lo cual hace que se adelante a la pista"          (el profe, 18/03)

    "Bruno reaccionaba a los cambios de acorde demasiado tarde, haciendo que
     las frases sonaran apresuradas"                   (el profe, 19/05)

Todo lo demás que hace esta app (qué agujero, qué escala, qué afinación) mide
la elección de notas, que según su propio profesor NO es el problema. Este
módulo mide el problema.

QUE MIDE EXACTAMENTE

Cada nota tiene un instante de comienzo. Si sabemos a qué velocidad va la base,
podemos dibujar una grilla de pulsos y preguntar, nota por nota, cuántos
milisegundos antes o después del pulso caíste.

    desvío negativo = tocaste ANTES del pulso (te adelantaste)
    desvío positivo = tocaste DESPUES del pulso (llegaste tarde)

LO QUE MAS IMPORTA NO ES EL PROMEDIO

Las dos citas de arriba se contradicen: una dice que se adelanta y la otra que
llega tarde. No es una contradicción, es el dato. Si un músico se adelantara
siempre, alcanzaría con avisarle. Lo que pasa es que el desvío es INESTABLE.

Por eso el reporte muestra tres números y no uno:

    - el promedio, que dice si hay un sesgo hacia adelante o hacia atrás
    - la DISPERSION, que dice cuánto varía de nota a nota. Este es el número
      que mide de verdad la solidez rítmica.
    - el porcentaje de notas que cayeron dentro de la tolerancia

Un promedio de cero con una dispersión de 80 ms no es tocar bien: es tocar mal
para los dos lados en partes iguales.

CUANTO PODEMOS AFIRMAR

La resolución de la app es de unos 6 milisegundos (ver
config.CORRECCION_INICIO_SEG, donde está medido). Los desvíos que importan
musicalmente arrancan en 30 ms y se vuelven audibles alrededor de 50. Así que
hay margen de sobra: medimos con una precisión diez veces mejor que el
fenómeno.
"""

import math
from dataclasses import dataclass, field
from statistics import mean, median, pstdev

import config


# En un blues de doce compases, los acordes cambian al empezar estos compases.
# Es la progresión que Bruno trabaja con el estudio de Carlos del Junco:
#   Fa7 | Sib7 | Fa7 | Fa7 | Sib7 | Sib7 | Fa7 | Fa7 | Do7 | Sib7 | Fa7 | Do7
# Los cambios son los compases 2, 3, 5, 7, 9, 10, 11 y 12.
COMPASES_DE_CAMBIO_BLUES = [2, 3, 5, 7, 9, 10, 11, 12]


@dataclass
class DesvioNota:
    """
    Una nota y su relación con el pulso más cercano.

    Campos:
        evento             la nota tocada
        indice_pulso       qué pulso de la grilla es el más cercano
        compas             en qué compás cae (empezando en 1)
        tiempo_del_compas  qué tiempo del compás es (1, 2, 3, 4...)
        desvio_seg         cuánto antes (negativo) o después (positivo)
        es_cambio          si ese compás empieza un acorde nuevo
    """

    evento: object
    indice_pulso: int
    compas: int
    tiempo_del_compas: int
    desvio_seg: float
    es_cambio: bool = False

    @property
    def desvio_ms(self):
        return self.desvio_seg * 1000.0

    @property
    def se_adelanto(self):
        return self.desvio_seg < 0

    def a_tiempo(self, tolerancia_ms=None):
        if tolerancia_ms is None:
            tolerancia_ms = config.TOLERANCIA_RITMO_MS
        return abs(self.desvio_ms) <= tolerancia_ms


@dataclass
class AnalisisRitmico:
    """El resultado completo: la grilla usada y el desvío de cada nota."""

    bpm: float
    compas: int
    subdivision: int
    offset_seg: float
    desvios: list = field(default_factory=list)

    @property
    def duracion_pulso_seg(self):
        return duracion_de_pulso(self.bpm)

    def desvios_ms(self):
        return [d.desvio_ms for d in self.desvios]

    def sesgo_ms(self):
        """
        El promedio. Dice si hay una tendencia a adelantarse o a atrasarse.
        Negativo = te adelantás en promedio.
        """
        valores = self.desvios_ms()
        return mean(valores) if valores else 0.0

    def dispersion_ms(self):
        """
        EL NUMERO QUE MAS IMPORTA. Cuánto varía el desvío de nota a nota.

        Es la desviación estándar. Si vale 20, tus notas caen casi siempre en
        el mismo lugar respecto del pulso, y eso es tocar sólido aunque el
        promedio no sea cero. Si vale 80, cada nota cae en un lugar distinto,
        y ahí el promedio no significa nada.
        """
        valores = self.desvios_ms()
        return pstdev(valores) if len(valores) > 1 else 0.0

    def mediana_ms(self):
        valores = self.desvios_ms()
        return median(valores) if valores else 0.0

    def ajuste_vs_azar(self):
        """
        Cuánto mejor que el AZAR explica la grilla lo que tocaste.

        POR QUE ESTE NUMERO ES IMPRESCINDIBLE

        La dispersión sola engaña. Si medís contra una grilla muy densa,
        cualquier nota cae cerca de algún punto y la dispersión baja sin que
        hayas tocado mejor. Hace falta un punto de comparación.

        Si las notas cayeran completamente al azar dentro de la grilla, la
        dispersión valdría paso/raiz(12), que es 0.289 veces el paso. Ese es el
        techo. Dividimos la dispersión medida por ese valor:

            1.00 o más -> la grilla no explica nada. O el tempo esta mal, o el
                          compás está mal, o no estabas tocando a tiempo.
            0.60       -> hay estructura, pero floja
            0.30       -> tocaste claramente sobre la grilla
            0.10       -> muy preciso

        Sin esto, la app podría informar con toda seriedad "dispersión 63 ms"
        sobre una medición que no significa nada. Preferimos decir cuándo no
        sabemos.
        """
        if len(self.desvios) < 4:
            return None

        paso_ms = paso_de_grilla(self.bpm, self.subdivision) * 1000.0
        dispersion_del_azar = paso_ms / math.sqrt(12)

        if dispersion_del_azar <= 0:
            return None

        return self.dispersion_ms() / dispersion_del_azar

    def la_grilla_explica_algo(self, limite=0.75):
        """
        Si podemos confiar en el análisis rítmico.

        Devuelve False cuando las notas están tan repartidas como si fueran al
        azar. En ese caso los demás números de este objeto no significan nada y
        no hay que mostrarlos como si fueran un diagnóstico.
        """
        ajuste = self.ajuste_vs_azar()
        return ajuste is not None and ajuste < limite

    def porcentaje_a_tiempo(self, tolerancia_ms=None):
        if not self.desvios:
            return 0.0
        buenas = sum(1 for d in self.desvios if d.a_tiempo(tolerancia_ms))
        return 100.0 * buenas / len(self.desvios)

    def peor_desvio(self):
        if not self.desvios:
            return None
        return max(self.desvios, key=lambda d: abs(d.desvio_ms))

    def en_los_cambios(self):
        """Los desvíos de las notas que caen en un compás de cambio de acorde."""
        return [d for d in self.desvios if d.es_cambio]

    def fuera_de_los_cambios(self):
        return [d for d in self.desvios if not d.es_cambio]

    def por_tiempo_del_compas(self):
        """
        Agrupa los desvíos según en qué tiempo del compás cayeron.

        Sirve para ver si el problema es parejo o si se concentra en algún
        lugar. Adelantarse solo en el tiempo 1 (donde suele caer el cambio de
        acorde) es un problema distinto de adelantarse siempre.
        """
        grupos = {}
        for desvio in self.desvios:
            grupos.setdefault(desvio.tiempo_del_compas, []).append(desvio.desvio_ms)
        return grupos


def duracion_de_pulso(bpm):
    """
    Cuántos segundos dura un pulso (una negra) a esa velocidad.

    A 60 BPM cada pulso dura exactamente un segundo. A 120, medio segundo.
    """
    if bpm <= 0:
        raise ValueError(f"El BPM tiene que ser mayor que cero, recibi {bpm}")
    return 60.0 / bpm


def paso_de_grilla(bpm, subdivision=1):
    """
    Cuántos segundos hay entre dos puntos de la grilla.

    `subdivision` dice contra qué figura medimos:
        1 = negras     (un punto por pulso)
        2 = corcheas   (dos puntos por pulso)
        3 = tresillos  (tres, que es la sensación de shuffle del blues)
        4 = semicorcheas

    Elegir bien esto importa. Si tocás corcheas y medís contra negras, la mitad
    de tus notas van a aparecer con medio pulso de desvío, y el reporte sería
    basura. En el blues casi siempre conviene 2 o 3.
    """
    if subdivision < 1:
        raise ValueError("La subdivision tiene que ser 1 o mas")
    return duracion_de_pulso(bpm) / subdivision


def estimar_offset(eventos, bpm, subdivision=1, candidatos=200):
    """
    Encuentra dónde arranca la grilla, o sea dónde cae el primer pulso.

    EL PROBLEMA. Sabemos a qué velocidad va la base, pero no en qué instante
    exacto de la grabación cae el primer pulso. Si nos equivocamos en eso,
    todos los desvíos salen corridos por igual y el análisis no vale nada.

    LA SOLUCION. Probamos muchos desplazamientos posibles dentro de un paso de
    grilla y nos quedamos con el que hace que las notas caigan más cerca de los
    pulsos. Es razonable: quien tocó estaba tratando de seguir la base, así que
    el desplazamiento correcto es el que mejor explica lo que tocó.

    Usamos la MEDIANA de los desvíos absolutos y no el promedio, para que dos o
    tres notas muy fuera de lugar no arrastren la estimación.
    """
    if not eventos:
        return 0.0

    paso = paso_de_grilla(bpm, subdivision)
    inicios = [evento.inicio_seg for evento in eventos]

    mejor_offset = 0.0
    mejor_error = None

    for numero in range(candidatos):
        offset = paso * numero / candidatos
        errores = [abs(_distancia_al_pulso(inicio, offset, paso)) for inicio in inicios]
        error = median(errores)

        if mejor_error is None or error < mejor_error:
            mejor_error = error
            mejor_offset = offset

    return mejor_offset


def ajustar_offset(offset_medido, eventos, bpm, subdivision=1):
    """
    Corrige un offset MEDIDO con la fase que mejor explica lo tocado.

    Cuando la app toca la base ella misma, sabe en qué instante arrancó el
    compás 1 respecto de la grabación: ese es el offset medido. Pero trae un
    error chico y constante, la latencia del micrófono y del navegador, que
    en esta máquina anda por las decenas de milisegundos. Sin corregirlo,
    todos los desvíos saldrían corridos por igual.

    `estimar_offset` encuentra la fase (dónde cae el pulso, módulo un paso de
    grilla) pero no sabe cuál es el compás 1. Acá se juntan las dos cosas:
    se toma la fase estimada y, de todos los instantes que tienen esa fase,
    el más cercano al medido. Así el número de compás lo pone la medición y
    los milisegundos los pone lo tocado, y la corrección nunca se aleja más
    de medio paso de grilla del valor medido.
    """
    if not eventos:
        return offset_medido
    paso = paso_de_grilla(bpm, subdivision)
    fase = estimar_offset(eventos, bpm, subdivision)
    vueltas = round((offset_medido - fase) / paso)
    return fase + vueltas * paso


def estimar_bpm(eventos, bpm_minimo=45.0, bpm_maximo=200.0, subdivision=1,
                paso_bpm=0.5):
    """
    Estima la velocidad de la base a partir de lo tocado. Devuelve (bpm, error).

    Prueba cada BPM del rango, calcula el mejor offset para ese BPM, y se queda
    con la combinación que deja las notas más cerca de la grilla.

    OJO CON ESTO. Estimar el tempo desde las notas es poco confiable: si tocaste
    corcheas parejas, 60 BPM y 120 BPM explican lo mismo, y el método puede
    elegir cualquiera. Siempre que sepas el BPM de tu base, pasalo a mano.
    Esta función es para cuando no lo sabés, y su resultado hay que mirarlo con
    desconfianza.
    """
    if len(eventos) < 4:
        return None, None

    mejor_bpm = None
    mejor_error = None

    bpm = bpm_minimo
    while bpm <= bpm_maximo:
        paso = paso_de_grilla(bpm, subdivision)
        offset = estimar_offset(eventos, bpm, subdivision, candidatos=60)
        errores = [
            abs(_distancia_al_pulso(evento.inicio_seg, offset, paso))
            for evento in eventos
        ]
        # Dividimos por el paso para no premiar a los BPM rápidos, donde la
        # grilla es tan densa que cualquier nota cae cerca de algún punto.
        error = median(errores) / paso

        if mejor_error is None or error < mejor_error:
            mejor_error = error
            mejor_bpm = bpm

        bpm += paso_bpm

    return mejor_bpm, mejor_error


def analizar(eventos, bpm, compas=4, subdivision=1, offset_seg=None,
             compases_de_cambio=None, compases_por_vuelta=12):
    """
    El análisis completo. Devuelve un AnalisisRitmico.

    `compas` es cuántos pulsos tiene cada compás (4 para un 4/4).
    `subdivision` contra qué figura medimos (ver paso_de_grilla).
    `offset_seg` dónde cae el primer pulso; si no lo pasás, se estima.
    `compases_de_cambio` en qué compases cambia el acorde, para poder comparar
        esos momentos contra el resto. Por defecto, los del blues de doce.
    `compases_por_vuelta` cada cuántos compases se repite la progresión: doce
        en el blues, lo que dure el coro en una base de Band-in-a-Box.
    """
    if not eventos:
        return AnalisisRitmico(bpm=bpm, compas=compas, subdivision=subdivision,
                               offset_seg=0.0, desvios=[])

    if compases_de_cambio is None:
        compases_de_cambio = COMPASES_DE_CAMBIO_BLUES

    if offset_seg is None:
        offset_seg = estimar_offset(eventos, bpm, subdivision)

    paso = paso_de_grilla(bpm, subdivision)
    puntos_por_compas = compas * subdivision

    desvios = []
    for evento in eventos:
        # A qué punto de la grilla apuntaba esta nota, y cuánto le erró.
        indice = _pulso_mas_cercano(evento.inicio_seg, offset_seg, paso)
        desvio = evento.inicio_seg - (offset_seg + indice * paso)

        # En qué compás y en qué tiempo del compás cae ese punto.
        # El módulo y la división entera hacen el trabajo: si hay 8 puntos por
        # compás y estamos en el punto 19, es el compás 3 (19 // 8 = 2, más 1)
        # y el punto 4 de ese compás (19 % 8 = 3, más 1).
        numero_compas = indice // puntos_por_compas + 1
        punto_en_compas = indice % puntos_por_compas
        tiempo_del_compas = punto_en_compas // subdivision + 1

        # Los compases de cambio se repiten cada vuelta: cada doce en el blues.
        compas_en_la_vuelta = (numero_compas - 1) % compases_por_vuelta + 1

        desvios.append(DesvioNota(
            evento=evento,
            indice_pulso=indice,
            compas=numero_compas,
            tiempo_del_compas=tiempo_del_compas,
            desvio_seg=desvio,
            es_cambio=compas_en_la_vuelta in compases_de_cambio,
        ))

    return AnalisisRitmico(
        bpm=bpm, compas=compas, subdivision=subdivision,
        offset_seg=offset_seg, desvios=desvios,
    )


def _pulso_mas_cercano(instante, offset, paso):
    """Qué punto de la grilla queda más cerca de ese instante."""
    return int(round((instante - offset) / paso))


def _distancia_al_pulso(instante, offset, paso):
    """Cuántos segundos separan ese instante del punto de grilla más cercano."""
    indice = _pulso_mas_cercano(instante, offset, paso)
    return instante - (offset + indice * paso)


# =============================================================================
# El diagnóstico en palabras
# =============================================================================

def diagnostico(analisis, tolerancia_ms=None):
    """
    Traduce los números a frases, usando el vocabulario de tus clases.

    Devuelve una lista de textos. Cada regla es explícita y con su umbral, así
    que se puede discutir y ajustar. No hay nada mágico acá.
    """
    if tolerancia_ms is None:
        tolerancia_ms = config.TOLERANCIA_RITMO_MS

    if not analisis.desvios:
        return ["No hay notas suficientes para analizar el ritmo."]

    frases = []
    sesgo = analisis.sesgo_ms()
    dispersion = analisis.dispersion_ms()
    a_tiempo = analisis.porcentaje_a_tiempo(tolerancia_ms)

    # --- Regla 1: la dispersión, que es lo que mide la solidez ---
    if dispersion < 25:
        frases.append(
            f"Tu tiempo es solido: las notas caen siempre mas o menos en el "
            f"mismo lugar del pulso (dispersion {dispersion:.0f} ms)."
        )
    elif dispersion < 50:
        frases.append(
            f"Tu tiempo es razonable pero variable (dispersion {dispersion:.0f} ms). "
            f"Cada nota cae en un lugar algo distinto respecto del pulso."
        )
    else:
        frases.append(
            f"El tiempo esta inestable: dispersion de {dispersion:.0f} ms. "
            f"Es el numero a bajar, mas que el promedio."
        )

    # --- Regla 2: el sesgo, adelantarse o atrasarse ---
    if abs(sesgo) < 15:
        frases.append(
            f"No hay tendencia a adelantarte ni a atrasarte (promedio "
            f"{sesgo:+.0f} ms)."
        )
    elif sesgo < 0:
        frases.append(
            f"Te adelantas al pulso: en promedio {abs(sesgo):.0f} ms antes. "
            f"Es lo que el profe viene marcando."
        )
    else:
        frases.append(
            f"Llegas tarde al pulso: en promedio {sesgo:.0f} ms despues."
        )

    # --- Regla 3: cuántas cayeron bien ---
    frases.append(
        f"{a_tiempo:.0f}% de las notas cayeron dentro de {tolerancia_ms:.0f} ms "
        f"del pulso."
    )

    # --- Regla 4: los cambios de acorde contra el resto ---
    cambios = analisis.en_los_cambios()
    resto = analisis.fuera_de_los_cambios()
    if len(cambios) >= 3 and len(resto) >= 3:
        sesgo_cambios = mean([d.desvio_ms for d in cambios])
        sesgo_resto = mean([d.desvio_ms for d in resto])
        diferencia = sesgo_cambios - sesgo_resto

        if abs(diferencia) > 20:
            direccion = "te adelantas mas" if diferencia < 0 else "llegas mas tarde"
            frases.append(
                f"En los compases de cambio de acorde {direccion} que en el "
                f"resto ({sesgo_cambios:+.0f} ms contra {sesgo_resto:+.0f} ms). "
                f"Es donde el profe recomienda simplificar a una sola nota."
            )
        else:
            frases.append(
                "Los cambios de acorde no te desestabilizan mas que el resto."
            )

    # --- Regla 5: si el problema se concentra en algún tiempo del compás ---
    por_tiempo = analisis.por_tiempo_del_compas()
    if len(por_tiempo) >= 2:
        promedios = {t: mean(v) for t, v in por_tiempo.items() if len(v) >= 2}
        if len(promedios) >= 2:
            peor = min(promedios, key=lambda t: promedios[t])
            mejor = max(promedios, key=lambda t: promedios[t])
            if promedios[peor] < -30 and promedios[peor] - promedios[mejor] < -25:
                frases.append(
                    f"Donde mas te adelantas es en el tiempo {peor} del compas "
                    f"({promedios[peor]:+.0f} ms)."
                )

    return frases


def linea_de_tiempo(analisis, ancho=40, tolerancia_ms=None):
    """
    Dibuja cada nota y su desvío, para ver el patrón de un vistazo.

    Los números salteados sirven, pero un dibujo muestra cosas que una tabla
    esconde: si te adelantás cada vez más a lo largo de la vuelta, o si te
    desestabilizás solo en cierto tramo.
    """
    if tolerancia_ms is None:
        tolerancia_ms = config.TOLERANCIA_RITMO_MS

    if not analisis.desvios:
        return "Sin notas para dibujar."

    # La escala del dibujo: medio paso de grilla a cada lado.
    maximo_ms = paso_de_grilla(analisis.bpm, analisis.subdivision) * 500.0
    medio = ancho // 2

    lineas = []
    for numero, desvio in enumerate(analisis.desvios, start=1):
        casillas = ["·"] * ancho
        casillas[medio] = "|"

        posicion = int(medio + (desvio.desvio_ms / maximo_ms) * medio)
        posicion = max(0, min(ancho - 1, posicion))
        casillas[posicion] = "o" if desvio.a_tiempo(tolerancia_ms) else "X"

        marca_cambio = "*" if desvio.es_cambio else " "
        lineas.append(
            f"{numero:3} {desvio.evento.como_tab():>7} "
            f"c{desvio.compas:<3} t{desvio.tiempo_del_compas} {marca_cambio} "
            f"[{''.join(casillas)}] {desvio.desvio_ms:+6.0f} ms"
        )

    lineas.append("")
    lineas.append(f"    antes del pulso <- | -> despues.  "
                  f"o = dentro de {tolerancia_ms:.0f} ms, X = fuera")
    lineas.append("    * = compas donde cambia el acorde")

    return "\n".join(lineas)
