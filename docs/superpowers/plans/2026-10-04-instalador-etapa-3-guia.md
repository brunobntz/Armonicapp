# Instalador, etapa 3: la guía y los cuatro cambios — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el instalador nuevo traiga la guía de uso (en la app y en PDF), el coach que el profe activa pegando una clave de Claude, ChatGPT o Gemini en Ajustes, los íconos donde los busca un usuario básico y un `registro.txt` sin ruido; armado y probado de punta a punta una sola vez.

**Architecture:** Primero cinco cambios de código, cada uno con sus tests: el registro sin tracebacks de conexiones cortadas; el coach hablándoles por HTTP a Claude, ChatGPT y Gemini (sin paquetes), con motivos que mandan a Ajustes en la versión instalada; la clave guardada en `%LOCALAPPDATA%\Armonica\coach.env`, reconocida por cómo empieza, con su ruta en el servidor; la sección del coach en Ajustes de la instalada; y los íconos del instalador. Después la guía: `armonica/web/guia.html` con un enlace "Guía" en la barra, el PDF impreso con Edge al armar, las capturas de la app con datos neutros y el capítulo de Band-in-a-Box armado con las capturas de Bruno. Al final, versión 0.2.0, documentación, un solo instalador y la prueba de `PROBAR.md`.

**Tech Stack:** Python 3.14 (biblioteca estándar), JavaScript sin dependencias, HTML/CSS (con `@media print` para el PDF), Microsoft Edge sin ventana (`--headless --print-to-pdf`), Inno Setup 6, Pillow (del `.venv`) para recortar capturas, pytest.

**Spec:** `docs/superpowers/specs/2026-10-02-instalador-profe-design.md` (secciones "La guía", "Cómo queda instalado", "El armado", "Probarlo"). Además, lo que Bruno aprobó en chat el 2026-10-04 después de probar el instalador 0.1.0 en su usuario (ver "Desvíos de la spec").

**Desvíos de la spec, decididos acá:**
- **El coach entra para el profe.** La spec lo dejaba afuera; Bruno lo pidió el 2026-10-04. La clave se pega en Ajustes (no en el instalador: así se cambia sin reinstalar) y se guarda en `%LOCALAPPDATA%\Armonica\coach.env`, no en Documentos, que puede estar subida a OneDrive. El desinstalador la borra.
- **Cualquiera de tres proveedores: Claude, ChatGPT o Gemini.** La app reconoce de quién es la clave por cómo empieza: `sk-ant-` Claude, `sk-` ChatGPT, `AIza` o `AQ.` Gemini (Google cambió el formato de sus claves en 2026: las nuevas empiezan con `AQ.`). Ollama sigue solo para Bruno (necesita una placa de video).
- **Por HTTP con la biblioteca estándar, sin los paquetes de cada proveedor.** Es a propósito, aunque lo normal en Python sería el SDK de cada uno: la versión instalada no los trae, y sumarlos agrega httpx, pydantic y bibliotecas compiladas sin firma que el Control inteligente de aplicaciones puede bloquear. OpenAI ya habla por HTTP así (`_http_json`).
- **Gemini por su forma propia (`generateContent` con la cabecera `x-goog-api-key`), no por su versión compatible con OpenAI:** con `Authorization: Bearer` las claves nuevas `AQ.` pueden ser rechazadas; con `x-goog-api-key` andan las nuevas y las viejas.
- **Modelos por defecto, verificados el 2026-10-04** en la documentación de cada uno: Claude `claude-opus-5-5`; ChatGPT `gpt-6-luna` (el más barato; piensa antes de contestar, así que el tope va en `max_completion_tokens`, `max_tokens` lo rechaza); Gemini `gemini-3.5-flash-lite` (estable, sin fecha de retiro anunciada). La app instalada no se actualiza sola: si un modelo se retira, el coach dice que hace falta una versión nueva.
- **Sin el parámetro `fallbacks` (beta) de la API de Claude.** Un beta que cambie rompería la app del profe, que no se actualiza. Un rechazo (`stop_reason: "refusal"`, o `SAFETY` en Gemini) se informa con un motivo.
- **Íconos:** el del escritorio siempre, sin preguntar (Bruno lo destildó y después no encontraba cómo abrir la app; el aviso de "Cerrar la app" ya manda al ícono del escritorio), uno más en `Documentos\Armonica` ("Abrir Armónica") y en Inicio "Armónica" y "Guía de Armónica".
- **Cerrar la pestaña deja la app abierta, como hoy** (suelta el micrófono al minuto). La guía explica "Cerrar la app". Apagarla sola traería otro problema: Chrome duerme las pestañas viejas y el profe volvería a una página que no carga.
- **El capítulo de instalar cubre pendrive y Drive.** El 2026-10-04, con el Control inteligente de aplicaciones activado, el instalador bajado de Drive se bloqueó sin "Ejecutar de todas formas"; sin la marca de internet (desbloqueado, o desde un pendrive) corrió. La captura del aviso común de SmartScreen no se puede sacar en la máquina de Bruno: va solo con texto, salvo que Bruno consiga otra PC.

## Global Constraints

- NUNCA commitear `config.py` ni `EVALUATION_2026-09-18.md` (cambios locales de Bruno). Cada commit agrega solo los archivos de su tarea.
- Los tests se corren con `.venv/Scripts/python.exe -m pytest` (en un worktree, con la ruta absoluta del `.venv` del repo principal: `C:\Users\bruno\repos\Armonicapp\.venv\Scripts\python.exe`).
- En la carpeta del repo de Bruno fallan tests por su entorno (umbral local en `config.py`, Ollama en su `.env`): `tests/test_audio.py::test_normalizar_arregla_una_grabacion_demasiado_baja` y `tests/test_servidor.py::test_la_lista_de_canciones_trae_la_ficha_para_la_armonica_puesta`. En un worktree no fallan.
- Ningún test toca la red, el micrófono, `Documentos` ni `%LOCALAPPDATA%\Armonica` de verdad: el coach se prueba reemplazando `_pedir` o `_http_json`, y la clave guardada va a un archivo temporal (fixture automática de `tests/conftest.py`).
- Nunca una clave real en tests, commits, capturas ni en la conversación. Las claves las pega Bruno.
- La clave del coach nunca vuelve al navegador: `/api/coach` y `/api/coach/clave` dicen si hay una, de quién es y si anda, nunca cuál es.
- Textos de pantalla, del instalador y de la guía en castellano rioplatense (voseo), sin jerga: nada de `.env`, `CARPETA_`, `material/`, `pip install`, `python main.py`, `winget`, `LLM_`, `127.0.0.1`, `localhost`, `pythonw`, "servidor" ni "puerto" en lo que ve el profe.
- Lo que es solo para Bruno va adentro de un elemento `solo-desarrollo`; lo que es solo para la instalada, en `solo-empaquetada` (`estilo.css` oculta cada uno en el otro modo).
- Las imágenes de la guía se commitean (el repo es público): sin nombres de personas, rutas con usuarios, correos ni datos de clase. Ancho máximo 1100 px, PNG optimizado.
- Comentarios y docstrings en castellano, explicando el porqué, como el resto del código.
- Mensajes de commit en castellano, una oración sin prefijo, y al final `Co-Authored-By: <el modelo que escribió el commit> <noreply@anthropic.com>`.
- AppId del instalador: `{DE843E22-3123-424E-AFFC-A46A5622326D}` (no cambia).

---

## Mapa de archivos

| Archivo | Qué cambia |
|---|---|
| `armonica/servidor.py` | `ServidorExclusivo.handle_error` calla los cortes de conexión; `POST /api/coach/clave`; `arrancar` avisa al coach si es la instalada |
| `armonica/coach.py` | Claude y Gemini por HTTP, ChatGPT al día; modelos vigentes; errores traducidos en un solo lugar; motivos para Bruno o para la instalada; la clave guardada (`ARCHIVO_CLAVE`, `ruta_de_la_clave`, `proveedor_de_la_clave`, `guardar_clave`, `probar`) |
| `armonica/web/index.html` | La sección "El coach" para la instalada; el enlace "Guía" en la barra |
| `armonica/web/app.js` | Guardar, probar y borrar la clave; el estado del coach en la instalada; Gemini en los nombres de proveedor |
| `armonica/web/estilo.css` | El enlace "Guía" con la forma de una solapa |
| `armonica/web/guia.html` (nuevo) | La guía |
| `armonica/web/guia/*.png` (nuevos) | Las capturas de la guía |
| `empaquetado/armonica.iss` | Íconos; la guía en Inicio; el desinstalador borra la clave |
| `herramientas/empaquetar.py` | `buscar_edge`, `orden_del_pdf`, `generar_pdf`; el PDF al armar, en la humo y en `dist/` |
| `tests/conftest.py` | La clave guardada nunca es la de verdad; los motivos, los de Bruno |
| `tests/test_coach.py`, `tests/test_servidor.py`, `tests/test_textos.py`, `tests/test_empaquetar.py`, `tests/test_guia.py` (nuevo) | Tests |
| `.env.ejemplo`, `README.md`, `EMPEZAR_EN_OTRA_MAQUINA.md`, `empaquetado/PROBAR.md`, `PROXIMOS_PASOS.md`, `VERSION` | Documentación y versión 0.2.0 |

Orden y dependencias: Tasks 1 a 7 son de código y no dependen de Bruno. Task 8 (capturas de la app) necesita la canción de ejemplo de Bruno en `empaquetado/ejemplos/canciones/<nombre>/` y cinco minutos de Bruno tocando; Task 9 necesita sus capturas de Band-in-a-Box en `empaquetado/capturas/bandinabox/` con `notas.txt`. Tasks 8 y 10 las hace el controlador (la sesión principal) con el navegador y con Bruno, no un subagente.

---

### Task 1: `registro.txt` sin tracebacks de conexiones cortadas

En la instalada, cada vez que el navegador corta una conexión (cierra una pestaña, cancela un pedido), `socketserver` escribe un traceback de `ConnectionAbortedError` en `registro.txt`. No es un error y tapa los de verdad.

**Files:**
- Modify: `armonica/servidor.py` (imports; clase `ServidorExclusivo`, ~línea 3007)
- Test: `tests/test_servidor.py` (al final del archivo)

**Interfaces:**
- Produces: `ServidorExclusivo.handle_error(self, request, client_address)`: si la excepción en curso es un `ConnectionError` (abarca `ConnectionAbortedError`, `ConnectionResetError`, `BrokenPipeError`) no escribe nada; cualquier otra, lo de siempre (`super().handle_error`).

- [ ] **Step 1: Escribir el test que falla**

Al final de `tests/test_servidor.py`:

```python
def test_un_corte_del_navegador_no_llena_el_registro(capsys):
    """
    El navegador corta conexiones todo el tiempo: cierra una pestaña, cancela
    un pedido. socketserver lo escribía como un traceback en registro.txt, y
    en la instalada eso tapaba los errores de verdad.
    """
    instancia = servidor.ServidorExclusivo(("127.0.0.1", 0), servidor.Manejador)
    try:
        for corte in (ConnectionAbortedError(10053, "anulada"), ConnectionResetError(),
                      BrokenPipeError()):
            try:
                raise corte
            except ConnectionError:
                instancia.handle_error(None, ("127.0.0.1", 50000))
        assert capsys.readouterr().err == ""

        try:
            raise ValueError("esto sí es un error")
        except ValueError:
            instancia.handle_error(None, ("127.0.0.1", 50000))
        assert "ValueError" in capsys.readouterr().err
    finally:
        instancia.server_close()
```

- [ ] **Step 2: Correrlo y ver que falla**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py::test_un_corte_del_navegador_no_llena_el_registro -v`
Expected: FAIL en el primer `assert` (el err trae "Exception occurred during processing of request").

- [ ] **Step 3: Implementar**

En `armonica/servidor.py`, agregar `import sys` en el bloque de imports de la biblioteca estándar (orden alfabético, después de `import socket`). En la clase `ServidorExclusivo`, después de `server_bind`:

```python
    def handle_error(self, request, client_address):
        """
        Una conexión cortada no es un error: el navegador corta cada vez que
        se cierra una pestaña o se cancela un pedido. socketserver la
        escribiría como un traceback, y en la instalada eso va a
        registro.txt y tapa los errores de verdad. Las demás, como siempre.
        """
        tipo = sys.exc_info()[0]
        if tipo is not None and issubclass(tipo, ConnectionError):
            return
        super().handle_error(request, client_address)
```

- [ ] **Step 4: Correr el test y la suite del servidor**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -q`
Expected: todo PASS (salvo el de Ollama en la carpeta de Bruno, ver Global Constraints).

- [ ] **Step 5: Commit**

```bash
git add armonica/servidor.py tests/test_servidor.py
git commit -m "El servidor no escribe en el registro las conexiones que corta el navegador, que en la instalada tapaban los errores de verdad." -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 2: El coach les habla por HTTP a Claude, ChatGPT y Gemini

Claude deja el paquete `anthropic` y habla por HTTP; ChatGPT pasa al modelo vigente y al parámetro que acepta; Gemini es nuevo. Los errores HTTP se traducen en un solo lugar, y los motivos que hablan de la clave mandan al `.env` (Bruno) o a Ajustes (la instalada).

**Files:**
- Modify: `armonica/coach.py` (docstring del módulo; constantes; `estado`; `_pedir`; `_pedir_a_claude`, `_pedir_a_openai`; funciones nuevas `_motivo_de_la_clave`, `_motivo_del_error`, `_pedir_por_http`, `_pedir_a_gemini`; `_http_json`)
- Modify: `armonica/servidor.py` (`arrancar`: `coach.CLAVE_EN_AJUSTES = empaquetada`)
- Modify: `tests/conftest.py` (fixture automática), `tests/test_coach.py`
- Modify: `.env.ejemplo`, `README.md` (tabla de proveedores, ~línea 556), `EMPEZAR_EN_OTRA_MAQUINA.md` (el paso `pip install anthropic`, ~líneas 86-97)

**Interfaces:**
- Consumes: `_http_json(url, cuerpo, cabeceras, segundos)` y `_texto_o_error(texto)` (existen).
- Produces:
  - `PROVEEDORES = ("claude", "ollama", "openai", "gemini")`; `PROVEEDORES_CON_CLAVE = ("claude", "openai", "gemini")`; `NOMBRES = {"claude": "Claude", "ollama": "Ollama", "openai": "ChatGPT", "gemini": "Gemini"}`.
  - `MODELOS_POR_DEFECTO`: claude `claude-opus-5-5`, ollama `qwen2.5:7b`, openai `gpt-6-luna`, gemini `gemini-3.5-flash-lite`. `URLS_POR_DEFECTO`: claude `https://api.anthropic.com/v1`, ollama `http://localhost:11434`, openai `https://api.openai.com/v1`, gemini `https://generativelanguage.googleapis.com/v1beta`.
  - `MAXIMO_DE_TOKENS_CON_PENSAMIENTO = 8000`; `VERSION_DE_LA_API_DE_CLAUDE = "2023-06-01"`; `SEGUNDOS_DE_ESPERA = {"claude": 90, "ollama": 240, "openai": 90, "gemini": 90}`.
  - `CLAVE_EN_AJUSTES = False` (lo pone `servidor.arrancar`); `_motivo_de_la_clave(cual, proveedor="claude") -> str` con `cual` en `"falta"`, `"invalida"`.
  - Un `CoachNoDisponible` levantado por `_http_json` ante un error HTTP lleva `codigo` (int) y `detalle` (el cuerpo de la respuesta de error, hasta 2000 caracteres).
  - `_pedir_a_gemini(conf, sistema, usuario) -> str`.

- [ ] **Step 1: La fixture que deja los motivos de Bruno**

Al final de `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def coach_como_en_la_maquina_de_bruno(monkeypatch):
    """
    Los motivos del coach hablan del .env, como en la máquina de Bruno. La
    versión instalada los cambia por "Ajustes" (servidor.arrancar); el test
    que pruebe eso lo prende a mano, y acá vuelve a apagarse.
    """
    from armonica import coach
    monkeypatch.setattr(coach, "CLAVE_EN_AJUSTES", False)
```

(Falla hasta el Step 4: `monkeypatch.setattr` exige que el atributo exista.)

- [ ] **Step 2: Escribir los tests que fallan**

En `tests/test_coach.py`, agregar arriba `import io` y `import urllib.error` (después de `import pytest`, en orden).

En `test_de_fabrica_es_claude_sin_clave`, la última línea:

```python
    assert conf["modelo"] == "claude-opus-5-5"
```

`test_cada_proveedor_tiene_su_modelo_y_su_direccion_por_defecto` queda:

```python
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
```

`test_un_proveedor_desconocido_se_explica` usa hoy `gemini` como proveedor desconocido: cambiarlo por `mistral` (en el `.env` y en el `assert`).

La fixture `http_falso` queda así (agrega el código y el detalle del error):

```python
@pytest.fixture
def http_falso(monkeypatch):
    """Reemplaza _http_json: guarda el pedido y contesta lo que se le diga."""
    registro = {"pedidos": [], "respuesta": None, "error": None, "codigo": None, "detalle": ""}

    def falso(url, cuerpo, cabeceras, segundos):
        registro["pedidos"].append({"url": url, "cuerpo": cuerpo,
                                    "cabeceras": cabeceras, "segundos": segundos})
        if registro["error"]:
            falla = coach.CoachNoDisponible(registro["error"])
            if registro["codigo"]:
                falla.codigo = registro["codigo"]
                falla.detalle = registro["detalle"]
            raise falla
        return registro["respuesta"]

    monkeypatch.setattr(coach, "_http_json", falso)
    return registro
```

`test_openai_manda_la_clave_en_la_cabecera` suma, al final:

```python
    # Los modelos de OpenAI que piensan rechazan max_tokens: el tope va en
    # max_completion_tokens, e incluye lo que piensan.
    assert "max_tokens" not in pedido["cuerpo"]
    assert pedido["cuerpo"]["max_completion_tokens"] >= 4000
    assert pedido["cuerpo"]["reasoning_effort"] == "low"
```

Y una sección nueva después de `test_una_respuesta_vacia_es_un_error_y_no_un_texto_vacio`:

```python
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


def test_sin_conexion_lo_dice(sin_entorno, tmp_path, http_falso):
    ruta = env_con(tmp_path, "LLM_CLAVE=sk-ant-prueba\n")
    http_falso["error"] = "No hay conexión con el servicio (sin red)."
    with pytest.raises(coach.CoachNoDisponible) as error:
        coach._pedir("s", "u", ruta)
    assert "conexión" in str(error.value)


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
```

- [ ] **Step 3: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_coach.py -q`
Expected: ERROR (la fixture de conftest: no existe `coach.CLAVE_EN_AJUSTES`). Después del Step 4, ninguno falla.

- [ ] **Step 4: Implementar en `armonica/coach.py`**

1. Docstring del módulo: "TRES PROVEEDORES" pasa a "CUATRO PROVEEDORES", y la lista queda:

```
    claude   la API de Claude (Anthropic). Es el de por defecto. Pide una
             clave. Cuesta centavos.
    ollama   un modelo LOCAL, corriendo en tu propia máquina con Ollama.
             No pide clave ni paquete ni internet. Pide una placa de video
             decente para que conteste en segundos y no en minutos.
    openai   la API de ChatGPT, para quien ya tiene una clave de ahí.
    gemini   la API de Gemini (Google). La clave de Google AI Studio es
             gratis, con un tope por día.

A los cuatro se les habla por HTTP con la biblioteca estándar, sin
paquetes: la versión instalada no los trae, y sumarlos agregaría
bibliotecas compiladas sin firma que Windows puede bloquear.
```

Y "Agregar un cuarto proveedor" pasa a "Agregar otro proveedor".

2. Constantes (reemplazan las de hoy):

```python
PROVEEDORES = ("claude", "ollama", "openai", "gemini")
PROVEEDOR_POR_DEFECTO = "claude"

# Los que piden clave (Ollama no: corre en la máquina).
PROVEEDORES_CON_CLAVE = ("claude", "openai", "gemini")

# Cómo se llama cada uno en pantalla.
NOMBRES = {"claude": "Claude", "ollama": "Ollama", "openai": "ChatGPT", "gemini": "Gemini"}

# El modelo de cada proveedor si no se elige otro con LLM_MODELO. Vigentes
# al 2026-10-04: la versión instalada no se actualiza sola, así que si uno
# se retira, el coach dice que hace falta una versión nueva de la app.
#
# Para Ollama va un modelo de 7 mil millones de parámetros: entra entero en
# una placa de 8 GB y contesta en pocos segundos. Qwen 2.5 habla bien
# castellano; llama3.1:8b es la alternativa. Uno más grande (14B) ya no
# entra en 8 GB y pasa a contestar en minutos. De ChatGPT y Gemini, los
# más baratos: alcanzan para explicar números ya medidos.
MODELOS_POR_DEFECTO = {
    "claude": "claude-opus-5-5",
    "ollama": "qwen2.5:7b",
    "openai": "gpt-6-luna",
    "gemini": "gemini-3.5-flash-lite",
}

URLS_POR_DEFECTO = {
    "claude": "https://api.anthropic.com/v1",
    "ollama": "http://localhost:11434",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}
```

Después de `MAXIMO_DE_TOKENS = 1500` (su comentario pasa a decir que es el de Ollama):

```python
# Los modelos de Claude, ChatGPT y Gemini piensan antes de contestar, y lo
# que piensan cuenta dentro del tope: con 1500 una respuesta podría cortarse
# antes de empezar. Este deja lugar para las dos cosas; la respuesta sigue
# siendo corta porque así lo pide SISTEMA.
MAXIMO_DE_TOKENS_CON_PENSAMIENTO = 8000

# La versión de la API de mensajes de Claude: va en cada pedido.
VERSION_DE_LA_API_DE_CLAUDE = "2023-06-01"
```

`SEGUNDOS_DE_ESPERA = {"claude": 90, "ollama": 240, "openai": 90, "gemini": 90}`.

Después de `ARCHIVO_ENV = ".env"`:

```python
# Si los motivos que hablan de la clave mandan a Ajustes (la versión
# instalada, que no tiene .env) o al .env (Bruno). Lo pone
# servidor.arrancar().
CLAVE_EN_AJUSTES = False
```

3. Los motivos, después de `configuracion`:

```python
def _motivo_de_la_clave(cual, proveedor="claude"):
    """
    Qué decir cuando falta la clave ("falta") o no es válida ("invalida").
    A Bruno lo manda al .env; al profe, a Ajustes.
    """
    if CLAVE_EN_AJUSTES:
        return {"falta": "Falta la clave. Pegala en Ajustes, en El coach.",
                "invalida": "La clave no es válida. Revisala en Ajustes, en El coach."}[cual]
    if cual == "falta":
        if proveedor == "claude":
            return "Falta la clave. Copiá .env.ejemplo a .env y poné la tuya en LLM_CLAVE."
        return f"Falta la clave de {NOMBRES[proveedor]}. Ponela en LLM_CLAVE en el .env."
    return f"La clave de {NOMBRES[proveedor]} no es válida. Revisá LLM_CLAVE en el .env."
```

4. `estado()`: el bloque de claude y el de openai se reemplazan por uno solo:

```python
    if conf["proveedor"] in PROVEEDORES_CON_CLAVE:
        if not conf["clave"]:
            return dict(base, disponible=False,
                        motivo=_motivo_de_la_clave("falta", conf["proveedor"]))
        return dict(base, disponible=True, motivo="")
```

5. `_pedir()` suma, antes del último `raise`:

```python
    if proveedor == "gemini":
        return _pedir_a_gemini(conf, sistema, usuario)
```

6. Los errores, en un solo lugar (antes de `_pedir_a_claude`):

```python
def _motivo_del_error(error, conf):
    """
    El motivo de un error HTTP de Claude, ChatGPT o Gemini, o None si no hay
    uno mejor que "El servicio contestó con un error (N)".
    """
    codigo = getattr(error, "codigo", None)
    detalle = getattr(error, "detalle", "") or ""
    # Gemini contesta 400, y no 401, a una clave que no es válida: se
    # reconoce por el motivo que viene en el cuerpo.
    if codigo == 401 or (codigo == 400 and "API_KEY_INVALID" in detalle):
        return _motivo_de_la_clave("invalida", conf["proveedor"])
    if codigo == 402:
        return "La cuenta de esa clave no tiene crédito."
    if codigo == 403:
        return "Esa clave no tiene permiso para usar el modelo."
    if codigo == 404:
        if CLAVE_EN_AJUSTES:
            return f"No existe el modelo {conf['modelo']!r}: hace falta una versión nueva de la app."
        return f"No existe el modelo {conf['modelo']!r}. Revisá LLM_MODELO en el .env."
    if codigo in (429, 529):
        return "El servicio está saturado, o la clave llegó a su tope de uso. Probá en un rato."
    return None


def _pedir_por_http(conf, url, cuerpo, cabeceras):
    """
    _http_json para un proveedor con clave, con los errores ya traducidos.
    Lo que contestó el servicio queda en el registro: en la instalada es lo
    único que Bruno puede mirar si el coach del profe no anda.
    """
    try:
        return _http_json(url, cuerpo, cabeceras,
                          segundos=SEGUNDOS_DE_ESPERA[conf["proveedor"]]) or {}
    except CoachNoDisponible as error:
        if getattr(error, "codigo", None):
            print(f"  El coach ({NOMBRES[conf['proveedor']]}) contestó {error.codigo}: "
                  f"{(getattr(error, 'detalle', '') or '')[:300]}")
        motivo = _motivo_del_error(error, conf)
        if motivo:
            raise CoachNoDisponible(motivo)
        raise
```

7. `_pedir_a_claude` entera:

```python
def _pedir_a_claude(conf, sistema, usuario):
    """La API de Claude, por HTTP."""
    if not conf["clave"]:
        raise CoachNoDisponible(_motivo_de_la_clave("falta", "claude"))
    cuerpo = {
        "model": conf["modelo"],
        "max_tokens": MAXIMO_DE_TOKENS_CON_PENSAMIENTO,
        "system": sistema,
        # Poco esfuerzo alcanza: no hay nada que deducir, solo explicar
        # números que ya están. Y es más barato y más rápido.
        "output_config": {"effort": "low"},
        "messages": [{"role": "user", "content": usuario}],
    }
    cabeceras = {"x-api-key": conf["clave"], "anthropic-version": VERSION_DE_LA_API_DE_CLAUDE}
    respuesta = _pedir_por_http(conf, conf["url"] + "/messages", cuerpo, cabeceras)
    if respuesta.get("stop_reason") == "refusal":
        raise CoachNoDisponible("El modelo no quiso contestar esto.")
    # El contenido es una lista de bloques: lo que pensó (vacío) y el texto.
    texto = "".join(bloque.get("text", "") for bloque in respuesta.get("content") or []
                    if isinstance(bloque, dict) and bloque.get("type") == "text")
    return _texto_o_error(texto)
```

8. `_pedir_a_openai` entera:

```python
def _pedir_a_openai(conf, sistema, usuario):
    """
    La API de ChatGPT (o cualquiera compatible: LM Studio, etc., cambiando
    LLM_URL). Por HTTP con la biblioteca estándar, sin paquete.

    Los modelos de ahora piensan antes de contestar: el tope va en
    max_completion_tokens (max_tokens lo rechazan) e incluye lo que piensan.
    """
    if not conf["clave"]:
        raise CoachNoDisponible(_motivo_de_la_clave("falta", "openai"))
    cuerpo = {
        "model": conf["modelo"],
        "max_completion_tokens": MAXIMO_DE_TOKENS_CON_PENSAMIENTO,
        # Poco esfuerzo alcanza, como con Claude: solo explica números.
        "reasoning_effort": "low",
        "messages": [{"role": "system", "content": sistema},
                     {"role": "user", "content": usuario}],
    }
    respuesta = _pedir_por_http(conf, conf["url"] + "/chat/completions", cuerpo,
                                {"Authorization": "Bearer " + conf["clave"]})
    opciones = respuesta.get("choices") or [{}]
    return _texto_o_error(((opciones[0].get("message") or {}).get("content") or ""))
```

9. `_pedir_a_gemini`, nueva, después de `_pedir_a_openai`:

```python
def _pedir_a_gemini(conf, sistema, usuario):
    """
    La API de Gemini (Google), por su forma propia: generateContent con la
    clave en x-goog-api-key. No por su versión compatible con OpenAI: ahí
    la clave va en Authorization: Bearer, que puede rechazar las claves
    nuevas de Google (empiezan con "AQ."). Así andan las nuevas y las
    viejas ("AIza").
    """
    if not conf["clave"]:
        raise CoachNoDisponible(_motivo_de_la_clave("falta", "gemini"))
    cuerpo = {
        "system_instruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user", "parts": [{"text": usuario}]}],
        "generationConfig": {
            # Incluye lo que el modelo piensa antes de contestar.
            "maxOutputTokens": MAXIMO_DE_TOKENS_CON_PENSAMIENTO,
            # Poco, como con los otros. Es el campo de los modelos Gemini 3;
            # uno 2.5 puesto en LLM_MODELO lo rechazaría.
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    url = f"{conf['url']}/models/{conf['modelo']}:generateContent"
    respuesta = _pedir_por_http(conf, url, cuerpo, {"x-goog-api-key": conf["clave"]})
    candidatos = respuesta.get("candidates") or []
    if not candidatos:
        if (respuesta.get("promptFeedback") or {}).get("blockReason"):
            raise CoachNoDisponible("El modelo no quiso contestar esto.")
        raise CoachNoDisponible("El modelo devolvió una respuesta vacía.")
    if candidatos[0].get("finishReason") == "SAFETY":
        raise CoachNoDisponible("El modelo no quiso contestar esto.")
    partes = (candidatos[0].get("content") or {}).get("parts") or []
    # Las partes marcadas "thought" son lo que pensó: no van.
    texto = "".join(parte.get("text", "") for parte in partes
                    if isinstance(parte, dict) and not parte.get("thought"))
    return _texto_o_error(texto)
```

10. En `_http_json`, el docstring dice "Es la única función que toca la red para Claude, Ollama, OpenAI y Gemini", y el `except urllib.error.HTTPError` queda:

```python
    except urllib.error.HTTPError as error:
        # El código y el cuerpo van aparte: quien llama elige el motivo sin
        # buscar números en el texto, y Gemini dice en el cuerpo si lo que
        # falló es la clave.
        falla = CoachNoDisponible(f"El servicio contestó con un error ({error.code}).")
        falla.codigo = error.code
        try:
            falla.detalle = error.read().decode("utf-8", "replace")[:2000]
        except (OSError, AttributeError, ValueError):
            falla.detalle = ""
        raise falla
```

- [ ] **Step 5: `servidor.arrancar` avisa si es la instalada**

En `armonica/servidor.py`, en `arrancar`, después de `Manejador.empaquetada = empaquetada`:

```python
    coach.CLAVE_EN_AJUSTES = empaquetada
```

- [ ] **Step 6: La documentación de Bruno**

- `.env.ejemplo`: el encabezado de la opción 1 queda `# 1. Claude (el de por defecto). Pide una clave.` (sin `pip install anthropic`) y su línea de modelo `# LLM_MODELO=claude-opus-5-5      # o claude-sonnet-5-5, mas barato`. En la opción 3, `# LLM_MODELO=gpt-6-luna`. Y una opción 4 al final, con el mismo formato que las otras:

```
# ---------------------------------------------------------------------------
# 4. Gemini (Google). La clave de https://aistudio.google.com/ es gratis,
#    con un tope por dia (en la version gratis, Google puede usar lo que se
#    le manda para mejorar sus productos).
# ---------------------------------------------------------------------------
# LLM_PROVEEDOR=gemini
# LLM_CLAVE=
# LLM_MODELO=gemini-3.5-flash-lite
```

- `README.md`, tabla de proveedores: "Qué pide" de Claude queda `una clave de console.anthropic.com`; ChatGPT, `una clave de platform.openai.com (no alcanza con la suscripción a ChatGPT)`; y una fila nueva `| **Gemini** | una clave de aistudio.google.com | gratis con un tope por día |`. Si el párrafo de arriba dice "uno de tres proveedores", pasa a cuatro.
- `EMPEZAR_EN_OTRA_MAQUINA.md`: sacar el bloque `pip install anthropic` y dejar "en el `.env` dejá `LLM_PROVEEDOR=claude` y pegá tu clave de https://console.anthropic.com/ en `LLM_CLAVE`."

- [ ] **Step 7: Correr toda la suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (salvo los de entorno de Bruno). `test_sin_clave_claude_no_intenta_conectarse` y `test_sin_clave_el_coach_se_declara_apagado` siguen pasando: el motivo de Bruno sigue nombrando `.env`.

- [ ] **Step 8: Commit**

```bash
git add armonica/coach.py armonica/servidor.py tests/conftest.py tests/test_coach.py .env.ejemplo README.md EMPEZAR_EN_OTRA_MAQUINA.md
git commit -m "El coach les habla por HTTP a Claude, ChatGPT y Gemini con los modelos vigentes, y en la versión instalada sus motivos mandan a Ajustes." -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 3: La clave del coach, reconocida, guardada en `%LOCALAPPDATA%\Armonica` y probada

**Files:**
- Modify: `armonica/coach.py` (docstring; constantes nuevas; `ruta_de_la_clave`, `proveedor_de_la_clave`, `guardar_clave`, `probar`; `configuracion`; `estado`)
- Modify: `armonica/servidor.py` (`do_POST`: ruta `/api/coach/clave`; método `_guardar_clave_del_coach`)
- Modify: `tests/conftest.py` (la fixture de la Task 2)
- Test: `tests/test_coach.py`, `tests/test_servidor.py`

**Interfaces:**
- Consumes: `_pedir(sistema, usuario, ruta_env=None)`, `PROVEEDORES_CON_CLAVE`, `NOMBRES` (Task 2).
- Produces:
  - `coach.ARCHIVO_CLAVE = None` (None = `%LOCALAPPDATA%\Armonica\coach.env`); `coach.ruta_de_la_clave() -> str`.
  - `coach.proveedor_de_la_clave(clave: str) -> str | None`: `"claude"`, `"openai"`, `"gemini"` o None.
  - `coach.guardar_clave(clave: str) -> str`: guarda `LLM_PROVEEDOR=<proveedor>` y `LLM_CLAVE=<clave>` (atómico) y devuelve el proveedor; con `""` borra el archivo y devuelve `""`; si no parece una clave o no se reconoce, `ValueError` con un motivo para mostrar, sin tocar nada.
  - `coach.probar(ruta_env=None) -> str`: un pedido mínimo; levanta `CoachNoDisponible` si no anda.
  - `coach.configuracion()`: cada valor sale del `.env`, si no de la clave guardada, si no del entorno.
  - `coach.estado()` suma `"clave_en_ajustes": bool` en todas sus respuestas.
  - `POST /api/coach/clave` con `{"clave": str}` → `{"ok": bool, "probada": bool, "proveedor"?: str, "motivo"?: str, "estado"?: dict}`. Nunca devuelve la clave.

- [ ] **Step 1: La fixture aísla la clave de verdad**

En `tests/conftest.py`, la fixture `coach_como_en_la_maquina_de_bruno` de la Task 2 queda:

```python
@pytest.fixture(autouse=True)
def coach_como_en_la_maquina_de_bruno(monkeypatch, tmp_path):
    """
    Los motivos del coach hablan del .env, como en la máquina de Bruno. La
    versión instalada los cambia por "Ajustes" (servidor.arrancar); el test
    que pruebe eso lo prende a mano, y acá vuelve a apagarse.

    Y la clave que se pega en Ajustes vive en %LOCALAPPDATA%\\Armonica:
    ningún test la lee ni la pisa. Cada uno tiene la suya, en una carpeta
    temporal que empieza vacía.
    """
    from armonica import coach
    monkeypatch.setattr(coach, "CLAVE_EN_AJUSTES", False)
    monkeypatch.setattr(coach, "ARCHIVO_CLAVE", str(tmp_path / "clave-del-coach" / "coach.env"))
```

(Falla hasta el Step 4: no existe `coach.ARCHIVO_CLAVE`.)

- [ ] **Step 2: Escribir los tests que fallan**

En `tests/test_coach.py` (agregar `import os` arriba si no está), una sección nueva al final:

```python
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
```

En `tests/test_servidor.py`, en la sección "El coach, desde la pantalla", después de `test_sin_clave_el_coach_se_declara_apagado`:

```python
@pytest.fixture
def coach_sin_env(monkeypatch, tmp_path):
    """El coach sin .env ni variables: solo lo que se pegue en Ajustes."""
    monkeypatch.setattr(coach, "ARCHIVO_ENV", str(tmp_path / "no-existe.env"))
    for nombre in ("LLM_PROVEEDOR", "LLM_CLAVE", "LLM_MODELO", "LLM_URL",
                   "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(nombre, raising=False)


def test_la_clave_pegada_en_ajustes_se_guarda_y_se_prueba(servidor_andando, coach_sin_env,
                                                          monkeypatch):
    pedidos = []
    monkeypatch.setattr(coach, "_pedir",
                        lambda sistema, usuario, ruta_env=None: pedidos.append(usuario) or "listo")

    respuesta = mandar(servidor_andando, "/api/coach/clave", {"clave": "AQ.Ab-prueba_123"})

    assert respuesta["ok"] is True and respuesta["probada"] is True
    assert respuesta["proveedor"] == "gemini"
    assert respuesta["estado"]["disponible"] is True
    assert respuesta["estado"]["clave_en_ajustes"] is True
    assert respuesta["estado"]["proveedor"] == "gemini"
    assert len(pedidos) == 1
    # La clave no vuelve nunca al navegador.
    assert "AQ.Ab-prueba_123" not in json.dumps(respuesta)
    assert "AQ.Ab-prueba_123" not in json.dumps(traer_json(servidor_andando, "/api/coach"))


def test_una_clave_que_no_anda_queda_guardada_y_dice_por_que(servidor_andando, coach_sin_env,
                                                             monkeypatch):
    def no_anda(sistema, usuario, ruta_env=None):
        raise coach.CoachNoDisponible("No hay conexión con el servicio. ¿Estás sin internet?")

    monkeypatch.setattr(coach, "_pedir", no_anda)

    respuesta = mandar(servidor_andando, "/api/coach/clave", {"clave": "sk-ant-prueba_123"})

    assert respuesta["ok"] is True and respuesta["probada"] is False
    assert respuesta["proveedor"] == "claude"
    assert "internet" in respuesta["motivo"]
    assert respuesta["estado"]["clave_en_ajustes"] is True


def test_una_clave_que_no_se_reconoce_no_se_guarda(servidor_andando, coach_sin_env):
    for mala in ("sk-ant con espacios", "desconocida-abcdefghij"):
        respuesta = mandar(servidor_andando, "/api/coach/clave", {"clave": mala})
        assert respuesta["ok"] is False
        assert respuesta["motivo"]
    assert traer_json(servidor_andando, "/api/coach")["clave_en_ajustes"] is False


def test_la_clave_se_borra_mandandola_vacia(servidor_andando, coach_sin_env, monkeypatch):
    monkeypatch.setattr(coach, "_pedir", lambda sistema, usuario, ruta_env=None: "listo")
    mandar(servidor_andando, "/api/coach/clave", {"clave": "sk-proj-prueba_123"})

    respuesta = mandar(servidor_andando, "/api/coach/clave", {"clave": ""})

    assert respuesta["ok"] is True and respuesta["probada"] is False
    assert respuesta["estado"]["clave_en_ajustes"] is False
    assert respuesta["estado"]["disponible"] is False


def test_sin_clave_en_el_pedido_es_un_error(servidor_andando, coach_sin_env):
    assert mandar(servidor_andando, "/api/coach/clave", {})["ok"] is False
```

- [ ] **Step 3: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_coach.py tests/test_servidor.py -q`
Expected: ERROR (la fixture no encuentra `coach.ARCHIVO_CLAVE`).

- [ ] **Step 4: Implementar en `armonica/coach.py`**

En el docstring del módulo, el párrafo "Es OPCIONAL…" suma que en la versión instalada no hay `.env`: la clave se pega en Ajustes, la app reconoce de qué proveedor es y la guarda en `%LOCALAPPDATA%\Armonica\coach.env`.

Agregar `import re` a los imports. Después de `CLAVE_EN_AJUSTES`:

```python
# La clave que se pega en Ajustes: la versión instalada no tiene .env. Va a
# %LOCALAPPDATA%\Armonica, que es de esta computadora, y no a Documentos,
# que puede estar subida a OneDrive. None quiere decir esa ruta; los tests
# la cambian por una temporal (conftest.py) y así nunca tocan la de verdad.
ARCHIVO_CLAVE = None

# Una clave: letras, números, guiones, guiones bajos y puntos. Nada de
# espacios ni saltos de línea: escrita en el archivo, un salto de línea
# agregaría otra configuración.
PATRON_DE_CLAVE = re.compile(r"[A-Za-z0-9_.\-]{10,300}")

# De quién es una clave, por cómo empieza. El orden importa: las de Claude
# también empiezan con "sk-". Las de Gemini son "AIza…" (las de antes) o
# "AQ.…" (las que da Google AI Studio desde 2026).
PREFIJOS_DE_CLAVE = (("sk-ant-", "claude"), ("sk-", "openai"),
                     ("AIza", "gemini"), ("AQ.", "gemini"))
```

Después de `leer_env`:

```python
def ruta_de_la_clave():
    """Dónde está la clave que se pegó en Ajustes."""
    if ARCHIVO_CLAVE:
        return ARCHIVO_CLAVE
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"),
                                                          "AppData", "Local")
    return os.path.join(base, "Armonica", "coach.env")


def proveedor_de_la_clave(clave):
    """De quién es una clave ("claude", "openai", "gemini"), o None."""
    for prefijo, proveedor in PREFIJOS_DE_CLAVE:
        if clave.startswith(prefijo):
            return proveedor
    return None


def guardar_clave(clave):
    """
    Guarda la clave que se pegó en Ajustes, con su proveedor, o la borra si
    viene vacía. Devuelve el proveedor ("" si se borró). Si no parece una
    clave, o no es de ninguno de los tres, es un ValueError con un motivo
    para mostrar, y no se toca nada.
    """
    clave = (clave or "").strip()
    ruta = ruta_de_la_clave()
    if not clave:
        if os.path.exists(ruta):
            os.remove(ruta)
        return ""
    proveedor = proveedor_de_la_clave(clave)
    if not PATRON_DE_CLAVE.fullmatch(clave) or proveedor is None:
        raise ValueError("No reconozco esa clave. Sirven las de Claude, ChatGPT o Gemini: "
                         "pegala de nuevo, entera y sin espacios.")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    # A un temporal y después se reemplaza, como ajustes.json: si algo corta
    # el guardado, queda la clave de antes entera.
    temporal = ruta + ".tmp"
    try:
        with open(temporal, "w", encoding="utf-8") as archivo:
            archivo.write(f"LLM_PROVEEDOR={proveedor}\nLLM_CLAVE={clave}\n")
        os.replace(temporal, ruta)
    except BaseException:
        if os.path.exists(temporal):
            os.remove(temporal)
        raise
    return proveedor
```

`configuracion` queda (docstring incluido):

```python
def configuracion(ruta_env=None):
    """
    Qué proveedor, con qué clave, qué modelo y en qué dirección.

    Devuelve un diccionario {"proveedor", "clave", "modelo", "url"}. Cada
    valor sale del .env; si no está, de la clave pegada en Ajustes; si no,
    de las variables de entorno. La variable ANTHROPIC_API_KEY también sirve
    como clave: si ya la tenés puesta por otra cosa, no hace falta más.
    """
    fuentes = (leer_env(ruta_env), leer_env(ruta_de_la_clave()))

    def valor(nombre, *alternativas):
        for fuente in fuentes:
            for candidato in (nombre,) + alternativas:
                if fuente.get(candidato):
                    return fuente[candidato].strip()
        for candidato in (nombre,) + alternativas:
            if os.environ.get(candidato):
                return os.environ[candidato].strip()
        return ""

    proveedor = (valor("LLM_PROVEEDOR") or PROVEEDOR_POR_DEFECTO).lower()
    return {
        "proveedor": proveedor,
        "clave": valor("LLM_CLAVE", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"),
        "modelo": valor("LLM_MODELO") or MODELOS_POR_DEFECTO.get(proveedor, ""),
        "url": (valor("LLM_URL") or URLS_POR_DEFECTO.get(proveedor, "")).rstrip("/"),
    }
```

En `estado`, la base suma si hay una clave pegada:

```python
    conf = configuracion(ruta_env)
    base = {"proveedor": conf["proveedor"], "modelo": conf["modelo"],
            "clave_en_ajustes": bool(leer_env(ruta_de_la_clave()).get("LLM_CLAVE"))}
```

Y antes de la sección "La llamada":

```python
def probar(ruta_env=None):
    """
    Un pedido mínimo para ver si la clave anda: Ajustes lo hace al guardarla.
    Devuelve el texto, o levanta CoachNoDisponible con el motivo. Cuesta una
    fracción de centavo.
    """
    return _pedir("Contestá solo con la palabra: listo.", "¿Me escuchás?", ruta_env)
```

- [ ] **Step 5: Implementar en `armonica/servidor.py`**

En `do_POST`, junto a las otras rutas del coach:

```python
        if self.path == "/api/coach/clave":
            return self._responder_json(self._guardar_clave_del_coach(cuerpo))
```

En la sección `# --- El coach ---`, después de `_estado_del_coach`:

```python
    def _guardar_clave_del_coach(self, peticion):
        """
        Ajustes → El coach: guarda la clave pegada (o la borra si viene
        vacía) y, si quedó una, la prueba con un pedido mínimo. Si la prueba
        falla la clave queda igual (puede ser que justo no haya internet) y
        se dice por qué. La clave no vuelve nunca al navegador.
        """
        clave = (peticion or {}).get("clave")
        if not isinstance(clave, str):
            return {"ok": False, "motivo": "Falta la clave."}
        try:
            proveedor = coach.guardar_clave(clave)
        except ValueError as error:
            return {"ok": False, "motivo": str(error)}
        except OSError as error:
            return {"ok": False, "motivo": f"No pude guardar la clave ({error.strerror or error})."}
        if not proveedor:
            return {"ok": True, "probada": False, "estado": coach.estado()}
        try:
            coach.probar()
        except coach.CoachNoDisponible as error:
            return {"ok": True, "probada": False, "proveedor": proveedor,
                    "motivo": str(error), "estado": coach.estado()}
        return {"ok": True, "probada": True, "proveedor": proveedor, "estado": coach.estado()}
```

- [ ] **Step 6: Correr toda la suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (salvo los de entorno de Bruno). Si algún test de `test_servidor.py` compara el diccionario de `/api/coach` entero, se le agrega `clave_en_ajustes`.

- [ ] **Step 7: Commit**

```bash
git add armonica/coach.py armonica/servidor.py tests/conftest.py tests/test_coach.py tests/test_servidor.py
git commit -m "La clave del coach se pega en Ajustes: la app reconoce si es de Claude, ChatGPT o Gemini, la guarda en LOCALAPPDATA, la prueba y nunca la devuelve al navegador." -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 4: El coach en Ajustes de la versión instalada

**Files:**
- Modify: `armonica/web/index.html` (la sección "El coach" de Ajustes, ~líneas 439-449)
- Modify: `armonica/web/app.js` (arranque ~línea 36; `mostrarEstadoDelCoach` ~línea 2646; `nombreDelProveedor` ~línea 4234; función nueva `configurarClaveDelCoach`)
- Test: `tests/test_textos.py`

**Interfaces:**
- Consumes: `POST /api/coach/clave` (con `proveedor`), `estado.clave_en_ajustes`, `estado.proveedor` (Task 3); `esLaInstalada()`, `pedir()`, `escapar()`, `cargarEstadoDelCoach()` (existen en app.js).
- Produces: en la instalada, Ajustes muestra el campo `#coach-clave`, los botones `#coach-guardar-clave` y `#coach-borrar-clave` y el renglón `#coach-resultado-clave`; `#estado-coach` se ve en los dos modos; `nombreDelProveedor("gemini") === "Gemini"`.

- [ ] **Step 1: Escribir el test que falla**

Al final de `tests/test_textos.py`:

```python
def test_la_clave_del_coach_se_pega_en_la_version_instalada():
    """
    El profe activa el coach pegando una clave en Ajustes: el campo y los
    botones no pueden quedar adentro de algo solo para Bruno.
    """
    with open(INDEX, encoding="utf-8") as archivo:
        html = archivo.read()
    # El campo es un <input>, que ClasesDeUnElemento saltea (no tiene cierre):
    # se lo busca como texto, y sus clases son las de los botones de al lado.
    assert 'id="coach-clave"' in html
    for id_ in ("coach-guardar-clave", "coach-borrar-clave",
                "coach-resultado-clave", "estado-coach"):
        lector = ClasesDeUnElemento(id_)
        lector.feed(html)
        assert lector.encontrado, f"no está #{id_}"
        assert "solo-desarrollo" not in lector.clases_en_la_cadena, f"#{id_} no se ve en la instalada"
```

- [ ] **Step 2: Correrlo y ver que falla**

Run: `.venv/Scripts/python.exe -m pytest tests/test_textos.py -v`
Expected: FAIL en `assert 'id="coach-clave"' in html`.

- [ ] **Step 3: Implementar el HTML**

Reemplazar la sección `<section class="solo-desarrollo"> <h2>El coach</h2> … </section>` de Ajustes por:

```html
  <section>
    <h2>El coach</h2>
    <p class="ayuda solo-desarrollo">
      Un modelo de lenguaje que explica lo que la app midió: recibe los
      números ya calculados y los cuenta como lo haría un profe. Nunca mide
      nada, y el audio no sale de tu máquina. Es opcional: se activa con una
      clave tuya en un archivo <code>.env</code> (mirá <code>.env.ejemplo</code>)
      y reiniciando la app.
    </p>
    <div class="solo-empaquetada">
      <p class="ayuda">
        Un asistente que explica en palabras lo que la app midió: por qué una
        nota salió baja, cómo practicar un cambio de acorde. Nunca mide nada:
        recibe los números que la app ya calculó. Necesita internet y una
        clave de Claude, ChatGPT o Gemini, que se pega acá una sola vez y
        queda guardada en esta computadora. Lo que le pregunta (números y
        texto, nunca el audio) sale de la computadora hacia la empresa de esa
        clave: Anthropic, OpenAI o Google.
      </p>
      <div class="controles">
        <input id="coach-clave" type="password" autocomplete="off" spellcheck="false"
               maxlength="300" placeholder="pegá la clave acá">
        <button id="coach-guardar-clave" class="principal">Guardar y probar</button>
        <button id="coach-borrar-clave" class="secundario" hidden>Borrar la clave</button>
      </div>
      <p id="coach-resultado-clave" class="ayuda"></p>
    </div>
    <p id="estado-coach" class="ayuda"></p>
  </section>
```

- [ ] **Step 4: Implementar el JS**

En el arranque (`DOMContentLoaded`), después de `configurarLaApp();`:

```js
  configurarClaveDelCoach();
```

`nombreDelProveedor` queda:

```js
function nombreDelProveedor(clave) {
  return { claude: "Claude", ollama: "Ollama (local)", openai: "ChatGPT", gemini: "Gemini" }[clave] ||
    clave || "el coach";
}
```

`mostrarEstadoDelCoach` queda:

```js
/* La solapa Ajustes: si el coach esta activo, y si no, como activarlo. */
async function mostrarEstadoDelCoach() {
  const datos = await cargarEstadoDelCoach();
  const donde = document.getElementById("estado-coach");
  if (!donde) return;
  document.getElementById("coach-borrar-clave").hidden = !datos.clave_en_ajustes;
  const proveedor = datos.proveedor ? nombreDelProveedor(datos.proveedor) : "";
  donde.className = "ayuda";
  if (datos.disponible && esLaInstalada()) {
    donde.innerHTML = "<strong>Activo</strong>, con " + escapar(proveedor) + ". Vas a ver el " +
      "botón del coach al pie de la devolución de una práctica, una pregunta libre al pie de " +
      "Teoría y, en Canciones, un botón para que te explique la base.";
  } else if (datos.disponible) {
    donde.innerHTML = "<strong>Activo</strong>: " + escapar(proveedor) + ", modelo <code>" +
      escapar(datos.modelo) + "</code>. Vas a ver el botón del coach al pie de la " +
      "devolución de una práctica, y una pregunta libre al pie de Teoría." +
      (datos.proveedor === "ollama"
        ? " Con un modelo local la primera respuesta tarda más: está cargando el modelo."
        : "");
  } else if (esLaInstalada()) {
    donde.innerHTML = "<strong>Apagado.</strong> " + escapar(datos.motivo);
  } else {
    donde.innerHTML = "<strong>Apagado</strong>" + (proveedor ? " (" + escapar(proveedor) + ")" : "") +
      ". " + escapar(datos.motivo);
  }
}


/* Ajustes → El coach, en la version instalada: pegar la clave, guardarla y
 * probarla, o borrarla. La clave va al servidor y no vuelve: el campo se
 * vacia siempre. */
function configurarClaveDelCoach() {
  const campo = document.getElementById("coach-clave");
  const resultado = document.getElementById("coach-resultado-clave");

  const guardar = async (clave) => {
    resultado.textContent = clave ? "Guardando y probando\u2026" : "Borrando\u2026";
    const respuesta = await pedir("/api/coach/clave", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clave: clave }),
    });
    campo.value = "";
    if (!respuesta.ok) {
      resultado.textContent = respuesta.motivo || "No se pudo guardar la clave.";
      return;
    }
    const de = respuesta.proveedor ? "de " + nombreDelProveedor(respuesta.proveedor) : "";
    if (!clave) {
      resultado.textContent = "Listo: la clave se borr\u00f3. El coach queda apagado.";
    } else if (respuesta.probada) {
      resultado.textContent = "Listo: es una clave " + de + " y anda. Ya pod\u00e9s usar el coach.";
    } else {
      resultado.textContent = "La clave " + de + " qued\u00f3 guardada, pero al probarla: " +
        respuesta.motivo;
    }
    await mostrarEstadoDelCoach();
  };

  document.getElementById("coach-guardar-clave").addEventListener("click", () => {
    const clave = campo.value.trim();
    if (!clave) {
      resultado.textContent = "Peg\u00e1 la clave en el casillero primero.";
      return;
    }
    guardar(clave);
  });
  campo.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter") document.getElementById("coach-guardar-clave").click();
  });
  document.getElementById("coach-borrar-clave").addEventListener("click", () => {
    if (confirm("\u00bfBorrar la clave? El coach queda apagado hasta que pegues otra.")) guardar("");
  });
}
```

- [ ] **Step 5: Correr los tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_textos.py -q`
Expected: PASS (incluido `test_la_pagina_instalada_no_muestra_jerga`: el `.env` quedó adentro del `<p class="ayuda solo-desarrollo">`).

- [ ] **Step 6: Probarlo en el navegador**

Sin claves reales. Levantar la instalada desde el repo con datos temporales (PowerShell):

```powershell
$env:ARMONICA_DATOS = Join-Path $env:TEMP "armonica-prueba-coach"; $env:ARMONICA_SIN_NAVEGADOR = "1"
Start-Process .\.venv\Scripts\pythonw.exe -ArgumentList "lanzador.pyw"
```

Abrir `http://127.0.0.1:8000`, Ajustes. Verificar: se ve "El coach" con el campo; "Guardar y probar" vacío avisa "Pegá la clave…"; `desconocida-abcdefghij` dice "No reconozco esa clave…"; `AQ.falsa-123456789` dice "La clave de Gemini quedó guardada, pero al probarla: …" con el motivo que dé Google, y aparece "Borrar la clave"; "Borrar la clave" la borra y vuelve a "Apagado. Falta la clave. Pegala en Ajustes, en El coach." Cerrar con Ajustes → Cerrar la app y borrar `%LOCALAPPDATA%\Armonica\coach.env` si quedó. (Si el implementador no tiene navegador, lo verifica el controlador en la Task 8.)

- [ ] **Step 7: Commit**

```bash
git add armonica/web/index.html armonica/web/app.js tests/test_textos.py
git commit -m "Ajustes de la versión instalada tiene El coach: se pega una clave de Claude, ChatGPT o Gemini, se guarda y se prueba, o se borra." -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 5: Los íconos del instalador, y el desinstalador borra la clave

**Files:**
- Modify: `empaquetado/armonica.iss` (`[Tasks]`, `[Icons]`, `[UninstallDelete]`). El archivo es UTF-8 con BOM: mantenerlo.
- Test: `tests/test_empaquetar.py`

**Interfaces:**
- Consumes: la ruta de la clave de la Task 3 (`%LOCALAPPDATA%\Armonica\coach.env`).
- Produces: íconos `{group}\Armónica`, `{autodesktop}\Armónica` (sin pregunta) y `{userdocs}\Armonica\Abrir Armónica`; ninguna sección `[Tasks]`; el desinstalador borra `{localappdata}\Armonica\coach.env` y la carpeta si queda vacía. Las funciones de test `entradas_de_la_seccion(texto, seccion)` y `destinos_de_los_iconos(texto)` y la constante `ISS` las reusa la Task 7.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_empaquetar.py`: agregar `import re` a los imports, y después de los imports:

```python
RAIZ = Path(__file__).resolve().parent.parent
ISS = RAIZ / "empaquetado" / "armonica.iss"
```

Y al final:

```python
def entradas_de_la_seccion(texto, seccion):
    """Las líneas de una sección del .iss, sin comentarios ni vacías."""
    lineas, adentro = [], False
    for linea in texto.splitlines():
        limpia = linea.strip()
        if limpia.startswith("[") and limpia.endswith("]"):
            adentro = limpia == f"[{seccion}]"
            continue
        if adentro and limpia and not limpia.startswith(";"):
            lineas.append(limpia)
    return lineas


def destinos_de_los_iconos(texto):
    return [re.match(r'Name: "([^"]+)"', linea).group(1)
            for linea in entradas_de_la_seccion(texto, "Icons")]


def test_los_iconos_para_abrir_la_app():
    """
    Escritorio sin preguntar (con la pregunta, Bruno lo destildó y después
    no encontraba cómo abrirla), Inicio, y uno en Documentos\\Armonica, al
    lado de sus frases y canciones.
    """
    texto = ISS.read_text(encoding="utf-8-sig")
    assert "[Tasks]" not in texto
    destinos = destinos_de_los_iconos(texto)
    for destino in ("{group}\\Armónica", "{autodesktop}\\Armónica",
                    "{userdocs}\\Armonica\\Abrir Armónica"):
        assert destino in destinos
    for linea in entradas_de_la_seccion(texto, "Icons"):
        assert "Tasks:" not in linea
        if "lanzador.pyw" in linea:
            assert 'Filename: "{app}\\python\\pythonw.exe"' in linea


def test_el_desinstalador_borra_la_clave_del_coach():
    texto = ISS.read_text(encoding="utf-8-sig")
    borrar = entradas_de_la_seccion(texto, "UninstallDelete")
    assert 'Type: files; Name: "{localappdata}\\Armonica\\coach.env"' in borrar
    assert 'Type: dirifempty; Name: "{localappdata}\\Armonica"' in borrar
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -v -k "iconos or clave"`
Expected: FAIL (`[Tasks]` está; falta el de Documentos; no se borra la clave).

- [ ] **Step 3: Implementar**

En `empaquetado/armonica.iss`: borrar la sección `[Tasks]` entera (las dos líneas). `[Icons]` queda:

```
[Icons]
Name: "{group}\Armónica"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\lanzador.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\Armonica.ico"
; El escritorio sin preguntar: con la pregunta se puede destildar, y después
; no hay cómo encontrarla. El aviso de "Cerrar la app" manda a este ícono.
Name: "{autodesktop}\Armónica"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\lanzador.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\Armonica.ico"
; Y en Documentos\Armonica, al lado de sus frases y canciones.
Name: "{userdocs}\Armonica\Abrir Armónica"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\lanzador.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\Armonica.ico"
```

Al final de `[UninstallDelete]` (antes de `[Code]`):

```
; La clave del coach que se pegó en Ajustes (armonica/coach.py): es de esta
; computadora, y no tiene que quedar si se saca la app.
Type: files; Name: "{localappdata}\Armonica\coach.env"
Type: dirifempty; Name: "{localappdata}\Armonica"
```

- [ ] **Step 4: Correr los tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add empaquetado/armonica.iss tests/test_empaquetar.py
git commit -m "El instalador pone el ícono del escritorio sin preguntar y otro en Documentos\Armonica, y el desinstalador borra la clave del coach." -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 6: La guía: la página, el enlace "Guía" y el texto

**Files:**
- Create: `armonica/web/guia.html`
- Modify: `armonica/web/index.html` (el `<nav>` de la barra), `armonica/web/estilo.css` (el enlace)
- Create: `tests/test_guia.py`

**Interfaces:**
- Consumes: los textos y botones reales de `index.html` y `app.js` (Tasks 1-5 incluidas), los ids de capítulo de abajo.
- Produces: `guia.html` con un `<section class="capitulo" id="...">` por capítulo, en este orden: `instalar`, `primeros-pasos`, `en-vivo`, `frases`, `canciones`, `aprendizaje`, `teoria`, `historial`, `coach`, `cerrar`, `si-algo-no-anda`, `version-nueva`. Adentro de `canciones`, un `<section id="bandinabox">` con solo el título y una oración de presentación (los pasos los escribe la Task 9). Cada captura va como `<figure><img src="guia/<archivo>" alt="..."><figcaption>...</figcaption></figure>` con los nombres de la tabla de abajo (las imágenes llegan en las Tasks 8 y 9: hasta entonces no cargan, es esperado). La Task 7 imprime esta página a PDF; la Task 8 agrega el test de que cada imagen exista.

**Cómo se escribe la guía:**
- Para el profe: usuario básico de Windows, sabe armónica y no sabe nada de programas. Le habla de vos, con oraciones cortas. Cada capítulo empieza con para qué sirve esa parte en una oración.
- Los nombres de botones, solapas y títulos van **exactamente** como en la pantalla, en negrita (por ejemplo **Grabar esta sesión**). Los que arma `app.js` (Canciones, Historial, la devolución de Frases) se leen en `app.js`; los de la pantalla fija, en `index.html`. No describir nada que la app no haga.
- Sin jerga (ver Global Constraints). Las carpetas se nombran como las ve el profe: `Documentos\Armonica\canciones`.
- `estilo.css` de la app para los colores y la letra, más un `<style>` propio: un índice arriba con enlaces a cada capítulo, ancho de lectura cómodo (unos 46em), imágenes con `max-width: 100%` y borde suave, y `@media print` que oculta el índice de enlaces y arranca cada capítulo en hoja nueva (`break-before: page`), sin cortar figuras (`break-inside: avoid`).
- Arriba: título "Guía de Armónica", la versión no (envejece) y una línea "Para abrir la app: el ícono **Armónica** del escritorio."

**Qué cubre cada capítulo** (los hechos salen del código; si el código dice otra cosa, manda el código):

| id | Título | Qué tiene que decir | Captura |
|---|---|---|---|
| `instalar` | Instalar | Bruno se lo pasa en un pendrive o por Drive. Por Drive: Google avisa "No se puede analizar el archivo en busca de virus" → **Descargar de todos modos**. Al abrirlo, Windows puede mostrar "Windows protegió su PC": **Más información** → **Ejecutar de todas formas**. Si en cambio dice "Control Inteligente de Aplicaciones bloqueó una aplicación…", no hay botón para seguir: pedirle a Bruno el instalador en un pendrive. No pide permisos de administrador. Al final queda: el ícono **Armónica** en el escritorio, **Armónica** y **Guía de Armónica** en el menú Inicio, y **Abrir Armónica** en `Documentos\Armonica`. Todo lo que guarda la app va a `Documentos\Armonica`. | `instalar-drive.png`, `instalar-bloqueo.png` |
| `primeros-pasos` | La primera vez | La tarjeta "Primeros pasos" con sus cuatro pasos y el botón **Listo**; si la barra no se mueve, **Abrir los permisos del micrófono**. Se vuelven a ver en Ajustes → **Ver los primeros pasos**. Ajustes → El micrófono: elegir el de la boca, soplar y ver la barra; **Medir el ruido** (tres segundos en silencio). | `primeros-pasos.png`, `ajustes-microfono.png` |
| `en-vivo` | En vivo | Qué muestra mientras tocás (la barra, el agujero, el diagrama "La armónica", "Lo que tocaste"); **Grabar esta sesión** y al terminar **Guardar** o **Descartar**; el "Resumen de la sesión". Tocar sobre una base elegida en Canciones. | `en-vivo.png` |
| `frases` | Frases | Qué es una frase de referencia; **Grabar una frase** o **Importar un audio** (de WhatsApp, por ejemplo); "Esto es lo que salió": nombre, descripción, lista, **Guardar**/**Descartar**; "Tus frases", las listas; practicar una y "Cómo te salió". | `frases.png` |
| `canciones` | Canciones | Una carpeta por canción en `Documentos\Armonica\canciones` (**Abrir la carpeta**), con la base de Band-in-a-Box (`.sgu` o `.mgu`), los audios y la tablatura en foto. Qué muestra de cada canción (ficha, cifrado, la casilla por compás para escribir dónde aterrizar), reproducir la base, **Practicar sobre esta base**, importar sus audios como frases. La app solo lee esa carpeta. Al final, el `<section id="bandinabox">` ("Preparar una canción en Band-in-a-Box", con una oración: "Estos son los pasos para guardar la base y su audio desde Band-in-a-Box."). | `canciones.png` |
| `aprendizaje` | Aprendizaje | Lee los resúmenes de clase de `Documentos\Armonica\apuntes` (archivos `.md`, `.txt`, `.docx` y `.pdf`, ver `armonica/clases.py`); buscar en las clases. Solo lee. | — |
| `teoria` | Teoría | Las posiciones, la escala, las notas guía; el círculo de quintas con **Tono de la armónica** y **Tono de la canción**. | `teoria.png` |
| `historial` | Historial | "Cómo vienen tus bends" (la franja verde es la zona afinada, medido contra la propia armónica) y "Las sesiones". | `historial.png` |
| `coach` | El coach | Qué hace (explica en palabras lo medido; nunca mide), que necesita internet y una clave de Claude, ChatGPT o Gemini, y cuál elegir: si Bruno le da una, esa; si quiere sacar la suya, **Gemini** en aistudio.google.com es gratis con un tope por día (en la versión gratis Google puede usar lo que se le manda para mejorar sus productos); **ChatGPT** en platform.openai.com y **Claude** en console.anthropic.com se pagan por uso, unos centavos por consulta, y la suscripción a ChatGPT Plus o a Claude no trae la clave (es aparte). En esos sitios se llama "API key". Dónde se pega: Ajustes → El coach → **Guardar y probar**; la app reconoce de quién es. Qué sale de la computadora (números y texto, nunca el audio) y hacia qué empresa. Dónde aparecen sus botones; **Borrar la clave**. | `ajustes-coach.png` |
| `cerrar` | Cerrar la app | Cerrar la pestaña no cierra la app: sigue abierta por detrás y al minuto suelta el micrófono. Para cerrarla del todo: Ajustes → **Cerrar la app**. Para volver a abrirla, el ícono del escritorio. Si ya está abierta y se toca el ícono, solo se abre la página. | — |
| `si-algo-no-anda` | Si algo no anda | La barra no se mueve (otro micrófono en Ajustes; "Mejoras de audio" de Windows; los permisos del micrófono). Un audio no se convierte y dice "Windows no lo dejó correr" (probar con el audio en `.wav`). El cartel "Armónica ya se está abriendo pero todavía no contesta" (esperar y volver a probar). El coach dice que hace falta una versión nueva: pedírsela a Bruno. Para cualquier otra cosa: mandarle a Bruno `Documentos\Armonica\registro.txt`. | — |
| `version-nueva` | Una versión nueva | Se instala encima, con el mismo procedimiento; frases, sesiones, canciones, ajustes y la clave del coach no se tocan. Desinstalar: Configuración → Aplicaciones → Armónica; `Documentos\Armonica` queda entera (la clave del coach se borra). | — |

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_guia.py`:

```python
"""
Tests de la guía (armonica/web/guia.html): que esté entera, que no tenga
jerga y que la app la enlace. Que cada imagen exista lo prueba
test_cada_imagen_de_la_guia_existe_y_no_es_enorme, que se agrega con las
capturas.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_guia.py -v
"""

import os
from html.parser import HTMLParser

from tests.test_textos import INDEX, JERGA, TextoVisible

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIA = os.path.join(RAIZ, "armonica", "web", "guia.html")

CAPITULOS = ("instalar", "primeros-pasos", "en-vivo", "frases", "canciones", "aprendizaje",
             "teoria", "historial", "coach", "cerrar", "si-algo-no-anda", "version-nueva")

# Además de la jerga de la app: lo que el profe no tiene por qué leer. "API"
# no está: es el nombre que le dan a la clave en los sitios donde se saca.
JERGA_DE_LA_GUIA = JERGA + ("LLM_", "127.0.0.1", "localhost", "pythonw", "servidor", "puerto")


class Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.enlaces = []

    def handle_starttag(self, etiqueta, atributos):
        propios = dict(atributos)
        if propios.get("id"):
            self.ids.append(propios["id"])
        if etiqueta == "a":
            self.enlaces.append(propios)


def leer(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        return archivo.read()


def test_la_guia_tiene_todos_los_capitulos_en_orden():
    lector = Ids()
    lector.feed(leer(GUIA))
    encontrados = [id_ for id_ in lector.ids if id_ in CAPITULOS]
    assert encontrados == list(CAPITULOS)
    assert "bandinabox" in lector.ids


def test_el_indice_lleva_a_cada_capitulo():
    lector = Ids()
    lector.feed(leer(GUIA))
    destinos = {enlace.get("href") for enlace in lector.enlaces}
    for capitulo in CAPITULOS:
        assert f"#{capitulo}" in destinos, f"el índice no lleva a {capitulo}"


def test_la_guia_no_tiene_jerga():
    lector = TextoVisible()
    lector.feed(leer(GUIA))
    visible = " ".join(lector.textos)
    for palabra in JERGA_DE_LA_GUIA:
        assert palabra not in visible, f"{palabra!r} aparece en la guía"


def test_la_app_enlaza_la_guia_en_otra_pestana():
    """
    Un <a> y no una solapa: las solapas son botones con data-panel, y
    configurarSolapas() escondería todos los paneles si hubiera una sin él.
    """
    lector = Ids()
    lector.feed(leer(INDEX))
    guia = [enlace for enlace in lector.enlaces if enlace.get("href") == "guia.html"]
    assert len(guia) == 1
    assert guia[0].get("target") == "_blank"
    assert "solapa" not in (guia[0].get("class") or "").split()
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_guia.py -v`
Expected: FAIL/ERROR (no existe `guia.html`; no hay enlace).

- [ ] **Step 3: El enlace en la barra**

En `armonica/web/index.html`, dentro de `<nav>`, después del botón de Ajustes:

```html
    <a class="enlace-guia" href="guia.html" target="_blank" rel="noopener">Guía</a>
```

En `armonica/web/estilo.css`, al lado de las reglas de `.solapa`, una regla `.enlace-guia` que copie su forma (mismo padding, letra, color, borde y radio que `.solapa` sin `.activa`, `text-decoration: none`, y el mismo `:hover`). Mirar las reglas de `.solapa` y repetir los valores: no inventar colores.

- [ ] **Step 4: Escribir `armonica/web/guia.html`**

Con la estructura, el estilo y el contenido de arriba. Esqueleto:

```html
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guía de Armónica</title>
<link rel="stylesheet" href="estilo.css">
<link rel="icon" type="image/png" href="icono.png">
<style>
  /* el estilo de lectura y el @media print, ver "Cómo se escribe la guía" */
</style>
</head>
<body class="guia">
<main>
  <h1>Guía de Armónica</h1>
  <p>Para abrir la app: el ícono <strong>Armónica</strong> del escritorio.</p>
  <nav class="indice"> <!-- un <a href="#id"> por capítulo --> </nav>

  <section class="capitulo" id="instalar">
    <h2>Instalar</h2>
    <!-- el contenido de la fila "instalar" de la tabla -->
  </section>
  <!-- un <section class="capitulo"> por fila de la tabla, en orden -->
</main>
</body>
</html>
```

(Los comentarios de este esqueleto marcan la forma, no el contenido: el contenido es la tabla de arriba, escrito entero, y en el archivo final no quedan comentarios de relleno.)

- [ ] **Step 5: Correr los tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_guia.py tests/test_textos.py -q`
Expected: PASS.

- [ ] **Step 6: Mirarla**

Abrir `armonica/web/guia.html` en el navegador (`start armonica\web\guia.html`): el índice lleva a cada capítulo, se lee cómodo, las imágenes todavía no cargan (es esperado). Vista previa de impresión (Ctrl+P): cada capítulo en hoja nueva y sin el índice de enlaces.

- [ ] **Step 7: Commit**

```bash
git add armonica/web/guia.html armonica/web/index.html armonica/web/estilo.css tests/test_guia.py
git commit -m "La guía de uso para el profe, con un enlace Guía en la barra de la app que la abre en otra pestaña." -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 7: El PDF de la guía al armar

**Files:**
- Modify: `herramientas/empaquetar.py` (constante `NOMBRE_DEL_PDF`; funciones `buscar_edge`, `orden_del_pdf`, `generar_pdf`; `armar`, `humo`, `instalador`; docstring del módulo)
- Modify: `empaquetado/armonica.iss` (`[Icons]`)
- Test: `tests/test_empaquetar.py`

**Interfaces:**
- Consumes: `armonica/web/guia.html` (Task 6); `entradas_de_la_seccion`, `destinos_de_los_iconos`, `ISS` (Task 5, en el test).
- Produces: `NOMBRE_DEL_PDF = "Guia de Armonica.pdf"`; `buscar_edge(entorno=None) -> Path | None`; `orden_del_pdf(edge, html, pdf, perfil) -> list[str]`; `generar_pdf(html, pdf, edge=None) -> Path`. El PDF queda en `{app}\Guia de Armonica.pdf` y en `dist\Guia de Armonica.pdf` (para mandárselo al profe junto con el instalador); en Inicio, "Guía de Armónica".

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_empaquetar.py`:

```python
def test_buscar_edge(tmp_path):
    edge = tmp_path / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.write_bytes(b"")
    assert empaquetar.buscar_edge({"ProgramFiles(x86)": str(tmp_path)}) == edge
    assert empaquetar.buscar_edge({"EDGE": str(edge)}) == edge
    assert empaquetar.buscar_edge({"ProgramFiles(x86)": str(tmp_path / "nada")}) is None


def test_la_orden_que_imprime_la_guia(tmp_path):
    html = tmp_path / "web" / "guia.html"
    orden = empaquetar.orden_del_pdf(Path("C:/Edge/msedge.exe"), html, tmp_path / "g.pdf",
                                     tmp_path / "perfil")
    assert orden[0].endswith("msedge.exe")
    assert "--headless" in orden
    assert f"--print-to-pdf={tmp_path / 'g.pdf'}" in orden
    # Un perfil aparte: así no se engancha al Edge que Bruno tenga abierto.
    assert f"--user-data-dir={tmp_path / 'perfil'}" in orden
    assert "--no-pdf-header-footer" in orden
    assert orden[-1] == html.resolve().as_uri()


def test_la_guia_esta_en_el_menu_inicio():
    texto = ISS.read_text(encoding="utf-8-sig")
    assert "{group}\\Guía de Armónica" in destinos_de_los_iconos(texto)
    guia = [linea for linea in entradas_de_la_seccion(texto, "Icons") if "Guía de Armónica" in linea]
    assert 'Filename: "{app}\\Guia de Armonica.pdf"' in guia[0]
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -v -k "edge or guia"`
Expected: FAIL (no existen las funciones ni el ícono).

- [ ] **Step 3: Implementar**

En `herramientas/empaquetar.py`, después de `nombre_del_instalador`:

```python
# La guía en PDF: va al programa (Inicio → Guía de Armónica) y a dist\, para
# mandársela al profe junto con el instalador.
NOMBRE_DEL_PDF = "Guia de Armonica.pdf"


def buscar_edge(entorno=None):
    """Microsoft Edge, que viene con Windows: imprime la guía a PDF sin ventana."""
    entorno = os.environ if entorno is None else entorno
    candidatos = []
    if entorno.get("EDGE"):
        candidatos.append(Path(entorno["EDGE"]))
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        if entorno.get(variable):
            candidatos.append(Path(entorno[variable]) / "Microsoft" / "Edge" / "Application"
                              / "msedge.exe")
    return next((candidato for candidato in candidatos if candidato.is_file()), None)


def orden_del_pdf(edge, html, pdf, perfil):
    """
    La línea de Edge que imprime `html` a `pdf`. Sin ventana, sin el
    encabezado y el pie que agrega el navegador, y con un perfil aparte:
    con el de Bruno se engancharía a su Edge abierto.
    """
    return [str(edge), "--headless", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", f"--user-data-dir={perfil}",
            "--no-pdf-header-footer", f"--print-to-pdf={pdf}",
            Path(html).resolve().as_uri()]


def generar_pdf(html, pdf, edge=None):
    """Imprime la guía a PDF con Edge. Si no queda un PDF, corta el armado."""
    edge = edge or buscar_edge()
    if edge is None:
        raise SystemExit("No encuentro Microsoft Edge (msedge.exe) para imprimir la guía.")
    pdf = Path(pdf)
    if pdf.exists():
        pdf.unlink()
    # ignore_cleanup_errors: Edge deja procesos que tardan en soltar el perfil.
    with tempfile.TemporaryDirectory(prefix="armonica-edge-", ignore_cleanup_errors=True) as perfil:
        subprocess.run(orden_del_pdf(edge, html, pdf, perfil), check=True, timeout=120,
                       capture_output=True)
    if not pdf.is_file() or pdf.read_bytes()[:5] != b"%PDF-":
        raise SystemExit(f"Edge no dejó la guía en PDF en {pdf}.")
    print(f"  Guía en PDF: {pdf.name}")
    return pdf
```

En `armar()`, después de escribir `LEEME.txt` y antes de leer la versión:

```python
        generar_pdf(ARMADO / "app" / "armonica" / "web" / "guia.html", ARMADO / NOMBRE_DEL_PDF)
```

En `humo()`, después de leer `version`:

```python
    if not (programa / NOMBRE_DEL_PDF).is_file():
        raise SystemExit(f"Al programa le falta {NOMBRE_DEL_PDF}.")
```

En `instalador()`, después de verificar `salida`:

```python
    shutil.copyfile(programa / NOMBRE_DEL_PDF, DIST / NOMBRE_DEL_PDF)
```

En el docstring del módulo, la línea de `armar` suma "imprime la guía a PDF con Edge", y la de `instalador` "y deja al lado la guía en PDF".

En `empaquetado/armonica.iss`, `[Icons]`, después del de Inicio:

```
Name: "{group}\Guía de Armónica"; Filename: "{app}\Guia de Armonica.pdf"
```

- [ ] **Step 4: Correr los tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -q`
Expected: PASS.

- [ ] **Step 5: Probar el PDF de verdad**

```powershell
.\.venv\Scripts\python.exe -c "from herramientas import empaquetar; empaquetar.generar_pdf('armonica/web/guia.html', r'$env:TEMP\guia-prueba.pdf')"
Start-Process "$env:TEMP\guia-prueba.pdf"
```

Expected: "Guía en PDF: guia-prueba.pdf"; el PDF abre, cada capítulo en hoja nueva, sin la fecha ni la ruta del navegador arriba y abajo.

- [ ] **Step 6: Commit**

```bash
git add herramientas/empaquetar.py empaquetado/armonica.iss tests/test_empaquetar.py
git commit -m "El armado imprime la guía a PDF con Edge, la pone en el programa y en dist, y el instalador la deja en el menú Inicio." -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 8: Las capturas de la app (la hace el controlador, con Bruno)

No es para un subagente: maneja el navegador (Playwright), mira cada imagen y necesita a Bruno tocando.

**Necesita:** Tasks 1-7 hechas; la canción de ejemplo de Bruno en `empaquetado/ejemplos/canciones/<nombre>/` (`.sgu` y `.wav`); Bruno disponible cinco minutos.

**Files:**
- Create: `armonica/web/guia/instalar-drive.png`, `instalar-bloqueo.png`, `primeros-pasos.png`, `ajustes-microfono.png`, `en-vivo.png`, `frases.png`, `canciones.png`, `teoria.png`, `historial.png`, `ajustes-coach.png`
- Modify: `tests/test_guia.py`

- [ ] **Step 1: El test de que cada imagen exista (falla)**

Al final de `tests/test_guia.py`:

```python
class Imagenes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fuentes = []

    def handle_starttag(self, etiqueta, atributos):
        if etiqueta == "img":
            self.fuentes.append(dict(atributos).get("src"))


def test_cada_imagen_de_la_guia_existe_y_no_es_enorme():
    lector = Imagenes()
    lector.feed(leer(GUIA))
    assert lector.fuentes, "la guía no tiene imágenes"
    for fuente in lector.fuentes:
        ruta = os.path.join(RAIZ, "armonica", "web", *fuente.split("/"))
        assert os.path.isfile(ruta), f"falta {fuente}"
        assert os.path.getsize(ruta) < 400_000, f"{fuente} pesa demasiado"
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_guia.py -v` → FAIL "falta guia/instalar-drive.png".

- [ ] **Step 2: Datos neutros y la app**

Carpeta de datos en el scratchpad (`$D`), con la canción de ejemplo copiada a `$D\canciones\<nombre>\`. Arrancar la instalada desde el worktree con `ARMONICA_DATOS=$D` y `ARMONICA_SIN_NAVEGADOR=1` (como en la Task 4, Step 6). Verificar `GET /api/hola`. Verificar de paso lo de la Task 4, Step 6, si el implementador no pudo.

- [ ] **Step 3: Sacar las capturas**

Con Playwright: ventana de 1280×800, `http://127.0.0.1:<puerto>`. En orden: la tarjeta de primeros pasos (`primeros-pasos.png`); Ajustes, el micrófono elegido y el ruido medido (`ajustes-microfono.png`); Canciones con la canción de ejemplo abierta (`canciones.png`), y desde ahí importar su audio como frase; Frases con esa frase (`frases.png`); Teoría (`teoria.png`); Ajustes → El coach sin clave (`ajustes-coach.png`). Con Bruno tocando: En vivo con una nota marcada (`en-vivo.png`); grabar y guardar una sesión corta; Historial (`historial.png`). Cada captura se recorta a lo que importa con Pillow, ancho máximo 1100 px, `optimize=True`, a `armonica/web/guia/`.

- [ ] **Step 4: Las del instalador**

De `empaquetado/capturas/instalar/`: `01-drive-no-puede-analizar.png` → `instalar-drive.png` (solo achicar); `02-control-inteligente-bloqueo.png` → `instalar-bloqueo.png`, tapando la ruta `C:\Users\bruno\Downloads\` con un rectángulo del color del fondo (o recortando ese renglón).

- [ ] **Step 5: Revisar cada imagen**

Abrir cada una: sin nombres de personas, rutas con usuarios, correos ni datos de clase; legible al ancho de la guía. Mirar `guia.html` en el navegador con las imágenes.

- [ ] **Step 6: Tests y commit**

Run: `.venv/Scripts/python.exe -m pytest tests/test_guia.py -q` → PASS.

```bash
git add armonica/web/guia/*.png tests/test_guia.py
git commit -m "Las capturas de la guía, sacadas de la app con datos neutros y recortadas." -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

Cerrar la app de prueba (Ajustes → Cerrar la app).

---

### Task 9: El capítulo de Band-in-a-Box, con las capturas de Bruno

**Necesita:** `empaquetado/capturas/bandinabox/` con las capturas numeradas (`01.png`, `02.png`…) y `notas.txt` (una línea por captura: qué tocó o escribió), y la versión de Band-in-a-Box que dijo Bruno.

**Files:**
- Create: `armonica/web/guia/bandinabox-NN.png` (las que hagan falta, numeradas de nuevo desde 01)
- Modify: `armonica/web/guia.html` (`<section id="bandinabox">`)

**Interfaces:**
- Consumes: el `<section id="bandinabox">` de la Task 6; el test de imágenes de la Task 8.

- [ ] **Step 1: Leer las notas y mirar cada captura**

Leer `notas.txt` entero y abrir cada imagen. Armar la lista de pasos: de dónde sale la canción, tonalidad y tempo, guardar el `.SGU`, exportar el audio a `.WAV` (cada ventana con sus opciones), y copiar los dos archivos a `Documentos\Armonica\canciones\<nombre>\` (en la app: Canciones → **Abrir la carpeta**).

- [ ] **Step 2: Elegir, recortar y marcar**

Una captura por paso, la que mejor muestra dónde hacer clic. Recortar a la zona útil (ancho máximo 1100 px, `optimize=True`) y, si ayuda, marcar el lugar del clic con un rectángulo de 3 px en el color de acento de `estilo.css`. Tapar cualquier dato personal (nombre de registro en la barra de título, rutas con usuarios). Guardar como `armonica/web/guia/bandinabox-01.png`, `-02`…

- [ ] **Step 3: Escribir el capítulo**

En `<section id="bandinabox">`: una lista numerada, un paso por ítem, cada uno con su figura. Los nombres de menús, ventanas y botones **exactamente como se ven en las capturas** (nunca de memoria). Una línea al principio: "Probado con Band-in-a-Box <versión>." Al final, qué hace la app con esos archivos (lee el tono, el tempo y el cifrado del `.SGU`; el `.WAV` es la base que suena). Mismo estilo que el resto de la guía.

- [ ] **Step 4: Tests, mirarla y commit**

Run: `.venv/Scripts/python.exe -m pytest tests/test_guia.py -q` → PASS. Mirar el capítulo en el navegador y en el PDF (Task 7, Step 5).

```bash
git add armonica/web/guia/bandinabox-*.png armonica/web/guia.html
git commit -m "La guía explica paso a paso cómo preparar una canción en Band-in-a-Box, con las capturas de Bruno." -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 10: Versión 0.2.0, la documentación, el instalador nuevo y la prueba

Los Steps 1-3 los puede hacer un subagente; del 4 en adelante, el controlador con Bruno.

**Files:**
- Modify: `VERSION` (`0.2.0`), `empaquetado/PROBAR.md`, `PROXIMOS_PASOS.md`, `README.md` (sección "El instalador para el profe")

- [ ] **Step 1: La versión**

`VERSION` queda `0.2.0`.

- [ ] **Step 2: `PROBAR.md`**

- En "Control inteligente de aplicaciones": lo que pasó el 2026-10-04 con el instalador bajado de Drive (bloqueado sin "Ejecutar de todas formas"; con Propiedades → **Desbloquear**, o desde un pendrive, corre), y que Drive antes avisa "No se puede analizar el archivo en busca de virus" → **Descargar de todos modos**.
- En "La prueba", pasos nuevos o cambiados: el paso 3 suma que estén los tres íconos (escritorio, Inicio con "Armónica" y "Guía de Armónica", y "Abrir Armónica" en `Documentos\Armonica`); un paso para la guía (el enlace **Guía** de la barra abre la guía en otra pestaña; Inicio → Guía de Armónica abre el PDF); un paso para el coach (Ajustes → El coach: Bruno pega una clave de cada proveedor que tenga, **Guardar y probar** dice de quién es y que anda, aparece el botón del coach en una devolución y contesta bien; **Borrar la clave**); el paso 10 suma que desinstalar borra `%LOCALAPPDATA%\Armonica\coach.env`.

- [ ] **Step 3: `PROXIMOS_PASOS.md` y `README.md`, y commit**

- `PROXIMOS_PASOS.md`: entrada "Instalador, etapa 3: la guía" (hecho, con fecha), y que el coach ya es para el profe (clave de Claude, ChatGPT o Gemini en Ajustes; los modelos por defecto vencen y piden una versión nueva). El "Falta" de la etapa 2 se actualiza.
- `README.md`, sección "El instalador para el profe": la guía (`armonica/web/guia.html`, el PDF en el programa y en `dist`), el coach del profe (la clave en Ajustes, guardada en `%LOCALAPPDATA%\Armonica\coach.env`, reconocida por cómo empieza).

```bash
git add VERSION empaquetado/PROBAR.md PROXIMOS_PASOS.md README.md
git commit -m "Versión 0.2.0: PROBAR.md suma la guía, el coach y los íconos nuevos, y la documentación cuenta la etapa 3." -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

- [ ] **Step 4: Armar (controlador)**

Después de mergear a `main`, desde el checkout principal:

```powershell
.\herramientas\empaquetar.ps1
```

Expected: tests sobre lo commiteado en verde, "Guía en PDF: Guia de Armonica.pdf", "Prueba de humo de 0.2.0: ok.", y en `dist\` el instalador `Armonica-0.2.0-instalador.exe` y `Guia de Armonica.pdf`.

- [ ] **Step 5: Instalar encima de la 0.1.0 y probar (controlador y Bruno)**

Con la Armónica del repo cerrada: instalar `dist\Armonica-0.2.0-instalador.exe` encima de la 0.1.0 que Bruno tiene instalada, con la app abierta. Verificar con el script de la prueba del 2026-10-04 (cerrar, doble arranque, instalar encima, desinstalar y volver a instalar) y además: los tres íconos, la guía (enlace y PDF), y que los datos de `Documentos\Armonica` siguen. Bruno pega sus claves en Ajustes y prueba el coach en una devolución con cada proveedor. Después, los pasos de `PROBAR.md` que quedan (el instalador bajado de Drive, con el Control inteligente activado: va bloqueado, se desbloquea o se usa el pendrive).

- [ ] **Step 6: Push (solo si Bruno lo pide)**

---

## Self-review

- **Cobertura de la spec, "La guía":** `guia.html` con botón en la barra (Task 6), PDF con Edge al armar (Task 7), capítulos (Task 6, Band-in-a-Box en la Task 9), captura del aviso de instalación (Task 8; SmartScreen común solo con texto, ver Desvíos), capturas con datos neutros guardadas en el repo (Task 8). "Cómo queda instalado": `Guia de Armonica.pdf` en el programa y "Guía de Armónica" en Inicio (Task 7). Los cuatro cambios del 2026-10-04: registro (Task 1), coach con tres proveedores (Tasks 2-4), íconos (Task 5), cerrar la pestaña (sin cambio de código; capítulo `cerrar` en la Task 6). Un solo instalador al final (Task 10).
- **Nombres entre tareas:** `CLAVE_EN_AJUSTES`, `PROVEEDORES_CON_CLAVE`, `NOMBRES`, `_motivo_de_la_clave` (Task 2) los usa la Task 3; `ARCHIVO_CLAVE`, `ruta_de_la_clave`, `proveedor_de_la_clave`, `guardar_clave` (devuelve el proveedor), `probar`, `clave_en_ajustes` y la respuesta de `/api/coach/clave` con `proveedor` (Task 3) los usan las Tasks 4 y 5; la fixture `coach_como_en_la_maquina_de_bruno` la crea la Task 2 y la amplía la Task 3; `entradas_de_la_seccion`, `destinos_de_los_iconos`, `ISS` (Task 5) los reusa la Task 7; `NOMBRE_DEL_PDF` es el mismo en `empaquetar.py` y en el `.iss`; los nombres de las capturas de la tabla de la Task 6 son los que crea la Task 8.
