/* Boletines IRVE · interfaz de navegador
 *
 * Todo pasa aquí dentro: los datos del cliente no salen del ordenador.
 * Lo que guardas (empresa, valores técnicos, códigos postales y el historial)
 * vive en el almacenamiento de este navegador.
 */

import { generarExpediente, valoresTecnicos, calcular, distribuidoraPorCups } from "./motor.js";

const $ = (s, raiz = document) => raiz.querySelector(s);
const $$ = (s, raiz = document) => [...raiz.querySelectorAll(s)];
const form = $("#formulario");

/* Cualquier texto que venga del usuario y acabe en la página pasa por aquí:
   un nombre de cliente con «<» o comillas no debe poder romper la pantalla. */
const escapar = v => String(v ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));

const CLAVE_BORRADOR = "irve-borrador";
const CLAVE_AJUSTES = "irve-ajustes";
const CLAVE_EXPEDIENTES = "irve-expedientes";

const CAMPOS_TECNICOS = [
  "seccion", "material", "fases", "tipo_cable", "diametro_tubo", "num_tubos",
  "conductor_proteccion", "iga_intensidad", "iga_poder_corte",
  "dif_intensidad", "dif_sensibilidad", "dif_clase", "fusible_seguridad",
  "tipo_instalacion_di", "tipo_instalacion_circuito",
  // La planta no es un dato tecnico, pero casi siempre es la misma (-1), asi
  // que se recuerda igual que los demas y se puede cambiar cuando toque.
  "plaza_planta",
];

let CFG = null;
const CACHE_PLANTILLAS = new Map();

/* ══════════════ guardar y recuperar ══════════════ */

const leer = (clave, defecto) => {
  try { return JSON.parse(localStorage.getItem(clave)) ?? defecto; }
  catch (e) { return defecto; }
};
const escribir = (clave, valor) => {
  try { localStorage.setItem(clave, JSON.stringify(valor)); return true; }
  catch (e) { return false; }
};

function guardarAjustes() {
  return escribir(CLAVE_AJUSTES, {
    empresa: CFG.empresa,
    tecnica: CFG.tecnica,
    codigos_postales: CFG.codigos_postales,
  });
}

/* ══════════════ arranque ══════════════ */

document.addEventListener("DOMContentLoaded", async () => {
  try {
    CFG = await (await fetch("config-inicial.json")).json();
  } catch (e) {
    $("#cargando").innerHTML = "<strong>No he podido cargar la configuración.</strong> "
      + "Recarga la página.";
    return;
  }
  const guardado = leer(CLAVE_AJUSTES, null);
  if (guardado) {
    CFG.empresa = { ...CFG.empresa, ...guardado.empresa };
    CFG.tecnica = { ...CFG.tecnica, ...guardado.tecnica };
    CFG.codigos_postales = { ...CFG.codigos_postales, ...guardado.codigos_postales };
  }

  rellenarListas();
  aplicarValoresTecnicos(CFG.tecnica);
  pintarLocalidades();
  pintarConfigEmpresa();
  pintarCodigosPostales();
  pintarExpedientes();
  ponerFechaHoy();
  restaurarBorrador();
  recalcular();

  // Se traen los impresos por adelantado para que generar sea instantáneo
  precargar();
  $("#sin-empresa").hidden = !!(CFG.empresa.razon_social || "").trim();
});

async function precargar() {
  const caja = $("#cargando");
  try {
    await Promise.all(["MTD.pdf", "ANEXO_IVE.pdf", "UNIFILAR.pdf", "SOLICITUD.pdf",
      "AUTORIZACION.pdf", "ANEXO_GARAJE.pdf", "CIE_base.pdf"].map(n => cargarPlantilla(n)));
    await cargarPlantilla("cie_mapa.json", "json");
    caja.hidden = true;
  } catch (e) {
    caja.className = "alarma";
    caja.innerHTML = "<strong>No he podido cargar los impresos.</strong> "
      + "Comprueba tu conexión y recarga la página.";
  }
}

function cargarPlantilla(nombre, como) {
  // Se guarda la promesa, no el resultado: si pulsas Generar mientras aún se
  // están trayendo los impresos, no se descargan dos veces.
  const clave = nombre + (como || "");
  if (!CACHE_PLANTILLAS.has(clave)) {
    CACHE_PLANTILLAS.set(clave, (async () => {
      const r = await fetch("plantillas/" + nombre);
      if (!r.ok) throw new Error("No encuentro " + nombre);
      return como === "json" ? r.json() : new Uint8Array(await r.arrayBuffer());
    })().catch(err => { CACHE_PLANTILLAS.delete(clave); throw err; }));
  }
  return CACHE_PLANTILLAS.get(clave);
}

/* ══════════════ pestañas ══════════════ */

$$(".pestana").forEach(b => b.addEventListener("click", () => {
  $$(".pestana").forEach(x => x.classList.remove("activa"));
  $$(".panel").forEach(x => x.classList.remove("activa"));
  b.classList.add("activa");
  $("#panel-" + b.dataset.panel).classList.add("activa");
  window.scrollTo({ top: 0 });
}));
$("#btn-ir-config").addEventListener("click", () => $$(".pestana")[2].click());

/* ══════════════ listas ══════════════ */

const porRuta = ruta => ruta.split(".").reduce((o, k) => (o == null ? o : o[k]), CFG);

function rellenarListas() {
  $$("[data-lista]").forEach(sel => {
    const origen = porRuta(sel.dataset.lista);
    if (!origen) return;
    sel.innerHTML = "";
    if (Array.isArray(origen)) origen.forEach(v => sel.add(new Option(v, v)));
    else Object.entries(origen).forEach(([k, v]) =>
      sel.add(new Option(typeof v === "object" ? v.etiqueta : v, k)));
  });
  if (form.elements.esquema) form.elements.esquema.value = "2";
}

function aplicarValoresTecnicos(valores) {
  CAMPOS_TECNICOS.forEach(k => {
    const c = form.elements[k];
    const v = valores[k];
    if (!c || v == null || v === "") return;
    if (c.options && ![...c.options].some(o => o.value === String(v))) c.add(new Option(v, v));
    c.value = v;
  });
}

form.elements.seccion.addEventListener("change", e => {
  const ajuste = (CFG.por_seccion || {})[e.target.value];
  if (!ajuste) return;
  Object.entries(ajuste).forEach(([k, v]) => {
    const c = form.elements[k];
    if (c && [...c.options].some(o => o.value === v)) c.value = v;
  });
  recalcular();
});

/* ══════════════ códigos postales ══════════════ */

function pintarLocalidades() {
  const lista = $("#lista-localidades");
  lista.innerHTML = "";
  Object.keys(CFG.codigos_postales || {}).sort()
    .forEach(n => lista.appendChild(new Option(n, n)));
}

function completarCodigoPostal(prefijo) {
  const loc = form.elements[prefijo + "_localidad"];
  const cp = form.elements[prefijo + "_cp"];
  if (!loc || !cp || cp.value.trim()) return;
  const guardado = (CFG.codigos_postales || {})[loc.value.trim().toUpperCase()];
  if (guardado) {
    cp.value = guardado;
    cp.classList.add("recordado");
    setTimeout(() => cp.classList.remove("recordado"), 1500);
  }
}

["titular", "empl", "cp"].forEach(pre => {
  const c = form.elements[pre + "_localidad"];
  if (!c) return;
  c.addEventListener("change", () => completarCodigoPostal(pre));
  c.addEventListener("blur", () => completarCodigoPostal(pre));
});

function aprenderCodigosPostales(datos) {
  let cambio = false;
  for (const pre of ["titular", "empl"]) {
    const loc = String(datos[pre + "_localidad"] || "").trim().toUpperCase();
    const cp = String(datos[pre + "_cp"] || "").replace(/\D/g, "");
    if (loc && cp.length === 5 && CFG.codigos_postales[loc] !== cp) {
      CFG.codigos_postales[loc] = cp;
      cambio = true;
    }
  }
  if (cambio) { guardarAjustes(); pintarLocalidades(); pintarCodigosPostales(); }
}

/* ══════════════ mostrar y ocultar ══════════════ */

$("#mismo_domicilio").addEventListener("change", e => {
  $("#bloque-emplazamiento").hidden = e.target.checked;
});
$("#incluir_anexo_garaje").addEventListener("change", e => {
  $("#bloque-cp").hidden = !e.target.checked;
  $("#pista-cp").hidden = !e.target.checked;
});

/* ══════════════ cálculo en vivo ══════════════ */

function recalcular() {
  const datos = datosFormulario();
  const tec = valoresTecnicos(datos, CFG);
  const c = calcular(datos, tec, CFG);
  const limite = CFG.calculo.caida_maxima_porcentaje;
  const es = (n, u) => n.toFixed(2).replace(".", ",") + " " + u;

  $("#calc-i").textContent = c.intensidad ? es(c.intensidad, "A") : "—";
  $("#calc-adm").textContent = es(c.pot_max_admisible, "kW");
  $("#calc-v").textContent = c.caida_v ? es(c.caida_v, "V") : "—";
  $("#calc-p").textContent = c.caida_v ? es(c.caida_pct, "%") : "—";

  const excedido = c.caida_pct > limite;
  const flojo = c.potencia_kw > c.pot_max_admisible + 0.01;
  $("#calculo").classList.toggle("pasado", excedido || flojo);
  $("#calc-limite").textContent = flojo
    ? `El cargador pide más de lo que admite una protección de ${c.intensidad_proteccion} A`
    : excedido ? `Pasa del ${limite} % que admite la ITC-BT-52`
      : `Límite ITC-BT-52: ${limite} %`;
}

// 'input' ya salta también en los desplegables y las casillas, así que con un
// solo escuchador basta. Con los dos, cada cambio recalculaba y guardaba dos
// veces.
form.addEventListener("input", e => {
  recalcular();
  if (e.target.name === "cups") ponerDistribuidora();
  guardarBorrador();
});

function ponerDistribuidora() {
  form.elements.distribuidora.value = distribuidoraPorCups(form.elements.cups.value, CFG);
}

/* ══════════════ borrador ══════════════ */

function datosFormulario() {
  const d = {};
  new FormData(form).forEach((v, k) => { d[k] = v; });
  d.incluir_anexo_garaje = $("#incluir_anexo_garaje").checked;
  d.mismo_domicilio = $("#mismo_domicilio").checked;
  if (d.mismo_domicilio) {
    ["tipo_via", "nombre_via", "numero", "bloque", "escalera", "piso", "puerta",
      "localidad", "cp", "provincia"].forEach(k => { d["empl_" + k] = d["titular_" + k] || ""; });
  }
  return d;
}

let relojBorrador = null;
function guardarBorrador() {
  clearTimeout(relojBorrador);
  relojBorrador = setTimeout(() => escribir(CLAVE_BORRADOR, datosFormulario()), 400);
}

function restaurarBorrador() {
  const d = leer(CLAVE_BORRADOR, null);
  if (d) cargarDatos(d, false);
}

function cargarDatos(d, avisar = true) {
  aplicarValoresTecnicos(d);
  Object.entries(d).forEach(([k, v]) => {
    const campo = form.elements[k];
    if (campo && campo.type !== "checkbox") campo.value = v ?? "";
  });
  $("#incluir_anexo_garaje").checked = !!d.incluir_anexo_garaje;
  $("#bloque-cp").hidden = !d.incluir_anexo_garaje;
  $("#pista-cp").hidden = !d.incluir_anexo_garaje;
  // Antes esto se adivinaba comparando el nombre de la vía, y con dos
  // direcciones en la misma calle y distinto número cambiaba el emplazamiento
  // sin decir nada. Ahora se guarda; la comparación queda solo para borradores
  // de antes de este cambio.
  const mismo = d.mismo_domicilio !== undefined
    ? !!d.mismo_domicilio
    : (!d.empl_nombre_via || d.empl_nombre_via === d.titular_nombre_via);
  $("#mismo_domicilio").checked = mismo;
  $("#bloque-emplazamiento").hidden = mismo;
  ponerDistribuidora();
  recalcular();
  if (avisar) { $$(".pestana")[0].click(); window.scrollTo({ top: 0, behavior: "smooth" }); }
}

function ponerFechaHoy() {
  const c = form.elements.fecha;
  if (!c.value) c.value = new Date().toISOString().slice(0, 10);
}

/* ══════════════ generar ══════════════ */

form.addEventListener("submit", async e => {
  e.preventDefault();
  const btn = $("#btn-generar");
  btn.disabled = true;
  btn.textContent = "Generando…";
  $("#resultado").hidden = true;

  // Se capturan los datos una sola vez: el formulario sigue siendo editable
  // mientras se genera, y lo que se archive tiene que ser lo que salió impreso.
  const datos = datosFormulario();
  let r;
  if (!window.PDFLib || !window.JSZip) {
    r = { error: "No se han podido cargar las librerías de PDF. Comprueba la "
                 + "conexión y recarga la página." };
  } else {
    try {
      r = await generarExpediente(datos, CFG, cargarPlantilla, window.PDFLib);
    } catch (err) {
      r = { error: String(err).slice(0, 200) };
    }
  }
  btn.disabled = false;
  btn.textContent = "Generar documentos";
  mostrarResultado(r, datos);

  if (!r.error) {
    aprenderCodigosPostales(datos);
    guardarExpediente(r.carpeta, datos, r.identificador);
  }
});

function descargar(nombre, bytes, tipo = "application/pdf") {
  const url = URL.createObjectURL(new Blob([bytes], { type: tipo }));
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

async function descargarZip(r, datos) {
  const zip = new window.JSZip();
  const carpeta = zip.folder(r.carpeta);
  r.documentos.filter(d => d.ok).forEach(d => carpeta.file(d.nombre, d.bytes));
  carpeta.file("datos.json", JSON.stringify(datos || datosFormulario(), null, 2));
  const blob = await zip.generateAsync({ type: "blob" });
  descargar(r.carpeta + ".zip", blob, "application/zip");
}

function mostrarResultado(r, datos) {
  const caja = $("#resultado");
  caja.hidden = false;
  caja.classList.toggle("fallo", !!r.error);

  if (r.error) {
    caja.innerHTML = `<h3>No he podido generar el expediente</h3><p>${escapar(r.error)}</p>`;
    return;
  }

  const docs = r.documentos.map((d, i) => {
    const marca = d.ok ? '<span class="marca-ok">✓</span>' : '<span class="marca-no">✗</span>';
    const extra = d.estado ? ` — <em>${escapar(d.estado)}</em>`
      : (d.error ? ` — ${escapar(d.error)}` : "");
    const sinEscribir = (d.faltan && d.faltan.length)
      ? ` <span class="marca-no">${d.faltan.length} campos sin escribir: `
        + `${escapar(d.faltan.slice(0, 4).join(", "))}</span>` : "";
    const enlace = d.ok
      ? ` <button type="button" class="enlace" data-doc="${i}">descargar</button>` : "";
    return `<li>${marca} ${escapar(d.nombre)}${extra}${sinEscribir}${enlace}</li>`;
  }).join("");

  const avisos = (r.avisos && r.avisos.length)
    ? `<div class="avisos"><strong>Revisa esto:</strong><ul>${
      r.avisos.map(a => `<li>${escapar(a)}</li>`).join("")}</ul></div>` : "";

  const c = r.calculo || {};
  caja.innerHTML = `
    <h3>Expediente generado</h3>
    <p class="ruta">${escapar(r.carpeta)}</p>
    ${r.identificador ? `<p class="pista">Identificador del CIE:
       <b>${escapar(r.identificador)}</b></p>` : ""}
    <p class="pista">Intensidad ${String(c.intensidad).replace(".", ",")} A ·
       caída ${String(c.caida_v).replace(".", ",")} V
       (${String(c.caida_pct).replace(".", ",")} %)</p>
    <ul>${docs}</ul>
    ${avisos}
    <div class="barra-accion" style="margin-top:16px">
      <button class="principal" id="btn-zip">Descargar todo en un ZIP</button>
    </div>`;

  $("#btn-zip").addEventListener("click", () => descargarZip(r, datos).catch(err => {
    alert("No he podido armar el ZIP: " + err
      + ". Puedes descargar los documentos uno a uno.");
  }));
  $$("[data-doc]", caja).forEach(b => b.addEventListener("click", () => {
    const d = r.documentos[Number(b.dataset.doc)];
    descargar(d.nombre, d.bytes);
  }));
  caja.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

$("#btn-limpiar").addEventListener("click", () => {
  if (!confirm("¿Vaciar todos los campos del formulario?")) return;
  form.reset();
  localStorage.removeItem(CLAVE_BORRADOR);
  rellenarListas();
  aplicarValoresTecnicos(CFG.tecnica);
  form.elements.titular_provincia.value = "MADRID";
  // form.reset() devuelve las casillas a su estado inicial, pero no oculta ni
  // enseña los bloques que dependen de ellas
  $("#bloque-emplazamiento").hidden = $("#mismo_domicilio").checked;
  $("#bloque-cp").hidden = !$("#incluir_anexo_garaje").checked;
  $("#pista-cp").hidden = !$("#incluir_anexo_garaje").checked;
  ponerFechaHoy();
  $("#resultado").hidden = true;
  recalcular();
});

/* ══════════════ expedientes ══════════════ */

function guardarExpediente(carpeta, datos, identificador) {
  const lista = leer(CLAVE_EXPEDIENTES, []);
  const sinEste = lista.filter(x => x.carpeta !== carpeta);
  sinEste.unshift({ carpeta, datos, identificador: identificador || "",
                    cuando: new Date().toISOString() });
  escribir(CLAVE_EXPEDIENTES, sinEste.slice(0, 60));
  pintarExpedientes();
}

function pintarExpedientes() {
  const ul = $("#lista-expedientes");
  const lista = leer(CLAVE_EXPEDIENTES, []);
  ul.innerHTML = lista.length ? "" : '<li class="pista">Todavía no has generado ninguno.</li>';
  lista.forEach(x => {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.textContent = x.carpeta.replace(/_/g, " ");
    b.addEventListener("click", () => cargarDatos(x.datos));
    li.appendChild(b);
    ul.appendChild(li);
  });
}

$("#btn-vaciar-expedientes").addEventListener("click", () => {
  if (!confirm("¿Borrar el historial de expedientes? Los PDF que ya te descargaste no se tocan.")) return;
  localStorage.removeItem(CLAVE_EXPEDIENTES);
  pintarExpedientes();
});

/* ══════════════ configuración ══════════════ */

const ETIQUETAS_EMPRESA = {
  razon_social: "Razón social", nif: "NIF de la empresa",
  categoria: "Categoría", num_registro: "Nº registro industrial",
  instalador_nombre: "Nombre del instalador", instalador_nif: "NIF del instalador",
  instalador_num_certificado: "Nº certificado de instalador",
  tipo_via: "Tipo de vía", nombre_via: "Nombre de la vía", numero: "Número",
  piso: "Piso", puerta: "Puerta", direccion_una_linea: "Dirección en una línea",
  municipio: "Municipio", provincia: "Provincia", cp: "Código postal",
  telefono: "Teléfono", email: "Correo electrónico", lugar_firma: "Lugar de firma",
};

function pintarConfigEmpresa() {
  const caja = $("#bloque-empresa");
  caja.innerHTML = "";
  Object.entries(ETIQUETAS_EMPRESA).forEach(([k, etiqueta]) => {
    const l = document.createElement("label");
    l.className = ["razon_social", "direccion_una_linea", "instalador_nombre"].includes(k)
      ? "c6" : "c3";
    l.innerHTML = `${etiqueta}<input data-empresa="${k}" value="${escapar(CFG.empresa[k])}">`;
    caja.appendChild(l);
  });
}

function pintarCodigosPostales() {
  const caja = $("#bloque-cps");
  const libreta = CFG.codigos_postales || {};
  const claves = Object.keys(libreta).sort();
  caja.innerHTML = claves.length
    ? claves.map(k => `<span class="cp"><b>${escapar(k)}</b> ${escapar(libreta[k])}</span>`).join("")
    : '<span class="pista">Todavía no ha aprendido ninguno.</span>';
}

function avisar(donde, texto) {
  const c = $(donde);
  if (!c) return;
  c.textContent = texto;
  setTimeout(() => { c.textContent = ""; }, 5000);
}

$("#btn-guardar-config").addEventListener("click", () => {
  $$("[data-empresa]").forEach(i => { CFG.empresa[i.dataset.empresa] = i.value; });
  avisar("#aviso-config", guardarAjustes() === false ? "No se ha podido guardar." : "Guardado.");
  $("#sin-empresa").hidden = !!(CFG.empresa.razon_social || "").trim();
});

$("#btn-guardar-preset").addEventListener("click", () => {
  CAMPOS_TECNICOS.forEach(k => {
    const c = form.elements[k];
    if (c) CFG.tecnica[k] = c.value;
  });
  guardarAjustes();
  avisar("#aviso-preset", "Guardado como valores por defecto.");
});

/* ══════════════ copia de seguridad ══════════════ */

$("#btn-exportar").addEventListener("click", () => {
  const copia = {
    version: 1,
    empresa: CFG.empresa,
    tecnica: CFG.tecnica,
    codigos_postales: CFG.codigos_postales,
    expedientes: leer(CLAVE_EXPEDIENTES, []),
  };
  descargar("boletines-irve-copia.json",
    new TextEncoder().encode(JSON.stringify(copia, null, 2)), "application/json");
});

$("#btn-importar").addEventListener("click", () => $("#fichero-importar").click());
$("#fichero-importar").addEventListener("change", async e => {
  const f = e.target.files[0];
  if (!f) return;
  try {
    const c = JSON.parse(await f.text());
    if (typeof c !== "object" || c === null) throw new Error("no es una copia");
    // Se comprueba antes de tocar nada: si el historial viene mal, no quiero
    // haber sustituido ya los datos de la empresa.
    if (c.expedientes !== undefined) {
      if (!Array.isArray(c.expedientes)) throw new Error("el historial está mal");
      if (c.expedientes.some(x => !x || typeof x.carpeta !== "string")) {
        throw new Error("hay expedientes sin nombre");
      }
    }
    if (c.empresa) CFG.empresa = { ...CFG.empresa, ...c.empresa };
    if (c.tecnica) CFG.tecnica = { ...CFG.tecnica, ...c.tecnica };
    if (c.codigos_postales) CFG.codigos_postales = { ...CFG.codigos_postales, ...c.codigos_postales };
    if (Array.isArray(c.expedientes)) escribir(CLAVE_EXPEDIENTES, c.expedientes);
    guardarAjustes();
    pintarConfigEmpresa(); pintarCodigosPostales(); pintarLocalidades();
    pintarExpedientes(); aplicarValoresTecnicos(CFG.tecnica); recalcular();
    avisar("#aviso-copia", "Copia restaurada.");
    $("#sin-empresa").hidden = !!(CFG.empresa.razon_social || "").trim();
  } catch (err) {
    avisar("#aviso-copia", "Ese archivo no vale: " + String(err).slice(0, 60));
  }
  e.target.value = "";
});
