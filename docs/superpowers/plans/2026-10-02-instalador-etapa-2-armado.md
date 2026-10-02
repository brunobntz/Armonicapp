# Instalador, etapa 2: el armado — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que Bruno corra un comando y obtenga `dist\Armonica-<VERSION>-instalador.exe`: el programa armado con Python embebido, las ruedas fijadas, ffmpeg y las licencias, probado con una prueba de humo, y antes de eso, la app endurecida para correr días escondida en la máquina del profe.

**Architecture:** Primero cinco arreglos chicos en la app que dejó pendientes la revisión final de la etapa 1 (pedidos de otros sitios, guardado atómico, vigía que no muere, una sola app con doble clic rápido, fotos HEIC con pi-heif). Después el armado en `herramientas/empaquetar.py` (Python, con tests de las piezas puras), llamado por un `herramientas/empaquetar.ps1` de pocas líneas: `fijar` (ruedas con SHA-256), `armar` (git archive → tests → descargas verificadas → `empaquetado/_armado/Armonica`), `humo` (lo abre como el acceso directo y lo cierra) e `instalador` (Inno Setup, `empaquetado/armonica.iss`).

**Tech Stack:** Python 3.14 (biblioteca estándar en todo lo nuevo), pip del `.venv`, Inno Setup 6 (ISCC, Pascal Script con WinHttp), PowerShell 5.1 para el envoltorio, pytest.

**Spec:** `docs/superpowers/specs/2026-10-02-instalador-profe-design.md` (secciones "Cómo queda instalado", "El armado", "Licencias", "Probarlo", "Riesgos"). Además, los pendientes que la revisión final de la etapa 1 mandó a esta etapa (memoria del proyecto): chequeo de Origin/Host, guardado atómico de `ajustes.json`, vigía con try/except, prueba de humo que verifique las bibliotecas, cerrar la app desde el instalador, una sola instancia con mutex, y respetar el layout que asume `lanzador.CARPETA_PROGRAMA`.

**Desvíos de la spec, decididos acá:**
- La lógica del armado va en `herramientas/empaquetar.py` (testeable con pytest) y `empaquetar.ps1` solo la llama.
- Las versiones y SHA-256 fijos van en `empaquetado/descargas.json` y `empaquetado/requisitos.txt` (commiteados), no escritos adentro del script.
- Fotos HEIC con **pi-heif** y no pillow-heif: la rueda de pillow-heif trae `libx265` (GPL; verificado en el `.venv`: `libx265-217-*.dll`). pi-heif 1.4.0 solo lee, es LGPL/BSD y tiene rueda `cp314-win_amd64`.
- El instalador cierra la app con `/api/hola` + `/api/apagar` (Pascal Script) y no con `CloseApplications`: el Restart Manager no puede cerrar un `pythonw` sin ventana.
- El PDF de la guía queda para la etapa 3.

## Global Constraints

- NUNCA commitear `config.py` ni `EVALUATION_2026-09-18.md` (cambios locales de Bruno). Cada commit agrega solo los archivos de su tarea.
- Los tests se corren con `.venv/Scripts/python.exe -m pytest` (o la ruta absoluta del `.venv` del repo principal si se trabaja en un worktree).
- En la carpeta del repo de Bruno fallan dos tests por su entorno (umbral local en `config.py`, Ollama del `.env`): `tests/test_audio.py::test_normalizar_arregla_una_grabacion_demasiado_baja` y `tests/test_servidor.py::test_la_lista_de_canciones_trae_la_ficha_para_la_armonica_puesta`. En un worktree no fallan.
- Ningún test ni herramienta toca `Documentos`, el repo (salvo `empaquetado/_descargas`, `empaquetado/_armado`, `dist`, todos gitignored) ni abre el navegador: la prueba de humo usa carpetas temporales y `ARMONICA_SIN_NAVEGADOR=1`.
- Descargas solo de las URLs fijadas: python.org, `github.com/BtbN/FFmpeg-Builds` y PyPI (vía pip). Si un SHA-256 no coincide, se corta; nunca se reemplaza el hash para que pase.
- Versiones fijas:
  - Python embebido: `https://www.python.org/ftp/python/3.14.6/python-3.14.6-embed-amd64.zip`, SHA-256 `df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c` (publicado por python.org).
  - ffmpeg: `https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-10-01-13-06/ffmpeg-n8.1.3-14-g330caae0c1-win64-lgpl-8.1.zip`, SHA-256 `84e4495b9883dbf3997435943d2d7057cc55a4c31973f7422f56b1b56974006d` (del `checksums.sha256` del release), 170.623.504 bytes.
  - Ruedas: numpy 2.5.3, sounddevice 0.5.6, cffi 2.1.1, pycparser 3.0, rich 15.0.0, markdown-it-py 4.2.0, mdurl 0.1.2, Pygments 2.21.0, pillow 12.3.0, pi-heif 1.4.0, pypdf 6.19.0.
- Layout instalado (lo asume `lanzador.CARPETA_PROGRAMA`): `{app}\python\` (embebido + `Lib\site-packages`), `{app}\app\` (`armonica\`, `config.py`, `VERSION`, `lanzador.pyw`, `LICENSE`), `{app}\ffmpeg\ffmpeg.exe`, `{app}\licencias\`, `{app}\Armonica.ico`. `python314._pth` con `python314.zip`, `.`, `Lib\site-packages`, `..\app`.
- AppId del instalador: `{DE843E22-3123-424E-AFFC-A46A5622326D}` (no cambia entre versiones: así una versión nueva se instala encima).
- Textos de pantalla y del instalador en castellano rioplatense (voseo), sin jerga.
- Comentarios y docstrings en castellano, explicando el porqué, como el resto del código.
- Mensajes de commit en castellano, una oración sin prefijo, y al final `Co-Authored-By: <el modelo que escribió el commit> <noreply@anthropic.com>`.

---

## Mapa de archivos

| Archivo | Qué cambia |
|---|---|
| `armonica/servidor.py` | Rechaza pedidos con Host u Origin ajenos; el vigía no se muere y se puede detener |
| `armonica/ajustes.py` | `guardar` escribe a un temporal y reemplaza |
| `armonica/lanzador.py` | Mutex de turno, `esperar_instancia`, `ARMONICA_SIN_NAVEGADOR` |
| `armonica/imagenes.py` | pillow-heif o pi-heif |
| `herramientas/empaquetar.py` (nuevo) | Todo el armado |
| `herramientas/empaquetar.ps1` (nuevo) | Lo llama con el Python del `.venv` |
| `empaquetado/descargas.json`, `empaquetado/requisitos.in` (nuevos) | Lo que se baja, fijado |
| `empaquetado/requisitos.txt` (nuevo, generado) | Las ruedas con su SHA-256 |
| `empaquetado/armonica.iss` (nuevo) | El instalador |
| `empaquetado/PROBAR.md` (nuevo) | La prueba en un usuario de Windows limpio |
| `.gitignore`, `README.md`, `PROXIMOS_PASOS.md` | Ignorar lo generado; documentar |
| `tests/test_servidor.py`, `tests/test_ajustes.py`, `tests/test_lanzador.py`, `tests/test_canciones.py`, `tests/test_empaquetar.py` (nuevo) | Tests |

---

### Task 1: El servidor rechaza pedidos de otros sitios

**Files:**
- Modify: `armonica/servidor.py` (`Manejador`: `NOMBRES_PROPIOS`, `_es_ajeno`; primera línea de `do_GET` y `do_POST`)
- Modify: `tests/test_servidor.py`

**Interfaces:**
- Produces: `Manejador.NOMBRES_PROPIOS = ("127.0.0.1", "localhost")`, `Manejador._es_ajeno(self) -> bool`. Todo pedido ajeno recibe 403 antes de hacer nada.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_servidor.py`, después de la función `mandar`, un ayudante:

```python
def pedir_con(base, ruta, cabeceras, cuerpo=None):
    """Un pedido con cabeceras a elección; devuelve el código HTTP."""
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    cabeceras = dict(cabeceras)
    if datos is not None:
        cabeceras["Content-Type"] = "application/json"
    pedido = urllib.request.Request(base + ruta, data=datos, headers=cabeceras,
                                    method="POST" if datos is not None else "GET")
    try:
        with urllib.request.urlopen(pedido, timeout=5) as respuesta:
            return respuesta.status
    except urllib.error.HTTPError as error:
        return error.code
```

Al final del archivo:

```python
# =============================================================================
# Pedidos de otros sitios
# =============================================================================

def test_un_pedido_con_otro_host_se_rechaza(servidor_andando):
    """Un dominio que apunta a 127.0.0.1 (DNS rebinding) no lee nada."""
    assert pedir_con(servidor_andando, "/api/inicio", {"Host": "evil.example"}) == 403


def test_un_pedido_desde_otra_pagina_se_rechaza(servidor_andando, tmp_path):
    """Una página cualquiera del navegador no puede cambiar nada."""
    codigo = pedir_con(servidor_andando, "/api/primeros-pasos",
                       {"Origin": "http://evil.example"}, {"hechos": True})
    assert codigo == 403
    assert ajustes.cargar(str(tmp_path / "ajustes.json")) == {}
    assert pedir_con(servidor_andando, "/api/inicio", {"Origin": "null"}) == 403


def test_la_propia_pagina_pasa(servidor_andando, tmp_path):
    puerto = servidor_andando.rsplit(":", 1)[1]
    assert pedir_con(servidor_andando, "/api/primeros-pasos",
                     {"Origin": f"http://127.0.0.1:{puerto}"}, {"hechos": True}) == 200
    assert pedir_con(servidor_andando, "/api/inicio",
                     {"Host": f"localhost:{puerto}", "Origin": f"http://localhost:{puerto}"}) == 200
    assert ajustes.cargar(str(tmp_path / "ajustes.json")) == {"primeros_pasos": True}
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -k "otro_host or otra_pagina or propia_pagina" -v`
Expected: FAIL en los dos primeros (`assert 200 == 403`); el tercero pasa (ya andaba).

- [ ] **Step 3: Implementar**

En `armonica/servidor.py`, en la clase `Manejador`, junto a `servidor_http = None`:

```python
    # Los nombres con que la propia página llama al servidor.
    NOMBRES_PROPIOS = ("127.0.0.1", "localhost")

    def _es_ajeno(self):
        """
        Si el pedido viene de otro sitio. El servidor escucha solo en esta
        máquina, pero cualquier página abierta en el navegador puede
        mandarle pedidos: con su propio Origin (un formulario o un fetch
        hacia 127.0.0.1) o con otro Host (un dominio que apunta a
        127.0.0.1: el "DNS rebinding"). La versión instalada corre días
        escondida en la máquina del profe, así que esos pedidos se
        rechazan. Un pedido sin Origin (la barra de direcciones, el
        instalador, los tests) pasa si el Host es propio.
        """
        host = (self.headers.get("Host") or "").strip()
        if host and (urllib.parse.urlsplit("//" + host).hostname or "") not in self.NOMBRES_PROPIOS:
            return True
        origen = self.headers.get("Origin")
        if origen is not None and (urllib.parse.urlsplit(origen).hostname or "") not in self.NOMBRES_PROPIOS:
            return True
        return False
```

Primera línea de `do_GET`:

```python
        if self._es_ajeno():
            return self.send_error(403)
```

Y la misma como primera línea de `do_POST` (antes de partir la ruta: un pedido ajeno no llega a leer el cuerpo).

- [ ] **Step 4: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -q`
Expected: todo pasa (salvo la falla de entorno conocida, si se corre en la carpeta de Bruno).

- [ ] **Step 5: Commit**

```bash
git add armonica/servidor.py tests/test_servidor.py
git commit -m "El servidor rechaza los pedidos que vienen de otros sitios" -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 2: Guardar los ajustes nunca deja el archivo a medias

**Files:**
- Modify: `armonica/ajustes.py` (`guardar`)
- Modify: `tests/test_ajustes.py`

**Interfaces:**
- Produces: `ajustes.guardar` escribe a `<ruta>.tmp` y hace `os.replace`; si falla, borra el temporal y deja el archivo anterior intacto.

- [ ] **Step 1: Escribir el test que falla**

Al final de `tests/test_ajustes.py`:

```python
def test_un_guardado_que_falla_no_rompe_lo_que_habia(tmp_path, monkeypatch):
    """
    El instalador de una versión nueva puede cerrar la app en cualquier
    momento: un guardado cortado no puede dejar un ajustes.json vacío.
    """
    ruta = str(tmp_path / "ajustes.json")
    ajustes.guardar({"tonalidad": "A"}, ruta)

    def dump_que_falla(*args, **kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(ajustes, "json", types.SimpleNamespace(load=json.load, dump=dump_que_falla))
    with pytest.raises(OSError):
        ajustes.guardar({"tonalidad": "D"}, ruta)
    monkeypatch.undo()

    assert ajustes.cargar(ruta) == {"tonalidad": "A"}
    assert not (tmp_path / "ajustes.json.tmp").exists()
```

- [ ] **Step 2: Correrlo y ver que falla**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ajustes.py -k guardado_que_falla -v`
Expected: FAIL con `assert {} == {'tonalidad': 'A'}` (el `open("w")` ya truncó el archivo).

- [ ] **Step 3: Implementar**

En `armonica/ajustes.py`, en `guardar`, reemplazar el bloque `with open(ruta, "w", ...) as archivo: json.dump(...)` por:

```python
    # A un temporal y después se reemplaza: si algo corta el guardado (el
    # instalador cerrando la app, un disco lleno), queda el archivo de antes
    # entero y no uno vacío que haría arrancar con la fábrica.
    temporal = ruta + ".tmp"
    try:
        with open(temporal, "w", encoding="utf-8") as archivo:
            json.dump(actuales, archivo, indent=2, ensure_ascii=False)
        os.replace(temporal, ruta)
    except BaseException:
        if os.path.exists(temporal):
            os.remove(temporal)
        raise
    return actuales
```

(`ruta` ya es un `str`: `ruta = ruta or ARCHIVO`.)

- [ ] **Step 4: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ajustes.py -q`
Expected: todo pasa.

- [ ] **Step 5: Commit**

```bash
git add armonica/ajustes.py tests/test_ajustes.py
git commit -m "Guardar los ajustes nunca deja el archivo a medias" -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 3: El vigía del micrófono no se muere

**Files:**
- Modify: `armonica/servidor.py` (`vigilar_el_microfono`)
- Modify: `tests/test_servidor.py`

**Interfaces:**
- Produces: `servidor.vigilar_el_microfono(clase, puerto, cada=1.0, detener=None)`: si `un_paso_del_vigia` levanta una excepción, la anota y sigue; `detener` (un `threading.Event`) lo corta (para tests).

- [ ] **Step 1: Escribir el test que falla**

Al final de `tests/test_servidor.py`:

```python
def test_el_vigia_sigue_aunque_una_mirada_falle(monkeypatch):
    """Un vigía muerto dejaría el micrófono tomado para siempre."""
    miradas = []

    def mirada(clase, puerto, memoria, ahora):
        miradas.append(ahora)
        if len(miradas) == 1:
            raise RuntimeError("algo inesperado")

    monkeypatch.setattr(servidor, "un_paso_del_vigia", mirada)
    detener = threading.Event()
    hilo = threading.Thread(target=servidor.vigilar_el_microfono, args=(None, 8000),
                            kwargs={"cada": 0.01, "detener": detener}, daemon=True)
    hilo.start()
    limite = time.monotonic() + 3
    while len(miradas) < 3 and time.monotonic() < limite:
        time.sleep(0.01)
    detener.set()
    hilo.join(timeout=2)

    assert len(miradas) >= 3
    assert not hilo.is_alive()
```

- [ ] **Step 2: Correrlo y ver que falla**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -k vigia_sigue -v`
Expected: FAIL (`assert 0 >= 3`: el hilo muere con `TypeError` por el argumento `detener`).

- [ ] **Step 3: Implementar**

Reemplazar `vigilar_el_microfono` en `armonica/servidor.py`:

```python
def vigilar_el_microfono(clase, puerto, cada=1.0, detener=None):
    """
    El vigía: mira cada `cada` segundos. Corre en un hilo daemon.

    Si una mirada falla por algo inesperado, lo anota y sigue: un vigía
    muerto dejaría el micrófono tomado para siempre, sin que nadie se entere
    (con pythonw no hay consola). `detener` es para los tests.
    """
    memoria = {"sin_nadie_desde": time.monotonic(), "apagado_por_vigia": False}
    while detener is None or not detener.is_set():
        time.sleep(cada)
        try:
            un_paso_del_vigia(clase, puerto, memoria, time.monotonic())
        except Exception as error:      # noqa: BLE001
            print(f"  El vigía del micrófono tropezó y sigue: {error}")
```

- [ ] **Step 4: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_servidor.py -k "vigia or que_hacer" -q`
Expected: todo pasa.

- [ ] **Step 5: Commit**

```bash
git add armonica/servidor.py tests/test_servidor.py
git commit -m "El vigia del microfono anota lo inesperado y sigue mirando" -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 4: Una sola app aunque se haga doble clic rápido, y sin navegador para la prueba

**Files:**
- Modify: `armonica/lanzador.py` (constantes, `_turno`, `tomar_el_turno`, `esperar_instancia`, `abrir_el_navegador`, `main`, docstring del módulo)
- Modify: `tests/test_lanzador.py`

**Interfaces:**
- Consumes: `buscar_instancia(puertos=PUERTOS, espera=0.5)` (existente).
- Produces:
  - `lanzador.NOMBRE_DEL_TURNO = "Local\\Armonica-lanzador"`, `lanzador.ESPERA_A_LA_OTRA = 20.0`
  - `lanzador.tomar_el_turno(nombre=NOMBRE_DEL_TURNO) -> (bool, manija | None)`
  - `lanzador.esperar_instancia(espera=ESPERA_A_LA_OTRA, cada=0.5, buscar=None) -> int | None` (la usa también la prueba de humo, Task 8)
  - `lanzador.abrir_el_navegador(puerto, entorno=None) -> bool` (no abre nada con `ARMONICA_SIN_NAVEGADOR`)
  - `main` pasa `abrir_navegador=not os.environ.get("ARMONICA_SIN_NAVEGADOR")` a `servidor.arrancar`.

- [ ] **Step 1: Escribir los tests que fallan**

Al final de `tests/test_lanzador.py` (sumar `import uuid` arriba):

```python
@pytest.mark.skipif(sys.platform != "win32", reason="el turno es un mutex de Windows")
def test_el_turno_es_de_uno_solo():
    import ctypes
    nombre = f"Local\\Armonica-prueba-{uuid.uuid4()}"
    primero, manija_1 = lanzador.tomar_el_turno(nombre)
    segundo, manija_2 = lanzador.tomar_el_turno(nombre)
    try:
        assert primero is True
        assert segundo is False
    finally:
        ctypes.windll.kernel32.CloseHandle(manija_1)
        ctypes.windll.kernel32.CloseHandle(manija_2)


def test_esperar_a_la_app_que_esta_arrancando():
    respuestas = iter([None, None, 8003])
    assert lanzador.esperar_instancia(espera=5, cada=0, buscar=lambda: next(respuestas)) == 8003
    assert lanzador.esperar_instancia(espera=0.05, cada=0.01, buscar=lambda: None) is None


def test_sin_navegador_para_la_prueba_de_humo(monkeypatch):
    abiertas = []
    monkeypatch.setattr(lanzador.webbrowser, "open", abiertas.append)
    assert lanzador.abrir_el_navegador(8001, {"ARMONICA_SIN_NAVEGADOR": "1"}) is False
    assert abiertas == []
    assert lanzador.abrir_el_navegador(8001, {}) is True
    assert abiertas == ["http://127.0.0.1:8001"]
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_lanzador.py -v`
Expected: FAIL con `AttributeError: module 'armonica.lanzador' has no attribute 'tomar_el_turno'` (y `esperar_instancia`, `abrir_el_navegador`).

- [ ] **Step 3: Implementar**

En `armonica/lanzador.py`, sumar `import time` a los imports y, después de `CARPETA_PROGRAMA`:

```python
# El turno: un mutex de Windows con nombre. Lo toma el primer lanzador y lo
# tiene mientras vive su app; un segundo lanzador lo encuentra tomado.
NOMBRE_DEL_TURNO = "Local\\Armonica-lanzador"
ERROR_ALREADY_EXISTS = 183

# Cuánto espera un segundo lanzador a que la app del primero conteste.
ESPERA_A_LA_OTRA = 20.0

# La manija del turno: tiene que vivir lo que vive el proceso. Si se
# cerrara, el próximo lanzador creería que es el primero.
_turno = None
```

Y estas funciones, después de `buscar_instancia`:

```python
def tomar_el_turno(nombre=NOMBRE_DEL_TURNO):
    """
    (es_el_primero, manija). Dos clics rápidos en el ícono abren dos
    lanzadores casi juntos: el segundo no llega a ver la app del primero,
    que todavía está arrancando, y levantaría otra con otro micrófono
    abierto. El que crea el mutex es el primero; el otro espera a que la
    app conteste y solo abre el navegador. Fuera de Windows no hay turno.
    """
    if sys.platform != "win32":
        return True, None
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    manija = kernel32.CreateMutexW(None, False, nombre)
    if not manija:
        raise OSError(f"CreateMutexW falló: {ctypes.get_last_error()}")
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS, manija


def esperar_instancia(espera=ESPERA_A_LA_OTRA, cada=0.5, buscar=None):
    """El puerto de la app cuando conteste, o None si no contesta a tiempo."""
    buscar = buscar or buscar_instancia
    limite = time.monotonic() + espera
    while True:
        puerto = buscar()
        if puerto is not None or time.monotonic() >= limite:
            return puerto
        time.sleep(cada)


def abrir_el_navegador(puerto, entorno=None):
    """
    Abre la página de la app. Con ARMONICA_SIN_NAVEGADOR no abre nada: la
    prueba de humo del armado abre y cierra la app sin tocar el navegador
    de quien la corre.
    """
    entorno = os.environ if entorno is None else entorno
    if entorno.get("ARMONICA_SIN_NAVEGADOR"):
        return False
    webbrowser.open(f"http://127.0.0.1:{puerto}")
    return True
```

En `main`, reemplazar el bloque desde `puerto = buscar_instancia()` hasta `return servidor.arrancar(puertos=PUERTOS, empaquetada=True)` por:

```python
        global _turno
        es_el_primero, _turno = tomar_el_turno()
        if not es_el_primero:
            puerto = esperar_instancia()
            if puerto is None:
                avisar("Armónica ya se está abriendo pero todavía no contesta. "
                       "Esperá un momento y volvé a probar.")
                return 1
            print(f"Otro lanzador la está abriendo en el {puerto}: solo abro el navegador.")
            abrir_el_navegador(puerto)
            return 0

        # Una app de una versión anterior, sin turno, también cuenta.
        puerto = buscar_instancia()
        if puerto is not None:
            print(f"Ya estaba abierta en el {puerto}: solo abro el navegador.")
            abrir_el_navegador(puerto)
            return 0

        # Recién ahora: con la carpeta y el entorno listos.
        from armonica import servidor
        try:
            return servidor.arrancar(puertos=PUERTOS, empaquetada=True,
                                     abrir_navegador=not os.environ.get("ARMONICA_SIN_NAVEGADOR"))
```

(el `except servidor.PuertoOcupado` que sigue queda igual). En el docstring del módulo, al final de "Para probarlo desde el repo", sumar la línea:

```
    set ARMONICA_SIN_NAVEGADOR=1     (opcional: no abre el navegador)
```

- [ ] **Step 4: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_lanzador.py -v`
Expected: todo pasa (14 en Windows).

- [ ] **Step 5: Commit**

```bash
git add armonica/lanzador.py tests/test_lanzador.py
git commit -m "Un doble clic rapido en el icono abre una sola app, y la prueba puede arrancarla sin navegador" -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 5: Fotos HEIC con pillow-heif o pi-heif

**Files:**
- Modify: `armonica/imagenes.py` (`import importlib`, `_modulo_heif`, `hay_soporte_heic`, `como_jpg`, docstring del módulo)
- Modify: `tests/test_canciones.py`

**Interfaces:**
- Produces: `imagenes._modulo_heif() -> módulo | None` (prueba `pillow_heif` y después `pi_heif`). `hay_soporte_heic()` y `como_jpg()` lo usan.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_canciones.py` (sumar `import sys` y `import types` arriba), después de los tests de imágenes existentes:

```python
def test_sin_pillow_heif_sirve_pi_heif(monkeypatch):
    """El instalador lleva pi-heif: solo lee, y no trae el codificador x265 (GPL)."""
    pi_heif = types.SimpleNamespace(register_heif_opener=lambda: None)
    monkeypatch.setitem(sys.modules, "pillow_heif", None)
    monkeypatch.setitem(sys.modules, "pi_heif", pi_heif)
    assert imagenes._modulo_heif() is pi_heif
    assert imagenes.hay_soporte_heic() is True


def test_sin_ninguna_de_las_dos_no_hay_heic(monkeypatch):
    monkeypatch.setitem(sys.modules, "pillow_heif", None)
    monkeypatch.setitem(sys.modules, "pi_heif", None)
    assert imagenes._modulo_heif() is None
    assert imagenes.hay_soporte_heic() is False
```

- [ ] **Step 2: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_canciones.py -k "pi_heif or ninguna" -v`
Expected: FAIL con `AttributeError: module 'armonica.imagenes' has no attribute '_modulo_heif'`.

- [ ] **Step 3: Implementar**

En `armonica/imagenes.py`, sumar `import importlib` y reemplazar `hay_soporte_heic` por:

```python
def _modulo_heif():
    """
    La biblioteca que le enseña a Pillow a leer HEIC: pillow-heif (la que se
    instala en el repo) o pi-heif (la que lleva el instalador). Se usan
    igual; pi-heif solo lee, y por eso no trae el codificador x265, que es
    GPL y no puede ir en un instalador que se le pasa a otro.
    """
    for nombre in ("pillow_heif", "pi_heif"):
        try:
            return importlib.import_module(nombre)
        except ImportError:
            continue
    return None


def hay_soporte_heic():
    """Si están las dos bibliotecas que hacen falta para leer un .HEIC."""
    if _modulo_heif() is None:
        return False
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    return True
```

En `como_jpg`, reemplazar:

```python
    import pillow_heif
    from PIL import Image
    pillow_heif.register_heif_opener()
```

por:

```python
    from PIL import Image
    _modulo_heif().register_heif_opener()
```

En el docstring del módulo, después de "que le enseña a Pillow a leer HEIC.", sumar: "(o pi-heif, que es la que lleva el instalador)".

- [ ] **Step 4: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_canciones.py -q`
Expected: todo pasa.

- [ ] **Step 5: Commit**

```bash
git add armonica/imagenes.py tests/test_canciones.py
git commit -m "Las fotos HEIC se leen con pillow-heif o con pi-heif, la del instalador" -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 6: Las piezas del armado

**Files:**
- Create: `herramientas/empaquetar.py` (constantes y funciones puras; el CLI llega en las Tasks 7-9)
- Create: `empaquetado/descargas.json`, `empaquetado/requisitos.in`
- Create: `tests/test_empaquetar.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces (en `herramientas.empaquetar`):
  - Constantes `RAIZ`, `EMPAQUETADO`, `DESCARGAS`, `RUEDAS`, `ARMADO`, `DIST` (todas `Path`), `ARCHIVOS_SUELTOS = ("config.py", "VERSION", "lanzador.pyw", "LICENSE")`, `PTH = "python314._pth"`, `LINEAS_PTH`.
  - `sha256_de(ruta) -> str`
  - `leer_descargas(ruta=None) -> {nombre: {"nombre","archivo","url","sha256"}}`
  - `bajar(descarga, carpeta=None, abrir=urllib.request.urlopen) -> Path`
  - `archivos_de_la_app(raiz) -> list[str]` (rutas relativas con `/`)
  - `escribir_pth(carpeta_python) -> None`
  - `cambios_sin_commitear(porcelain: str) -> list[str]`
  - `extraer_ffmpeg(zip_ffmpeg, carpeta_ffmpeg, carpeta_licencia) -> None`
  - `copiar_licencias(site_packages, destino) -> list[str]` (los paquetes sin licencia)
  - `nombre_canonico(nombre) -> str`, `leer_requisitos_in(texto) -> {canónico: (nombre, versión)}`, `requisitos_con_hash(ruedas, fijados) -> str`
  - `texto_leeme_licencias(descargas) -> str`
  - `buscar_iscc(entorno=None) -> Path | None`, `nombre_del_instalador(version) -> str`

- [ ] **Step 1: Los datos fijados y el .gitignore**

`empaquetado/descargas.json`:

```json
[
  {
    "nombre": "python",
    "archivo": "python-3.14.6-embed-amd64.zip",
    "url": "https://www.python.org/ftp/python/3.14.6/python-3.14.6-embed-amd64.zip",
    "sha256": "df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c"
  },
  {
    "nombre": "ffmpeg",
    "archivo": "ffmpeg-n8.1.3-14-g330caae0c1-win64-lgpl-8.1.zip",
    "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-10-01-13-06/ffmpeg-n8.1.3-14-g330caae0c1-win64-lgpl-8.1.zip",
    "sha256": "84e4495b9883dbf3997435943d2d7057cc55a4c31973f7422f56b1b56974006d"
  }
]
```

`empaquetado/requisitos.in`:

```
# Lo que va en site-packages del programa instalado, con versiones fijas.
# Una línea nombre==versión por paquete, dependencias incluidas: nada entra
# sin que alguien lo elija. Después de cambiar algo:
#     python -m herramientas.empaquetar fijar
numpy==2.5.3
sounddevice==0.5.6
cffi==2.1.1
pycparser==3.0
rich==15.0.0
markdown-it-py==4.2.0
mdurl==0.1.2
Pygments==2.21.0
pillow==12.3.0
pi-heif==1.4.0
pypdf==6.19.0
```

En `.gitignore`, al final:

```
# El armado del instalador (herramientas/empaquetar.py)
empaquetado/_descargas/
empaquetado/_armado/
empaquetado/ejemplos/
dist/
```

- [ ] **Step 2: Escribir los tests que fallan**

`tests/test_empaquetar.py`:

```python
"""
Tests de herramientas/empaquetar.py — las piezas del armado del instalador.

Nada de esto baja algo de internet ni toca el repo: todo pasa en tmp_path.

Cómo correrlos:   .venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -v
"""

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from herramientas import empaquetar


def test_las_descargas_fijadas_se_leen():
    descargas = empaquetar.leer_descargas()
    assert set(descargas) == {"python", "ffmpeg"}
    assert descargas["python"]["url"].startswith("https://www.python.org/")
    assert len(descargas["ffmpeg"]["sha256"]) == 64


def test_una_descarga_incompleta_es_un_error(tmp_path):
    ruta = tmp_path / "descargas.json"
    ruta.write_text('[{"nombre": "python", "url": "x"}]', encoding="utf-8")
    with pytest.raises(ValueError, match="archivo"):
        empaquetar.leer_descargas(ruta)


def _descarga(contenido, sha256=None):
    return {"nombre": "x", "archivo": "x.zip", "url": "https://example.invalid/x.zip",
            "sha256": sha256 or hashlib.sha256(contenido).hexdigest()}


def test_bajar_verifica_el_sha256(tmp_path):
    contenido = b"contenido de prueba"
    destino = empaquetar.bajar(_descarga(contenido), tmp_path,
                               abrir=lambda url: io.BytesIO(contenido))
    assert destino.read_bytes() == contenido


def test_un_sha256_distinto_no_se_usa(tmp_path):
    with pytest.raises(ValueError, match="no coincide"):
        empaquetar.bajar(_descarga(b"bueno", sha256="0" * 64), tmp_path,
                         abrir=lambda url: io.BytesIO(b"bueno"))
    assert list(tmp_path.iterdir()) == []


def test_lo_ya_bajado_no_se_vuelve_a_bajar(tmp_path):
    contenido = b"ya estaba"
    (tmp_path / "x.zip").write_bytes(contenido)

    def no_bajar(url):
        raise AssertionError("no tenía que bajar")

    assert empaquetar.bajar(_descarga(contenido), tmp_path, abrir=no_bajar).read_bytes() == contenido


def test_los_archivos_de_la_app(tmp_path):
    for nombre in empaquetar.ARCHIVOS_SUELTOS:
        (tmp_path / nombre).write_text("x", encoding="utf-8")
    (tmp_path / "armonica" / "web").mkdir(parents=True)
    (tmp_path / "armonica" / "__pycache__").mkdir()
    (tmp_path / "armonica" / "servidor.py").write_text("x", encoding="utf-8")
    (tmp_path / "armonica" / "web" / "app.js").write_text("x", encoding="utf-8")
    (tmp_path / "armonica" / "__pycache__" / "servidor.cpython-314.pyc").write_bytes(b"x")
    (tmp_path / "main.py").write_text("x", encoding="utf-8")
    assert empaquetar.archivos_de_la_app(tmp_path) == [
        "config.py", "VERSION", "lanzador.pyw", "LICENSE",
        "armonica/servidor.py", "armonica/web/app.js"]


def test_sin_un_archivo_suelto_no_se_arma(tmp_path):
    (tmp_path / "armonica").mkdir()
    with pytest.raises(ValueError, match="config.py"):
        empaquetar.archivos_de_la_app(tmp_path)


def test_el_pth_del_python_embebido(tmp_path):
    empaquetar.escribir_pth(tmp_path)
    assert (tmp_path / "python314._pth").read_text(encoding="utf-8").splitlines() == [
        "python314.zip", ".", "Lib\\site-packages", "..\\app"]


def test_los_cambios_sin_commitear_que_irian_al_paquete():
    porcelain = (" M config.py\n"
                 "?? EVALUATION_2026-09-18.md\n"
                 " M armonica/servidor.py\n"
                 "R  viejo.py -> armonica/nuevo.py\n"
                 " M README.md\n")
    assert empaquetar.cambios_sin_commitear(porcelain) == [
        "config.py", "armonica/servidor.py", "armonica/nuevo.py"]


def test_de_ffmpeg_solo_el_ejecutable_y_su_licencia(tmp_path):
    zip_falso = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(zip_falso, "w") as z:
        z.writestr("ffmpeg-n8.1/bin/ffmpeg.exe", b"exe")
        z.writestr("ffmpeg-n8.1/bin/ffprobe.exe", b"otro")
        z.writestr("ffmpeg-n8.1/LICENSE.txt", b"LGPL")
        z.writestr("ffmpeg-n8.1/doc/ffmpeg.html", b"doc")
    empaquetar.extraer_ffmpeg(zip_falso, tmp_path / "ffmpeg", tmp_path / "licencias")
    assert sorted(p.name for p in (tmp_path / "ffmpeg").iterdir()) == ["ffmpeg.exe"]
    assert (tmp_path / "licencias" / "LICENSE.txt").read_bytes() == b"LGPL"


def test_un_zip_sin_ffmpeg_es_un_error(tmp_path):
    zip_falso = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(zip_falso, "w") as z:
        z.writestr("otra-cosa/LICENSE.txt", b"x")
    with pytest.raises(ValueError, match="ffmpeg.exe"):
        empaquetar.extraer_ffmpeg(zip_falso, tmp_path / "f", tmp_path / "l")


def test_las_licencias_de_cada_paquete(tmp_path):
    site = tmp_path / "site-packages"
    (site / "numpy-2.5.3.dist-info").mkdir(parents=True)
    (site / "numpy-2.5.3.dist-info" / "LICENSE.txt").write_text("BSD", encoding="utf-8")
    (site / "pi_heif-1.4.0.dist-info" / "licenses").mkdir(parents=True)
    (site / "pi_heif-1.4.0.dist-info" / "licenses" / "LICENSE.txt").write_text("LGPL", encoding="utf-8")
    (site / "mdurl-0.1.2.dist-info").mkdir()
    (site / "mdurl-0.1.2.dist-info" / "METADATA").write_text("x", encoding="utf-8")
    (site / "_sounddevice_data" / "portaudio-binaries").mkdir(parents=True)
    (site / "_sounddevice_data" / "portaudio-binaries" / "README.md").write_text("PA", encoding="utf-8")

    sin_licencia = empaquetar.copiar_licencias(site, tmp_path / "licencias")

    assert (tmp_path / "licencias" / "numpy" / "LICENSE.txt").read_text(encoding="utf-8") == "BSD"
    assert (tmp_path / "licencias" / "pi_heif" / "LICENSE.txt").read_text(encoding="utf-8") == "LGPL"
    assert (tmp_path / "licencias" / "portaudio" / "README.md").read_text(encoding="utf-8") == "PA"
    assert sin_licencia == ["mdurl"]


def test_los_requisitos_con_su_hash(tmp_path):
    fijados = empaquetar.leer_requisitos_in("# comentario\nnumpy==2.5.3\nmarkdown-it-py==4.2.0\n")
    assert fijados == {"numpy": ("numpy", "2.5.3"), "markdown-it-py": ("markdown-it-py", "4.2.0")}
    numpy = tmp_path / "numpy-2.5.3-cp314-cp314-win_amd64.whl"
    numpy.write_bytes(b"n")
    md = tmp_path / "markdown_it_py-4.2.0-py3-none-any.whl"
    md.write_bytes(b"m")

    texto = empaquetar.requisitos_con_hash([numpy, md], fijados)

    assert f"numpy==2.5.3 --hash=sha256:{hashlib.sha256(b'n').hexdigest()}" in texto
    assert f"markdown-it-py==4.2.0 --hash=sha256:{hashlib.sha256(b'm').hexdigest()}" in texto


def test_una_rueda_sin_fijar_es_un_error(tmp_path):
    fijados = empaquetar.leer_requisitos_in("numpy==2.5.3\n")
    numpy = tmp_path / "numpy-2.5.3-cp314-cp314-win_amd64.whl"
    numpy.write_bytes(b"n")
    colado = tmp_path / "colado-1.0-py3-none-any.whl"
    colado.write_bytes(b"c")
    with pytest.raises(ValueError, match="colado"):
        empaquetar.requisitos_con_hash([numpy, colado], fijados)
    with pytest.raises(ValueError, match="numpy"):
        empaquetar.requisitos_con_hash([], fijados)


def test_requisitos_in_mal_escrito():
    with pytest.raises(ValueError):
        empaquetar.leer_requisitos_in("numpy>=2\n")


def test_el_leeme_de_licencias_dice_de_donde_sale_ffmpeg():
    texto = empaquetar.texto_leeme_licencias(empaquetar.leer_descargas())
    assert "github.com/BtbN/FFmpeg-Builds" in texto
    assert "LGPL" in texto
    assert "3.14.6" in texto


def test_buscar_inno_setup(tmp_path):
    iscc = tmp_path / "Programs" / "Inno Setup 6" / "ISCC.exe"
    iscc.parent.mkdir(parents=True)
    iscc.write_bytes(b"")
    assert empaquetar.buscar_iscc({"LOCALAPPDATA": str(tmp_path)}) == iscc
    assert empaquetar.buscar_iscc({"LOCALAPPDATA": str(tmp_path / "nada")}) is None


def test_el_nombre_del_instalador():
    assert empaquetar.nombre_del_instalador("0.1.0") == "Armonica-0.1.0-instalador.exe"
```

- [ ] **Step 3: Correrlos y ver que fallan**

Run: `.venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -v`
Expected: ERROR de colección con `ImportError: cannot import name 'empaquetar' from 'herramientas'`.

- [ ] **Step 4: Escribir `herramientas/empaquetar.py` (las piezas)**

```python
"""
empaquetar.py — Arma el instalador de Windows de Armónica, para el profe.

Lo corre Bruno en su máquina (herramientas\\empaquetar.ps1 lo llama con el
Python del .venv). Los pasos, en orden; cualquiera que falle corta todo:

    fijar        una vez, o al cambiar una versión: baja las ruedas de
                 empaquetado/requisitos.in y escribe requisitos.txt con el
                 SHA-256 de cada una. Se commitea.
    armar        toma el código commiteado (git archive HEAD), corre los
                 tests en esa copia, baja lo que falte verificando los
                 SHA-256 y arma el programa en empaquetado/_armado/Armonica.
    humo         abre ese programa como lo abre el acceso directo, con los
                 datos en una carpeta temporal y sin navegador, y lo cierra.
    instalador   compila empaquetado/armonica.iss con Inno Setup a dist/.

Sin argumentos hace armar, humo e instalador.

POR QUÉ git archive Y NO LA CARPETA: en la carpeta de trabajo están el
config.py con los valores de la máquina de Bruno y el .env con la clave del
coach. Al paquete va solo lo commiteado.
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EMPAQUETADO = RAIZ / "empaquetado"
DESCARGAS = EMPAQUETADO / "_descargas"
RUEDAS = DESCARGAS / "ruedas"
ARMADO = EMPAQUETADO / "_armado" / "Armonica"
DIST = RAIZ / "dist"

# Lo que va a {app}\app además del paquete armonica.
ARCHIVOS_SUELTOS = ("config.py", "VERSION", "lanzador.pyw", "LICENSE")

# Con este archivo el Python embebido usa exactamente estas rutas y nada del
# sistema. ..\app es donde está el código (lo asume lanzador.CARPETA_PROGRAMA).
PTH = "python314._pth"
LINEAS_PTH = ("python314.zip", ".", "Lib\\site-packages", "..\\app")

# Las ruedas para el programa instalado: Windows de 64 bits, CPython 3.14,
# solo binarias (nada se compila en la máquina de Bruno).
OPCIONES_DE_RUEDAS = ["--only-binary=:all:", "--platform", "win_amd64",
                      "--python-version", "3.14", "--implementation", "cp"]


def sha256_de(ruta):
    hash_ = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            hash_.update(bloque)
    return hash_.hexdigest()


def leer_descargas(ruta=None):
    """Lo que se baja de afuera, con su SHA-256 fijo: {nombre: descarga}."""
    with open(ruta or EMPAQUETADO / "descargas.json", encoding="utf-8") as archivo:
        descargas = json.load(archivo)
    for descarga in descargas:
        faltan = {"nombre", "archivo", "url", "sha256"} - set(descarga)
        if faltan:
            raise ValueError(f"A la descarga {descarga.get('nombre', '?')} le falta: "
                             f"{', '.join(sorted(faltan))}.")
    return {descarga["nombre"]: descarga for descarga in descargas}


def bajar(descarga, carpeta=None, abrir=urllib.request.urlopen):
    """
    El archivo de `descarga`, en `carpeta`: el que ya estaba si su SHA-256
    es el fijado, si no se baja. Si lo bajado no coincide, se borra y es un
    error: nunca se usa algo distinto de lo fijado.
    """
    carpeta = Path(carpeta or DESCARGAS)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / descarga["archivo"]
    if destino.is_file() and sha256_de(destino) == descarga["sha256"]:
        return destino
    parcial = destino.with_name(destino.name + ".parcial")
    print(f"  Bajando {descarga['archivo']}...")
    with abrir(descarga["url"]) as respuesta, open(parcial, "wb") as archivo:
        shutil.copyfileobj(respuesta, archivo)
    obtenido = sha256_de(parcial)
    if obtenido != descarga["sha256"]:
        parcial.unlink()
        raise ValueError(f"{descarga['archivo']}: el SHA-256 no coincide (fijado "
                         f"{descarga['sha256']}, vino {obtenido}). No se usa.")
    os.replace(parcial, destino)
    return destino


def archivos_de_la_app(raiz):
    """Lo que va a {app}\\app: los sueltos y el paquete armonica, sin cachés."""
    raiz = Path(raiz)
    faltan = [nombre for nombre in ARCHIVOS_SUELTOS if not (raiz / nombre).is_file()]
    if faltan:
        raise ValueError(f"Faltan en el código: {', '.join(faltan)}.")
    archivos = list(ARCHIVOS_SUELTOS)
    for ruta in sorted((raiz / "armonica").rglob("*")):
        if ruta.is_file() and "__pycache__" not in ruta.parts and ruta.suffix != ".pyc":
            archivos.append(ruta.relative_to(raiz).as_posix())
    return archivos


def escribir_pth(carpeta_python):
    (Path(carpeta_python) / PTH).write_text("\n".join(LINEAS_PTH) + "\n", encoding="utf-8")


def cambios_sin_commitear(porcelain):
    """De `git status --porcelain`, los archivos que irían al paquete."""
    cambiados = []
    for linea in porcelain.splitlines():
        ruta = linea[3:].strip().strip('"')
        if " -> " in ruta:
            ruta = ruta.split(" -> ", 1)[1]
        if ruta in ARCHIVOS_SUELTOS or ruta.startswith("armonica/"):
            cambiados.append(ruta)
    return cambiados


def extraer_ffmpeg(zip_ffmpeg, carpeta_ffmpeg, carpeta_licencia):
    """Del zip de BtbN, solo bin/ffmpeg.exe y su LICENSE.txt."""
    carpeta_ffmpeg = Path(carpeta_ffmpeg)
    carpeta_licencia = Path(carpeta_licencia)
    encontrados = set()
    with zipfile.ZipFile(zip_ffmpeg) as zip_:
        for nombre in zip_.namelist():
            partes = nombre.split("/")
            if partes[-2:] == ["bin", "ffmpeg.exe"]:
                carpeta_ffmpeg.mkdir(parents=True, exist_ok=True)
                (carpeta_ffmpeg / "ffmpeg.exe").write_bytes(zip_.read(nombre))
                encontrados.add("ffmpeg.exe")
            elif len(partes) == 2 and partes[1] == "LICENSE.txt":
                carpeta_licencia.mkdir(parents=True, exist_ok=True)
                (carpeta_licencia / "LICENSE.txt").write_bytes(zip_.read(nombre))
                encontrados.add("LICENSE.txt")
    faltan = {"ffmpeg.exe", "LICENSE.txt"} - encontrados
    if faltan:
        raise ValueError(f"El zip de ffmpeg no trae: {', '.join(sorted(faltan))}.")


def copiar_licencias(site_packages, destino):
    """
    Las licencias de cada paquete instalado (lo que trae su .dist-info) a
    destino/<paquete>/, más el README de PortAudio, que viaja adentro de
    sounddevice y es la licencia de esa biblioteca. Devuelve los paquetes
    que no traían ninguna, para avisar.
    """
    site_packages = Path(site_packages)
    destino = Path(destino)
    sin_licencia = []
    for info in sorted(site_packages.glob("*.dist-info")):
        paquete = info.name[: -len(".dist-info")].rsplit("-", 1)[0]
        copiadas = 0
        for archivo in sorted(info.rglob("*")):
            relativo = archivo.relative_to(info)
            es_licencia = (relativo.parts[0] == "licenses" or archivo.name.upper().startswith(
                ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")))
            if not archivo.is_file() or not es_licencia:
                continue
            if relativo.parts[0] == "licenses":
                relativo = Path(*relativo.parts[1:])
            final = destino / paquete / relativo
            final.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archivo, final)
            copiadas += 1
        if not copiadas:
            sin_licencia.append(paquete)
    portaudio = site_packages / "_sounddevice_data" / "portaudio-binaries" / "README.md"
    if portaudio.is_file():
        (destino / "portaudio").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(portaudio, destino / "portaudio" / "README.md")
    return sin_licencia


def nombre_canonico(nombre):
    return re.sub(r"[-_.]+", "-", nombre).lower()


def leer_requisitos_in(texto):
    """{nombre canónico: (nombre, versión)}: una línea nombre==versión por paquete."""
    fijados = {}
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        nombre, separador, version = linea.partition("==")
        if not separador or not nombre.strip() or not version.strip():
            raise ValueError(f"En requisitos.in cada línea es nombre==versión: {linea!r}")
        fijados[nombre_canonico(nombre.strip())] = (nombre.strip(), version.strip())
    return fijados


def requisitos_con_hash(ruedas, fijados):
    """
    El texto de requisitos.txt: cada paquete fijado con el SHA-256 de su
    rueda. Una rueda que no está fijada (una dependencia nueva) o un paquete
    fijado sin su rueda es un error: lo que entra al paquete se elige a mano.
    """
    con_hash = {}
    for rueda in ruedas:
        rueda = Path(rueda)
        nombre, version = rueda.name.split("-")[:2]
        canonico = nombre_canonico(nombre)
        if canonico not in fijados:
            raise ValueError(f"pip trajo {rueda.name}, que no está en requisitos.in: fijalo a mano.")
        if fijados[canonico][1] != version:
            raise ValueError(f"{rueda.name} no es la versión fijada ({fijados[canonico][1]}).")
        con_hash[canonico] = sha256_de(rueda)
    faltan = sorted(set(fijados) - set(con_hash))
    if faltan:
        raise ValueError(f"Sin rueda para Windows y Python 3.14: {', '.join(faltan)}.")
    lineas = ["# Generado por `python -m herramientas.empaquetar fijar`: no editar a mano."]
    for canonico in sorted(con_hash):
        nombre, version = fijados[canonico]
        lineas.append(f"{nombre}=={version} --hash=sha256:{con_hash[canonico]}")
    return "\n".join(lineas) + "\n"


def texto_leeme_licencias(descargas):
    """licencias\\LEEME.txt: qué hay adentro y de dónde sale cada cosa."""
    ffmpeg = descargas["ffmpeg"]
    python = descargas["python"]
    version_python = re.search(r"python-([\d.]+)-embed", python["archivo"]).group(1)
    return (
        "Armónica viene con estas piezas, cada una con su licencia en esta carpeta.\n\n"
        "Armónica (MIT): Armonica\\LICENSE\n"
        f"Python {version_python} embebido (PSF): Python\\LICENSE.txt\n"
        f"  {python['url']}\n"
        "Paquetes de Python: una carpeta por paquete, con lo que trae cada uno.\n"
        "PortAudio (lo usa sounddevice): portaudio\\README.md\n"
        "ffmpeg (LGPL 2.1 o posterior), compilado por BtbN/FFmpeg-Builds: ffmpeg\\LICENSE.txt\n"
        f"  binario: {ffmpeg['url']}\n"
        "  código fuente de FFmpeg: https://git.ffmpeg.org/ffmpeg.git\n"
        "  scripts con que se compiló: https://github.com/BtbN/FFmpeg-Builds\n"
    )


def buscar_iscc(entorno=None):
    """El compilador de Inno Setup, o None si no está instalado."""
    entorno = os.environ if entorno is None else entorno
    candidatos = []
    if entorno.get("ISCC"):
        candidatos.append(Path(entorno["ISCC"]))
    if entorno.get("LOCALAPPDATA"):
        candidatos.append(Path(entorno["LOCALAPPDATA"]) / "Programs" / "Inno Setup 6" / "ISCC.exe")
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        if entorno.get(variable):
            candidatos.append(Path(entorno[variable]) / "Inno Setup 6" / "ISCC.exe")
    return next((candidato for candidato in candidatos if candidato.is_file()), None)


def nombre_del_instalador(version):
    return f"Armonica-{version}-instalador.exe"
```

(Los imports `argparse`, `io`, `subprocess`, `sys`, `tarfile` y `tempfile` los usan las Tasks 7-9; si el linter del implementador se queja, dejarlos igual: el archivo se completa en esas tareas.)

- [ ] **Step 5: Correr los tests y verlos pasar**

Run: `.venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -v`
Expected: 18 passed.

- [ ] **Step 6: Commit**

```bash
git add herramientas/empaquetar.py empaquetado/descargas.json empaquetado/requisitos.in tests/test_empaquetar.py .gitignore
git commit -m "Las piezas del armado del instalador: descargas fijadas con su SHA-256, archivos de la app y licencias" -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 7: Fijar las ruedas

**Files:**
- Modify: `herramientas/empaquetar.py` (`fijar`, `main` con el paso `fijar`)
- Create (generado): `empaquetado/requisitos.txt`

**Interfaces:**
- Consumes: `leer_requisitos_in`, `requisitos_con_hash`, `RUEDAS`, `OPCIONES_DE_RUEDAS` (Task 6).
- Produces: `empaquetar.fijar() -> Path` (la ruta de requisitos.txt); `empaquetar.main(argv=None) -> int` con `paso` en `fijar | armar | humo | instalador | todo` (las Tasks 8 y 9 completan los otros) y `--programa`.

Esta tarea BAJA ruedas de PyPI (unos 30 MB). Necesita el permiso de Bruno, pedido antes de empezar la ejecución del plan.

- [ ] **Step 1: Implementar `fijar` y el `main`**

Al final de `herramientas/empaquetar.py`:

```python
def _pip(*argumentos):
    """pip del .venv: el mismo Python 3.14 que el embebido."""
    subprocess.run([sys.executable, "-m", "pip", *argumentos], check=True)


def fijar():
    """
    Baja las ruedas de requisitos.in para Windows y Python 3.14, con sus
    dependencias, y escribe requisitos.txt con el SHA-256 de cada una. Si pip
    trae algo que no está en requisitos.in, corta: hay que fijarlo a mano.
    """
    requisitos_in = EMPAQUETADO / "requisitos.in"
    fijados = leer_requisitos_in(requisitos_in.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="armonica-ruedas-") as temporal:
        _pip("download", "-r", str(requisitos_in), "-d", temporal, *OPCIONES_DE_RUEDAS)
        ruedas = sorted(Path(temporal).glob("*.whl"))
        texto = requisitos_con_hash(ruedas, fijados)
        if RUEDAS.exists():
            shutil.rmtree(RUEDAS)
        RUEDAS.mkdir(parents=True)
        for rueda in ruedas:
            shutil.copy2(rueda, RUEDAS / rueda.name)
    destino = EMPAQUETADO / "requisitos.txt"
    destino.write_text(texto, encoding="utf-8")
    print(f"  Fijadas {len(fijados)} ruedas en {destino.relative_to(RAIZ)}. Commitealo.")
    return destino


def main(argv=None):
    parser = argparse.ArgumentParser(description="Arma el instalador de Windows de Armónica.")
    parser.add_argument("paso", nargs="?", default="todo",
                        choices=["fijar", "armar", "humo", "instalador", "todo"])
    parser.add_argument("--programa", default=None,
                        help="la carpeta del programa para `humo` (por defecto, la armada)")
    argumentos = parser.parse_args(argv)
    if argumentos.paso == "fijar":
        fijar()
        return 0
    raise SystemExit(f"El paso {argumentos.paso} todavía no está.")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Correr `fijar` de verdad**

Run (desde la raíz del repo): `.venv/Scripts/python.exe -m herramientas.empaquetar fijar`
Expected: pip baja 11 ruedas; termina con "Fijadas 11 ruedas en empaquetado\requisitos.txt. Commitealo." Si pip trae una rueda que no está en `requisitos.in` (`ValueError: pip trajo ...`), o falta una (`Sin rueda para Windows y Python 3.14: ...`), PARAR y reportar el mensaje: la lista se decide con el controlador, no se agrega sola.

Verificar: `empaquetado/requisitos.txt` tiene 11 líneas `nombre==versión --hash=sha256:<64 hex>` más el comentario, y `empaquetado/_descargas/ruedas/` tiene 11 `.whl`.

- [ ] **Step 3: Correr los tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -q`
Expected: todo pasa.

- [ ] **Step 4: Commit**

```bash
git add herramientas/empaquetar.py empaquetado/requisitos.txt
git commit -m "Las ruedas del instalador quedan fijadas con su SHA-256" -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 8: Armar el programa y la prueba de humo

**Files:**
- Modify: `herramientas/empaquetar.py` (`avisar_cambios`, `copiar_commiteado`, `correr_tests`, `armar`, `humo`, ayudantes HTTP; `main` con `armar` y `humo`)

**Interfaces:**
- Consumes: todo lo de la Task 6; `fijar`/`_pip` (Task 7); `lanzador.buscar_instancia`, `lanzador.esperar_instancia`, `ARMONICA_SIN_NAVEGADOR` (Task 4); `imagenes.hay_soporte_heic` con pi-heif (Task 5); `audio.hay_ffmpeg`.
- Produces: `empaquetar.armar() -> str` (la versión armada), `empaquetar.humo(programa=None, espera=30.0) -> None`.

Esta tarea BAJA el Python embebido (12 MB) y ffmpeg (170 MB), y abre la app armada (que prende el micrófono) sin navegador. Necesita el permiso de Bruno, pedido antes de empezar.

- [ ] **Step 1: Implementar `armar`**

En `herramientas/empaquetar.py`, antes de `main`:

```python
def avisar_cambios():
    """Lo que está cambiado sin commitear no entra: se avisa y se sigue."""
    porcelain = subprocess.run(["git", "status", "--porcelain"], cwd=RAIZ, check=True,
                               capture_output=True, text=True).stdout
    for ruta in cambios_sin_commitear(porcelain):
        print(f"  Aviso: {ruta} tiene cambios sin commitear: no entran al paquete.")


def copiar_commiteado(destino):
    """El código de HEAD, tal cual está commiteado, en `destino`."""
    archivo = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=RAIZ,
                             check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archivo)) as tar:
        tar.extractall(destino, filter="data")


def correr_tests(codigo):
    """Los tests en la copia commiteada. Si fallan, no se arma nada."""
    print("  Corriendo los tests sobre lo commiteado...")
    resultado = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                               cwd=codigo)
    if resultado.returncode != 0:
        raise SystemExit("Los tests fallan sobre lo commiteado: no se arma.")


def armar():
    """
    El programa en empaquetado/_armado/Armonica, con el layout que espera
    el lanzador. Devuelve la versión.
    """
    avisar_cambios()
    descargas = leer_descargas()
    with tempfile.TemporaryDirectory(prefix="armonica-armado-") as temporal:
        codigo = Path(temporal) / "codigo"
        copiar_commiteado(codigo)
        correr_tests(codigo)
        zip_python = bajar(descargas["python"])
        zip_ffmpeg = bajar(descargas["ffmpeg"])
        requisitos = EMPAQUETADO / "requisitos.txt"
        _pip("download", "--require-hashes", "-r", str(requisitos), "-d", str(RUEDAS),
             *OPCIONES_DE_RUEDAS)

        if ARMADO.exists():
            shutil.rmtree(ARMADO)
        python = ARMADO / "python"
        with zipfile.ZipFile(zip_python) as zip_:
            zip_.extractall(python)
        escribir_pth(python)
        site_packages = python / "Lib" / "site-packages"
        _pip("install", "--no-index", "--find-links", str(RUEDAS), "--require-hashes",
             "-r", str(requisitos), "--target", str(site_packages))

        for relativo in archivos_de_la_app(codigo):
            final = ARMADO / "app" / relativo
            final.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(codigo / relativo, final)
        shutil.copyfile(codigo / "Armonica.ico", ARMADO / "Armonica.ico")

        licencias = ARMADO / "licencias"
        extraer_ffmpeg(zip_ffmpeg, ARMADO / "ffmpeg", licencias / "ffmpeg")
        (licencias / "Armonica").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(codigo / "LICENSE", licencias / "Armonica" / "LICENSE")
        (licencias / "Python").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(python / "LICENSE.txt", licencias / "Python" / "LICENSE.txt")
        for paquete in copiar_licencias(site_packages, licencias):
            print(f"  Aviso: {paquete} no trae archivo de licencia en su .dist-info.")
        (licencias / "LEEME.txt").write_text(texto_leeme_licencias(descargas), encoding="utf-8")

        version = (codigo / "VERSION").read_text(encoding="utf-8").strip()
    print(f"  Armado {version} en {ARMADO.relative_to(RAIZ)}.")
    return version
```

- [ ] **Step 2: Implementar `humo`**

```python
# Lo que el programa armado tiene que poder importar y encontrar.
CHEQUEO_DE_BIBLIOTECAS = (
    "import numpy, sounddevice, rich, pypdf; "
    "from armonica import audio, imagenes; "
    "assert imagenes.hay_soporte_heic(), 'falta el soporte de fotos HEIC'; "
    "assert audio.hay_ffmpeg(), 'falta ffmpeg'; "
    "print('  Bibliotecas: ok')"
)


def _traer_json(url):
    with urllib.request.urlopen(url, timeout=15) as respuesta:
        return json.loads(respuesta.read())


def _mandar_json(url, cuerpo):
    pedido = urllib.request.Request(url, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
                                    headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=15) as respuesta:
        return json.loads(respuesta.read())


def humo(programa=None, espera=30.0):
    """
    Abre el programa armado (o instalado) como lo abre el acceso directo
    (pythonw + lanzador.pyw), con los datos en una carpeta temporal y sin
    navegador; verifica que conteste como la versión instalada y lo cierra
    con /api/apagar, el botón de Ajustes. Prende el micrófono un momento.
    """
    from armonica import lanzador

    programa = Path(programa or ARMADO)
    if lanzador.buscar_instancia() is not None:
        raise SystemExit("Hay una Armónica abierta (puertos 8000 a 8010): cerrala antes de la prueba.")
    version = (programa / "app" / "VERSION").read_text(encoding="utf-8").strip()

    with tempfile.TemporaryDirectory(prefix="armonica-humo-") as temporal:
        entorno = dict(os.environ)
        entorno["PATH"] = str(programa / "ffmpeg") + os.pathsep + entorno.get("PATH", "")
        subprocess.run([str(programa / "python" / "python.exe"), "-c", CHEQUEO_DE_BIBLIOTECAS],
                       cwd=temporal, env=entorno, check=True)

        datos = Path(temporal) / "Armonica"
        entorno_app = dict(os.environ, ARMONICA_DATOS=str(datos), ARMONICA_SIN_NAVEGADOR="1")
        proceso = subprocess.Popen([str(programa / "python" / "pythonw.exe"),
                                    str(programa / "app" / "lanzador.pyw")],
                                   cwd=str(programa / "app"), env=entorno_app)
        try:
            puerto = lanzador.esperar_instancia(espera=espera)
            if puerto is None:
                raise SystemExit("La app armada no contestó /api/hola.")
            base = f"http://127.0.0.1:{puerto}"
            inicio = _traer_json(base + "/api/inicio")
            if inicio.get("empaquetada") is not True or inicio.get("version") != version:
                raise SystemExit(f"La app armada no se presenta bien: empaquetada="
                                 f"{inicio.get('empaquetada')}, version={inicio.get('version')}.")
            if not _traer_json(base + "/api/canciones").get("ok"):
                raise SystemExit("La app armada no pudo listar las canciones.")
            if not (datos / "registro.txt").is_file():
                raise SystemExit("La app armada no escribió registro.txt.")
            if not _mandar_json(base + "/api/apagar", {}).get("ok"):
                raise SystemExit("La app armada no aceptó cerrarse.")
            proceso.wait(timeout=15)
        finally:
            if proceso.poll() is None:
                proceso.kill()
                proceso.wait()
    print(f"  Prueba de humo de {version}: ok.")
```

Y en `main`, antes del `raise SystemExit(...)` final:

```python
    if argumentos.paso == "armar":
        armar()
        return 0
    if argumentos.paso == "humo":
        humo(argumentos.programa)
        return 0
```

- [ ] **Step 3: Armar de verdad**

Run (desde la raíz del repo, con todo commiteado): `.venv/Scripts/python.exe -m herramientas.empaquetar armar`
Expected:
- avisa que `config.py` tiene cambios sin commitear (en la carpeta de Bruno) y sigue;
- los tests pasan sobre lo commiteado;
- baja `python-3.14.6-embed-amd64.zip` y el zip de ffmpeg, sin error de SHA-256 (si el de Python no coincide con el publicado por python.org, PARAR y reportar: no reemplazar el hash);
- pip instala las 11 ruedas con `--require-hashes`;
- termina con "Armado 0.1.0 en empaquetado\_armado\Armonica."

Verificar a mano que existan: `empaquetado/_armado/Armonica/python/pythonw.exe`, `.../python/python314._pth` (4 líneas), `.../python/Lib/site-packages/pi_heif/`, `.../app/armonica/servidor.py`, `.../app/VERSION`, `.../ffmpeg/ffmpeg.exe`, `.../licencias/LEEME.txt`, `.../licencias/ffmpeg/LICENSE.txt`, `.../licencias/Python/LICENSE.txt`, `.../Armonica.ico`. Que `app/config.py` sea el commiteado (umbral `0.01`, `DISPOSITIVO_ENTRADA = None`), no el local de Bruno.

- [ ] **Step 4: La prueba de humo**

Con ninguna Armónica abierta en 8000-8010 (si Bruno tiene la suya abierta, pedirle que la cierre o esperar):

Run: `.venv/Scripts/python.exe -m herramientas.empaquetar humo`
Expected: "Bibliotecas: ok" y "Prueba de humo de 0.1.0: ok."; ningún navegador se abre; al terminar, `netstat -ano` no muestra puertos 8000-8010 de esta prueba en LISTENING.

- [ ] **Step 5: Correr los tests y commitear**

Run: `.venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -q`

```bash
git add herramientas/empaquetar.py
git commit -m "Armar el programa del instalador desde lo commiteado, y probarlo como lo abre el acceso directo" -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 9: El instalador con Inno Setup

**Files:**
- Create: `empaquetado/armonica.iss`
- Create: `herramientas/empaquetar.ps1`
- Modify: `herramientas/empaquetar.py` (`instalador`, `todo` en `main`)

**Interfaces:**
- Consumes: `buscar_iscc`, `nombre_del_instalador`, `ARMADO`, `DIST`, `EMPAQUETADO` (Task 6); `armar`, `humo` (Task 8); `/api/hola` y `/api/apagar` del servidor.
- Produces: `empaquetar.instalador(programa=None) -> Path`; `dist/Armonica-0.1.0-instalador.exe`.

Esta tarea necesita Inno Setup 6 instalado. Si `buscar_iscc()` no lo encuentra, instalarlo con `winget install --id JRSoftware.InnoSetup -e` SOLO con el permiso de Bruno (pedido antes de empezar).

- [ ] **Step 1: El script de Inno Setup**

`empaquetado/armonica.iss`, guardado en **UTF-8 con BOM** (sin BOM, Inno Setup lee los acentos mal):

```iss
; armonica.iss — El instalador de Windows de Armónica, para el profe.
;
; Lo compila `python -m herramientas.empaquetar instalador`, que pasa:
;   /DVersion=0.1.0  /DArmado=<empaquetado\_armado\Armonica>
;   /DEjemplos=<empaquetado\ejemplos>  /O<dist>
;
; Instalación por usuario, sin pedir administrador, en
; %LOCALAPPDATA%\Programs\Armonica. Los datos del profe van a
; Documentos\Armonica: ni una versión nueva ni el desinstalador los tocan.

#ifndef Version
  #error Falta /DVersion
#endif
#ifndef Armado
  #error Falta /DArmado
#endif
#ifndef Ejemplos
  #define Ejemplos "ejemplos"
#endif

[Setup]
; El AppId no cambia nunca: así una versión nueva se instala encima.
AppId={{DE843E22-3123-424E-AFFC-A46A5622326D}
AppName=Armónica
AppVersion={#Version}
AppPublisher=Bruno
DefaultDirName={autopf}\Armonica
DefaultGroupName=Armónica
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=Armonica-{#Version}-instalador
SetupIconFile={#Armado}\Armonica.ico
UninstallDisplayIcon={app}\Armonica.ico
UninstallDisplayName=Armónica
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; La app la cierra el código de abajo: con pythonw no hay ventana, y el
; cierre de aplicaciones de Windows no la ve.
CloseApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Poner un ícono en el escritorio"

[Files]
Source: "{#Armado}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Los ejemplos que eligió Bruno: solo si el profe no tiene ya un archivo con
; ese nombre, y el desinstalador no los borra.
Source: "{#Ejemplos}\*"; DestDir: "{userdocs}\Armonica"; Flags: recursesubdirs createallsubdirs onlyifdoesntexist uninsneveruninstall skipifsourcedoesntexist

[Icons]
Name: "{group}\Armónica"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\lanzador.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\Armonica.ico"
Name: "{autodesktop}\Armónica"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\lanzador.pyw"""; WorkingDir: "{app}\app"; IconFilename: "{app}\Armonica.ico"; Tasks: escritorio

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\lanzador.pyw"""; WorkingDir: "{app}\app"; Description: "Abrir Armónica"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Las cachés que Python escribe al usar la app. Los datos están en
; Documentos\Armonica, fuera de {app}.
Type: filesandordirs; Name: "{app}"

[Code]
const
  PrimerPuerto = 8000;
  UltimoPuerto = 8010;

{ Cierra Armónica si está abierta: pregunta /api/hola en cada puerto y, si
  contesta, le pide /api/apagar, el mismo botón de Ajustes. Devuelve '' si
  quedó cerrada (o no estaba), o el motivo para mostrar si no se pudo. }
function CerrarLaApp(): String;
var
  Puerto: Integer;
  Pedido: Variant;
begin
  Result := '';
  for Puerto := PrimerPuerto to UltimoPuerto do
  begin
    try
      Pedido := CreateOleObject('WinHttp.WinHttpRequest.5.1');
      Pedido.SetTimeouts(300, 300, 1000, 1000);
      Pedido.Open('GET', 'http://127.0.0.1:' + IntToStr(Puerto) + '/api/hola', False);
      Pedido.Send('');
      if (Pedido.Status = 200) and (Pos('"armonica"', Pedido.ResponseText) > 0) then
      begin
        Pedido := CreateOleObject('WinHttp.WinHttpRequest.5.1');
        Pedido.SetTimeouts(300, 300, 3000, 3000);
        Pedido.Open('POST', 'http://127.0.0.1:' + IntToStr(Puerto) + '/api/apagar', False);
        Pedido.SetRequestHeader('Content-Type', 'application/json');
        Pedido.Send('{}');
        if Pos('"ok": true', Pedido.ResponseText) > 0 then
          Sleep(2000)
        else
          Result := 'Armónica está grabando. Pará la grabación, cerrala desde Ajustes y volvé a abrir este programa.';
      end;
    except
      { Nada escuchando en ese puerto, u otro programa: se sigue. }
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := CerrarLaApp();
end;

function InitializeUninstall(): Boolean;
var
  Motivo: String;
begin
  Motivo := CerrarLaApp();
  Result := Motivo = '';
  if not Result then
    MsgBox(Motivo, mbError, MB_OK);
end;
```

- [ ] **Step 2: `instalador` y `todo` en `empaquetar.py`**

Antes de `main`:

```python
def instalador(programa=None):
    """Compila empaquetado/armonica.iss con Inno Setup a dist/."""
    programa = Path(programa or ARMADO)
    iscc = buscar_iscc()
    if iscc is None:
        raise SystemExit("No encuentro Inno Setup (ISCC.exe). Se instala una vez con:\n"
                         "    winget install --id JRSoftware.InnoSetup -e")
    version = (programa / "app" / "VERSION").read_text(encoding="utf-8").strip()
    DIST.mkdir(exist_ok=True)
    subprocess.run([str(iscc), f"/DVersion={version}", f"/DArmado={programa}",
                    f"/DEjemplos={EMPAQUETADO / 'ejemplos'}", f"/O{DIST}",
                    str(EMPAQUETADO / "armonica.iss")], check=True)
    salida = DIST / nombre_del_instalador(version)
    if not salida.is_file():
        raise SystemExit(f"Inno Setup terminó pero no está {salida}.")
    print(f"  Listo: {salida}")
    return salida
```

En `main`, reemplazar el `raise SystemExit(f"El paso ... todavía no está.")` por:

```python
    if argumentos.paso == "instalador":
        instalador(argumentos.programa)
        return 0
    armar()
    humo()
    instalador()
    return 0
```

- [ ] **Step 3: El envoltorio de PowerShell**

`herramientas/empaquetar.ps1`:

```powershell
# empaquetar.ps1 - Arma el instalador de Armonica para el profe.
#
# Todo lo hace herramientas\empaquetar.py; esto solo lo llama con el Python
# del entorno virtual, desde la raiz del repo. Los pasos se pueden pedir de a
# uno:  .\herramientas\empaquetar.ps1 fijar | armar | humo | instalador
# Sin nada, arma, prueba y compila el instalador en dist\.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
& .\.venv\Scripts\python.exe -m herramientas.empaquetar @args
exit $LASTEXITCODE
```

- [ ] **Step 4: Compilar de verdad**

Con el armado de la Task 8 en su lugar:

Run: `.venv/Scripts/python.exe -m herramientas.empaquetar instalador`
Expected: ISCC compila sin errores ni advertencias de archivos faltantes y termina con "Listo: ...\dist\Armonica-0.1.0-instalador.exe". Anotar el tamaño del `.exe` en el reporte (se espera entre 60 y 120 MB).

Run también: `powershell -ExecutionPolicy Bypass -File herramientas/empaquetar.ps1 humo`
Expected: la prueba de humo pasa igual que en la Task 8 (verifica el envoltorio). En un worktree no hay `.venv` y el envoltorio no puede andar: ese chequeo se hace en la carpeta principal después del merge, y se anota en el reporte.

- [ ] **Step 5: Correr los tests y commitear**

Run: `.venv/Scripts/python.exe -m pytest tests/test_empaquetar.py -q`

```bash
git add empaquetado/armonica.iss herramientas/empaquetar.ps1 herramientas/empaquetar.py
git commit -m "El instalador con Inno Setup: por usuario, cierra la app antes de instalar y no toca los datos" -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```

---

### Task 10: Probar el instalador en una carpeta temporal

**Files:**
- Ninguno nuevo en el repo; evidencia en el reporte.

**Interfaces:**
- Consumes: `dist/Armonica-0.1.0-instalador.exe` (Task 9), `empaquetar humo --programa` (Task 8).

Instala de verdad (por usuario) en una carpeta temporal, sin íconos, y lo desinstala. Escribe y borra una entrada en `HKCU\...\Uninstall`. Necesita el permiso de Bruno, pedido antes de empezar. No tiene que tocar `Documentos` (no hay `empaquetado/ejemplos/`; si existiera, moverla a un costado durante esta prueba).

Todo en PowerShell, desde la raíz del repo (con Git Bash las rutas `/tmp/...` le llegan mal al instalador de Windows). Con un worktree, `.\.venv` es la ruta absoluta del `.venv` del repo principal.

- [ ] **Step 1: Instalar en silencio**

```powershell
$Prueba = Join-Path $env:TEMP "armonica-instalador-prueba"
$Opciones = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOICONS /TASKS=`"`" /DIR=`"$Prueba\instalado`" /LOG=`"$Prueba\instalar.log`""
$p = Start-Process -FilePath ".\dist\Armonica-0.1.0-instalador.exe" -ArgumentList $Opciones -Wait -PassThru
$p.ExitCode
```

Expected: `0`; `$Prueba\instalado` tiene `python\`, `app\`, `ffmpeg\`, `licencias\`, `Armonica.ico` y `unins000.exe`; no se creó ningún ícono ni `Documentos\Armonica`.

- [ ] **Step 2: Prueba de humo sobre lo instalado**

Run: `.\.venv\Scripts\python.exe -m herramientas.empaquetar humo --programa "$Prueba\instalado"`
Expected: "Prueba de humo de 0.1.0: ok."

- [ ] **Step 3: Instalar encima con la app abierta**

```powershell
$env:ARMONICA_SIN_NAVEGADOR = "1"; $env:ARMONICA_DATOS = "$Prueba\datos"
Start-Process "$Prueba\instalado\python\pythonw.exe" -ArgumentList "`"$Prueba\instalado\app\lanzador.pyw`""
Remove-Item Env:ARMONICA_SIN_NAVEGADOR, Env:ARMONICA_DATOS
```

Esperar a que conteste (`.\.venv\Scripts\python.exe -c "from armonica import lanzador; print(lanzador.esperar_instancia())"` imprime un puerto) y volver a correr el Step 1. Expected: código `0`; el puerto deja de escuchar (`netstat -ano`), porque el instalador cerró la app con `/api/apagar`; `$Prueba\datos\registro.txt` sigue ahí.

- [ ] **Step 4: Desinstalar**

```powershell
Start-Process "$Prueba\instalado\unins000.exe" -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait
```

El desinstalador se copia a `%TEMP%` y termina después: esperar hasta 30 segundos a que `Test-Path "$Prueba\instalado"` dé `False`. Expected: `$Prueba\instalado` ya no está; `$Prueba\datos` sigue intacto; `reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{DE843E22-3123-424E-AFFC-A46A5622326D}_is1"` da error (la clave ya no existe).

- [ ] **Step 5: Reporte**

Sin commit: anotar en el reporte cada paso con el comando y la salida. Borrar `$Prueba` al final.

---

### Task 11: Documentar el armado y la prueba en un usuario limpio

**Files:**
- Create: `empaquetado/PROBAR.md`
- Modify: `README.md` (sección nueva antes de `## Los tests`)
- Modify: `PROXIMOS_PASOS.md`

- [ ] **Step 1: `empaquetado/PROBAR.md`**

```markdown
# Probar el instalador en un Windows limpio

Antes de mandarle una versión al profe, en un segundo usuario de Windows
(Configuración → Cuentas → Otros usuarios → Agregar cuenta; Windows Home no
tiene Sandbox), sin Python ni ffmpeg instalados:

1. Subir `dist\Armonica-<versión>-instalador.exe` a Drive y bajarlo desde
   ese usuario con el navegador. Sacar una captura del aviso de SmartScreen
   ("Windows protegió su PC" → "Más información" → "Ejecutar de todas
   formas"): va a la guía.
2. Instalar: no tiene que pedir permisos de administrador.
3. Abrir desde el ícono del escritorio: se abre el navegador y no aparece
   ninguna ventana negra.
4. Hacer los primeros pasos. Tocar en En vivo: la aguja se mueve.
5. Grabar una sesión, guardar una frase, abrir una canción de ejemplo y
   reproducir su base, importar un audio de WhatsApp (usa ffmpeg), ver una
   foto .HEIC de una canción.
6. Hacer doble clic en el ícono dos veces seguidas, rápido: una sola app;
   la segunda vez solo se abre el navegador.
7. Cerrar la pestaña: al minuto se apaga el ícono de micrófono en uso de
   Windows. Ajustes → Cerrar la app: el proceso termina.
8. Instalar una versión nueva encima con la app abierta: el instalador la
   cierra; la frase y los ajustes siguen.
9. Desinstalar desde Configuración → Aplicaciones: `Documentos\Armonica`
   sigue entera.

Si algo falla, `Documentos\Armonica\registro.txt` tiene el detalle.
```

- [ ] **Step 2: README**

Antes de `## Los tests`, una sección nueva:

```markdown
## El instalador para el profe

`herramientas\empaquetar.ps1` arma `dist\Armonica-<versión>-instalador.exe`:
un instalador por usuario (sin administrador) con Python 3.14 embebido, las
bibliotecas, ffmpeg y las licencias, que abre la app con el lanzador
(`lanzador.pyw`). Hace falta Inno Setup 6 (`winget install --id
JRSoftware.InnoSetup -e`) y conexión la primera vez.

    .\herramientas\empaquetar.ps1            arma, prueba y compila
    .\herramientas\empaquetar.ps1 fijar      después de cambiar empaquetado\requisitos.in

Toma el código commiteado, no la carpeta: lo que tengas sin commitear (tu
`config.py`, por ejemplo) no entra, y lo avisa. Corre los tests sobre esa
copia, baja Python embebido, ffmpeg y las ruedas verificando el SHA-256
fijado en `empaquetado\descargas.json` y `empaquetado\requisitos.txt`
(quedan en `empaquetado\_descargas\`), arma el programa en
`empaquetado\_armado\Armonica`, lo abre como el acceso directo con una
carpeta de datos temporal y sin navegador, y lo cierra. Las fotos HEIC usan
pi-heif, que solo lee: pillow-heif trae el codificador x265, que es GPL.
Los ejemplos para el profe van en `empaquetado\ejemplos\` (no se commitean)
y se copian a su `Documentos\Armonica` solo si no tiene ya ese archivo.
Antes de mandar una versión, la prueba en un usuario limpio está en
`empaquetado\PROBAR.md`.

Para una versión nueva: cambiar `VERSION`, commitear y volver a armar. El
profe instala encima; sus datos no se tocan.
```

- [ ] **Step 3: PROXIMOS_PASOS**

Después de la entrada de la etapa 1:

```markdown
   - **Instalador, etapa 2: el armado.** Hecho (la fecha del commit,
     AAAA-MM-DD): `herramientas\empaquetar.ps1` → `dist\Armonica-<versión>-instalador.exe`
     con Python 3.14.6 embebido, ruedas fijadas con SHA-256, ffmpeg LGPL de
     BtbN, pi-heif y licencias; prueba de humo; Inno Setup por usuario que
     cierra la app antes de instalar. Además: el servidor rechaza pedidos
     de otros sitios, `ajustes.json` se guarda atómico, el vigía no se
     muere, y un doble clic rápido abre una sola app. Falta: la prueba en
     un usuario limpio (`empaquetado\PROBAR.md`) y la etapa 3 (la guía).
```

- [ ] **Step 4: Commit**

```bash
git add empaquetado/PROBAR.md README.md PROXIMOS_PASOS.md
git commit -m "README y PROBAR.md: como se arma el instalador y como se prueba en un Windows limpio" -m "Co-Authored-By: <modelo> <noreply@anthropic.com>"
```
