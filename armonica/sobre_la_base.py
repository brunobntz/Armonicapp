"""
sobre_la_base.py — Qué tocaste sobre cada acorde de la base.

Cuando practicás sobre una base que la app misma reproduce, la app sabe en
qué instante arrancó el compás 1 y a qué tempo iba. Con eso, cada nota que
tocaste cae en un compás y un tiempo concretos, y sobre un acorde concreto.
Este módulo cuenta lo que se puede contar de eso:

- de cada nota, si era una nota del acorde que sonaba, y qué grado (la 3a,
  la 7a, la tónica...);
- en los compases donde cambia el acorde, si la primera nota que tocaste era
  una nota guía (la 3a o la 7a). Es el ejercicio del profe: "aterrizar en una
  nota guía en el tiempo 1 del cambio".

Cuenta, no opina: una nota fuera del acorde puede ser una nota de paso
buscada. Y con menos de tres notas no hay nada que contar, y lo dice.
"""

from dataclasses import dataclass

from armonica import tablas

MINIMO_DE_NOTAS = 3
GRADOS_GUIA = set(tablas.GRADOS_GUIA)


@dataclass
class NotaSobreLaBase:
    evento: object
    compas: int              # absoluto desde el compás 1 de la base
    compas_en_la_vuelta: int  # el del cifrado (la base repite el coro)
    tiempo: int
    acorde: str
    intervalo: int           # semitonos desde la raíz del acorde
    en_el_acorde: bool
    es_guia: bool

    @property
    def grado(self):
        return tablas.NOMBRES_GRADOS.get(self.intervalo, f"{self.intervalo} semitonos")


def evaluar(eventos, base, bpm, offset_seg, nombre_cancion=""):
    """
    El análisis completo, como diccionario listo para guardar y mostrar.

    `bpm` es el tempo al que sonó la base (puede ser más lento que el del
    archivo) y `offset_seg` el instante de la grabación en que cayó el tiempo
    1 del compás 1. Las notas anteriores a ese instante son del conteo y no
    cuentan.
    """
    notas = colocar(eventos, base, bpm, offset_seg)
    por_compas = {}
    for nota in notas:
        por_compas.setdefault(nota.compas, []).append(nota)

    cambios = set(base.compases_de_cambio())
    cambios_con_nota = 0
    aterrizajes_en_guia = 0
    for compas, lista in sorted(por_compas.items()):
        if lista[0].compas_en_la_vuelta not in cambios:
            continue
        cambios_con_nota += 1
        primera = min(lista, key=lambda n: n.evento.inicio_seg)
        if primera.tiempo == 1 and primera.es_guia:
            aterrizajes_en_guia += 1

    en_el_acorde = sum(1 for n in notas if n.en_el_acorde)
    suficiente = len(notas) >= MINIMO_DE_NOTAS
    return {
        "cancion": nombre_cancion,
        "bpm": bpm,
        "offset_seg": round(offset_seg, 3),
        "notas": len(notas),
        "suficiente": suficiente,
        "en_el_acorde": en_el_acorde,
        "porcentaje_en_el_acorde": round(100.0 * en_el_acorde / len(notas)) if suficiente else None,
        "cambios_con_nota": cambios_con_nota,
        "aterrizajes_en_guia": aterrizajes_en_guia,
        "por_compas": [
            {
                "compas": compas,
                "compas_en_la_vuelta": lista[0].compas_en_la_vuelta,
                "es_cambio": lista[0].compas_en_la_vuelta in cambios,
                "notas": [
                    {"tab": n.evento.como_tab(), "tiempo": n.tiempo, "acorde": n.acorde,
                     "grado": n.grado, "en_el_acorde": n.en_el_acorde, "es_guia": n.es_guia}
                    for n in sorted(lista, key=lambda n: n.evento.inicio_seg)
                ],
            }
            for compas, lista in sorted(por_compas.items())
        ],
    }


def colocar(eventos, base, bpm, offset_seg):
    """Cada nota reconocida, puesta en su compás, su tiempo y su acorde."""
    segundos_por_pulso = 60.0 / bpm
    pulsos_por_compas = base.pulsos_por_compas
    desde, hasta = base.coro_desde, base.coro_hasta
    if not 1 <= desde < hasta <= base.compases:
        desde, hasta = 1, max(base.compases, 1)
    vuelta = hasta - desde + 1

    colocadas = []
    for evento in eventos:
        if evento.nota is None:
            continue
        instante = evento.inicio_seg - offset_seg
        if instante < 0:
            continue
        pulsos = int(instante // segundos_por_pulso)
        compas = pulsos // pulsos_por_compas + 1
        tiempo = pulsos % pulsos_por_compas + 1
        # La base repite el coro: pasado el último compás vuelve al primero.
        compas_en_la_vuelta = (compas - desde) % vuelta + desde
        acorde = base.acorde_en(compas_en_la_vuelta, tiempo)
        if acorde is None:
            continue
        intervalo = (evento.nota.midi - acorde.clase_raiz()) % 12
        en_el_acorde = intervalo in acorde.intervalos()
        colocadas.append(NotaSobreLaBase(
            evento=evento, compas=compas, compas_en_la_vuelta=compas_en_la_vuelta,
            tiempo=tiempo, acorde=acorde.nombre(), intervalo=intervalo,
            en_el_acorde=en_el_acorde,
            es_guia=en_el_acorde and intervalo in GRADOS_GUIA,
        ))
    return colocadas


def como_texto(evaluacion):
    """Las líneas para el resumen de la sesión."""
    if not evaluacion:
        return ""
    lineas = [f"SOBRE LA BASE {evaluacion['cancion']} a {evaluacion['bpm']} BPM"]
    if not evaluacion["suficiente"]:
        lineas.append(f"  {evaluacion['notas']} notas: muy pocas para contar algo.")
        return "\n".join(lineas)
    lineas.append(f"  {evaluacion['en_el_acorde']} de {evaluacion['notas']} notas eran del "
                  f"acorde que sonaba ({evaluacion['porcentaje_en_el_acorde']}%).")
    if evaluacion["cambios_con_nota"]:
        lineas.append(f"  En los cambios de acorde, aterrizaste en una nota guia "
                      f"{evaluacion['aterrizajes_en_guia']} de {evaluacion['cambios_con_nota']} veces.")
    for compas in evaluacion["por_compas"]:
        marca = "*" if compas["es_cambio"] else " "
        notas = " ".join(
            f"{n['tab']}({'guia' if n['es_guia'] else n['grado'] if n['en_el_acorde'] else 'fuera'})"
            for n in compas["notas"])
        lineas.append(f"  c{compas['compas']:<3}{marca} {compas['notas'][0]['acorde']:<8} {notas}")
    lineas.append("    * = compas donde cambia el acorde; guia = la 3a o la 7a")
    return "\n".join(lineas)
