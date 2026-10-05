"""
Tests de armonica/coach.py — el modelo de lenguaje que explica lo medido.

NUNCA TOCAN LA RED. La llamada al modelo (_pedir, o _http_json para los
proveedores por HTTP) se reemplaza por una falsa que devuelve lo que le
pedimos y guarda lo que recibió: así se verifica qué le mandamos, que es lo
único que está en nuestras manos.
"""

import io
import os
import urllib.error

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
    assert conf["modelo"] == "claude-opus-5-5"


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
    assert openai["modelo"] == "gpt-6-luna"
    assert openai["url"] == "https://api.openai.com/v1"

    gemini = coach.configuracion(env_con(tmp_path, "LLM_PROVEEDOR=gemini\nLLM_CLAVE=AQ.x\n"))
    assert gemini["modelo"] == "gemini-3.5-flash-lite"
    assert gemini["url"] == "https://generativelanguage.googleapis.com/v1beta"


def test_un_proveedor_desconocido_se_explica(sin_entorno, tmp_path):
    estado = coach.estado(env_con(tmp_path, "LLM_PROVEEDOR=mistral\n"))
    assert estado["disponible"] is False
    assert "mistral" in estado["motivo"] and "ollama" in estado["motivo"]


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


def test_el_prompt_de_teoria_dice_que_acorde_va_en_cada_compas():
    # Encontrado probando con qwen2.5:7b y llama3.1:8b: a "como aterrizo en
    # la 3ra del compas 5" cada modelo contestaba una nota distinta (D, A,
    # Ab). No era el modelo: el prompt mandaba los tres acordes sueltos y
    # nunca decia cual va en el compas 5. La pantalla si lo sabe.
    teoria = {
        "tonalidad": "C", "nombre_posicion": "12a posicion", "tono": "F",
        "nombre_escala": "Escala de blues mayor", "notas": [], "tonica": "F",
        "corrida": [], "evitar": [], "posiciones_utiles": [],
        "acordes": [{"nombre": "F7"}, {"nombre": "Bb7"}, {"nombre": "C7"}],
        "progresion": [
            {"compas": 1, "grado": "I", "acorde": "F7", "cambia": True},
            {"compas": 2, "grado": "IV", "acorde": "Bb7", "cambia": True},
            {"compas": 3, "grado": "I", "acorde": "F7", "cambia": True},
            {"compas": 4, "grado": "I", "acorde": "F7", "cambia": False},
            {"compas": 5, "grado": "IV", "acorde": "Bb7", "cambia": True},
        ],
    }
    prompt = coach.prompt_de_teoria(teoria, "como aterrizo en la 3ra del compas 5")

    assert "compas 5: Bb7" in prompt


def test_el_prompt_de_teoria_pide_nombrar_nota_y_agujero_no_octavas():
    # Con los mismos datos, los modelos contestaban "de F4 a G4", que en la
    # armonica no dice nada: lo que el alumno necesita es "D, 4 aspirado".
    teoria = {"tonalidad": "C", "corrida": [], "acordes": [], "evitar": [],
              "posiciones_utiles": []}
    prompt = coach.prompt_de_teoria(teoria, "que toco?")

    assert "4 aspirado (↓4)" in prompt      # el ejemplo de como nombrar
    assert "F4" in prompt and "G4" in prompt   # y el ejemplo de como no


def test_el_prompt_de_teoria_aclara_que_la_3ra_es_un_grado_y_no_una_posicion():
    # Preguntando por "la 3ra de Bb7", qwen2.5:7b acertaba la nota 4 de 4
    # veces y en 3 de 4 mandaba al alumno a "la 3ra posicion (slant harp)":
    # confundia el grado del acorde con la posicion. El alumno esta en la
    # posicion de la pantalla y no la cambia.
    teoria = {"tonalidad": "C", "nombre_posicion": "12a posicion", "corrida": [],
              "acordes": [], "evitar": [], "posiciones_utiles": []}
    prompt = coach.prompt_de_teoria(teoria, "como aterrizo en la 3ra de Bb7")

    assert "grado del acorde, no de una posición" in prompt
    assert "ya está en la 12a posicion y no la cambia" in prompt


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
    registro = {"pedidos": [], "respuesta": None, "error": None, "codigo": None, "detalle": "",
                "sin_conexion": False}

    def falso(url, cuerpo, cabeceras, segundos):
        registro["pedidos"].append({"url": url, "cuerpo": cuerpo,
                                    "cabeceras": cabeceras, "segundos": segundos})
        if registro["error"]:
            falla = coach.CoachNoDisponible(registro["error"])
            if registro["codigo"]:
                falla.codigo = registro["codigo"]
                falla.detalle = registro["detalle"]
            if registro["sin_conexion"]:
                falla.sin_conexion = True
            raise falla
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
    # Los modelos de OpenAI que piensan rechazan max_tokens: el tope va en
    # max_completion_tokens, e incluye lo que piensan.
    assert "max_tokens" not in pedido["cuerpo"]
    assert pedido["cuerpo"]["max_completion_tokens"] >= 4000
    assert pedido["cuerpo"]["reasoning_effort"] == "low"


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


# =============================================================================
# Claude y Gemini: por HTTP, sin paquetes. Y los errores, traducidos.
# =============================================================================

def test_claude_manda_el_pedido_por_http_con_la_clave_en_la_cabecera(sin_entorno, tmp_path,
                                                                      http_falso):
    ruta = env_con(tmp_path, "LLM_CLAVE=sk-ant-prueba\n")
    http_falso["respuesta"] = {"stop_reason": "end_turn", "content": [
        {"type": "thinking", "thinking": ""},
        {"type": "text", "text": "  El bend te queda corto.  "}]}

    texto = coach._pedir("el sistema", "el usuario", ruta)

    assert texto == "El bend te queda corto."
    pedido = http_falso["pedidos"][0]
    assert pedido["url"] == "https://api.anthropic.com/v1/messages"
    assert pedido["cabeceras"]["x-api-key"] == "sk-ant-prueba"
    assert pedido["cabeceras"]["anthropic-version"] == "2023-06-01"
    assert pedido["cuerpo"]["model"] == "claude-opus-5-5"
    assert pedido["cuerpo"]["system"] == "el sistema"
    assert pedido["cuerpo"]["messages"] == [{"role": "user", "content": "el usuario"}]
    # Opus 5.5 siempre piensa, y lo que piensa entra en max_tokens: un tope
    # chico cortaría la respuesta. Y apagar el pensamiento o mandar
    # temperature es un error 400 en ese modelo.
    assert pedido["cuerpo"]["max_tokens"] >= 4000
    assert "thinking" not in pedido["cuerpo"]
    assert "temperature" not in pedido["cuerpo"]


def test_gemini_manda_el_pedido_por_su_forma_propia(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=gemini\nLLM_CLAVE=AQ.Ab-prueba\n")
    http_falso["respuesta"] = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"text": "lo que pensó", "thought": True},
        {"text": "  Practicá el cambio despacio.  "}]}}]}

    texto = coach._pedir("el sistema", "el usuario", ruta)

    assert texto == "Practicá el cambio despacio."
    pedido = http_falso["pedidos"][0]
    assert pedido["url"] == ("https://generativelanguage.googleapis.com/v1beta/models/"
                             "gemini-3.5-flash-lite:generateContent")
    # x-goog-api-key y no Authorization: Bearer, que rechaza las claves AQ.
    assert pedido["cabeceras"] == {"x-goog-api-key": "AQ.Ab-prueba"}
    assert pedido["cuerpo"]["system_instruction"] == {"parts": [{"text": "el sistema"}]}
    assert pedido["cuerpo"]["contents"] == [{"role": "user", "parts": [{"text": "el usuario"}]}]
    configuracion = pedido["cuerpo"]["generationConfig"]
    assert configuracion["maxOutputTokens"] >= 4000
    assert configuracion["thinkingConfig"] == {"thinkingLevel": "low"}


@pytest.mark.parametrize("respuesta", [
    {"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]},
    {"promptFeedback": {"blockReason": "SAFETY"}},
])
def test_gemini_que_no_quiere_contestar_se_dice(sin_entorno, tmp_path, http_falso, respuesta):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=gemini\nLLM_CLAVE=AIza-prueba\n")
    http_falso["respuesta"] = respuesta
    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", ruta)
    assert "no quiso" in str(error.value)


@pytest.mark.parametrize("codigo, palabras", [
    (401, "no es válida"), (402, "crédito"), (403, "permiso"),
    (404, "No existe el modelo"), (429, "saturado"), (529, "saturado")])
def test_claude_traduce_cada_error_a_un_motivo(sin_entorno, tmp_path, http_falso,
                                               codigo, palabras):
    ruta = env_con(tmp_path, "LLM_CLAVE=sk-ant-prueba\n")
    http_falso["error"] = f"El servicio contestó con un error ({codigo})."
    http_falso["codigo"] = codigo

    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", ruta)
    assert palabras in str(error.value)


def test_openai_con_la_clave_mala_lo_dice(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=openai\nLLM_CLAVE=sk-vieja\n")
    http_falso["error"] = "El servicio contestó con un error (401)."
    http_falso["codigo"] = 401
    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", ruta)
    assert "no es válida" in str(error.value)


def test_gemini_contesta_400_a_una_clave_mala(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=gemini\nLLM_CLAVE=AIza-vieja\n")
    http_falso["error"] = "El servicio contestó con un error (400)."
    http_falso["codigo"] = 400
    http_falso["detalle"] = '{"error": {"status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}'
    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", ruta)
    assert "no es válida" in str(error.value)


def test_un_400_que_no_es_la_clave_no_culpa_a_la_clave(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_PROVEEDOR=gemini\nLLM_CLAVE=AIza-buena\n")
    http_falso["error"] = "El servicio contestó con un error (400)."
    http_falso["codigo"] = 400
    http_falso["detalle"] = '{"error": {"status": "INVALID_ARGUMENT", "message": "otra cosa"}}'
    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", ruta)
    assert "(400)" in str(error.value)


@pytest.mark.parametrize("proveedor, clave", [
    ("claude", "sk-ant-prueba"), ("openai", "sk-prueba"), ("gemini", "AQ.prueba")])
def test_sin_conexion_lo_dice_sin_jerga(sin_entorno, tmp_path, http_falso, capsys,
                                        proveedor, clave):
    ruta = env_con(tmp_path, f"LLM_PROVEEDOR={proveedor}\nLLM_CLAVE={clave}\n")
    # Lo mismo que levanta _http_json cuando no hay red: el texto trae el
    # error crudo del sistema, que no es para mostrarle al profe.
    http_falso["error"] = ("No hay conexión con el servicio "
                           "(<urlopen error [Errno 11001] getaddrinfo failed>).")
    http_falso["sin_conexion"] = True
    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", ruta)
    assert str(error.value) == "No hay conexión con el servicio. ¿Estás sin internet?"
    assert "Errno" not in str(error.value) and "getaddrinfo" not in str(error.value)
    # El texto crudo no se pierde: queda en el registro.
    assert "Errno 11001" in capsys.readouterr().out


def test_http_json_marca_cuando_no_pudo_conectarse(monkeypatch):
    def falla(pedido, timeout):
        raise urllib.error.URLError("sin red")

    monkeypatch.setattr(coach.urllib.request, "urlopen", falla)
    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._http_json("https://ejemplo.invalid/x", {"a": 1}, {}, segundos=1)
    assert error.value.sin_conexion is True
    assert getattr(error.value, "codigo", None) is None
    assert "sin red" in str(error.value)


def test_claude_que_no_quiere_contestar_se_dice(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_CLAVE=sk-ant-prueba\n")
    http_falso["respuesta"] = {"stop_reason": "refusal", "content": []}
    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", ruta)
    assert "no quiso" in str(error.value)


@pytest.mark.parametrize("proveedor, clave", [
    ("claude", "sk-ant-prueba"), ("openai", "sk-prueba"), ("gemini", "AQ.prueba")])
def test_con_clave_cada_proveedor_esta_disponible_sin_ningun_paquete(sin_entorno, tmp_path,
                                                                     proveedor, clave):
    estado = coach.estado(env_con(tmp_path, f"LLM_PROVEEDOR={proveedor}\nLLM_CLAVE={clave}\n"))
    assert estado["disponible"] is True


def test_sin_clave_gemini_lo_dice(sin_entorno, tmp_path):
    estado = coach.estado(env_con(tmp_path, "LLM_PROVEEDOR=gemini\n"))
    assert estado["disponible"] is False
    assert "Gemini" in estado["motivo"]


def test_en_la_instalada_los_motivos_mandan_a_ajustes(sin_entorno, tmp_path, http_falso,
                                                      monkeypatch):
    monkeypatch.setattr(coach, "CLAVE_EN_AJUSTES", True)

    motivo = coach.estado(sin_entorno)["motivo"]
    assert "Ajustes" in motivo and ".env" not in motivo

    con_clave = env_con(tmp_path, "LLM_CLAVE=sk-ant-vieja_123\n")
    for codigo in (401, 404):
        http_falso["error"] = f"El servicio contestó con un error ({codigo})."
        http_falso["codigo"] = codigo
        with pytest.raises(coach.CoachNoDisponible) as error:
            coach._pedir("s", "u", con_clave)
        assert ".env" not in str(error.value)
        assert "LLM_" not in str(error.value)


def test_el_error_http_lleva_su_codigo_y_su_detalle(monkeypatch):
    def falla(pedido, timeout):
        raise urllib.error.HTTPError(pedido.full_url, 400, "Bad Request", {},
                                     io.BytesIO(b'{"error": {"reason": "API_KEY_INVALID"}}'))

    monkeypatch.setattr(coach.urllib.request, "urlopen", falla)
    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._http_json("https://ejemplo.invalid/x", {"a": 1}, {}, segundos=1)
    assert error.value.codigo == 400
    assert "API_KEY_INVALID" in error.value.detalle


def test_el_prompt_de_la_base_lleva_el_cifrado_y_los_hechos():
    """El coach recibe el cifrado compás por compás y lo que la app contó."""
    ficha = {
        "tonalidad": "F", "modo": "mayor", "bpm": 65, "pulsos_por_compas": 4,
        "con_swing": True, "coro_desde": 1, "coro_hasta": 2,
        "hechos": {"cadencias": [{"tipo": "ii-V-I", "a": "F", "compas": 2}]},
        "cifrado": [{"compas": 1, "acordes": [{"nombre": "Gm7"}, {"nombre": "C7"}]},
                    {"compas": 2, "acordes": [{"nombre": "FMaj7"}]}],
    }
    prompt = coach.prompt_de_base("Georgia", ficha, "C")
    assert "1: Gm7 C7" in prompt and "2: FMaj7" in prompt
    assert "ii-V-I" in prompt
    assert "no agregues ni cambies ninguno" in prompt
    assert '"armonica_del_alumno": "C"' in prompt


def test_explicar_la_base_pasa_por_pedir(monkeypatch):
    recibido = {}

    def falsa(sistema, usuario, ruta_env=None):
        recibido["sistema"], recibido["usuario"] = sistema, usuario
        return "Es un blues de doce."

    monkeypatch.setattr(coach, "_pedir", falsa)
    assert coach.explicar_base("Blues", {"cifrado": [], "hechos": {}}, "C") == "Es un blues de doce."
    assert recibido["sistema"] == coach.SISTEMA
    assert "Blues" in recibido["usuario"]


# =============================================================================
# La clave que se pega en Ajustes (la versión instalada no tiene .env)
# =============================================================================

@pytest.mark.parametrize("clave, proveedor", [
    ("sk-ant-api03-abcdefghij", "claude"),
    ("sk-proj-abcdefghij", "openai"),
    ("sk-abcdefghijklmnop", "openai"),
    ("AIzaSyAbcdefghijklmnop", "gemini"),
    ("AQ.Ab8RN6Kabcdefghij", "gemini"),
    ("hola-abcdefghij", None),
])
def test_de_quien_es_cada_clave(clave, proveedor):
    assert coach.proveedor_de_la_clave(clave) == proveedor


@pytest.mark.parametrize("clave, proveedor, modelo", [
    ("sk-ant-guardada_123", "claude", "claude-opus-5-5"),
    ("sk-proj-guardada_123", "openai", "gpt-6-luna"),
    ("AQ.Ab-guardada_123", "gemini", "gemini-3.5-flash-lite"),
])
def test_la_clave_guardada_se_usa_con_su_proveedor(sin_entorno, clave, proveedor, modelo):
    assert coach.guardar_clave(clave) == proveedor

    conf = coach.configuracion(sin_entorno)

    assert conf["clave"] == clave
    assert conf["proveedor"] == proveedor
    assert conf["modelo"] == modelo
    estado = coach.estado(sin_entorno)
    assert estado["clave_en_ajustes"] is True and estado["disponible"] is True


def test_el_env_le_gana_a_la_clave_guardada(sin_entorno, tmp_path):
    coach.guardar_clave("sk-ant-guardada_123")
    conf = coach.configuracion(env_con(tmp_path, "LLM_PROVEEDOR=ollama\n"))
    assert conf["proveedor"] == "ollama"


def test_la_clave_guardada_le_gana_al_entorno(sin_entorno, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "desde-el-entorno")
    coach.guardar_clave("sk-ant-guardada_123")
    assert coach.configuracion(sin_entorno)["clave"] == "sk-ant-guardada_123"


def test_guardar_vacio_borra_la_clave(sin_entorno):
    coach.guardar_clave("sk-ant-guardada_123")

    assert coach.guardar_clave("  ") == ""

    assert not os.path.exists(coach.ruta_de_la_clave())
    assert coach.estado(sin_entorno)["clave_en_ajustes"] is False


def test_guardar_es_atomico_y_no_deja_temporales(sin_entorno):
    coach.guardar_clave("sk-ant-guardada_123")
    assert os.listdir(os.path.dirname(coach.ruta_de_la_clave())) == ["coach.env"]


@pytest.mark.parametrize("mala", [
    "sk-ant con espacio", "sk-ant\nLLM_PROVEEDOR=ollama", "sk-" + "x" * 300, "sk-corta",
    "sk-ant-ñandú12345", "desconocida-abcdefghij"])
def test_lo_que_no_es_una_clave_conocida_no_se_guarda(sin_entorno, mala):
    with pytest.raises(ValueError):
        coach.guardar_clave(mala)
    assert not os.path.exists(coach.ruta_de_la_clave())


def test_la_ruta_de_la_clave_esta_en_localappdata(monkeypatch):
    monkeypatch.setattr(coach, "ARCHIVO_CLAVE", None)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Usuarios\alguien\AppData\Local")
    assert coach.ruta_de_la_clave() == os.path.join(
        r"C:\Usuarios\alguien\AppData\Local", "Armonica", "coach.env")


def test_probar_hace_un_pedido_minimo(llamada_falsa):
    assert coach.probar() == "Vamos por partes: el bend del 3 te queda corto."
    assert llamada_falsa["usuario"]
