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

En la máquina de Bruno, que lo tiene Activado, el instalador sin firma corrió.
Pero ese instalador se armó ahí mismo: no pasó por internet, así que no trae
la marca de "descargado de internet" (Mark of the Web). Todavía no se probó si
Windows bloquea el instalador BAJADO de Drive: el paso 1 de la prueba lo
comprueba. Con el control activado no hay "Ejecutar de todas formas".

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
   navegador (desde el usuario de prueba, si usás uno). Sacar una captura del
   aviso de SmartScreen ("Windows protegió su PC" → "Más información" →
   "Ejecutar de todas formas"): va a la guía. Si en cambio lo bloquea sin
   ofrecer "Ejecutar de todas formas", es el Control inteligente de
   aplicaciones: anotarlo, porque cambia qué hay que firmar.
2. Instalar: no tiene que pedir permisos de administrador.
3. Abrir desde el ícono del escritorio: se abre el navegador y no aparece
   ninguna ventana negra.
4. Hacer los primeros pasos. Tocar en En vivo: la aguja se mueve.
5. Grabar una sesión, guardar una frase, abrir una canción de ejemplo y
   reproducir su base.
6. Con una foto .HEIC de una canción y un audio de WhatsApp (usa ffmpeg),
   anotar si la conversión anda o si sale "Windows no lo dejó correr" (ver
   Control inteligente de aplicaciones, arriba). En la máquina de Bruno tiene
   que andar. La foto no usa ffmpeg: tiene que verse siempre.
7. Hacer doble clic en el ícono dos veces seguidas, rápido: una sola app;
   la segunda vez solo se abre el navegador.
8. Cerrar la pestaña: al minuto se apaga el ícono de micrófono en uso de
   Windows. Ajustes → Cerrar la app: el proceso termina.
9. Con la app abierta, volver a correr el instalador (sirve el mismo): la
   cierra antes de instalar, y la frase y los ajustes siguen.
10. Desinstalar desde Configuración → Aplicaciones: `Documentos\Armonica`
    sigue entera.

Si algo falla, `Documentos\Armonica\registro.txt` tiene el detalle.
