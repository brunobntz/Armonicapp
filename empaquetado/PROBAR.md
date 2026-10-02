# Probar el instalador en un Windows limpio

Antes de mandarle una versión al profe, probala en un segundo usuario de
Windows (Configuración → Cuentas → Otros usuarios → Agregar cuenta; Windows
Home no tiene Sandbox), sin Python ni ffmpeg instalados.

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

Con el control activado, en la máquina de Bruno (que lo tiene en Activado)
corrió el instalador sin firma y la app anda. Pero ese instalador se armó ahí
mismo: no pasó por internet, así que no trae la marca de "descargado de
internet" (Mark of the Web). Si Windows bloquea el instalador BAJADO de Drive
todavía no se probó: el paso 1 de la prueba lo comprueba, y con el control
activado no hay "Ejecutar de todas formas".

Lo que no anda es el `ffmpeg.exe` que viaja con la app, que tampoco está
firmado: Windows no lo deja correr y no se pueden convertir los audios que no
son `.wav` (WhatsApp, m4a, etc.). La app lo dice en castellano: "Windows no lo
dejó correr. Probá con el audio en .wav." La grabación, el En vivo, las
frases, las fotos y los .wav andan igual.

No le pidas al profe que lo apague a la ligera: en muchas versiones de
Windows, una vez desactivado no se puede volver a activar sin reinstalar
(verificalo en la máquina antes de tocarlo). Si lo tiene activado, hay que decidir entre firmar el `ffmpeg.exe`
(o todo el paquete) o usar un ffmpeg con reputación (queda en
`PROXIMOS_PASOS.md`). Firmar solo el instalador no alcanza: lo que Windows
bloquea es el `ffmpeg.exe`, que el instalador apenas copia.

## La prueba

Antes de pasar al usuario de prueba, cerrá Armónica en el tuyo (Ajustes →
Cerrar la app) o cerrá la sesión: 127.0.0.1 es el mismo para todas las
sesiones de Windows, y el lanzador o el instalador del usuario de prueba
hablarían con tu app en vez de arrancar la suya.

1. Subir `dist\Armonica-<versión>-instalador.exe` a Drive y bajarlo desde
   ese usuario con el navegador. Sacar una captura del aviso de SmartScreen
   ("Windows protegió su PC" → "Más información" → "Ejecutar de todas
   formas"): va a la guía. Si en cambio lo bloquea sin ofrecer "Ejecutar de
   todas formas", es el Control inteligente de aplicaciones: anotarlo, porque
   cambia qué hay que firmar.
2. Instalar: no tiene que pedir permisos de administrador.
3. Abrir desde el ícono del escritorio: se abre el navegador y no aparece
   ninguna ventana negra.
4. Hacer los primeros pasos. Tocar en En vivo: la aguja se mueve.
5. Grabar una sesión, guardar una frase, abrir una canción de ejemplo y
   reproducir su base.
6. Con una foto .HEIC de una canción y un audio de WhatsApp (usa ffmpeg),
   anotar si la conversión anda o si sale "Windows no lo dejó correr" (ver
   Control inteligente de aplicaciones, arriba). La foto no usa ffmpeg: tiene
   que verse siempre.
7. Hacer doble clic en el ícono dos veces seguidas, rápido: una sola app;
   la segunda vez solo se abre el navegador.
8. Cerrar la pestaña: al minuto se apaga el ícono de micrófono en uso de
   Windows. Ajustes → Cerrar la app: el proceso termina.
9. Instalar una versión nueva encima con la app abierta: el instalador la
   cierra; la frase y los ajustes siguen.
10. Desinstalar desde Configuración → Aplicaciones: `Documentos\Armonica`
    sigue entera.

Si algo falla, `Documentos\Armonica\registro.txt` tiene el detalle.
