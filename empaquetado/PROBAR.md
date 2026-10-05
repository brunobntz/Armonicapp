# Probar el instalador antes de mandarlo

Antes de mandarle una versión al profe, probala como la va a usar él. Hay dos
maneras:

- **En un segundo usuario de Windows** (Configuración → Cuentas → Otros
  usuarios → Agregar cuenta; Windows Home no tiene Sandbox). Es la prueba más
  fiel: ese usuario no tiene Python ni ffmpeg instalados, ni el permiso del
  micrófono dado, ni `Documentos\Armonica`.
- **En tu propio usuario.** Alcanza para casi todo. El programa va a
  `%LOCALAPPDATA%\Programs\Armonica` y los datos a `Documentos\Armonica`, sin
  tocar el repo ni sus `material\`, `frases\` y `sesiones\`. El instalador no
  deja elegir la carpeta, y no hace falta. Lo que no se prueba así es el
  permiso del micrófono (ya lo diste) ni que la app ande sin el Python y el
  ffmpeg que tenés instalados. Lo segundo está cubierto igual: el Python del
  paquete no mira el del sistema, el ffmpeg del paquete va primero en el PATH,
  y la prueba de humo del armado lo verifica. Antes de empezar fijate que no
  exista `Documentos\Armonica`, así salen los primeros pasos; al terminar
  borrala a mano, porque desinstalar no la toca.

## Control inteligente de aplicaciones

Windows 11 trae una protección que se llama Control inteligente de
aplicaciones (Smart App Control). Mirá cómo está en la máquina del profe, en
Seguridad de Windows → Control de aplicaciones y navegador → Control
inteligente de aplicaciones. Dice una de tres cosas:

- **Activado:** Windows no deja correr programas sin firma ni reputación.
- **Evaluación:** todavía no bloquea nada, pero Windows puede activarlo solo.
- **Desactivado:** no pasa nada de lo que sigue.

Si no aparece esa opción, no aplica (por ejemplo, en una máquina que vino de
Windows 10).

En la máquina de Bruno, que lo tiene Activado, el instalador sin firma corrió
cuando se armó ahí mismo: no pasó por internet, así que no traía la marca de
"descargado de internet" (Mark of the Web). Bajado de Drive es otra cosa, y se
probó el 2026-10-04 con el control Activado: Windows lo bloqueó y no ofreció
"Ejecutar de todas formas". Lo que lo frenaba era esa marca: con clic derecho
en el instalador → Propiedades → **Desbloquear** (que se la saca) → Aceptar,
corrió. Por lo mismo corre desde un pendrive, si se copia desde `dist\` y no
desde lo bajado. La guía le dice al profe que, si se encuentra con ese
bloqueo, pida el instalador en un pendrive y no toque nada de Windows.
Antes de todo eso, Drive avisa "No se puede analizar el archivo en busca de
virus" (lo dice con los archivos grandes, que no alcanza a revisar): se sigue
con **Descargar de todos modos**.

El `ffmpeg.exe` que viaja con la app tampoco está firmado. Las primeras veces
Windows no lo dejó correr, y desde el 2026-10-02 corre con el control todavía
activado: Windows le da reputación a cada archivo exacto (por su hash), y ese
la ganó. Así que en la máquina del profe probablemente ande, pero solo ese
archivo: un ffmpeg distinto, aunque sea de la misma versión, arranca sin
reputación y puede volver a bloquearse (ver `PROXIMOS_PASOS.md`). Si se
bloquea, la app lo dice en castellano: "Windows no lo dejó correr. Probá con
el audio en .wav." Entonces no se pueden convertir los audios que no son
`.wav` (WhatsApp, m4a, etc.); la grabación, el En vivo, las frases, las fotos
y los .wav andan igual.

No le pidas al profe que lo apague a la ligera: en muchas versiones de
Windows, una vez desactivado no se puede volver a activar sin reinstalar
(verificalo en la máquina antes de tocarlo). Si el ffmpeg se bloquea en su
máquina, las salidas son firmar el `ffmpeg.exe` (o todo el paquete) o usar
otro ffmpeg con reputación. Firmar solo el instalador no alcanza: lo que
Windows bloquea es el `ffmpeg.exe`, que el instalador apenas copia.

## La prueba

Antes de empezar, cerrá la Armónica del repo (Ajustes → Cerrar la app, o su
ventana negra). Si queda abierta, la app instalada la encuentra en 127.0.0.1
y abre esa en vez de arrancar la suya, y el instalador la cierra. Pasa
también desde otro usuario: 127.0.0.1 es el mismo para todas las sesiones de
Windows.

1. Subir `dist\Armonica-<versión>-instalador.exe` a Drive y bajarlo con el
   navegador (desde el usuario de prueba, si usás uno). Drive avisa "No se
   puede analizar el archivo en busca de virus": **Descargar de todos
   modos**. Después depende del Control inteligente de aplicaciones (arriba):
   si está Activado, Windows lo bloquea sin ofrecer "Ejecutar de todas
   formas", y hay que desbloquearlo (Propiedades → **Desbloquear**) o
   usarlo desde el pendrive; si no, probablemente salga el aviso común de
   SmartScreen ("Windows protegió su PC" → "Más información" → "Ejecutar de
   todas formas"). Mirar que lo que sale coincida con el capítulo "Instalar"
   de la guía: es lo que va a seguir el profe.
2. Instalar: no tiene que pedir permisos de administrador.
3. Abrir desde el ícono del escritorio: se abre el navegador y no aparece
   ninguna ventana negra. Mirar que los íconos estén en los tres lugares: el
   escritorio ("Armónica"), el menú Inicio ("Armónica" y "Guía de Armónica")
   y `Documentos\Armonica` ("Abrir Armónica"). Los que dicen Armónica abren
   la app.
4. Hacer los primeros pasos. Tocar en En vivo: la aguja se mueve.
5. Grabar una sesión, guardar una frase, copiar a mano la carpeta de una
   canción a `Documentos\Armonica\canciones` (el instalador no lleva
   canciones: el profe trae las suyas), abrirla en Canciones y reproducir su
   base.
6. Con una foto .HEIC de una canción y un audio de WhatsApp (usa ffmpeg),
   anotar si la conversión anda o si sale "Windows no lo dejó correr" (ver
   Control inteligente de aplicaciones, arriba). En la máquina de Bruno tiene
   que andar. La foto no usa ffmpeg: tiene que verse siempre.
7. La guía. En la barra de la app, el enlace **Guía** la abre en otra
   pestaña, con sus doce capítulos y las capturas. En el menú Inicio, **Guía
   de Armónica** abre el PDF: mirar que tenga todos los capítulos y que las
   capturas se vean.
8. El coach, con internet. En Ajustes → El coach, pegar una clave de cada
   proveedor que tengas (Claude, ChatGPT, Gemini) y tocar **Guardar y
   probar**: dice de quién es y que anda, y el estado pasa a "Activo". El
   casillero queda vacío: la clave no vuelve a la pantalla. Después de
   practicar algo, en la devolución aparece el botón del coach y contesta
   bien, en castellano y sin inventar números; en Teoría hay una pregunta
   libre. Probar **Borrar la clave** (pide confirmación y el coach queda
   apagado) y pegar una de nuevo, para que quede guardada para los pasos
   que siguen; se guarda en `%LOCALAPPDATA%\Armonica\coach.env`.

   Con claves reales, además, se miran los textos que hasta ahora solo se
   probaron con respuestas inventadas:
   - Una clave de OpenAI sin crédito (y una de Claude, si se puede): mirar
     el cuerpo real del error, un 429 en OpenAI y un 400 en Claude, y que
     Guardar y probar diga "La cuenta de esa clave no tiene crédito." (la
     clave queda guardada, sin comprobar).
   - Un 503 de Gemini, si aparece: tiene que decir "El servicio tuvo un
     problema. Probá en un rato."
   - Una clave que el servicio rechaza (por ejemplo, con una letra de
     menos): dice que no es válida y no queda guardada; sigue la de antes.
   - Si Edge ofrece guardar la clave como una contraseña al pegarla.
   - Si `console.anthropic.com` sigue andando: la guía manda a ese sitio.
9. Hacer doble clic en el ícono dos veces seguidas, rápido: una sola app;
   la segunda vez solo se abre el navegador.
10. Cerrar la pestaña: al minuto se apaga el ícono de micrófono en uso de
    Windows. Ajustes → Cerrar la app: el proceso termina.
11. Con la app abierta, volver a correr el instalador (sirve el mismo; con
    una versión anterior instalada, la nueva encima también): la cierra antes
    de instalar, y la frase, los ajustes y la clave del coach siguen.
12. Desinstalar desde Configuración → Aplicaciones: `Documentos\Armonica`
    sigue entera con sus datos (el ícono "Abrir Armónica" sí se va con el
    programa), y `%LOCALAPPDATA%\Armonica\coach.env` ya no está: la clave es
    de esta computadora y no queda.

Si algo falla, `Documentos\Armonica\registro.txt` tiene el detalle.
