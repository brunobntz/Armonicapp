"""
pantalla.py — La pantalla en vivo, mientras tocás.

QUE SE VE Y POR QUE

Cuatro cosas, en orden de importancia para el que está tocando:

  1. EL MEDIDOR DE AFINACION. Grande, arriba de todo. Es lo único que no
     podés saber de otra forma mientras tocás: tu oído te dice si la nota
     está "más o menos", no que estás 30 cents bajo.

  2. EL DIAGRAMA DE LA ARMONICA. Los diez agujeros, con la escala de
     referencia marcada y el que estás tocando resaltado. Sirve para ubicarte
     sin mirar la armónica.

  3. LA TABLATURA que venís tocando, para ver la frase.

  4. Los contadores de la sesión.

UNA DECISION IMPORTANTE: NADA PARPADEA

La pantalla se redibuja doce veces por segundo, pero lo que muestra cambia
mucho más rápido. Si cada ventana de análisis modificara la pantalla, sería
ilegible: verías el agujero saltando entre valores durante cada transición.

Por eso la pantalla guarda la ÚLTIMA NOTA CONFIRMADA y la sostiene hasta que
haya otra. Preferís leer una nota que ya pasó a no poder leer ninguna.

SOBRE rich

Es la única biblioteca de presentación del proyecto, y está aislada acá. El
resto de la app no la importa. Si algún día hacés una interfaz gráfica, este
es el archivo que se reemplaza.
"""

from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import config
from armonica import mapeo, posiciones, segmentacion


class EstadoPantalla:
    """
    Lo que la pantalla sabe en cada instante.

    Es un objeto aparte del dibujo a propósito: acá vive la lógica de qué
    mostrar, y en las funciones de abajo, cómo mostrarlo. Se puede probar sin
    dibujar nada.
    """

    def __init__(self, tonalidad, posicion=None, escala=None):
        self.tonalidad = tonalidad
        self.posicion = posicion
        self.escala = escala

        self.nota_actual = None
        self.cents_actual = 0.0
        self.en_escala_actual = False
        self.volumen_actual = 0.0

        self.eventos = []
        self.ventanas_analizadas = 0
        self.segundos = 0.0

        # Los agujeros de la escala de referencia, para marcarlos en el
        # diagrama. Se calculan una sola vez al empezar.
        self.midis_de_la_escala = set()
        if posicion and escala:
            self.midis_de_la_escala = {
                nota.midi
                for nota in posiciones.notas_de_escala(tonalidad, posicion, escala)
            } if posiciones.tiene_tabla_explicita(posicion) else set()

            if not self.midis_de_la_escala:
                from armonica import teoria
                self.midis_de_la_escala = {
                    nota.midi
                    for nota in teoria.agujeros_para_escala(
                        tonalidad, posicion, escala
                    ).agujeros
                }

    def actualizar(self, nota, cents, volumen, segundos):
        """
        Registra lo que se detectó en esta ventana.

        Si no se detectó nada, la nota anterior se SOSTIENE. Ver la nota que
        acabás de tocar es más útil que ver un espacio vacío entre notas.
        """
        self.ventanas_analizadas += 1
        self.segundos = segundos
        self.volumen_actual = volumen

        if nota is None:
            return

        self.nota_actual = nota
        self.cents_actual = cents
        self.en_escala_actual = nota.midi % 12 in {
            midi % 12 for midi in self.midis_de_la_escala
        } if self.midis_de_la_escala else False

    def registrar_eventos(self, eventos):
        """Guarda los eventos ya segmentados, para la línea de tablatura."""
        self.eventos = eventos

    def tab_reciente(self, cuantas=None):
        """Las últimas notas tocadas, como texto."""
        if cuantas is None:
            cuantas = config.CANTIDAD_TAB_VISIBLE
        return [evento.como_tab() for evento in self.eventos[-cuantas:]]


# =============================================================================
# Los dibujos
# =============================================================================

def medidor_de_cents(cents, ancho=None, afinada=True):
    """
    La barra de afinación:   bajo [-------|---o---] alto

    Es lo más importante de la pantalla. Va grande y con color: verde si estás
    dentro de 10 cents, amarillo hasta 25, rojo más allá.

    Los umbrales no son arbitrarios. Menos de 10 cents casi nadie lo escucha;
    a partir de 25 suena claramente desafinado.
    """
    if ancho is None:
        ancho = config.ANCHO_MEDIDOR_CENTS

    medio = ancho // 2
    posicion = int(medio + (cents / 50.0) * medio)
    posicion = max(0, min(ancho - 1, posicion))

    if abs(cents) <= 10:
        color = "bold green"
    elif abs(cents) <= 25:
        color = "bold yellow"
    else:
        color = "bold red"

    barra = Text()
    barra.append("bajo ", style="dim")
    barra.append("[", style="dim")
    for indice in range(ancho):
        if indice == posicion:
            barra.append("O", style=color)
        elif indice == medio:
            barra.append("|", style="white")
        else:
            barra.append("-", style="dim")
    barra.append("]", style="dim")
    barra.append(" alto", style="dim")

    if not afinada:
        barra.append("   sin nota", style="dim")
    else:
        barra.append(f"  {cents:+5.0f} cents", style=color)

    return barra


def diagrama(estado):
    """
    Los diez agujeros de la armónica, con la escala marcada.

    Cuatro filas: soplado, aspirado, y las dos de bends. Cada celda se pinta
    según tres estados:
        - el agujero que estás tocando AHORA (fondo azul)
        - un agujero de la escala de referencia (verde)
        - cualquier otro agujero disponible (gris)
    """
    tabla = Table(show_header=True, header_style="dim", box=None, padding=(0, 1))
    # Los anchos estan medidos: "aspirado" son 8 caracteres y la tablatura
    # mas larga es "↑10''" con 6. Si quedan cortos, rich trunca con "..."
    # y la pantalla se vuelve ilegible.
    tabla.add_column("", style="dim", width=10)
    for agujero in range(1, 11):
        tabla.add_column(str(agujero), justify="center", width=8)

    formas = mapeo.todas_las_formas(estado.tonalidad)
    por_agujero = {}
    for lista in formas.values():
        for nota in lista:
            clave = (nota.agujero, nota.direccion, nota.bend)
            por_agujero[clave] = nota

    filas = [
        ("soplado", mapeo.SOPLADO, 0),
        ("aspirado", mapeo.ASPIRADO, 0),
        ("bend '", None, 1),
        ("bend ''", None, 2),
        ("bend '''", None, 3),
    ]

    for etiqueta, direccion, bend in filas:
        celdas = []
        hay_alguna = False

        for agujero in range(1, 11):
            nota = None
            if direccion is not None:
                nota = por_agujero.get((agujero, direccion, bend))
            else:
                # Para las filas de bends probamos las dos direcciones.
                for prueba in (mapeo.ASPIRADO, mapeo.SOPLADO):
                    nota = por_agujero.get((agujero, prueba, bend))
                    if nota is not None:
                        break

            if nota is None:
                celdas.append(Text("·", style="dim"))
                continue

            hay_alguna = True
            celdas.append(_celda(nota, estado))

        # No dibujamos la fila del tercer bend si esa armónica no lo tiene.
        if hay_alguna:
            tabla.add_row(etiqueta, *celdas)

    return tabla


def _celda(nota, estado):
    """El texto y el color de un agujero en el diagrama."""
    texto = nota.como_tab()

    es_la_actual = (
        estado.nota_actual is not None
        and estado.nota_actual.agujero == nota.agujero
        and estado.nota_actual.direccion == nota.direccion
        and estado.nota_actual.bend == nota.bend
    )

    if es_la_actual:
        estilo = config.COLOR_ACTUAL
    elif nota.midi in estado.midis_de_la_escala:
        estilo = config.COLOR_EN_ESCALA
    else:
        estilo = config.COLOR_NEUTRO

    return Text(texto, style=estilo)


def encabezado(estado):
    """La línea de arriba: qué armónica, qué posición, qué escala."""
    if estado.posicion:
        texto = posiciones.descripcion_completa(
            estado.tonalidad, estado.posicion, estado.escala
        )
    else:
        texto = f"Armonica en {estado.tonalidad}"
    return Text(texto, style="bold")


def nota_grande(estado):
    """
    El agujero y la nota que estás tocando, en letra grande.

    Si la nota está fuera de la escala de referencia se pinta distinto, pero
    NO se dice que esté mal: fuera de escala es información, no un reproche.
    La tercera mayor sobre un dominante está afuera y es lo que suena a blues.
    """
    if estado.nota_actual is None:
        return Text("  ---  ", style="dim")

    if not estado.midis_de_la_escala:
        estilo = "bold white"
        aclaracion = ""
    elif estado.en_escala_actual:
        estilo = f"bold {config.COLOR_EN_ESCALA}"
        aclaracion = ""
    else:
        estilo = f"bold {config.COLOR_FUERA_ESCALA}"
        aclaracion = "  (fuera de la escala)"

    linea = Text()
    linea.append(f"  {estado.nota_actual.como_tab()}  ", style=estilo)
    linea.append(f"{estado.nota_actual.nombre}", style=estilo)
    linea.append(aclaracion, style="dim")
    return linea


def linea_de_tab(estado):
    """La tablatura reciente, con la última nota resaltada."""
    tabs = estado.tab_reciente()
    if not tabs:
        return Text("(todavia no tocaste nada)", style="dim")

    linea = Text()
    for tablatura in tabs[:-1]:
        linea.append(tablatura + " ", style="dim white")
    linea.append(tabs[-1], style="bold white")
    return linea


def pie(estado):
    """Los contadores y el recordatorio de cómo salir."""
    minutos, segundos = divmod(int(estado.segundos), 60)
    texto = Text()
    texto.append(f"{len(estado.eventos)} notas   ", style="dim")
    texto.append(f"{minutos}:{segundos:02d}   ", style="dim")
    texto.append(f"volumen {estado.volumen_actual:.3f}   ", style="dim")
    texto.append("Ctrl+C para terminar y guardar", style="dim italic")
    return texto


def armar(estado):
    """Junta todo en el panel que se dibuja en pantalla."""
    hay_nota = estado.nota_actual is not None

    contenido = Group(
        encabezado(estado),
        Text(""),
        Align.center(nota_grande(estado)),
        Align.center(medidor_de_cents(estado.cents_actual, afinada=hay_nota)),
        Text(""),
        diagrama(estado),
        Text(""),
        linea_de_tab(estado),
        Text(""),
        pie(estado),
    )

    return Panel(contenido, title="Armonica", border_style="blue")


# =============================================================================
# Modo de demostración
# =============================================================================
#
#     python -m armonica.pantalla
#
# Dibuja la pantalla con una nota inventada, sin micrófono. Sirve para ajustar
# colores y tamaños sin tener que tocar.

if __name__ == "__main__":
    from rich.console import Console

    from armonica.consola import preparar_consola

    preparar_consola()

    estado = EstadoPantalla("C", 12, "blues_mayor")
    estado.actualizar(mapeo.tab_a_nota("-6'", "C"), -18.0, 0.12, 42.5)
    estado.registrar_eventos([
        segmentacion.Evento(mapeo.tab_a_nota(t, "C"), 0.0, 0.4, 440.0,
                            0.0, 0.99, 30)
        for t in ["-2''", "-2", "-3'''", "-3''", "4", "-4", "-5", "6", "-6'"]
    ])

    Console().print(armar(estado))
