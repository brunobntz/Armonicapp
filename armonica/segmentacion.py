"""
segmentacion.py — Convierte ventanas sueltas en notas tocadas.

EL PROBLEMA

El detector de tono trabaja 86 veces por segundo. Si tocás una nota durante
medio segundo, produce 43 mediciones que dicen todas lo mismo. Eso no es una
tablatura: es una planilla.

Este módulo agrupa esas 43 mediciones en UN evento que dice "tocaste el 4
aspirado, empezó en el segundo 1.2 y duró 0.5 segundos". Recién ahí se puede
escribir la tab y medir el ritmo.

Es exactamente lo que hacés cuando convertís un mayor de movimientos en un
saldo: la información está en los movimientos, pero lo que se lee es el saldo.

LOS TRES FILTROS

1. VOLUMEN. Por debajo de config.UMBRAL_VOLUMEN_RMS es silencio y ni se
   analiza. Eso ya pasó en tono.py.

2. HUECOS TOLERADOS. Una nota larga puede tener una ventana suelta donde el
   detector dudó: un golpe de aire, un instante de transición. Si cortáramos
   ahí, una nota se partiría en dos. Toleramos hasta
   config.VENTANAS_SILENCIO_TOLERADAS ventanas seguidas que no coincidan,
   antes de dar la nota por terminada.

3. DURACIÓN MÍNIMA. Al pasar de un agujero a otro, la armónica pasa por
   frecuencias intermedias durante unos milisegundos, y el detector puede
   reportar una nota fantasma. Descartamos todo lo que dure menos de
   config.DURACION_MINIMA_SEG.

Los tres valores están en config.py porque hay que ajustarlos con tu micrófono
y tu forma de tocar. Son los parámetros que más cambian el resultado.
"""

from dataclasses import dataclass, field
from statistics import median

import config
from armonica import mapeo


@dataclass
class Evento:
    """
    Una nota tocada: qué, cuándo y por cuánto tiempo.

    Campos:
        nota           el objeto Nota (agujero, dirección, bend), o None
        inicio_seg     en qué segundo de la grabación empezó
        duracion_seg   cuánto duró
        frecuencia_hz  la frecuencia mediana de todas sus ventanas
        cents          cuán desafinada estuvo, en promedio. Negativo = bajo
        confianza      qué tan clara fue la detección, de 0 a 1
        ventanas       cuántas mediciones se agruparon acá
        en_escala      si pertenece a la escala de referencia (lo llena
                       marcar_escala, porque este módulo no sabe de escalas)

    Usamos la MEDIANA y no el promedio para la frecuencia. El promedio se
    arruina con un solo valor disparatado; la mediana lo ignora. Con 43
    mediciones de las cuales una salió mal, la mediana ni se entera.
    """

    nota: object
    inicio_seg: float
    duracion_seg: float
    frecuencia_hz: float
    cents: float
    confianza: float
    ventanas: int
    en_escala: bool = field(default=False)

    @property
    def fin_seg(self):
        return self.inicio_seg + self.duracion_seg

    def como_tab(self, notacion=None):
        """La tablatura de esta nota, o '?' si no se reconoció."""
        if self.nota is None:
            return "?"
        return self.nota.como_tab(notacion)

    def como_tab_con_nota(self, notacion=None):
        if self.nota is None:
            return "?"
        return self.nota.como_tab_con_nota(notacion)

    def esta_afinada(self, tolerancia_cents=20.0):
        """
        Si la nota estuvo dentro de la tolerancia de afinación.

        Sirve sobre todo para los bends, que son notas continuas y muy fáciles
        de pasar o de quedarse corto. Veinte cents es el punto donde un oído
        entrenado empieza a escuchar que algo no está.
        """
        return abs(self.cents) <= tolerancia_cents


def segmentar(mediciones, tabla_inversa, duracion_minima=None,
              huecos_tolerados=None, tolerancia_cents=None,
              frecuencia_muestreo=None, correccion_inicio=None):
    """
    Agrupa las mediciones de tono en eventos de nota.

    `mediciones` es lo que devuelve tono.detectar_en_senal.
    `tabla_inversa` es lo que devuelve mapeo.construir_tabla_inversa.

    Devuelve una lista de Evento, en orden cronológico.
    """
    if duracion_minima is None:
        duracion_minima = config.DURACION_MINIMA_SEG
    if huecos_tolerados is None:
        huecos_tolerados = config.VENTANAS_SILENCIO_TOLERADAS
    if frecuencia_muestreo is None:
        frecuencia_muestreo = config.FRECUENCIA_MUESTREO
    if correccion_inicio is None:
        correccion_inicio = config.CORRECCION_INICIO_SEG

    # Cuánto tiempo cubre cada ventana. Se usa para calcular la duración.
    salto_seg = config.SALTO_VENTANA / frecuencia_muestreo

    # --- Primero traducimos cada ventana a una nota (o a None) ---
    # Separar esto del agrupamiento hace que las dos partes se entiendan solas.
    notas_por_ventana = []
    for medicion in mediciones:
        if medicion["frecuencia"] is None:
            notas_por_ventana.append((None, 0.0))
            continue
        nota, cents = mapeo.frecuencia_a_nota(
            medicion["frecuencia"],
            tabla_inversa=tabla_inversa,
            tolerancia_cents=tolerancia_cents,
        )
        notas_por_ventana.append((nota, cents))

    # --- Ahora agrupamos ventanas consecutivas con la misma nota ---
    eventos = []
    total = len(mediciones)
    indice = 0

    while indice < total:
        nota_actual = notas_por_ventana[indice][0]

        # Las ventanas sin nota no arrancan nada: son silencio o ruido.
        if nota_actual is None:
            indice += 1
            continue

        # Encontramos hasta dónde llega esta nota, tolerando huecos.
        inicio = indice
        ultima_coincidente = indice
        huecos_seguidos = 0
        siguiente = indice + 1

        while siguiente < total:
            if notas_por_ventana[siguiente][0] == nota_actual:
                ultima_coincidente = siguiente
                huecos_seguidos = 0
            else:
                huecos_seguidos += 1
                if huecos_seguidos > huecos_tolerados:
                    break
            siguiente += 1

        evento = _armar_evento(
            mediciones, notas_por_ventana, nota_actual,
            inicio, ultima_coincidente, salto_seg, correccion_inicio,
        )

        # El filtro de duración mínima: las notas fantasma de transición se van
        # acá. Es el parámetro que más conviene ajustar al calibrar.
        if evento.duracion_seg >= duracion_minima:
            eventos.append(evento)

        # Seguimos DESPUÉS de la última ventana que coincidió, no después del
        # hueco: esas ventanas de hueco todavía pueden ser el arranque de la
        # nota siguiente.
        indice = ultima_coincidente + 1

    return eventos


def _armar_evento(mediciones, notas_por_ventana, nota, inicio, fin, salto_seg,
                  correccion_inicio=0.0):
    """
    Construye un Evento a partir del tramo de ventanas que le corresponde.

    Solo promedia las ventanas que efectivamente coincidieron con la nota. Las
    de los huecos quedaron adentro del tramo pero no aportan sus valores, que
    justamente eran dudosos.
    """
    frecuencias = []
    cents = []
    confianzas = []

    for i in range(inicio, fin + 1):
        if notas_por_ventana[i][0] != nota:
            continue
        frecuencias.append(mediciones[i]["frecuencia"])
        cents.append(notas_por_ventana[i][1])
        confianzas.append(mediciones[i]["confianza"])

    inicio_crudo = mediciones[inicio]["tiempo_seg"]

    # La nota suena desde que arranca la primera ventana hasta que termina la
    # última. Cada ventana "cubre" un salto de tiempo, por eso el salto extra.
    duracion_seg = (mediciones[fin]["tiempo_seg"] - inicio_crudo) + salto_seg

    # La corrección del inicio. La ventana que reconoce la nota arrancó ANTES de
    # que la nota sonara, así que sin corregir todo parece tocado antes de
    # tiempo. Ver config.CORRECCION_INICIO_SEG, donde está la medición.
    #
    # No dejamos que un inicio se vaya a negativo: si la grabación empieza justo
    # con una nota, esa nota empieza en cero y no antes.
    inicio_seg = max(0.0, inicio_crudo + correccion_inicio)

    # Lo que le sumamos al inicio se lo descontamos a la duración, para que el
    # final de la nota siga cayendo donde estaba.
    duracion_seg = max(salto_seg, duracion_seg - (inicio_seg - inicio_crudo))

    return Evento(
        nota=nota,
        inicio_seg=inicio_seg,
        duracion_seg=duracion_seg,
        frecuencia_hz=median(frecuencias),
        cents=median(cents),
        confianza=sum(confianzas) / len(confianzas),
        ventanas=len(frecuencias),
    )


def marcar_escala(eventos, tonalidad, posicion, escala):
    """
    Completa el campo `en_escala` de cada evento.

    Está separado de segmentar() a propósito: la segmentación no tiene por qué
    saber nada de escalas ni de posiciones. Así se puede transcribir sin elegir
    una escala de referencia, y también se puede volver a marcar la misma
    transcripción contra otra escala sin recalcular nada.

    Modifica los eventos y además los devuelve, por comodidad.
    """
    from armonica import posiciones

    for evento in eventos:
        evento.en_escala = posiciones.nota_en_escala(
            evento.nota, tonalidad, posicion, escala
        )
    return eventos


def como_tablatura(eventos, notacion=None, con_notas=False, por_linea=12):
    """
    Escribe los eventos como tablatura legible.

    Con `con_notas=True` agrega el nombre de la nota al lado de cada agujero,
    que es como pediste verlo:  ↓4 D5   ↑5 E5

    `por_linea` corta en varias líneas para que entre en la pantalla.
    """
    if not eventos:
        return ""

    if con_notas:
        piezas = [e.como_tab_con_nota(notacion) for e in eventos]
        separador = "   "
    else:
        piezas = [e.como_tab(notacion) for e in eventos]
        separador = " "

    lineas = []
    for comienzo in range(0, len(piezas), por_linea):
        lineas.append(separador.join(piezas[comienzo:comienzo + por_linea]))

    return "\n".join(lineas)


def resumen_corto(eventos):
    """
    Una línea con lo esencial, para imprimir después de transcribir.

    El resumen completo, con estadísticas y puntos a trabajar, llega en el
    paso 6.
    """
    if not eventos:
        return "No se detecto ninguna nota."

    reconocidas = [e for e in eventos if e.nota is not None]
    duracion_total = eventos[-1].fin_seg - eventos[0].inicio_seg
    duracion_media = sum(e.duracion_seg for e in eventos) / len(eventos)

    return (
        f"{len(eventos)} notas en {duracion_total:.1f} segundos "
        f"(duracion media {duracion_media * 1000:.0f} ms, "
        f"{len(reconocidas)} reconocidas)"
    )


def estimar_afinacion_armonica(eventos, minimo_notas=4):
    """
    Estima a qué afinación está tu armónica, mirando solo las notas naturales.

    Devuelve (cents_de_desvio, cantidad_de_notas_usadas), o (None, 0) si no hay
    suficientes notas naturales para decir algo.

    POR QUÉ IMPORTA

    La app mide la afinación contra La = 440 Hz, que es el estándar de
    orquesta. Pero las armónicas casi nunca se afinan ahí: Hohner las entrega
    afinadas a 442 o 443 Hz, y encima la presión del aire sube o baja el tono.

    Si tu armónica está 20 cents alta, TODAS tus notas van a leerse como
    "20 cents altas", y no es culpa tuya: es el instrumento. Peor todavía, tus
    bends van a parecer más afinados de lo que son, porque el error del
    instrumento tira para arriba y el del bend tira para abajo.

    Este cálculo separa las dos cosas. Usa SOLO las notas sin bend, porque esas
    las da la lengüeta y no dependen de vos. Lo que salga de ahí es la afinación
    de la armónica; lo que se desvíe de ese valor, es tu forma de tocar.

    Usamos la mediana para que una nota mal tocada no arrastre el resultado.
    """
    naturales = [
        evento.cents for evento in eventos
        if evento.nota is not None and evento.nota.bend == 0
    ]

    if len(naturales) < minimo_notas:
        return None, len(naturales)

    return median(naturales), len(naturales)


def afinacion_equivalente_hz(cents):
    """
    Traduce un desvío en cents al La de referencia equivalente.

    Ejemplo: +20 cents equivale a una armónica afinada con La = 445 Hz.
    Es más fácil de entender así, porque es como lo dicen los fabricantes.
    """
    return 440.0 * (2.0 ** (cents / 1200.0))


def cents_relativos(evento, afinacion_armonica):
    """
    Cuán desafinada estuvo una nota RESPECTO DE TU PROPIA ARMONICA.

    Es el número que de verdad habla de cómo tocaste. Si tu armónica está
    +20 cents y tocaste un bend a -28, contra el estándar parece un error de
    28 cents, pero contra tu instrumento son 48: estás bajando el bend casi
    medio semitono de más.
    """
    if afinacion_armonica is None:
        return evento.cents
    return evento.cents - afinacion_armonica
