# Empezar en otra máquina

Para dejar la app andando en una computadora nueva, con el acceso directo en
el escritorio y el coach configurado. Escrito para Windows 11. Son seis
pasos, y al final hay un prompt para pegarle a Claude Code y que los haga
con vos.

## 0. Antes de nada: de dónde sale la carpeta

Hay dos formas de tener el proyecto en la máquina nueva, y conviene elegir
una sola.

**A. Clonar desde GitHub (recomendada).** Una carpeta local, fuera de
OneDrive, con la última versión del código. Es lo que hacen los pasos de
abajo. Tus frases y sesiones no viajan con git: se copian aparte (paso 5).

**B. Usar la carpeta de OneDrive directamente.** Funciona, con dos
cuidados. Primero: la carpeta `.venv` que hay adentro es el entorno virtual
de la OTRA máquina y no sirve acá; hay que borrarla y crear una nueva (el
paso 2 lo hace igual). Segundo: OneDrive sincroniza todo lo que toca la app,
incluidas las sesiones con audio, y mientras está sincronizando puede
trabar la escritura de un archivo. Si te pasa, es eso. Con esta opción,
salteá el `git clone` y pará la terminal en la carpeta de OneDrive.

## 1. Lo que hay que tener instalado

Todo desde una terminal PowerShell, una sola vez:

```powershell
winget install Python.Python.3.12
winget install Git.Git
winget install Gyan.FFmpeg
```

Y si vas a usar el coach local (paso 4, opción Ollama):

```powershell
winget install Ollama.Ollama
```

Después cerrá y abrí la terminal, para que tome los programas nuevos.

## 2. La carpeta y el entorno

```powershell
cd $HOME\Documents
git clone https://github.com/brunobntz/Armonicapp.git
cd Armonicapp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
```

Si los tests pasan, el proyecto está sano. No necesitan micrófono ni
internet.

## 3. El acceso directo en el escritorio

```powershell
powershell -ExecutionPolicy Bypass -File herramientas\acceso_directo.ps1
```

Deja "Armonica" en el escritorio, con el icono de la armónica. Doble clic
abre la app en el navegador; la ventana negra que queda atrás es el servidor
y hay que minimizarla, no cerrarla. La configuración de arranque (armónica,
posición, escala) está en la línea `set OPCIONES` de `Armonica.bat`.

Abrila una vez y andá a **Ajustes**: elegí el micrófono explícitamente, no
"el predeterminado de Windows", y soplá: la barra tiene que moverse.
Después medí el ruido de fondo y poné el número que te dice en
`UMBRAL_VOLUMEN_RMS` dentro de `config.py`:

```powershell
python main.py --calibrar
```

## 4. El coach

Es opcional. Se activa con un archivo `.env` que git ignora:

```powershell
copy .env.ejemplo .env
```

Y en el `.env` elegís UNA de estas dos opciones.

**Claude (con clave, cuesta centavos por devolución):**

```powershell
pip install anthropic
```

y en el `.env` dejá `LLM_PROVEEDOR=claude` y pegá tu clave de
https://console.anthropic.com/ en `LLM_CLAVE`.

**Ollama (local, gratis, sin internet).** Con una placa de video de 8 GB
entra entero un modelo de 7 mil millones de parámetros y contesta en pocos
segundos. Bajalo una vez (unos 4,7 GB):

```powershell
ollama pull qwen2.5:7b
```

Ollama queda corriendo solo como servicio; si no, `ollama serve`. En el
`.env` dejá activas estas líneas, y las de Claude comentadas con `#`:

```
LLM_PROVEEDOR=ollama
LLM_MODELO=qwen2.5:7b
```

Con cualquiera de las dos, reiniciá la app y en **Ajustes** tiene que decir
"Activo". Si dice otra cosa, el mensaje te dice qué falta.

Para probarlo: en **Frases**, elegí una frase y dale Practicar; al terminar,
abajo de la devolución aparece "Que me lo explique el coach". Con Ollama la
primera respuesta tarda diez o veinte segundos porque carga el modelo en la
placa; las siguientes, unos segundos. Si el castellano de Qwen no te
convence, probá `ollama pull llama3.1:8b` y cambiá `LLM_MODELO`.

## 4b. Los apuntes de las clases

La solapa **Aprendizaje** lee los resúmenes de tus clases de `material/`.
Si ya los tenés en otro lado (por ejemplo, en la carpeta donde tu asistente
deja los recaps del profe), agregá en el `.env` la ruta, y la app lee de ahí
sin copiar nada. Solo lee: nunca escribe en esa carpeta.

```
CARPETA_CLASES=C:\ruta\a\mis\clases
```

## 5. Tus datos

`frases/`, `sesiones/` y `material/` no viajan con git. Copiá de la otra
máquina (o de la carpeta de OneDrive) lo que quieras tener acá:

- `frases/` entera: los `.json` y los `_audio.wav`, y `_listas.json` con
  tus listas de reproducción.
- `sesiones/` si te importa el historial de bends.
- `material/` con los apuntes y audios de las clases.

## 6. Verificar

Abrí la app desde el acceso directo, tocá algo en **En vivo** y fijate que
el diagrama siga la nota. Practicá una frase y pedile la explicación al
coach. Si las dos cosas andan, está todo.

---

## El prompt para Claude Code

Abrí Claude Code en la carpeta del proyecto en la máquina nueva y pegale
esto, cambiando lo que corresponda:

> Acabo de clonar este repositorio en una laptop nueva (Windows 11, placa
> NVIDIA RTX 5050 de 8 GB, 32 GB de RAM). Leé `README.md`,
> `CONTRIBUTING.md` y `EMPEZAR_EN_OTRA_MAQUINA.md` antes de hacer nada, y
> seguí esa guía en orden: verificá qué falta instalar (Python, ffmpeg,
> Ollama), armá el entorno virtual, corré los tests, creá el acceso directo
> del escritorio con `herramientas\acceso_directo.ps1`, ayudame a elegir el
> micrófono y a calibrar el umbral, bajá el modelo `qwen2.5:7b`, dejá el
> `.env` con `LLM_PROVEEDOR=ollama`, y probá una devolución del coach de
> punta a punta. Antes de cada paso que cambie algo en la máquina, decime qué
> vas a hacer. Al final contame qué quedó configurado y cuánto tardó la
> primera respuesta del coach.

Si en vez de Ollama querés Claude, cambiá la última parte por: "dejá el
`.env` con `LLM_PROVEEDOR=claude` y decime dónde pegar mi clave; no la
escribas vos ni la pidas por acá".
