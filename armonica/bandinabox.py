"""
bandinabox.py — Leer una base de Band-in-a-Box (.sgu o .mgu) sin abrir el
programa.

De un archivo de Band-in-a-Box salen las cuatro cosas que la app necesita para
practicar sobre una base sin tipear nada: el TONO, el TEMPO, el COMPÁS y qué
ACORDE suena en cada tiempo. Si el archivo trae melodía (.mgu), también sale
la melodía como notas MIDI con su instante, y de ahí a la tablatura de tu
armónica hay un paso.

El formato es binario y propietario, y PG Music no lo documenta. Lo que hay
acá es un port a Python puro del lector de MuseScore (`bb.cpp`, GPL, de
Werner Schweer), que lo importa desde 2009. Se verificó contra una base real
exportada por Band-in-a-Box 2024: "Georgia On My Mind" a 65 BPM en Fa, con
sus 62 acordes y 917 notas de melodía. El test lo repite con una base
sintética escrita con el mismo formato, así no depende de ese archivo.

CÓMO ESTÁ ARMADO EL ARCHIVO (lo que se entiende, byte a byte)

    versión (1 byte, 0x43 a 0x49)
    título  (1 byte de largo + los caracteres)
    2 bytes que no se usan
    estilo  (1 byte, 1 = Jazz Swing, 2 = Country 12/8, ...): de acá sale el
            compás, porque el archivo no lo dice de otra forma
    tono    (1 byte: 1 = Do mayor ... 17 = La# mayor, 18 = Do menor ...)
    tempo   (2 bytes, little endian)
    marcas de parte por compás (a/b), comprimidas
    tipo de cada acorde, un byte por tiempo, comprimido
    raíz de cada acorde, un byte por tiempo, comprimido, con el bajo mezclado
    coro: compás donde empieza, donde termina, cuántas vueltas
    ... cosas del arreglo que no leemos, entre ellas el nombre del .STY ...
    melodía: eventos MIDI de 12 bytes, donde dicen los últimos 4 bytes del
             archivo (posición y cantidad)

"Comprimido" es siempre lo mismo: un byte con valor es un dato; un byte en
cero seguido de N significa "saltá N posiciones". Así una canción de 32
compases con un acorde por compás ocupa unas decenas de bytes.

Lo que NO hace: no lee el arreglo (qué toca cada instrumento). Eso lo
inventa Band-in-a-Box al reproducir a partir del estilo, y no está en el
archivo. Para escuchar la base hace falta el audio que exporta el programa.
"""

import os
from dataclasses import dataclass, field

from armonica import notas

EXTENSIONES = (".sgu", ".mgu")

# Los estilos incorporados, en el orden en que Band-in-a-Box los numera. De
# cada uno importan dos cosas: cuántos pulsos tiene el compás y si las corcheas
# van con swing, porque eso decide contra qué figura medir el ritmo
# (subdivisión 3 con swing, 2 sin swing: ver README, "analizar el ritmo").
# La lista es la de MuseScore; los estilos que agregó Band-in-a-Box después
# se guardan con un número más alto y se tratan como 4/4 sin swing, avisando.
ESTILOS = [
    # (nombre, pulsos por compás, con swing)
    ("Jazz Swing", 4, True),
    ("Country 12/8", 4, True),
    ("Country 4/4", 4, False),
    ("Bossa Nova", 4, False),
    ("Ethnic", 4, False),
    ("Blues Shuffle", 4, True),
    ("Blues Straight", 4, False),
    ("Waltz", 3, False),
    ("Pop Ballad", 4, False),
    ("Rock Shuffle", 4, True),
    ("Lite Rock", 4, False),
    ("Medium Rock", 4, False),
    ("Heavy Rock", 4, False),
    ("Miami Rock", 4, False),
    ("Milly Pop", 4, False),
    ("Funk", 4, False),
    ("Jazz Waltz", 3, True),
    ("Rhumba", 4, False),
    ("Cha Cha", 4, False),
    ("Bouncy", 4, True),
    ("Irish", 4, False),
    ("Pop Ballad 12/8", 4, True),
    ("Country 12/8 old", 4, True),
    ("Reggae", 4, False),
]

# Las raíces, en el orden en que Band-in-a-Box las numera (1 a 17). Las
# últimas cinco son las enarmónicas con sostenido: el programa distingue Reb
# de Do# para escribir el cifrado, pero para la armónica son la misma nota.
RAICES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B",
          "C#", "D#", "F#", "G#", "A#"]

# El tipo de acorde por su número. Son los que aparecen en cifrados de verdad;
# la tabla completa de Band-in-a-Box tiene más de doscientos (7sus#5b9#11 y
# parecidos), y los que no están acá se muestran como "?N" para que se vean y
# alguien los agregue con su fuente. La nomenclatura es la de MuseScore
# (chords.xml), que es la que se ve en cualquier partitura.
TIPOS = {
    1: "", 2: "Maj", 3: "5b", 4: "+", 5: "6", 6: "Maj7", 7: "Maj9",
    8: "Maj9#11", 9: "Maj13#11", 10: "Maj13", 11: "Maj9(no 3)", 12: "+",
    13: "Maj7#5", 14: "69", 15: "2", 16: "m", 17: "m+", 18: "mMaj7",
    19: "m7", 20: "m9", 21: "m11", 22: "m13", 23: "m6", 24: "m#5",
    25: "m7#5", 26: "m69", 27: "Lyd", 28: "Maj7Lyd", 29: "Maj7b5",
    32: "m7b5", 33: "dim", 34: "m9b5", 40: "5",
    56: "7+", 57: "9+", 58: "13+", 59: "(blues)", 60: "7(Blues)",
    64: "7", 65: "13", 66: "7b13", 67: "7#11", 68: "13#11", 69: "7#11b13",
    70: "9", 72: "9b13", 73: "9#11", 74: "13#11", 75: "9#11b13",
    76: "7b9", 77: "13b9", 78: "7b9b13", 79: "7b9#11", 80: "13b9#11",
    81: "7b9#11b13", 82: "7#9", 83: "13#9", 84: "7#9b13", 85: "9#11",
    86: "13#9#11", 87: "7#9#11b13", 88: "7b5", 89: "13b5", 90: "7b5b13",
    91: "9b5", 92: "9b5b13", 93: "7b5b9", 94: "13b5b9", 95: "7b5b9b13",
    96: "7b5#9", 97: "13b5#9", 98: "7b5#9b13", 99: "7#5", 100: "13#5",
    101: "7#5#11", 102: "13#5#11", 103: "9#5", 104: "9#5#11", 105: "7#5b9",
    106: "13#5b9", 107: "7#5b9#11", 108: "13#5b9#11", 109: "7#5#9",
    110: "13#5#9#11", 111: "7#5#9#11", 112: "13#5#9#11", 113: "7alt",
    128: "7sus", 129: "13sus", 130: "7susb13", 131: "7sus#11",
    134: "9sus", 135: "9susb13", 140: "7susb9", 141: "13susb9",
    177: "4", 184: "sus", 185: "dim7", 186: "sus2", 191: "6add9",
    192: "sus4", 193: "11", 194: "Maj11", 196: "m7add11", 197: "Maj7add13",
    198: "madd9",
    199: "m9Maj7", 200: "5", 201: "m11b5", 205: "aug7", 210: "Maj7#11",
    213: "add2", 214: "add9", 216: "Maj7sus", 220: "m7b9", 221: "m7b13",
    223: "madd2",
}

# Cómo se traduce cada tipo de Band-in-a-Box a los acordes que la app sabe
# calcular (tablas.ACORDES_INTERVALOS). Lo que importa para las notas guía es
# la 3a y la 7a: un 9, un 13 o un 7b9 se tratan como dominante porque tienen
# la 3a mayor y la 7a menor, que es lo que se escucha. Lo que no tiene
# traducción honesta (un sus, un aumentado) queda en None y la app no opina.
_FAMILIAS = {
    "mayor": {1, 2, 5, 14, 15, 27, 191, 213, 214},
    "mayor7": {6, 7, 8, 9, 10, 11, 28, 29, 194, 197, 210, 216},
    "menor": {16, 23, 26, 198, 223},
    "menor7": {19, 20, 21, 22, 196, 199, 220, 221},
    "dominante": {59, 60, 64, 65, 66, 67, 68, 69, 70, 72, 73, 74, 75, 76,
                  77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90,
                  91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103,
                  104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 193},
    "disminuido7": {33, 185},
}
FAMILIA_POR_TIPO = {numero: familia
                    for familia, numeros in _FAMILIAS.items()
                    for numero in numeros}

# Band-in-a-Box cuenta los ticks a 120 por negra, y la melodía empieza
# después de un compás de conteo de cuatro negras.
TICKS_POR_NEGRA = 120
TICKS_DE_CONTEO = 4 * TICKS_POR_NEGRA


@dataclass
class Acorde:
    """Un acorde de la base, en el tiempo en que empieza a sonar."""
    compas: int            # empezando en 1
    tiempo: int            # tiempo del compás, empezando en 1
    raiz: str              # "F", "Bb"
    tipo: str              # "Maj7", "m7", "7", "" para mayor
    bajo: str = ""         # "C#" en un Dm/C#; "" si el bajo es la raíz
    numero_tipo: int = 0   # el byte original, por si el nombre no alcanza

    def nombre(self):
        texto = f"{self.raiz}{self.tipo}"
        if self.bajo:
            texto += f"/{self.bajo}"
        return texto

    def familia(self):
        """El tipo de acorde que la app sabe calcular, o None si no hay."""
        return FAMILIA_POR_TIPO.get(self.numero_tipo)

    def clase_raiz(self):
        return notas.nombre_a_midi(self.raiz + "4") % 12


@dataclass
class NotaDeMelodia:
    """Una nota de la melodía, en segundos según el tempo de la base."""
    inicio_seg: float
    duracion_seg: float
    midi: int
    velocidad: int


@dataclass
class Base:
    titulo: str
    tonalidad: str          # "F", "Bb"
    modo: str               # "mayor" o "menor"
    bpm: int
    pulsos_por_compas: int
    con_swing: bool
    estilo: str
    compases: int
    acordes: list = field(default_factory=list)
    melodia: list = field(default_factory=list)
    coro_desde: int = 1
    coro_hasta: int = 0
    vueltas: int = 1
    avisos: list = field(default_factory=list)

    @property
    def subdivision(self):
        """Contra qué figura medir el ritmo: tresillos con swing, corcheas sin."""
        return 3 if self.con_swing else 2

    def acorde_en(self, compas, tiempo=1):
        """El acorde que suena en ese compás y tiempo (el último que empezó)."""
        actual = None
        for acorde in self.acordes:
            if (acorde.compas, acorde.tiempo) <= (compas, tiempo):
                actual = acorde
            else:
                break
        return actual

    def acorde_en_segundo(self, segundos):
        """El acorde que suena en ese instante, contando desde el compás 1."""
        pulso = 60.0 / self.bpm
        pulsos = int(segundos // pulso)
        compas = pulsos // self.pulsos_por_compas + 1
        tiempo = pulsos % self.pulsos_por_compas + 1
        return self.acorde_en(compas, tiempo)

    def compases_de_cambio(self):
        """Los compases en cuyo tiempo 1 empieza un acorde distinto al anterior."""
        cambios = []
        anterior = None
        for acorde in self.acordes:
            nombre = acorde.nombre()
            if acorde.tiempo == 1 and nombre != anterior and acorde.compas > 1:
                cambios.append(acorde.compas)
            anterior = nombre
        return cambios

    def cifrado(self):
        """El cifrado compás por compás, como se escribe en un atril."""
        filas = []
        for numero in range(1, self.compases + 1):
            en_el_compas = [a for a in self.acordes if a.compas == numero]
            if not en_el_compas:
                filas.append("%")
                continue
            partes = []
            for acorde in en_el_compas:
                if acorde.tiempo > 1 and not partes:
                    partes.append("%")
                partes.append(acorde.nombre())
            filas.append(" ".join(partes))
        return filas


def es_base(ruta):
    return str(ruta).lower().endswith(EXTENSIONES)


def leer(ruta):
    """Lee un .sgu o .mgu y devuelve una Base. Levanta ValueError si no lo es."""
    with open(ruta, "rb") as archivo:
        datos = archivo.read()
    base = interpretar(datos)
    if not base.titulo:
        base.titulo = os.path.splitext(os.path.basename(str(ruta)))[0]
    return base


def interpretar(datos):
    """Lo mismo que `leer`, pero desde los bytes. Es lo que prueban los tests."""
    if len(datos) < 12:
        raise ValueError("El archivo es demasiado corto para ser una base de Band-in-a-Box.")
    lector = _Lector(datos)

    version = lector.byte()
    if not 0x43 <= version <= 0x49:
        raise ValueError(
            f"No parece una base de Band-in-a-Box (version {version:#x}). "
            "Se leen los .sgu y .mgu que exporta el programa."
        )
    titulo = lector.texto()
    lector.saltar(2)
    numero_estilo = lector.byte() - 1
    numero_tono = lector.byte()
    bpm = lector.entero16()

    avisos = []
    if 0 <= numero_estilo < len(ESTILOS):
        estilo, pulsos, con_swing = ESTILOS[numero_estilo]
    else:
        estilo, pulsos, con_swing = f"estilo {numero_estilo + 1}", 4, False
        avisos.append(f"No conozco el estilo {numero_estilo + 1}: asumo 4/4 sin swing.")

    if not 1 <= numero_tono <= 2 * len(RAICES):
        raise ValueError(f"Tono desconocido en el archivo: {numero_tono}.")
    tonalidad = RAICES[(numero_tono - 1) % len(RAICES)]
    modo = "menor" if numero_tono > len(RAICES) else "mayor"
    if bpm <= 0:
        raise ValueError("La base no tiene tempo.")

    # Las marcas de parte (a/b) no las usamos, pero hay que pasar por encima.
    compas = lector.byte()
    while compas < 255:
        valor = lector.byte()
        if valor == 0:
            compas += lector.byte()
        else:
            compas += 1

    tipos = _leer_comprimido(lector)
    raices = _leer_comprimido(lector)
    if [t for t, _ in tipos] != [t for t, _ in raices]:
        raise ValueError("Los acordes están rotos: tipos y raíces no coinciden.")

    acordes = []
    ultimo_tiempo = 0
    for (tiempo_absoluto, numero_tipo), (_, valor_raiz) in zip(tipos, raices):
        raiz = valor_raiz % 18
        bajo = (raiz - 1 + valor_raiz // 18) % 18 + 1
        if raiz == 0 or raiz > len(RAICES):
            raise ValueError(f"Raíz desconocida en el archivo: {valor_raiz}.")
        acordes.append(Acorde(
            compas=tiempo_absoluto // pulsos + 1,
            tiempo=tiempo_absoluto % pulsos + 1,
            raiz=RAICES[raiz - 1],
            tipo=TIPOS.get(numero_tipo, f"?{numero_tipo}"),
            bajo="" if bajo == raiz else RAICES[bajo - 1],
            numero_tipo=numero_tipo,
        ))
        if numero_tipo not in TIPOS:
            avisos.append(f"Acorde de tipo {numero_tipo} desconocido en el compás "
                          f"{acordes[-1].compas}: se muestra como ?{numero_tipo}.")
        ultimo_tiempo = max(ultimo_tiempo, tiempo_absoluto)
    compases = ultimo_tiempo // pulsos + 1 if acordes else 0

    # MuseScore saltea este byte con un "??" y lee después inicio, fin y
    # vueltas. En la base real el byte vale 1 y lo que sigue es 32, 3: o sea
    # que ESTE es el compás de inicio, el siguiente el de fin y el otro las
    # vueltas. Con la lectura de MuseScore saldría "del 32 al 3", que no
    # existe, y la descartaría.
    coro_desde = lector.byte()
    coro_hasta = lector.byte()
    vueltas = lector.byte()
    if not 1 <= coro_desde < coro_hasta <= max(compases, 1):
        coro_desde, coro_hasta, vueltas = 1, compases, 1

    melodia = _leer_melodia(datos, bpm, avisos)

    return Base(
        titulo=titulo, tonalidad=tonalidad, modo=modo, bpm=bpm,
        pulsos_por_compas=pulsos, con_swing=con_swing, estilo=estilo,
        compases=compases, acordes=acordes, melodia=melodia,
        coro_desde=coro_desde, coro_hasta=coro_hasta, vueltas=vueltas,
        avisos=avisos,
    )


def _leer_comprimido(lector, maximo=255 * 4):
    """
    Una lista de (posición, valor) del formato comprimido: un byte con valor
    es un dato en la posición actual; un cero seguido de N salta N posiciones.
    Termina cuando la posición llega al máximo (255 compases de 4).
    """
    resultado = []
    posicion = 0
    while posicion < maximo:
        valor = lector.byte()
        if valor == 0:
            posicion += lector.byte()
        else:
            resultado.append((posicion, valor))
            posicion += 1
    return resultado


def _leer_melodia(datos, bpm, avisos):
    """
    Los eventos MIDI del final del archivo: 12 bytes cada uno, con el tick
    en los primeros 4, el tipo en el 5°, la altura en el 6°, la velocidad en
    el 7°, el canal en el 8° y la duración en los últimos 4.
    """
    inicio = datos[-4] | (datos[-3] << 8)
    cantidad = datos[-2] | (datos[-1] << 8)
    if cantidad == 0 or inicio + 12 > len(datos):
        return []

    segundos_por_tick = 60.0 / bpm / TICKS_POR_NEGRA
    notas_leidas = []
    ultima_duracion = 0
    indice = inicio
    for _ in range(cantidad):
        if indice + 12 > len(datos):
            avisos.append("La melodía está cortada: el archivo termina antes.")
            break
        tipo = datos[indice + 4] & 0xF0
        if tipo == 0:
            break
        if tipo == 0x90:
            tick = int.from_bytes(datos[indice:indice + 4], "little") - TICKS_DE_CONTEO
            duracion = int.from_bytes(datos[indice + 8:indice + 12], "little")
            if duracion == 0:
                duracion = ultima_duracion
            ultima_duracion = duracion
            if tick >= 0 and duracion > 0:
                notas_leidas.append(NotaDeMelodia(
                    inicio_seg=tick * segundos_por_tick,
                    duracion_seg=duracion * segundos_por_tick,
                    midi=datos[indice + 5],
                    velocidad=datos[indice + 6],
                ))
        indice += 12
    return notas_leidas


class _Lector:
    def __init__(self, datos):
        self.datos = datos
        self.indice = 0

    def byte(self):
        if self.indice >= len(self.datos):
            raise ValueError("El archivo termina antes de lo esperado.")
        valor = self.datos[self.indice]
        self.indice += 1
        return valor

    def entero16(self):
        bajo = self.byte()
        return bajo | (self.byte() << 8)

    def texto(self):
        largo = self.byte()
        inicio = self.indice
        self.saltar(largo)
        return self.datos[inicio:inicio + largo].decode("latin-1")

    def saltar(self, cuantos):
        self.indice += cuantos
        if self.indice > len(self.datos):
            raise ValueError("El archivo termina antes de lo esperado.")


# =============================================================================
# Para los tests y para quien quiera fabricar una base: el camino inverso
# =============================================================================

def escribir(base):
    """
    Arma los bytes de una base con el mismo formato que lee `interpretar`.

    Existe para que los tests no dependan de un archivo real que no se sube al
    repo. Escribe solo lo que `interpretar` lee, así que Band-in-a-Box no
    tiene por qué abrir lo que sale de acá.
    """
    salida = bytearray([0x49, len(base.titulo)]) + base.titulo.encode("latin-1")
    salida += b"\x00\x00"
    numero_estilo = next((n for n, (nombre, _, _) in enumerate(ESTILOS)
                          if nombre == base.estilo), 0) + 1
    numero_tono = RAICES.index(base.tonalidad) + 1
    if base.modo == "menor":
        numero_tono += len(RAICES)
    salida += bytes([numero_estilo, numero_tono, base.bpm & 0xFF, base.bpm >> 8])
    salida += bytes([1, 1, 0, 254])  # marca de parte en el compás 1, y saltar al 255: fin

    posiciones = [((a.compas - 1) * base.pulsos_por_compas + a.tiempo - 1, a)
                  for a in base.acordes]
    salida += _escribir_comprimido([(p, a.numero_tipo) for p, a in posiciones])

    def valor_raiz(acorde):
        raiz = RAICES.index(acorde.raiz) + 1
        if not acorde.bajo:
            return raiz
        bajo = RAICES.index(acorde.bajo) + 1
        return raiz + 18 * ((bajo - raiz) % 18)
    salida += _escribir_comprimido([(p, valor_raiz(a)) for p, a in posiciones])
    salida += bytes([base.coro_desde, base.coro_hasta, base.vueltas])

    inicio_melodia = len(salida)
    segundos_por_tick = 60.0 / base.bpm / TICKS_POR_NEGRA
    for nota in base.melodia:
        tick = int(round(nota.inicio_seg / segundos_por_tick)) + TICKS_DE_CONTEO
        duracion = int(round(nota.duracion_seg / segundos_por_tick))
        salida += tick.to_bytes(4, "little") + bytes([0x90, nota.midi, nota.velocidad, 1])
        salida += duracion.to_bytes(4, "little")
    cantidad = len(base.melodia)
    salida += bytes([inicio_melodia & 0xFF, inicio_melodia >> 8, cantidad & 0xFF, cantidad >> 8])
    return bytes(salida)


def _escribir_comprimido(pares, maximo=255 * 4):
    salida = bytearray()
    posicion = 0
    for destino, valor in pares:
        while destino > posicion:
            salto = min(destino - posicion, 255)
            salida += bytes([0, salto])
            posicion += salto
        salida.append(valor)
        posicion += 1
    while posicion < maximo:
        salto = min(maximo - posicion, 255)
        salida += bytes([0, salto])
        posicion += salto
    return salida
