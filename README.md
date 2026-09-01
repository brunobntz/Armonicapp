# Armónica → Tablatura

App de escritorio (Windows, terminal) que escucha una armónica diatónica de 10 agujeros
por el micrófono, transcribe lo tocado a tablatura por agujero (`4 -4 5 -4'`) con su nota,
y ayuda a improvisar mostrando la escala de la posición elegida.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

(Se completa a medida que avanzan los pasos del plan.)

## Tests

```bash
python -m pytest
```

## Estructura

Ver el docstring de `armonica/__init__.py`: un módulo por responsabilidad, tablas
musicales aisladas en `armonica/tablas.py`, parámetros ajustables en `config.py`.
