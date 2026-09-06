"""
transcripcion.py — La cadena completa, de un archivo .wav a notas tocadas.

POR QUE EXISTE ESTE MODULO

La cadena del proyecto siempre fue la misma:

    leer audio -> normalizar -> detectar tono -> mapear a agujeros -> agrupar

pero estaba escrita dos veces en main.py, y ahora hacía falta una tercera en
el servidor web para poder importar el audio de una frase. Tres copias de la
misma cadena son tres lugares donde arreglar el mismo error.

QUE AGREGA ADEMAS DE JUNTARLA

Los controles que hay que hacer SIEMPRE que el audio viene de afuera y no del
micrófono de la app:

  - ¿Es transcribible? Si en la grabación hay una banda tocando, el detector
    de tono es monofónico y devuelve basura. Una frase de referencia armada
    con basura queda guardada para siempre y arruina cada práctica futura.

  - ¿Entra en esta armónica? Si el audio es de una armónica más grave, muchas
    notas quedan por debajo del agujero 1 y se pierden sin avisar.

Ninguno de los dos adivina: informan, y el que llama decide.

LO QUE ESTE MODULO NO PUEDE HACER

No puede decirte con seguridad de qué armónica es una grabación. Suena a que
debería poder, y no: una armónica en Do, con bends, alcanza casi todas las
notas del registro medio, así que una frase tocada en La leída como si fuera
en Do cae entera dentro de lo posible. La tablatura sale distinta de la que
tocó Leandro, pero no hay ninguna nota "imposible" que lo delate.

Lo que sí se detecta es cuando el audio se va de RANGO, que es el caso de una
armónica más grave. Para lo otro está `--que-tono`, que compara las cuatro
armónicas entre sí en vez de mirar una sola.
"""

from dataclasses import dataclass, field

import config
from armonica import audio, mapeo, segmentacion, tono


# Debajo de este puntaje de monofonía, las notas detectadas no son confiables.
# Es el mismo umbral que usa el modo --que-tono, por el mismo motivo.
MONOFONIA_MINIMA = 0.55

# Qué proporción de las ventanas con sonido tiene que caer dentro del alcance
# de la armónica declarada. Una de cada cinco afuera ya es mucho: significa que
# se está perdiendo un pedazo entero de lo tocado.
COBERTURA_MINIMA = 0.80


@dataclass
class Transcripcion:
    """Todo lo que salió de analizar un audio."""

    eventos: list = field(default_factory=list)
    mediciones: list = field(default_factory=list)
    muestras: object = None
    frecuencia_muestreo: int = config.FRECUENCIA_MUESTREO

    # Cuántas ventanas dieron una frecuencia, y de esas cuántas cayeron en un
    # agujero de la armónica. Ver `cobertura`.
    ventanas_con_tono: int = 0
    ventanas_en_la_armonica: int = 0

    @property
    def reconocidas(self):
        """Las notas que cayeron en un agujero de la armónica."""
        return [e for e in self.eventos if e.nota is not None]

    @property
    def cobertura(self):
        """
        Qué proporción de lo que sonó entra en la armónica declarada.

        SE MIDE SOBRE LAS VENTANAS Y NO SOBRE LOS EVENTOS

        Parece más natural contar notas, y sería un error: segmentacion.
        segmentar DESCARTA las ventanas que no caen en ningún agujero, no las
        marca. Contado sobre los eventos, este número daría 1.0 siempre, aun
        con un audio entero fuera de rango. Las ventanas son las únicas que
        todavía saben lo que se perdió.
        """
        if self.ventanas_con_tono <= 0:
            return 0.0
        return self.ventanas_en_la_armonica / self.ventanas_con_tono

    @property
    def duracion_seg(self):
        if self.muestras is None:
            return 0.0
        return len(self.muestras) / self.frecuencia_muestreo


def desde_muestras(muestras, frecuencia_muestreo, tonalidad,
                   posicion=None, escala=None):
    """La cadena entera, a partir de muestras ya leídas."""
    mediciones = tono.detectar_en_senal(muestras, frecuencia_muestreo)

    tabla = mapeo.construir_tabla_inversa(tonalidad)
    eventos = segmentacion.segmentar(mediciones, tabla,
                                     frecuencia_muestreo=frecuencia_muestreo)

    if posicion is not None and escala:
        segmentacion.marcar_escala(eventos, tonalidad, posicion, escala)

    con_tono, en_la_armonica = _contar_ventanas(mediciones, tabla)

    return Transcripcion(eventos, mediciones, muestras, frecuencia_muestreo,
                         con_tono, en_la_armonica)


def desde_archivo(ruta, tonalidad, posicion=None, escala=None):
    """
    Lo mismo, pero leyendo un .wav del disco.

    Normaliza antes de analizar: sin eso, una grabación con poco volumen se
    descarta entera como si fuera silencio. Le pasó a la primera grabación de
    este proyecto, que tenía pico 0.03 y devolvió una sola nota en 18
    segundos. Ver config.NORMALIZAR_ARCHIVOS.
    """
    muestras, frecuencia_muestreo = audio.leer_wav(ruta)

    if config.NORMALIZAR_ARCHIVOS:
        muestras = audio.normalizar(muestras)

    return desde_muestras(muestras, frecuencia_muestreo, tonalidad,
                          posicion, escala)


def _contar_ventanas(mediciones, tabla_inversa):
    """
    Cuántas ventanas tuvieron tono, y cuántas de esas entran en la armónica.

    Repite el mapeo que ya hizo `segmentar`, a propósito: es una búsqueda en
    un diccionario por ventana, y a cambio `segmentar` no tiene que cambiar su
    firma para devolver algo que solo le sirve a este módulo.
    """
    con_tono = 0
    en_la_armonica = 0

    for medicion in mediciones:
        if medicion["frecuencia"] is None:
            continue
        con_tono += 1
        nota, _ = mapeo.frecuencia_a_nota(medicion["frecuencia"],
                                          tabla_inversa=tabla_inversa)
        if nota is not None:
            en_la_armonica += 1

    return con_tono, en_la_armonica


def revisar(transcripcion, tonalidad):
    """
    Si este audio sirve para armar una frase de referencia.

    Devuelve (sirve, motivo, avisos):
        sirve   True o False
        motivo  por qué no sirve, en castellano, o "" si sirve
        avisos  cosas raras que igual dejan seguir

    La diferencia entre "motivo" y "aviso" es si el resultado sería INVENTADO
    o solamente incompleto. Un audio polifónico da notas inventadas y no hay
    nada que hacer con eso. Un audio que se sale de rango da notas reales a
    las que les falta un pedazo: se avisa y vos decidís.

    La monofonía se mira PRIMERO, antes que "no se reconoció ninguna nota",
    porque cuando las dos cosas pasan juntas la polifonía es la causa y la
    otra es la consecuencia. Decir "no reconocí nada" cuando el problema es
    que hay una banda tocando manda a buscar el error en el lugar equivocado.
    """
    avisos = []

    calidad = tono.medir_monofonia(transcripcion.muestras,
                                   transcripcion.frecuencia_muestreo)

    # El silencio también da puntaje 0, y decirle "no parece una armónica
    # sola" a un archivo mudo manda a buscar el problema donde no está.
    if calidad["con_sonido"] == 0:
        return False, (
            "En el audio no hay nada por encima del umbral de volumen. "
            f"{calidad['explicacion']} Si grabaste bajito, corré  "
            "python main.py --calibrar  para medir el ruido de tu pieza."
        ), avisos

    if calidad["puntaje"] < MONOFONIA_MINIMA:
        return False, (
            "El audio no parece una armónica sola: puntaje de monofonía "
            f"{calidad['puntaje']:.2f} sobre 1 ({calidad['veredicto']}). El "
            "detector de tono es monofónico, así que las notas que saldrían "
            "de acá serían inventadas. Hace falta la armónica sola, sin la "
            "base sonando atrás."
        ), avisos

    if not transcripcion.reconocidas:
        return False, "No se reconoció ninguna nota en el audio.", avisos

    cobertura = transcripcion.cobertura
    if cobertura < COBERTURA_MINIMA:
        avisos.append(
            f"Solo el {cobertura * 100:.0f}% de lo que suena entra en una "
            f"armónica en {tonalidad}: el resto queda fuera de su alcance y "
            "se pierde. Si la grabación es de otra armónica, corré  "
            "python main.py --wav <archivo> --que-tono  para saber cuál."
        )

    return True, "", avisos
