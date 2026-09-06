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
let celdasPorClave = {};


/* ==========================================================================
   Arranque
   ========================================================================== */

document.addEventListener("DOMContentLoaded", async () => {
  configurarSolapas();
  configurarBotones();
  configurarPrueba();

  inicio = await pedir("/api/inicio");
  TOLERANCIA = inicio.tolerancia_cents || 10;

  mostrarEncabezado();
  llenarTonalidades();
  marcarUmbral();
  dibujarDiagrama(inicio.diagrama);
  ajustarZonaBuena();

  conectarEnVivo();
});


async function pedir(ruta, opciones) {
  const respuesta = await fetch(ruta, opciones);
  return respuesta.json();
}


function mostrarEncabezado() {
  let texto = "Armónica en " + inicio.tonalidad;
  if (inicio.posicion) {
    texto += ", " + inicio.nombre_posicion + " → tocás en " + inicio.tono_resultante;
  }
  if (inicio.nombre_escala) {
    texto += ". " + inicio.nombre_escala;
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
  const empezar = document.getElementById("boton-empezar");
  const terminar = document.getElementById("boton-terminar");

  empezar.addEventListener("click", async () => {
    empezar.disabled = true;
    document.getElementById("seccion-resumen").hidden = true;
    await comenzar({ modo: "sesion" });
  });

  terminar.addEventListener("click", async () => {
    terminar.disabled = true;
    terminar.textContent = "Guardando...";
    const respuesta = await pedir("/api/terminar", { method: "POST" });
    terminar.textContent = "Terminar y guardar";
    mostrarResumen(respuesta);
  });

  // --- Los de la solapa Frases ---
  document.getElementById("boton-grabar-frase")
    .addEventListener("click", async () => {
      const campo = document.getElementById("nombre-frase");
      const nombre = campo.value.trim();
      if (!nombre) {
        avisarFrase("Pone un nombre antes de grabar.");
        campo.focus();
        return;
      }
      document.getElementById("seccion-comparacion").hidden = true;
      await comenzar({ modo: "frase", nombre: nombre });
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

      const campo = document.getElementById("nombre-frase");
      const nombre = campo.value.trim() || sinExtension(archivo.name);
      campo.value = nombre;

      document.getElementById("seccion-comparacion").hidden = true;
      await elegirQueImportar(nombre, archivo);
    });
}


/* Un audio puede ser una frase o puede ser una clase entera.
 *
 * Antes de guardar nada, se busca donde hay armonica. Si hay un solo tramo,
 * el archivo ES la frase y se guarda sin preguntar. Si hay varios, alguien
 * estuvo hablando en el medio y hay que elegir cual guardar: guardar la clase
 * entera daria una referencia con diez segundos de silencio adentro, contra
 * la que es imposible practicar. */
async function elegirQueImportar(nombre, archivo) {
  limpiarDudoso();
  limpiarTramos();
  avisarFrase("Buscando d\u00f3nde hay arm\u00f3nica en " + archivo.name + "...");

  const respuesta = await subir("/api/frases/tramos", nombre, archivo, {});

  if (!respuesta.ok) {
    avisarFrase(respuesta.motivo || "no pude leer ese audio");
    return;
  }

  const tramos = respuesta.tramos || [];

  if (!tramos.length) {
    avisarFrase(respuesta.sirve
      ? "No encontr\u00e9 ning\u00fan tramo con arm\u00f3nica en ese audio."
      : respuesta.motivo);
    return;
  }

  if (tramos.length === 1) {
    return importar(nombre, archivo, false, tramos[0]);
  }

  avisarFrase("");
  mostrarTramos(respuesta, nombre, archivo);
}


function mostrarTramos(respuesta, nombre, archivo) {
  const contenedor = document.getElementById("tramos");
  const tocando = respuesta.tramos
    .reduce((suma, tramo) => suma + tramo.duracion_seg, 0);

  contenedor.innerHTML =
    "<h3>" + respuesta.tramos.length + " tramos con arm\u00f3nica</h3>" +
    "<p>De los " + respuesta.duracion_seg.toFixed(0) + " segundos del audio, " +
    tocando.toFixed(0) + " tienen arm\u00f3nica. El resto es silencio, alguien " +
    "hablando, o la base sola. Eleg\u00ed qu\u00e9 tramo guardar como frase: " +
    "la grabaci\u00f3n entera no sirve de referencia porque los silencios " +
    "tambi\u00e9n contar\u00edan.</p>" +
    respuesta.tramos.map((tramo) =>
      '<div class="tramo">' +
        '<span class="cuando">' + reloj(tramo.desde_seg) + " a " +
          reloj(tramo.hasta_seg) + "</span>" +
        '<span class="notas">' + tramo.tab.join(" ") +
          (tramo.hay_mas ? " \u2026" : "") + "</span>" +
        '<span class="cuando">' + tramo.notas + " notas</span>" +
        '<button data-tramo="' + tramo.numero + '">Guardar este</button>' +
      "</div>"
    ).join("");

  contenedor.querySelectorAll("[data-tramo]").forEach((boton) => {
    boton.addEventListener("click", () => {
      const tramo = respuesta.tramos.find(
        (candidato) => String(candidato.numero) === boton.dataset.tramo);
      contenedor.querySelectorAll("button").forEach((otro) => {
        otro.disabled = true;
      });
      importar(nombre, archivo, false, tramo);
    });
  });
}


function reloj(segundos) {
  const minutos = Math.floor(segundos / 60);
  const resto = (segundos % 60).toFixed(1).padStart(4, "0");
  return minutos + ":" + resto;
}


function limpiarTramos() {
  document.getElementById("tramos").innerHTML = "";
}


/* Manda el audio y muestra el resultado. `igual` en true saltea el control de
 * monofonia: es lo que pasa cuando ya viste la tablatura y dijiste que sirve. */
async function importar(nombre, archivo, igual, tramo) {
  const campo = document.getElementById("nombre-frase");
  limpiarDudoso();
  avisarFrase("Analizando " + archivo.name + "...");

  const extra = { igual: igual ? "1" : "0" };
  if (tramo) {
    extra.desde = tramo.desde_seg;
    extra.hasta = tramo.hasta_seg;
  }

  const respuesta = await subir("/api/frases/importar", nombre, archivo, extra);

  if (!respuesta.ok) {
    avisarFrase(respuesta.motivo || "no pude importar ese audio");
    if (respuesta.se_puede_igual) mostrarDudoso(respuesta, nombre, archivo, tramo);
    return;
  }

  limpiarTramos();

  const frase = respuesta.frase;
  avisarFrase("Importada \u00ab" + frase.nombre + "\u00bb: " + frase.notas +
              " notas en " + frase.duracion_seg.toFixed(1) +
              " s, arm\u00f3nica en " + frase.tonalidad + ".");
  (respuesta.avisos || []).forEach(mostrarAviso);
  campo.value = "";
  cargarFrases();
}


/* Sube un archivo. El nombre y las opciones van en la URL y los bytes crudos
 * en el cuerpo: es lo mismo que hace multipart pero sin nada que parsear del
 * otro lado. */
async function subir(ruta, nombre, archivo, extra) {
  const partes = ["nombre=" + encodeURIComponent(nombre),
                  "archivo=" + encodeURIComponent(archivo.name || "")];

  const tonalidad = document.getElementById("tonalidad-frase").value;
  if (tonalidad) partes.push("tonalidad=" + encodeURIComponent(tonalidad));

  Object.entries(extra || {}).forEach(([clave, valor]) =>
    partes.push(clave + "=" + encodeURIComponent(valor)));

  const respuesta = await fetch(ruta + "?" + partes.join("&"),
                                { method: "POST", body: archivo });
  return respuesta.json();
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


/* Cuando el audio no pasa el control, no se guarda nada: se muestra lo que
 * HABRIA salido y decidis vos. El umbral es una heuristica; el que reconoce
 * la frase de Leandro en esa tablatura sos vos. */
function mostrarDudoso(respuesta, nombre, archivo, tramo) {
  const caja = document.createElement("div");
  caja.className = "dudoso";
  caja.id = "caja-dudosa";

  const previa = (respuesta.vista_previa || []);
  caja.innerHTML =
    "<p>Esto es lo que habr\u00eda transcrito. Si reconoc\u00e9s la frase, " +
    "guardala igual; si es un choclo de notas sueltas, no sirve como " +
    "referencia y vas a estar practicando contra ruido.</p>" +
    '<div class="tab-corta">' + (previa.join(" ") || "(nada)") +
    (previa.length >= 24 ? " \u2026" : "") + "</div>";

  const guardar = document.createElement("button");
  guardar.className = "principal";
  guardar.textContent = "Guardar igual";
  guardar.addEventListener("click", () => importar(nombre, archivo, true, tramo));

  const descartar = document.createElement("button");
  descartar.className = "secundario";
  descartar.textContent = "Descartar";
  descartar.addEventListener("click", limpiarDudoso);

  caja.appendChild(guardar);
  caja.appendChild(descartar);
  document.getElementById("lista-frases").before(caja);
}


function limpiarDudoso() {
  const caja = document.getElementById("caja-dudosa");
  if (caja) caja.remove();
}


function sinExtension(nombre) {
  return nombre.replace(/\.[^.]+$/, "");
}


/* Un aviso no es un error: la frase se guardo igual. Se muestra aparte para
 * que no se confunda con los mensajes de "no pude". */
function mostrarAviso(texto) {
  const caja = document.createElement("div");
  caja.className = "aviso";
  caja.textContent = texto;
  document.getElementById("lista-frases").before(caja);
  setTimeout(() => caja.remove(), 20000);
}


/* Empezar a escuchar. Los tres modos usan la misma ruta: lo unico que cambia
 * es que hace el servidor cuando termina. */
async function comenzar(cuerpo) {
  const respuesta = await pedir("/api/comenzar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
  if (!respuesta.ok) {
    avisarFrase(respuesta.motivo || "no pude empezar");
    document.getElementById("boton-empezar").disabled = false;
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
  resaltarAgujero(estado.nota);
  dibujarTab(estado.tab);
  dibujarNivel(estado);
  sincronizarBotones(estado);

  const minutos = Math.floor(estado.segundos / 60);
  const segundos = String(Math.floor(estado.segundos % 60)).padStart(2, "0");
  document.getElementById("contadores").textContent = estado.escuchando
    ? `${estado.cantidad_notas} notas · ${minutos}:${segundos}`
    : "";
}


function dibujarMedidor(estado) {
  const grande = document.getElementById("nota-grande");
  const nombre = document.getElementById("nombre-nota");
  const cents = document.getElementById("cents");
  const punto = document.getElementById("punto");
  const pista = document.getElementById("pista");

  if (!estado.nota) {
    grande.textContent = "—";
    grande.className = "";
    nombre.textContent = "";
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
  grande.className = estado.nota.en_escala === false ? "fuera-de-escala" : "";
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

function dibujarDiagrama(filas) {
  const contenedor = document.getElementById("diagrama");
  contenedor.innerHTML = "";
  celdasPorClave = {};

  // Los números de agujero, arriba de todo.
  const encabezado = document.createElement("div");
  encabezado.className = "fila-diagrama";
  encabezado.appendChild(document.createElement("div"));
  for (let agujero = 1; agujero <= 10; agujero++) {
    const numero = document.createElement("div");
    numero.className = "numeros-agujeros";
    numero.textContent = agujero;
    encabezado.appendChild(numero);
  }
  contenedor.appendChild(encabezado);

  filas.forEach((fila) => {
    const elemento = document.createElement("div");
    elemento.className = "fila-diagrama";

    const etiqueta = document.createElement("div");
    etiqueta.className = "etiqueta-fila";
    etiqueta.textContent = fila.etiqueta;
    elemento.appendChild(etiqueta);

    fila.celdas.forEach((celda) => {
      const caja = document.createElement("div");
      if (!celda) {
        caja.className = "celda vacia";
        caja.textContent = "·";
      } else {
        caja.className = "celda" + (celda.en_escala ? " en-escala" : "");
        caja.innerHTML = celda.tab +
          '<span class="nombre">' + celda.nombre + "</span>";
        celdasPorClave[clave(celda)] = caja;
      }
      elemento.appendChild(caja);
    });

    contenedor.appendChild(elemento);
  });
}


function clave(nota) {
  return nota.agujero + "|" + nota.direccion + "|" + nota.bend;
}


let celdaResaltada = null;

function resaltarAgujero(nota) {
  const nueva = nota ? celdasPorClave[clave(nota)] : null;
  if (nueva === celdaResaltada) return;

  if (celdaResaltada) celdaResaltada.classList.remove("actual");
  if (nueva) nueva.classList.add("actual");
  celdaResaltada = nueva;
}


function dibujarTab(tabs) {
  const contenedor = document.getElementById("tab");
  if (!tabs || !tabs.length) {
    contenedor.textContent = "—";
    return;
  }
  contenedor.innerHTML = tabs
    .map((tab, indice) =>
      indice === tabs.length - 1 ? '<span class="ultima">' + tab + "</span>" : tab)
    .join(" ");
}


/* ==========================================================================
   El resumen al terminar
   ========================================================================== */

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

  let html = "<table><thead><tr><th>Fecha</th><th>Armónica</th>" +
             "<th>Posición</th><th class='numero'>Notas</th>" +
             "<th class='numero'>Minutos</th><th class='numero'>Afinación</th>" +
             "</tr></thead><tbody>";

  sesiones.slice().reverse().forEach((sesion) => {
    const afinacion = sesion.afinacion === null || sesion.afinacion === undefined
      ? "—"
      : (sesion.afinacion > 0 ? "+" : "") + sesion.afinacion.toFixed(0);
    html += "<tr><td>" + (sesion.fecha || "—") + "</td>" +
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
  const escuchando = estado.escuchando;
  const modo = estado.modo || "sesion";
  const enFrase = escuchando && (modo === "frase" || modo === "practicar");

  document.getElementById("boton-empezar").disabled = escuchando;
  document.getElementById("boton-terminar").disabled =
    !(escuchando && modo === "sesion");

  document.getElementById("boton-grabar-frase").disabled = escuchando;
  document.getElementById("boton-terminar-frase").hidden = !enFrase;
  document.getElementById("nombre-frase").disabled = escuchando;
  document.getElementById("tonalidad-frase").disabled = escuchando;

  document.querySelectorAll("#lista-frases button")
    .forEach((boton) => { boton.disabled = escuchando; });

  // Un <label> no se puede deshabilitar: se apaga el <input> que tiene adentro
  // y se lo pinta de apagado para que se note.
  document.querySelectorAll(".como-boton, .frase label.audio")
    .forEach((etiqueta) => {
      etiqueta.classList.toggle("apagado", escuchando);
      const entrada = etiqueta.querySelector("input");
      if (entrada) entrada.disabled = escuchando;
    });

  if (enFrase) {
    avisarFrase(modo === "frase"
      ? "Grabando \u00ab" + estado.nombre_frase + "\u00bb. Toca la frase y dale Terminar."
      : "Practicando \u00ab" + estado.nombre_frase + "\u00bb. Tocala y dale Terminar.");
  } else if (escuchando) {
    avisarFrase(AVISO_SESION);
  } else if (document.getElementById("estado-frase").textContent === AVISO_SESION) {
    // El aviso valia mientras la sesion estaba andando. Si sigue ahi
    // despues de terminar, dice una mentira: se limpia solo.
    avisarFrase("");
  }
}


const AVISO_SESION = "Hay una sesi\u00f3n en vivo andando. Terminala primero.";


async function cargarFrases() {
  const datos = await pedir("/api/frases");
  const contenedor = document.getElementById("lista-frases");

  if (!datos.frases || !datos.frases.length) {
    contenedor.innerHTML = '<div class="aviso">Todav\u00eda no guardaste ninguna ' +
      "frase. Escrib\u00ed un nombre arriba, dale Grabar y toc\u00e1 la frase como " +
      "querr\u00edas tocarla.</div>";
    return;
  }

  contenedor.innerHTML = datos.frases.map((frase) =>
    '<div class="frase">' +
      '<div class="datos">' +
        "<h3>" + escapar(frase.nombre) + "</h3>" +
        '<div class="tab-corta">' + frase.tab.join(" ") +
          (frase.notas > frase.tab.length ? " \u2026" : "") + "</div>" +
        '<div class="ayuda">' + frase.notas + " notas \u00b7 " +
          frase.duracion_seg.toFixed(1) + " s \u00b7 arm\u00f3nica en " + frase.tonalidad +
          (frase.posicion ? " \u00b7 " + frase.posicion + "\u00aa posici\u00f3n" : "") +
          (frase.fecha ? " \u00b7 " + frase.fecha : "") + "</div>" +
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

  contenedor.querySelectorAll("[data-practicar]").forEach((boton) => {
    boton.addEventListener("click", async () => {
      document.getElementById("seccion-comparacion").hidden = true;
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
      avisarFrase("Comparando " + archivo.name + " contra \u00ab" + nombre + "\u00bb...");

      const respuesta = await subir("/api/frases/intento", nombre, archivo, {});
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
      if (!confirm("\u00bfBorrar la frase \u00ab" + nombre + "\u00bb?")) return;
      await pedir("/api/frases/borrar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: nombre }),
      });
      cargarFrases();
    });
  });
}


/* Que mostrar al terminar, segun si estabas grabando o practicando. */
function terminarFrase(respuesta) {
  if (!respuesta.ok) {
    avisarFrase(respuesta.motivo || "algo sali\u00f3 mal");
    return;
  }

  if (respuesta.modo === "frase") {
    const frase = respuesta.frase;
    avisarFrase("Guardada \u00ab" + frase.nombre + "\u00bb: " + frase.notas +
                " notas en " + frase.duracion_seg.toFixed(1) + " s.");
    document.getElementById("nombre-frase").value = "";
    cargarFrases();
    return;
  }

  avisarFrase("");
  mostrarComparacion(respuesta.comparacion);
  cargarFrases();
}


function mostrarComparacion(c) {
  const seccion = document.getElementById("seccion-comparacion");
  const contenedor = document.getElementById("comparacion");

  let html = "<p class='ayuda'>\u00ab" + escapar(c.nombre) + "\u00bb \u00b7 " +
    c.aciertos + " de " + c.esperadas + " notas (" + c.porcentaje + "%)</p>" +
    '<div class="barra-aciertos"><div style="width:' + c.porcentaje + '%"></div></div>';

  // La velocidad va aparte de los desvios: tocar mas lento no es un error,
  // es una decision. Lo que se mide es si el ritmo INTERNO se mantuvo.
  const masLento = c.velocidad > 0;
  html += "<p>Tocaste un " + Math.abs(c.velocidad) + "% m\u00e1s " +
          (masLento ? "lento" : "r\u00e1pido") + " que la referencia";
  html += (c.relativa === null)
    ? ". La frase tiene una sola nota: no hay ritmo que medir.</p>"
    : ". Sacada la velocidad, tu ritmo qued\u00f3 <strong>" + c.calidad +
      "</strong> (dispersi\u00f3n " + c.dispersion_ms + " ms, " +
      c.relativa.toFixed(2) + " de una nota).</p>";

  if (c.notas.length) {
    html += "<h2>Nota por nota</h2><div class='notas-comparadas'>";
    c.notas.forEach((nota) => {
      const aTiempo = Math.abs(nota.desvio_ms) <= 40;
      const afinada = Math.abs(nota.cents) <= TOLERANCIA;
      html += '<span class="' + (aTiempo && afinada ? "bien" : "mal") + '">' +
        nota.tab + " <em>" + (nota.desvio_ms > 0 ? "+" : "") + nota.desvio_ms +
        " ms \u00b7 " + (nota.cents > 0 ? "+" : "") + nota.cents + " c</em></span>";
    });
    html += "</div>";
  }

  if (c.faltantes.length) {
    html += "<p class='ayuda'>Te faltaron: " + c.faltantes.join(" ") + "</p>";
  }
  if (c.sobrantes.length) {
    html += "<p class='ayuda'>De m\u00e1s: " + c.sobrantes.join(" ") + "</p>";
  }
  if (c.cambiadas.length) {
    html += "<p class='ayuda'>Cambiadas: " + c.cambiadas
      .map((par) => (par.esperada || "\u2014") + " \u2192 " + (par.tocada || "\u2014"))
      .join(", ") + "</p>";
  }

  contenedor.innerHTML = html;
  seccion.hidden = false;
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
  ["marca-umbral", "marca-umbral-ajustes"].forEach((id) => {
    const marca = document.getElementById(id);
    if (marca) marca.style.left = umbral + "%";
  });
}


function dibujarNivel(estado) {
  const ancho = aPorcentaje(estado.pico);
  const umbral = inicio.umbral_volumen || 0.01;

  ["barra-nivel", "barra-nivel-ajustes"].forEach((id) => {
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
    texto.innerHTML = "Dale a <strong>Empezar a escuchar</strong> y sopl\u00e1: " +
      "esta barra se tiene que mover. Si no se mueve, and\u00e1 a " +
      "<strong>Ajustes</strong> y eleg\u00ed otro micr\u00f3fono.";
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


/* Probar el microfono: escucha un rato y no guarda nada. Es el modo mas
 * barato de contestar la pregunta "¿me esta escuchando?". */
function configurarPrueba() {
  const boton = document.getElementById("boton-probar");
  if (!boton) return;

  boton.addEventListener("click", async () => {
    const aviso = document.getElementById("estado-microfono");

    if (boton.dataset.andando === "si") {
      const respuesta = await pedir("/api/terminar", { method: "POST" });
      boton.dataset.andando = "no";
      boton.textContent = "Probar";
      aviso.textContent = respuesta.notas
        ? "Reconoci\u00f3 " + respuesta.notas + " notas. El micr\u00f3fono anda."
        : "No reconoci\u00f3 ninguna nota.";
      return;
    }

    await guardarAjustes();     // primero fijamos el microfono elegido
    const respuesta = await comenzar({ modo: "prueba" });
    if (respuesta.ok) {
      boton.dataset.andando = "si";
      boton.textContent = "Terminar la prueba";
      aviso.textContent = "Sopl\u00e1: la barra de abajo se tiene que mover.";
    } else {
      aviso.textContent = respuesta.motivo || "no pude abrir el micr\u00f3fono";
    }
  });
}
