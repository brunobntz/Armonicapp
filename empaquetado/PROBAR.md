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

Con el control activado, el instalador sin firma corrió (probado en la máquina
de Bruno, que lo tiene en Activado), y la app anda. Lo que no anda es el
`ffmpeg.exe` que viaja con ella, que tampoco está firmado: Windows no lo deja
correr y no se pueden convertir los audios que no son `.wav` (WhatsApp, m4a,
etc.). La app lo dice en castellano: "Windows no lo dejó correr. Probá con el
audio en .wav." La grabación, el En vivo, las frases, las fotos y los .wav
andan igual.

No le pidas al profe que lo apague a la ligera: una vez desactivado no se
puede volver a activar sin reinstalar Windows. Si lo tiene activado, hay que
decidir entre un ffmpeg con firma o reputación, o firmar el instalador
(queda en `PROXIMOS_PASOS.md`).

## La prueba

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
6. Con una foto .HEIC y un audio de WhatsApp, anotar si la conversión anda o
   si sale "Windows no lo dejó correr" (ver Control inteligente de
   aplicaciones, arriba). La foto no usa ffmpeg: tiene que verse siempre.
7. Hacer doble clic en el ícono dos veces seguidas, rápido: una sola app;
   la segunda vez solo se abre el navegador.
8. Cerrar la pestaña: al minuto se apaga el ícono de micrófono en uso de
   Windows. Ajustes → Cerrar la app: el proceso termina.
9. Instalar una versión nueva encima con la app abierta: el instalador la
   cierra; la frase y los ajustes siguen.
10. Desinstalar desde Configuración → Aplicaciones: `Documentos\Armonica`
    sigue entera.

Si algo falla, `Documentos\Armonica\registro.txt` tiene el detalle.
