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


# Normalizar el audio de los archivos antes de analizarlo.
#
# POR QUÉ. La primera grabación real de Bruno llegó con un pico del 3% de la
# escala: unos 30 dB por debajo de lo normal. Con el umbral de volumen fijo,
# el 99% de las ventanas quedaba descartado como silencio y la app detectó
# UNA sola nota en 18 segundos de escala.
#
# Normalizar sube toda la señal hasta un pico conocido, así el umbral de
# volumen significa lo mismo sin importar cuánta ganancia tenía el micrófono.
# No inventa información: multiplica todo por un número.
#
# Ponelo en False si querés ver los niveles tal cual quedaron grabados.
NORMALIZAR_ARCHIVOS = True

# A qué pico se lleva la señal al normalizar. 0.7 deja margen para que ninguna
# suma de armónicos sature.
PICO_NORMALIZACION = 0.7


# =============================================================================
# 2. DETECCIÓN DE TONO (YIN) — cómo decidimos qué frecuencia estás tocando
# =============================================================================

# Umbral del algoritmo YIN: cuánta confianza exigimos para aceptar un tono.
# El valor típico del paper original es 0.10 a 0.15.
#   - Más bajo (0.08): más exigente. Menos falsos positivos, pero puede perder
#     notas suaves o bends a medio hacer.
#   - Más alto (0.20): más permisivo. Detecta más, pero también detecta ruido.
UMBRAL_YIN = 0.12

# Cuánto mejor tiene que ser un período MÁS LARGO para preferirlo al que
# encontró YIN. Es la corrección de los errores de octava.
#
# EL PROBLEMA
#
# YIN recorre los retardos de menor a mayor y se queda con el primero que baja
# del umbral. Si un armónico agudo domina el sonido, su retardo —que es más
# corto— aparece primero, y YIN devuelve esa frecuencia con toda confianza.
# Medido: una nota de Do4 con el cuarto armónico dominante se reportaba como
# Do6, con confianza 0.95. En la armónica eso es tocar el agujero 1 y ver el 8.
#
# POR QUE NO ALCANZA CON "ELEGIR EL PERIODO MAS LARGO QUE TAMBIEN SEA BUENO"
#
# Porque una onda que se repite cada T también se repite cada 2T, 3T y 4T,
# SIEMPRE. Medido sobre un Do6 legítimo: el retardo correcto da 0.001 y sus
# múltiplos dan 0.002 y 0.005, todos "buenos". Con esa regla, cada nota aguda
# bajaría dos octavas.
#
# Lo que distingue los dos casos no es que el múltiplo sea bueno, sino que sea
# CLARAMENTE MEJOR que el que encontró YIN:
#
#   Do6 legítimo:            0.001 -> 0.005   el múltiplo es 5 veces PEOR
#   Do4 con 4to armónico:    0.046 -> 0.004   el múltiplo es 11 veces MEJOR
#
# 0.7 quiere decir "el múltiplo tiene que medir menos del 70% que el original".
# El número sale de las mediciones, no de la intuición: los casos que hay que
# corregir daban razones de 0.09 a 0.50, y los que NO hay que tocar daban 2.0
# o más. Cualquier valor entre 0.5 y 1.0 separa los dos grupos; 0.7 queda
# centrado.
#
# Sobre 372 casos fabricados con un armónico dominante, arregla el 61%. Sobre
# 124 notas legítimas no rompe ninguna: la corrección se verifica antes de
# aceptarse y, si no pasa, queda lo que había. Subirlo a 0.95 arregla cuatro
# puntos más; no vale el riesgo de aflojar una regla que hoy es segura.
FACTOR_CORRECCION_OCTAVA = 0.7

# Cuánta energía tiene que haber EN la frecuencia detectada para aceptarla.
# Se mide como amplitud del fundamental dividida por el volumen del bloque.
#
# POR QUÉ EXISTE. Si tocás dos agujeros a la vez (por ejemplo el 6 y el 7
# soplados, que dan Sol5 y Do6), la onda combinada se repite a la frecuencia
# de un Do dos octavas más abajo, aunque ese Do no suene. Se llama "fundamental
# ausente" y es un fenómeno real de la acústica: el oído también lo escucha.
#
# YIN mide repetición, así que reporta ese Do grave. No se equivoca: la onda
# de verdad se repite ahí. Pero para una tablatura es una nota que no tocaste.
#
# La defensa es preguntar si en esa frecuencia HAY energía. En la grabación de
# Bruno, las notas reales dieron entre 0.11 y 0.85; el instante en que sonaron
# dos agujeros juntos dio 0.006. El umbral 0.05 los separa con mucho margen.
#
# Ponelo en 0.0 para desactivar la verificación.
ENERGIA_FUNDAMENTAL_MINIMA = 0.05

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

# Cuántas ventanas seguidas tienen que dar la MISMA nota para que el cartel
# grande de la pantalla la muestre.
#
# La tablatura pasa por segmentacion, que descarta lo que dura menos de
# DURACION_MINIMA_SEG. El cartel grande no pasaba por ningún filtro: mostraba
# la última ventana que dio nota, una por una, ochenta y seis veces por
# segundo. Una sola ventana equivocada —un ataque, un cambio de nota, un golpe
# de aire— se veía como un cambio de nota en la pantalla.
#
# Tres ventanas son unos 35 milisegundos de retraso: no se nota al tocar, y
# saca los parpadeos de una y dos ventanas.
#
# Bajalo a 1 si querés la respuesta más inmediata posible y no te molesta el
# parpadeo. Subilo si todavía ves notas que no tocaste.
VENTANAS_PARA_CONFIRMAR = 3

# Cuánto tiempo sin ninguna nota tiene que pasar para que el cartel se apague,
# en segundos.
#
# Es un umbral distinto y MÁS LARGO que el de arriba, a propósito. Son dos
# preguntas distintas:
#
#   mostrar una nota nueva   tiene que estar confirmada, para no parpadear
#   apagar el cartel         tiene que aguantar los huecos de una nota larga
#
# Dentro de una nota sostenida hay ventanas sueltas donde el detector no
# encuentra nada: un golpe de aire, un cambio de embocadura. Si el cartel se
# apagara con tres ventanas vacías, el agujero desaparecería en cada
# respiración. Con 0.4 segundos aguanta los huecos y se apaga cuando de verdad
# dejaste de tocar.
SEGUNDOS_PARA_APAGAR_CARTEL = 0.4

# Cuántos segundos de lo tocado se guardan en memoria MIENTRAS NO ESTÁS
# GRABANDO, para poder mostrarte la tablatura de lo último que hiciste.
#
# El micrófono queda encendido todo el tiempo que la app está abierta, y eso
# obliga a poner un tope: sin él, cada minuto de estar ahí sentado suma diez
# megas de audio y ochenta mil mediciones, y a la media hora la app se comió
# la memoria de la máquina sin que hayas tocado nada que quisieras guardar.
#
# Cuando apretás Grabar, el tope no se aplica: ahí se guarda todo.
SEGUNDOS_EN_PANTALLA = 20.0

# Cuánto silencio de armónica separa un TRAMO del siguiente, en segundos.
#
# Sirve para partir una grabación larga en los pedazos donde realmente hay
# armónica. Los audios de clase del profe son así: habla, toca una frase,
# vuelve a hablar. Sin esto, importar la clase entera como frase de referencia
# daría una referencia con diez segundos de silencio en el medio, contra la
# que es imposible practicar.
#
# Un segundo y medio es más que cualquier silencio DENTRO de una frase tocada,
# y menos que cualquier explicación hablada. Subilo si te parte una frase en
# dos; bajalo si te junta dos frases distintas en una.
HUECO_ENTRE_TRAMOS_SEG = 1.5

# Cuántas notas tiene que tener un tramo para que valga la pena ofrecerlo.
#
# Con menos de esto casi siempre es una nota suelta de prueba, o una sílaba
# de la voz que el detector confundió. No se descartan por ser errores: se
# descartan porque no son una frase.
NOTAS_MINIMAS_POR_TRAMO = 3

# Corrección del instante de inicio de cada nota, en segundos.
#
# POR QUÉ HACE FALTA. El detector trabaja por ventanas de 46 ms. Cuando una nota
# empieza, la primera ventana que la reconoce ARRANCÓ ANTES de que la nota
# sonara: le alcanza con que la nota ocupe una parte para detectarla. Resultado:
# la app cree que empezaste antes de lo que empezaste.
#
# Medido contra audio generado, donde sabemos el instante exacto, el sesgo va de
# 23 a 34 milisegundos, siempre hacia atrás. Sumando 28 ms el error residual
# queda en unos 6 ms, que es bastante menos que la resolución de una ventana.
#
# ESTO IMPORTA MUCHO para el análisis de ritmo del paso 5b. Los desvíos de
# tiempo que queremos medir rondan los 70 ms, así que un sesgo fijo de 30 ms
# sería casi la mitad de la señal: mediría el retardo del algoritmo en vez de
# tu forma de tocar.
#
# Ponelo en 0.0 si querés ver los tiempos crudos, sin corregir.
CORRECCION_INICIO_SEG = 0.028

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
# 3b. RITMO — cuánto desvío del pulso aceptamos
# =============================================================================

# Cuántos milisegundos de desvío respecto del pulso todavía cuentan como
# "a tiempo".
#
# Referencias para calibrar esto:
#   - Menos de 20 ms: casi nadie lo escucha.
#   - 30 a 50 ms: un músico entrenado lo nota.
#   - Más de 50 ms: suena claramente adelantado o atrasado.
#
# Empezamos en 40, que es exigente pero alcanzable. Si al principio te da un
# porcentaje muy bajo y se vuelve desmoralizante, subilo a 60 y bajalo a
# medida que mejores. La app mide lo mismo; solo cambia dónde ponés la vara.
TOLERANCIA_RITMO_MS = 40.0

# Contra qué figura medimos el pulso, por defecto.
#   1 = negras, 2 = corcheas, 3 = tresillos (el shuffle del blues), 4 = semis.
# Si tocás corcheas y medís contra negras, la mitad de las notas aparecen con
# medio pulso de desvío y el reporte no sirve. En blues suele convenir 2 o 3.
SUBDIVISION_RITMO = 2


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
#   - La de las hojas del profe:  el número con una rayita arriba o abajo
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
