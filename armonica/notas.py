"""
notas.py — Conversiones entre frecuencia (Hz), número MIDI y nombre de nota.

Este módulo es la traducción entre dos idiomas:
  - El del micrófono, que habla en frecuencias:   440.0 Hz
  - El de la música, que habla en nombres:        "A4"

En el medio usamos el NÚMERO MIDI como idioma común: un entero donde cada unidad
es un semitono. Es más cómodo que las frecuencias porque sumar un semitono es
sumar 1, en vez de multiplicar por 1.0594...

Referencias fijas de todo el sistema:
    MIDI 69 = A4 = 440 Hz     (el La de la orquesta)
    MIDI 60 = C4 = 261.63 Hz  (el Do central del piano)

Este módulo es Python puro: solo usa `math` de la biblioteca estándar. Nada de
numpy, nada de audio. Se puede portar a otro lenguaje casi línea por línea.
"""

import math

from armonica import tablas


def midi_a_frecuencia(midi):
    """
    Convierte un número MIDI a su frecuencia en Hz.

    La fórmula sale de que una octava (12 semitonos) es el DOBLE de frecuencia.
    Entonces cada semitono multiplica la frecuencia por la raíz doceava de 2.

        frecuencia = 440 * 2 ** ((midi - 69) / 12)

    Ejemplo: midi 69 -> 2**0 = 1 -> 440 Hz.
             midi 81 -> 2**1 = 2 -> 880 Hz (una octava más arriba).

    Acepta valores con decimales: midi 69.5 es medio semitono arriba del La.
    Eso sirve para calcular dónde cae un bend a medio hacer.
    """
    exponente = (midi - tablas.MIDI_LA_REFERENCIA) / 12.0
    return tablas.FRECUENCIA_LA_REFERENCIA * (2.0 ** exponente)


def frecuencia_a_midi(frecuencia_hz):
    """
    Convierte una frecuencia en Hz a número MIDI, CON decimales.

    Es la fórmula inversa de la anterior. Usamos logaritmo en base 2 porque
    queremos saber "cuántas veces se duplicó la frecuencia".

        midi = 69 + 12 * log2(frecuencia / 440)

    Devuelve decimales a propósito. Si tocás un poco desafinado, en vez de
    69 vas a obtener 69.23. Ese 0.23 es información valiosa: son 23 cents de
    desafinación, y es justo lo que el medidor de afinación va a mostrar.

    Lanza ValueError si la frecuencia no es positiva, porque el logaritmo de
    cero o de un número negativo no existe.
    """
    if frecuencia_hz <= 0:
        raise ValueError(f"La frecuencia debe ser mayor que cero, recibí {frecuencia_hz}")

    proporcion = frecuencia_hz / tablas.FRECUENCIA_LA_REFERENCIA
    return tablas.MIDI_LA_REFERENCIA + 12.0 * math.log2(proporcion)


def midi_a_nombre(midi, usar_sostenidos=False):
    """
    Convierte un número MIDI a nombre de nota con octava: 60 -> "C4".

    Dos cuentas:
      - La CLASE de nota (qué nota es, sin importar la octava) es el resto de
        dividir por 12. MIDI 60 y 72 dan resto 0: los dos son "C".
      - La OCTAVA es la división entera por 12, menos 1. El "menos 1" es una
        convención histórica para que el Do central (MIDI 60) sea C4.

    Por defecto usamos bemoles (Db, Eb, Bb) porque es como se habla en armónica
    y en blues. Con usar_sostenidos=True obtenés C#, D#, A#.

    Si le pasás un número con decimales lo redondea al semitono más cercano.
    """
    midi_redondeado = int(round(midi))

    clase = midi_redondeado % 12
    octava = midi_redondeado // 12 - 1

    if usar_sostenidos:
        nombre = tablas.NOMBRES_NOTAS_SOSTENIDOS[clase]
    else:
        nombre = tablas.NOMBRES_NOTAS[clase]

    return f"{nombre}{octava}"


def nombre_a_midi(nombre):
    """
    Convierte un nombre de nota a número MIDI: "C4" -> 60.

    Es la operación inversa de midi_a_nombre. La usamos sobre todo en los tests,
    donde es mucho más legible escribir "Bb4" que 70.

    Acepta bemoles y sostenidos: "Db4" y "C#4" dan el mismo resultado (61).
    También acepta octavas negativas como "C-1" (el MIDI 0).
    """
    nombre = nombre.strip()

    # Separamos la parte de la nota de la parte de la octava. Recorremos desde
    # el principio mientras sean letras, '#' o 'b'; lo que queda es la octava.
    corte = 0
    while corte < len(nombre) and (nombre[corte].isalpha() or nombre[corte] in "#b"):
        corte += 1

    parte_nota = nombre[:corte]
    parte_octava = nombre[corte:]

    if not parte_nota or not parte_octava:
        raise ValueError(f"Nombre de nota mal formado: {nombre!r}. Se espera algo como 'C4' o 'Bb3'.")

    # Buscamos la clase de nota en cualquiera de las dos listas de nombres.
    if parte_nota in tablas.NOMBRES_NOTAS:
        clase = tablas.NOMBRES_NOTAS.index(parte_nota)
    elif parte_nota in tablas.NOMBRES_NOTAS_SOSTENIDOS:
        clase = tablas.NOMBRES_NOTAS_SOSTENIDOS.index(parte_nota)
    else:
        raise ValueError(f"No reconozco la nota {parte_nota!r} en {nombre!r}")

    try:
        octava = int(parte_octava)
    except ValueError:
        raise ValueError(f"La octava {parte_octava!r} de {nombre!r} no es un número entero")

    # Deshacemos la convención del "menos 1" de midi_a_nombre.
    return (octava + 1) * 12 + clase


def desviacion_cents(frecuencia_hz, midi_objetivo):
    """
    Cuántos cents separan una frecuencia de una nota, con signo.

    Un CENT es la centésima parte de un semitono. Es la unidad estándar para
    hablar de afinación porque es proporcional: 10 cents suenan igual de
    desafinados en una nota grave que en una aguda, aunque en Hz la diferencia
    sea muy distinta.

        cents = 1200 * log2(frecuencia_tocada / frecuencia_de_la_nota)

    El signo importa y es el que espera cualquier afinador:
        negativo = estás por DEBAJO de la nota (bemol, te falta subir)
        positivo = estás por ENCIMA de la nota (sostenido, te pasaste)
        cero     = afinación perfecta

    Referencias para el oído: menos de 5 cents es imperceptible. 10 cents se nota
    si prestás atención. 20 cents ya suena desafinado. 50 cents es medio semitono,
    o sea el punto exacto entre dos notas.
    """
    if frecuencia_hz <= 0:
        raise ValueError(f"La frecuencia debe ser mayor que cero, recibí {frecuencia_hz}")

    frecuencia_objetivo = midi_a_frecuencia(midi_objetivo)
    return 1200.0 * math.log2(frecuencia_hz / frecuencia_objetivo)


def midi_mas_cercano(frecuencia_hz):
    """
    Dada una frecuencia, devuelve (nota_midi_entera, desviacion_en_cents).

    Es la función que más se va a usar en el resto de la app: agarra lo que
    salió del detector de tono y responde "esto es la nota X, y estás a Y cents".

    Ejemplo: 452 Hz -> (69, 46.6) = "es un La, pero estás 46 cents alto".

    Ojo con el caso de los bends: si estás a más de 50 cents de una nota, ya
    estás más cerca de la siguiente. Quien llama a esta función decide si esa
    desviación es aceptable, comparándola con TOLERANCIA_CENTS de config.py.
    """
    midi_exacto = frecuencia_a_midi(frecuencia_hz)
    midi_entero = int(round(midi_exacto))
    cents = desviacion_cents(frecuencia_hz, midi_entero)
    return midi_entero, cents


def clase_de_nota(midi):
    """
    Devuelve la clase de nota (0 a 11) ignorando la octava. C=0, Db=1, ... B=11.

    Sirve para preguntas del tipo "¿esta nota pertenece a la escala?", donde la
    octava no importa: un Do es un Do en cualquier registro.
    """
    return int(round(midi)) % 12


def nombre_de_clase(clase, usar_sostenidos=False):
    """
    Convierte una clase de nota (0 a 11) en su nombre sin octava: 10 -> "Bb".

    Se usa para mostrar tonalidades ("estás tocando en G") y escalas, donde
    hablamos de la nota en abstracto y no de una octava concreta.
    """
    clase = int(clase) % 12
    if usar_sostenidos:
        return tablas.NOMBRES_NOTAS_SOSTENIDOS[clase]
    return tablas.NOMBRES_NOTAS[clase]
