/* app.js — La lógica de la página.
 *
 * Javascript común, sin bibliotecas. Hace tres cosas:
 *
 *   1. Pide una vez los datos que no cambian (el diagrama de la armónica).
 *   2. Se queda escuchando el estado en vivo por server-sent events.
 *   3. Dibuja el historial cuando cambiás de solapa.
 *
 * Todo el trabajo pesado lo hace Python. Acá solo se dibuja.
 */

"use strict";

// Cuántos cents de desvío todavía cuentan como afinado.
let TOLERANCIA = 10;

let inicio = null;
let fuente = null;      // la conexión de eventos


/* ==========================================================================
   Arranque
   ========================================================================== */

document.addEventListener("DOMContentLoaded", async () => {
  configurarSolapas();
  configurarBotones();
  configurarListas();
  configurarPendiente();
  configurarSesionPendiente();

  inicio = await pedir("/api/inicio");
  TOLERANCIA = inicio.tolerancia_cents || 10;

  mostrarEncabezado();
  llenarTonalidades();
  marcarUmbral();
  dibujarDiagrama(inicio.diagrama);
  ajustarZonaBuena();

  conectarEnVivo();
  recuperarPendiente();
  recuperarSesionPendiente();
});


async function pedir(ruta, opciones) {
  const respuesta = await fetch(ruta, opciones);
  return respuesta.json();
}


function mostrarEncabezado() {
  // Va al lado del nombre de la app, en una línea: con qué armónica, en qué
  // posición, y qué escala se marca en verde.
  let texto = "armónica en " + inicio.tonalidad;
  if (inicio.posicion) {
    texto += " · " + inicio.nombre_posicion + " → tocás en " + inicio.tono_resultante;
  }
  if (inicio.nombre_escala) {
    texto += " · " + inicio.nombre_escala.toLowerCase();
  }
  document.getElementById("encabezado").textContent = texto;
}


/* ==========================================================================
   Las solapas
   ========================================================================== */

function configurarSolapas() {
  document.querySelectorAll(".solapa").forEach((boton) => {
    boton.addEventListener("click", () => {
      document.querySelectorAll(".solapa").forEach((otro) =>
        otro.classList.toggle("activa", otro === boton));

      const cual = boton.dataset.panel;
      ["vivo", "frases", "historial", "ajustes"].forEach((nombre) => {
        document.getElementById("panel-" + nombre).hidden = nombre !== cual;
      });

      if (cual === "historial") cargarHistorial();
      if (cual === "frases") cargarFrases();
      if (cual === "ajustes") cargarAjustes();
    });
  });
}


/* ==========================================================================
   Empezar y terminar
   ========================================================================== */

function configurarBotones() {
  const grabar = document.getElementById("boton-grabar");

  /* Un solo boton para las dos cosas, porque son la misma decision vista en
   * dos momentos: "quiero que esto quede" y "listo, guardalo". El microfono
   * ya esta prendido, asi que no hay un tercer estado que explicar. */
  grabar.addEventListener("click", async () => {
    grabar.disabled = true;

    if (grabar.dataset.grabando === "si") {
      // La bandera frena a sincronizarBotones, que si no pisaria el texto
      // quince veces por segundo mientras se guarda.
      grabar.dataset.guardando = "si";
      grabar.textContent = "Terminando...";
      const respuesta = await pedir("/api/terminar", { method: "POST" });
      delete grabar.dataset.guardando;
      // Terminar ya no guarda: muestra lo que grabaste y ahi decidis. El
      // nombre, la descripcion y el BPM van en ese paso.
      if (respuesta.ok) {
        mostrarSesionPendiente(respuesta.pendiente);
      } else {
        avisarQueSeGuardo(respuesta);
      }
    } else {
      document.getElementById("seccion-resumen").hidden = true;
      document.getElementById("aviso-guardado").textContent = "";
      ocultarSesionPendiente();
      await comenzar({ modo: "sesion" });
    }

    grabar.disabled = false;
  });

  // --- Los de la solapa Frases ---
  //
  // Grabar ya no pide nombre: se lo pones al terminar, cuando viste lo que
  // salio. Por eso aca no hay ningun campo que leer.
  document.getElementById("boton-grabar-frase")
    .addEventListener("click", async () => {
      ocultarPendiente();
      limpiarTramos();
      document.getElementById("seccion-comparacion").hidden = true;
      await comenzar({ modo: "frase" });
    });

  document.getElementById("boton-terminar-frase")
    .addEventListener("click", async () => {
      const boton = document.getElementById("boton-terminar-frase");
      boton.disabled = true;
      const respuesta = await pedir("/api/terminar", { method: "POST" });
      boton.disabled = false;
      terminarFrase(respuesta);
    });

  document.getElementById("archivo-frase")
    .addEventListener("change", async (evento) => {
      const archivo = evento.target.files[0];
      evento.target.value = "";               // asi se puede volver a elegir
      if (!archivo) return;

      ocultarPendiente();
      document.getElementById("seccion-comparacion").hidden = true;
      await elegirQueImportar(archivo);
    });
}


/* Un audio puede ser una frase o puede ser una clase entera.
 *
 * Antes de transcribir nada, se busca donde hay armonica. Si hay un solo
 * tramo, el archivo ES la frase y pasa directo a la vista previa. Si hay
 * varios, alguien estuvo hablando en el medio y hay que elegir cual: guardar
 * la clase entera daria una referencia con diez segundos de silencio adentro,
 * contra la que es imposible practicar. */
async function elegirQueImportar(archivo) {
  limpiarTramos();
  avisarFrase("");

  const respuesta = await subir("/api/frases/tramos", archivo, {}, "",
                                "Buscando dónde hay armónica en " + archivo.name);

  if (!respuesta.ok) {
    avisarFrase(respuesta.motivo || "no pude leer ese audio");
    return;
  }

  const tramos = respuesta.tramos || [];

  if (!tramos.length) {
    avisarFrase(respuesta.sirve
      ? "No encontré ningún tramo con armónica en ese audio."
      : respuesta.motivo);
    return;
  }

  if (tramos.length === 1) {
    return importar(archivo, tramos[0]);
  }

  avisarFrase("");
  mostrarTramos(respuesta, archivo);
}


function mostrarTramos(respuesta, archivo) {
  const contenedor = document.getElementById("tramos");
  const tocando = respuesta.tramos
    .reduce((suma, tramo) => suma + tramo.duracion_seg, 0);

  contenedor.innerHTML =
    "<h3>" + respuesta.tramos.length + " tramos con armónica</h3>" +
    "<p>De los " + respuesta.duracion_seg.toFixed(0) + " segundos del audio, " +
    tocando.toFixed(0) + " tienen armónica. El resto es silencio, alguien " +
    "hablando, o la base sola. Escuchá cada uno y elegí cuál importar: la " +
    "grabación entera no sirve de referencia porque los silencios " +
    "también contarían.</p>" +
    respuesta.tramos.map((tramo) =>
      '<div class="tramo" data-fila="' + tramo.numero + '">' +
        '<button class="reproducir" data-escuchar="' + tramo.numero +
          '" title="Escuchar este tramo">▶</button>' +
        '<span class="cuando">' + reloj(tramo.desde_seg) + " a " +
          reloj(tramo.hasta_seg) + "</span>" +
        '<span class="notas">' + tramo.tab.join(" ") +
          (tramo.hay_mas ? " …" : "") + "</span>" +
        '<span class="cuando">' + tramo.notas + " notas</span>" +
        '<button data-tramo="' + tramo.numero + '">Este</button>' +
        // La línea de abajo: se llena mientras suena, y se puede clickear o
        // arrastrar para moverse dentro del tramo.
        '<div class="progreso" data-progreso="' + tramo.numero + '">' +
          '<div class="relleno"></div><div class="perilla"></div></div>' +
        '<span class="problema-audio" hidden></span>' +
      "</div>"
    ).join("");

  contenedor.querySelectorAll("[data-tramo]").forEach((boton) => {
    boton.addEventListener("click", () => {
      const tramo = respuesta.tramos.find(
        (candidato) => String(candidato.numero) === boton.dataset.tramo);
      contenedor.querySelectorAll("button").forEach((otro) => {
        otro.disabled = true;
      });
      importar(archivo, tramo);
    });
  });

  prepararReproductor(archivo, respuesta.tramos, contenedor);
}


function reloj(segundos) {
  const minutos = Math.floor(segundos / 60);
  const resto = (segundos % 60).toFixed(1).padStart(4, "0");
  return minutos + ":" + resto;
}


function limpiarTramos() {
  apagarReproductor();
  document.getElementById("tramos").innerHTML = "";
}


/* ==========================================================================
   Escuchar los tramos

   El archivo que elegiste ya está en el navegador, así que no hace falta
   que el servidor lo devuelva: se reproduce directo desde ahí, arrancando
   en el segundo donde empieza el tramo y frenando donde termina. Chrome y
   Edge decodifican wav, mp3, m4a, ogg y opus sin ayuda; si alguno no puede,
   la fila lo dice en vez de fallar en silencio.

   Hay UN reproductor para todos los tramos: apretar ▶ en otro corta el
   que sonaba. La línea de abajo de cada fila se llena mientras suena y se
   puede clickear o arrastrar para moverse dentro del tramo.
   ========================================================================== */

const reproductor = {
  audio: null,        // el <audio>, creado una sola vez
  url: null,          // la URL local del archivo elegido
  tramos: [],
  contenedor: null,
  actual: null,       // el tramo que suena (o está en pausa)
  animacion: null,    // el requestAnimationFrame que mueve la línea
};


function prepararReproductor(archivo, tramos, contenedor) {
  apagarReproductor();

  if (!reproductor.audio) {
    reproductor.audio = new Audio();
    reproductor.audio.preload = "auto";
    reproductor.audio.addEventListener("error", () => {
      if (!reproductor.actual) return;
      const fila = filaDelTramo(reproductor.actual);
      if (!fila) return;
      const aviso = fila.querySelector(".problema-audio");
      aviso.textContent = "El navegador no puede reproducir este formato. " +
        "Convertilo a .wav o .mp3 y volvé a elegirlo.";
      aviso.hidden = false;
      marcarSonando(null);
    });
    reproductor.audio.addEventListener("timeupdate", alAvanzar);
    // Sin esto, después de pausar y volver, el tiempo seguiría avanzando y
    // la línea se quedaría quieta.
    reproductor.audio.addEventListener("play", moverLaLinea);
  }

  reproductor.url = URL.createObjectURL(archivo);
  reproductor.audio.src = reproductor.url;
  reproductor.tramos = tramos;
  reproductor.contenedor = contenedor;

  contenedor.querySelectorAll("[data-escuchar]").forEach((boton) => {
    boton.addEventListener("click", () => {
      const tramo = tramoNumero(boton.dataset.escuchar);
      if (reproductor.actual === tramo && !reproductor.audio.paused) {
        reproductor.audio.pause();
        boton.textContent = "▶";
        boton.title = "Seguir";
        return;
      }
      reproducirTramo(tramo);
    });
  });

  // La línea: clic o arrastre para moverse dentro del tramo.
  contenedor.querySelectorAll("[data-progreso]").forEach((barra) => {
    const tramo = tramoNumero(barra.dataset.progreso);
    const irA = (evento) => {
      const caja = barra.getBoundingClientRect();
      const fraccion = Math.max(0, Math.min(1, (evento.clientX - caja.left) / caja.width));
      const segundo = tramo.desde_seg + fraccion * (tramo.hasta_seg - tramo.desde_seg);
      if (reproductor.actual !== tramo) {
        reproducirTramo(tramo, segundo);
      } else {
        reproductor.audio.currentTime = segundo;
        pintarLinea(tramo);
      }
    };
    barra.addEventListener("pointerdown", (evento) => {
      barra.setPointerCapture(evento.pointerId);
      barra.classList.add("arrastrando");
      irA(evento);
    });
    barra.addEventListener("pointermove", (evento) => {
      if (barra.classList.contains("arrastrando")) irA(evento);
    });
    ["pointerup", "pointercancel"].forEach((nombre) =>
      barra.addEventListener(nombre, () => barra.classList.remove("arrastrando")));
  });
}


function tramoNumero(numero) {
  return reproductor.tramos.find((t) => String(t.numero) === String(numero));
}


function filaDelTramo(tramo) {
  if (!reproductor.contenedor || !tramo) return null;
  return reproductor.contenedor.querySelector('[data-fila="' + tramo.numero + '"]');
}


/* Arranca un tramo. Si `desde` viene, arranca ahí (es un clic en la línea);
 * si no, desde el principio del tramo, o desde donde lo pausaste. */
async function reproducirTramo(tramo, desde) {
  const audio = reproductor.audio;

  let inicio = desde;
  if (inicio === undefined) {
    const enPausaAdentro = reproductor.actual === tramo && audio.paused &&
      audio.currentTime > tramo.desde_seg && audio.currentTime < tramo.hasta_seg - 0.05;
    inicio = enPausaAdentro ? audio.currentTime : tramo.desde_seg;
  }

  reproductor.actual = tramo;
  marcarSonando(tramo);

  // No se puede saltar a un segundo antes de que el navegador sepa cuánto
  // dura el archivo: la primera vez hay que esperar a que lo lea.
  if (audio.readyState === 0) {
    await new Promise((listo) => {
      audio.addEventListener("loadedmetadata", listo, { once: true });
      audio.addEventListener("error", listo, { once: true });
      audio.load();
    });
    if (audio.readyState === 0) return;                 // no lo pudo leer
  }

  audio.currentTime = inicio;
  try {
    await audio.play();
  } catch (error) {
    // play() rechaza si el navegador no puede con el formato; el evento
    // "error" del audio ya lo avisa en la fila.
  }
}


/* Cada vez que el audio avanza: frena al llegar al final del tramo, y pinta.
 *
 * Va enganchado a `timeupdate`, que el navegador dispara unas cuatro veces
 * por segundo AUNQUE LA PESTAÑA ESTÉ OCULTA. Eso es lo que garantiza que el
 * tramo frene donde tiene que frenar aunque estés mirando otra cosa. Para
 * que la línea se mueva suave se agrega la animación de abajo, que el
 * navegador congela en pestañas ocultas —y por eso no puede ser la única. */
function alAvanzar() {
  const tramo = reproductor.actual;
  const audio = reproductor.audio;
  if (!tramo) return;

  if (!audio.paused && audio.currentTime >= tramo.hasta_seg) {
    audio.pause();
    audio.currentTime = tramo.desde_seg;
    const boton = filaDelTramo(tramo)?.querySelector("[data-escuchar]");
    if (boton) { boton.textContent = "▶"; boton.title = "Escuchar de nuevo"; }
  }
  pintarLinea(tramo);
}


function moverLaLinea() {
  cancelAnimationFrame(reproductor.animacion);
  const paso = () => {
    if (!reproductor.actual || reproductor.audio.paused) return;
    pintarLinea(reproductor.actual);
    reproductor.animacion = requestAnimationFrame(paso);
  };
  reproductor.animacion = requestAnimationFrame(paso);
}


function pintarLinea(tramo) {
  const fila = filaDelTramo(tramo);
  if (!fila) return;
  const largo = tramo.hasta_seg - tramo.desde_seg;
  const fraccion = largo > 0
    ? Math.max(0, Math.min(1, (reproductor.audio.currentTime - tramo.desde_seg) / largo))
    : 0;
  fila.querySelector(".relleno").style.width = fraccion * 100 + "%";
  fila.querySelector(".perilla").style.left = fraccion * 100 + "%";
}


/* Marca la fila que suena y pone el botón en "pausa"; las demás vuelven a ▶. */
function marcarSonando(tramo) {
  if (!reproductor.contenedor) return;
  reproductor.contenedor.querySelectorAll(".tramo").forEach((fila) => {
    const esta = tramo && fila.dataset.fila === String(tramo.numero);
    fila.classList.toggle("sonando", Boolean(esta));
    const boton = fila.querySelector("[data-escuchar]");
    if (boton) {
      boton.textContent = esta ? "❚❚" : "▶";
      boton.title = esta ? "Pausar" : "Escuchar este tramo";
    }
    if (!esta) {
      fila.querySelector(".relleno").style.width = "0%";
      fila.querySelector(".perilla").style.left = "0%";
    }
  });
}


function apagarReproductor() {
  cancelAnimationFrame(reproductor.animacion);
  if (reproductor.audio) {
    reproductor.audio.pause();
    reproductor.audio.removeAttribute("src");
  }
  if (reproductor.url) {
    URL.revokeObjectURL(reproductor.url);
    reproductor.url = null;
  }
  reproductor.actual = null;
  reproductor.tramos = [];
  reproductor.contenedor = null;
}


/* Importar: transcribe el audio (o el tramo elegido) y lo deja pendiente.
 * No guarda nada. Lo que salio aparece en la misma vista previa que una
 * frase grabada con el microfono, y ahi le pones nombre. */
async function importar(archivo, tramo) {
  limpiarTramos();
  avisarFrase("");

  const extra = {};
  if (tramo) {
    extra.desde = tramo.desde_seg;
    extra.hasta = tramo.hasta_seg;
  }

  const respuesta = await subir("/api/frases/importar", archivo, extra, "",
                                "Transcribiendo " + archivo.name +
                                (tramo ? " (" + reloj(tramo.desde_seg) + " a " +
                                         reloj(tramo.hasta_seg) + ")" : ""));

  if (!respuesta.ok) {
    avisarFrase(respuesta.motivo || "no pude importar ese audio");
    return;
  }

  avisarFrase("");
  mostrarPendiente(respuesta.pendiente);
}


/* Sube un archivo. Las opciones van en la URL y los bytes crudos en el
 * cuerpo: es lo mismo que hace multipart pero sin nada que parsear del otro
 * lado. Va tambien el nombre del archivo: ffmpeg necesita la extension para
 * convertirlo, y el servidor lo usa como nombre sugerido de la frase.
 *
 * `nombre` se usa solo para comparar un intento contra una frase guardada:
 * al importar va vacio, porque el nombre se pone despues.
 *
 * `queHace` es lo que dice el cartel de espera mientras el servidor trabaja.
 * El cartel vive aca y no en cada llamada para que ninguna subida nueva
 * pueda olvidarselo: una clase entera tarda un minuto y sin cartel parece
 * que la app se colgo. */
async function subir(ruta, archivo, extra, nombre, queHace) {
  const partes = ["nombre=" + encodeURIComponent(nombre || ""),
                  "archivo=" + encodeURIComponent(archivo.name || "")];

  const tonalidad = document.getElementById("tonalidad-frase").value;
  if (tonalidad) partes.push("tonalidad=" + encodeURIComponent(tonalidad));

  Object.entries(extra || {}).forEach(([clave, valor]) =>
    partes.push(clave + "=" + encodeURIComponent(valor)));

  mostrarEspera(queHace || ("Analizando " + archivo.name));
  try {
    const respuesta = await fetch(ruta + "?" + partes.join("&"),
                                  { method: "POST", body: archivo });
    return await respuesta.json();
  } catch (error) {
    return { ok: false, motivo: "se corto la conexion con el servidor: " + error.message };
  } finally {
    ocultarEspera();
  }
}


/* ==========================================================================
   El cartel de espera

   Mientras esta puesto, los botones que podrian pisar lo que se esta
   analizando quedan apagados. `esperando` lo lee sincronizarBotones, que
   corre con cada latido del estado en vivo: si no lo supiera, volveria a
   prenderlos al segundo.
   ========================================================================== */

let esperando = false;
let relojDeEspera = null;

function mostrarEspera(queHace) {
  esperando = true;
  const cartel = document.getElementById("esperando");
  document.getElementById("esperando-que").textContent = queHace;

  const arranque = Date.now();
  const reloj = document.getElementById("esperando-reloj");
  const marcar = () => {
    const segundos = Math.floor((Date.now() - arranque) / 1000);
    reloj.textContent = Math.floor(segundos / 60) + ":" +
      String(segundos % 60).padStart(2, "0");
  };
  marcar();
  clearInterval(relojDeEspera);
  relojDeEspera = setInterval(marcar, 1000);

  cartel.hidden = false;
  cartel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  apagarLoQueSePuedeApretar(true);
}


function ocultarEspera() {
  esperando = false;
  clearInterval(relojDeEspera);
  relojDeEspera = null;
  document.getElementById("esperando").hidden = true;
  apagarLoQueSePuedeApretar(false);
}


/* Los controles de la solapa Frases que no tiene sentido tocar mientras se
 * graba o se analiza algo. Lo usan el cartel de espera y sincronizarBotones. */
function apagarLoQueSePuedeApretar(ocupado) {
  document.getElementById("boton-grabar-frase").disabled = ocupado;
  document.getElementById("tonalidad-frase").disabled = ocupado;

  document.querySelectorAll("#lista-frases button, #tramos button")
    .forEach((boton) => { boton.disabled = ocupado; });

  // Un <label> no se puede deshabilitar: se apaga el <input> que tiene adentro
  // y se lo pinta de apagado para que se note.
  document.querySelectorAll(".como-boton, .frase label.audio")
    .forEach((etiqueta) => {
      etiqueta.classList.toggle("apagado", ocupado);
      const entrada = etiqueta.querySelector("input");
      if (entrada) entrada.disabled = ocupado;
    });
}


/* Las armonicas que la app conoce. Por defecto queda la que tenes puesta,
 * porque la mayoria de las veces es la correcta. */
function llenarTonalidades() {
  const selector = document.getElementById("tonalidad-frase");
  selector.innerHTML = (inicio.tonalidades || [inicio.tonalidad])
    .map((clave) => '<option value="' + clave + '"' +
         (clave === inicio.tonalidad ? " selected" : "") + ">" + clave + "</option>")
    .join("");
}


async function comenzar(cuerpo) {
  const respuesta = await pedir("/api/comenzar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
  if (!respuesta.ok) {
    avisarFrase(respuesta.motivo || "no pude empezar");
  }
  return respuesta;
}


function avisarFrase(texto) {
  document.getElementById("estado-frase").textContent = texto;
}


/* ==========================================================================
   El estado en vivo
   ========================================================================== */

function conectarEnVivo() {
  fuente = new EventSource("/api/vivo");
  fuente.onmessage = (mensaje) => dibujarEstado(JSON.parse(mensaje.data));
}


function dibujarEstado(estado) {
  dibujarMedidor(estado);
  resaltarAgujero(estado.nota, estado.cents);
  dibujarTab(estado.tab);
  dibujarNivel(estado);
  sincronizarBotones(estado);

  const minutos = Math.floor(estado.segundos / 60);
  const segundos = String(Math.floor(estado.segundos % 60)).padStart(2, "0");
  // El contador es de la GRABACION, no de estar escuchando: si contara
  // siempre, diria "cuatro mil notas" por haber dejado la app abierta.
  document.getElementById("contadores").textContent = estado.grabando
    ? `● ${estado.cantidad_notas} notas · ${minutos}:${segundos}`
    : "";
}


function dibujarMedidor(estado) {
  const grande = document.getElementById("nota-grande");
  const nombre = document.getElementById("nombre-nota");
  const cents = document.getElementById("cents");
  const punto = document.getElementById("punto");
  const pista = document.getElementById("pista");
  const direccion = document.getElementById("direccion-nota");

  if (!estado.nota) {
    grande.textContent = "—";
    grande.className = "";
    nombre.textContent = "";
    direccion.textContent = "";
    direccion.className = "";
    cents.textContent = estado.escuchando ? "esperando una nota" : "sin nota";
    cents.className = "";
    punto.setAttribute("cx", 200);
    punto.style.fill = "var(--tenue)";
    pista.textContent = "";
    return;
  }

  grande.textContent = estado.nota.tab;
  nombre.textContent = estado.nota.nombre;

  // Fuera de escala NO es un error: la tercera mayor sobre un acorde
  // dominante está afuera y es lo que suena a blues. Se marca distinto, no
  // se reprocha.
  // El color dice la dirección, igual que en la armónica de abajo. Fuera
  // de escala gana: es lo que hay que notar.
  grande.className = estado.nota.en_escala === false
    ? "fuera-de-escala" : (estado.nota.direccion || "");
  direccion.textContent = estado.nota.direccion || "";
  direccion.className = estado.nota.direccion || "";
  pista.textContent = estado.nota.en_escala === false
    ? "fuera de la escala de referencia (no es un error)" : "";

  // La escala del medidor: 400 unidades de ancho para 100 cents.
  const posicion = Math.max(10, Math.min(390, 200 + estado.cents * 4));
  punto.setAttribute("cx", posicion);

  const magnitud = Math.abs(estado.cents);
  const clase = magnitud <= TOLERANCIA ? "afinado"
              : magnitud <= 25 ? "cerca" : "lejos";
  const color = magnitud <= TOLERANCIA ? "var(--verde)"
              : magnitud <= 25 ? "var(--amarillo)" : "var(--rojo)";

  punto.style.fill = color;
  cents.className = clase;
  cents.textContent = (estado.cents > 0 ? "+" : "") +
                      estado.cents.toFixed(0) + " cents";
}


function ajustarZonaBuena() {
  // La franja verde del medidor tiene que coincidir con la tolerancia real.
  const zona = document.getElementById("zona-buena");
  const ancho = TOLERANCIA * 4 * 2;
  zona.setAttribute("x", 200 - ancho / 2);
  zona.setAttribute("width", ancho);
}


/* ==========================================================================
   El diagrama de la armónica
   ========================================================================== */

/* La armónica, agujeros 1→10 de izquierda a derecha, como el instrumento.
 *
 * Cada agujero es una columna: arriba lo soplado, abajo lo aspirado, el
 * número en el medio, y los bends apilados HACIA AFUERA. Los huecos se
 * dibujan igual, vacíos: sin ellos las columnas no quedarían alineadas y un
 * bend dejaría de leerse como un movimiento vertical.
 *
 * Hay dos diagramas con los mismos datos: el grande de En vivo y la
 * miniatura del cartel de grabar una frase. Se dibujan con la misma función y
 * se iluminan los dos a la vez. */
let diagramas = [];

function dibujarDiagrama(filas) {
  diagramas = [];
  const grande = document.getElementById("diagrama");
  if (grande) diagramas.push(armarDiagrama(grande, filas, false));
  const mini = document.getElementById("diagrama-mini");
  if (mini) diagramas.push(armarDiagrama(mini, filas, true));
}


function armarDiagrama(contenedor, filas, compacto) {
  contenedor.innerHTML = "";
  contenedor.classList.toggle("diagrama-mini", compacto);
  const registro = { celdas: {}, columnas: {}, celdaResaltada: null, columnaResaltada: null };

  if (!compacto) {
    const rotulos = document.createElement("div");
    rotulos.className = "columna rotulos";
    ["bend", "bend", "soplado", "", "aspirado", "bend", "bend", "bend"].forEach((texto) => {
      const rotulo = document.createElement("div");
      rotulo.className = "rotulo";
      rotulo.textContent = texto;
      rotulos.appendChild(rotulo);
    });
    contenedor.appendChild(rotulos);
  }

  filas.forEach((fila) => {
    const columna = document.createElement("div");
    columna.className = "columna";

    // De arriba hacia abajo: los bends soplados (afuera), el soplado, el
    // número, el aspirado, los bends aspirados (afuera). El servidor manda
    // el lado soplado de adentro hacia afuera y el aspirado de afuera hacia
    // adentro, así que uno se da vuelta y el otro también.
    fila.soplado.slice().reverse().forEach((celda) =>
      columna.appendChild(dibujarCelda(celda, registro, compacto)));

    const numero = document.createElement("div");
    numero.className = "numero-agujero";
    numero.textContent = fila.agujero;
    columna.appendChild(numero);

    fila.aspirado.slice().reverse().forEach((celda) =>
      columna.appendChild(dibujarCelda(celda, registro, compacto)));

    // La aguja del bend vive dentro de la columna y se mueve dentro de ella.
    const aguja = document.createElement("div");
    aguja.className = "aguja-bend";
    aguja.hidden = true;
    columna.appendChild(aguja);

    registro.columnas[fila.agujero] = { elemento: columna, aguja: aguja };
    contenedor.appendChild(columna);
  });

  return registro;
}


function dibujarCelda(celda, registro, compacto) {
  const caja = document.createElement("div");
  if (!celda) {
    caja.className = "celda vacia";
    caja.innerHTML = "&nbsp;";
    return caja;
  }
  caja.className = "celda " + celda.direccion +
    (celda.bend ? " bend" : "") + (celda.en_escala ? " en-escala" : "");
  caja.innerHTML = celda.tab +
    (compacto ? "" : '<span class="nombre">' + celda.nombre + "</span>");
  registro.celdas[clave(celda)] = caja;
  return caja;
}


function clave(nota) {
  return nota.agujero + "|" + nota.direccion + "|" + nota.bend;
}


function resaltarAgujero(nota, cents) {
  diagramas.forEach((diagrama) => resaltarEn(diagrama, nota, cents));
}


function resaltarEn(diagrama, nota, cents) {
  const nueva = nota ? diagrama.celdas[clave(nota)] : null;
  if (nueva !== diagrama.celdaResaltada) {
    if (diagrama.celdaResaltada) diagrama.celdaResaltada.classList.remove("actual");
    if (nueva) nueva.classList.add("actual");
    diagrama.celdaResaltada = nueva;
  }

  const columna = nota ? diagrama.columnas[nota.agujero] : null;
  if (columna !== diagrama.columnaResaltada) {
    if (diagrama.columnaResaltada) {
      diagrama.columnaResaltada.elemento.classList.remove("sonando", "soplado", "aspirado");
      diagrama.columnaResaltada.aguja.hidden = true;
    }
    if (columna) columna.elemento.classList.add("sonando", nota.direccion);
    diagrama.columnaResaltada = columna;
  }

  moverAguja(nota, cents, nueva, columna);
}


/* Dónde poner la línea que marca tu afinación.
 *
 * Dos celdas vecinas de la misma columna están exactamente a un semitono, o
 * sea a cien cents. La línea se corre desde el centro de la celda actual una
 * fracción de celda igual a los cents de desvío.
 *
 * EL SIGNO ES EL MISMO PARA LOS DOS LADOS, Y ESA ES LA GRACIA DE ESTA
 * DISPOSICIÓN: un bend es bajar de tono, y bajar de tono es alejarse del
 * número, hacia afuera. Del lado aspirado, afuera es abajo; del lado soplado,
 * afuera es arriba. Estar bajo de afinación siempre corre la línea hacia el
 * bend siguiente. */
function moverAguja(nota, cents, celda, columna) {
  if (!nota || !celda || !columna) {
    if (columna) columna.aguja.hidden = true;
    return;
  }

  const base = columna.elemento.getBoundingClientRect();
  if (!base.height) return;
  const caja = celda.getBoundingClientRect();
  const centro = caja.top - base.top + caja.height / 2;

  const haciaAbajo = nota.direccion === "aspirado";
  const corrimiento = (cents / 100) * (caja.height + 4) * (haciaAbajo ? -1 : 1);

  columna.aguja.hidden = false;
  columna.aguja.style.top = (centro + corrimiento) / base.height * 100 + "%";
  columna.aguja.classList.toggle("afinada", Math.abs(cents) <= TOLERANCIA);
}


function dibujarTab(tabs) {
  const contenedor = document.getElementById("tab");
  if (!tabs || !tabs.length) {
    contenedor.textContent = "—";
    return;
  }
  contenedor.innerHTML = tabs
    .map((tab, indice) => {
      // La tab viene con flecha (↓2) o con guion (-2), según la notación.
      const clase = (/^[↓-]/.test(tab) ? "aspirado" : "soplado") +
                    (indice === tabs.length - 1 ? " ultima" : "");
      return '<span class="' + clase + '">' + tab + "</span>";
    })
    .join(" ");
}


/* ==========================================================================
   La sesion pendiente: lo que grabaste, y la decision

   Es la misma idea que la frase pendiente. Al terminar ves lo que salio y
   recien ahi le pones nombre y descripcion. Y aca va la pregunta que solo
   tiene sentido despues de tocar: sobre que base estabas, a cuantos BPM.
   ========================================================================== */

function mostrarSesionPendiente(pendiente) {
  const panel = document.getElementById("sesion-pendiente");
  if (!pendiente) {
    panel.hidden = true;
    return;
  }

  document.getElementById("sesion-tab").innerHTML =
    pendiente.tab.map((t) => escapar(t)).join(" ") + (pendiente.hay_mas ? " …" : "");
  document.getElementById("sesion-datos").textContent =
    pendiente.notas + " notas · " + pendiente.duracion_seg.toFixed(0) +
    " s · armónica en " + pendiente.tonalidad +
    (pendiente.posicion ? " · " + pendiente.posicion + "ª posición" : "");

  document.getElementById("sesion-titulo").value = "";
  document.getElementById("sesion-descripcion").value = "";
  document.getElementById("sesion-estado").textContent = "";
  // El BPM se deja como estaba: si venis tocando sobre la misma base, no
  // tenes que escribirlo cada vez.
  document.getElementById("sesion-subdivision").value =
    String(inicio.subdivision_ritmo || 2);

  panel.hidden = false;
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  document.getElementById("sesion-titulo").focus();
}


function ocultarSesionPendiente() {
  document.getElementById("sesion-pendiente").hidden = true;
}


/* Al arrancar: si habia una sesion sin guardar, se vuelve a mostrar. */
async function recuperarSesionPendiente() {
  const datos = await pedir("/api/sesiones/pendiente");
  if (datos.pendiente) mostrarSesionPendiente(datos.pendiente);
}


function configurarSesionPendiente() {
  document.getElementById("sesion-guardar").addEventListener("click", guardarSesion);
  document.getElementById("sesion-descartar").addEventListener("click", async () => {
    await pedir("/api/sesiones/descartar", { method: "POST" });
    ocultarSesionPendiente();
    const aviso = document.getElementById("aviso-guardado");
    aviso.className = "problema";
    aviso.textContent = "Descartada.";
    setTimeout(() => { aviso.textContent = ""; }, 6000);
  });
  ["sesion-titulo", "sesion-bpm"].forEach((id) => {
    document.getElementById(id).addEventListener("keydown", (evento) => {
      if (evento.key === "Enter") guardarSesion();
    });
  });
}


async function guardarSesion() {
  const estado = document.getElementById("sesion-estado");
  const bpm = document.getElementById("sesion-bpm").value.trim();
  estado.textContent = "Guardando...";

  const respuesta = await pedir("/api/sesiones/guardar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      titulo: document.getElementById("sesion-titulo").value,
      comentario: document.getElementById("sesion-descripcion").value,
      bpm: bpm ? Number(bpm) : null,
      subdivision: Number(document.getElementById("sesion-subdivision").value),
    }),
  });

  if (!respuesta.ok) {
    estado.textContent = respuesta.motivo || "no se pudo guardar";
    return;
  }

  ocultarSesionPendiente();
  mostrarResumen(respuesta);
  avisarQueSeGuardo(respuesta);
}


/* El bloque de ritmo del resumen. Solo existe si diste un BPM.
 *
 * `confiable` es lo que decide como se lee: si la grilla no explica lo
 * tocado, los numeros se muestran tachados de sentido, no de diagnostico.
 * Preferimos decir cuando no sabemos. */
function htmlDeRitmo(r) {
  let html = "<h2>Ritmo</h2>";
  html += "<p class='ayuda'>Base a " + r.bpm + " BPM, midiendo contra " +
          escapar(r.figura) + ". " + r.notas_medidas + " notas medidas.</p>";

  if (!r.confiable) {
    html += '<div class="aviso"><strong>La grilla no explica lo que tocaste</strong>' +
      (r.ajuste_vs_azar !== null
        ? " (ajuste " + r.ajuste_vs_azar.toFixed(2) + ", donde 1.00 es azar puro)."
        : ".") +
      " Los números de abajo NO son un diagnóstico: puede ser que el BPM o la " +
      "figura estén mal, o que lo que tocaste no sea métrico (un solo con " +
      "fraseo libre, por ejemplo). Para medir ritmo de verdad sirve una escala " +
      "en negras o corcheas parejas sobre la base.</div>";
  }

  const clase = r.confiable ? "" : " tenue";
  html += '<table class="ritmo' + clase + '"><tbody>' +
    "<tr><td>Dispersión</td><td class='numero'><strong>" + r.dispersion_ms +
      " ms</strong></td><td class='ayuda'>el número a bajar: cuánto varía nota a nota</td></tr>" +
    "<tr><td>Promedio</td><td class='numero'>" + (r.sesgo_ms > 0 ? "+" : "") + r.sesgo_ms +
      " ms</td><td class='ayuda'>" + (r.sesgo_ms < 0 ? "te adelantás" : "llegás tarde") + "</td></tr>" +
    "<tr><td>A tiempo</td><td class='numero'>" + r.a_tiempo_pct +
      " %</td><td class='ayuda'>dentro de " + r.tolerancia_ms + " ms</td></tr>" +
    "</tbody></table>";

  (r.diagnostico || []).forEach((frase) => {
    html += '<div class="hallazgo"><p class="accion">' + escapar(frase) + "</p></div>";
  });
  return html;
}


/* ==========================================================================
   El resumen al terminar
   ========================================================================== */

/* Decir, ARRIBA Y AL LADO DEL BOTON, que paso al guardar.
 *
 * El resumen se dibuja al final de la pagina, despues de las diez filas del
 * diagrama. Apretabas Terminar y guardar, se guardaba bien, y no pasaba nada
 * visible: la confirmacion estaba a dos pantallas de distancia. */
function avisarQueSeGuardo(respuesta) {
  const aviso = document.getElementById("aviso-guardado");
  const archivos = Object.keys(respuesta.guardado || {}).length;

  if (!respuesta.ok) {
    aviso.className = "problema";
    aviso.textContent = respuesta.motivo || "no se pudo guardar";
  } else if (!archivos) {
    aviso.className = "problema";
    aviso.textContent = "No se guardó nada: no se reconoció ninguna nota.";
  } else {
    aviso.className = "";
    const notas = (respuesta.resumen || {}).notas || 0;
    aviso.textContent = "Guardado en sesiones/ — " + notas + " notas.";
    // Y llevamos la vista al resumen, que es lo que queres leer ahora.
    document.getElementById("seccion-resumen")
      .scrollIntoView({ behavior: "smooth", block: "start" });
  }

  setTimeout(() => { aviso.textContent = ""; }, 12000);
}


function mostrarResumen(respuesta) {
  const seccion = document.getElementById("seccion-resumen");
  const contenedor = document.getElementById("resumen");
  const datos = respuesta.resumen || {};

  if (!datos.hay) {
    contenedor.innerHTML = '<div class="aviso">No se detectó ninguna nota. ' +
      "Si el micrófono no engancha, corré <code>python main.py --calibrar</code> " +
      "para medir el ruido de tu habitación.</div>";
    seccion.hidden = false;
    return;
  }

  let html = "<p class='ayuda'>" + datos.notas + " notas en " +
             datos.duracion_seg.toFixed(0) + " segundos";
  if (datos.afinacion !== null && datos.afinacion !== undefined) {
    html += " · tu armónica midió " +
            (datos.afinacion > 0 ? "+" : "") + datos.afinacion.toFixed(0) + " cents";
  }
  html += "</p>";

  datos.hallazgos.forEach((hallazgo, numero) => {
    html += '<div class="hallazgo">' +
      "<h3>" + (numero + 1) + ". " + hallazgo.titulo +
      ' <span class="ayuda">(confianza ' + hallazgo.confianza + ")</span></h3>" +
      "<p>" + hallazgo.evidencia + "</p>" +
      '<p class="accion">' + hallazgo.accion + "</p></div>";
  });

  if (datos.pares && datos.pares.length) {
    html += "<h2>Tus pares más repetidos</h2><table><tbody>";
    datos.pares.forEach((par) => {
      html += "<tr><td>" + par.de + " → " + par.a +
              '</td><td class="numero">' + par.veces + " veces</td></tr>";
    });
    html += "</tbody></table>";
  }

  (datos.sin_medir || []).forEach((texto) => {
    html += '<div class="aviso">' + texto + "</div>";
  });

  if (respuesta.ritmo) html += htmlDeRitmo(respuesta.ritmo);

  if (respuesta.guardado && Object.keys(respuesta.guardado).length) {
    html += "<p class='ayuda'>Guardado en sesiones/: " +
            Object.values(respuesta.guardado).join(", ") + "</p>";
  }

  contenedor.innerHTML = html;
  seccion.hidden = false;
}


/* ==========================================================================
   El historial
   ========================================================================== */

async function cargarHistorial() {
  const datos = await pedir("/api/historial");
  dibujarBends(datos.bends);
  dibujarSesiones(datos.sesiones);
}


function dibujarBends(bends) {
  const contenedor = document.getElementById("grafico-bends");
  const nombres = Object.keys(bends);

  if (!nombres.length) {
    contenedor.innerHTML = '<div class="aviso">Todavía no hay suficientes ' +
      "sesiones para ver una tendencia. Hacen falta al menos dos sesiones " +
      "donde aparezca el mismo bend.</div>";
    return;
  }

  contenedor.innerHTML = nombres.map((tab) => graficoDeBend(tab, bends[tab])).join("");
}


function graficoDeBend(tab, puntos) {
  const ancho = 640, alto = 150;
  const margen = { izq: 44, der: 12, arriba: 12, abajo: 26 };
  const util = { ancho: ancho - margen.izq - margen.der,
                 alto: alto - margen.arriba - margen.abajo };

  // La escala vertical: 60 cents para cada lado, o más si algún punto se pasa.
  const tope = Math.max(60, ...puntos.map((p) => Math.abs(p.cents) + 10));
  const aY = (cents) => margen.arriba + util.alto / 2 - (cents / tope) * (util.alto / 2);
  const aX = (indice) => puntos.length === 1
    ? margen.izq + util.ancho / 2
    : margen.izq + (indice / (puntos.length - 1)) * util.ancho;

  const altoZona = (TOLERANCIA / tope) * util.alto;
  const linea = puntos.map((p, i) => aX(i) + "," + aY(p.cents)).join(" ");

  const circulos = puntos.map((p, i) => {
    const color = Math.abs(p.cents) <= TOLERANCIA ? "var(--verde)"
                : Math.abs(p.cents) <= 25 ? "var(--amarillo)" : "var(--rojo)";
    return '<circle cx="' + aX(i) + '" cy="' + aY(p.cents) + '" r="5" fill="' +
           color + '"><title>' + p.fecha + ": " + p.cents.toFixed(0) +
           " cents (" + p.veces + " veces)</title></circle>";
  }).join("");

  const primero = puntos[0].cents;
  const ultimo = puntos[puntos.length - 1].cents;
  const cambio = Math.abs(ultimo) - Math.abs(primero);
  let veredicto;
  if (puntos.length < 3) {
    veredicto = "hacen falta más sesiones para ver una tendencia";
  } else if (cambio < -8) {
    veredicto = "mejorando: " + Math.abs(cambio).toFixed(0) + " cents más cerca";
  } else if (cambio > 8) {
    veredicto = "empeorando: " + cambio.toFixed(0) + " cents más lejos";
  } else {
    veredicto = "sin cambios";
  }

  return '<div class="grafico-bend">' +
    "<h3>" + tab + "</h3>" +
    '<div class="resumen-linea">' + puntos.length + " sesiones · último: " +
    (ultimo > 0 ? "+" : "") + ultimo.toFixed(0) + " cents · " + veredicto + "</div>" +
    '<svg viewBox="0 0 ' + ancho + " " + alto + '">' +
      '<rect x="' + margen.izq + '" y="' + (aY(0) - altoZona) +
        '" width="' + util.ancho + '" height="' + (altoZona * 2) +
        '" fill="rgba(78,201,122,0.13)"/>' +
      '<line x1="' + margen.izq + '" y1="' + aY(0) + '" x2="' + (ancho - margen.der) +
        '" y2="' + aY(0) + '" stroke="var(--tenue)" stroke-width="1"/>' +
      '<text x="8" y="' + (aY(tope) + 12) + '" fill="var(--tenue)" font-size="11">+' +
        tope.toFixed(0) + "</text>" +
      '<text x="8" y="' + (aY(0) + 4) + '" fill="var(--tenue)" font-size="11">0</text>' +
      '<text x="8" y="' + aY(-tope) + '" fill="var(--tenue)" font-size="11">-' +
        tope.toFixed(0) + "</text>" +
      '<polyline points="' + linea +
        '" fill="none" stroke="var(--azul)" stroke-width="2"/>' +
      circulos +
    "</svg></div>";
}


function dibujarSesiones(sesiones) {
  const contenedor = document.getElementById("tabla-sesiones");

  if (!sesiones || !sesiones.length) {
    contenedor.innerHTML = '<div class="aviso">Todavía no guardaste ninguna ' +
      "sesión.</div>";
    return;
  }

  let html = "<table><thead><tr><th>Fecha</th><th>Qué</th><th>Armónica</th>" +
             "<th>Posición</th><th class='numero'>Notas</th>" +
             "<th class='numero'>Minutos</th><th class='numero'>Afinación</th>" +
             "</tr></thead><tbody>";

  sesiones.slice().reverse().forEach((sesion) => {
    const afinacion = sesion.afinacion === null || sesion.afinacion === undefined
      ? "—"
      : (sesion.afinacion > 0 ? "+" : "") + sesion.afinacion.toFixed(0);
    html += "<tr><td>" + (sesion.fecha || "—") + "</td>" +
            "<td>" + escapar(sesion.titulo || "") + "</td>" +
            "<td>" + (sesion.tonalidad || "—") + "</td>" +
            "<td>" + (sesion.posicion ? sesion.posicion + "ª" : "—") + "</td>" +
            '<td class="numero">' + sesion.notas + "</td>" +
            '<td class="numero">' + sesion.duracion_min + "</td>" +
            '<td class="numero">' + afinacion + "</td></tr>";
  });

  contenedor.innerHTML = html + "</tbody></table>";
}


/* ==========================================================================
   Las frases

   El servidor es el que sabe si esta escuchando y en que modo. Los botones
   se dibujan a partir de eso y no de lo que hizo el ultimo clic: asi dos
   pestanas abiertas, o un modo que arranco desde la terminal, no dejan la
   pantalla mintiendo.
   ========================================================================== */

function sincronizarBotones(estado) {
  const grabando = estado.grabando;
  const modo = estado.modo || "sesion";
  const enFrase = grabando && (modo === "frase" || modo === "practicar");
  const enSesion = grabando && modo === "sesion";

  // El boton de grabar cuenta las dos cosas: si esta grabando y si lo que
  // esta grabando es una sesion o una frase. Grabando una frase, este boton
  // no puede hacer nada: el que termina es el de la solapa Frases.
  const grabar = document.getElementById("boton-grabar");
  grabar.dataset.grabando = enSesion ? "si" : "no";
  grabar.disabled = grabando && !enSesion;
  if (grabar.dataset.guardando !== "si") {
    grabar.textContent = enSesion ? "Terminar" : "Grabar esta sesión";
  }

  document.getElementById("boton-terminar-frase").hidden = !enFrase;
  apagarLoQueSePuedeApretar(grabando || esperando);

  dibujarCartelDeFrase(estado, enFrase);

  if (enFrase) {
    avisarFrase(modo === "frase"
      ? "Cuando termines, dale a Terminar."
      : "Tocala igual que la referencia y dale a Terminar.");
  } else if (grabando) {
    avisarFrase(AVISO_SESION);
  } else if (document.getElementById("estado-frase").textContent === AVISO_SESION) {
    // El aviso valia mientras la sesion estaba andando. Si sigue ahi
    // despues de terminar, dice una mentira: se limpia solo.
    avisarFrase("");
  }
}


const AVISO_SESION = "Hay una sesi\u00f3n en vivo andando. Terminala primero.";


/* El cartel grande de "te estoy escuchando", en la solapa Frases.
 *
 * Una frase dura cuatro segundos. Antes lo unico que pasaba al apretar Grabar
 * era que aparecia un boton chico y una linea de texto: para cuando lo leias,
 * ya habias terminado de tocar. Ahora hay un punto rojo latiendo, el reloj, la
 * barra de nivel y la tablatura saliendo en vivo. */
function dibujarCartelDeFrase(estado, enFrase) {
  const cartel = document.getElementById("grabando-frase");
  if (!cartel) return;

  cartel.hidden = !enFrase;
  if (!enFrase) return;

  document.getElementById("que-se-graba").textContent =
    estado.modo === "frase"
      ? "Grabando una frase"
      : "Practicando «" + estado.nombre_frase + "»";

  const minutos = Math.floor(estado.segundos / 60);
  const segundos = String(Math.floor(estado.segundos % 60)).padStart(2, "0");
  document.getElementById("reloj-frase").textContent =
    estado.cantidad_notas + " notas \u00b7 " + minutos + ":" + segundos;

  const tab = document.getElementById("tab-frase");
  tab.textContent = (estado.tab || []).length
    ? estado.tab.join(" ")
    : "Toc\u00e1 la frase\u2026";
}


/* ==========================================================================
   La frase pendiente: lo que salio, y la decision

   Aparece al terminar de grabar o de importar. Lo grabado queda en memoria
   del servidor hasta que elijas guardarlo o tirarlo; si recargas la pagina,
   se vuelve a pedir y sigue ahi.
   ========================================================================== */

const LISTA_NUEVA = "nueva";     // un valor que ningun nombre real va a tener

function mostrarPendiente(pendiente) {
  const panel = document.getElementById("pendiente");
  if (!pendiente) {
    panel.hidden = true;
    return;
  }

  document.getElementById("pendiente-titulo").textContent =
    pendiente.origen === "archivo" ? "Esto es lo que se importó" : "Esto es lo que salió";

  document.getElementById("pendiente-tab").innerHTML =
    pendiente.tab.map((t) => escapar(t)).join(" ");

  document.getElementById("pendiente-datos").textContent =
    pendiente.notas + " notas · " + pendiente.duracion_seg.toFixed(1) +
    " s · armónica en " + pendiente.tonalidad +
    (pendiente.posicion ? " · " + pendiente.posicion + "ª posición" : "");

  // El control de monofonia, si dudo, se muestra pero no manda: la tablatura
  // esta a la vista y el que reconoce la frase sos vos.
  const aviso = document.getElementById("pendiente-aviso");
  const textos = [];
  if (!pendiente.sirve && pendiente.motivo) textos.push(pendiente.motivo);
  (pendiente.avisos || []).forEach((a) => textos.push(a));
  aviso.hidden = !textos.length;
  aviso.textContent = textos.join(" ");

  const nombre = document.getElementById("pendiente-nombre");
  nombre.value = pendiente.nombre_sugerido || "";
  document.getElementById("pendiente-descripcion").value = "";
  document.getElementById("pendiente-estado").textContent = "";
  document.getElementById("pendiente-lista-nueva").hidden = true;
  document.getElementById("pendiente-lista-nueva").value = "";

  llenarSelectorDeListas("pendiente-lista", listaElegida, true);

  panel.hidden = false;
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  nombre.focus();
  nombre.select();
}


function ocultarPendiente() {
  document.getElementById("pendiente").hidden = true;
}


/* Al arrancar la pagina: si habia una frase sin guardar, se vuelve a
 * mostrar. Lo grabado no se pierde por recargar. */
async function recuperarPendiente() {
  const datos = await pedir("/api/frases/pendiente");
  if (datos.pendiente) {
    await cargarFrases();          // para tener las listas en el selector
    mostrarPendiente(datos.pendiente);
  }
}


/* Un <select> de listas. Con `conNueva`, la ultima opcion es "nueva lista…"
 * y al elegirla aparece un campo para escribir el nombre. */
function llenarSelectorDeListas(id, elegida, conNueva) {
  const selector = document.getElementById(id);
  const opciones = ['<option value="">ninguna</option>']
    .concat(ultimasListas.map((l) =>
      '<option value="' + escapar(l.nombre) + '"' +
      (l.nombre === elegida ? " selected" : "") + ">" +
      escapar(l.nombre) + "</option>"));
  if (conNueva) opciones.push('<option value="' + LISTA_NUEVA + '">nueva lista…</option>');
  selector.innerHTML = opciones.join("");
}


function listaElegidaEn(idSelector, idCampoNuevo) {
  const valor = document.getElementById(idSelector).value;
  if (valor === LISTA_NUEVA) {
    return document.getElementById(idCampoNuevo).value.trim();
  }
  return valor;
}


function configurarPendiente() {
  const selector = document.getElementById("pendiente-lista");
  const campoNuevo = document.getElementById("pendiente-lista-nueva");

  selector.addEventListener("change", () => {
    campoNuevo.hidden = selector.value !== LISTA_NUEVA;
    if (!campoNuevo.hidden) campoNuevo.focus();
  });

  document.getElementById("pendiente-descartar").addEventListener("click", async () => {
    await pedir("/api/frases/descartar", { method: "POST" });
    ocultarPendiente();
    avisarFrase("Descartada. Grabá otra cuando quieras.");
  });

  document.getElementById("pendiente-guardar").addEventListener("click", () => guardarPendiente(false));

  // Enter en el nombre guarda: es lo que uno espera de un formulario de una linea.
  document.getElementById("pendiente-nombre").addEventListener("keydown", (evento) => {
    if (evento.key === "Enter") guardarPendiente(false);
  });
}


async function guardarPendiente(reemplazar) {
  const estado = document.getElementById("pendiente-estado");
  const nombre = document.getElementById("pendiente-nombre").value.trim();
  if (!nombre) {
    estado.textContent = "Ponele un nombre.";
    document.getElementById("pendiente-nombre").focus();
    return;
  }

  estado.textContent = "Guardando...";
  const respuesta = await pedir("/api/frases/guardar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nombre: nombre,
      comentario: document.getElementById("pendiente-descripcion").value,
      lista: listaElegidaEn("pendiente-lista", "pendiente-lista-nueva"),
      reemplazar: reemplazar,
    }),
  });

  if (!respuesta.ok) {
    if (respuesta.repetida && confirm("Ya hay una frase que se llama «" + nombre +
                                      "». ¿La reemplazo?")) {
      return guardarPendiente(true);
    }
    estado.textContent = respuesta.motivo || "no se pudo guardar";
    return;
  }

  ocultarPendiente();
  const frase = respuesta.frase;
  avisarFrase("Guardada «" + frase.nombre + "»: " + frase.notas + " notas en " +
              frase.duracion_seg.toFixed(1) + " s" +
              (frase.lista ? ", en la lista «" + frase.lista + "»." : "."));
  (respuesta.avisos || []).forEach((a) => avisarFrase(
    document.getElementById("estado-frase").textContent + " " + a));

  // La frase recien guardada aparece en su lista, ya visible.
  if (frase.lista) listaElegida = frase.lista;
  await cargarFrases();
  const fila = document.querySelector('[data-frase="' + CSS.escape(frase.nombre) + '"]');
  if (fila) fila.scrollIntoView({ behavior: "smooth", block: "center" });
}


/* Que hacer al apretar Terminar en la solapa Frases. */
function terminarFrase(respuesta) {
  if (!respuesta.ok) {
    avisarFrase(respuesta.motivo || "algo salió mal");
    return;
  }

  if (respuesta.modo === "frase") {
    avisarFrase("");
    mostrarPendiente(respuesta.pendiente);
    return;
  }

  avisarFrase("");
  mostrarComparacion(respuesta.comparacion);
  cargarFrases();
}


/* ==========================================================================
   Las listas de reproduccion y las frases
   ========================================================================== */

let listaElegida = "";            // "" es todas; " " es "sin lista"
let frasesMarcadas = new Set();
let ultimasFrases = [];
let ultimasListas = [];


async function cargarFrases() {
  const datos = await pedir("/api/frases");
  ultimasFrases = datos.frases || [];
  ultimasListas = datos.listas || [];
  dibujarFiltrosDeLista();
  dibujarListaDeFrases();
}


function dibujarFiltrosDeLista() {
  const donde = document.getElementById("filtros-lista");
  const sinLista = ultimasFrases.some((f) => !f.lista);

  const opciones = [{ clave: "", texto: "todas (" + ultimasFrases.length + ")" }]
    .concat(ultimasListas.map((l) => ({ clave: l.nombre, texto: l.nombre + " (" + l.frases + ")" })));
  if (sinLista) {
    const cuantas = ultimasFrases.filter((f) => !f.lista).length;
    opciones.push({ clave: " ", texto: "sin lista (" + cuantas + ")" });
  }

  // Si la lista que estabas mirando ya no existe, volvemos a todas.
  if (listaElegida && !opciones.some((o) => o.clave === listaElegida)) {
    listaElegida = "";
  }

  donde.innerHTML = opciones.map((opcion) =>
    '<button class="bolsa' + (opcion.clave === listaElegida ? " activa" : "") +
    '" data-lista="' + escapar(opcion.clave) + '">' + escapar(opcion.texto) +
    "</button>").join("");

  donde.querySelectorAll("[data-lista]").forEach((boton) => {
    boton.addEventListener("click", () => {
      listaElegida = boton.dataset.lista;
      cerrarEdicionDeLista();
      dibujarFiltrosDeLista();
      dibujarListaDeFrases();
    });
  });

  // Renombrar y borrar solo tienen sentido con una lista real elegida.
  const editando = !document.getElementById("editar-lista").hidden;
  document.getElementById("boton-nueva-lista").textContent =
    listaElegida && listaElegida !== " " && !editando ? "editar esta lista" : "+ nueva lista";
}


function frasesVisibles() {
  if (listaElegida === "") return ultimasFrases;
  if (listaElegida === " ") return ultimasFrases.filter((f) => !f.lista);
  return ultimasFrases.filter((f) => f.lista === listaElegida);
}


function dibujarListaDeFrases() {
  const contenedor = document.getElementById("lista-frases");
  const visibles = frasesVisibles();

  if (!ultimasFrases.length) {
    contenedor.innerHTML = '<div class="aviso">Todavía no guardaste ninguna ' +
      "frase. Dale a Grabar una frase, tocala, y al terminar le ponés nombre.</div>";
    actualizarMovedor();
    return;
  }

  if (!visibles.length) {
    contenedor.innerHTML = '<div class="aviso">Esta lista está vacía. Marcá ' +
      "frases en «todas» y mandalas acá, o elegí esta lista al guardar una nueva.</div>";
    actualizarMovedor();
    return;
  }

  contenedor.innerHTML = visibles.map((frase) =>
    '<div class="frase" data-frase="' + escapar(frase.nombre) + '">' +
      '<input type="checkbox" data-marcar="' + escapar(frase.nombre) + '"' +
        (frasesMarcadas.has(frase.nombre) ? " checked" : "") + ">" +
      '<div class="datos">' +
        "<h3>" + escapar(frase.nombre) +
          (frase.lista && listaElegida === ""
            ? ' <span class="etiqueta-lista">' + escapar(frase.lista) + "</span>"
            : "") + "</h3>" +
        (frase.comentario
          ? '<div class="descripcion">' + escapar(frase.comentario) + "</div>"
          : "") +
        '<div class="tab-corta">' + frase.tab.join(" ") + "</div>" +
        '<div class="ayuda">' + frase.notas + " notas · " +
          frase.duracion_seg.toFixed(1) + " s · armónica en " + frase.tonalidad +
          (frase.posicion ? " · " + frase.posicion + "ª posición" : "") +
          (frase.fecha ? " · " + frase.fecha : "") + "</div>" +
      "</div>" +
      (frase.hay_audio
        ? '<audio controls preload="none" src="/api/frases/audio?nombre=' +
          encodeURIComponent(frase.nombre) + '"></audio>'
        : '<span class="ayuda">sin audio</span>') +
      '<button data-practicar="' + escapar(frase.nombre) + '">Practicar</button>' +
      '<label class="audio">Con un .wav' +
        '<input type="file" accept=".wav,audio/wav" data-intento="' +
        escapar(frase.nombre) + '"></label>' +
      '<button class="borrar" data-borrar="' + escapar(frase.nombre) + '">Borrar</button>' +
    "</div>"
  ).join("");

  contenedor.querySelectorAll("[data-marcar]").forEach((casilla) => {
    casilla.addEventListener("change", () => {
      if (casilla.checked) frasesMarcadas.add(casilla.dataset.marcar);
      else frasesMarcadas.delete(casilla.dataset.marcar);
      actualizarMovedor();
    });
  });

  contenedor.querySelectorAll("[data-practicar]").forEach((boton) => {
    boton.addEventListener("click", async () => {
      document.getElementById("seccion-comparacion").hidden = true;
      ocultarPendiente();
      await comenzar({ modo: "practicar", nombre: boton.dataset.practicar });
    });
  });

  contenedor.querySelectorAll("[data-intento]").forEach((entrada) => {
    entrada.addEventListener("change", async (evento) => {
      const archivo = evento.target.files[0];
      evento.target.value = "";
      if (!archivo) return;

      const nombre = entrada.dataset.intento;
      document.getElementById("seccion-comparacion").hidden = true;
      avisarFrase("");

      const respuesta = await subir("/api/frases/intento", archivo, {}, nombre,
                                    "Comparando " + archivo.name + " contra «" + nombre + "»");
      if (!respuesta.ok) {
        avisarFrase(respuesta.motivo || "no pude comparar ese audio");
        return;
      }
      avisarFrase("");
      mostrarComparacion(respuesta.comparacion);
    });
  });

  contenedor.querySelectorAll("[data-borrar]").forEach((boton) => {
    boton.addEventListener("click", async () => {
      const nombre = boton.dataset.borrar;
      if (!confirm("¿Borrar la frase «" + nombre + "»? Se borra también su audio.")) return;
      await pedir("/api/frases/borrar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: nombre }),
      });
      frasesMarcadas.delete(nombre);
      cargarFrases();
    });
  });

  actualizarMovedor();
}


/* Los controles para mandar las marcadas a una lista. Aparecen recien cuando
 * marcaste algo: mostrarlos siempre seria ruido. */
function actualizarMovedor() {
  const caja = document.getElementById("mover-a-lista");
  caja.hidden = frasesMarcadas.size === 0;
  if (caja.hidden) return;

  document.getElementById("cuantas-marcadas").textContent =
    frasesMarcadas.size === 1 ? "1 frase marcada"
                              : frasesMarcadas.size + " frases marcadas";
  llenarSelectorDeListas("lista-destino", "", false);
}


function cerrarEdicionDeLista() {
  document.getElementById("editar-lista").hidden = true;
}


function configurarListas() {
  const edicion = document.getElementById("editar-lista");
  const campo = document.getElementById("lista-nombre-nuevo");
  const borrar = document.getElementById("boton-borrar-lista");

  // Un solo boton que es "+ nueva lista" o "editar esta lista" segun que
  // este elegido. Abre el mismo formulario de una linea.
  document.getElementById("boton-nueva-lista").addEventListener("click", () => {
    const editando = listaElegida && listaElegida !== " ";
    edicion.hidden = false;
    campo.value = editando ? listaElegida : "";
    campo.placeholder = editando ? "nuevo nombre" : "nombre de la lista";
    borrar.hidden = !editando;
    dibujarFiltrosDeLista();
    campo.focus();
  });

  document.getElementById("boton-cancelar-lista").addEventListener("click", () => {
    cerrarEdicionDeLista();
    dibujarFiltrosDeLista();
  });

  async function guardarLista() {
    const nombre = campo.value.trim();
    if (!nombre) { campo.focus(); return; }

    const editando = listaElegida && listaElegida !== " ";
    const respuesta = editando
      ? await pedir("/api/listas/renombrar", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ viejo: listaElegida, nuevo: nombre }) })
      : await pedir("/api/listas/crear", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nombre: nombre }) });

    if (!respuesta.ok) {
      avisarFrase(respuesta.motivo || "no pude guardar la lista");
      return;
    }
    listaElegida = respuesta.nombre;
    cerrarEdicionDeLista();
    await cargarFrases();
  }

  document.getElementById("boton-guardar-lista").addEventListener("click", guardarLista);
  campo.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter") guardarLista();
  });

  borrar.addEventListener("click", async () => {
    if (!confirm("¿Borrar la lista «" + listaElegida + "»? Las frases quedan, sin lista.")) return;
    await pedir("/api/listas/borrar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre: listaElegida }) });
    listaElegida = "";
    cerrarEdicionDeLista();
    await cargarFrases();
  });

  document.getElementById("boton-mover").addEventListener("click", async () => {
    const destino = document.getElementById("lista-destino").value;
    const respuesta = await pedir("/api/frases/lista", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombres: Array.from(frasesMarcadas), lista: destino }) });

    avisarFrase(respuesta.ok
      ? respuesta.movidas + (destino ? " frases a «" + destino + "»." : " frases sacadas de su lista.")
      : "no pude mover nada");
    frasesMarcadas.clear();
    await cargarFrases();
  });

  document.getElementById("boton-desmarcar").addEventListener("click", () => {
    frasesMarcadas.clear();
    dibujarListaDeFrases();
  });
}


function mostrarComparacion(c) {
  const seccion = document.getElementById("seccion-comparacion");
  const contenedor = document.getElementById("comparacion");
  const d = c.devolucion || null;

  let html = "<p class='ayuda'>Contra «" + escapar(c.nombre) + "»</p>";

  // Los tres numeros. Cada uno dice si esta medido o no: preferimos un
  // "sin datos" honesto a un numero con cara de diagnostico.
  if (d) {
    html += '<div class="tarjetas">' +
      tarjeta(d.notas.porcentaje + "%", "notas",
              d.notas.aciertos + " de " + d.notas.esperadas, true,
              d.notas.porcentaje >= 90 ? "bien" : d.notas.porcentaje >= 70 ? "regular" : "mal") +
      tarjeta(d.afinacion.medida ? "±" + d.afinacion.desvio_tipico_cents + " c" : "—",
              "afinación",
              d.afinacion.medida
                ? (d.afinacion.bends_fuera.length
                    ? d.afinacion.bends_fuera.length + (d.afinacion.bends_fuera.length === 1 ? " bend fuera" : " bends fuera")
                    : "bends en su lugar")
                : "pocas notas para medir",
              d.afinacion.medida,
              !d.afinacion.medida ? "" : d.afinacion.bends_fuera.length ? "regular" : "bien") +
      tarjeta(d.tiempo.medido ? d.tiempo.a_tiempo + "/" + d.tiempo.medidas : "—",
              "a tiempo",
              d.tiempo.medido
                ? d.tiempo.calidad + (d.tiempo.velocidad_pct !== 0
                    ? " · " + Math.abs(d.tiempo.velocidad_pct) + "% más " +
                      (d.tiempo.velocidad_pct > 0 ? "lento" : "rápido")
                    : "")
                : "pocas notas para medir",
              d.tiempo.medido,
              !d.tiempo.medido ? "" :
                (d.tiempo.calidad === "muy parecida" || d.tiempo.calidad === "parecida") ? "bien" : "regular") +
      "</div>";

    html += "<h2>Qué hacer con esto</h2>";
    d.consejos.forEach((consejo, indice) => {
      html += '<div class="hallazgo' + (indice === 0 ? " primero" : "") +
              '"><p class="accion">' + escapar(consejo) + "</p></div>";
    });
  }

  // Escuchar las dos, una debajo de la otra. La tablatura no lleva el
  // ritmo, y el ritmo es lo que estas tratando de copiar.
  if (c.referencia_con_audio || c.intento_con_audio) {
    html += "<h2>Escuchalas seguidas</h2><div class='escuchar-par'>";
    if (c.referencia_con_audio) {
      html += '<label>la referencia<audio controls preload="none" src="/api/frases/audio?nombre=' +
              encodeURIComponent(c.nombre) + '"></audio></label>';
    }
    if (c.intento_con_audio) {
      html += '<label>tu intento<audio controls preload="none" src="/api/frases/intento/audio?t=' +
              Date.now() + '"></audio></label>';
    }
    html += "</div>";
  }

  if (c.notas.length) {
    html += "<h2>Nota por nota</h2><p class='ayuda'>Desvío de tiempo con la " +
            "velocidad descontada, y afinación respecto de la referencia.</p>" +
            "<div class='notas-comparadas'>";
    c.notas.forEach((nota) => {
      const aTiempo = Math.abs(nota.desvio_ms) <= 40;
      const afinada = Math.abs(nota.cents) <= TOLERANCIA;
      html += '<span class="' + (aTiempo && afinada ? "bien" : "mal") + '">' +
        nota.tab + " <em>" + (nota.desvio_ms > 0 ? "+" : "") + nota.desvio_ms +
        " ms · " + (nota.cents > 0 ? "+" : "") + nota.cents + " c</em></span>";
    });
    html += "</div>";
  }

  if (c.faltantes.length) {
    html += "<p class='ayuda'>Te faltaron: " + c.faltantes.join(" ") + "</p>";
  }
  if (c.sobrantes.length) {
    html += "<p class='ayuda'>De más: " + c.sobrantes.join(" ") + "</p>";
  }
  if (c.cambiadas.length) {
    html += "<p class='ayuda'>Cambiadas: " + c.cambiadas
      .map((par) => (par.esperada || "—") + " → " + (par.tocada || "—"))
      .join(", ") + "</p>";
  }

  contenedor.innerHTML = html;
  seccion.hidden = false;
  seccion.scrollIntoView({ behavior: "smooth", block: "start" });
}


/* Una de las tres tarjetas de arriba: el numero grande, que es, y un
 * detalle. `medida` en falso la pinta apagada. */
function tarjeta(numero, rotulo, detalle, medida, tono) {
  return '<div class="tarjeta' + (medida ? "" : " apagada") + (tono ? " " + tono : "") + '">' +
    '<div class="numero">' + escapar(numero) + "</div>" +
    '<div class="rotulo">' + escapar(rotulo) + "</div>" +
    '<div class="detalle">' + escapar(detalle) + "</div></div>";
}


/* Los nombres de frase los escribis vos y van a parar adentro del HTML. */
function escapar(texto) {
  return String(texto).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}


/* ==========================================================================
   El nivel de entrada

   Es lo primero que hay que poder ver cuando "no anda nada". Sin esta barra,
   un microfono equivocado y una armonica tocada bajito se ven exactamente
   igual: la pantalla quieta.
   ========================================================================== */

/* Cuanto de la barra ocupa el volumen. La escala es logaritmica porque el
 * oido lo es: en escala lineal, todo lo que se toca de verdad se amontona
 * contra el borde izquierdo y no se distingue nada. */
function aPorcentaje(volumen) {
  if (!volumen || volumen <= 0) return 0;
  const db = 20 * Math.log10(volumen);       // 0 = saturado, -60 = casi nada
  return Math.max(0, Math.min(100, (db + 60) / 60 * 100));
}


function marcarUmbral() {
  const umbral = aPorcentaje(inicio.umbral_volumen || 0.01);
  ["marca-umbral", "marca-umbral-ajustes", "marca-umbral-frases"].forEach((id) => {
    const marca = document.getElementById(id);
    if (marca) marca.style.left = umbral + "%";
  });
}


function dibujarNivel(estado) {
  const ancho = aPorcentaje(estado.pico);
  const umbral = inicio.umbral_volumen || 0.01;

  ["barra-nivel", "barra-nivel-ajustes", "barra-nivel-frases"].forEach((id) => {
    const barra = document.getElementById(id);
    if (!barra) return;
    barra.style.width = ancho + "%";
    barra.classList.toggle("callado", estado.pico < umbral);
    barra.classList.toggle("saturado", estado.pico > 0.95);
  });

  const texto = document.getElementById("texto-nivel");
  if (!texto) return;

  if (estado.error_de_audio) {
    texto.innerHTML = "<strong>El micr\u00f3fono fall\u00f3:</strong> " +
      escapar(estado.error_de_audio) +
      " \u2014 prob\u00e1 con otro en <strong>Ajustes</strong>.";
    texto.className = "ayuda lejos";
    return;
  }

  texto.className = "ayuda";

  if (!estado.escuchando) {
    texto.innerHTML = "El micr\u00f3fono no est\u00e1 abierto. Prob\u00e1 " +
      "eligiendo otro en <strong>Ajustes</strong>.";
  } else if (estado.pico < umbral) {
    texto.innerHTML = "Escuchando, pero no llega nada por encima del umbral. " +
      "Si est\u00e1s tocando, el micr\u00f3fono elegido no es el que us\u00e1s.";
  } else if (estado.pico > 0.95) {
    texto.textContent = "Est\u00e1 saturando: baj\u00e1 el volumen de entrada " +
      "o alejate un poco del micr\u00f3fono.";
  } else {
    texto.textContent = "Entrando bien.";
  }
}


/* ==========================================================================
   Los ajustes
   ========================================================================== */

async function cargarAjustes() {
  llenarSelector("ajuste-tonalidad",
    (inicio.tonalidades || []).map((clave) => ({ valor: clave, texto: clave })),
    inicio.tonalidad);

  llenarSelector("ajuste-posicion",
    [{ valor: "", texto: "sin posici\u00f3n" }].concat(
      (inicio.posiciones || []).map((posicion) =>
        ({ valor: posicion.numero, texto: posicion.nombre }))),
    inicio.posicion === null ? "" : inicio.posicion);

  llenarSelector("ajuste-escala",
    [{ valor: "", texto: "sin escala de referencia" }].concat(
      (inicio.escalas || []).map((escala) =>
        ({ valor: escala.clave, texto: escala.nombre }))),
    inicio.escala || "");

  mostrarResultadoDeAjustes();

  const datos = await pedir("/api/dispositivos");
  llenarSelector("selector-microfono",
    [{ valor: "", texto: "el predeterminado de Windows" }].concat(
      (datos.dispositivos || []).map((aparato) =>
        ({ valor: aparato.numero, texto: aparato.numero + ". " + aparato.nombre }))),
    datos.elegido === null || datos.elegido === undefined ? "" : datos.elegido);

  if (!datos.ok) {
    document.getElementById("estado-microfono").textContent =
      datos.motivo || "no pude leer la lista de micr\u00f3fonos";
  }
}


function llenarSelector(id, opciones, elegido) {
  const selector = document.getElementById(id);
  if (!selector || selector.dataset.listo === "si") return;

  selector.innerHTML = opciones.map((opcion) =>
    '<option value="' + opcion.valor + '"' +
    (String(opcion.valor) === String(elegido) ? " selected" : "") + ">" +
    escapar(opcion.texto) + "</option>").join("");

  selector.dataset.listo = "si";
  selector.addEventListener("change", guardarAjustes);
}


async function guardarAjustes() {
  const posicion = document.getElementById("ajuste-posicion").value;
  const dispositivo = document.getElementById("selector-microfono").value;

  const respuesta = await pedir("/api/configuracion", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tonalidad: document.getElementById("ajuste-tonalidad").value,
      posicion: posicion === "" ? null : Number(posicion),
      escala: document.getElementById("ajuste-escala").value || null,
      dispositivo: dispositivo === "" ? null : Number(dispositivo),
    }),
  });

  if (!respuesta.ok) {
    document.getElementById("resultado-ajustes").textContent = respuesta.motivo;
    return;
  }

  // El servidor devuelve los datos iniciales de nuevo: la armonica cambio y
  // con ella el diagrama entero, que se dibuja en Python y no aca.
  inicio = respuesta.inicio;
  mostrarEncabezado();
  dibujarDiagrama(inicio.diagrama);
  marcarUmbral();
  mostrarResultadoDeAjustes();
}


function mostrarResultadoDeAjustes() {
  const donde = document.getElementById("resultado-ajustes");
  if (!donde) return;

  donde.textContent = inicio.posicion
    ? "Arm\u00f3nica en " + inicio.tonalidad + ", " + inicio.nombre_posicion +
      ": toc\u00e1s en " + inicio.tono_resultante + "."
    : "Arm\u00f3nica en " + inicio.tonalidad +
      ". Sin posici\u00f3n no se marca ninguna escala en el diagrama.";
}


