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

**Lo primero de todo: elegí el micrófono, y elegilo EXPLÍCITAMENTE.** Abrí
la app y andá a la solapa **Ajustes**. No dejes puesto "el predeterminado de
Windows": medido en esta máquina, con esa opción el micrófono se agota y se
reabre cada pocos segundos, mientras que eligiendo el mismo aparato por su
nombre anda de corrido. Windows tiene siempre media docena de entradas y
la predeterminada rara vez es la que usás: en la máquina donde se escribió
esto era el micrófono de la cámara web, a un metro de la cara. Con el
equivocado, la app "no anda" y en realidad está escuchando otra cosa. La barra
de nivel te lo dice en dos segundos.

Después, medí el ruido de tu habitación. Es la calibración
más importante de todas y toma tres segundos:

```powershell
python main.py --calibrar
```

Te dice qué número poner en `UMBRAL_VOLUMEN_RMS` dentro de `config.py`.
Sin eso, la app puede no detectar nada (si el umbral está muy alto) o detectar
tu respiración (si está muy bajo).

Y después, la interfaz web. La forma corta es **doble clic en `Armonica.bat`**,
o en el acceso directo del escritorio, que se crea con un comando y lleva el
icono de la armónica:

```powershell
powershell -ExecutionPolicy Bypass -File herramientas\acceso_directo.ps1
```

Cualquiera de los dos abre el navegador solo.
La ventana negra que queda atrás ES el servidor, así que minimizala en vez de
cerrarla. Para cambiar la armónica, la posición o la escala de arranque, editá
la línea `set OPCIONES` que está adentro del `.bat`.

Lo mismo desde la terminal:

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
| Abrir la interfaz web | doble clic en `Armonica.bat`, o `python main.py --web --posicion 12 --escala blues_mayor` |
| Tocar y ver la pantalla en vivo | `python main.py --vivo --posicion 12 --escala blues_mayor` |
| Practicar la afinación de un bend | `python main.py --afinador --bend "-3''"` |
| Consultar una escala sin tocar | `python main.py --teoria --posicion 12 --escala blues_mayor` |
| Ver un acorde y sus notas guía | `python main.py --acorde F7` |
| Transcribir una grabación | `python main.py --wav grabacion.wav --posicion 12 --escala blues_mayor --detalle` |
| Guardar una frase de referencia | `python main.py --grabar-frase "lick de 3a" --posicion 3` (o la solapa **Frases** de la web) |
| Ver dónde hay armónica en una clase | `python main.py --wav clase.ogg --tramos` |
| Importar una frase de un audio | `python main.py --grabar-frase "lick del profe" --wav lean_01.ogg --tonalidad A` |
| Importar solo un tramo de esa clase | `python main.py --grabar-frase "lick del profe" --wav clase.ogg --desde 15.9 --hasta 26.6` |
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

**Formato WAV.** La app lee `.wav` de 16 bits. En Windows 11, la Grabadora de
sonido tiene la opción de formato en su configuración.

Los audios que te mandan por WhatsApp o desde un iPhone vienen en otro formato
(`.opus`, `.m4a`) y hay que convertirlos. La app lo hace sola si tenés
**ffmpeg** instalado, que se instala una sola vez:

```powershell
winget install ffmpeg
```

Después cerrá y abrí la terminal. Sin ffmpeg no pasa nada malo: la app te dice
que falta y te da ese comando.

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
sale distinta, pero no hay ninguna nota imposible que lo delate. Por eso al
importar **le decís vos con qué armónica se grabó**, que es un dato que tenés
y la app no. Si dudás, `--que-tono` compara las cuatro entre sí.

Y hay algo menos intuitivo, que está medido en
`tests/test_transcripcion.py`: **el control de monofonía no es lo primero que
se rompe cuando hay una base atrás.** Con la base al 20% del volumen de la
armónica, el puntaje da 0.83 y pasa cómodo; pero de cinco notas tocadas se
reconocen tres, y las otras dos se pierden sin que nadie avise. Cuando el
control sí rechaza, ya no quedaba ninguna nota que rescatar.

O sea: el rango peligroso no es el que la app rechaza, es el que **acepta**
con una base bajita. Por eso la recomendación es grabar la armónica sola, y no
"que se escuche fuerte".

---

## Los audios de tu profesor no son frases: son clases

Es la diferencia que más cuesta ver. Un audio que te manda el profesor por
WhatsApp casi nunca es una frase suelta: habla, toca, vuelve a hablar. Medido
sobre dos audios reales, la armónica ocupa el 64% y el 41% del archivo,
repartida en 8 y en 10 tramos.

Si importás la clase entera como frase de referencia, te queda una referencia
de setenta segundos con silencios de ocho segundos adentro, y nunca vas a
poder acertarle: esos silencios eran el profesor explicando.

Por eso la app primero busca **dónde** hay armónica:

```powershell
python main.py --wav clase.ogg --tramos
```

```
  8 tramos con armonica, 49 s de 76 (64% del audio).

   1. 0:04.3 a 0:12.5  (8.1 s, 19 notas)  ↓3''' ↑8 ↓5 ↓5 ↓5 ↑6 ↓6' ...
   2. 0:15.9 a 0:26.6  (10.7 s, 23 notas)  ↓6' ↑6 ↑6 ↑6 ↓4 ↓4 ↑4 ...
```

y después guardás el que quieras:

```powershell
python main.py --grabar-frase "lick del profe" --wav clase.ogg --desde 15.9 --hasta 26.6
```

En la web es lo mismo con un botón: subís el audio, te muestra los tramos con
su tablatura, y elegís cuál guardar. Si el audio tiene un solo tramo, no
pregunta nada y lo guarda.

Antes de elegir, **podés escuchar cada tramo**: cada fila tiene un botón de
reproducir y pausar, y una línea abajo que se llena mientras suena y se
arrastra para moverte dentro del tramo. Se reproduce desde el archivo que
elegiste, en el navegador, sin pasar por el servidor.

**El recorte se hace sobre el audio, no sobre la lista de notas.** Es más
trabajo y vale la pena: así todo lo que se mide después —la monofonía, la
cobertura, los tiempos— habla del pedazo que vas a guardar y no del archivo
entero. En el audio real, recortar subió la monofonía de 0.76 a 0.80 y la
detección de 0.38 a 0.56. Una clase con la base sonando entre frase y frase
puede no pasar el control aunque el tramo elegido esté limpio.

Como el análisis avanza en ventanas de tamaño fijo desde el comienzo del
archivo, recortar corre esa grilla y puede cambiar una nota o dos de veinte.
Ninguna de las dos lecturas es la equivocada, pero mostrarte una y guardar la
otra sí sería un error: por eso la lista de tramos ya viene calculada con el
mismo recorte que se va a usar al guardar.

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
| `FACTOR_CORRECCION_OCTAVA` | Corrige las notas que salen una o dos octavas más agudas. |
| `VENTANAS_PARA_CONFIRMAR` | Cuántas ventanas seguidas hacen falta para cambiar el cartel grande. |
| `SEGUNDOS_EN_PANTALLA` | Cuánto de lo tocado se recuerda mientras NO estás grabando. |
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
| `frases.py` | Frases de referencia, comparación, y los tramos de una grabación. |
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

Cinco solapas. **En vivo** tiene el medidor de afinación con una aguja que se
mueve suave (en la terminal parpadea quince veces por segundo y no se puede
leer mientras soplás), el diagrama de la armónica con la escala en verde, y la
tablatura que vas tocando. **Frases** es el modo "repetí esta frase": grabás
una frase de referencia con un nombre —o importás un `.wav`, tuyo o del
profe—, y después le das Practicar. Al terminar te da una **devolución**:
tres números (notas acertadas, afinación de los bends, notas a tiempo) y dos
o tres consejos en orden de importancia, del tipo "el ↓3'' te queda 36 cents
alto: el bend se queda corto". Con el mismo criterio de toda la app: si
coincidieron menos de tres notas, dice eso y no opina de ritmo ni de
afinación. Abajo podés escuchar la referencia y tu intento uno debajo del
otro, que es la única forma de OÍR la diferencia de ritmo que los números
describen, y después viene el detalle nota por nota. El intento también
puede ser un archivo, si ya lo grabaste con la grabadora de Windows. **Historial** grafica cómo viene cada bend sesión por sesión, leyendo
los JSON que ya se guardaban. **Teoría** es lo que `teoria.py` sabía y solo
se veía en la terminal: elegís armónica, posición y escala (las doce
posiciones, no solo las seis con tabla) y te muestra la escala marcada en la
armónica con la tónica en un aro, la corrida de dos octavas, el blues de
doce compases con las notas guía de cada acorde y por dónde agarrarlas, qué
notas naturales evitar sobre cada acorde y por qué, y en qué posición
conviene esa escala. **Cada bloque dice de dónde sale el dato**: del
cálculo, de la tabla escrita a mano (y si las dos coinciden, que es la
conciliación de los tests mostrada en pantalla), o de una clase, de la que
solo se cita la fecha. Los selectores de Teoría no cambian lo que la app
tiene puesto: podés estudiar la 3ª sin dejar de tocar en 12ª. Y **Ajustes**
tiene el micrófono y la configuración: la armónica que tenés en la mano, la
posición y la escala de referencia se cambian ahí, sin reiniciar nada.

### El coach (opcional)

Un modelo de lenguaje que **explica lo que la app midió**. Recibe los
números ya calculados —los tres de la devolución, los consejos, la nota por
nota; o lo que está en pantalla en Teoría— y los cuenta como lo haría un
profe que te escuchó una vez. Nunca mide nada, nunca inventa un número, y si
algo no está medido lo dice. Aparece como un botón al pie de la devolución de
una práctica y como una pregunta libre al pie de Teoría.

Es opcional y está apagado por defecto. Se activa copiando `.env.ejemplo`
a `.env` (git lo ignora: la clave es tuya) y eligiendo ahí uno de tres
proveedores:

| Proveedor | Qué pide | Qué cuesta |
|---|---|---|
| **Claude** (por defecto) | una clave de console.anthropic.com y `pip install anthropic` | centavos por devolución |
| **Ollama** (modelo local) | instalar [Ollama](https://ollama.com) y bajar un modelo: `ollama pull qwen2.5:7b` | nada, ni internet |
| **ChatGPT** | una clave de OpenAI | según su tarifa |

Con Ollama, una placa de video de 8 GB contesta en segundos; sin placa, en
minutos. `LLM_MODELO` cambia el modelo de cualquiera de los tres y
`LLM_URL` la dirección (sirve para LM Studio o cualquier servidor compatible
con la API de OpenAI). El audio nunca sale de tu máquina con ninguno: al
coach le llegan números y texto. Los tres se hablan desde `armonica/coach.py`
y nada más sabe cuál está puesto; agregar un cuarto es agregar una función.
Los tests nunca tocan la red: la llamada se reemplaza por una falsa.

**El micrófono queda encendido todo el tiempo.** Abrís la app y podés tocar y
ver lo que sale sin apretar nada: el medidor, el diagrama y la tablatura
funcionan siempre. Grabar es una decisión aparte, con un solo botón que dice
*Grabar esta sesión* y después *Terminar y guardar*.

Escuchar y grabar son dos cosas distintas, y vale la pena entender por qué:
mientras no grabás, el audio se tira y la historia se recorta a
`SEGUNDOS_EN_PANTALLA`. Sin ese recorte, dejar la app abierta sumaría diez
megas de audio por minuto sin que hayas tocado nada que quisieras guardar. Al
apretar Grabar se tira todo lo anterior y ahí sí se guarda hasta el final.

Al terminar de grabar aparece **lo que grabaste** —la tablatura, cuántas
notas, cuánto duró— y ahí le ponés **nombre** y **descripción**, los dos
opcionales. Dentro de un mes son la diferencia entre doce carpetas con fecha y
hora y saber cuál era la que valía la pena: el nombre va al archivo
(`2026-09-08_18-30-00_bloque-t2_tab.txt`, después de la fecha para que sigan
ordenándose solos) y los dos al encabezado de la tab, del resumen y del JSON.
En el Historial cada sesión aparece con su nombre.

Y en ese mismo paso está la pregunta que solo tiene sentido después de tocar:
**¿sobre qué base estabas, a cuántos BPM?** Si lo contestás, al guardar se
mide el **ritmo** —dispersión, promedio, porcentaje a tiempo, y el
diagnóstico— y queda en el resumen y en el JSON. Si lo dejás vacío, no se
inventa nada. Es la tercera medición del proyecto, y hasta acá solo existía en
la terminal con `--bpm`: la pantalla nunca la había podido usar. Con esto el
"Bloque T2" deja de ser un ejercicio especial: ponés el BPM de tu base de
Band-in-a-Box, tocás la escala en corcheas, y listo.

Vale lo mismo que en la terminal: si la grilla no explica lo que tocaste
(`ajuste_vs_azar` cerca de 1), los números se muestran apagados y **sin
diagnóstico**. Un solo con fraseo libre no es material para medir ritmo, y la
app lo dice en vez de reportar "dispersión 63 ms" con cara de verdad.

En **Frases** el orden es al revés, a propósito: primero grabás, después
nombrás. Apretás *Grabar una frase*, tocás —con un cartel de punto rojo, reloj,
barra de nivel y la tablatura saliendo en vivo—, y al terminar aparece **lo
que salió**: la tablatura, cuántas notas, cuánto duró. Recién ahí le ponés
nombre, descripción y lista, y la guardás. O la descartás y grabás de nuevo.
Importar un audio termina en la misma pantalla. Antes el nombre iba antes de
grabar y la frase se guardaba sola al terminar, con una línea de texto como
única confirmación: la primera frase grabada se perdió sin que nadie se diera
cuenta. Si recargás la página con una frase sin guardar, sigue ahí.

Las frases se organizan en **listas de reproducción** —"turnarounds", "clase
del martes", "para calentar"—. Una lista existe aunque esté vacía: la creás,
la renombrás (arrastra sus frases) y la borrás (las frases quedan, sin lista:
ordenar no borra grabaciones). Cada frase está en una lista o en ninguna.
Marcás varias con su casilla y las mandás juntas. Después elegís una lista y
practicás solo esas, con sus reproductores en fila.

El diagrama de la armónica es **como el instrumento**: agujeros 1 a 10 de
izquierda a derecha, cada uno una columna. Arriba lo soplado, abajo lo
aspirado, el número en el medio, y los bends apilados **hacia afuera**: los
soplados (8, 9, 10) suben por encima del soplado, los aspirados bajan por
debajo del aspirado. Es la disposición de todas las tablas de armónica y la
del modo horizontal de Bending Trainer.

**El color dice la dirección.** Soplado en cobre, aspirado en azul hielo; un
bend es el mismo color con el borde punteado; lo que está en la escala de
referencia lleva un punto verde. Antes el color decía "en escala" y nada
decía de un vistazo si había que soplar o aspirar, que es lo primero que se
mira.

Una **línea lavanda** marca dónde está tu afinación entre una nota y la de al
lado. Corre en vertical dentro de la columna, y el signo es el mismo para los
dos lados, que es la gracia de esta disposición: un bend es bajar de tono, y
bajar de tono es alejarse del número, hacia afuera. En un bend a medio hacer
la ves en el medio, y se pone verde cuando llegaste.

En el cartel de grabar una frase hay una **miniatura** del mismo diagrama,
que se ilumina igual mientras tocás: no hace falta cambiar de solapa para
ver dónde estás.

**La apariencia.** Fondo carbón cálido, con un resplandor cobre y un grano
casi invisible: es una pantalla para mirar de noche, de reojo, con la
armónica en la boca. Hay un solo color protagonista, el cobre de las placas
de lengüetas, y lo llevan el botón de grabar, la solapa activa y las
etiquetas. Los demás colores tienen un significado cada uno y no se usan
para otra cosa: azul aspirado, lavanda la aguja, verde afinada o en escala,
amarillo cerca o aviso, rojo lejos o grabando. La nota grande del medidor y
la tablatura también van en cobre o azul según la dirección.

Tres tipografías con un trabajo cada una: **Fraunces** para los títulos y
la nota grande, **Instrument Sans** para el texto, **IBM Plex Mono** para la
tablatura y los números. Están en `armonica/web/fuentes/`, así que la app se
ve igual sin internet.

Arriba de todo, en **En vivo**, hay una **barra de nivel de entrada**. Es lo
primero que hay que mirar cuando parece que no anda nada: sin ella, un
micrófono equivocado y una armónica tocada bajito se ven exactamente igual
—la pantalla quieta— y no hay forma de saber cuál de los dos es.

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

Son 684 y no necesitan micrófono: el audio se genera, y la captura en vivo se
prueba inyectando datos en la cola interna, que es exactamente lo que hace la
placa de sonido.

Uno solo se saltea si no tenés ffmpeg instalado: es el que convierte un
`.m4a` de verdad. Los demás no necesitan nada.

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

---

## Aportar

Licencia MIT. Si querés ayudar con la armónica, o arrancar la **guitarra**
como instrumento hermano en el mismo repo, leé [CONTRIBUTING.md](CONTRIBUTING.md):
cómo correrlo, las reglas de la casa, y por dónde empezar. Primero un issue,
después el código.
