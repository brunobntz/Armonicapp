"""
frases.py — Guardar una frase de referencia y practicar contra ella.

COMO FUNCIONA EL MODO

1. Tocás una frase bien una vez, o usás una grabación que te mandó Leandro.
   La app la transcribe y la guarda como REFERENCIA.
2. Después la practicás. La app compara tu intento contra la referencia y te
   dice qué notas erraste, dónde te adelantaste y qué bends te salieron peor.

POR QUE LA REFERENCIA ES UNA GRABACION Y NO UNA TABLATURA ESCRITA

Porque la tablatura NO LLEVA RITMO. "↓4 ↓5 ↑6" no dice si son negras o
corcheas, y tu propio atril lo anota: "la tablatura no transmite el ritmo
preciso". Una grabación sí lo lleva, gratis y sin tener que inventar una
notación nueva.

Y además las frases terminan siendo las de tu profesor, no unas que se me
ocurrieron a mí.

EL PROBLEMA DIFICIL: COMPARAR EL TIEMPO SIN METRONOMO

La referencia tiene su propio tempo y tu intento otro. Si tocaste la misma
frase un 5% más rápido, TODAS las notas caen antes, y sería absurdo reportar
veinte errores de tiempo cuando en realidad tocaste bien pero más ligero.

La solución es separar las dos cosas. Primero buscamos la velocidad y el
desfase globales que mejor explican tu intento:

    tiempo_tuyo ≈ velocidad * tiempo_de_la_referencia + desfase

Eso se resuelve con una recta de mínimos cuadrados, que es exactamente lo
mismo que ajustar una tendencia a una serie de datos. Después restamos esa
recta, y lo que queda son los desvíos LOCALES: dónde te apuraste o te
colgaste dentro de la frase, más allá de que la hayas tocado más rápido o
más lento en general.

Son dos cosas distintas y merecen dos números distintos:
    - la velocidad global, que es una decisión y no un error
    - los desvíos locales, que sí hablan de tu tiempo
"""

import io
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from statistics import mean, median, pstdev

import config


CARPETA_POR_DEFECTO = "frases"


@dataclass
class NotaDeFrase:
    """Una nota dentro de una frase guardada."""

    tab: str
    inicio_seg: float
    duracion_seg: float
    cents: float = 0.0

    def como_diccionario(self):
        return {
            "tab": self.tab,
            "inicio_seg": round(self.inicio_seg, 3),
            "duracion_seg": round(self.duracion_seg, 3),
            "cents": round(self.cents, 1),
        }


@dataclass
class Frase:
    """Una frase de referencia: qué notas, en qué momento, y con qué afinación."""

    nombre: str
    tonalidad: str = "C"
    posicion: int = None
    escala: str = None
    notas: list = field(default_factory=list)
    fecha: str = ""
    comentario: str = ""

    @property
    def cantidad(self):
        return len(self.notas)

    @property
    def duracion_seg(self):
        if not self.notas:
            return 0.0
        return self.notas[-1].inicio_seg + self.notas[-1].duracion_seg - self.notas[0].inicio_seg

    def tablatura(self):
        return [nota.tab for nota in self.notas]

    def como_texto(self, por_linea=12):
        tabs = self.tablatura()
        lineas = []
        for comienzo in range(0, len(tabs), por_linea):
            lineas.append(" ".join(tabs[comienzo:comienzo + por_linea]))
        return "\n".join(lineas)


def desde_eventos(eventos, nombre, tonalidad="C", posicion=None, escala=None,
                  comentario="", notacion=None):
    """
    Convierte una transcripción en una frase de referencia.

    Los tiempos se guardan RELATIVOS al comienzo de la primera nota. Así no
    importa cuánto silencio hubo antes de que empezaras a tocar.
    """
    reconocidas = [e for e in eventos if e.nota is not None]
    if not reconocidas:
        raise ValueError("No hay ninguna nota reconocida para guardar como frase.")

    cero = reconocidas[0].inicio_seg

    return Frase(
        nombre=nombre,
        tonalidad=tonalidad,
        posicion=posicion,
        escala=escala,
        comentario=comentario,
        fecha=datetime.now().isoformat(timespec="seconds"),
        notas=[
            NotaDeFrase(
                tab=evento.como_tab(notacion),
                inicio_seg=evento.inicio_seg - cero,
                duracion_seg=evento.duracion_seg,
                cents=evento.cents,
            )
            for evento in reconocidas
        ],
    )


# =============================================================================
# La comparación
# =============================================================================

@dataclass
class Comparacion:
    """El resultado de comparar un intento contra una frase de referencia."""

    frase: Frase
    velocidad: float = 1.0
    desfase_seg: float = 0.0
    pares: list = field(default_factory=list)      # (nota_ref, nota_intento, desvio_ms)
    faltantes: list = field(default_factory=list)  # notas de la referencia que no tocaste
    sobrantes: list = field(default_factory=list)  # notas que agregaste
    cambiadas: list = field(default_factory=list)  # (esperada, tocada)

    def notas_esperadas(self):
        return self.frase.cantidad

    def aciertos(self):
        return len(self.pares)

    def porcentaje_de_notas(self):
        if not self.frase.cantidad:
            return 0.0
        return 100.0 * len(self.pares) / self.frase.cantidad

    def desvios_ms(self):
        return [desvio for _, _, desvio in self.pares]

    def desvio_medio_ms(self):
        valores = self.desvios_ms()
        return mean(valores) if valores else 0.0

    def dispersion_ms(self):
        valores = self.desvios_ms()
        return pstdev(valores) if len(valores) > 1 else 0.0

    def peor_desvio(self):
        if not self.pares:
            return None
        return max(self.pares, key=lambda par: abs(par[2]))

    def diferencia_de_velocidad(self):
        """
        Cuánto más rápido o más lento tocaste, en porcentaje.

        Positivo = más lento que la referencia. Negativo = más rápido.
        No es un error: es una decisión. Por eso va separado de los desvíos.
        """
        return (self.velocidad - 1.0) * 100.0

    def espaciado_tipico_ms(self):
        """
        Cuánto tiempo pasa entre nota y nota en la frase de referencia.

        Es la vara contra la cual hay que leer los desvíos. Cincuenta
        milisegundos son muchísimo en una frase de corcheas rápidas y son
        nada en una de redondas.
        """
        if len(self.frase.notas) < 2:
            return 0.0
        separaciones = [
            (siguiente.inicio_seg - anterior.inicio_seg) * 1000.0
            for anterior, siguiente in zip(self.frase.notas, self.frase.notas[1:])
        ]
        return median(separaciones)

    def dispersion_relativa(self):
        """
        La dispersión medida en "notas de la frase", no en milisegundos.

        0.10 significa que tus notas caen dentro de un décimo del espacio que
        hay entre nota y nota: muy parecido a la referencia.
        0.50 significa que caen a media nota de distancia: estás tocando otra
        cosa con las mismas notas.

        Devuelve None si la frase tiene una sola nota y no hay espaciado que
        medir.
        """
        espaciado = self.espaciado_tipico_ms()
        if espaciado <= 0:
            return None
        return self.dispersion_ms() / espaciado

    def calidad(self):
        """
        Una palabra para la comparación: "muy parecida", "parecida", "distinta".

        Está basada en la dispersión relativa y no en los milisegundos, porque
        los milisegundos solos no significan nada sin saber qué tan rápida es
        la frase.
        """
        relativa = self.dispersion_relativa()
        if relativa is None:
            return "sin datos"
        if relativa < 0.15:
            return "muy parecida"
        if relativa < 0.35:
            return "parecida"
        if relativa < 0.60:
            return "reconocible pero distinta"
        return "distinta"


def comparar(frase, eventos, notacion=None):
    """
    Compara un intento contra una frase de referencia.

    El alineamiento usa el mismo algoritmo que compara dos textos: encuentra
    los tramos iguales y marca lo que sobra, lo que falta y lo que cambió. Así
    una nota de más en el medio no descoloca todo lo que viene después.
    """
    reconocidas = [e for e in eventos if e.nota is not None]
    if not reconocidas:
        return Comparacion(frase=frase, faltantes=list(frase.notas))

    cero = reconocidas[0].inicio_seg
    tabs_referencia = frase.tablatura()
    tabs_intento = [e.como_tab(notacion) for e in reconocidas]

    comparacion = Comparacion(frase=frase)

    # --- Paso 1: alinear las dos secuencias de notas ---
    emparejados = []
    igualador = SequenceMatcher(None, tabs_referencia, tabs_intento)

    for operacion, ref_desde, ref_hasta, int_desde, int_hasta in igualador.get_opcodes():
        if operacion == "equal":
            for salto in range(ref_hasta - ref_desde):
                emparejados.append((ref_desde + salto, int_desde + salto))
        elif operacion == "delete":
            comparacion.faltantes.extend(frase.notas[ref_desde:ref_hasta])
        elif operacion == "insert":
            comparacion.sobrantes.extend(tabs_intento[int_desde:int_hasta])
        elif operacion == "replace":
            for salto in range(max(ref_hasta - ref_desde, int_hasta - int_desde)):
                esperada = (frase.notas[ref_desde + salto].tab
                            if ref_desde + salto < ref_hasta else None)
                tocada = (tabs_intento[int_desde + salto]
                          if int_desde + salto < int_hasta else None)
                comparacion.cambiadas.append((esperada, tocada))

    if not emparejados:
        return comparacion

    # --- Paso 2: ajustar la velocidad y el desfase globales ---
    tiempos_referencia = [frase.notas[i].inicio_seg for i, _ in emparejados]
    tiempos_intento = [reconocidas[j].inicio_seg - cero for _, j in emparejados]

    comparacion.velocidad, comparacion.desfase_seg = _ajustar_recta(
        tiempos_referencia, tiempos_intento
    )

    # --- Paso 3: los desvíos que quedan después de sacar la velocidad ---
    for (indice_ref, indice_int), tiempo_ref, tiempo_int in zip(
        emparejados, tiempos_referencia, tiempos_intento
    ):
        esperado = comparacion.velocidad * tiempo_ref + comparacion.desfase_seg
        desvio_ms = (tiempo_int - esperado) * 1000.0
        comparacion.pares.append(
            (frase.notas[indice_ref], reconocidas[indice_int], desvio_ms)
        )

    return comparacion


def _ajustar_recta(equis, ye):
    """
    La recta que mejor lleva `equis` a `ye`, sin dejarse arrastrar por outliers.

    Devuelve (pendiente, ordenada). La pendiente es la relación de velocidad y
    la ordenada es el desfase.

    POR QUE NO USAMOS MINIMOS CUADRADOS

    Lo natural sería una regresión común, pero eleva los errores al cuadrado y
    entonces UNA sola nota muy fuera de lugar mueve toda la recta. Comparando
    dos tomas reales de Bruno pasó exactamente eso: en la segunda hizo una
    pausa larga antes de arrancar, esa nota quedó 900 ms corrida, y la recta se
    inclinó para acomodarla. Resultado: todas las demás notas aparecían con un
    desvío que no tenían.

    Usamos el metodo de Theil-Sen: la pendiente es la MEDIANA de las pendientes
    entre todos los pares de puntos. Una nota descolgada aporta unas pocas
    pendientes raras entre miles, y la mediana ni se entera. La ordenada se
    calcula igual, como mediana.

    Es la misma idea que veníamos usando en todo el proyecto: la mediana
    aguanta lo que el promedio no.
    """
    if len(equis) < 2:
        return 1.0, 0.0

    pendientes = []
    for primero in range(len(equis)):
        for segundo in range(primero + 1, len(equis)):
            separacion = equis[segundo] - equis[primero]
            # Dos notas muy juntas dan una pendiente enorme por un error chico.
            # Las salteamos: no aportan información sobre la velocidad global.
            if abs(separacion) < 0.05:
                continue
            pendientes.append((ye[segundo] - ye[primero]) / separacion)

    if not pendientes:
        return 1.0, median(ye) - median(equis)

    pendiente = median(pendientes)

    # Una pendiente absurda significa que las dos interpretaciones no tienen
    # nada que ver. Mejor no corregir nada que corregir mal.
    if not 0.25 <= pendiente <= 4.0:
        pendiente = 1.0

    ordenada = median([y - pendiente * x for x, y in zip(equis, ye)])
    return pendiente, ordenada


# =============================================================================
# El informe
# =============================================================================

def informe(comparacion, tolerancia_ms=None):
    """El resultado de la práctica, en texto."""
    if tolerancia_ms is None:
        tolerancia_ms = config.TOLERANCIA_RITMO_MS

    frase = comparacion.frase
    lineas = []

    lineas.append("=" * 72)
    lineas.append(f"  FRASE: {frase.nombre}")
    lineas.append("=" * 72)

    if not comparacion.pares and not comparacion.cambiadas:
        lineas.append("")
        lineas.append("  No se reconocio ninguna nota de la frase.")
        return "\n".join(lineas)

    # --- Las notas ---
    lineas.append("")
    lineas.append(f"  Notas de la frase:   {comparacion.notas_esperadas()}")
    lineas.append(f"  Las que acertaste:   {comparacion.aciertos()}  "
                  f"({comparacion.porcentaje_de_notas():.0f}%)")

    if comparacion.faltantes:
        tabs = " ".join(nota.tab for nota in comparacion.faltantes[:8])
        lineas.append(f"  Te comiste:          {tabs}")
    if comparacion.sobrantes:
        lineas.append(f"  Agregaste:           {' '.join(comparacion.sobrantes[:8])}")
    if comparacion.cambiadas:
        detalle = ", ".join(
            f"{esperada or '-'} por {tocada or '-'}"
            for esperada, tocada in comparacion.cambiadas[:5]
        )
        lineas.append(f"  Cambiaste:           {detalle}")

    # --- La velocidad, que no es un error ---
    diferencia = comparacion.diferencia_de_velocidad()
    lineas.append("")
    if abs(diferencia) < 3:
        lineas.append(f"  Velocidad: practicamente igual a la referencia.")
    elif diferencia > 0:
        lineas.append(f"  Velocidad: tocaste {diferencia:.0f}% MAS LENTO que la "
                      f"referencia.")
    else:
        lineas.append(f"  Velocidad: tocaste {abs(diferencia):.0f}% MAS RAPIDO "
                      f"que la referencia.")
    lineas.append("  (Eso no es un error: es una decision. Los desvios de abajo")
    lineas.append("  ya tienen la velocidad descontada.)")

    # --- El tiempo dentro de la frase ---
    if comparacion.pares:
        espaciado = comparacion.espaciado_tipico_ms()
        relativa = comparacion.dispersion_relativa()

        lineas.append("")
        lineas.append("  DENTRO DE LA FRASE, una vez sacada la velocidad:")
        lineas.append(f"    Dispersion:  {comparacion.dispersion_ms():.0f} ms")
        if relativa is not None:
            lineas.append(f"    En la frase: {relativa:.2f} de la distancia entre "
                          f"nota y nota")
            lineas.append(f"                 (la frase tiene una nota cada "
                          f"{espaciado:.0f} ms)")
            lineas.append(f"    Veredicto:   {comparacion.calidad()}")
        dentro = sum(1 for d in comparacion.desvios_ms() if abs(d) <= tolerancia_ms)
        lineas.append(f"    A tiempo:    {dentro} de {len(comparacion.pares)} "
                      f"(dentro de {tolerancia_ms:.0f} ms)")

        peor = comparacion.peor_desvio()
        if peor is not None and abs(peor[2]) > tolerancia_ms:
            cuando = "antes" if peor[2] < 0 else "despues"
            lineas.append(f"    Lo peor:     el {peor[0].tab}, "
                          f"{abs(peor[2]):.0f} ms {cuando} de lo que va")

    # --- Nota por nota ---
    lineas.append("")
    lineas.append("NOTA POR NOTA")
    lineas.append("-" * 72)
    lineas.append(f"  {'nota':>8} {'desvio':>9}  {'':<21} {'afinacion':>18}")

    for nota_ref, evento, desvio in comparacion.pares:
        marca = "ok" if abs(desvio) <= tolerancia_ms else "  "
        dibujo = _barrita(desvio, tolerancia_ms)

        diferencia_cents = evento.cents - nota_ref.cents
        if abs(diferencia_cents) < 15:
            afinacion = ""
        else:
            hacia = "mas bajo" if diferencia_cents < 0 else "mas alto"
            afinacion = f"{abs(diferencia_cents):.0f} cents {hacia}"

        lineas.append(f"  {nota_ref.tab:>8} {desvio:+8.0f}ms {dibujo} {marca} "
                      f"{afinacion:>18}")

    return "\n".join(lineas)


def _barrita(desvio_ms, tolerancia_ms, ancho=21):
    """Un dibujito del desvío de una nota, centrado en cero."""
    escala = max(tolerancia_ms * 4, 200.0)
    medio = ancho // 2
    posicion = int(medio + (desvio_ms / escala) * medio)
    posicion = max(0, min(ancho - 1, posicion))

    casillas = ["·"] * ancho
    casillas[medio] = "|"
    casillas[posicion] = "o" if abs(desvio_ms) <= tolerancia_ms else "X"
    return "[" + "".join(casillas) + "]"


# =============================================================================
# Guardar y cargar
# =============================================================================

def _nombre_de_archivo(nombre):
    """Convierte el nombre de una frase en un nombre de archivo seguro."""
    limpio = "".join(
        caracter if caracter.isalnum() or caracter in "-_" else "_"
        for caracter in nombre.strip().lower().replace(" ", "_")
    )
    return (limpio or "frase") + ".json"


def guardar(frase, carpeta=None):
    """Escribe la frase como JSON y devuelve la ruta."""
    if carpeta is None:
        carpeta = CARPETA_POR_DEFECTO

    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, _nombre_de_archivo(frase.nombre))

    datos = {
        "version": 1,
        "nombre": frase.nombre,
        "fecha": frase.fecha,
        "comentario": frase.comentario,
        "tonalidad": frase.tonalidad,
        "posicion": frase.posicion,
        "escala": frase.escala,
        "notas": [nota.como_diccionario() for nota in frase.notas],
    }

    with io.open(ruta, "w", encoding="utf-8", newline="") as archivo:
        archivo.write(json.dumps(datos, indent=2, ensure_ascii=False))

    return ruta


def cargar(ruta):
    """Lee una frase guardada."""
    with io.open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)

    return Frase(
        nombre=datos.get("nombre", os.path.basename(ruta)),
        tonalidad=datos.get("tonalidad", "C"),
        posicion=datos.get("posicion"),
        escala=datos.get("escala"),
        fecha=datos.get("fecha", ""),
        comentario=datos.get("comentario", ""),
        notas=[
            NotaDeFrase(
                tab=nota["tab"],
                inicio_seg=nota["inicio_seg"],
                duracion_seg=nota["duracion_seg"],
                cents=nota.get("cents", 0.0),
            )
            for nota in datos.get("notas", [])
        ],
    )


def listar(carpeta=None):
    """Las frases guardadas, como lista de (nombre, ruta)."""
    if carpeta is None:
        carpeta = CARPETA_POR_DEFECTO

    if not os.path.isdir(carpeta):
        return []

    encontradas = []
    for archivo in sorted(os.listdir(carpeta)):
        if not archivo.endswith(".json"):
            continue
        ruta = os.path.join(carpeta, archivo)
        try:
            encontradas.append((cargar(ruta).nombre, ruta))
        except (ValueError, KeyError):
            continue

    return encontradas


def buscar(nombre, carpeta=None):
    """Encuentra una frase por su nombre. Devuelve None si no está."""
    objetivo = _nombre_de_archivo(nombre)
    for _, ruta in listar(carpeta):
        if os.path.basename(ruta) == objetivo:
            return cargar(ruta)
    return None
