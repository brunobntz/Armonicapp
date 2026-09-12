# Empezar en otra máquina

Para clonar el proyecto en una computadora nueva y dejarlo andando con el
coach local. Escrito para una laptop con Windows 11 y una placa NVIDIA, que es
donde Ollama rinde. Son cinco pasos y un prompt para Claude Code al final,
por si preferís que te acompañe.

## 1. Lo que hay que tener instalado

Todo desde una terminal PowerShell, una sola vez:

```powershell
winget install Python.Python.3.12
winget install Git.Git
winget install Gyan.FFmpeg
winget install Ollama.Ollama
```

Después cerrá y abrí la terminal, para que tome los programas nuevos.

## 2. Clonar y preparar el proyecto

```powershell
cd $HOME\Documents
git clone https://github.com/brunobntz/Armonicapp.git
cd Armonicapp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
```

Si los tests pasan, el proyecto está sano. No necesitan micrófono.

## 3. El micrófono y el ruido de la habitación

Abrí la app y elegí el micrófono en **Ajustes**, explícitamente, no "el
predeterminado de Windows":

```powershell
python main.py --web --posicion 12 --escala blues_mayor
```

Después medí el ruido de fondo y poné el número que te dice en
`UMBRAL_VOLUMEN_RMS` dentro de `config.py`:

```powershell
python main.py --calibrar
```

## 4. El coach local con Ollama

Con una placa de 8 GB entra entero un modelo de 7 mil millones de parámetros
y contesta en pocos segundos. Bajalo una vez (son unos 4,7 GB):

```powershell
ollama pull qwen2.5:7b
```

Ollama queda corriendo solo como servicio; si no, `ollama serve`. Ahora la
configuración del coach:

```powershell
copy .env.ejemplo .env
```

Y en el `.env` dejá estas dos líneas activas (las de Claude comentadas):

```
LLM_PROVEEDOR=ollama
LLM_MODELO=qwen2.5:7b
```

Reiniciá la app y en **Ajustes** tiene que decir "Activo: Ollama (local)".
Si dice que no encuentra el modelo o que Ollama no está corriendo, el
mensaje te dice qué hacer.

Para probarlo: en **Frases**, elegí una frase y dale Practicar; al terminar,
abajo de la devolución aparece "Que me lo explique el coach". La primera
respuesta tarda diez o veinte segundos porque carga el modelo en la placa;
las siguientes, unos segundos.

Si el castellano de Qwen no te convence, probá `ollama pull llama3.1:8b` y
cambiá `LLM_MODELO`. Los dos entran en 8 GB. Uno más grande (14B) ya no, y
pasa a contestar en minutos.

## 5. Tus datos

`frases/`, `sesiones/` y `material/` no viajan con git. Si querés las frases
que ya tenés en la otra máquina, copiá la carpeta `frases/` entera (los JSON
y los `_audio.wav`) a la nueva. Lo mismo con `sesiones/` si te importa el
historial.

---

## El prompt para Claude Code

Si abrís Claude Code en la carpeta del proyecto en la laptop, pegale esto:

> Acabo de clonar este repositorio en una laptop nueva (Windows 11, RTX 5050
> de 8 GB, 32 GB de RAM). Leé `README.md`, `CONTRIBUTING.md` y
> `EMPEZAR_EN_OTRA_MAQUINA.md` antes de hacer nada. Quiero dejar la app
> andando con el coach local por Ollama, siguiendo esos pasos en orden:
> verificá qué falta instalar (Python, ffmpeg, Ollama), armá el entorno
> virtual, corré los tests, ayudame a elegir el micrófono y a calibrar el
> umbral, bajá el modelo `qwen2.5:7b`, dejá el `.env` con
> `LLM_PROVEEDOR=ollama`, y probá una devolución del coach de punta a punta.
> Antes de cada paso que cambie algo en la máquina, decime qué vas a hacer.
> Contame al final qué quedó configurado y cuánto tardó la primera respuesta
> del coach.
