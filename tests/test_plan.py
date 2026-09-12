"""
Tests de armonica/plan.py — el plan de estudio armado por el coach.

Sin red: la llamada al modelo se reemplaza por una falsa. Los apuntes son
inventados.
"""

import json
import os

import pytest

from armonica import clases, coach, plan


RECAP = """# Clase 2026-03-04

## Propósito de la reunión

Revisar el ejercicio de la semana.

## Puntos clave

- **El bend del 3:** quedó corto.

## Próximos pasos

- **Ana:** practicar el bend del 3 hasta que quede afinado.
"""

RESPUESTA_JSON = json.dumps({
    "viendo": "Estamos en la escala de dos octavas en 2ª, con el bend del 3 corto.",
    "recomendaciones": [
        {"que": "Practicá el bend del 3 sostenido, mirando el medidor.",
         "por_que": "Queda corto: no bajás lo suficiente.",
         "en_la_app": "En vivo, con la línea lavanda.", "solapa": "vivo"},
        {"que": "Mirá la pentatónica mayor en 1ª.", "por_que": "Para el contraste.",
         "en_la_app": "Teoría.", "solapa": "teoria",
         "config": {"posicion": 1, "escala": "pentatonica_mayor", "otra": "no"}},
        {"que": "Algo con solapa inválida", "solapa": "cocina"},
        {"sin_que": True},
    ],
    "frase_del_profe": "Anticipar un compás.",
}, ensure_ascii=False)


@pytest.fixture
def carpetas(tmp_path):
    de_clases = tmp_path / "clases"
    de_clases.mkdir()
    (de_clases / "2026-03-04.md").write_text(RECAP, encoding="utf-8")
    (de_clases / "aprendizaje.md").write_text("# Síntesis\n\nEl ritmo.", encoding="utf-8")
    del_plan = tmp_path / "material"
    return str(de_clases), str(del_plan)


@pytest.fixture
def coach_falso(monkeypatch, tmp_path):
    recibido = {}

    def falsa(sistema, usuario, ruta_env=None):
        recibido["usuario"] = usuario
        return recibido.get("respuesta", RESPUESTA_JSON)

    monkeypatch.setattr(coach, "_pedir", falsa)
    env = tmp_path / ".env"
    env.write_text("LLM_PROVEEDOR=ollama\n", encoding="utf-8")
    recibido["env"] = str(env)
    return recibido


# =============================================================================
# Interpretar lo que devuelve el modelo
# =============================================================================

def test_interpreta_el_json_y_descarta_lo_que_no_sirve():
    datos = plan.interpretar(RESPUESTA_JSON)

    assert datos["en_crudo"] is False
    assert datos["viendo"].startswith("Estamos en la escala")
    assert len(datos["recomendaciones"]) == 3           # la sin "que" se descarta
    assert datos["recomendaciones"][0]["solapa"] == "vivo"
    assert datos["recomendaciones"][1]["config"] == {"posicion": 1, "escala": "pentatonica_mayor"}
    assert datos["recomendaciones"][2]["solapa"] == ""  # "cocina" no es una solapa
    assert datos["frase_del_profe"] == "Anticipar un compás."


def test_interpreta_el_json_aunque_venga_en_un_bloque_de_codigo():
    datos = plan.interpretar("```json\n" + RESPUESTA_JSON + "\n```")
    assert datos["en_crudo"] is False and len(datos["recomendaciones"]) == 3


def test_si_no_es_json_el_texto_queda_como_viendo():
    datos = plan.interpretar("Bueno, mirá: lo primero es el bend del 3.")
    assert datos["en_crudo"] is True
    assert datos["viendo"].startswith("Bueno")
    assert datos["recomendaciones"] == []


# =============================================================================
# Armar y guardar
# =============================================================================

def test_armar_manda_las_clases_y_la_sintesis_y_guarda_con_fecha(carpetas, coach_falso):
    de_clases, del_plan = carpetas

    datos = plan.armar(de_clases, del_plan, coach_falso["env"])

    assert "bend del 3" in coach_falso["usuario"]           # la clase fue
    assert "El ritmo." in coach_falso["usuario"]            # la síntesis también
    assert 'solapa "teoria"' in coach_falso["usuario"]     # y el catálogo de la app
    assert datos["clases_usadas"] == ["2026-03-04"]
    assert datos["proveedor"] == "ollama"
    assert datos["fecha"][:4] == "2026"

    guardado = plan.cargar(del_plan)
    assert guardado["viendo"] == datos["viendo"]
    assert os.path.isfile(os.path.join(del_plan, "_plan.json"))


def test_el_plan_nunca_se_guarda_en_la_carpeta_de_clases(carpetas, coach_falso):
    de_clases, del_plan = carpetas
    antes = sorted(os.listdir(de_clases))
    plan.armar(de_clases, del_plan, coach_falso["env"])
    assert sorted(os.listdir(de_clases)) == antes


def test_sin_clases_con_recap_no_se_llama_al_modelo(tmp_path, coach_falso):
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    with pytest.raises(coach.CoachNoDisponible):
        plan.armar(str(vacia), str(tmp_path / "material"), coach_falso["env"])
    assert "usuario" not in coach_falso


def test_cargar_sin_plan_da_none_y_borrar_no_rompe(tmp_path):
    assert plan.cargar(str(tmp_path)) is None
    plan.borrar(str(tmp_path))


# =============================================================================
# Fase 3: el plan como contexto de la devolucion
# =============================================================================

def test_el_plan_como_contexto_lleva_solo_lo_que_dice_el_profe():
    contexto = plan.como_contexto(plan.interpretar(RESPUESTA_JSON) | {"fecha": "2026-03-05T10:00"})
    assert contexto.startswith("Plan de estudio armado el 2026-03-05")
    assert "bend del 3" in contexto
    assert "Anticipar un compás" in contexto


def test_la_devolucion_recibe_el_plan_como_contexto_y_no_como_datos():
    prompt = coach.prompt_de_devolucion({"nombre": "x", "devolucion": {}}, contexto="El profe: anticipar.")
    assert "El profe: anticipar." in prompt
    assert "no saques números de acá" in prompt


def test_sin_plan_la_devolucion_es_la_de_siempre():
    prompt = coach.prompt_de_devolucion({"nombre": "x", "devolucion": {}})
    assert "plan de estudio" not in prompt
