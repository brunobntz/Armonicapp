# Instalador para el profe — diseño

Fecha: 2026-10-02. Diseño aprobado en chat por Bruno el mismo día; esta
spec lo deja escrito y lo ajusta a lo que el código hace hoy (commit
`1716441`).

## Para qué y para quién

Pasarle la app al profe de armónica para que la use en su computadora:
Windows, usuario básico (usa ChatGPT, no una terminal). Tiene que poder
instalarla con doble clic, abrirla desde un ícono, configurar el micrófono
sin ayuda y no perder nunca lo que guarda cuando llegue una versión nueva.

Éxito = en un usuario de Windows recién creado, sin Python ni nada
instalado, se baja el `.exe` de Drive, se instala, se abre, se elige el
micrófono, se mide el ruido, se toca en En vivo y la aguja se mueve; se
guarda una frase, se cierra la app, se instala una versión nueva encima y
la frase sigue ahí.

## Qué queda afuera

Firma de código (SmartScreen va a avisar; la guía lo explica), actualización
automática, Mac, el coach para el profe, un botón para ChatGPT y un capítulo
"Usarla para enseñar".

## Cómo queda instalado

Instalación por usuario, sin pedir administrador:

```
%LOCALAPPDATA%\Programs\Armonica\          el programa (lo pisa cada versión)
    python\        Python 3.14.6 embebido de python.org + Lib\site-packages
    app\           el código (armonica\, config.py, VERSION, lanzador.pyw)
    ffmpeg\        ffmpeg.exe (build LGPL de BtbN)
    licencias\     las licencias de todo lo que va adentro
    Guia de Armonica.pdf
    Armonica.ico
```

Paquetes en `site-packages`, con versiones fijas (las del `.venv` de hoy):
numpy 2.5.3, sounddevice 0.5.6 (trae PortAudio), rich 15.0.0, pillow 12.3.0,
pillow-heif 1.7.0 (ver "Riesgos"), pypdf 6.19.0.

Accesos directos: escritorio y menú Inicio ("Armónica" y "Guía de
Armónica"), con el ícono. El acceso directo ejecuta
`python\pythonw.exe app\lanzador.pyw`.

Los datos del profe van a `Documentos\Armonica\`, la carpeta Documentos
REAL del usuario aunque esté redirigida a OneDrive (se pide a Windows con
`SHGetKnownFolderPath(FOLDERID_Documents)`, no se arma con `%USERPROFILE%`):

```
Documentos\Armonica\
    frases\        sus frases (hoy frases/)
    sesiones\      sus sesiones grabadas (hoy sesiones/)
    canciones\     una carpeta por canción (CARPETA_CANCIONES)
    apuntes\       los apuntes de clase (CARPETA_CLASES)
    material\      lo interno de la app: _canciones.json, _plan.json, _cache\
    ajustes.json   micrófono, umbral, armónica/posición/escala, primera vez
    registro.txt   lo que la app escribe en la consola, para diagnosticar
```

El instalador de una versión nueva y el desinstalador no tocan esta
carpeta. Los ejemplos que elige Bruno (frases, una canción) se copian
ahí al instalar solo si no existen.

Hoy todas esas rutas son relativas a la carpeta desde donde se arranca la
app, así que no hace falta cambiar los módulos: el lanzador se para en
`Documentos\Armonica\` y define `CARPETA_CANCIONES` y `CARPETA_CLASES` como
variables de entorno antes de importar la app. `.env` no hay: el profe no
usa el coach.

## El lanzador

`lanzador.pyw` en la raíz del repo, de tres líneas; la lógica va en
`armonica/lanzador.py`, con tests.

1. Encuentra la carpeta de datos (o `ARMONICA_DATOS` si está definida: la
   usan la prueba de humo y los tests), la crea con sus subcarpetas si
   falta, y se para ahí.
2. Manda `stdout` y `stderr` a `registro.txt` (con `pythonw` no hay
   consola). Al arrancar, si el registro pasa de 1 MB, se queda con los
   últimos 200 KB.
3. Antepone `ffmpeg\` al `PATH` del proceso (la app busca ffmpeg en el PATH).
4. **Una sola instancia:** recorre los puertos 8000 a 8010 preguntando
   `GET /api/hola`; si alguno contesta que es esta app, abre el navegador
   ahí y termina.
5. Si no hay ninguna, levanta el servidor en el primer puerto libre de esa
   lista y abre el navegador.

Para que "libre" sea cierto hay que corregir algo de hoy: en Windows,
`HTTPServer` usa `SO_REUSEADDR` y una segunda instancia se queda con el
mismo puerto sin error. El servidor pasa a enlazar en exclusiva
(`allow_reuse_address = False`), así un puerto ocupado falla y se prueba el
siguiente. `main.py --web` gana lo mismo: si el 8000 está ocupado, lo dice
claro en vez de compartirlo en silencio.

El lanzador llama a `servidor.arrancar(..., empaquetada=True)` directo, sin
pasar por `main.py`. Con `empaquetada`, `/api/inicio` lo informa y la
pantalla usa los textos para el profe (ver abajo).

## Cambios en la app

Todos sirven también a Bruno salvo los que dependen de `empaquetada`.

**`armonica/ajustes.py` y `ajustes.json`.** Lo que hoy se elige en Ajustes
se pierde al cerrar. Pasa a guardarse en `ajustes.json` (en la carpeta desde
donde se arranca; en el repo, gitignored):

- el micrófono POR NOMBRE, no por número (los números cambian al enchufar
  otro dispositivo). Al arrancar se busca ese nombre con la misma regla de
  `/api/dispositivos` (el primero con ese nombre); si no está, se usa el de
  Windows y Ajustes lo avisa: "El micrófono que elegiste no está conectado;
  uso el de Windows."
- el umbral de volumen;
- armónica, posición y escala;
- si ya se pasó por los primeros pasos.

Orden de precedencia: lo que se escribe explícitamente en la línea de
comandos (Armonica.bat de Bruno) le gana a `ajustes.json`, que le gana a
`config.py` (la "fábrica"). Los valores se aplican sobre los atributos de
`config` al arrancar, así los módulos que leen `config.UMBRAL_VOLUMEN_RMS`
siguen igual.

**Medir el ruido, en Ajustes.** Un botón que pide silencio, escucha 3 s con
el mismo micrófono que está usando la app y guarda el umbral con la regla
de `--calibrar` (máx(0,003; pico × 3)). Muestra el resultado en palabras.
Los avisos que hoy dicen "corré `python main.py --calibrar`" pasan a decir
"Medí el ruido en Ajustes", para todos.

**Primeros pasos.** Si `ajustes.json` no dice que ya se hicieron, al abrir
aparece un cartel con cuatro pasos en orden:

1. Elegir el micrófono.
2. Sacar las "Mejoras de audio" de Windows (cancelan ruido y se comen la
   armónica), con un botón que abre `ms-settings:sound` y qué tocar ahí.
3. Medir el ruido.
4. Ir a En vivo y tocar una nota. Si la barra no se mueve, un botón a
   `ms-settings:privacy-microphone` ("Permitir que las aplicaciones de
   escritorio accedan al micrófono").

"Listo" lo marca hecho; Ajustes tiene "Ver los primeros pasos" para volver.
Las páginas de configuración de Windows las abre el servidor
(`os.startfile`), no el navegador, que preguntaría antes de abrir un
`ms-settings:`. Solo esas dos direcciones: lista cerrada.

**Sin jerga de programador.** Con `empaquetada`, ningún texto en pantalla
nombra `.env`, `CARPETA_CLASES`, `material/`, `pip install`, `winget`,
la terminal ni rutas crudas. Donde hoy se muestra una carpeta va un botón
"Abrir la carpeta" (frases, sesiones, canciones, apuntes; lista cerrada,
el servidor la abre con `os.startfile`). La sección del coach no se
muestra. El mensaje de la cámara de Ajustes (anécdota de la máquina de
Bruno) se reescribe en general. Los textos a cambiar están al final, en
"Textos con jerga hoy".

**Cerrar la app.** Un botón "Cerrar la app" en Ajustes (`POST /api/apagar`):
el servidor responde, suelta el micrófono y termina. La página queda con
"La app está cerrada. Para volver a abrirla, el ícono Armónica del
escritorio." Hoy la única forma de cerrarla es la ventana negra.

**El micrófono se apaga solo.** Hoy queda prendido mientras viva el
proceso. Con `pythonw` el profe cierra la pestaña y el proceso sigue: el
micrófono quedaría tomado (y Windows muestra el ícono de micrófono en uso).
El servidor cuenta las páginas conectadas a `/api/vivo`; si no hay ninguna
por un minuto, apaga el micrófono, y lo prende de nuevo cuando una se
conecta. Si estaba grabando, la grabación se corta como si se hubiera
apretado Parar y queda como sesión pendiente (la pantalla ya recupera las
pendientes al abrir). El plan verifica ese camino en el código.

**ffmpeg sin ventana.** `audio.py` llama a ffmpeg sin
`CREATE_NO_WINDOW`; desde `pythonw` cada conversión abriría una consola
negra un instante. Se agrega la bandera en Windows.

**Versión.** Un archivo `VERSION` en la raíz (primera: `0.1.0`), visible en
Ajustes y en el nombre del instalador.

## La guía

`armonica/web/guia.html`, con un botón "Guía" en la barra que la abre en
otra pestaña, y la misma página pasada a PDF con Edge sin ventana
(`msedge --headless --print-to-pdf`) al armar el instalador.

Capítulos: instalar (con la captura del aviso de SmartScreen: "Más
información" → "Ejecutar de todas formas"), los primeros pasos, En vivo,
Frases, Canciones (exportar desde Band-in-a-Box paso a paso, armado a
partir de las FOTOS de Bruno de los menús, sin inventar nombres de menú),
Apuntes, Teoría, Historial, si algo no anda (la barra no se mueve, no
suena, `registro.txt` para mandarle a Bruno), y versión nueva (instalar
encima; los datos no se tocan).

Capturas de la app con datos neutros (el repo es público), sacadas una vez
y guardadas en el repo; si la pantalla cambia mucho, se vuelven a sacar.

## El armado

`herramientas\empaquetar.ps1`, que corre Bruno en su máquina:

1. Toma el código con `git archive HEAD` a una carpeta temporal. Nunca el
   working tree: ahí están el `config.py` con sus valores locales y el
   `.env` con la clave del coach. Si hay cambios sin commitear en archivos
   que van al paquete, avisa que no van a entrar y sigue.
2. Corre los tests en esa copia, con el Python del `.venv` (misma versión
   que el embebido). Al no haber `.env` ni `material\`, los tests corren
   aislados de la máquina de Bruno. Si fallan, para.
3. Descarga a `empaquetado\_descargas\` (gitignored) lo que falte, con
   versiones y SHA-256 fijos escritos en el script: el Python embebido,
   las ruedas de los paquetes (`pip download` con `--require-hashes`) y el
   ffmpeg LGPL de un tag fechado de BtbN. Si un hash no coincide, para.
4. Arma el programa en una carpeta de preparación: Python embebido con su
   `python314._pth` apuntando a `Lib\site-packages` y a `..\app`, las
   ruedas instaladas con `pip install --target`, el código, ffmpeg, las
   licencias.
5. Prueba de humo: arranca ese programa con `ARMONICA_DATOS` en una carpeta
   temporal, espera `GET /api/hola`, pide `/api/inicio` y `/api/canciones`,
   y lo cierra con el botón de cerrar (`POST /api/apagar`).
6. Genera el PDF de la guía con Edge.
7. Compila `empaquetado\armonica.iss` con Inno Setup (`ISCC.exe`; el script
   avisa si no está y cómo instalarlo) a
   `dist\Armonica-<VERSION>-instalador.exe` (gitignored).

Inno Setup: `PrivilegesRequired=lowest`, carpeta
`{localappdata}\Programs\Armonica`, accesos directos, desinstalador que no
toca `Documentos\Armonica`, `CloseApplications` para cerrar la app si está
abierta al instalar encima, y los ejemplos con `onlyifdoesntexist`.

## Licencias

`licencias\` lleva el texto de cada cosa que va adentro: la app (MIT), el
Python embebido (PSF), numpy, sounddevice y PortAudio, rich, Pillow,
pillow-heif y las bibliotecas que trae, pypdf, y ffmpeg (LGPL, con dónde
bajar el código fuente del build usado).

## Probarlo

En un segundo usuario de Windows que crea Bruno (Windows Home no tiene
Sandbox), sin Python ni ffmpeg:

- bajar el `.exe` desde Drive y sacar la captura de SmartScreen;
- instalar sin permisos de administrador;
- abrir desde el escritorio: se abre el navegador y no aparece ninguna
  ventana negra;
- hacer los primeros pasos; tocar en En vivo y que la aguja se mueva;
- grabar una sesión, guardar una frase, abrir una canción de ejemplo y
  reproducir su base, importar un audio (usa ffmpeg);
- abrir dos veces el ícono: una sola app, la segunda vez solo abre el
  navegador;
- cerrar la pestaña y ver que el ícono de micrófono en uso de Windows se
  apaga al minuto; "Cerrar la app" y ver que el proceso termina;
- instalar una versión nueva encima: la frase y los ajustes siguen;
- desinstalar: `Documentos\Armonica` sigue.

## Lo que tiene que aportar Bruno

- Las fotos de los menús de Band-in-a-Box para el capítulo de Canciones.
- Los ejemplos en `empaquetado\ejemplos\` (frases, una canción con su base
  y su audio) que se pueden dar al profe.
- El segundo usuario de Windows para la prueba.
- Inno Setup instalado (`winget install JRSoftware.InnoSetup`).

## Orden de trabajo

Tres etapas, cada una con su plan, en este orden:

1. **La app y el lanzador.** Todo lo de "Cambios en la app" más
   `armonica/lanzador.py` y `lanzador.pyw`. Se prueba con el `.venv`
   (`pythonw lanzador.pyw` con `ARMONICA_DATOS` en una carpeta de prueba)
   y le sirve a Bruno aunque no haya instalador.
2. **El armado.** `empaquetar.ps1`, `armonica.iss`, licencias, prueba de
   humo, y la primera prueba en el segundo usuario de Windows.
3. **La guía.** Necesita las fotos de Band-in-a-Box y las capturas; el PDF
   entra al armado cuando está.

## Riesgos y preguntas abiertas

- **pillow-heif y su licencia.** Las ruedas de pillow-heif pueden traer el
  codificador x265 (GPL). El armado lo verifica; si lo trae, se usa
  `pi-heif`, que solo lee (lo único que la app necesita) y pesa menos. El
  cambio en `imagenes.py` es un import con alternativa.
- **Antivirus.** Un `pythonw.exe` sin firmar en `AppData` puede llamar la
  atención de Defender. Si pasa en la prueba, se documenta en la guía.
- **Capturas que envejecen.** Las de la guía son fotos fijas; cada versión
  con cambios de pantalla grandes las vuelve a sacar.
- **Tamaño.** ffmpeg estático pesa unos 80 MB y es el grueso del
  instalador. Se acepta: importar audios de WhatsApp y medir el compás 1
  lo necesitan.

## Textos con jerga hoy

Relevados el 2026-10-02 sobre `1716441`; el plan los ubica de nuevo antes
de cambiarlos.

En `armonica/web/index.html`: el aviso de Frases que dice "siempre que
tengas ffmpeg instalado"; en Ajustes, el origen de los apuntes (`material/`,
`CARPETA_CLASES`, `.env`), el estado del coach (`.env`, `.env.ejemplo`,
"reiniciando la app") y la anécdota de la cámara junto al micrófono; en
Canciones, `material/canciones/`, `CARPETA_CANCIONES` y `.env`.

En `armonica/web/app.js`: "corré `python main.py --calibrar`"; "Guardado en
sesiones/" con rutas crudas; los avisos de apuntes vacíos y de canciones
vacías con carpetas y `.env`; el aviso de HEIC con "bibliotecas que no
vienen con Python" y el `pip install`; el origen de los apuntes; el nombre
crudo del modelo del coach.

Mensajes del servidor que llegan a la pantalla: los motivos del coach
(`coach.py`: `.env`, `LLM_CLAVE`, `pip install anthropic`, `ollama
serve`/`pull`); `transcripcion.py` (`python main.py --calibrar`,
`python main.py --wav ... --que-tono`); `audio.py` (winget, "la terminal");
`clases.py` (`pip install pypdf`); `imagenes.py` (`pip install
pillow-heif`); y el texto crudo de la excepción cuando falla el micrófono
(`servidor.py`), que pasa a una frase en castellano con el detalle en
`registro.txt`.
