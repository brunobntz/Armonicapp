# Cómo aportar

Gracias por asomarte. Este proyecto nació para una persona que aprende
armónica diatónica con un profesor, y creció midiendo lo que ese profesor
marcaba en las clases. La idea es que sirva para cualquiera que esté
aprendiendo, y que se pueda extender a otros instrumentos.

## Qué hace falta

Abrí un *issue* antes de arrancar algo grande, así no trabajamos dos veces
lo mismo. Hay tres frentes donde una mano sirve:

- **Armónica.** Bugs, precisión de la detección, mejores diagnósticos.
  Mirá los issues abiertos.
- **Guitarra.** Todavía no existe. La idea es un instrumento hermano en el
  mismo repo, en una carpeta `guitarra/`, que reutilice el detector de tono,
  el análisis de ritmo y la interfaz web. Si querés empezar por ahí, abrí un
  issue contando qué querrías que la app te enseñe y desde dónde arrancás.
- **Otros instrumentos.** Mismo criterio: primero el issue, después el código.

## Cómo correrlo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
python main.py --web
```

Los tests corren **sin micrófono**: todo lo que necesita audio lo fabrica
con `numpy`. Si tu cambio necesita audio real, dejalo en `audio_prueba/`,
que no se sube.

## Las reglas de la casa

- **Python 3.11+, solo `sounddevice` y `numpy`.** El detector de tono (YIN)
  está escrito a mano a propósito: la gracia es entender qué hace. No
  agregues bibliotecas de audio.
- **Comentarios y nombres en español.** Los comentarios explican *por qué*,
  no *qué*. Cuando un número viene de una medición, decí de cuál.
- **Claridad antes que ingenio.** Quien lee esto sabe algo de Python y mucho
  de música, no al revés.
- **Cada cambio con su test.** Y si el cambio corrige algo que estaba mal,
  el test tiene que fallar sin el arreglo.
- **La app se calla cuando no sabe.** Antes de mostrar un número nuevo,
  preguntate cómo se rompe y qué pasa cuando no aplica. Un diagnóstico
  inventado es peor que ninguno.
- **Un commit por paso**, con un mensaje que cuente qué cambió y por qué.
- **No se pisa lo verificado en silencio.** Las tablas de notas y escalas
  están contrastadas contra cálculo y contra material de clase. Si algo te
  parece mal, abrí un issue con la fuente.

## Lo que no va al repo

`material/` (apuntes de clases, contenido de terceros), `frases/`,
`sesiones/`, `audio_prueba/` y `.env` (la clave del coach) están en
`.gitignore`. Son datos de quien usa la app en su máquina. No los subas, ni
los tuyos ni los de nadie.

## El coach (LLM)

Es opcional y vive entero en `armonica/coach.py`. Dos reglas: el modelo
recibe números que la app ya midió y solo los explica, nunca mide ni
inventa; y los tests **nunca tocan la red** (se reemplaza `_pedir()` por una
función falsa, mirá `tests/test_coach.py`). Para otro proveedor, reemplazá
`_pedir()` y nada más.
