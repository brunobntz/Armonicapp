"""
resumen.py — Las estadísticas de una sesión de práctica.

QUE HACE Y QUE NO

Este módulo CUENTA: cuántas notas, qué agujeros, cuáles de la escala te
salteaste, qué pares de agujeros repetís. Son hechos, sin opinión.

Lo que hay que ARREGLAR está en prioridades.py, que es otro módulo a propósito.
La separación importa: contar es objetivo y siempre se puede hacer; opinar
requiere que el dato sea confiable, y a veces no lo es.

EL DATO MAS INTERESANTE: LOS PARES REPETIDOS

Cuando improvisás, tu mano y tu boca tienen caminos preferidos. Si el 4 aspirado
siempre lo seguís con el 5 aspirado, eso es un automatismo, y los automatismos
son los que hacen que todos tus solos suenen parecidos.

Contar los pares consecutivos más repetidos los pone a la vista. No son un
error: son tu vocabulario. Pero conviene saber cuál es, para poder salirse.
"""

from collections import Counter
from dataclasses import dataclass, field
from statistics import mean, pstdev

from armonica import posiciones, segmentacion


@dataclass
class ResumenSesion:
    """Todo lo contable de una sesión."""

    duracion_seg: float = 0.0
    cantidad_notas: int = 0
    notas_reconocidas: int = 0
    tonalidad: str = ""
    posicion: int = None
    escala: str = ""
    tonalidad_resultante: str = ""

    conteo_por_agujero: list = field(default_factory=list)
    agujeros_de_la_escala_sin_usar: list = field(default_factory=list)
    fuera_de_escala: list = field(default_factory=list)
    porcentaje_fuera_de_escala: float = 0.0
    pares_repetidos: list = field(default_factory=list)

    duracion_media_ms: float = 0.0
    variacion_duracion: float = 0.0
    afinacion_armonica_cents: float = None
    notas_por_minuto: float = 0.0

    def registros_usados(self):
        """Cuántas notas en cada zona de la armónica."""
        zonas = {"grave (1-3)": 0, "medio (4-7)": 0, "agudo (8-10)": 0}
        for tablatura, cuantas, agujero in self.conteo_por_agujero:
            if agujero <= 3:
                zonas["grave (1-3)"] += cuantas
            elif agujero <= 7:
                zonas["medio (4-7)"] += cuantas
            else:
                zonas["agudo (8-10)"] += cuantas
        return zonas


def resumir(eventos, tonalidad="C", posicion=None, escala=None):
    """Cuenta todo lo contable de una lista de eventos."""
    resumen = ResumenSesion(tonalidad=tonalidad, posicion=posicion,
                            escala=escala or "")

    if not eventos:
        return resumen

    reconocidas = [e for e in eventos if e.nota is not None]

    resumen.cantidad_notas = len(eventos)
    resumen.notas_reconocidas = len(reconocidas)
    resumen.duracion_seg = eventos[-1].fin_seg - eventos[0].inicio_seg

    if resumen.duracion_seg > 0:
        resumen.notas_por_minuto = len(eventos) * 60.0 / resumen.duracion_seg

    duraciones = [e.duracion_seg for e in eventos]
    resumen.duracion_media_ms = mean(duraciones) * 1000.0
    if len(duraciones) > 1 and mean(duraciones) > 0:
        resumen.variacion_duracion = pstdev(duraciones) / mean(duraciones)

    afinacion, _ = segmentacion.estimar_afinacion_armonica(eventos)
    resumen.afinacion_armonica_cents = afinacion

    if posicion is not None:
        resumen.tonalidad_resultante = posiciones.tonalidad_resultante(
            tonalidad, posicion
        )

    _contar_agujeros(reconocidas, resumen)
    _contar_pares(reconocidas, resumen)
    _revisar_escala(reconocidas, resumen, tonalidad, posicion, escala)

    return resumen


def _contar_agujeros(reconocidas, resumen):
    """
    Cuántas veces tocaste cada agujero, de más a menos.

    Guardamos también el número de agujero para poder agrupar por registro
    después sin volver a parsear el texto.
    """
    cuenta = Counter()
    agujeros = {}
    for evento in reconocidas:
        tablatura = evento.como_tab()
        cuenta[tablatura] += 1
        agujeros[tablatura] = evento.nota.agujero

    resumen.conteo_por_agujero = [
        (tablatura, cuantas, agujeros[tablatura])
        for tablatura, cuantas in cuenta.most_common()
    ]


def _contar_pares(reconocidas, resumen, cuantos=5):
    """
    Los pares de agujeros consecutivos más repetidos: tu vocabulario.

    Un par es "tocaste A y después B". Si un par aparece muchas veces, es un
    camino que tu boca ya tiene aprendido.
    """
    if len(reconocidas) < 2:
        return

    pares = Counter()
    for anterior, siguiente in zip(reconocidas, reconocidas[1:]):
        pares[(anterior.como_tab(), siguiente.como_tab())] += 1

    resumen.pares_repetidos = [
        (par, cuantas) for par, cuantas in pares.most_common(cuantos)
        if cuantas > 1
    ]


def _revisar_escala(reconocidas, resumen, tonalidad, posicion, escala):
    """
    Qué agujeros de la escala no usaste, y qué tocaste fuera de ella.

    OJO CON "FUERA DE ESCALA". No es un error. La tercera mayor sobre un acorde
    dominante está fuera de la escala de blues, y es justamente lo que suena a
    blues. Lo contamos como dato, no como falta.
    """
    if not (posicion and escala):
        return

    fuera = [e for e in reconocidas if not e.en_escala]
    resumen.fuera_de_escala = [
        (tablatura, cuantas)
        for tablatura, cuantas in Counter(e.como_tab() for e in fuera).most_common()
    ]
    if reconocidas:
        resumen.porcentaje_fuera_de_escala = 100.0 * len(fuera) / len(reconocidas)

    # Los agujeros de la escala que ni tocaste.
    from armonica import mapeo

    try:
        de_la_escala = posiciones.agujeros_de_escala(posicion, escala)
    except ValueError:
        # La posición no tiene tabla explícita; lo calculamos.
        from armonica import teoria
        de_la_escala = (
            teoria.agujeros_para_escala(tonalidad, posicion, escala)
            .tablaturas("guion")
        )

    # Comparamos por NOTA (midi) y no por texto de tablatura.
    #
    # Es importante por las ambigüedades: en una armónica en Do, el ↑3 y el ↓2
    # dan exactamente la misma nota. Si comparáramos textos, el ↑3 aparecería
    # siempre como "no usado" aunque hubieras tocado esa nota toda la sesión,
    # porque la transcripción siempre lo llama ↓2. Sería un reproche falso.
    midis_usados = {evento.nota.midi for evento in reconocidas}

    sin_usar = []
    for tablatura in de_la_escala:
        nota = mapeo.tab_a_nota(tablatura, tonalidad)
        if nota.midi not in midis_usados:
            sin_usar.append(nota)

    # Ordenados de grave a agudo, que es como se lee una armónica. Ordenarlos
    # por el texto daría "↓1, ↓10, ↓2", que no le sirve a nadie.
    sin_usar.sort(key=lambda nota: nota.midi)

    # Si dos tablaturas dan la misma nota, mostramos una sola.
    vistas = set()
    resumen.agujeros_de_la_escala_sin_usar = []
    for nota in sin_usar:
        if nota.midi in vistas:
            continue
        vistas.add(nota.midi)
        resumen.agujeros_de_la_escala_sin_usar.append(nota.como_tab())


# =============================================================================
# Presentación
# =============================================================================

def como_texto(resumen, analisis_ritmico=None):
    """El resumen en texto, listo para mostrar o para guardar en un archivo."""
    lineas = []

    lineas.append("=" * 72)
    lineas.append("  RESUMEN DE LA SESION")
    lineas.append("=" * 72)

    if resumen.cantidad_notas == 0:
        lineas.append("")
        lineas.append("  No se detecto ninguna nota.")
        return "\n".join(lineas)

    if resumen.posicion:
        lineas.append(f"  {posiciones.descripcion_completa(resumen.tonalidad, resumen.posicion, resumen.escala)}")
    else:
        lineas.append(f"  Armonica en {resumen.tonalidad}")

    minutos, segundos = divmod(int(resumen.duracion_seg), 60)
    lineas.append(f"  {minutos} min {segundos} s de musica, "
                  f"{resumen.cantidad_notas} notas "
                  f"({resumen.notas_por_minuto:.0f} por minuto)")

    if resumen.afinacion_armonica_cents is not None:
        equivalente = segmentacion.afinacion_equivalente_hz(
            resumen.afinacion_armonica_cents
        )
        lineas.append(f"  Tu armonica midio {resumen.afinacion_armonica_cents:+.0f} "
                      f"cents (La = {equivalente:.0f} Hz)")

    lineas.append(f"  Duracion media de nota: {resumen.duracion_media_ms:.0f} ms "
                  f"(variando {resumen.variacion_duracion * 100:.0f}%)")

    # --- Agujeros más usados ---
    lineas.append("")
    lineas.append("AGUJEROS MAS USADOS")
    lineas.append("-" * 72)
    total = resumen.notas_reconocidas or 1
    for tablatura, cuantas, _ in resumen.conteo_por_agujero[:12]:
        porcentaje = 100.0 * cuantas / total
        barra = "#" * int(porcentaje / 2)
        lineas.append(f"  {tablatura:>7} {cuantas:4}  {porcentaje:5.1f}%  {barra}")

    if len(resumen.conteo_por_agujero) > 12:
        lineas.append(f"  (y {len(resumen.conteo_por_agujero) - 12} agujeros mas)")

    # --- Registros ---
    lineas.append("")
    lineas.append("REGISTROS")
    lineas.append("-" * 72)
    for zona, cuantas in resumen.registros_usados().items():
        porcentaje = 100.0 * cuantas / total
        lineas.append(f"  {zona:>13}: {cuantas:4} notas  {porcentaje:5.1f}%  "
                      f"{'#' * int(porcentaje / 2)}")

    # --- Los pares repetidos: el vocabulario ---
    if resumen.pares_repetidos:
        lineas.append("")
        lineas.append("TUS PARES MAS REPETIDOS")
        lineas.append("-" * 72)
        lineas.append("  Los caminos que tu boca ya tiene aprendidos. No son un")
        lineas.append("  error: son tu vocabulario. Sirve saber cual es.")
        lineas.append("")
        for (primero, segundo), cuantas in resumen.pares_repetidos:
            lineas.append(f"  {primero:>7} -> {segundo:<7} {cuantas:3} veces")

    # --- La escala de referencia ---
    if resumen.escala:
        lineas.append("")
        lineas.append("CONTRA LA ESCALA DE REFERENCIA")
        lineas.append("-" * 72)

        if resumen.agujeros_de_la_escala_sin_usar:
            lineas.append("  Agujeros de la escala que no usaste:")
            lineas.append("    " + "  ".join(resumen.agujeros_de_la_escala_sin_usar))
        else:
            lineas.append("  Usaste todos los agujeros de la escala.")

        lineas.append("")
        lineas.append(f"  Notas fuera de la escala: "
                      f"{resumen.porcentaje_fuera_de_escala:.0f}%")
        if resumen.fuera_de_escala:
            detalle = ", ".join(f"{tablatura} ({cuantas})"
                                for tablatura, cuantas in resumen.fuera_de_escala[:6])
            lineas.append(f"    {detalle}")
        lineas.append("  (Fuera de escala no es un error: la tercera mayor sobre un")
        lineas.append("  acorde dominante esta afuera y es lo que suena a blues.)")

    # --- Ritmo, solo si es confiable ---
    if analisis_ritmico is not None:
        lineas.append("")
        lineas.append("RITMO")
        lineas.append("-" * 72)
        if analisis_ritmico.la_grilla_explica_algo():
            lineas.append(f"  Base a {analisis_ritmico.bpm:.0f} BPM")
            lineas.append(f"  Dispersion: {analisis_ritmico.dispersion_ms():.0f} ms")
            lineas.append(f"  Promedio:   {analisis_ritmico.sesgo_ms():+.0f} ms")
            lineas.append(f"  A tiempo:   {analisis_ritmico.porcentaje_a_tiempo():.0f}%")
        else:
            ajuste = analisis_ritmico.ajuste_vs_azar()
            texto = f"{ajuste:.2f}" if ajuste is not None else "no calculable"
            lineas.append(f"  No se pudo medir: la grilla no explica lo tocado "
                          f"(ajuste {texto}).")

    return "\n".join(lineas)


def como_tabla_comparativa(resumenes):
    """
    Compara varias sesiones, una fila por sesión.

    Es la base para ver progreso en el tiempo. Por ahora se usa a mano; en V2
    puede leer todos los JSON de la carpeta de sesiones.
    """
    if not resumenes:
        return "Sin sesiones para comparar."

    lineas = [
        f"{'sesion':>20} {'notas':>7} {'min':>6} {'dur ms':>8} "
        f"{'afinacion':>10} {'fuera %':>8}"
    ]
    lineas.append("-" * 64)

    for nombre, resumen in resumenes:
        afinacion = (f"{resumen.afinacion_armonica_cents:+.0f}"
                     if resumen.afinacion_armonica_cents is not None else "-")
        lineas.append(
            f"{nombre:>20} {resumen.cantidad_notas:7} "
            f"{resumen.duracion_seg / 60:6.1f} {resumen.duracion_media_ms:8.0f} "
            f"{afinacion:>10} {resumen.porcentaje_fuera_de_escala:8.0f}"
        )

    return "\n".join(lineas)
