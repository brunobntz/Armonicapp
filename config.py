"""
config.py — TODOS los parámetros ajustables de la app, en un solo lugar.

La idea: si querés cambiar cómo se comporta la app (que sea más o menos sensible,
que descarte notas más cortas, etc.) tocás SOLO este archivo, nunca el código.

Cada parámetro dice: qué es, en qué unidad está, y qué pasa si lo subís o lo bajás.
Algunos todavía no se usan (los usará un paso posterior del plan), pero están
declarados desde el principio para que este archivo sea el mapa completo.
"""

# =============================================================================
# 1. AUDIO — cómo capturamos el sonido
# =============================================================================

# Muestras por segundo. 44100 Hz es el estándar de CD y lo que casi cualquier
# micrófono de Windows soporta sin conversiones. No lo bajes salvo problemas de
# rendimiento: menos muestras = menos precisión en las notas agudas.
FRECUENCIA_MUESTREO = 44100

# Cuántas muestras analizamos por ventana de detección de tono.
# 2048 muestras a 44100 Hz = 46 ms de audio.
#   - Más grande (4096): detecta mejor las notas graves, pero reacciona más lento.
#   - Más chico (1024): reacciona más rápido, pero no "ve" bien las notas graves.
# Regla práctica: la ventana debe contener al menos 2 ciclos de la nota más grave
# que quieras detectar. G3 = 196 Hz -> un ciclo son 225 muestras -> 2048 sobra.
TAMANO_VENTANA = 2048

# Cada cuántas muestras avanzamos entre ventana y ventana ("salto" o hop).
# 512 muestras = 11.6 ms, o sea unos 86 análisis por segundo.
#   - Más chico: más resolución temporal (capta notas rápidas), más CPU.
#   - Más grande: menos CPU, pero podés perder notas cortas.
SALTO_VENTANA = 512

# Dispositivo de entrada de audio.
#   None = micrófono predeterminado de Windows.
#   Si tenés varios micrófonos, corré `python -m sounddevice` para ver la lista
#   y poné acá el número o el nombre del que quieras usar.
DISPOSITIVO_ENTRADA = None

# Canales de entrada. 1 = mono. La armónica es una sola fuente, no hace falta estéreo.
CANALES = 1


# =============================================================================
# 2. DETECCIÓN DE TONO (YIN) — cómo decidimos qué frecuencia estás tocando
# =============================================================================

# Umbral del algoritmo YIN: cuánta confianza exigimos para aceptar un tono.
# El valor típico del paper original es 0.10 a 0.15.
#   - Más bajo (0.08): más exigente. Menos falsos positivos, pero puede perder
#     notas suaves o bends a medio hacer.
#   - Más alto (0.20): más permisivo. Detecta más, pero también detecta ruido.
UMBRAL_YIN = 0.12

# Rango de frecuencias que consideramos válidas, en Hz.
# La nota más grave de nuestras armónicas es G3 = 196 Hz (armónica en G, agujero 1
# soplado). La más aguda ronda C7 = 2093 Hz (armónica en D, agujero 10 soplado).
# Dejamos margen a los dos lados.
#   - Achicar el rango reduce el error clásico de los detectores: la octava equivocada.
FRECUENCIA_MINIMA_HZ = 150.0
FRECUENCIA_MAXIMA_HZ = 2500.0


# =============================================================================
# 3. SEGMENTACIÓN — cómo agrupamos ventanas sueltas en "notas tocadas"
# =============================================================================

# Umbral de volumen (RMS, valor entre 0.0 y 1.0). Por debajo de esto consideramos
# que hay silencio y ni siquiera intentamos detectar la nota.
#   - Más bajo (0.005): capta notas muy suaves, pero también el ruido de fondo
#     de la habitación y de tu respiración.
#   - Más alto (0.05): ignora el ruido, pero te obliga a tocar fuerte.
# ESTE ES EL PRIMER PARÁMETRO A CALIBRAR con tu micrófono y tu habitación.
UMBRAL_VOLUMEN_RMS = 0.01

# Duración mínima, en segundos, para que algo cuente como nota.
# Por debajo lo descartamos: suele ser un chirrido de transición entre dos notas,
# no una nota que quisiste tocar.
#   - Más bajo (0.03): captura notas muy rápidas, pero mete basura.
#   - Más alto (0.15): solo notas claras y sostenidas, pero perdés frases rápidas.
DURACION_MINIMA_SEG = 0.06

# Cuántas ventanas seguidas SIN detección toleramos antes de cerrar una nota.
# Sirve para que un solo frame malo (un golpe de aire, un instante de duda) no
# parta una nota larga en dos notas cortas.
#   - Más alto (5): notas más "pegadas", tolera imperfecciones.
#   - Más bajo (1): corta al primer frame dudoso.
VENTANAS_SILENCIO_TOLERADAS = 3

# Tolerancia en cents para afirmar "esta frecuencia ES esta nota".
# Un semitono son 100 cents, así que 50 cents equivale a "el semitono más cercano".
#   - Más bajo (30): más estricto. Los bends a medio hacer no se cuentan como nota.
#     Bueno para practicar afinación, molesto para transcribir.
#   - Más alto (50): acepta todo como el semitono más cercano.
TOLERANCIA_CENTS = 50.0


# =============================================================================
# 4. MAPEO A LA ARMÓNICA — resolución de ambigüedades
# =============================================================================

# En la afinación Richter hay notas que se pueden tocar de dos formas.
# Ejemplo en armónica en C: G4 es el agujero 2 aspirado y también el 3 soplado.
# Sin más contexto no se puede saber cuál usaste, así que elegimos uno.
#   "aspirado" = preferir el aspirado (típico del blues, 2a posición).
#   "soplado"  = preferir el soplado (más común en melodías de 1a posición).
# En V2 esto se podría inferir por contexto: qué agujero tocaste justo antes.
PREFERENCIA_AMBIGUEDAD = "aspirado"


# =============================================================================
# 4b. NOTACIÓN — cómo se escribe la tablatura en pantalla y en los archivos
# =============================================================================

# En tu material conviven tres notaciones distintas:
#   - La que vos confirmaste:      -4   -4'   -3''
#   - La de tu atril de 12a:       ↓4   ↓4'   ↓3''   (y ↑ para soplado)
#   - La de las hojas de Leandro:  el número con una rayita arriba o abajo
#
# Internamente la app NUNCA guarda texto: guarda agujero, dirección y cantidad
# de bends. El texto se arma recién al mostrarlo. Por eso cambiar de notación
# es cambiar esta línea, y no afecta nada más.
#
#   "flechas" ->  ↑4  ↓4   ↓4'   ↓3''      (la de tu atril, la elegida)
#   "guion"   ->  4   -4   -4'   -3''      (la estandar de los metodos)
NOTACION = "flechas"

# Símbolo de los bends. El apóstrofo simple es lo estándar en tablatura de
# armónica: uno por cada medio tono. Tu atril usa ′ ″ ‴ (primas tipográficas),
# que se ven mejor pero son incómodas de tipear.
SIMBOLO_BEND = "'"

# Símbolo de overblow, para cuando entren (fuera de V1). Tu atril usa "°".
SIMBOLO_OVERBLOW = "°"


# =============================================================================
# 5. PANTALLA — cómo se ve en la terminal
# =============================================================================

# Cuántas veces por segundo se redibuja la pantalla en vivo.
# Más de 15 no aporta nada al ojo humano y gasta CPU.
REFRESCOS_POR_SEGUNDO = 12

# Cuántas notas de la tablatura mostramos en la línea de historial.
CANTIDAD_TAB_VISIBLE = 20

# Ancho, en caracteres, del medidor de afinación en cents.
# Se dibuja como una barra centrada en 0 cents (afinación perfecta).
ANCHO_MEDIDOR_CENTS = 21

# Colores del diagrama (nombres válidos de la librería rich).
COLOR_EN_ESCALA = "green"             # agujero que pertenece a la escala de referencia
COLOR_FUERA_ESCALA = "yellow"         # nota tocada que NO está en la escala
COLOR_ACTUAL = "bold white on blue"   # agujero que estás tocando ahora
COLOR_NEUTRO = "dim white"            # agujero disponible pero fuera de la escala


# =============================================================================
# 6. RESUMEN DE SESIÓN — umbrales de las reglas de fortalezas y débiles
# =============================================================================

# Cuántos pares de agujeros consecutivos (bigramas) mostramos en el resumen.
TOP_PARES_CONSECUTIVOS = 5

# Si usaste este porcentaje o más de los agujeros de la escala, es una fortaleza.
UMBRAL_BUENA_COBERTURA = 0.75

# Si usaste menos que esto, es un punto a trabajar.
UMBRAL_MALA_COBERTURA = 0.40

# Si un solo par de agujeros representa más que este porcentaje de tus transiciones,
# es señal de que estás repitiendo siempre la misma frase.
UMBRAL_FRASE_REPETIDA = 0.20

# Si el porcentaje de notas fuera de la escala supera esto, lo señalamos.
UMBRAL_FUERA_ESCALA_ALTO = 0.25

# Duración media de nota, en segundos, por debajo de la cual decimos que estás
# tocando todo muy parejo y rápido, y conviene sostener más las notas.
UMBRAL_NOTAS_CORTAS_SEG = 0.20


# =============================================================================
# 7. ARCHIVOS — dónde se guarda todo
# =============================================================================

CARPETA_SESIONES = "sesiones"
CARPETA_AUDIO_PRUEBA = "audio_prueba"

# Si es True, cada sesión en vivo guarda también el audio crudo en .wav.
# Muy recomendado: te permite reprocesar la misma sesión con otros umbrales sin
# tener que volver a tocar exactamente lo mismo.
GUARDAR_AUDIO_DE_SESION = True
