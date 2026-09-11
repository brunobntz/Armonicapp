"""
prioridades.py — Qué atacar primero, y qué hacer al respecto.

POR QUE EXISTE ESTE MODULO

Los reportes de la app dan muchos números correctos, y eso no alcanza. Bruno
lo dijo con todas las letras: "corri los tests y me da el detalle de todo, pero
no me queda claro donde esta el peor problema o como atacarlo".

Un informe que enumera veinte datos deja el trabajo de priorizar del lado del
que lo lee. Este módulo hace ese trabajo: mira todo lo medido, descarta lo que
no es confiable, y devuelve una lista ORDENADA de cosas para arreglar, cada una
con la evidencia que la sostiene y una acción concreta.

LAS TRES REGLAS DE HONESTIDAD

1. Si un dato no es confiable, no se reporta como hallazgo. Se dice que no se
   pudo medir y por qué. Un diagnóstico inventado es peor que ninguno.

2. Cada hallazgo lleva su NIVEL DE CONFIANZA. Un error que se repite igual en
   dos tomas distintas vale mucho más que uno que apareció una vez.

3. Los errores CONSISTENTES van antes que los erráticos, aunque sean más chicos.
   Un bend que siempre cae 30 cents bajo es un hábito, y los hábitos se
   corrigen recalibrando. Un bend que cae en cualquier lado es falta de control
   y lleva mucho más tiempo. Conviene empezar por lo primero.
"""

from dataclasses import dataclass
from statistics import mean, pstdev

import config
from armonica import posiciones, segmentacion


@dataclass
class Hallazgo:
    """
    Una cosa para trabajar, con su evidencia y su acción.

    Campos:
        titulo      qué pasa, en una línea
        evidencia   los números que lo sostienen
        accion      qué hacer concretamente
        confianza   "alta", "media" o "baja"
        peso        cuánto importa, de 0 a 100. Ordena la lista.
    """

    titulo: str
    evidencia: str
    accion: str
    confianza: str = "media"
    peso: float = 50.0


def analizar(eventos, analisis_ritmico=None, tonalidad=None, posicion=None,
             escala=None):
    """
    Devuelve (hallazgos ordenados, cosas_que_no_se_pudieron_medir).

    Los hallazgos vienen de mayor a menor prioridad.
    """
    hallazgos = []
    sin_medir = []

    _revisar_bends(eventos, hallazgos, sin_medir)
    _revisar_ritmo(analisis_ritmico, hallazgos, sin_medir)
    _revisar_registros(eventos, hallazgos)
    _revisar_duraciones(eventos, hallazgos)
    _revisar_escala(eventos, hallazgos, tonalidad, posicion, escala)

    hallazgos.sort(key=lambda h: -h.peso)
    return hallazgos, sin_medir


# =============================================================================
# Los bends: lo que más se puede medir bien
# =============================================================================

def _revisar_bends(eventos, hallazgos, sin_medir):
    """
    Busca bends que caigan sistemáticamente fuera de la nota.

    Mide contra la afinación de TU armónica, no contra el estándar, porque si
    no estaríamos culpándote de cómo la afinó el fabricante.
    """
    afinacion, cuantas_naturales = segmentacion.estimar_afinacion_armonica(eventos)

    if afinacion is None:
        sin_medir.append(
            f"La afinacion de los bends: hacen falta al menos 4 notas naturales "
            f"para saber como esta afinada tu armonica, y hay {cuantas_naturales}."
        )
        return

    por_bend = {}
    for evento in eventos:
        if evento.nota is None or evento.nota.bend == 0:
            continue
        relativo = segmentacion.cents_relativos(evento, afinacion)
        por_bend.setdefault(evento.como_tab(), []).append(relativo)

    for tablatura, desvios in por_bend.items():
        if len(desvios) < 2:
            continue

        promedio = mean(desvios)
        dispersion = pstdev(desvios) if len(desvios) > 1 else 0.0

        if abs(promedio) < 20:
            continue

        direccion = "te pasas de bend" if promedio < 0 else "te quedas corto"
        cuanto = abs(promedio)

        # Un error consistente es un hábito: se arregla más fácil que uno
        # errático, y por eso va primero.
        if dispersion < 15:
            hallazgos.append(Hallazgo(
                titulo=f"El {tablatura}: {direccion}, siempre lo mismo",
                evidencia=(
                    f"{cuanto:.0f} cents fuera de la nota, en {len(desvios)} "
                    f"apariciones, con una variacion de apenas {dispersion:.0f} "
                    f"cents entre una y otra."
                ),
                accion=(
                    f"Es un habito, no falta de control: siempre parás en el mismo "
                    f"lugar equivocado. Tocá el {tablatura} solo, con el medidor "
                    f"de la app a la vista, hasta que el punto quede en el centro. "
                    f"Diez repeticiones lentas alcanzan para recalibrar el oido."
                ),
                confianza="alta" if len(desvios) >= 3 else "media",
                peso=60 + min(cuanto, 60),
            ))
        else:
            hallazgos.append(Hallazgo(
                titulo=f"El {tablatura}: cae en cualquier lado",
                evidencia=(
                    f"{cuanto:.0f} cents de promedio fuera de la nota, pero "
                    f"variando {dispersion:.0f} cents entre una aparicion y otra "
                    f"({len(desvios)} veces)."
                ),
                accion=(
                    f"Acá el problema es control, no calibracion, y lleva mas "
                    f"tiempo. Sostené el {tablatura} cuatro tiempos mirando el "
                    f"medidor, sin buscar la nota de golpe: llegá y quedate."
                ),
                confianza="alta" if len(desvios) >= 3 else "media",
                peso=50 + min(dispersion, 50),
            ))


# =============================================================================
# El ritmo: solo si la medición es confiable
# =============================================================================

def _revisar_ritmo(analisis, hallazgos, sin_medir):
    """
    Reporta el ritmo SOLO si la grilla explica lo tocado mejor que el azar.

    Este chequeo es la parte más importante de la función. Sin él, la app
    informaría "dispersion 77 ms" sobre notas repartidas al azar, y eso no es
    un diagnóstico: es un número con cara de diagnóstico.
    """
    if analisis is None:
        return

    ajuste = analisis.ajuste_vs_azar()

    if ajuste is None:
        sin_medir.append("El ritmo: hacen falta al menos 4 notas.")
        return

    if not analisis.la_grilla_explica_algo():
        sin_medir.append(
            f"EL RITMO. Las notas caen casi tan repartidas como si fueran al "
            f"azar respecto del pulso (ajuste {ajuste:.2f}, donde 1.00 es azar "
            f"puro). Puede ser que el BPM o el compas no sean los correctos, o "
            f"que el material no sea metrico: una frase de solo con fraseo "
            f"expresivo no cae sobre la grilla ni tiene por que. "
            f"Para medir ritmo hace falta material metrico: una escala en "
            f"negras o corcheas parejas sobre la base."
        )
        return

    dispersion = analisis.dispersion_ms()
    sesgo = analisis.sesgo_ms()

    if dispersion > 50:
        hallazgos.append(Hallazgo(
            titulo="El tiempo esta inestable",
            evidencia=(
                f"Dispersion de {dispersion:.0f} ms: cada nota cae en un lugar "
                f"distinto respecto del pulso. El ajuste contra el azar es "
                f"{ajuste:.2f}."
            ),
            accion=(
                "Bajá el tempo hasta que la dispersion baje de 30 ms, y recien "
                "ahi subilo. Adelantarse es el sintoma; acelerar lo alimenta."
            ),
            confianza="alta",
            peso=95,
        ))
    elif abs(sesgo) > 30:
        hacia = "adelantás" if sesgo < 0 else "atrasás"
        hallazgos.append(Hallazgo(
            titulo=f"Te {hacia} de forma pareja",
            evidencia=(
                f"{abs(sesgo):.0f} ms {'antes' if sesgo < 0 else 'despues'} del "
                f"pulso en promedio, pero con poca variacion "
                f"(dispersion {dispersion:.0f} ms)."
            ),
            accion=(
                "Es el problema facil de los dos: tu tiempo es solido y solo "
                "esta corrido. Alcanza con escuchar la base un compas entero "
                "antes de entrar."
            ),
            confianza="alta",
            peso=70,
        ))

    # Los cambios de acorde, que es donde el profe dice que se le complica.
    cambios = analisis.en_los_cambios()
    resto = analisis.fuera_de_los_cambios()
    if len(cambios) >= 3 and len(resto) >= 3:
        diferencia = mean([d.desvio_ms for d in cambios]) - \
                     mean([d.desvio_ms for d in resto])
        if abs(diferencia) > 25:
            hallazgos.append(Hallazgo(
                titulo="Los cambios de acorde te desacomodan",
                evidencia=(
                    f"En los compases donde cambia el acorde caes {abs(diferencia):.0f} "
                    f"ms mas {'temprano' if diferencia < 0 else 'tarde'} que en el resto."
                ),
                accion=(
                    "Es lo que el profe te viene diciendo desde marzo. Tocá la "
                    "vuelta entera con UNA sola nota por acorde, redonda, sin "
                    "adornos. Cuando eso salga parejo, agregá la segunda nota."
                ),
                confianza="media",
                peso=85,
            ))


# =============================================================================
# Cobertura: qué parte de la armónica usás
# =============================================================================

def _revisar_registros(eventos, hallazgos):
    """
    Mira si usás los tres registros o te quedás en una zona.

    Es un hallazgo suave: quedarse en el registro medio puede ser una decisión
    musical. Por eso tiene poco peso y confianza media.
    """
    reconocidas = [e for e in eventos if e.nota is not None]
    if len(reconocidas) < 12:
        return

    zonas = {"grave (1-3)": 0, "medio (4-7)": 0, "agudo (8-10)": 0}
    for evento in reconocidas:
        if evento.nota.agujero <= 3:
            zonas["grave (1-3)"] += 1
        elif evento.nota.agujero <= 7:
            zonas["medio (4-7)"] += 1
        else:
            zonas["agudo (8-10)"] += 1

    total = len(reconocidas)
    vacias = [nombre for nombre, cuantas in zonas.items() if cuantas == 0]

    if vacias:
        hallazgos.append(Hallazgo(
            titulo=f"No usaste el registro {' ni el '.join(vacias)}",
            evidencia=" / ".join(
                f"{nombre}: {cuantas} notas ({100 * cuantas / total:.0f}%)"
                for nombre, cuantas in zonas.items()
            ),
            accion=(
                "Si fue una decision musical, esta bien. Si es que no te sale, "
                "probá el modo teoria para ver que agujeros de la escala tenes "
                "ahi."
            ),
            confianza="baja",
            peso=25,
        ))


def _revisar_duraciones(eventos, hallazgos):
    """
    Si todas las notas duran lo mismo, el fraseo suena plano.

    Un solo con vida alterna notas largas y cortas. Uno donde todas duran igual
    suena a escala, aunque las notas sean las correctas.
    """
    if len(eventos) < 12:
        return

    duraciones = [e.duracion_seg for e in eventos]
    promedio = mean(duraciones)
    if promedio <= 0:
        return

    variacion = pstdev(duraciones) / promedio

    if variacion < 0.35:
        hallazgos.append(Hallazgo(
            titulo="Todas las notas duran mas o menos lo mismo",
            evidencia=(
                f"Duracion media {promedio * 1000:.0f} ms, variando solo un "
                f"{variacion * 100:.0f}%."
            ),
            accion=(
                "El interes puede venir del tiempo y no de las notas. Probá el "
                "ejercicio del trino de tu atril: una vuelta entera con dos "
                "notas, cambiando solo el ritmo."
            ),
            confianza="media",
            peso=40,
        ))


def _revisar_escala(eventos, hallazgos, tonalidad, posicion, escala):
    """
    Cuántas notas cayeron fuera de la escala de referencia.

    Ojo: fuera de escala NO significa mal. La tercera mayor sobre un acorde
    dominante esta fuera de la escala de blues y es justamente lo que suena a
    blues. Por eso el umbral es alto y el peso bajo.
    """
    if not (tonalidad and posicion and escala):
        return

    reconocidas = [e for e in eventos if e.nota is not None]
    if len(reconocidas) < 12:
        return

    fuera = [e for e in reconocidas if not e.en_escala]
    porcentaje = 100.0 * len(fuera) / len(reconocidas)

    if porcentaje > 35:
        agujeros = {}
        for evento in fuera:
            agujeros[evento.como_tab()] = agujeros.get(evento.como_tab(), 0) + 1
        top = sorted(agujeros.items(), key=lambda x: -x[1])[:3]

        hallazgos.append(Hallazgo(
            titulo=f"{porcentaje:.0f}% de las notas quedan fuera de la escala elegida",
            evidencia="Las mas repetidas: " + ", ".join(
                f"{tab} ({veces} veces)" for tab, veces in top
            ),
            accion=(
                "Puede que la escala de referencia no sea la que estas tocando. "
                "Fuera de escala no es un error: la tercera mayor sobre un "
                "dominante suena a blues justamente por estar afuera."
            ),
            confianza="baja",
            peso=30,
        ))


# =============================================================================
# Presentación
# =============================================================================

def imprimir(hallazgos, sin_medir, cuantos=3):
    """
    Devuelve el texto del diagnóstico, listo para mostrar.

    Muestra pocos hallazgos a propósito. Una lista de diez cosas para arreglar
    no se ataca: se ignora.
    """
    lineas = []
    lineas.append("=" * 72)
    lineas.append("  QUE ATACAR PRIMERO")
    lineas.append("=" * 72)

    if not hallazgos:
        lineas.append("")
        lineas.append("  No aparecio nada para corregir con confianza suficiente.")
    else:
        for numero, hallazgo in enumerate(hallazgos[:cuantos], start=1):
            lineas.append("")
            lineas.append(f"  {numero}. {hallazgo.titulo}   [confianza {hallazgo.confianza}]")
            lineas.append(f"     Evidencia: {hallazgo.evidencia}")
            lineas.append(f"     Que hacer: {hallazgo.accion}")

        sobrantes = len(hallazgos) - cuantos
        if sobrantes > 0:
            lineas.append("")
            lineas.append(f"  (hay {sobrantes} cosa(s) mas, menos importantes)")

    if sin_medir:
        lineas.append("")
        lineas.append("-" * 72)
        lineas.append("  LO QUE NO SE PUDO MEDIR EN ESTA GRABACION")
        for texto in sin_medir:
            lineas.append("")
            lineas.append(f"  - {texto}")

    return "\n".join(lineas)
