# Próximos pasos

Para arrancar una sesión nueva desde acá. Leer primero `README.md` (qué hace
la app) y `CONTRIBUTING.md` (las reglas de la casa). Estado al 2026-09-17:
repo público en GitHub, 925 tests, todo lo listado en el README está hecho.

## Cómo trabajamos

- Un paso por vez, un commit por paso, y para los pasos grandes: plan
  primero, ok después.
- Todo con test, y los tests nunca abren el micrófono ni tocan la red.
- Nada personal en el repo: ni nombres de terceros (se dice "el profe"), ni
  rutas de una máquina, ni servicios de nube. Los datos viven en `material/`,
  `frases/`, `sesiones/` y el `.env`, que git ignora.
- La carpeta de clases (`CARPETA_CLASES`) es solo lectura. Hay tests que lo
  garantizan; no se rompen.
- El coach explica números que la app midió. Nunca inventa notas, agujeros ni
  cents. Cuando no hay datos, la app se calla.
- Después de cada cambio de código, reiniciar el servidor: Python no recarga
  solo.

## Pendientes que dependen de datos del usuario

1. **Ollama en la laptop.** Ya instalado. Falta contar cuánto tarda la
   primera respuesta y las siguientes, y si el castellano de `qwen2.5:7b`
   convence; si no, probar `llama3.1:8b` cambiando `LLM_MODELO`.
2. **El "8 soplado".** El detector muestra ↑8 donde el usuario cree que hay
   ↑4. Medido sobre los audios de clase: en esos instantes suena un Mi6 real
   (1336 Hz), sin energía una octava abajo, o sea NO es un error de octava
   del detector. Falta que el usuario escuche el segundo audio de clase en
   25,0 s y diga si es un 8 de verdad o algo raro de la grabación. Si es un
   4, investigar la grabación (teléfono, códec), no el detector.

## Issues abiertos en GitHub, en el orden sugerido

3. **#3 Ejercicios generados desde Teoría.** Teoría ya sabe las notas guía de
   cada acorde y en qué agujero se agarran. Falta un botón "armar ejercicio"
   que genere una frase sintética (por ejemplo, la 3ª de cada acorde en el
   tiempo 1 de cada compás, a un BPM dado), con audio
   (`herramientas/generar_wav.py` tiene la base) y la guarde en Frases para
   practicarla como cualquier otra. Es lo que el plan del coach recomienda y
   la app hoy no puede dar.
4. **#2 Band-in-a-Box.** Hecho el primer paso (2026-09-16):
   `armonica/bandinabox.py` lee el `.sgu`/`.mgu` directo y `--base` lo
   muestra: tono, tempo, compás, swing, cifrado y melodía en tablatura. Lo
   que sigue, en orden:
   - **Canciones.** Hecho (2026-09-16): solapa Canciones, una carpeta por
     canción en `material/canciones/<nombre>/` (o `CARPETA_CANCIONES`),
     solo lectura con test. Ficha de la base, cifrado con cambios, audios
     con "Importar como frases", fotos (HEIC vía `pillow-heif` opcional,
     caché en `material/_cache/`), melodía en tab, y el reproductor de la
     base: la app la sintetiza con Web Audio a partir del cifrado (click,
     acordes, bajo, melodía opcional, tempo, repetir) e ilumina el compás
     y el acorde que suenan. Y con el audio real si hay uno en la carpeta
     (exportado desde Band-in-a-Box en WAV): el cifrado lo sigue desde el
     compás 1, que la app mide escuchando dónde entra el bajo
     (`compas_uno.py`), o se marca con un botón, y queda en
     `material/_canciones.json` (`canciones_ajustes.py`).
   - **Las notas de cada acorde en el cifrado.** Hecho (2026-09-17): nota
     y agujero más cómodo bajo cada acorde, guías en cobre, hover con el
     porqué y las notas a evitar (regla: medio tono arriba de una nota del
     acorde), zoom del acorde que suena y el que viene en lavanda. Y la
     tablatura en una ventana aparte (`tablatura.html`). Y "qué dice la
     base": hechos contados (`canciones.hechos_de_la_base`: cadencias,
     acordes fuera de la tonalidad) más la explicación del coach a pedido
     (`coach.explicar_base`), guardada en `_canciones.json`.
   - **Tocar sobre la base.** Hecho (2026-09-16): "Practicar sobre esta
     base" la lleva a En vivo; al grabar hay un compás de conteo, el acorde
     y sus notas guía se ven en pantalla y en el diagrama, la sesión se
     guarda con BPM, figura y offset del compás 1, y el resumen trae el
     bloque "Sobre la base" (`armonica/sobre_la_base.py`). PENDIENTE DE
     MEDIR con micrófono real: el offset del compás 1 lleva la latencia
     del micrófono; `ritmo.ajustar_offset` la corrige con lo tocado, pero
     hay que ver cuánto da en la máquina del usuario (mirar `offset_seg`
     en el JSON de la sesión contra lo que se escucha en el wav).
   - **El círculo de quintas en Teoría.** Hecho (2026-09-17): rueda SVG
     con posiciones fijas y notas que giran, modo "tono de la canción"
     (qué armónica pide cada posición), clic abre la posición
     (`teoria.circulo_de_quintas`, `/api/quintas`).
   - **La tablatura del profe, leída de la foto.** Renglón por renglón,
     en una tarjeta que se corrige como las frases (el profe anota los
     bends distinto). Es lectura de una imagen escrita a mano: la hace el
     coach con visión (Claude, o un modelo local con imágenes en Ollama),
     y queda marcada como "leída de la foto, sin verificar" hasta que el
     usuario la revisa. Aviso igual que con el plan: la foto sale de la
     máquina si el coach es Claude.
5. **#5 Filtros en Historial** por armónica, posición y lista, cuando se
   llene.
6. **#6 La guitarra** como instrumento hermano, en `guitarra/`, reutilizando
   `tono.py`, `ritmo.py` y la interfaz web. Cuando haya interés.

## Ideas nuevas, de más útil a más lejana

- **Sesión guiada.** "Practicar el plan": recorrer las recomendaciones del
  coach una por una, abriendo la frase o el ejercicio, y una devolución de
  la sesión entera al final.
- **Metrónomo con conteo de entrada** en En vivo, a N BPM, con un compás de
  conteo antes de grabar. Sin base no hay ritmo medible; con esto lo hay.
- **Loop de un tramo a menor velocidad** en el reproductor de tramos:
  repetir y tocar al 75 % sin cambiar el tono (el navegador lo soporta:
  `preservesPitch`). Para sacar una frase de oído antes de practicarla.
- **Comparar dos intentos de oído.** Guardar el wav de cada práctica y poder
  escuchar dos intentos seguidos desde el historial de la frase.
- **Resumen semanal del coach.** Sesiones, prácticas y plan de la semana en
  tres líneas. Con Ollama no cuesta nada.
- **Exportar un resumen al cuaderno.** La app escribe Markdown en
  `material/` (nunca en la carpeta de clases) para que el usuario lo lleve a
  su cuaderno.
- **Overblows**, si el profe los sigue trayendo: una tabla más en
  `tablas.py` y que el detector los acepte. Hoy están fuera de alcance a
  propósito.

## Limpieza menor

- En la máquina de desarrollo original hay una etiqueta git local,
  `respaldo-antes-de-reescribir`, con el historial anterior a la reescritura
  de mensajes. Borrarla cuando el usuario esté tranquilo:
  `git tag -d respaldo-antes-de-reescribir`.
