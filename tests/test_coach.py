"""
Tests de armonica/coach.py — el modelo de lenguaje que explica lo medido.

NUNCA TOCAN LA RED. La llamada al modelo (_pedir) se reemplaza por una falsa
que devuelve lo que le pedimos y guarda lo que recibió: así se verifica qué
le mandamos, que es lo único que está en nuestras manos.
"""

import pytest

from armonica import coach


# =============================================================================
# El .env
# =============================================================================

def test_lee_el_env_ignorando_comentarios_y_comillas(tmp_path):
    ruta = tmp_path / ".env"
    ruta.write_text(
        "# la clave\nLLM_CLAVE=\"abc-123\"\n\nLLM_MODELO='un-modelo'\nSIN_IGUAL\n",
        encoding="utf-8")

    valores = coach.leer_env(str(ruta))

    assert valores == {"LLM_CLAVE": "abc-123", "LLM_MODELO": "un-modelo"}


def test_sin_env_no_hay_clave_y_el_modelo_es_el_de_siempre(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_CLAVE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODELO", raising=False)

    clave, modelo = coach.configuracion(str(tmp_path / "no-existe.env"))

    assert clave == ""
    assert modelo == coach.MODELO_POR_DEFECTO


def test_sin_clave_el_estado_dice_como_activarlo(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_CLAVE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    estado = coach.estado(str(tmp_path / "no-existe.env"))

    assert estado["disponible"] is False
    assert ".env" in estado["motivo"]


def test_la_variable_de_entorno_del_sdk_tambien_sirve(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "desde-el-entorno")
    clave, _ = coach.configuracion(str(tmp_path / "no-existe.env"))
    assert clave == "desde-el-entorno"


# =============================================================================
# Los prompts: que le mandamos
# =============================================================================

COMPARACION = {
    "nombre": "lean 1 tramo 2",
    "velocidad": 20,
    "faltantes": [], "sobrantes": [], "cambiadas": [],
    "notas": [{"tab": "-3''", "desvio_ms": 12, "cents": 35}],
    "devolucion": {
        "notas": {"aciertos": 12, "esperadas": 12, "porcentaje": 100},
        "afinacion": {"medida": True, "desvio_tipico_cents": 0,
                      "bends_fuera": [{"tab": "-3''", "cents": 35, "veces": 2}]},
        "tiempo": {"medido": True, "velocidad_pct": 20, "calidad": "muy parecida",
                   "a_tiempo": 11, "medidas": 12, "peor": {"tab": "-6", "desvio_ms": 180}},
        "consejos": ["El -3'' te queda 35 cents alto: el bend se queda corto."],
    },
}


def test_el_prompt_de_devolucion_lleva_los_numeros_medidos_y_los_consejos():
    prompt = coach.prompt_de_devolucion(COMPARACION)

    assert "lean 1 tramo 2" in prompt
    assert "35" in prompt and "-3''" in prompt
    assert "bend se queda corto" in prompt          # los consejos van adentro
    assert "no los contradigas" in prompt           # y se le pide respetarlos


def test_el_sistema_prohibe_inventar_numeros():
    assert "No inventes" in coach.SISTEMA
    assert "rioplatense" in coach.SISTEMA


def test_el_prompt_de_teoria_lleva_lo_que_esta_en_pantalla_y_la_pregunta():
    teoria = {
        "tonalidad": "C", "nombre_posicion": "12a posicion", "tono": "F",
        "nombre_escala": "Escala de blues mayor", "notas": ["F", "G", "Ab", "A", "C", "D"],
        "tonica": "F", "corrida": [{"tab": "-2''", "nombre": "F4"}],
        "acordes": [{"nombre": "F7"}], "evitar": [{"acorde": "F7", "agujeros": ["2"]}],
        "posiciones_utiles": [],
    }
    prompt = coach.prompt_de_teoria(teoria, "¿por qué evito el 2 soplado?")

    assert "-2'' F4" in prompt
    assert "F7" in prompt
    assert "¿por qué evito el 2 soplado?" in prompt


# =============================================================================
# Las dos preguntas, con la llamada falsa
# =============================================================================

@pytest.fixture
def llamada_falsa(monkeypatch):
    """Reemplaza _pedir: guarda lo que recibio y contesta algo fijo."""
    recibido = {}

    def falsa(sistema, usuario, ruta_env=None):
        recibido["sistema"] = sistema
        recibido["usuario"] = usuario
        return "Vamos por partes: el bend del 3 te queda corto."

    monkeypatch.setattr(coach, "_pedir", falsa)
    return recibido


def test_explicar_devolucion_manda_el_sistema_y_los_datos(llamada_falsa):
    texto = coach.explicar_devolucion(COMPARACION)

    assert texto.startswith("Vamos por partes")
    assert llamada_falsa["sistema"] == coach.SISTEMA
    assert "35" in llamada_falsa["usuario"]


def test_preguntar_teoria_sin_pregunta_no_llama_a_nadie(llamada_falsa):
    with pytest.raises(coach.CoachNoDisponible):
        coach.preguntar_teoria({}, "   ")
    assert llamada_falsa == {}


def test_sin_clave_pedir_no_intenta_conectarse(tmp_path, monkeypatch):
    """La llamada real, sin clave: tiene que fallar ANTES de tocar la red."""
    monkeypatch.delenv("LLM_CLAVE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", str(tmp_path / "no-existe.env"))
    assert ".env" in str(error.value)
