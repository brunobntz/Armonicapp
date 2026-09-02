"""
tono.py — Detector de tono YIN, implementado a mano con numpy.

QUÉ PROBLEMA RESUELVE

El micrófono entrega 44100 números por segundo. Ninguno de esos números dice
"esto es un La". Lo que hay que descubrir es cada cuánto se REPITE la onda,
porque esa repetición es la frecuencia, y la frecuencia es la nota.

Si la onda se repite cada 100 muestras y hay 44100 muestras por segundo,
entonces se repite 441 veces por segundo: son 441 Hz, un La un poco alto.

Todo el algoritmo es buscar ese "cada cuánto". En la jerga, ese retardo se
llama TAU (la letra griega τ) y se mide en muestras.

POR QUÉ YIN Y NO OTRA COSA

Lo obvio sería usar la transformada de Fourier, que descompone el sonido en
frecuencias. El problema es que una armónica no produce una frecuencia sola:
produce la nota y además sus armónicos, que son múltiplos. Un La4 de 440 Hz
trae también 880, 1320, 1760... y a veces el armónico suena MÁS FUERTE que la
nota. Fourier señala el más fuerte, y ahí aparece el error clásico de los
afinadores baratos: te marcan una octava arriba de lo que tocaste.

YIN no mira frecuencias: compara la onda consigo misma desplazada. Busca el
desplazamiento en el que la onda se parece más a sí misma. Como la nota
fundamental es la repetición más larga, YIN la encuentra a ella y no a sus
armónicos. Por eso es el estándar para instrumentos monofónicos.

Publicado en 2002 por Alain de Cheveigné y Hideki Kawahara. Los pasos que siguen
son los del paper, en el mismo orden, con los nombres traducidos.

CUÁNTO CUESTA

El paso 1 tiene un bucle de Python de unas 280 vueltas por ventana. Se podría
hacer más rápido con transformadas de Fourier, pero sería mucho más difícil de
leer, y a 86 ventanas por segundo esto consume alrededor del 10% de un núcleo.
Preferimos que se entienda.
"""

import numpy as np

import config


def detectar_frecuencia(bloque, frecuencia_muestreo=None, umbral=None,
                        frecuencia_minima=None, frecuencia_maxima=None):
    """
    Encuentra la frecuencia de un bloque de audio.

    Devuelve una tupla (frecuencia_en_hz o None, confianza entre 0 y 1).

    Devuelve None cuando el bloque no tiene un tono claro: silencio, ruido, un
    golpe de aire, o dos notas sonando juntas. Es lo correcto: preferimos decir
    "no sé" antes que inventar una nota.

    La CONFIANZA es cuán periódica resultó la señal. Cerca de 1 es una nota
    limpia y sostenida; cerca de 0.5 es dudosa. Sirve para descartar detecciones
    flojas más adelante.
    """
    if frecuencia_muestreo is None:
        frecuencia_muestreo = config.FRECUENCIA_MUESTREO
    if umbral is None:
        umbral = config.UMBRAL_YIN
    if frecuencia_minima is None:
        frecuencia_minima = config.FRECUENCIA_MINIMA_HZ
    if frecuencia_maxima is None:
        frecuencia_maxima = config.FRECUENCIA_MAXIMA_HZ

    bloque = np.asarray(bloque, dtype=np.float64)

    # Convertimos el rango de frecuencias que nos interesa a un rango de taus.
    # Frecuencia alta = repetición corta = tau chico, y al revés. Por eso el
    # mínimo de frecuencia da el máximo de tau.
    #
    # Acotar el rango no es solo velocidad: es lo que más previene los errores
    # de octava. Si sabemos que la armónica no baja de 150 Hz, no tiene sentido
    # dejar que el algoritmo proponga 75 Hz.
    tau_maximo = int(frecuencia_muestreo / frecuencia_minima) + 1

    # Para el extremo agudo buscamos un poco MÁS ARRIBA de lo que aceptamos, y
    # después descartamos lo que se pase. Parece contradictorio, pero evita un
    # error feo.
    #
    # Si un sonido de 4000 Hz entra por el micrófono y solo buscamos hasta 2500,
    # el algoritmo no puede encontrar su período verdadero (11 muestras) porque
    # está fuera del rango. Pero sí encuentra el DOBLE de ese período, 22
    # muestras, porque una onda que se repite cada 11 muestras también se repite
    # cada 22. Y 22 muestras son 2004 Hz: una nota que nunca sonó, reportada con
    # toda confianza.
    #
    # Buscando hasta 4000 Hz lo encontramos donde de verdad está, y recién ahí
    # lo descartamos por estar fuera de rango. Mejor un "no sé" que una nota
    # inventada.
    MARGEN_AGUDO = 1.6
    tau_minimo = max(6, int(frecuencia_muestreo / (frecuencia_maxima * MARGEN_AGUDO)))

    if len(bloque) < tau_maximo * 2:
        # La ventana tiene que contener al menos dos repeticiones de la nota más
        # grave, o no hay con qué comparar.
        return None, 0.0

    # Si el bloque es silencio, las cuentas de abajo dividen por cero.
    # Preguntamos antes.
    if np.max(np.abs(bloque)) < 1e-9:
        return None, 0.0

    # --- Los cuatro pasos de YIN ---
    diferencia = _funcion_diferencia(bloque, tau_maximo)
    normalizada = _diferencia_media_normalizada(diferencia)
    tau = _buscar_primer_minimo(normalizada, umbral, tau_minimo, tau_maximo)

    if tau is None:
        return None, 0.0

    tau_afinado = _afinar_con_parabola(normalizada, tau)

    # De retardo a frecuencia: si la onda se repite cada tau muestras y hay
    # `frecuencia_muestreo` muestras por segundo, se repite esta cantidad de
    # veces por segundo.
    frecuencia = frecuencia_muestreo / tau_afinado

    # Una última verificación: la interpolación puede empujar el resultado un
    # poco fuera del rango pedido.
    if not (frecuencia_minima <= frecuencia <= frecuencia_maxima):
        return None, 0.0

    # Última verificación: ¿hay energía DE VERDAD en esa frecuencia?
    # Ver proporcion_del_fundamental() para el porqué. Es lo que distingue una
    # nota real de dos agujeros sonando juntos.
    if config.ENERGIA_FUNDAMENTAL_MINIMA > 0:
        proporcion = proporcion_del_fundamental(bloque, frecuencia,
                                                frecuencia_muestreo)
        if proporcion < config.ENERGIA_FUNDAMENTAL_MINIMA:
            return None, 0.0

    # La confianza es lo contrario de la "aperiodicidad" que mide YIN.
    # normalizada[tau] cerca de 0 = muy periódica = confianza cerca de 1.
    confianza = float(1.0 - normalizada[tau])
    confianza = max(0.0, min(1.0, confianza))

    return float(frecuencia), confianza


def proporcion_del_fundamental(bloque, frecuencia_hz, frecuencia_muestreo):
    """
    Cuánta de la energía del bloque está realmente en esa frecuencia.

    Devuelve la amplitud de esa frecuencia dividida por el volumen del bloque.
    Cerca de 0 significa que la frecuencia detectada no suena.

    POR QUÉ HACE FALTA ESTO

    YIN mide cada cuánto se repite la onda, y eso NO siempre coincide con una
    nota que estés tocando. El caso concreto que apareció en la primera
    grabación de Bruno: soplar dos agujeros a la vez, el 6 y el 7, da Sol5 y
    Do6 sonando juntos. Esas dos frecuencias están en relación 3 a 4, así que
    la onda combinada se repite a la frecuencia de un Do dos octavas más abajo,
    aunque ese Do no exista en el sonido.

    Se llama FUNDAMENTAL AUSENTE, y es un fenómeno real: el oído humano también
    lo escucha, y es la razón por la que un parlante chico de teléfono puede
    hacerte sentir el bajo de una canción sin poder reproducirlo.

    YIN reporta ese Do grave, y no se equivoca: la onda de verdad se repite ahí.
    Pero para una tablatura es una nota que nunca tocaste.

    La forma de distinguirlos es preguntar si EN esa frecuencia hay energía.
    Comparamos la señal contra un seno y un coseno de esa frecuencia; si la
    señal la contiene, la comparación da un número grande. Es la misma idea de
    la transformada de Fourier, pero para una sola frecuencia, y por eso cuesta
    apenas dos multiplicaciones de vectores.
    """
    bloque = np.asarray(bloque, dtype=np.float64)
    cantidad = len(bloque)
    if cantidad == 0:
        return 0.0

    volumen = np.sqrt(np.mean(bloque ** 2))
    if volumen < 1e-12:
        return 0.0

    tiempo = np.arange(cantidad) / frecuencia_muestreo
    parte_coseno = np.dot(bloque, np.cos(2 * np.pi * frecuencia_hz * tiempo))
    parte_seno = np.dot(bloque, np.sin(2 * np.pi * frecuencia_hz * tiempo))

    # np.hypot(a, b) es la raíz de a^2 + b^2: la amplitud combinada de las dos
    # partes. El 2/cantidad convierte esa suma en la amplitud de la onda.
    amplitud = 2.0 * np.hypot(parte_coseno, parte_seno) / cantidad

    return float(amplitud / volumen)


def _funcion_diferencia(bloque, tau_maximo):
    """
    PASO 1 del paper: la función de diferencia.

    Para cada retardo tau posible, mide cuánto se PARECE la onda a sí misma
    corrida tau muestras. La cuenta es:

        d(tau) = suma de (x[j] - x[j + tau])^2

    O sea: corré la onda tau lugares, restala de la original, elevá cada
    diferencia al cuadrado y sumá todo.

    Si tau coincide con el período de la nota, la onda corrida queda casi igual
    a la original, las restas dan casi cero y d(tau) es chiquito. Si tau no
    coincide, las restas son grandes y d(tau) es grande.

    Entonces: buscar la nota es buscar el tau donde d(tau) es mínimo.

    (Elevamos al cuadrado por lo mismo que en el RMS: para que las diferencias
    negativas no se cancelen con las positivas.)
    """
    # Cuántas muestras podemos comparar. Restamos tau_maximo porque para el
    # retardo más grande necesitamos que quepan las dos copias dentro del bloque.
    ancho = len(bloque) - tau_maximo

    diferencia = np.zeros(tau_maximo)
    for tau in range(tau_maximo):
        recorte = bloque[:ancho] - bloque[tau:tau + ancho]
        # np.dot de un vector consigo mismo es la suma de sus cuadrados,
        # y es más rápido que escribir np.sum(recorte ** 2).
        diferencia[tau] = np.dot(recorte, recorte)

    return diferencia


def _diferencia_media_normalizada(diferencia):
    """
    PASO 2 del paper: la diferencia media normalizada acumulada (la "CMNDF").

    Es el paso que hace que YIN funcione mejor que la autocorrelación de toda
    la vida, y también el más difícil de intuir.

    EL PROBLEMA QUE RESUELVE. La función del paso 1 tiene un mínimo perfecto en
    tau = 0, porque cualquier onda es idéntica a sí misma sin correrla. Y tiende
    a dar valores cada vez más chicos a medida que tau crece. Si buscáramos el
    mínimo directamente, siempre ganaría un tau que no nos sirve.

    LA SOLUCIÓN. Dividir cada d(tau) por el promedio de todos los d anteriores:

        d'(tau) = d(tau) / [ (1/tau) * suma de d(1) hasta d(tau) ]

    Así deja de importar cuánto vale d(tau) en términos absolutos, y pasa a
    importar cuánto MEJOR es que sus antecesores. Un tau que baja mucho respecto
    del promedio se destaca; uno que baja porque todo bajaba, no.

    El resultado ronda 1 cuando no hay periodicidad, y baja hacia 0 en el
    período verdadero. Eso permite usar un umbral fijo (0.10 a 0.15) que sirve
    para cualquier volumen y cualquier instrumento, que es la gracia del método.
    """
    normalizada = np.ones(len(diferencia))

    # Por definición del paper, d'(0) = 1.
    # np.cumsum va acumulando la suma corrida: [d1, d1+d2, d1+d2+d3, ...]
    acumulado = np.cumsum(diferencia[1:])

    # Los taus van de 1 en adelante.
    taus = np.arange(1, len(diferencia))
    promedios = acumulado / taus

    # Donde el promedio sea cero (señal perfectamente plana) dejamos el 1 que ya
    # está, en vez de dividir por cero.
    seguros = promedios > 1e-12
    normalizada[1:][seguros] = diferencia[1:][seguros] / promedios[seguros]

    return normalizada


def _buscar_primer_minimo(normalizada, umbral, tau_minimo, tau_maximo):
    """
    PASO 3 del paper: el umbral absoluto.

    Buscamos el PRIMER tau cuyo valor esté por debajo del umbral y sea un
    mínimo local. Devuelve None si no hay ninguno.

    ¿Por qué el primero y no el más chico? Porque si una nota se repite cada 100
    muestras, también se repite cada 200 y cada 300. Los tres son mínimos, y a
    veces uno de los grandes es apenas más profundo. Quedarnos con el más chico
    equivale a elegir la nota fundamental y no una octava más abajo. Este único
    detalle evita la mayoría de los errores de octava.

    "Mínimo local" quiere decir que el valor siguiente ya no sigue bajando: es
    el fondo del pozo y no la pendiente de entrada.
    """
    tau = tau_minimo

    while tau < tau_maximo:
        if normalizada[tau] < umbral:
            # Bajamos del umbral. Ahora avanzamos mientras siga bajando, para
            # quedarnos en el fondo del pozo y no en el borde.
            while tau + 1 < tau_maximo and normalizada[tau + 1] < normalizada[tau]:
                tau += 1
            return tau
        tau += 1

    # Ningún tau bajó del umbral: no hay una nota clara. Devolvemos None en vez
    # del mínimo global, que es lo que hace el paper original. Preferimos decir
    # "no sé" antes que arriesgar una nota inventada sobre ruido: la app
    # transcribe lo que tocás, y una nota de más ensucia más que una de menos.
    return None


def _afinar_con_parabola(normalizada, tau):
    """
    PASO 4 del paper: la interpolación parabólica.

    Tau es un número entero de muestras, pero el período real casi nunca cae
    justo en un número entero. Esa diferencia importa mucho más de lo que parece.

    Ejemplo real: a 44100 Hz, tau = 100 da 441 Hz y tau = 101 da 436.6 Hz.
    Son 4.4 Hz de salto, o sea 17 cents. Sin afinar, el medidor de afinación
    tendría un error del tamaño de lo que queremos medir, y sería inútil para
    controlar bends.

    LA IDEA: mirar el punto mínimo y sus dos vecinos. Esos tres puntos definen
    una parábola, y el fondo de la parábola cae entre las muestras. Es el mismo
    razonamiento que estimar dónde estuvo el pico de una curva cuando solo
    tenés mediciones de a una hora.

    La fórmula del vértice de una parábola que pasa por (tau-1, a), (tau, b) y
    (tau+1, c) es:   tau + 0.5 * (a - c) / (a - 2b + c)
    """
    if tau <= 0 or tau >= len(normalizada) - 1:
        # Está en el borde y no tiene dos vecinos. Devolvemos el entero.
        return float(tau)

    anterior = normalizada[tau - 1]
    actual = normalizada[tau]
    siguiente = normalizada[tau + 1]

    denominador = anterior - 2.0 * actual + siguiente

    if abs(denominador) < 1e-12:
        # Los tres puntos están alineados: no hay parábola que ajustar.
        return float(tau)

    ajuste = 0.5 * (anterior - siguiente) / denominador

    # El ajuste tiene que ser menor a media muestra. Si da más, algo raro pasó
    # y es más seguro quedarse con el entero.
    if abs(ajuste) > 1.0:
        return float(tau)

    return float(tau) + float(ajuste)


def detectar_en_senal(muestras, frecuencia_muestreo=None, umbral_volumen=None):
    """
    Corre el detector sobre una señal entera y devuelve una lista de mediciones.

    Cada elemento es un diccionario con:
        tiempo_seg   en qué segundo de la grabación cae esta ventana
        frecuencia   en Hz, o None si no se detectó nada
        confianza    entre 0 y 1
        volumen      el RMS de la ventana

    Es lo que va a consumir la segmentación en el paso 5 para agrupar ventanas
    en notas. También lo usa el modo de demostración de acá abajo.

    Las ventanas por debajo del umbral de volumen ni se analizan: es silencio,
    y correr YIN sobre silencio es gastar tiempo para obtener ruido.
    """
    from armonica import audio      # importado acá para evitar un ciclo

    if frecuencia_muestreo is None:
        frecuencia_muestreo = config.FRECUENCIA_MUESTREO
    if umbral_volumen is None:
        umbral_volumen = config.UMBRAL_VOLUMEN_RMS

    mediciones = []

    for inicio, bloque in audio.cortar_en_bloques(muestras):
        volumen = audio.volumen_rms(bloque)

        if volumen < umbral_volumen:
            frecuencia, confianza = None, 0.0
        else:
            frecuencia, confianza = detectar_frecuencia(bloque, frecuencia_muestreo)

        mediciones.append({
            "tiempo_seg": inicio / frecuencia_muestreo,
            "frecuencia": frecuencia,
            "confianza": confianza,
            "volumen": volumen,
        })

    return mediciones


# =============================================================================
# Modo de demostración
# =============================================================================
#
#     python -m armonica.tono audio_prueba/corrida_12a.wav
#     python -m armonica.tono audio_prueba/corrida_12a.wav C
#
# Muestra qué frecuencia detecta en cada ventana y, si le pasás una tonalidad
# de armónica, a qué agujero corresponde. Es el primer momento en que se ve la
# cadena completa: audio -> frecuencia -> nota -> agujero.

if __name__ == "__main__":
    import sys

    from armonica import audio, mapeo
    from armonica.consola import preparar_consola

    preparar_consola()

    if len(sys.argv) < 2:
        print("Uso: python -m armonica.tono <archivo.wav> [tonalidad]")
        raise SystemExit(1)

    ruta = sys.argv[1]
    tonalidad = sys.argv[2] if len(sys.argv) > 2 else None

    muestras, fs = audio.leer_wav(ruta)
    print(f"\n{ruta}")
    print(f"  {len(muestras) / fs:.2f} segundos, {fs} Hz de muestreo")

    tabla = mapeo.construir_tabla_inversa(tonalidad) if tonalidad else None
    mediciones = detectar_en_senal(muestras, fs)

    detectadas = [m for m in mediciones if m["frecuencia"]]
    print(f"  {len(mediciones)} ventanas, {len(detectadas)} con tono detectado\n")

    encabezado = f"{'tiempo':>8} {'volumen':>8} {'Hz':>9} {'conf':>6}"
    if tabla:
        encabezado += f"  {'nota':>6}  {'agujero':>9}  {'cents':>6}"
    print(encabezado)
    print("-" * len(encabezado))

    for m in mediciones:
        linea = f"{m['tiempo_seg']:8.3f} {m['volumen']:8.4f}"
        if m["frecuencia"] is None:
            linea += f"{'-':>10}{'-':>7}"
        else:
            linea += f" {m['frecuencia']:9.2f} {m['confianza']:6.2f}"
            if tabla:
                nota, cents = mapeo.frecuencia_a_nota(
                    m["frecuencia"], tabla_inversa=tabla
                )
                if nota is None:
                    linea += f"  {'?':>6}  {'fuera':>9}  {cents:6.1f}"
                else:
                    linea += f"  {nota.nombre:>6}  {nota.como_tab():>9}  {cents:6.1f}"
        print(linea)
