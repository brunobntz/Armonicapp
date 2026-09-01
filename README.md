# Armónica → Tablatura

App de escritorio (Windows, terminal) que escucha una armónica diatónica de 10 agujeros
por el micrófono, transcribe lo tocado a tablatura por agujero (`4 -4 5 -4'`) con su nota,
y ayuda a improvisar mostrando la escala de la posición elegida.

## Instalación (una sola vez)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Uso diario

```powershell
cd "C:\Users\bruno\OneDrive2\OneDrive\Armonica\APP"
.\.venv\Scripts\Activate.ps1
python main.py
```

Cuando el entorno está activado vas a ver `(.venv)` al principio de la línea.

## Tests

```powershell
python -m pytest
```

## Nota sobre PowerShell

Windows PowerShell 5.1 (el que viene con Windows) **no soporta `&&`** para encadenar
comandos: da el error "El token '&&' no es un separador de instrucciones válido".
Usá punto y coma en su lugar:

```powershell
python -m pytest; python main.py
```

## Estructura

Ver el docstring de `armonica/__init__.py`: un módulo por responsabilidad, tablas
musicales aisladas en `armonica/tablas.py`, parámetros ajustables en `config.py`.
