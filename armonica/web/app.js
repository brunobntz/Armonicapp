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

  inicio = await pedir("/api/inicio");
  TOLERANCIA = inicio.tolerancia_cents || 10;

  mostrarEncabezado();
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
      document.getElementById("panel-vivo").hidden = cual !== "vivo";
      document.getElementById("panel-historial").hidden = cual !== "historial";

      if (cual === "historial") cargarHistorial();
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
    await pedir("/api/comenzar", { method: "POST" });
    terminar.disabled = false;
  });

  terminar.addEventListener("click", async () => {
    terminar.disabled = true;
    terminar.textContent = "Guardando...";
    const respuesta = await pedir("/api/terminar", { method: "POST" });
    terminar.textContent = "Terminar y guardar";
    empezar.disabled = false;
    mostrarResumen(respuesta);
  });
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
