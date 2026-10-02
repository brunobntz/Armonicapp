# Instalador, etapa 1: la app y el lanzador — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la app se pueda abrir desde un ícono sin ventana negra, recuerde lo que se elige en Ajustes, guíe la primera vez, no muestre jerga de programador en la versión instalada y se pueda cerrar desde la pantalla. Es todo lo que el instalador (etapa 2) va a empaquetar.

**Architecture:** Un módulo nuevo `armonica/ajustes.py` guarda lo elegido en `ajustes.json` (en la carpeta desde donde arranca la app). El servidor (`armonica/servidor.py`) suma rutas chicas (`/api/hola`, `/api/medir-ruido`, `/api/apagar`, `/api/abrir`, `/api/primeros-pasos`), enlaza el puerto en exclusiva, cuenta las páginas conectadas para apagar el micrófono y sabe si es la versión instalada (`empaquetada`). Un lanzador nuevo (`armonica/lanzador.py` + `lanzador.pyw`) se para en `Documentos\Armonica`, manda la salida a `registro.txt`, pone ffmpeg en el PATH y abre una sola instancia.

**Tech Stack:** Python 3.14 (solo biblioteca estándar en lo nuevo: `json`, `ctypes`, `socket`, `http.server`, `urllib`), JavaScript y CSS sin frameworks, pytest.

**Spec:** `docs/superpowers/specs/2026-10-02-instalador-profe-design.md` (secciones "El lanzador", "Cambios en la app", "Textos con jerga hoy", "Orden de trabajo" etapa 1).

## Global Constraints

- NUNCA commitear `config.py` ni `EVALUATION_2026-09-18.md`: tienen cambios locales de Bruno (`DISPOSITIVO_ENTRADA = 1`, `UMBRAL_VOLUMEN_RMS = 0.0030`). Cada commit agrega solo los archivos de su tarea.
- Los tests se corren con `.venv/Scripts/python.exe -m pytest` (el Python del sistema no tiene `rich`).
- Fallas conocidas que NO son de este plan: `tests/test_audio.py::test_normalizar_arregla_una_grabacion_demasiado_baja` (por el umbral local de Bruno en `config.py`) y `tests/test_servidor.py::test_la_lista_de_canciones_trae_la_ficha_para_la_armonica_puesta` (timeout por el Ollama del `.env`). No arreglarlas acá.
- Ningún test escribe en la carpeta del repo: `ajustes.json`, carpetas de frases y demás van a `tmp_path` con `monkeypatch`.
- Sin dependencias nuevas.
- Las rutas de datos siguen relativas a la carpeta de arranque; solo el lanzador sabe de `Documentos\Armonica`.
- Orden de precedencia: lo escrito en la línea de comandos > `ajustes.json` > `config.py`.
- El micrófono se guarda POR NOMBRE, nunca por número.
- Textos de pantalla en castellano rioplatense (voseo), sin jerga de programador cuando `empaquetada` es verdadero.
- Comentarios y docstrings en castellano, explicando el porqué, como el resto del código.
- Mensajes de commit en castellano, una oración sin prefijo, y la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` al final.

---

## Mapa de archivos

| Archivo | Qué cambia |
|---|---|
| `armonica/ajustes.py` (nuevo) | Cargar y guardar `ajustes.json`, validar, precedencia, micrófono por nombre |
| `armonica/version.py` (nuevo) + `VERSION` (nuevo) | La versión de la app |
| `armonica/lanzador.py` (nuevo) + `lanzador.pyw` (nuevo) | Abrir la app desde un ícono |
| `armonica/servidor.py` | Ajustes al arrancar y al cambiar, puerto exclusivo, rutas nuevas, contar páginas, vigía del micrófono, `empaquetada` |
| `armonica/microfono.py` | `resumen_de_ruido` (sale de `medir_ruido_de_fondo`) |
| `armonica/audio.py` | ffmpeg con `CREATE_NO_WINDOW` |
| `armonica/transcripcion.py` | Dos avisos sin comandos de terminal |
| `main.py` | `--web` pasa solo lo escrito y avisa si el puerto está ocupado |
| `armonica/web/index.html`, `app.js`, `estilo.css` | Medir el ruido, La app (versión, cerrar), primeros pasos, abrir carpetas, textos |
| `.gitignore` | `ajustes.json`, `registro.txt` |
| `README.md`, `PROXIMOS_PASOS.md` | Documentar |
| `tests/test_ajustes.py`, `tests/test_lanzador.py`, `tests/test_textos.py`, `tests/test_main.py` (nuevos) | Tests |
| `tests/test_servidor.py`, `tests/test_microfono.py`, `tests/test_audio.py`, `tests/test_transcripcion.py` | Tests nuevos y la fixture aislada |

---

### Task 1: `armonica/ajustes.py` — lo elegido, guardado en `ajustes.json`

**Files:**
- Create: `armonica/ajustes.py`
- Create: `tests/test_ajustes.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces:
  - `ajustes.ARCHIVO: str = "ajustes.json"` (se lee en cada llamada, así se puede monkeypatchear)
  - `ajustes.FABRICA: dict = {"tonalidad": "C", "posicion": None, "escala": None}`
  - `ajustes.cargar(ruta=None) -> dict` (claves válidas solamente; `{}` si no hay archivo o está roto)
  - `ajustes.guardar(cambios: dict, ruta=None) -> dict` (pisa solo lo que viene; `ValueError` si algo es inválido)
  - `ajustes.valores_de_arranque(guardados, tonalidad=None, posicion=None, escala=None) -> dict` con claves `tonalidad`, `posicion`, `escala`
  - `ajustes.aplicar_a_config(guardados, modulo=None) -> None` (pone `UMBRAL_VOLUMEN_RMS`)
  - `ajustes.resolver_microfono(nombre, entradas) -> int | None` (`entradas`: lista de `(numero, nombre, canales)` como devuelve `microfono.listar_dispositivos()`)
  - Claves válidas: `microfono` (str; `""` = el de Windows), `umbral` (número entre 0 y 1), `tonalidad` (en `tablas.TONALIDADES`), `posicion` (None o int en `tablas.POSICIONES_CON_TABLA`), `escala` (None o en `tablas.ESCALAS_INTERVALOS`), `primeros_pasos` (bool).

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_ajustes.py`:

```python
"""
Tests de armonica/ajustes.py — lo que se elige en Ajustes, guardado para la
próxima vez.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_ajustes.py -v
"""

import json
import types

import pytest

from armonica import ajustes


def test_sin_archivo_no_hay_ajustes(tmp_path):
    assert ajustes.cargar(str(tmp_path / "ajustes.json")) == {}


def test_guardar_y_volver_a_leer(tmp_path):
    ruta = str(tmp_path / "ajustes.json")
    elegidos = {"microfono": "Micrófono (USB Audio)", "umbral": 0.0042,
                "tonalidad": "A", "posicion": 2, "escala": "blues_mayor",
                "primeros_pasos": True}
    assert ajustes.guardar(elegidos, ruta) == elegidos
    assert ajustes.cargar(ruta) == elegidos
    with open(ruta, encoding="utf-8") as archivo:
        assert json.load(archivo)["microfono"] == "Micrófono (USB Audio)"


def test_guardar_pisa_solo_lo_que_viene(tmp_path):
    ruta = str(tmp_path / "ajustes.json")
    ajustes.guardar({"tonalidad": "A", "umbral": 0.004}, ruta)
    assert ajustes.guardar({"umbral": 0.006}, ruta) == {"tonalidad": "A", "umbral": 0.006}


@pytest.mark.parametrize("clave, valor", [
    ("tonalidad", "H"), ("posicion", 7), ("posicion", True), ("umbral", 0),
    ("umbral", "alto"), ("escala", "inventada"), ("primeros_pasos", "si"),
    ("microfono", 3), ("otra_cosa", 1),
])
def test_un_ajuste_invalido_no_se_guarda(tmp_path, clave, valor):
    ruta = str(tmp_path / "ajustes.json")
    with pytest.raises(ValueError):
        ajustes.guardar({clave: valor}, ruta)
    assert ajustes.cargar(ruta) == {}


def test_lo_invalido_en_el_archivo_se_ignora(tmp_path):
    """Un archivo editado a mano, o de otra versión, no rompe el arranque."""
    ruta = tmp_path / "ajustes.json"
    ruta.write_text(json.dumps({"tonalidad": "H", "umbral": 0.004, "vieja": 1}), encoding="utf-8")
    assert ajustes.cargar(str(ruta)) == {"umbral": 0.004}


def test_un_archivo_roto_no_rompe(tmp_path):
    ruta = tmp_path / "ajustes.json"
    ruta.write_text("{esto no es json", encoding="utf-8")
    assert ajustes.cargar(str(ruta)) == {}


def test_la_linea_de_comandos_le_gana_a_lo_guardado_y_lo_guardado_a_la_fabrica():
    assert ajustes.valores_de_arranque({}) == {"tonalidad": "C", "posicion": None, "escala": None}
    guardados = {"tonalidad": "A", "posicion": 2}
    assert ajustes.valores_de_arranque(guardados) == {"tonalidad": "A", "posicion": 2, "escala": None}
    assert ajustes.valores_de_arranque(guardados, tonalidad="D") == \
        {"tonalidad": "D", "posicion": 2, "escala": None}


def test_el_umbral_guardado_pisa_el_de_config():
    falso = types.SimpleNamespace(UMBRAL_VOLUMEN_RMS=0.01)
    ajustes.aplicar_a_config({}, falso)
    assert falso.UMBRAL_VOLUMEN_RMS == 0.01
    ajustes.aplicar_a_config({"umbral": 0.004}, falso)
    assert falso.UMBRAL_VOLUMEN_RMS == 0.004


def test_el_microfono_se_busca_por_nombre():
    """Windows repite el nombre una vez por API de audio: vale el primero."""
    entradas = [(0, "Asignador de sonido Microsoft - Input", 2),
                (1, "Micrófono (USB Audio)", 1),
                (7, "Micrófono (USB Audio)", 1)]
    assert ajustes.resolver_microfono(" micrófono (usb audio) ", entradas) == 1
    assert ajustes.resolver_microfono("Cámara", entradas) is None
    assert ajustes.resolver_microfono("", entradas) is None
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ajustes.py -v`
Expected: ERROR de colección con `ImportError: cannot import name 'ajustes' from 'armonica'`.

- [ ] **Step 3: Escribir `armonica/ajustes.py`**

```python
"""
ajustes.py — Lo que se elige en Ajustes, guardado para la próxima vez.

Hasta ahora lo que se cambiaba en la solapa Ajustes vivía en memoria: al
cerrar la app volvía todo a config.py y a lo que dijera Armonica.bat. Para
Bruno era una molestia; para el profe, que abre la app desde un ícono, sería
elegir el micrófono cada vez.

Se guarda en ajustes.json, en la carpeta desde donde arranca la app (en la
versión instalada, Documentos\\Armonica). Manda, de más a menos:

    lo escrito en la línea de comandos   (Armonica.bat)
    ajustes.json                          (lo que se eligió en pantalla)
    config.py                             (la fábrica)

EL MICRÓFONO SE GUARDA POR NOMBRE. Windows numera las entradas en el orden
en que las encuentra, y enchufar unos auriculares corre los números: el
número de ayer hoy puede ser la cámara.
"""

import json
import os

import config
from armonica import tablas

ARCHIVO = "ajustes.json"

# Con qué armónica arranca la app si nadie eligió nada.
FABRICA = {"tonalidad": "C", "posicion": None, "escala": None}


def _es_entero(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


def _valido(clave, valor):
    """Si `valor` sirve para `clave`. Lo que no se conoce, no sirve."""
    if clave == "microfono":
        return isinstance(valor, str)
    if clave == "umbral":
        return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
                and 0 < valor < 1)
    if clave == "tonalidad":
        return valor in tablas.TONALIDADES
    if clave == "posicion":
        return valor is None or (_es_entero(valor) and valor in tablas.POSICIONES_CON_TABLA)
    if clave == "escala":
        return valor is None or valor in tablas.ESCALAS_INTERVALOS
    if clave == "primeros_pasos":
        return isinstance(valor, bool)
    return False


def cargar(ruta=None):
    """
    Lo guardado, solo lo que sigue siendo válido. Un archivo que falta o que
    está roto da {}: la app arranca igual, con la fábrica.
    """
    ruta = ruta or ARCHIVO
    if not os.path.isfile(ruta):
        return {}
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError):
        return {}
    if not isinstance(datos, dict):
        return {}
    return {clave: valor for clave, valor in datos.items() if _valido(clave, valor)}


def guardar(cambios, ruta=None):
    """
    Guarda lo que viene, pisando solo eso. Algo inválido es un error y no se
    guarda nada: mejor ruidoso que un ajuste a medias.
    """
    for clave, valor in cambios.items():
        if not _valido(clave, valor):
            raise ValueError(f"Ajuste inválido: {clave} = {valor!r}")
    ruta = ruta or ARCHIVO
    actuales = cargar(ruta)
    actuales.update(cambios)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(actuales, archivo, indent=2, ensure_ascii=False)
    return actuales


def valores_de_arranque(guardados, tonalidad=None, posicion=None, escala=None):
    """
    Con qué armónica, posición y escala arrancar. Lo que viene en los
    argumentos es lo escrito en la línea de comandos (None = no se escribió);
    si no, lo guardado; si no, la fábrica.
    """
    escritos = {"tonalidad": tonalidad, "posicion": posicion, "escala": escala}
    return {clave: (escritos[clave] if escritos[clave] is not None
                    else guardados.get(clave, FABRICA[clave]))
            for clave in FABRICA}


def aplicar_a_config(guardados, modulo=None):
    """
    El umbral guardado pisa el de config.py. Se escribe sobre el módulo, así
    todo lo que lee config.UMBRAL_VOLUMEN_RMS (el hilo de audio, la barra de
    nivel, el análisis de archivos) usa el medido sin enterarse.
    """
    modulo = modulo or config
    if "umbral" in guardados:
        modulo.UMBRAL_VOLUMEN_RMS = guardados["umbral"]


def resolver_microfono(nombre, entradas):
    """
    El número del micrófono que se llama `nombre`, o None si no está
    conectado. Misma regla que la lista de Ajustes: Windows repite cada
    micrófono una vez por API de audio, y vale el primero.
    """
    buscado = (nombre or "").strip().lower()
    if not buscado:
        return None
    for numero, nombre_de_la_entrada, _canales in entradas:
        if nombre_de_la_entrada.strip().lower() == buscado:
            return numero
    return None
```

Y en `.gitignore`, al final:

```
# Lo que la app guarda al usarla desde el repo (en la instalada va a Documentos\Armonica)
ajustes.json
registro.txt
```

- [ ] **Step 4: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ajustes.py -v`
Expected: 17 passed.

- [ ] **Step 5: Commit**

```bash
git add armonica/ajustes.py tests/test_ajustes.py .gitignore
git commit -m "Lo elegido en Ajustes se guarda en ajustes.json, con el microfono por nombre" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: El servidor arranca con lo guardado y guarda lo que cambia

**Files:**
- Modify: `armonica/servidor.py` (imports; `EstadoCompartido.__init__`; nuevas `microfono_guardado` y `nombre_del_microfono`; `_listar_dispositivos`; `_cambiar_configuracion`; `arrancar`)
- Modify: `main.py` (nueva `_explicitos_para_la_web`; rama `--web` de `main`)
- Modify: `armonica/web/app.js` (`cargarAjustes`: mostrar el aviso)
- Modify: `tests/test_servidor.py` (fixture `servidor_andando` aislada; tests nuevos)
- Create: `tests/test_main.py`

**Interfaces:**
- Consumes: todo `armonica/ajustes.py` (Task 1).
- Produces:
  - `servidor.microfono_guardado(guardados, listar=None) -> (int | None, str)` (número y aviso)
  - `servidor.nombre_del_microfono(numero, listar=None) -> str | None` (`""` = el de Windows, None = no se sabe)
  - `EstadoCompartido.aviso_microfono: str`
  - `/api/dispositivos` devuelve además `"aviso"`.
  - `servidor.arrancar(tonalidad=None, posicion=None, escala=None, puerto=8000, abrir_navegador=True)`: None = no vino.
  - `main._explicitos_para_la_web(argv) -> {"tonalidad", "posicion", "escala"}`
  - La fixture `servidor_andando` ahora pide `tmp_path, monkeypatch` y pone `ajustes.ARCHIVO` en `tmp_path / "ajustes.json"`.

- [ ] **Step 1: Aislar la fixture y escribir los tests que fallan**

En `tests/test_servidor.py`, cambiar el import de armonica para sumar `ajustes` y `microfono`:

```python
from armonica import (ajustes, audio, clases, coach, exportacion, frases, mapeo,
                      microfono, plan, segmentacion, servidor)
```

Cambiar la firma y el comienzo de la fixture `servidor_andando`:

```python
@pytest.fixture
def servidor_andando(tmp_path, monkeypatch):
    """
    Levanta el servidor en un puerto que elige el sistema, y lo apaga al final.

    El puerto 0 significa "el que esté libre": así dos tests en paralelo no
    chocan, y tampoco molestamos si tenés la app abierta en el 8000. Lo que
    se elige en Ajustes va a un ajustes.json temporal, nunca al del repo.
    """
    monkeypatch.setattr(ajustes, "ARCHIVO", str(tmp_path / "ajustes.json"))
    servidor.Manejador.estado = servidor.EstadoCompartido("C", 12, "blues_mayor")
```

(el resto de la fixture queda igual).

Agregar, después de `test_no_se_puede_cambiar_la_configuracion_mientras_graba`:

```python
def test_lo_que_se_elige_en_ajustes_queda_guardado(servidor_andando, tmp_path, monkeypatch):
    """
    Armónica, posición, escala y micrófono van a ajustes.json. El micrófono
    por NOMBRE: el número cambia al enchufar otro aparato.
    """
    monkeypatch.setattr(microfono, "listar_dispositivos",
                        lambda: [(3, "Micrófono (USB Audio) ", 1)])
    respuesta = mandar(servidor_andando, "/api/configuracion", {
        "tonalidad": "A", "posicion": 2, "escala": "blues_mayor", "dispositivo": 3})
    assert respuesta["ok"] is True
    assert ajustes.cargar(str(tmp_path / "ajustes.json")) == {
        "tonalidad": "A", "posicion": 2, "escala": "blues_mayor",
        "microfono": "Micrófono (USB Audio)"}


def test_el_microfono_guardado_se_busca_por_nombre():
    lista = lambda: [(7, "Micrófono (USB Audio)", 1)]  # noqa: E731
    assert servidor.microfono_guardado({}, lista) == (config.DISPOSITIVO_ENTRADA, "")
    assert servidor.microfono_guardado({"microfono": ""}, lista) == (None, "")
    assert servidor.microfono_guardado({"microfono": "Micrófono (USB Audio)"}, lista) == (7, "")
    numero, aviso = servidor.microfono_guardado({"microfono": "Cámara HD"}, lista)
    assert numero is None
    assert "Cámara HD" in aviso and "no está conectado" in aviso


def test_el_nombre_del_microfono_para_guardarlo():
    lista = lambda: [(7, " Micrófono (USB Audio) ", 1)]  # noqa: E731
    assert servidor.nombre_del_microfono(None, lista) == ""
    assert servidor.nombre_del_microfono(7, lista) == "Micrófono (USB Audio)"
    assert servidor.nombre_del_microfono(9, lista) is None


def test_la_lista_de_microfonos_trae_el_aviso(servidor_andando, monkeypatch):
    monkeypatch.setattr(microfono, "listar_dispositivos", lambda: [])
    servidor.Manejador.estado.aviso_microfono = "El micrófono que elegiste no está conectado"
    assert traer_json(servidor_andando, "/api/dispositivos")["aviso"] == \
        "El micrófono que elegiste no está conectado"
```

Crear `tests/test_main.py`:

```python
"""
Tests de main.py — lo que no es de ningún módulo: cómo se arranca.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_main.py -v
"""

import main


def test_para_la_web_solo_cuenta_lo_escrito():
    """
    El "C" por defecto de --tonalidad no puede pisar la armónica elegida en
    Ajustes: solo cuenta lo que se escribió.
    """
    assert main._explicitos_para_la_web(["--web"]) == \
        {"tonalidad": None, "posicion": None, "escala": None}
    assert main._explicitos_para_la_web(["--web", "--tonalidad", "A", "--posicion", "2"]) == \
        {"tonalidad": "A", "posicion": 2, "escala": None}
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py tests/test_main.py -k "ajustes or microfono or aviso or web" -v`
Expected: FAIL. `test_lo_que_se_elige...` con `{} != {...}`, los otros con `AttributeError: module 'armonica.servidor' has no attribute 'microfono_guardado'` / `nombre_del_microfono`, `KeyError: 'aviso'`, y `AttributeError: module 'main' has no attribute '_explicitos_para_la_web'`.

- [ ] **Step 3: Implementar en el servidor**

En `armonica/servidor.py`, sumar `ajustes` al primer import de armonica:

```python
from armonica import ajustes, canciones, canciones_ajustes, compas_uno, imagenes, sobre_la_base
```

En `EstadoCompartido.__init__`, justo después de `self.dispositivo = config.DISPOSITIVO_ENTRADA`:

```python
        # Si el micrófono guardado en Ajustes no está conectado al arrancar,
        # se usa el de Windows y esto lo dice en Ajustes.
        self.aviso_microfono = ""
```

Agregar estas dos funciones justo antes de `def encender_microfono(clase):`:

```python
def microfono_guardado(guardados, listar=None):
    """
    El número del micrófono guardado en ajustes.json y, si no está
    conectado, el aviso para Ajustes. Sin nada guardado manda config.py.
    """
    if "microfono" not in guardados:
        return config.DISPOSITIVO_ENTRADA, ""
    nombre = guardados["microfono"]
    if not nombre:
        return None, ""
    if listar is None:
        from armonica import microfono
        listar = microfono.listar_dispositivos
    try:
        entradas = listar()
    except Exception:      # noqa: BLE001
        return None, "No pude ver la lista de micrófonos; uso el de Windows."
    numero = ajustes.resolver_microfono(nombre, entradas)
    if numero is None:
        return None, f"El micrófono que elegiste ({nombre}) no está conectado; uso el de Windows."
    return numero, ""


def nombre_del_microfono(numero, listar=None):
    """
    El nombre del micrófono número `numero`, para guardarlo: "" si es el de
    Windows, None si no aparece en la lista (entonces no se guarda nada).
    """
    if numero is None:
        return ""
    if listar is None:
        from armonica import microfono
        listar = microfono.listar_dispositivos
    try:
        entradas = listar()
    except Exception:      # noqa: BLE001
        return None
    for otro, nombre, _canales in entradas:
        if otro == numero:
            return nombre.strip()
    return None
```

En `_listar_dispositivos`, el `return` final pasa a ser:

```python
        return {
            "ok": True,
            "dispositivos": salida,
            "elegido": type(self).estado.dispositivo,
            "aviso": type(self).estado.aviso_microfono,
        }
```

En `_cambiar_configuracion`, reemplazar el bloque final (desde el comentario `# El hilo de audio se reinicia SIEMPRE` hasta el `return`) por:

```python
        # El hilo de audio se reinicia SIEMPRE, cambies lo que cambies. Abrio
        # el microfono viejo y no lo va a soltar solo, y ademas armo su tabla
        # de notas una sola vez al arrancar: si cambiaste de armonica y no lo
        # reiniciamos, sigue transcribiendo con la anterior.
        if clase.audio_automatico:
            apagar_microfono(clase)
            encender_microfono(clase)

        # Y queda guardado para la proxima vez que se abra la app.
        cambios = {"tonalidad": estado.tonalidad, "posicion": estado.posicion,
                   "escala": estado.escala}
        if "dispositivo" in peticion:
            nombre = nombre_del_microfono(estado.dispositivo)
            if nombre is not None:
                cambios["microfono"] = nombre
            estado.aviso_microfono = ""
        ajustes.guardar(cambios)

        return {"ok": True, "inicio": self._datos_iniciales()}
```

Reemplazar el comienzo de `arrancar` (firma, docstring y las dos primeras líneas) por:

```python
def arrancar(tonalidad=None, posicion=None, escala=None, puerto=8000,
             abrir_navegador=True):
    """
    Levanta el servidor y bloquea hasta que lo cortes con Ctrl+C.

    tonalidad, posicion y escala en None quieren decir "no vinieron": manda
    lo guardado en Ajustes (ajustes.json) y, si no hay nada, la fabrica.
    """
    guardados = ajustes.cargar()
    ajustes.aplicar_a_config(guardados)
    valores = ajustes.valores_de_arranque(guardados, tonalidad, posicion, escala)
    tonalidad, posicion, escala = valores["tonalidad"], valores["posicion"], valores["escala"]

    Manejador.estado = EstadoCompartido(tonalidad, posicion, escala)
    Manejador.estado.dispositivo, Manejador.estado.aviso_microfono = \
        microfono_guardado(guardados)

    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
```

(el resto de `arrancar` queda igual).

- [ ] **Step 4: Implementar en `main.py`**

Agregar, justo antes de `def main():`:

```python
def _explicitos_para_la_web(argv):
    """
    La armónica, posición y escala que se escribieron en la línea de
    comandos, y solo esas: lo que no se escribió queda en None para que
    mande lo guardado en Ajustes. Si no, el "C" por defecto de --tonalidad
    pisaría siempre la armónica elegida en pantalla.
    """
    parser = crear_parser()
    parser.set_defaults(tonalidad=None, posicion=None, escala=None)
    escritos = parser.parse_args(argv)
    return {"tonalidad": escritos.tonalidad, "posicion": escritos.posicion,
            "escala": escritos.escala}
```

Y en `main()`, la rama `--web` pasa a ser:

```python
    if argumentos.web:
        from armonica import servidor
        return servidor.arrancar(puerto=argumentos.puerto,
                                 **_explicitos_para_la_web(sys.argv[1:]))
```

- [ ] **Step 5: Mostrar el aviso en Ajustes**

En `armonica/web/app.js`, al final de `cargarAjustes()`, reemplazar:

```js
  if (!datos.ok) {
    document.getElementById("estado-microfono").textContent =
      datos.motivo || "no pude leer la lista de micr\u00f3fonos";
  }
```

por:

```js
  if (!datos.ok) {
    document.getElementById("estado-microfono").textContent =
      datos.motivo || "no pude leer la lista de micr\u00f3fonos";
  } else if (datos.aviso) {
    document.getElementById("estado-microfono").textContent = datos.aviso;
  }
```

- [ ] **Step 6: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ajustes.py tests/test_main.py tests/test_servidor.py -q`
Expected: todo pasa salvo, a lo sumo, `test_la_lista_de_canciones_trae_la_ficha_para_la_armonica_puesta` (falla conocida, ver Global Constraints).

- [ ] **Step 7: Commit**

```bash
git add armonica/servidor.py main.py armonica/web/app.js tests/test_servidor.py tests/test_main.py
git commit -m "La app arranca con lo elegido en Ajustes y lo guarda cuando cambia" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Un puerto para una sola app, `/api/hola` y la versión

**Files:**
- Create: `VERSION`
- Create: `armonica/version.py`
- Modify: `armonica/servidor.py` (`import socket`; `ServidorExclusivo`; `PuertoOcupado`; `enlazar`; `Manejador.empaquetada`; GET `/api/hola`; `_datos_iniciales`; `arrancar`)
- Modify: `main.py` (rama `--web`: puerto ocupado)
- Modify: `tests/test_servidor.py`

**Interfaces:**
- Consumes: `arrancar` de Task 2.
- Produces:
  - `version.version() -> str` (contenido de `VERSION`, sin espacios)
  - `servidor.ServidorExclusivo(ThreadingHTTPServer)` (sin `SO_REUSEADDR`, con `SO_EXCLUSIVEADDRUSE` en Windows)
  - `servidor.PuertoOcupado(OSError)`
  - `servidor.enlazar(puertos) -> ServidorExclusivo` (el primero libre; si no, `PuertoOcupado`)
  - `Manejador.empaquetada: bool = False`
  - `GET /api/hola` → `{"app": "armonica", "version": "0.1.0"}`
  - `/api/inicio` suma `"version"` y `"empaquetada"`.
  - `servidor.arrancar(tonalidad=None, posicion=None, escala=None, puerto=8000, abrir_navegador=True, empaquetada=False, puertos=None)`

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_servidor.py`, sumar `import socket` y `import re` a los imports de arriba, y `version` al import de armonica:

```python
from armonica import (ajustes, audio, clases, coach, exportacion, frases, mapeo,
                      microfono, plan, segmentacion, servidor, version)
```

En la fixture `servidor_andando`, después de `servidor.Manejador.ultima_comparacion = None`:

```python
    servidor.Manejador.empaquetada = False
```

Agregar al final del archivo:

```python
# =============================================================================
# Una sola app por puerto, y quién es
# =============================================================================

def test_un_puerto_ocupado_no_se_comparte():
    """
    En Windows, HTTPServer pide SO_REUSEADDR y una segunda app se quedaba con
    el mismo puerto sin ningún error. Ahora un puerto ocupado es un error.
    """
    ocupante = socket.socket()
    ocupante.bind(("127.0.0.1", 0))
    ocupante.listen()
    puerto = ocupante.getsockname()[1]
    try:
        with pytest.raises(servidor.PuertoOcupado):
            servidor.enlazar([puerto])
    finally:
        ocupante.close()


def test_si_el_primero_esta_ocupado_usa_el_siguiente():
    ocupante = socket.socket()
    ocupante.bind(("127.0.0.1", 0))
    ocupante.listen()
    puerto = ocupante.getsockname()[1]
    try:
        libre = servidor.enlazar([puerto, 0])
        try:
            assert libre.server_address[1] != puerto
        finally:
            libre.server_close()
    finally:
        ocupante.close()


def test_dos_apps_no_comparten_el_puerto():
    primera = servidor.enlazar([0])
    try:
        with pytest.raises(servidor.PuertoOcupado):
            servidor.enlazar([primera.server_address[1]])
    finally:
        primera.server_close()


def test_hola_dice_que_es_esta_app(servidor_andando):
    assert traer_json(servidor_andando, "/api/hola") == \
        {"app": "armonica", "version": version.version()}


def test_la_version_sale_del_archivo():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, "VERSION"), encoding="utf-8") as archivo:
        assert version.version() == archivo.read().strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.version())


def test_inicio_dice_la_version_y_si_es_la_instalada(servidor_andando):
    datos = traer_json(servidor_andando, "/api/inicio")
    assert datos["version"] == version.version()
    assert datos["empaquetada"] is False
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -k "puerto or apps or hola or version" -v`
Expected: ERROR de colección con `ImportError: cannot import name 'version' from 'armonica'`.

- [ ] **Step 3: La versión**

Crear `VERSION` (una línea):

```
0.1.0
```

Crear `armonica/version.py`:

```python
"""
version.py — Qué versión de la app es esta.

Sale del archivo VERSION de la raíz, que es lo único que hay que cambiar al
sacar una nueva: lo lee la pantalla (Ajustes), /api/hola y el armado del
instalador para el nombre del .exe. En la versión instalada VERSION queda al
lado de la carpeta armonica\\, igual que en el repo.
"""

import os

RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")


def version():
    try:
        with open(RUTA, encoding="utf-8") as archivo:
            return archivo.read().strip()
    except OSError:
        return "sin versión"
```

- [ ] **Step 4: El puerto exclusivo, `/api/hola` y lo que dice `/api/inicio`**

En `armonica/servidor.py`, sumar `import socket` a los imports de la biblioteca estándar y `version` al segundo import de armonica:

```python
from armonica import (audio, clases, coach, exportacion, frases, mapeo, plan, posiciones,
                      prioridades, resumen as modulo_resumen, ritmo,
                      segmentacion, tablas, teoria, tono, transcripcion, version)
```

Agregar justo antes de `def arrancar(`:

```python
class PuertoOcupado(OSError):
    """Ninguno de los puertos pedidos estaba libre."""


class ServidorExclusivo(ThreadingHTTPServer):
    """
    El servidor de la app, dueño exclusivo de su puerto.

    HTTPServer pide SO_REUSEADDR, y en Windows eso deja que una SEGUNDA app
    se enganche al mismo puerto sin ningún error: dos servidores, dos
    micrófonos abiertos, y el navegador hablando con cualquiera de los dos.
    Sin SO_REUSEADDR y con SO_EXCLUSIVEADDRUSE, un puerto ocupado falla al
    enlazar, que es lo que necesitan el lanzador (para probar el siguiente)
    y main.py (para decir que ya hay una abierta).
    """

    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def enlazar(puertos):
    """El servidor en el primer puerto libre de `puertos`."""
    puertos = list(puertos)
    for puerto in puertos:
        try:
            return ServidorExclusivo(("127.0.0.1", puerto), Manejador)
        except OSError:
            continue
    if len(puertos) == 1:
        raise PuertoOcupado(f"El puerto {puertos[0]} está ocupado.")
    raise PuertoOcupado(f"Los puertos del {puertos[0]} al {puertos[-1]} están ocupados.")
```

En la clase `Manejador`, junto a `audio_automatico = False`:

```python
    # Si es la versión instalada (la abre el lanzador): la pantalla usa los
    # textos para el profe, sin carpetas ni comandos.
    empaquetada = False
```

En `do_GET`, después de la línea de `/api/inicio`:

```python
        if self.path == "/api/hola":
            return self._responder_json({"app": "armonica", "version": version.version()})
```

En `_datos_iniciales`, sumar al diccionario que devuelve (después de `"corrida": ...`):

```python
            "version": version.version(),
            "empaquetada": type(self).empaquetada,
```

Reemplazar la firma de `arrancar` y la creación del servidor (de Task 2) por:

```python
def arrancar(tonalidad=None, posicion=None, escala=None, puerto=8000,
             abrir_navegador=True, empaquetada=False, puertos=None):
    """
    Levanta el servidor y bloquea hasta que lo cortes con Ctrl+C.

    tonalidad, posicion y escala en None quieren decir "no vinieron": manda
    lo guardado en Ajustes (ajustes.json) y, si no hay nada, la fabrica.
    `puertos` es la lista que prueba el lanzador; sin ella, solo `puerto`.
    Si no hay ninguno libre, PuertoOcupado.
    """
    guardados = ajustes.cargar()
    ajustes.aplicar_a_config(guardados)
    valores = ajustes.valores_de_arranque(guardados, tonalidad, posicion, escala)
    tonalidad, posicion, escala = valores["tonalidad"], valores["posicion"], valores["escala"]

    Manejador.estado = EstadoCompartido(tonalidad, posicion, escala)
    Manejador.estado.dispositivo, Manejador.estado.aviso_microfono = \
        microfono_guardado(guardados)
    Manejador.empaquetada = empaquetada

    servidor = enlazar(puertos or [puerto])
    direccion = f"http://127.0.0.1:{servidor.server_address[1]}"
```

(se borra la línea vieja `direccion = f"http://127.0.0.1:{puerto}"`; el resto queda igual).

En `main.py`, la rama `--web`:

```python
    if argumentos.web:
        from armonica import servidor
        try:
            return servidor.arrancar(puerto=argumentos.puerto,
                                     **_explicitos_para_la_web(sys.argv[1:]))
        except servidor.PuertoOcupado as error:
            print(f"  {error} ¿Ya está abierta la app? Cerrala, o usá --puerto con otro número.")
            return 1
```

- [ ] **Step 5: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py tests/test_main.py -q`
Expected: todo pasa (salvo la falla conocida del timeout).

- [ ] **Step 6: Commit**

```bash
git add VERSION armonica/version.py armonica/servidor.py main.py tests/test_servidor.py
git commit -m "Un puerto para una sola app, /api/hola dice quien es, y la version en VERSION" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Medir el ruido desde Ajustes

**Files:**
- Modify: `armonica/microfono.py` (nueva `resumen_de_ruido`; `medir_ruido_de_fondo` la usa)
- Modify: `armonica/servidor.py` (`SEGUNDOS_DE_RUIDO`; `EstadoCompartido`: `_ruido`, `empezar_a_medir_ruido`, `anotar_volumen`, `terminar_de_medir_ruido`; `_una_vuelta_de_microfono`; POST `/api/medir-ruido`)
- Modify: `armonica/web/index.html` (sección El micrófono)
- Modify: `armonica/web/app.js` (`medirRuido`, `configurarLaApp`, `DOMContentLoaded`, aviso del resumen)
- Modify: `tests/test_microfono.py`, `tests/test_servidor.py`

**Interfaces:**
- Consumes: `ajustes.guardar` (Task 1); fixture aislada (Task 2).
- Produces:
  - `microfono.resumen_de_ruido(niveles) -> (mediana, pico)` o `(None, None)`
  - `EstadoCompartido.empezar_a_medir_ruido()`, `.anotar_volumen(volumen)`, `.terminar_de_medir_ruido() -> list`
  - `servidor.SEGUNDOS_DE_RUIDO = 3.0`
  - `POST /api/medir-ruido` → `{"ok": True, "umbral", "pico", "mediana"}` o `{"ok": False, "motivo"}`
  - JS: `medirRuido(donde)` (la usa también Task 8) y `configurarLaApp()` (Tasks 6 y 8 le suman cosas).

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_microfono.py`, al final:

```python
def test_el_resumen_del_ruido_es_la_mediana_y_el_pico():
    assert microfono.resumen_de_ruido([0.003, 0.001, 0.002]) == (0.002, 0.003)
    assert microfono.resumen_de_ruido([]) == (None, None)
```

En `tests/test_servidor.py`, sumar `import time` a los imports de arriba y al final del archivo:

```python
# =============================================================================
# Medir el ruido
# =============================================================================

def test_medir_el_ruido_guarda_el_umbral(servidor_andando, tmp_path, monkeypatch):
    """
    Escucha lo que entra por el micrófono que ya está abierto (acá, un hilo
    que hace de micrófono) y deja el umbral en tres veces el pico del ruido,
    en config y en ajustes.json.
    """
    monkeypatch.setattr(servidor, "SEGUNDOS_DE_RUIDO", 0.3)
    monkeypatch.setattr(config, "UMBRAL_VOLUMEN_RMS", config.UMBRAL_VOLUMEN_RMS)
    estado = servidor.Manejador.estado
    estado.escuchando = True

    def microfono_falso():
        fin = time.monotonic() + 1.0
        while time.monotonic() < fin:
            for volumen in (0.001, 0.002):
                estado.anotar_volumen(volumen)
            time.sleep(0.01)

    hilo = threading.Thread(target=microfono_falso, daemon=True)
    hilo.start()
    respuesta = mandar(servidor_andando, "/api/medir-ruido")
    hilo.join()

    assert respuesta["ok"] is True
    assert respuesta["pico"] == 0.002
    assert respuesta["umbral"] == 0.006
    assert config.UMBRAL_VOLUMEN_RMS == 0.006
    assert ajustes.cargar(str(tmp_path / "ajustes.json"))["umbral"] == 0.006


def test_sin_microfono_abierto_no_se_mide(servidor_andando):
    servidor.Manejador.estado.escuchando = False
    respuesta = mandar(servidor_andando, "/api/medir-ruido")
    assert respuesta["ok"] is False
    assert "micrófono" in respuesta["motivo"]


def test_si_no_llega_audio_no_se_inventa_un_umbral(servidor_andando, monkeypatch):
    monkeypatch.setattr(servidor, "SEGUNDOS_DE_RUIDO", 0.1)
    servidor.Manejador.estado.escuchando = True
    respuesta = mandar(servidor_andando, "/api/medir-ruido")
    assert respuesta["ok"] is False
    assert "audio" in respuesta["motivo"]
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_microfono.py tests/test_servidor.py -k "resumen or ruido or umbral" -v`
Expected: FAIL con `AttributeError: module 'armonica.microfono' has no attribute 'resumen_de_ruido'` y, en el servidor, `HTTPError 404` o `AttributeError: ... 'anotar_volumen'`.

- [ ] **Step 3: `resumen_de_ruido` en `armonica/microfono.py`**

Reemplazar `medir_ruido_de_fondo` por estas dos funciones:

```python
def medir_ruido_de_fondo(segundos=3.0, dispositivo=None):
    """
    Escucha sin que toques nada y devuelve (mediana, pico) del ruido.

    Es la calibración más importante de todas: el umbral de volumen tiene que
    quedar por encima del ruido de tu habitación y por debajo de tu nota más
    floja. Medirlo es mucho mejor que adivinarlo.
    """
    niveles = []
    with CapturaMicrofono(dispositivo=dispositivo, guardar_audio=False) as captura:
        for _, ventana in captura.ventanas(tiempo_maximo_seg=segundos):
            niveles.append(audio.volumen_rms(ventana))
    return resumen_de_ruido(niveles)


def resumen_de_ruido(niveles):
    """
    (mediana, pico) de los volúmenes medidos en silencio, o (None, None) si
    no llegó nada. Lo usan --calibrar y el botón Medir el ruido de Ajustes.
    """
    if not niveles:
        return None, None
    ordenados = sorted(niveles)
    return ordenados[len(ordenados) // 2], ordenados[-1]
```

- [ ] **Step 4: La medición en el servidor**

En `armonica/servidor.py`, después de `ESPERA_ENTRE_INTENTOS = 0.5`:

```python
# Cuánto escucha "Medir el ruido". Lo mismo que --calibrar.
SEGUNDOS_DE_RUIDO = 3.0
```

En `EstadoCompartido.__init__`, junto a `self.aviso_microfono = ""`:

```python
        # Mientras se mide el ruido, el hilo de audio anota acá el volumen de
        # cada ventana. None = no se está midiendo.
        self._ruido = None
```

Agregar estos métodos a `EstadoCompartido` (después de `actualizar`):

```python
    # --- Medir el ruido, con el micrófono que ya está abierto ---

    def empezar_a_medir_ruido(self):
        with self._candado:
            self._ruido = []

    def anotar_volumen(self, volumen):
        """Lo llama el hilo de audio en cada ventana; no hace nada si no se mide."""
        with self._candado:
            if self._ruido is not None:
                self._ruido.append(volumen)

    def terminar_de_medir_ruido(self):
        with self._candado:
            niveles, self._ruido = self._ruido or [], None
        return niveles
```

En `_una_vuelta_de_microfono`, justo después de `volumen = audio.volumen_rms(ventana)`:

```python
            estado.anotar_volumen(volumen)
```

En `do_POST`, junto a las otras rutas JSON (por ejemplo después de `/api/configuracion`):

```python
        if self.path == "/api/medir-ruido":
            return self._responder_json(self._medir_ruido())
```

Y el método, después de `_cambiar_configuracion`:

```python
    def _medir_ruido(self):
        """
        Lo de --calibrar, desde la pantalla: escucha SEGUNDOS_DE_RUIDO en
        silencio con el micrófono que ya está abierto (abrir otro en el mismo
        aparato puede fallar en Windows) y deja el umbral en tres veces el
        pico del ruido. Queda en config para ya y en ajustes.json para la
        próxima vez.
        """
        from armonica import microfono

        estado = type(self).estado
        if estado.grabando:
            return {"ok": False, "motivo": "No se puede medir mientras grabás."}
        if not estado.escuchando:
            return {"ok": False,
                    "motivo": "El micrófono no está abierto: elegí uno arriba y probá de nuevo."}

        estado.empezar_a_medir_ruido()
        time.sleep(SEGUNDOS_DE_RUIDO)
        mediana, pico = microfono.resumen_de_ruido(estado.terminar_de_medir_ruido())
        if pico is None:
            return {"ok": False,
                    "motivo": "No llegó audio del micrófono. Probá con otro."}

        umbral = round(microfono.umbral_sugerido(pico), 4)
        config.UMBRAL_VOLUMEN_RMS = umbral
        ajustes.guardar({"umbral": umbral})
        return {"ok": True, "umbral": umbral, "pico": round(pico, 4),
                "mediana": round(mediana, 4)}
```

(Si `time` no está importado arriba en `servidor.py`, sumar `import time` a los imports de la biblioteca estándar.)

- [ ] **Step 5: El botón en Ajustes**

En `armonica/web/index.html`, en la sección "El micrófono", reemplazar el párrafo de ayuda y sumar el botón después de la barra (el párrafo nuevo saca además la anécdota de la cámara, que es de la máquina de Bruno):

```html
  <section>
    <h2>El micrófono</h2>
    <p class="ayuda">
      Windows tiene siempre varias entradas y la que viene elegida rara vez es
      la que querés (a veces es la de la cámara). Elegí una y soplá: la barra
      de abajo se tiene que mover. Si no se mueve, probá con otra.
    </p>
    <div class="controles">
      <select id="selector-microfono"></select>
      <span id="estado-microfono"></span>
    </div>
    <div class="barra-nivel ancha"><div id="barra-nivel-ajustes"></div>
      <div id="marca-umbral-ajustes"></div>
    </div>
    <div class="controles">
      <button id="boton-medir-ruido" class="secundario">Medir el ruido</button>
      <span id="resultado-ruido" class="ayuda"></span>
    </div>
    <p class="ayuda">
      Medir el ruido son tres segundos en silencio: la app escucha tu
      habitación y pone la rayita de la barra justo por encima. Lo que pasa la
      rayita es armónica; lo de abajo, ruido.
    </p>
  </section>
```

En `armonica/web/app.js`, después de `guardarAjustes()`:

```js
/* Medir el ruido: tres segundos en silencio, y el umbral queda justo por
 * encima. Lo usan Ajustes y los primeros pasos; `donde` es el renglon donde
 * se cuenta como salio. */
async function medirRuido(donde) {
  donde.textContent = "Midiendo: tres segundos en silencio\u2026";
  const respuesta = await pedir("/api/medir-ruido", { method: "POST" });
  if (!respuesta.ok) {
    donde.textContent = respuesta.motivo;
    return;
  }
  inicio.umbral_volumen = respuesta.umbral;
  marcarUmbral();
  donde.textContent = "Listo: la rayita qued\u00f3 justo encima del ruido de tu habitaci\u00f3n. " +
    "Toc\u00e1 una nota: la barra la tiene que pasar.";
}


/* Los botones de Ajustes que no son elegir algo. */
function configurarLaApp() {
  document.getElementById("boton-medir-ruido").addEventListener("click", () =>
    medirRuido(document.getElementById("resultado-ruido")));
}
```

En el `DOMContentLoaded` del principio, después de `configurarDestinos();`:

```js
  configurarLaApp();
```

Y en `mostrarResumen` (cerca de la línea 1116), el aviso que mandaba a la terminal:

```js
    contenedor.innerHTML = '<div class="aviso">No se detectó ninguna nota. ' +
      "Si el micrófono no engancha, medí el ruido en <strong>Ajustes</strong>.</div>";
```

- [ ] **Step 6: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_microfono.py tests/test_servidor.py -q`
Expected: todo pasa (salvo la falla conocida del timeout).

- [ ] **Step 7: Commit**

```bash
git add armonica/microfono.py armonica/servidor.py armonica/web/index.html armonica/web/app.js tests/test_microfono.py tests/test_servidor.py
git commit -m "Medir el ruido desde Ajustes, con el microfono que ya esta abierto" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: El micrófono se apaga solo si no hay ninguna página

**Files:**
- Modify: `armonica/servidor.py` (`SEGUNDOS_SIN_PAGINA`; `Manejador.conectados` y `candado_conexiones`; `_transmitir_estado`; nuevas `que_hacer_con_el_microfono`, `un_paso_del_vigia`, `vigilar_el_microfono`, `_pedir_parar`; `arrancar`)
- Modify: `tests/test_servidor.py`

**Interfaces:**
- Consumes: `encender_microfono`, `apagar_microfono` (existentes); `arrancar` de Task 3.
- Produces:
  - `Manejador.conectados: int`, `Manejador.candado_conexiones: threading.Lock`
  - `servidor.que_hacer_con_el_microfono(conectados, sin_nadie_desde, ahora, prendido, apagado_por_vigia, espera=SEGUNDOS_SIN_PAGINA) -> "apagar" | "prender" | None`
  - `servidor.un_paso_del_vigia(clase, puerto, memoria, ahora) -> "apagar" | "prender" | None` (`memoria`: dict con `sin_nadie_desde` y `apagado_por_vigia`)
  - `servidor.vigilar_el_microfono(clase, puerto, cada=1.0)` (bucle, en un hilo daemon)

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_servidor.py`, sumar `import types` a los imports. En la fixture `servidor_andando`, después de `servidor.Manejador.empaquetada = False`:

```python
    servidor.Manejador.conectados = 0
```

Al final del archivo:

```python
# =============================================================================
# El micrófono se apaga solo
# =============================================================================

def test_las_paginas_conectadas_se_cuentan(servidor_andando):
    respuesta = urllib.request.urlopen(servidor_andando + "/api/vivo", timeout=5)
    try:
        assert respuesta.readline().startswith(b"data:")
        assert servidor.Manejador.conectados == 1
    finally:
        respuesta.close()
    limite = time.monotonic() + 3
    while servidor.Manejador.conectados and time.monotonic() < limite:
        time.sleep(0.05)
    assert servidor.Manejador.conectados == 0


@pytest.mark.parametrize("conectados, desde, ahora, prendido, por_vigia, esperado", [
    (1, None, 100.0, True, False, None),        # hay una página: nada
    (0, 0.0, 30.0, True, False, None),          # sin página hace poco: espera
    (0, 0.0, 60.0, True, False, "apagar"),      # un minuto sin página: apaga
    (0, 0.0, 90.0, False, True, None),          # ya apagado: nada
    (1, None, 91.0, False, True, "prender"),    # vuelve una página: prende
    (1, None, 91.0, False, False, None),        # apagado por un error: no insiste
])
def test_que_hacer_con_el_microfono(conectados, desde, ahora, prendido, por_vigia, esperado):
    assert servidor.que_hacer_con_el_microfono(
        conectados, desde, ahora, prendido, por_vigia, espera=60.0) == esperado


class HiloFalso:
    def __init__(self, vivo):
        self.vivo = vivo

    def is_alive(self):
        return self.vivo


def test_el_vigia_corta_la_grabacion_y_apaga(monkeypatch):
    """
    Con la pestaña cerrada y grabando, nadie puede apretar Parar: el vigía lo
    aprieta (la grabación queda pendiente, como siempre) y suelta el
    micrófono. Cuando vuelve una página, lo prende.
    """
    llamadas = []
    monkeypatch.setattr(servidor, "_pedir_parar", lambda puerto: llamadas.append(("parar", puerto)))
    monkeypatch.setattr(servidor, "apagar_microfono", lambda clase: llamadas.append("apagar"))
    monkeypatch.setattr(servidor, "encender_microfono", lambda clase: llamadas.append("prender"))
    clase = types.SimpleNamespace(conectados=0, hilo_audio=HiloFalso(True),
                                  estado=types.SimpleNamespace(grabando=True))
    memoria = {"sin_nadie_desde": 0.0, "apagado_por_vigia": False}

    assert servidor.un_paso_del_vigia(clase, 8000, memoria, 30.0) is None
    assert servidor.un_paso_del_vigia(clase, 8000, memoria, 61.0) == "apagar"
    assert llamadas == [("parar", 8000), "apagar"]

    clase.conectados = 1
    clase.hilo_audio = HiloFalso(False)
    assert servidor.un_paso_del_vigia(clase, 8000, memoria, 62.0) == "prender"
    assert llamadas[-1] == "prender"
    assert memoria["apagado_por_vigia"] is False
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -k "conectadas or que_hacer or vigia" -v`
Expected: FAIL con `AttributeError: type object 'Manejador' has no attribute 'conectados'` (o `assert 0 == 1`) y `AttributeError: module 'armonica.servidor' has no attribute 'que_hacer_con_el_microfono'`.

- [ ] **Step 3: Contar las páginas**

En `armonica/servidor.py`, después de `SEGUNDOS_DE_RUIDO = 3.0`:

```python
# Cuánto se espera sin ninguna página abierta antes de soltar el micrófono.
SEGUNDOS_SIN_PAGINA = 60.0
```

En la clase `Manejador`, junto a `empaquetada = False`:

```python
    # Cuántas páginas están conectadas a /api/vivo. Con pythonw no hay
    # ventana que cerrar: si se cierra la pestaña, la app sigue y el
    # micrófono quedaría tomado. El vigía mira esto para soltarlo.
    conectados = 0
    candado_conexiones = threading.Lock()
```

Reemplazar el cuerpo de `_transmitir_estado` desde `self.send_response(200)` hasta el final por:

```python
        clase = type(self)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        with clase.candado_conexiones:
            clase.conectados += 1
        try:
            while True:
                datos = json.dumps(clase.estado.como_diccionario(), ensure_ascii=False)
                self.wfile.write(f"data: {datos}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(1.0 / REFRESCOS_POR_SEGUNDO)
        except ConnectionError:
            # El navegador cerró la pestaña. Es normal, no es un error. En
            # Windows llega como ConnectionAbortedError, que el except de
            # antes (BrokenPipe y ConnectionReset) no agarraba.
            pass
        finally:
            with clase.candado_conexiones:
                clase.conectados -= 1
```

(el `import time` local del principio del método se puede dejar o borrar; `time` ya está importado arriba).

- [ ] **Step 4: El vigía**

Agregar después de `apagar_microfono`:

```python
def que_hacer_con_el_microfono(conectados, sin_nadie_desde, ahora, prendido,
                               apagado_por_vigia, espera=SEGUNDOS_SIN_PAGINA):
    """
    La decisión del vigía, sin efectos: "apagar", "prender" o None.

    Solo prende lo que él apagó. Si el micrófono se cayó por un error, el
    hilo de audio ya reintentó y se rindió: insistir cada segundo no arregla
    nada y llena el registro.
    """
    if conectados > 0:
        return "prender" if apagado_por_vigia and not prendido else None
    if prendido and sin_nadie_desde is not None and ahora - sin_nadie_desde >= espera:
        return "apagar"
    return None


def _pedir_parar(puerto):
    """Aprieta Parar como lo haría la página: la grabación queda pendiente."""
    pedido = urllib.request.Request(f"http://127.0.0.1:{puerto}/api/terminar",
                                    data=b"{}", method="POST",
                                    headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=10):
            pass
    except OSError as error:
        print(f"  No pude cortar la grabación: {error}")


def un_paso_del_vigia(clase, puerto, memoria, ahora):
    """Una mirada del vigía. `memoria` guarda desde cuándo no hay nadie."""
    conectados = clase.conectados
    if conectados > 0:
        memoria["sin_nadie_desde"] = None
    elif memoria.get("sin_nadie_desde") is None:
        memoria["sin_nadie_desde"] = ahora
    prendido = clase.hilo_audio is not None and clase.hilo_audio.is_alive()
    accion = que_hacer_con_el_microfono(conectados, memoria["sin_nadie_desde"], ahora,
                                        prendido, memoria.get("apagado_por_vigia", False))
    if accion == "apagar":
        if clase.estado.grabando:
            _pedir_parar(puerto)
        apagar_microfono(clase)
        memoria["apagado_por_vigia"] = True
        print("  Ninguna página abierta hace un minuto: apagué el micrófono.")
    elif accion == "prender":
        encender_microfono(clase)
        memoria["apagado_por_vigia"] = False
    return accion


def vigilar_el_microfono(clase, puerto, cada=1.0):
    """El vigía: mira cada `cada` segundos. Corre en un hilo daemon."""
    memoria = {"sin_nadie_desde": time.monotonic(), "apagado_por_vigia": False}
    while True:
        time.sleep(cada)
        un_paso_del_vigia(clase, puerto, memoria, time.monotonic())
```

Sumar `import urllib.request` a los imports de la biblioteca estándar de `servidor.py` si no está.

En `arrancar`, reemplazar:

```python
    # El microfono se prende solo: podes tocar y ver sin apretar nada.
    Manejador.audio_automatico = True
    encender_microfono(Manejador)
```

por:

```python
    # El microfono se prende solo: podes tocar y ver sin apretar nada. Y se
    # apaga solo si un minuto no hay ninguna pagina mirando.
    Manejador.audio_automatico = True
    encender_microfono(Manejador)
    threading.Thread(target=vigilar_el_microfono,
                     args=(Manejador, servidor.server_address[1]), daemon=True).start()
```

- [ ] **Step 5: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -q`
Expected: todo pasa (salvo la falla conocida del timeout).

- [ ] **Step 6: Commit**

```bash
git add armonica/servidor.py tests/test_servidor.py
git commit -m "El microfono se suelta solo cuando no queda ninguna pagina abierta" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Cerrar la app desde la pantalla

**Files:**
- Modify: `armonica/servidor.py` (`Manejador.servidor_http`; nueva `apagar_todo`; POST `/api/apagar`; `arrancar`)
- Modify: `armonica/web/index.html` (sección "La app" en Ajustes)
- Modify: `armonica/web/app.js` (`cerrarLaApp`, `configurarLaApp`, `cargarAjustes`)
- Modify: `tests/test_servidor.py`

**Interfaces:**
- Consumes: `ServidorExclusivo` (Task 3), `apagar_microfono`.
- Produces:
  - `Manejador.servidor_http` (la instancia que corre, o None)
  - `servidor.apagar_todo(clase)`
  - `POST /api/apagar` → `{"ok": True}` (y el servidor termina) o `{"ok": False, "motivo"}` si está grabando
  - Sección HTML con `#version-app` y `#boton-cerrar-app` (Task 8 le suma `#boton-primeros-pasos`).

- [ ] **Step 1: Escribir los tests que fallan**

En la fixture `servidor_andando`, después de `servidor.Manejador.conectados = 0`:

```python
    servidor.Manejador.servidor_http = None
```

Al final de `tests/test_servidor.py`:

```python
# =============================================================================
# Cerrar la app
# =============================================================================

def test_cerrar_la_app_corta_el_servidor():
    """Con pythonw no hay ventana negra que cerrar: el botón es la forma."""
    servidor.Manejador.estado = servidor.EstadoCompartido("C", None, None)
    servidor.Manejador.hilo_audio = None
    servidor.Manejador.detener = None
    instancia = servidor.ServidorExclusivo(("127.0.0.1", 0), servidor.Manejador)
    servidor.Manejador.servidor_http = instancia
    hilo = threading.Thread(target=instancia.serve_forever, daemon=True)
    hilo.start()
    try:
        base = f"http://127.0.0.1:{instancia.server_address[1]}"
        assert mandar(base, "/api/apagar")["ok"] is True
        hilo.join(timeout=5)
        assert not hilo.is_alive()
    finally:
        servidor.Manejador.servidor_http = None
        instancia.server_close()


def test_no_se_cierra_mientras_graba(servidor_andando):
    servidor.Manejador.estado.grabando = True
    try:
        respuesta = mandar(servidor_andando, "/api/apagar")
    finally:
        servidor.Manejador.estado.grabando = False
    assert respuesta["ok"] is False
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -k "cerrar or no_se_cierra" -v`
Expected: FAIL con `HTTPError: HTTP Error 404` (la ruta no existe).

- [ ] **Step 3: Implementar**

En `armonica/servidor.py`, en `Manejador`, junto a `conectados = 0`:

```python
    # El servidor que está corriendo, para que "Cerrar la app" lo pueda
    # cortar. Lo pone arrancar().
    servidor_http = None
```

Después de `apagar_microfono`:

```python
def apagar_todo(clase):
    """
    Lo que hace "Cerrar la app": suelta el micrófono y corta el servidor.
    Corre en un hilo aparte y espera un poco, para que la respuesta llegue a
    la página antes de que se corte todo.
    """
    time.sleep(0.2)
    apagar_microfono(clase)
    if clase.servidor_http is not None:
        clase.servidor_http.shutdown()
```

En `do_POST`, junto a `/api/medir-ruido`:

```python
        if self.path == "/api/apagar":
            return self._responder_json(self._apagar())
```

Y el método, después de `_medir_ruido`:

```python
    def _apagar(self):
        """Cerrar la app. Grabando no: se perdería lo grabado."""
        clase = type(self)
        if clase.estado.grabando:
            return {"ok": False, "motivo": "Estás grabando: pará la grabación primero."}
        print("  Cerrada desde la pantalla.")
        threading.Thread(target=apagar_todo, args=(clase,), daemon=True).start()
        return {"ok": True}
```

En `arrancar`, justo después de `servidor = enlazar(puertos or [puerto])`:

```python
    Manejador.servidor_http = servidor
```

- [ ] **Step 4: La sección "La app" en Ajustes**

En `armonica/web/index.html`, al final del panel de Ajustes (después de la sección "Con qué estás tocando", antes de `</main>`):

```html
  <section>
    <h2>La app</h2>
    <p class="ayuda">Versión <span id="version-app"></span>.</p>
    <div class="controles">
      <button id="boton-cerrar-app" class="secundario">Cerrar la app</button>
    </div>
    <p class="ayuda">
      Cerrar la pestaña no cierra la app: sigue abierta por detrás, y al
      minuto suelta el micrófono. Con este botón se cierra del todo.
    </p>
  </section>
```

En `armonica/web/app.js`, después de `configurarLaApp`:

```js
async function cerrarLaApp() {
  if (!confirm("\u00bfCerrar la app? Para volver a abrirla, el \u00edcono Arm\u00f3nica del escritorio.")) return;
  const respuesta = await pedir("/api/apagar", { method: "POST" });
  if (!respuesta.ok) {
    alert(respuesta.motivo);
    return;
  }
  if (fuente) fuente.close();
  document.body.innerHTML = '<main class="panel"><section><h2>La app est\u00e1 cerrada</h2>' +
    '<p class="ayuda">Para volver a abrirla, el \u00edcono Arm\u00f3nica del escritorio.</p>' +
    "</section></main>";
}
```

En `configurarLaApp()`, sumar al final:

```js
  document.getElementById("boton-cerrar-app").addEventListener("click", cerrarLaApp);
```

Y al principio de `cargarAjustes()`:

```js
  document.getElementById("version-app").textContent = inicio.version || "";
```

- [ ] **Step 5: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -q`
Expected: todo pasa (salvo la falla conocida del timeout).

- [ ] **Step 6: Commit**

```bash
git add armonica/servidor.py armonica/web/index.html armonica/web/app.js tests/test_servidor.py
git commit -m "Cerrar la app desde Ajustes, y la version a la vista" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Abrir carpetas y páginas de Windows desde la pantalla

**Files:**
- Modify: `armonica/servidor.py` (`PAGINAS_DE_WINDOWS`; nuevas `carpetas_que_se_abren`, `abrir_en_windows`; POST `/api/abrir`)
- Modify: `armonica/web/app.js` (`botonAbrir`, `configurarAbrir`, `DOMContentLoaded`)
- Modify: `tests/test_servidor.py`

**Interfaces:**
- Produces:
  - `servidor.PAGINAS_DE_WINDOWS = {"sonido": "ms-settings:sound", "permisos-microfono": "ms-settings:privacy-microphone"}`
  - `servidor.carpetas_que_se_abren() -> {"frases", "sesiones", "canciones", "apuntes": ruta}`
  - `servidor.abrir_en_windows(destino)` (envuelve `os.startfile`; los tests la reemplazan)
  - `POST /api/abrir` con `{"que": clave}` → `{"ok": True}` o `{"ok": False, "motivo"}`. Solo claves de la lista cerrada.
  - JS: `botonAbrir(que, texto)` devuelve el HTML de un botón con `data-abrir`; un clic en cualquier `[data-abrir]` llama a `/api/abrir` (lo usan Tasks 8 y 9).

- [ ] **Step 1: Escribir los tests que fallan**

Al final de `tests/test_servidor.py`:

```python
# =============================================================================
# Abrir carpetas y páginas de Windows
# =============================================================================

def test_abre_la_configuracion_de_sonido_y_las_carpetas(servidor_andando, tmp_path, monkeypatch):
    abiertos = []
    monkeypatch.setattr(servidor, "abrir_en_windows", abiertos.append)
    monkeypatch.setattr(frases, "CARPETA_POR_DEFECTO", str(tmp_path / "frases"))

    assert mandar(servidor_andando, "/api/abrir", {"que": "sonido"})["ok"] is True
    assert mandar(servidor_andando, "/api/abrir", {"que": "frases"})["ok"] is True

    assert abiertos == ["ms-settings:sound", os.path.abspath(str(tmp_path / "frases"))]
    assert (tmp_path / "frases").is_dir()


@pytest.mark.parametrize("que", ["C:\\Windows", "..", "notepad", ""])
def test_solo_se_abre_lo_de_la_lista(servidor_andando, monkeypatch, que):
    abiertos = []
    monkeypatch.setattr(servidor, "abrir_en_windows", abiertos.append)
    assert mandar(servidor_andando, "/api/abrir", {"que": que})["ok"] is False
    assert abiertos == []
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -k "abre or solo_se_abre" -v`
Expected: FAIL con `AttributeError: <module 'armonica.servidor'> has no attribute 'abrir_en_windows'`.

- [ ] **Step 3: Implementar**

En `armonica/servidor.py`, después de `SEGUNDOS_SIN_PAGINA`:

```python
# Las páginas de Configuración de Windows que la app abre en los primeros
# pasos. Las abre el servidor y no el navegador, que preguntaría antes de
# abrir un "ms-settings:". Lista cerrada: nada que venga de la página se
# abre si no está acá.
PAGINAS_DE_WINDOWS = {
    "sonido": "ms-settings:sound",
    "permisos-microfono": "ms-settings:privacy-microphone",
}
```

Después de `apagar_todo`:

```python
def carpetas_que_se_abren():
    """Las carpetas del usuario que tienen botón "Abrir la carpeta"."""
    return {
        "frases": frases.CARPETA_POR_DEFECTO,
        "sesiones": exportacion.CARPETA_POR_DEFECTO,
        "canciones": canciones.carpeta_de_canciones(),
        "apuntes": clases.carpeta_de_clases(),
    }


def abrir_en_windows(destino):
    """Abre una carpeta o una página de Configuración como un doble clic."""
    os.startfile(destino)
```

En `do_POST`, junto a `/api/apagar`:

```python
        if self.path == "/api/abrir":
            return self._responder_json(self._abrir(cuerpo))
```

Y el método, después de `_apagar`:

```python
    def _abrir(self, peticion):
        """Una carpeta del usuario o una página de Windows, de la lista cerrada."""
        que = str((peticion or {}).get("que") or "")
        carpetas = carpetas_que_se_abren()
        if que in PAGINAS_DE_WINDOWS:
            destino = PAGINAS_DE_WINDOWS[que]
        elif que in carpetas:
            destino = os.path.abspath(carpetas[que])
            os.makedirs(destino, exist_ok=True)
        else:
            return {"ok": False, "motivo": "Eso no se abre desde acá."}
        try:
            abrir_en_windows(destino)
        except (AttributeError, OSError) as error:
            # AttributeError: os.startfile solo existe en Windows.
            print(f"  No pude abrir {destino}: {error}")
            return {"ok": False, "motivo": "No pude abrirlo."}
        return {"ok": True}
```

- [ ] **Step 4: El botón en la página**

En `armonica/web/app.js`, después de `cerrarLaApp`:

```js
/* "Abrir la carpeta" (o una pagina de Windows): un boton con data-abrir.
 * Lo abre el servidor; aca solo se avisa si no pudo. */
function botonAbrir(que, texto) {
  return '<button class="secundario chico" data-abrir="' + que + '">' +
    escapar(texto || "Abrir la carpeta") + "</button>";
}


function configurarAbrir() {
  document.addEventListener("click", async (evento) => {
    const boton = evento.target.closest("[data-abrir]");
    if (!boton) return;
    const respuesta = await pedir("/api/abrir", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ que: boton.dataset.abrir }),
    });
    if (!respuesta.ok) alert(respuesta.motivo);
  });
}
```

En el `DOMContentLoaded`, después de `configurarLaApp();`:

```js
  configurarAbrir();
```

- [ ] **Step 5: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -q`
Expected: todo pasa (salvo la falla conocida del timeout).

- [ ] **Step 6: Commit**

```bash
git add armonica/servidor.py armonica/web/app.js tests/test_servidor.py
git commit -m "Abrir las carpetas del usuario y la configuracion de sonido desde la pantalla" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Los primeros pasos

**Files:**
- Modify: `armonica/servidor.py` (POST `/api/primeros-pasos`; `_datos_iniciales`)
- Modify: `armonica/web/index.html` (cartel después de `</header>`; botón en "La app")
- Modify: `armonica/web/app.js` (`mostrarPrimerosPasos`, `configurarPrimerosPasos`, `DOMContentLoaded`)
- Modify: `armonica/web/estilo.css`
- Modify: `tests/test_servidor.py`

**Interfaces:**
- Consumes: `ajustes.cargar/guardar` (Task 1), `medirRuido` (Task 4), `[data-abrir]` (Task 7), `irASolapa` (existente en app.js).
- Produces:
  - `/api/inicio` suma `"primeros_pasos_hechos": bool`
  - `POST /api/primeros-pasos` con `{"hechos": bool}` → `{"ok": True}`

- [ ] **Step 1: Escribir el test que falla**

Al final de `tests/test_servidor.py`:

```python
# =============================================================================
# Los primeros pasos
# =============================================================================

def test_los_primeros_pasos_se_muestran_hasta_que_se_hacen(servidor_andando, tmp_path):
    assert traer_json(servidor_andando, "/api/inicio")["primeros_pasos_hechos"] is False
    assert mandar(servidor_andando, "/api/primeros-pasos", {"hechos": True})["ok"] is True
    assert traer_json(servidor_andando, "/api/inicio")["primeros_pasos_hechos"] is True
    assert ajustes.cargar(str(tmp_path / "ajustes.json"))["primeros_pasos"] is True
```

- [ ] **Step 2: Correrlo y ver que falla**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -k primeros_pasos -v`
Expected: FAIL con `KeyError: 'primeros_pasos_hechos'`.

- [ ] **Step 3: Implementar en el servidor**

En `_datos_iniciales`, sumar al diccionario:

```python
            "primeros_pasos_hechos": bool(ajustes.cargar().get("primeros_pasos", False)),
```

En `do_POST`, junto a `/api/abrir`:

```python
        if self.path == "/api/primeros-pasos":
            ajustes.guardar({"primeros_pasos": bool((cuerpo or {}).get("hechos"))})
            return self._responder_json({"ok": True})
```

- [ ] **Step 4: El cartel**

En `armonica/web/index.html`, justo después de `</header>`:

```html
<!-- Los primeros pasos: arriba de todo, sobre cualquier solapa, hasta que
     se aprieta Listo. Se vuelven a ver desde Ajustes. -->
<section id="primeros-pasos" class="primeros-pasos" hidden>
  <h2>Primeros pasos</h2>
  <ol>
    <li><strong>Elegí el micrófono.</strong> En Ajustes, el que tenés cerca
      de la boca. <button class="secundario chico" data-paso="ajustes">Ir a Ajustes</button></li>
    <li><strong>Sacá las mejoras de audio de Windows.</strong> Están pensadas
      para la voz y se comen la armónica. En la configuración de sonido,
      entrá a tu micrófono y apagá "Mejoras de audio".
      <button class="secundario chico" data-abrir="sonido">Abrir la configuración de sonido</button></li>
    <li><strong>Medí el ruido.</strong> Tres segundos en silencio.
      <button class="secundario chico" data-paso="medir">Medir el ruido</button>
      <span class="resultado-ruido ayuda"></span></li>
    <li><strong>Tocá.</strong> En En vivo, una nota cualquiera: la barra se
      tiene que mover y aparecer el agujero.
      <button class="secundario chico" data-paso="vivo">Ir a En vivo</button></li>
  </ol>
  <p class="ayuda">
    Si la barra no se mueve con nada, Windows puede estar bloqueando el
    micrófono: <button class="secundario chico" data-abrir="permisos-microfono">Abrir los permisos del micrófono</button>
    y prendé "Permitir que las aplicaciones de escritorio accedan al micrófono".
  </p>
  <button id="primeros-pasos-listo" class="principal">Listo</button>
</section>
```

En la sección "La app" de Ajustes (Task 6), dentro de su `<div class="controles">`, antes de "Cerrar la app":

```html
      <button id="boton-primeros-pasos" class="secundario">Ver los primeros pasos</button>
```

En `armonica/web/estilo.css`, al final:

```css
/* Los primeros pasos: arriba de todo, con el borde cobre de lo que hay que
 * hacer, hasta que se aprieta Listo. */
.primeros-pasos {
  position: relative;
  z-index: 1;
  max-width: 884px;
  margin: 18px auto 0;
  padding: 18px 22px;
  border: 1px solid var(--cobre);
  border-radius: 10px;
  background: var(--panel);
}
.primeros-pasos h2 { margin-top: 0; }
.primeros-pasos ol { margin: 8px 0 12px; padding-left: 22px; line-height: 1.6; }
.primeros-pasos li { margin-bottom: 10px; }
.primeros-pasos li button { margin-left: 6px; }
```

En `armonica/web/app.js`, después de `configurarAbrir`:

```js
/* Los primeros pasos: el cartel de arriba la primera vez. Cada paso lleva a
 * donde se hace; Listo lo guarda en ajustes.json. */
function mostrarPrimerosPasos(mostrar) {
  document.getElementById("primeros-pasos").hidden = !mostrar;
}


function configurarPrimerosPasos() {
  const caja = document.getElementById("primeros-pasos");
  caja.addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-paso]");
    if (!boton) return;
    if (boton.dataset.paso === "ajustes") irASolapa("ajustes");
    if (boton.dataset.paso === "vivo") irASolapa("vivo");
    if (boton.dataset.paso === "medir") medirRuido(caja.querySelector(".resultado-ruido"));
  });
  document.getElementById("primeros-pasos-listo").addEventListener("click", async () => {
    await pedir("/api/primeros-pasos", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hechos: true }),
    });
    inicio.primeros_pasos_hechos = true;
    mostrarPrimerosPasos(false);
  });
  document.getElementById("boton-primeros-pasos").addEventListener("click", () => {
    mostrarPrimerosPasos(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}
```

En el `DOMContentLoaded`: después de `configurarAbrir();` sumar `configurarPrimerosPasos();`, y después de `inicio = await pedir("/api/inicio");` (y la línea de `TOLERANCIA`) sumar:

```js
  mostrarPrimerosPasos(!inicio.primeros_pasos_hechos);
```

- [ ] **Step 5: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -q`
Expected: todo pasa (salvo la falla conocida del timeout).

- [ ] **Step 6: Commit**

```bash
git add armonica/servidor.py armonica/web/index.html armonica/web/app.js armonica/web/estilo.css tests/test_servidor.py
git commit -m "Los primeros pasos: microfono, mejoras de audio, ruido y tocar, hasta apretar Listo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Sin jerga de programador en la versión instalada

**Files:**
- Modify: `armonica/web/index.html` (Frases, Ajustes: apuntes y coach, Canciones)
- Modify: `armonica/web/app.js` (`esLaInstalada`, `DOMContentLoaded`, guardado de sesiones, apuntes vacíos, canciones vacías, origen de las clases, error del micrófono, explicación de la base)
- Modify: `armonica/web/estilo.css`
- Modify: `armonica/transcripcion.py` (dos avisos)
- Create: `tests/test_textos.py`
- Modify: `tests/test_transcripcion.py:206`

**Interfaces:**
- Consumes: `inicio.empaquetada` (Task 3), `botonAbrir` (Task 7).
- Produces: clases CSS `solo-desarrollo` (se oculta en la instalada) y `solo-empaquetada` (solo se ve en la instalada); `body.empaquetada`; JS `esLaInstalada()`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_textos.py`:

```python
"""
Tests de los textos que ve el usuario de la versión instalada.

El profe no tiene terminal, ni .env, ni sabe qué es material/: nada de eso
puede aparecer en pantalla. Lo que es solo para Bruno va adentro de un
elemento con la clase solo-desarrollo, que la versión instalada oculta.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_textos.py -v
"""

import os
from html.parser import HTMLParser

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(RAIZ, "armonica", "web", "index.html")
JERGA = (".env", "CARPETA_", "material/", "pip install", "python main.py", "winget")


class TextoVisible(HTMLParser):
    """Junta el texto que no está adentro de un elemento solo-desarrollo."""

    VACIOS = {"br", "img", "input", "meta", "link", "hr", "source"}

    def __init__(self):
        super().__init__()
        self.pila = []      # (etiqueta, oculto)
        self.textos = []

    def handle_starttag(self, etiqueta, atributos):
        if etiqueta in self.VACIOS:
            return
        clases = (dict(atributos).get("class") or "").split()
        afuera = self.pila[-1][1] if self.pila else False
        self.pila.append((etiqueta, afuera or "solo-desarrollo" in clases
                          or etiqueta in ("script", "style")))

    def handle_endtag(self, etiqueta):
        for i in range(len(self.pila) - 1, -1, -1):
            if self.pila[i][0] == etiqueta:
                del self.pila[i:]
                return

    def handle_data(self, datos):
        if not (self.pila and self.pila[-1][1]):
            self.textos.append(datos)


def test_la_pagina_instalada_no_muestra_jerga():
    with open(INDEX, encoding="utf-8") as archivo:
        html = archivo.read()
    lector = TextoVisible()
    lector.feed(html)
    visible = " ".join(lector.textos)
    for palabra in JERGA:
        assert palabra not in visible, f"{palabra!r} se ve en la versión instalada"


def test_ningun_aviso_manda_a_la_terminal():
    for ruta in (os.path.join(RAIZ, "armonica", "web", "app.js"),
                 os.path.join(RAIZ, "armonica", "transcripcion.py")):
        with open(ruta, encoding="utf-8") as archivo:
            assert "python main.py" not in archivo.read(), ruta
```

En `tests/test_transcripcion.py`, cambiar la última línea de ese test (línea 206):

```python
    assert "elegí esa al importarla" in avisos[0]
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_textos.py tests/test_transcripcion.py -v`
Expected: FAIL. `'.env' se ve en la versión instalada`, `python main.py` en `transcripcion.py`, y el aviso de `test_transcripcion` sin "elegí esa al importarla".

- [ ] **Step 3: El mecanismo**

En `armonica/web/estilo.css`, al final:

```css
/* Lo que es solo para quien usa la app desde el repo (carpetas, .env, el
 * coach) no se ve en la versión instalada, y al revés. */
body.empaquetada .solo-desarrollo,
body:not(.empaquetada) .solo-empaquetada { display: none !important; }
```

En `armonica/web/app.js`, después de `mostrarEncabezado`:

```js
/* Si es la version instalada (la abre el lanzador): sin carpetas, sin .env,
 * sin comandos. */
function esLaInstalada() {
  return Boolean(inicio && inicio.empaquetada);
}
```

En el `DOMContentLoaded`, después de `inicio = await pedir("/api/inicio");`:

```js
  document.body.classList.toggle("empaquetada", esLaInstalada());
```

- [ ] **Step 4: Los textos de `index.html`**

En Frases, el párrafo del audio:

```html
      Si no es un <code>.wav</code> lo convierte sola<span class="solo-desarrollo">,
      siempre que tengas ffmpeg instalado</span>. Si atrás hay una base sonando, el detector no puede
```

En Ajustes, la sección de los apuntes:

```html
  <section>
    <h2>Los apuntes de las clases</h2>
    <p class="ayuda solo-desarrollo">
      La solapa Aprendizaje lee los resúmenes de tus clases de
      <code>material/</code>, o de la carpeta que diga <code>CARPETA_CLASES</code>
      en el <code>.env</code>. Solo lee: nunca escribe ahí.
    </p>
    <p class="ayuda solo-empaquetada">
      La solapa Aprendizaje lee los resúmenes de tus clases de tu carpeta de
      apuntes. Solo lee: nunca escribe ahí.
      <button class="secundario chico" data-abrir="apuntes">Abrir la carpeta</button>
    </p>
    <p id="estado-clases" class="ayuda"></p>
  </section>
```

En Ajustes, la sección del coach pasa a `<section class="solo-desarrollo">` (el contenido queda igual).

En Canciones, el párrafo de arriba:

```html
    <p class="ayuda">
      <span class="solo-desarrollo">Una carpeta por canción en <code>material/canciones/</code> (o en la
      que diga <code>CARPETA_CANCIONES</code> en el <code>.env</code>),</span>
      <span class="solo-empaquetada">Una carpeta por canción en tu carpeta de canciones
      <button class="secundario chico" data-abrir="canciones">Abrir la carpeta</button>,</span>
      con lo que te manden: la base de Band-in-a-Box (<code>.sgu</code> o
      <code>.mgu</code>), los audios (m4a, mp3, mp4) y la tablatura en foto.
      De la base salen el tono, el tempo, el compás y el cifrado; los audios
      se escuchan acá y se pueden importar como frases. La app solo lee esa
      carpeta: nunca escribe ahí.
      <span id="canciones-estado"></span>
    </p>
```

Si el test de Step 2 encuentra jerga en otro lugar de `index.html` que no está en esta lista, se trata igual: lo de desarrollo adentro de un `solo-desarrollo` y, si hace falta, una alternativa `solo-empaquetada` en palabras del profe.

- [ ] **Step 5: Los textos de `app.js`**

El aviso de guardado de la sesión (cerca de la línea 1099):

```js
    aviso.textContent = (esLaInstalada() ? "Guardado \u2014 " : "Guardado en sesiones/ \u2014 ") +
      notas + " notas.";
```

Los archivos guardados (cerca de la línea 1155):

```js
  if (respuesta.guardado && Object.keys(respuesta.guardado).length) {
    html += esLaInstalada()
      ? "<p class='ayuda'>Guardado en tu carpeta de sesiones. " + botonAbrir("sesiones") + "</p>"
      : "<p class='ayuda'>Guardado en sesiones/: " +
        Object.values(respuesta.guardado).join(", ") + "</p>";
  }
```

El error del micrófono en `dibujarNivel`:

```js
  if (estado.error_de_audio) {
    texto.innerHTML = esLaInstalada()
      ? "<strong>El micr\u00f3fono fall\u00f3.</strong> Prob\u00e1 con otro en <strong>Ajustes</strong>; " +
        "el detalle qued\u00f3 en registro.txt."
      : "<strong>El micr\u00f3fono fall\u00f3:</strong> " + escapar(estado.error_de_audio) +
        " \u2014 prob\u00e1 con otro en <strong>Ajustes</strong>.";
    texto.className = "ayuda lejos";
    return;
  }
```

Los apuntes vacíos (cerca de la línea 2592):

```js
  if (!datos.existe || !datos.cantidad) {
    contenedor.innerHTML = esLaInstalada()
      ? '<div class="aviso">Todav\u00eda no hay apuntes. Dej\u00e1 los res\u00famenes de tus clases ' +
        "(Markdown, texto o Word, con la fecha en el nombre: <code>2026-09-08.md</code>) en tu " +
        "carpeta de apuntes. " + botonAbrir("apuntes") + "</div>"
      : '<div class="aviso">Todav\u00eda no hay apuntes. Dej\u00e1 los res\u00famenes ' +
        "de tus clases (Markdown, texto o Word, con la fecha en el nombre: " +
        "<code>2026-09-08.md</code>) en <code>material/</code>, o apunt\u00e1 " +
        "<code>CARPETA_CLASES</code> en el <code>.env</code> a la carpeta donde ya los ten\u00e9s. " +
        "La app solo lee esa carpeta: nunca escribe ah\u00ed.</div>";
    return;
  }
```

Las canciones vacías (cerca de la línea 2753):

```js
  if (!cuantas) {
    contenedor.innerHTML = '<div class="aviso">Todav\u00eda no hay canciones. Cre\u00e1 una carpeta ' +
      "por canci\u00f3n adentro de " +
      (esLaInstalada() ? "tu carpeta de canciones " + botonAbrir("canciones")
                       : "<code>material/canciones/</code>") +
      " y dej\u00e1 ah\u00ed la base, los audios y la foto de la tablatura. " +
      "Con volver a esta solapa alcanza.</div>";
    return;
  }
```

`mostrarOrigenDeLasClases` (cerca de la línea 4005):

```js
  donde.innerHTML = esLaInstalada()
    ? "Se leen de tu carpeta de apuntes: " + datos.cantidad +
      (datos.cantidad === 1 ? " clase." : " clases.")
    : (datos.origen === "configurada"
        ? "Se leen de la carpeta configurada en <code>CARPETA_CLASES</code> del <code>.env</code>"
        : "Se leen de <code>material/</code>, la carpeta por defecto") +
      ": " + datos.cantidad + (datos.cantidad === 1 ? " clase" : " clases") +
      (datos.existe ? "" : " (la carpeta no existe todav\u00eda)") +
      ". La app solo lee esa carpeta.";
```

En `htmlDeLaExplicacion` (cerca de la línea 2912), el aviso del coach no se muestra en la instalada:

```js
  } else if (!(e && e.texto) && !esLaInstalada()) {
```

- [ ] **Step 6: Los avisos de `transcripcion.py`**

El del audio mudo:

```python
        return False, (
            "En el audio no hay nada por encima del umbral de volumen. "
            f"{calidad['explicacion']} Si grabaste bajito, medí el ruido en "
            "Ajustes y probá de nuevo."
        ), avisos
```

El de la cobertura:

```python
        avisos.append(
            f"Solo el {cobertura * 100:.0f}% de lo que suena entra en una "
            f"armónica en {tonalidad}: el resto queda fuera de su alcance y "
            "se pierde. Si la grabación es de otra armónica, elegí esa al "
            "importarla."
        )
```

- [ ] **Step 7: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_textos.py tests/test_transcripcion.py tests/test_servidor.py -q`
Expected: todo pasa (salvo la falla conocida del timeout). Además: `node --check armonica/web/app.js` sin errores.

- [ ] **Step 8: Commit**

```bash
git add armonica/web/index.html armonica/web/app.js armonica/web/estilo.css armonica/transcripcion.py tests/test_textos.py tests/test_transcripcion.py
git commit -m "La version instalada no muestra carpetas, .env ni comandos: botones para abrir las carpetas" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: ffmpeg sin ventana negra

**Files:**
- Modify: `armonica/audio.py` (`convertir_a_wav`)
- Modify: `tests/test_audio.py`

**Interfaces:**
- Produces: `audio.convertir_a_wav` llama a `subprocess.run(..., creationflags=CREATE_NO_WINDOW)` en Windows (0 en otros sistemas).

- [ ] **Step 1: Escribir el test que falla**

Al final de `tests/test_audio.py` (sumar `import subprocess` arriba si no está):

```python
def test_ffmpeg_no_abre_una_ventana(monkeypatch, tmp_path):
    """
    Desde pythonw (la versión instalada) no hay consola: cada llamada a
    ffmpeg abriría una ventana negra un instante. CREATE_NO_WINDOW lo evita.
    """
    vistas = {}

    def run_falso(comando, **opciones):
        vistas.update(opciones)
        return subprocess.CompletedProcess(comando, 0, "", "")

    monkeypatch.setattr(audio, "hay_ffmpeg", lambda: True)
    monkeypatch.setattr(audio.subprocess, "run", run_falso)
    audio.convertir_a_wav(tmp_path / "clase.m4a", tmp_path / "clase.wav")
    assert vistas["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
```

- [ ] **Step 2: Correrlo y ver que falla**

Run: `.venv/Scripts/python.exe -m pytest tests/test_audio.py -k ventana -v`
Expected: FAIL con `KeyError: 'creationflags'`.

- [ ] **Step 3: Implementar**

En `armonica/audio.py`, en `convertir_a_wav`, el `subprocess.run` pasa a ser:

```python
    resultado = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(origen),
            "-ac", "1",                       # mono: la armonica es una sola fuente
            "-ar", str(frecuencia_muestreo),  # la frecuencia que usa la app
            "-sample_fmt", "s16",             # 16 bits, que es lo unico que leemos
            str(destino),
        ],
        capture_output=True, text=True,
        # Sin consola (la version instalada corre con pythonw), cada llamada
        # abriria una ventana negra un instante.
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
```

- [ ] **Step 4: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_audio.py -q`
Expected: todo pasa salvo `test_normalizar_arregla_una_grabacion_demasiado_baja` (falla conocida por el `config.py` local).

- [ ] **Step 5: Commit**

```bash
git add armonica/audio.py tests/test_audio.py
git commit -m "ffmpeg sin ventana negra cuando la app corre sin consola" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: El lanzador

**Files:**
- Create: `armonica/lanzador.py`
- Create: `lanzador.pyw`
- Create: `tests/test_lanzador.py`

**Interfaces:**
- Consumes: `servidor.arrancar(puertos=..., empaquetada=True)`, `servidor.PuertoOcupado`, `GET /api/hola` (Task 3).
- Produces:
  - `lanzador.PUERTOS = range(8000, 8011)`
  - `lanzador.carpeta_de_documentos() -> str`
  - `lanzador.carpeta_de_datos(entorno=None) -> str` (`ARMONICA_DATOS` o `Documentos\Armonica`)
  - `lanzador.preparar_carpeta(raiz)`
  - `lanzador.recortar_registro(ruta, maximo=1_000_000, conservar=200_000)`
  - `lanzador.abrir_registro(raiz) -> archivo`
  - `lanzador.preparar_entorno(raiz, carpeta_programa, entorno=None)`
  - `lanzador.buscar_instancia(puertos=PUERTOS, espera=0.5) -> int | None`
  - `lanzador.main() -> int`

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_lanzador.py`:

```python
"""
Tests de armonica/lanzador.py — abrir la app desde un ícono.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_lanzador.py -v
"""

import os
import socket
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from armonica import lanzador, servidor


def test_los_datos_van_donde_diga_armonica_datos(tmp_path):
    assert lanzador.carpeta_de_datos({"ARMONICA_DATOS": str(tmp_path)}) == str(tmp_path)


def test_sin_la_variable_van_a_documentos(monkeypatch):
    monkeypatch.setattr(lanzador, "carpeta_de_documentos", lambda: os.path.join("D:", "Docs"))
    assert lanzador.carpeta_de_datos({}) == os.path.join("D:", "Docs", "Armonica")


@pytest.mark.skipif(sys.platform != "win32", reason="Documentos se le pregunta a Windows")
def test_windows_dice_donde_esta_documentos():
    assert os.path.isdir(lanzador.carpeta_de_documentos())


def test_preparar_la_carpeta_crea_lo_que_falta(tmp_path):
    lanzador.preparar_carpeta(str(tmp_path))
    for nombre in ("frases", "sesiones", "canciones", "apuntes", "material"):
        assert (tmp_path / nombre).is_dir()


def test_el_registro_largo_se_recorta(tmp_path):
    ruta = tmp_path / "registro.txt"
    ruta.write_bytes(b"a" * 1200 + b"z" * 300)
    lanzador.recortar_registro(str(ruta), maximo=1000, conservar=300)
    assert ruta.read_bytes() == b"z" * 300

    ruta.write_bytes(b"corto")
    lanzador.recortar_registro(str(ruta), maximo=1000, conservar=300)
    assert ruta.read_bytes() == b"corto"


def test_el_entorno_apunta_a_la_carpeta_de_datos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)     # monkeypatch vuelve a esta carpeta al final
    datos = tmp_path / "datos"
    datos.mkdir()
    programa = tmp_path / "programa"
    (programa / "ffmpeg").mkdir(parents=True)
    entorno = {"PATH": "C:\\otro"}

    lanzador.preparar_entorno(str(datos), str(programa), entorno)

    assert os.getcwd() == str(datos)
    assert entorno["CARPETA_CANCIONES"] == os.path.join(str(datos), "canciones")
    assert entorno["CARPETA_CLASES"] == os.path.join(str(datos), "apuntes")
    assert entorno["PATH"] == os.path.join(str(programa), "ffmpeg") + os.pathsep + "C:\\otro"


def test_sin_ffmpeg_al_lado_el_path_no_cambia(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entorno = {"PATH": "C:\\otro"}
    lanzador.preparar_entorno(str(tmp_path), str(tmp_path / "programa"), entorno)
    assert entorno["PATH"] == "C:\\otro"


def test_encuentra_una_app_ya_abierta():
    servidor.Manejador.estado = servidor.EstadoCompartido("C", None, None)
    abierta = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Manejador)
    threading.Thread(target=abierta.serve_forever, daemon=True).start()
    libre = socket.socket()
    libre.bind(("127.0.0.1", 0))
    puerto_libre = libre.getsockname()[1]
    libre.close()
    try:
        puerto = abierta.server_address[1]
        assert lanzador.buscar_instancia([puerto_libre, puerto]) == puerto
        assert lanzador.buscar_instancia([puerto_libre]) is None
    finally:
        abierta.shutdown()
        abierta.server_close()


def test_otro_programa_en_el_puerto_no_es_la_app(tmp_path):
    otro = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        lambda *a, **k: SimpleHTTPRequestHandler(*a, directory=str(tmp_path), **k))
    threading.Thread(target=otro.serve_forever, daemon=True).start()
    try:
        assert lanzador.buscar_instancia([otro.server_address[1]]) is None
    finally:
        otro.shutdown()
        otro.server_close()
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_lanzador.py -v`
Expected: ERROR de colección con `ImportError: cannot import name 'lanzador' from 'armonica'`.

- [ ] **Step 3: Escribir `armonica/lanzador.py`**

```python
"""
lanzador.py — Abrir la app desde un ícono, sin ventana negra.

Lo usa el acceso directo de la versión instalada (lanzador.pyw, con
pythonw.exe). Hace lo que Armonica.bat hace para Bruno, más lo que necesita
alguien sin terminal:

1. Los datos van a Documentos\\Armonica: frases, sesiones, canciones,
   apuntes. La app guarda todo relativo a la carpeta desde donde arranca,
   así que alcanza con pararse ahí. Las canciones y los apuntes se le dicen
   por las mismas variables que usa el .env de Bruno.
2. Sin consola, lo que la app imprime va a registro.txt: es lo que Bruno
   pide cuando algo no anda.
3. ffmpeg viaja con el programa, en la carpeta de al lado: va primero en el
   PATH.
4. Una sola app: si ya hay una abierta, solo se abre el navegador.

Para probarlo desde el repo, sin tocar Documentos:

    set ARMONICA_DATOS=C:\\ruta\\de\\prueba
    .venv\\Scripts\\pythonw.exe lanzador.pyw
"""

import ctypes
import json
import os
import sys
import traceback
import urllib.request
import webbrowser
from datetime import datetime

PUERTOS = range(8000, 8011)
SUBCARPETAS = ("frases", "sesiones", "canciones", "apuntes", "material")
MAXIMO_REGISTRO = 1_000_000
CONSERVAR_REGISTRO = 200_000

# app\armonica\lanzador.py -> app -> la carpeta del programa, donde está ffmpeg\.
CARPETA_PROGRAMA = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def carpeta_de_documentos():
    """
    La carpeta Documentos de verdad. Con OneDrive puede no ser
    %USERPROFILE%\\Documents, así que se le pregunta a Windows.
    """
    if sys.platform == "win32":
        try:
            return _documentos_segun_windows()
        except OSError:
            pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def _documentos_segun_windows():
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
    documentos = GUID(0xFDD39AD0, 0x238F, 0x46AF,
                      (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
    ruta = ctypes.c_wchar_p()
    resultado = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(documentos), 0, None, ctypes.byref(ruta))
    if resultado != 0:
        raise OSError(f"SHGetKnownFolderPath devolvió {resultado}")
    try:
        return ruta.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(ruta)


def carpeta_de_datos(entorno=None):
    """Documentos\\Armonica, o ARMONICA_DATOS si está (pruebas)."""
    entorno = os.environ if entorno is None else entorno
    return entorno.get("ARMONICA_DATOS") or os.path.join(carpeta_de_documentos(), "Armonica")


def preparar_carpeta(raiz):
    for nombre in SUBCARPETAS:
        os.makedirs(os.path.join(raiz, nombre), exist_ok=True)


def recortar_registro(ruta, maximo=MAXIMO_REGISTRO, conservar=CONSERVAR_REGISTRO):
    """Si el registro pasa de `maximo` bytes, se queda con los últimos `conservar`."""
    if not os.path.isfile(ruta) or os.path.getsize(ruta) <= maximo:
        return
    with open(ruta, "rb") as archivo:
        archivo.seek(-conservar, os.SEEK_END)
        cola = archivo.read()
    with open(ruta, "wb") as archivo:
        archivo.write(cola)


def abrir_registro(raiz):
    """Manda stdout y stderr a registro.txt: con pythonw no hay consola."""
    ruta = os.path.join(raiz, "registro.txt")
    recortar_registro(ruta)
    registro = open(ruta, "a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = sys.stderr = registro
    return registro


def preparar_entorno(raiz, carpeta_programa, entorno=None):
    """Se para en la carpeta de datos y le dice a la app dónde está cada cosa."""
    entorno = os.environ if entorno is None else entorno
    os.chdir(raiz)
    entorno["CARPETA_CANCIONES"] = os.path.join(raiz, "canciones")
    entorno["CARPETA_CLASES"] = os.path.join(raiz, "apuntes")
    ffmpeg = os.path.join(carpeta_programa, "ffmpeg")
    if os.path.isdir(ffmpeg):
        entorno["PATH"] = ffmpeg + os.pathsep + entorno.get("PATH", "")


def buscar_instancia(puertos=PUERTOS, espera=0.5):
    """El puerto de una app ya abierta, o None. Pregunta /api/hola."""
    for puerto in puertos:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/hola",
                                        timeout=espera) as respuesta:
                if json.loads(respuesta.read()).get("app") == "armonica":
                    return puerto
        except (OSError, ValueError):
            continue
    return None


def avisar(texto):
    """
    Un cartel de Windows. Sin consola y antes de que haya página, es la
    única forma de decir que algo salió mal.
    """
    print(texto)
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, texto, "Armónica", 0x10)


def main():
    raiz = carpeta_de_datos()
    try:
        preparar_carpeta(raiz)
        abrir_registro(raiz)
        print(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} ---")
        preparar_entorno(raiz, CARPETA_PROGRAMA)

        puerto = buscar_instancia()
        if puerto is not None:
            print(f"Ya estaba abierta en el {puerto}: solo abro el navegador.")
            webbrowser.open(f"http://127.0.0.1:{puerto}")
            return 0

        # Recién ahora: con la carpeta y el entorno listos.
        from armonica import servidor
        try:
            return servidor.arrancar(puertos=PUERTOS, empaquetada=True)
        except servidor.PuertoOcupado as error:
            avisar(f"{error} Cerrá otros programas y probá de nuevo.")
            return 1
    except Exception:      # noqa: BLE001
        traceback.print_exc()
        avisar("La app no pudo arrancar. El detalle quedó en "
               + os.path.join(raiz, "registro.txt"))
        return 1
```

Y `lanzador.pyw` en la raíz del repo:

```python
"""
Abre la app sin ventana negra: lo ejecuta el acceso directo de la versión
instalada con pythonw.exe. Todo lo que hace está en armonica/lanzador.py.
"""

import sys

from armonica import lanzador

sys.exit(lanzador.main())
```

- [ ] **Step 4: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_lanzador.py -v`
Expected: 9 passed (fuera de Windows, 8 y uno salteado).

- [ ] **Step 5: Commit**

```bash
git add armonica/lanzador.py lanzador.pyw tests/test_lanzador.py
git commit -m "El lanzador: Documentos\\Armonica, registro.txt, ffmpeg al lado y una sola app" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Probar de punta a punta y documentar

**Files:**
- Modify: `README.md` (sección "La interfaz web", párrafo de **Ajustes**; "Ajustar el comportamiento")
- Modify: `PROXIMOS_PASOS.md`

- [ ] **Step 1: La suite completa**

Run: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: todo pasa salvo las dos fallas conocidas de Global Constraints. Y `node --check armonica/web/app.js` sin errores.

- [ ] **Step 2: El lanzador de verdad, con una carpeta de prueba**

Desde Git Bash, con una carpeta de prueba que NO sea Documentos (el scratchpad de la sesión, o `%TEMP%`). En lo que sigue, `$PRUEBA` es esa carpeta:

```bash
PRUEBA="$TEMP/armonica-prueba"
ARMONICA_DATOS="$PRUEBA" .venv/Scripts/pythonw.exe lanzador.pyw &
```

Verificar, en orden:
1. No aparece ninguna ventana negra; se abre el navegador.
2. `$PRUEBA` tiene `frases`, `sesiones`, `canciones`, `apuntes`, `material` y `registro.txt` con el encabezado de la fecha y "Servidor andando en http://127.0.0.1:8000" (o el siguiente puerto, si Bruno tiene su app abierta en el 8000).
3. Aparece el cartel de primeros pasos. "Ir a Ajustes" cambia de solapa; "Medir el ruido" cuenta el resultado; "Abrir la configuración de sonido" abre Configuración de Windows; "Listo" lo oculta y `ajustes.json` tiene `"primeros_pasos": true`.
4. Ajustes no muestra `.env`, `material/` ni la sección del coach; Canciones y Aprendizaje vacíos muestran "Abrir la carpeta" y el botón abre la carpeta de prueba.
5. Elegir otro micrófono y otra armónica: `ajustes.json` guarda el NOMBRE del micrófono y la armónica.
6. Volver a ejecutar el mismo comando: no arranca otra app; `registro.txt` dice "Ya estaba abierta en el ...: solo abro el navegador".
7. Cerrar la pestaña y esperar 70 segundos: `registro.txt` dice "Ninguna página abierta hace un minuto: apagué el micrófono" y el ícono de micrófono en uso de Windows se apaga. Abrir la página de nuevo: la barra vuelve a moverse.
8. Ajustes → "Cerrar la app": la página dice que está cerrada y el proceso termina (`netstat -ano | grep :8000` ya no muestra el puerto en LISTENING).
9. Ejecutar de nuevo: arranca con el micrófono y la armónica elegidos, sin cartel de primeros pasos.

Si algo no da, es un bug: volver a la tarea que lo introdujo, con un test que lo reproduzca.

- [ ] **Step 3: `Armonica.bat` sigue andando como antes**

Con la app de prueba cerrada, abrir `Armonica.bat`: arranca con `--tonalidad C --posicion 12 --escala blues_mayor` (lo escrito gana a `ajustes.json`) y con los textos de desarrollo (no es la instalada: se ven `.env` y la sección del coach). La primera vez muestra los primeros pasos, porque el repo todavía no tiene `ajustes.json`: con "Listo" no vuelven. Si el 8000 está ocupado por otra app, la consola dice "El puerto 8000 está ocupado. ¿Ya está abierta la app?...".

- [ ] **Step 4: Documentar**

En `README.md`, reemplazar el párrafo de **Ajustes** de "La interfaz web":

```markdown
**Ajustes**
tiene el micrófono y la configuración: la armónica que tenés en la mano, la
posición y la escala de referencia se cambian ahí, sin reiniciar nada, y
quedan guardadas en `ajustes.json` para la próxima vez (el micrófono, por
nombre: el número cambia al enchufar otro aparato). Lo que se escribe en la
línea de comandos, como las opciones de `Armonica.bat`, gana a lo guardado.
**Medir el ruido** escucha tres segundos en silencio y deja el umbral justo
por encima, como `--calibrar`, pero guardado. La primera vez aparecen los
**primeros pasos** (micrófono, mejoras de audio de Windows, ruido, tocar), y
al pie de Ajustes están la versión y **Cerrar la app**. Sin ninguna página
abierta, al minuto la app suelta el micrófono.
```

En "Ajustar el comportamiento", la fila de `UMBRAL_VOLUMEN_RMS`:

```markdown
| `UMBRAL_VOLUMEN_RMS` | Qué tan fuerte hay que tocar para que cuente. **Medilo con "Medir el ruido" en Ajustes** (o `--calibrar`); lo medido queda en `ajustes.json` y gana a este valor. |
```

Y al final de "La interfaz web", antes de "### El coach (opcional)":

```markdown
**La versión instalada.** `lanzador.pyw` abre la app sin ventana negra: es
lo que va a ejecutar el acceso directo del instalador para el profe (ver
`docs/superpowers/specs/2026-10-02-instalador-profe-design.md`). Guarda todo
en `Documentos\Armonica` (frases, sesiones, canciones, apuntes, `ajustes.json`
y `registro.txt` con lo que la app imprime), abre una sola app aunque se
haga doble clic dos veces, y muestra la pantalla sin carpetas, `.env` ni
comandos. Para probarlo desde el repo sin tocar Documentos:
`ARMONICA_DATOS=<carpeta>` y `.venv\Scripts\pythonw.exe lanzador.pyw`.
```

En `PROXIMOS_PASOS.md`, sumar en la lista de lo hecho:

```markdown
   - **Instalador, etapa 1: la app y el lanzador.** Hecho (la fecha del commit, AAAA-MM-DD): ajustes
     guardados en `ajustes.json` (micrófono por nombre), Medir el ruido,
     primeros pasos, Cerrar la app, micrófono que se suelta sin páginas,
     puerto exclusivo y `/api/hola`, `VERSION`, textos sin jerga en la
     instalada, ffmpeg sin ventana, y `lanzador.pyw`. Falta la etapa 2 (el
     armado con Inno Setup) y la 3 (la guía).
```

- [ ] **Step 5: Commit**

```bash
git add README.md PROXIMOS_PASOS.md
git commit -m "README y PROXIMOS_PASOS: ajustes guardados, primeros pasos y el lanzador" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
