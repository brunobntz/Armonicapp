"""
Tests de armonica/coach.py — el modelo de lenguaje que explica lo medido.

NUNCA TOCAN LA RED. La llamada al modelo (_pedir, o _http_json para los
proveedores por HTTP) se reemplaza por una falsa que devuelve lo que le
pedimos y guarda lo que recibió: así se verifica qué le mandamos, que es lo
único que está en nuestras manos.
"""

import pytest

from armonica import coach


@pytest.fixture
def sin_entorno(monkeypatch, tmp_path):
    """Sin claves en el entorno y sin .env: la configuracion de fabrica."""
    for nombre in ("LLM_PROVEEDOR", "LLM_CLAVE", "LLM_MODELO", "LLM_URL",
                   "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(nombre, raising=False)
    return str(tmp_path / "no-existe.env")


def env_con(tmp_path, texto):
    ruta = tmp_path / ".env"
    ruta.write_text(texto, encoding="utf-8")
    return str(ruta)


# =============================================================================
# El .env
# =============================================================================

def test_lee_el_env_ignorando_comentarios_y_comillas(tmp_path):
    ruta = env_con(tmp_path,
                   "# la clave\nLLM_CLAVE=\"abc-123\"\n\nLLM_MODELO='un-modelo'\nSIN_IGUAL\n")
    assert coach.leer_env(ruta) == {"LLM_CLAVE": "abc-123", "LLM_MODELO": "un-modelo"}


def test_de_fabrica_es_claude_sin_clave(sin_entorno):
    conf = coach.configuracion(sin_entorno)
    assert conf["proveedor"] == "claude"
    assert conf["clave"] == ""
    assert conf["modelo"] == "claude-opus-5"


def test_sin_clave_el_estado_dice_como_activarlo(sin_entorno):
    estado = coach.estado(sin_entorno)
    assert estado["disponible"] is False
    assert ".env" in estado["motivo"]
    assert estado["proveedor"] == "claude"


def test_la_variable_de_entorno_del_sdk_tambien_sirve(sin_entorno, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "desde-el-entorno")
    assert coach.configuracion(sin_entorno)["clave"] == "desde-el-entorno"


def test_cada_proveedor_tiene_su_modelo_y_su_direccion_por_defecto(sin_entorno, tmp_path):
    ollama = coach.configuracion(env_con(tmp_path, "LLM_PROVEEDOR=ollama\n"))
    assert ollama["modelo"] == "qwen2.5:7b"
    assert ollama["url"] == "http://localhost:11434"

    openai = coach.configuracion(env_con(tmp_path, "LLM_PROVEEDOR=openai\nLLM_CLAVE=sk-x\n"))
    assert openai["modelo"] == "gpt-4o-mini"
    assert openai["url"] == "https://api.openai.com/v1"


def test_un_proveedor_desconocido_se_explica(sin_entorno, tmp_path):
    estado = coach.estado(env_con(tmp_path, "LLM_PROVEEDOR=gemini\n"))
    assert estado["disponible"] is False
    assert "gemini" in estado["motivo"] and "ollama" in estado["motivo"]


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


def test_sin_clave_claude_no_intenta_conectarse(sin_entorno):
    """La llamada real, sin clave: tiene que fallar ANTES de tocar la red."""
    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", sin_entorno)
    assert ".env" in str(error.value)


# =============================================================================
# Ollama y OpenAI: que pedido HTTP arman, con la red reemplazada
# =============================================================================

@pytest.fixture
def http_falso(monkeypatch):
    """Reemplaza _http_json: guarda el pedido y contesta lo que se le diga."""
    registro = {"pedidos": [], "respuesta": None, "error": None}

    def falso(url, cuerpo, cabeceras, segundos):
        registro["pedidos"].append({"url": url, "cuerpo": cuerpo,
                                    "cabeceras": cabeceras, "segundos": segundos})
        if registro["error"]:
            raise coach.CoachNoDisponible(registro["error"])
        return registro["respuesta"]

    monkeypatch.setattr(coach, "_http_json", falso)
    return registro


def test_ollama_manda_el_chat_al_servidor_local_sin_clave(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=ollama\n")
    http_falso["respuesta"] = {"message": {"role": "assistant", "content": "  Bien ahí.  "}}

    texto = coach._pedir("el sistema", "el usuario", ruta)

    assert texto == "Bien ahí."
    pedido = http_falso["pedidos"][0]
    assert pedido["url"] == "http://localhost:11434/api/chat"
    assert pedido["cuerpo"]["model"] == "qwen2.5:7b"
    assert pedido["cuerpo"]["stream"] is False
    assert pedido["cuerpo"]["messages"] == [
        {"role": "system", "content": "el sistema"},
        {"role": "user", "content": "el usuario"}]
    assert "Authorization" not in pedido["cabeceras"]
    assert pedido["segundos"] >= 120          # un modelo local tarda


def test_ollama_apagado_se_dice_con_esas_palabras(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=ollama\n")
    http_falso["error"] = "No hay conexión con el servicio (rechazada)."

    estado = coach.estado(ruta)
    assert estado["disponible"] is False
    assert "no está corriendo" in estado["motivo"]

    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", ruta)
    assert "no está corriendo" in str(error.value)


def test_ollama_sin_el_modelo_dice_como_bajarlo(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=ollama\nLLM_MODELO=llama3.1:8b\n")
    http_falso["respuesta"] = {"models": [{"name": "qwen2.5:7b"}]}

    estado = coach.estado(ruta)
    assert estado["disponible"] is False
    assert "ollama pull llama3.1:8b" in estado["motivo"]


def test_ollama_con_el_modelo_esta_disponible(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=ollama\n")
    http_falso["respuesta"] = {"models": [{"name": "qwen2.5:7b"}]}
    assert coach.estado(ruta)["disponible"] is True


def test_openai_manda_la_clave_en_la_cabecera(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=openai\nLLM_CLAVE=sk-prueba\nLLM_MODELO=gpt-x\n")
    http_falso["respuesta"] = {"choices": [{"message": {"content": "Dale."}}]}

    texto = coach._pedir("s", "u", ruta)

    assert texto == "Dale."
    pedido = http_falso["pedidos"][0]
    assert pedido["url"] == "https://api.openai.com/v1/chat/completions"
    assert pedido["cabeceras"]["Authorization"] == "Bearer sk-prueba"
    assert pedido["cuerpo"]["model"] == "gpt-x"


def test_openai_sin_clave_no_toca_la_red(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=openai\n")
    with pytest.raises(coach.CoachNoDisponible):
        coach._pedir("s", "u", ruta)
    assert http_falso["pedidos"] == []


def test_una_respuesta_vacia_es_un_error_y_no_un_texto_vacio(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=ollama\n")
    http_falso["respuesta"] = {"message": {"content": "   "}}
    with pytest.raises(coach.CoachNoDisponible):
        coach._pedir("s", "u", ruta)
