"""
afinador.py — Practicar la afinación de un bend, con el medidor a la vista.

POR QUE EXISTE ESTE MODO

El análisis de las grabaciones de Bruno encontró una sola cosa concreta y
repetida: el ↓3'' cae 32 a 41 cents por debajo de la nota, y el ↓4' se queda
25 cents corto, siempre igual.

La receta para eso es "diez repeticiones lentas mirando el medidor". Pero con
lo que había, eso significaba grabar, cortar, analizar y leer un informe: para
cuando veías el resultado ya no te acordabas de qué habías hecho con la boca.

Este modo cierra el círculo: tocás, ves el número al instante, corregís.

QUE HACE DISTINTO AL MODO EN VIVO

El modo en vivo transcribe todo lo que toques. Este se concentra en UNA nota:
la elegís, y el módulo cuenta cada intento, te muestra si mejorás, y al final
te dice si el error es un hábito (siempre el mismo desvío) o falta de control
(desvío distinto cada vez). Son dos problemas diferentes y se arreglan de
maneras diferentes.

Sin objetivo elegido funciona como afinador común: te dice qué nota estás
tocando y cuán afinada está. Sirve para revisar si una lengüeta de la armónica
se desafinó.
"""

from dataclasses import dataclass, field
from statistics import mean, pstdev

import config


# Cuánto tiene que durar una nota para contarla como intento.
# Más corto que esto suele ser una transición, no un intento de verdad.
DURACION_MINIMA_INTENTO_SEG = 0.25


@dataclass
class Intento:
    """Una vez que tocaste la nota objetivo."""

    cents: float
    duracion_seg: float
    instante_seg: float

    def a_tiempo(self, tolerancia=10.0):
        return abs(self.cents) <= tolerancia


@dataclass
class PracticaDeBend:
    """
    Lleva la cuenta de tus intentos sobre una nota.

    `objetivo` es la Nota que querés practicar, o None para usarlo como
    afinador libre.

    `afinacion_armonica` son los cents que tu armónica está corrida respecto de
    La = 440. Si lo pasás, todo se mide CONTRA TU INSTRUMENTO y no contra el
    estándar, que es lo único que tiene sentido: tu armónica está a 444 Hz y no
    es culpa tuya.
    """

    objetivo: object = None
    afinacion_armonica: float = 0.0
    tolerancia_cents: float = 10.0
    intentos: list = field(default_factory=list)

    def registrar(self, evento):
        """
        Guarda un evento como intento, si corresponde.

        Devuelve True si lo contó. Descarta las notas que no son la objetivo y
        las demasiado cortas para ser un intento real.
        """
        if evento.nota is None:
            return False

        if self.objetivo is not None:
            mismo = (evento.nota.agujero == self.objetivo.agujero
                     and evento.nota.direccion == self.objetivo.direccion
                     and evento.nota.bend == self.objetivo.bend)
            if not mismo:
                return False

        if evento.duracion_seg < DURACION_MINIMA_INTENTO_SEG:
            return False

        self.intentos.append(Intento(
            cents=evento.cents - self.afinacion_armonica,
            duracion_seg=evento.duracion_seg,
            instante_seg=evento.inicio_seg,
        ))
        return True

    # --- Las estadísticas ---

    def cantidad(self):
        return len(self.intentos)

    def promedio(self):
        return mean(i.cents for i in self.intentos) if self.intentos else 0.0

    def dispersion(self):
        if len(self.intentos) < 2:
            return 0.0
        return pstdev(i.cents for i in self.intentos)

    def aciertos(self):
        return sum(1 for i in self.intentos if i.a_tiempo(self.tolerancia_cents))

    def porcentaje_de_aciertos(self):
        if not self.intentos:
            return 0.0
        return 100.0 * self.aciertos() / len(self.intentos)

    def mejor(self):
        if not self.intentos:
            return None
        return min(self.intentos, key=lambda i: abs(i.cents))

    def ultimos(self, cuantos=10):
        return self.intentos[-cuantos:]

    def esta_mejorando(self, ventana=5):
        """
        Compara los últimos intentos contra los primeros.

        Devuelve la diferencia de error absoluto promedio. Negativo significa
        que estás mejorando: el error se achicó.

        Devuelve None si no hay suficientes intentos para comparar.
        """
        if len(self.intentos) < ventana * 2:
            return None

        primeros = mean(abs(i.cents) for i in self.intentos[:ventana])
        ultimos = mean(abs(i.cents) for i in self.intentos[-ventana:])
        return ultimos - primeros

    def diagnostico(self):
        """
        Qué tipo de problema tenés con esta nota, en palabras.

        La distinción que importa: un error consistente es un hábito y se
        recalibra; uno errático es falta de control y lleva mucho más tiempo.
        """
        if not self.intentos:
            return "Todavia no hay intentos."

        if len(self.intentos) < 3:
            return f"{len(self.intentos)} intento(s). Hacen falta unos cuantos mas."

        promedio = self.promedio()
        dispersion = self.dispersion()

        if abs(promedio) <= self.tolerancia_cents and dispersion < 15:
            return "Muy bien: caes en la nota y caes siempre en el mismo lugar."

        if dispersion < 15:
            direccion = "por debajo" if promedio < 0 else "por encima"
            return (
                f"Es un HABITO, no falta de control: caes {abs(promedio):.0f} "
                f"cents {direccion} pero siempre en el mismo lugar "
                f"(varias solo {dispersion:.0f} cents). Se recalibra rapido: "
                f"apunta un poco mas {'arriba' if promedio < 0 else 'abajo'} "
                f"y fijate el medidor."
            )

        return (
            f"Es CONTROL, no calibracion: cada intento cae en un lugar distinto "
            f"(varias {dispersion:.0f} cents). Llega despacio y quedate, en vez "
            f"de buscar la nota de golpe. Sostene cuatro tiempos."
        )


def barra_grande(cents, ancho=41, tolerancia=10.0):
    """
    El medidor de afinación, más ancho que el del modo en vivo.

    Acá es lo único que importa en pantalla, así que ocupa todo el espacio.
    Cada casilla vale unos 2.5 cents, que es más fino de lo que cualquier oído
    distingue.
    """
    medio = ancho // 2
    posicion = int(medio + (cents / 50.0) * medio)
    posicion = max(0, min(ancho - 1, posicion))

    casillas = ["-"] * ancho

    # Marcamos la zona aceptable, para tener una referencia visual de a dónde
    # hay que llegar y no solo un punto.
    ancho_zona = max(1, int((tolerancia / 50.0) * medio))
    for indice in range(medio - ancho_zona, medio + ancho_zona + 1):
        if 0 <= indice < ancho:
            casillas[indice] = "="

    casillas[medio] = "|"
    casillas[posicion] = "O"

    return "[" + "".join(casillas) + "]"


def historial_en_texto(practica, cuantos=10):
    """
    Los últimos intentos, uno por línea, para ver el patrón.

    Ver diez números seguidos muestra cosas que un promedio esconde: si venís
    mejorando, si te desestabilizaste, si el primero siempre sale mal.
    """
    ultimos = practica.ultimos(cuantos)
    if not ultimos:
        return "  (todavia no tocaste la nota objetivo)"

    lineas = []
    primero = len(practica.intentos) - len(ultimos) + 1

    for numero, intento in enumerate(ultimos, start=primero):
        marca = "ok" if intento.a_tiempo(practica.tolerancia_cents) else "  "
        lineas.append(
            f"  {numero:3}. {intento.cents:+6.0f} cents  "
            f"{barra_grande(intento.cents, ancho=31, tolerancia=practica.tolerancia_cents)}  {marca}"
        )

    return "\n".join(lineas)


def resumen_en_texto(practica):
    """El informe que se muestra al terminar la práctica."""
    lineas = []
    lineas.append("=" * 72)

    if practica.objetivo is not None:
        lineas.append(f"  PRACTICA DEL {practica.objetivo.como_tab()} "
                      f"({practica.objetivo.nombre})")
    else:
        lineas.append("  AFINADOR")
    lineas.append("=" * 72)

    if not practica.intentos:
        lineas.append("")
        lineas.append("  No se registro ningun intento.")
        lineas.append(f"  Una nota tiene que durar al menos "
                      f"{DURACION_MINIMA_INTENTO_SEG:.2f} s para contar.")
        return "\n".join(lineas)

    lineas.append("")
    lineas.append(f"  Intentos:    {practica.cantidad()}")
    lineas.append(f"  Promedio:    {practica.promedio():+.0f} cents")
    lineas.append(f"  Dispersion:  {practica.dispersion():.0f} cents")
    lineas.append(f"  Dentro de {practica.tolerancia_cents:.0f} cents: "
                  f"{practica.aciertos()} de {practica.cantidad()} "
                  f"({practica.porcentaje_de_aciertos():.0f}%)")

    mejor = practica.mejor()
    if mejor is not None:
        lineas.append(f"  El mejor:    {mejor.cents:+.0f} cents")

    progreso = practica.esta_mejorando()
    if progreso is not None:
        if progreso < -5:
            lineas.append(f"  Mejoraste {abs(progreso):.0f} cents entre los "
                          f"primeros intentos y los ultimos.")
        elif progreso > 5:
            lineas.append(f"  Empeoraste {progreso:.0f} cents. Puede ser "
                          f"cansancio: pará y volvé en un rato.")
        else:
            lineas.append("  Te mantuviste parejo de principio a fin.")

    lineas.append("")
    lineas.append("ULTIMOS INTENTOS")
    lineas.append("-" * 72)
    lineas.append(historial_en_texto(practica))

    lineas.append("")
    lineas.append("DIAGNOSTICO")
    lineas.append("-" * 72)
    lineas.append(f"  {practica.diagnostico()}")

    return "\n".join(lineas)
