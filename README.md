# Armónica → Tablatura

Escucha tu armónica por el micrófono, la transcribe a tablatura y mide lo que
no se puede medir de oído: la afinación de los bends y el tiempo.

Está hecha para armónica diatónica de 10 agujeros, afinación Richter, y para
las armónicas en Do, Sol, Re y La. Agregar otra tonalidad es una línea.

---

## Empezar

Una sola vez:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Antes de la primera sesión, medí el ruido de tu habitación. Es la calibración
más importante de todas y toma tres segundos:

```powershell
python main.py --calibrar
```

Te dice qué número poner en `UMBRAL_VOLUMEN_RMS` dentro de `config.py`.
Sin eso, la app puede no detectar nada (si el umbral está muy alto) o detectar
tu respiración (si está muy bajo).

Y después, la interfaz web:

```powershell
python main.py --web --posicion 12 --escala blues_mayor
```

Se abre el navegador con el medidor de afinación grande, el diagrama de la
armónica y el histórico de tus sesiones. El servidor corre en tu propia
máquina: no hay nada en internet.

O en la terminal, si preferís:

```powershell
python main.py
```

Sin argumentos arranca un menú que te pregunta lo que hace falta. Todo tiene
valor por defecto, así que después de la primera vez son cuatro Enter.

> **Nota sobre PowerShell.** Windows PowerShell 5.1 no soporta `&&` para
> encadenar comandos: da un error de sintaxis que parece un problema del
> proyecto y no lo es. Usá `;` en su lugar.

---

## Los modos

| Qué querés | Comando |
|---|---|
| Abrir la interfaz web | `python main.py --web --posicion 12 --escala blues_mayor` |
| Tocar y ver la pantalla en vivo | `python main.py --vivo --posicion 12 --escala blues_mayor` |
| Practicar la afinación de un bend | `python main.py --afinador --bend "-3''"` |
| Consultar una escala sin tocar | `python main.py --teoria --posicion 12 --escala blues_mayor` |
| Ver un acorde y sus notas guía | `python main.py --acorde F7` |
| Transcribir una grabación | `python main.py --wav grabacion.wav --posicion 12 --escala blues_mayor --detalle` |
| Guardar una frase de referencia | `python main.py --grabar-frase "lick de 3a" --posicion 3` (o la solapa **Frases** de la web) |
| Importar una frase de un audio | `python main.py --grabar-frase "lick de Lean" --wav lean_01.wav --posicion 3` |
| Practicar contra esa frase | `python main.py --practicar "lick de 3a"` (o la solapa **Frases** de la web) |
| Practicar con un audio ya grabado | `python main.py --practicar "lick de 3a" --wav mi_intento.wav` |
| Saber con qué armónica se grabó algo | `python main.py --wav ajeno.wav --que-tono` |
| Medir el ruido de fondo | `python main.py --calibrar` |

Y para analizar el ritmo, agregale a cualquier modo el BPM de tu base:

```powershell
python main.py --wav grabacion.wav --bpm 65 --subdivision 3 --detalle
```

La `--subdivision` dice contra qué figura medir: `1` negras, `2` corcheas
rectas, `3` tresillos. Si tu base es de estilo `sw8` (corcheas con swing), va
`3`. Si medís corcheas con swing contra corcheas rectas, la mitad de tus notas
aparecen con medio pulso de desvío y el reporte no sirve.

---

## Grabar bien

Tres cosas, en orden de importancia.

**Auriculares, siempre.** Si la base entra por el micrófono, el detector de
tono no tiene nada que hacer: es monofónico y con bajo, batería y piano
sonando devuelve basura. La app tiene una medida para eso:

```powershell
python main.py --wav grabacion.wav --monofonia
```

**Formato WAV.** La app no lee m4a ni mp3. En Windows 11, la Grabadora de
sonido tiene la opción de formato en su configuración.

**Nivel de entrada.** Si el pico queda muy bajo, la app lo normaliza sola,
pero más señal es siempre menos ruido. Y dejá dos segundos de silencio al
principio: sirven de referencia.

---

## Qué mide, y qué tan en serio tomarlo

Este es el punto más importante del proyecto. La app se calla cuando no sabe,
en vez de inventar números. Tres controles la mantienen honesta:

**La afinación** es la medida más confiable. El detector tiene menos de
2 cents de error propio, y un semitono son 100. Antes de juzgar tus bends,
calcula cómo está afinada TU armónica usando solo las notas naturales (las que
da la lengüeta y no dependen de vos) y mide todo contra eso. La tuya está a
La = 444 Hz, que es lo que entrega Hohner, y no es culpa tuya.

**El ritmo** solo se reporta si la grilla explica lo tocado mejor que el azar.
Si tus notas caen tan repartidas como si fueran al azar respecto del pulso, la
app lo dice y no diagnostica. Pasó con las grabaciones del estudio de Carlos
del Junco: son un solo con fraseo expresivo, las notas no caen sobre la grilla
ni tienen por qué, y reportar "dispersión 77 ms" habría sido un número con
cara de diagnóstico.

Para medir ritmo de verdad hace falta material **métrico**: una escala en
negras o corcheas parejas sobre la base, no un solo.

**La transcripción** avisa cuando el audio es polifónico, con `--monofonia`.
Y cuando importás una frase desde un `.wav`, ese control se corre solo y la
importación se rechaza: una frase de referencia mal transcrita queda guardada
para siempre y arruina todas las prácticas que vengan después.

Lo que ese control **no** puede hacer es decirte de qué armónica es una
grabación. Suena a que debería: no puede. Una armónica en Do, con bends,
alcanza casi todas las notas del registro medio, así que una frase tocada en
La leída como si fuera en Do cae entera dentro de lo posible —la tablatura
sale distinta, pero no hay ninguna nota imposible que lo delate. Para eso está
`--que-tono`, que compara las cuatro armónicas entre sí en vez de mirar una
sola. Hay un test que documenta ese límite a propósito.

---

## Los archivos que deja

Cada sesión guarda cuatro archivos en `sesiones/`, con fecha y hora:

- `_tab.txt` — la tablatura, para leer o llevar a la clase
- `_resumen.txt` — las estadísticas y qué atacar primero
- `_eventos.json` — cada nota con todos sus datos, para comparar sesiones
- `_audio.wav` — el audio crudo

El JSON guarda además **con qué parámetros se analizó**. Sin eso, comparar dos
sesiones podría ser comparar dos reglas distintas sin darte cuenta. Y el audio
te deja volver a analizar la misma sesión con otros umbrales, sin tocar de
nuevo.

Las frases de referencia van a `frases/`. Ninguna de esas dos carpetas se
sube a git.

---

## Ajustar el comportamiento

Todo lo ajustable está en `config.py`, con un comentario que dice qué es, en
qué unidad, y qué pasa si lo subís o lo bajás. Nunca hace falta tocar el
código.

Los que más se usan:

| Parámetro | Para qué |
|---|---|
| `UMBRAL_VOLUMEN_RMS` | Qué tan fuerte hay que tocar para que cuente. **Calibralo con `--calibrar`.** |
| `DURACION_MINIMA_SEG` | Descarta notas más cortas que esto. Subilo si aparecen notas fantasma. |
| `VENTANAS_SILENCIO_TOLERADAS` | Subilo si una nota tuya aparece partida en dos. |
| `NOTACION` | `"flechas"` (↑4 ↓4') o `"guion"` (4 -4'). |
| `TOLERANCIA_RITMO_MS` | Qué desvío del pulso todavía cuenta como a tiempo. |
| `SUBDIVISION_RITMO` | Contra qué figura medir el pulso por defecto. |

---

## Cómo está armado

Un módulo por responsabilidad. Los primeros siete son Python puro, sin audio
ni pantalla: son los que se podrían portar a otro lenguaje si algún día hay
una versión web o de teléfono.

| Módulo | Qué hace |
|---|---|
| `tablas.py` | **Solo datos.** Afinación Richter, bends, escalas, acordes, posiciones. No importa nada. |
| `notas.py` | Frecuencia ↔ MIDI ↔ nombre de nota, y cents. |
| `mapeo.py` | De una frecuencia al agujero de la armónica. |
| `posiciones.py` | Tonalidad por posición, pertenencia a escalas. Lee las tablas escritas a mano. |
| `teoria.py` | Lo mismo, pero **calculado**. Cubre las 12 posiciones, acordes y arpegios. |
| `tonalidad.py` | Deduce qué armónica y en qué tono se grabó algo. |
| `transcripcion.py` | La cadena de un `.wav` a notas, y si ese audio sirve. |
| `ritmo.py` | Desvío respecto del pulso, y si la medición es confiable. |
| `tono.py` | El detector YIN, escrito a mano en numpy. |
| `audio.py` | Leer y escribir `.wav`, ventanas, volumen. |
| `microfono.py` | La captura en vivo. |
| `segmentacion.py` | De ventanas sueltas a notas tocadas. |
| `frases.py` | Frases de referencia y comparación. |
| `afinador.py` | La práctica de un bend, con estadísticas. |
| `resumen.py` | Las estadísticas de una sesión. Cuenta, no opina. |
| `prioridades.py` | Qué atacar primero. Opina, pero solo con datos confiables. |
| `exportacion.py` | Los archivos de sesión. |
| `pantalla.py` | El dibujo con `rich`, para la terminal. |
| `servidor.py` | La interfaz web. Solo biblioteca estándar. |
| `menu.py` | El menú interactivo. |

### Dos ideas que se repiten en todo el proyecto

**Dos fuentes que se validan entre sí.** Las escalas están escritas a mano en
`tablas.py` y también calculadas en `teoria.py`. Un test las concilia. Cuando
se escribieron las tablas, ese test encontró tres erratas reales. Lo mismo
pasa entre los compases de cambio de acorde de `ritmo.py` y los que deduce
`teoria.py`.

**La mediana en vez del promedio.** Aparece en la frecuencia de cada nota, en
la estimación del pulso, en la afinación de la armónica y en el ajuste de
velocidad al comparar frases. Un solo valor disparatado arruina un promedio y
la mediana ni se entera.

---

## La interfaz web

```powershell
python main.py --web --posicion 12 --escala blues_mayor
```

Tres solapas. **En vivo** tiene el medidor de afinación con una aguja que se
mueve suave (en la terminal parpadea quince veces por segundo y no se puede
leer mientras soplás), el diagrama de la armónica con la escala en verde, y la
tablatura que vas tocando. **Frases** es el modo "repetí esta frase": grabás
una frase de referencia con un nombre —o importás un `.wav`, tuyo o de
Leandro—, y después le das Practicar y te dice nota por nota qué erraste,
cuánto te desviaste del tiempo y cómo salió cada bend. El intento también
puede ser un archivo, si ya lo grabaste con la grabadora de Windows. **Historial** grafica cómo viene cada bend sesión por sesión, leyendo
los JSON que ya se guardaban.

Los tres modos escuchan exactamente igual: lo único que cambia es qué hace el
servidor cuando terminás. Y los botones se dibujan a partir del estado que
manda Python, no de lo que hizo el último clic, así dos pestañas abiertas
nunca muestran cosas distintas.

No agrega ninguna dependencia. Usa `http.server` de la biblioteca estándar, y
para mandar el estado en vivo usa *server-sent events*: una respuesta HTTP
común que nunca se cierra, por la que el servidor va escribiendo líneas. Es
más simple que un WebSocket y alcanza, porque los datos van en una sola
dirección.

Python sigue haciendo todo el trabajo: el navegador solo dibuja.

---

## Los tests

```powershell
python -m pytest -q
```

Son 589 y no necesitan micrófono: el audio se genera, y la captura en vivo se
prueba inyectando datos en la cola interna, que es exactamente lo que hace la
placa de sonido.

Varios de ellos existen porque encontraron un error de verdad, y el comentario
lo cuenta. Vale la pena leerlos: son la documentación de por qué el código es
como es.

Para generar los audios de prueba:

```powershell
python -m herramientas.generar_wav
```

---

## Lo que no hace

- **Overblows.** El `↓3'''` sí está; los overblows (`↑6°`, `↑4°`) no. Se
  agregan con una tabla nueva en `tablas.py`.
- **Transcribir temas con banda.** Probado y documentado en
  `herramientas/prueba_demucs.py`: separar las pistas no alcanza, porque la
  armónica queda mezclada con la guitarra y el piano. Haría falta detección de
  tono polifónica, que es otro proyecto.
- **Ritmo escrito en la tablatura.** La tab dice qué agujero, no si es negra o
  corchea. Por eso las frases de referencia son grabaciones y no texto.
- **Correr en el teléfono.** La interfaz web corre en tu computadora y el
  micrófono lo captura Python. Para una versión de teléfono habría que
  portar los módulos puros a JavaScript y reescribir YIN con Web Audio.
  Están escritos para eso, pero es otro proyecto.
