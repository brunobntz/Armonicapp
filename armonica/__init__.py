"""
Paquete `armonica`: lógica de la app de transcripción de armónica.

Cada módulo tiene UNA responsabilidad:

  tablas.py        -> solo datos: afinación, bends, tonalidades, posiciones, escalas
  notas.py         -> frecuencia <-> MIDI <-> nombre de nota
  mapeo.py         -> nota -> agujero / dirección / bend
  posiciones.py    -> tonalidad por posición, pertenencia a escalas (tablas explícitas)
  teoria.py        -> escalas calculadas por intervalos (12 posiciones)
  tono.py          -> detector de tono YIN
  audio.py         -> micrófono y archivos .wav
  segmentacion.py  -> ventanas -> eventos de nota
  tonalidad.py     -> detectar tonalidad de lo tocado y sugerir armónica
  resumen.py       -> estadísticas y fortalezas/débiles
  exportacion.py   -> escribir archivos de sesión
  pantalla.py      -> diagrama y feedback en terminal (rich)

Regla de oro: los módulos "musicales" (tablas, notas, mapeo, posiciones, teoria,
tonalidad, resumen) NO importan sounddevice ni rich. Son Python puro y portables.
"""
