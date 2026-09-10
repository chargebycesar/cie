/* Boletines IRVE · interfaz de navegador
 *
 * Todo pasa aquí dentro: los datos del cliente no salen del ordenador.
 * Lo que guardas (empresa, valores técnicos, códigos postales y el historial)
 * vive en el almacenamiento de este navegador.
 */

import { generarExpediente, valoresTecnicos, calcular, distribuidoraPorCups } from "./motor.js";
import { buscarCodigoPostal, claveCalle, codigosDe, esCodigoPostal, municipioDe,
         normalizar } from "./cp.js";

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
    valores_fijos_mtd: CFG.valores_fijos_mtd,
    valores_fijos_cie: CFG.valores_fijos_cie,
    extras: CFG.extras,
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
    // Los valores de cada impreso se mezclan con los de fábrica, no los
    // sustituyen: así, si algún día se añade uno nuevo, aparece igual.
    CFG.valores_fijos_mtd = { ...CFG.valores_fijos_mtd, ...guardado.valores_fijos_mtd };
    CFG.valores_fijos_cie = { ...CFG.valores_fijos_cie, ...guardado.valores_fijos_cie };
    CFG.extras = { ...CFG.extras, ...guardado.extras };
  }

  rellenarListas();
  aplicarValoresTecnicos(CFG.tecnica);
  if (migrarLibreta()) guardarAjustes();
  pintarLocalidades();
  pintarConfigEmpresa();
  pintarPestanasDoc();
  pintarPanelDoc();
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

/* Un municipio puede tener muchos códigos postales, así que no se recuerdan por
   localidad -eso hacía que la segunda instalación del mismo pueblo heredara el
   código de la primera- sino por calle. Y para acertar a la primera se le puede
   preguntar al callejero oficial del IGN, que lo sabe por calle y número. */

const CAMPOS_DIRECCION = {
  titular: { via: "titular_tipo_via", nombre: "titular_nombre_via",
             numero: "titular_numero", localidad: "titular_localidad",
             provincia: "titular_provincia", cp: "titular_cp" },
  empl: { via: "empl_tipo_via", nombre: "empl_nombre_via",
          numero: "empl_numero", localidad: "empl_localidad",
          provincia: "empl_provincia", cp: "empl_cp" },
  cp: { localidad: "cp_localidad", cp: "cp_cp" },
};

const valor = nombre => {
  const c = form.elements[nombre];
  return c ? String(c.value || "").trim() : "";
};

function direccionDe(pre) {
  const c = CAMPOS_DIRECCION[pre] || {};
  return {
    tipoVia: valor(c.via), nombreVia: valor(c.nombre), numero: valor(c.numero),
    municipio: valor(c.localidad), provincia: valor(c.provincia),
  };
}

const claveDe = pre => {
  const d = direccionDe(pre);
  return claveCalle(d.municipio, d.tipoVia, d.nombreVia);
};

/* La libreta guarda calle → código postal. Lo de antes, localidad → código, se
   convierte en sugerencias del municipio: no se borra, pero deja de rellenarse
   solo, porque era justo lo que fallaba. */
function libreta() {
  return CFG.codigos_postales || (CFG.codigos_postales = {});
}

function migrarLibreta() {
  const vieja = libreta();
  let cambio = false;
  for (const [clave, cp] of Object.entries(vieja)) {
    if (clave.includes("|")) continue;              // ya es de las nuevas
    delete vieja[clave];
    vieja[`${normalizar(clave)}|`] = cp;            // solo para sugerir
    cambio = true;
  }
  return cambio;
}

function pintarLocalidades() {
  const lista = $("#lista-localidades");
  if (!lista) return;
  const nombres = [...new Set(Object.keys(libreta()).map(municipioDe))]
    .filter(Boolean).sort();
  lista.innerHTML = "";
  nombres.forEach(n => lista.appendChild(new Option(n, n)));
}

/* Las sugerencias de cada casilla: los códigos que ya has usado en ese
   municipio. Si hay más de uno, ahí se ve que hay que elegir. */
function pintarSugerencias(pre) {
  const lista = $(`#cps-${pre}`);
  if (!lista) return;
  const municipio = valor((CAMPOS_DIRECCION[pre] || {}).localidad);
  lista.innerHTML = "";
  codigosDe(libreta(), municipio)
    .forEach(cp => lista.appendChild(new Option(cp, cp)));
}

function avisarCp(texto, error = false) {
  const caja = $("#aviso-cp");
  if (!caja) return;
  caja.textContent = texto || "";
  caja.classList.toggle("error", !!error);
}

/* Al salir de la localidad o de la calle: si esa calle ya se usó, se pone su
   código. Nunca se rellena a partir del municipio solo. */
function completarCodigoPostal(pre) {
  pintarSugerencias(pre);
  const campo = form.elements[(CAMPOS_DIRECCION[pre] || {}).cp];
  if (!campo || campo.value.trim()) return;
  const guardado = libreta()[claveDe(pre)];
  if (!esCodigoPostal(guardado)) return;
  campo.value = guardado;
  campo.classList.add("recordado");
  setTimeout(() => campo.classList.remove("recordado"), 1500);
}

Object.keys(CAMPOS_DIRECCION).forEach(pre => {
  const c = CAMPOS_DIRECCION[pre];
  [c.localidad, c.nombre, c.via].filter(Boolean).forEach(nombre => {
    const campo = form.elements[nombre];
    if (!campo) return;
    campo.addEventListener("change", () => completarCodigoPostal(pre));
    campo.addEventListener("blur", () => completarCodigoPostal(pre));
  });
});

/* El botón: se lo pregunta al callejero oficial. Es lo único de la aplicación
   que sale de este ordenador, por eso hay que pulsarlo a mano y por eso solo
   sale la dirección: ni el nombre, ni el DNI, ni el teléfono de nadie. */
$$(".buscar-cp").forEach(boton => {
  boton.addEventListener("click", async () => {
    const pre = boton.dataset.cp;
    const campo = form.elements[(CAMPOS_DIRECCION[pre] || {}).cp];
    const direccion = direccionDe(pre);
    boton.disabled = true;
    const antes = boton.textContent;
    boton.textContent = "…";
    avisarCp("Preguntando al callejero del IGN. Solo sale la dirección.");
    try {
      const r = await buscarCodigoPostal(direccion);
      if (!r.ok) {
        avisarCp(`No he podido: ${r.motivo}. Escríbelo a mano.`, true);
        return;
      }
      const [primera, ...otras] = r.opciones;
      if (campo) campo.value = primera.cp;
      let cambio = apuntarCodigo(claveDe(pre), primera.cp);
      // Los demás códigos de esa calle se apuntan como sugerencia del
      // municipio, para tenerlos a mano la próxima vez.
      r.opciones.forEach(o => {
        cambio = apuntarCodigo(`${normalizar(o.municipio)}|`, o.cp) || cambio;
      });
      if (cambio) { guardarAjustes(); pintarLocalidades(); pintarCodigosPostales(); }
      pintarSugerencias(pre);
      // Si no encuentra tu portal usa el más cercano de la calle, y eso hay
      // que decirlo: en una calle larga el código cambia a mitad.
      const donde = primera.exacto
        ? primera.direccion
        : `${primera.direccion}, que es el portal más cercano que conoce`;
      avisarCp(otras.length
        ? `${primera.cp}, por ${donde}. Esa calle también tiene `
          + `${otras.map(o => o.cp).join(" y ")}: comprueba cuál es tu portal.`
        : `${primera.cp}, por ${donde}.`);
    } finally {
      boton.disabled = false;
      boton.textContent = antes;
    }
  });
});

function apuntarCodigo(clave, cp) {
  if (!clave || !esCodigoPostal(cp)) return false;
  if (libreta()[clave] === cp) return false;
  libreta()[clave] = cp;
  return true;
}

/* Al generar el expediente se apunta el código de cada calle usada. */
function aprenderCodigosPostales() {
  let cambio = false;
  for (const pre of ["titular", "empl"]) {
    const cp = valor((CAMPOS_DIRECCION[pre] || {}).cp).replace(/\D/g, "");
    const municipio = normalizar(valor(CAMPOS_DIRECCION[pre].localidad));
    cambio = apuntarCodigo(claveDe(pre), cp) || cambio;
    if (municipio) cambio = apuntarCodigo(`${municipio}|`, cp) || cambio;
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
    aprenderCodigosPostales();
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
  const guardados = libreta();
  // Las entradas que acaban en «|» son solo del municipio: se guardan para
  // sugerir, pero no rellenan nada. Aquí se enseñan las calles, que son las
  // que sirven.
  const calles = Object.keys(guardados).filter(k => !k.endsWith("|")).sort();
  caja.innerHTML = calles.length
    ? calles.map(k => {
      const [municipio, via] = k.split("|");
      return `<span class="cp"><b>${escapar(guardados[k])}</b> `
        + `${escapar(via)} · ${escapar(municipio)}</span>`;
    }).join("")
    : '<span class="pista">Todavía no ha aprendido ninguna.</span>';
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

/* ══════════════ ajustes por documento ══════════════ */

/* Una pestaña por impreso. Arriba, lo que la aplicación pone siempre, con su
   valor de fábrica -el de un punto de recarga corriente-. Abajo, cualquier
   otro campo del impreso, para no tener que tocar el programa cuando algún
   expediente pida algo distinto. */
const DOCS_CONFIG = [
  { id: "MTD.pdf", titulo: "MTD", fijos: "valores_fijos_mtd" },
  { id: "CIE", titulo: "CIE", fijos: "valores_fijos_cie" },
  { id: "ANEXO_IVE.pdf", titulo: "Anexo IVE" },
  { id: "UNIFILAR.pdf", titulo: "Unifilar" },
  { id: "SOLICITUD.pdf", titulo: "Solicitud" },
  { id: "AUTORIZACION.pdf", titulo: "Autorización" },
  { id: "ANEXO_GARAJE.pdf", titulo: "Anexo garaje" },
];

const ETIQUETAS_FIJOS = {
  uso: "Uso", grado_electrificacion: "Grado de electrificación",
  uso_instalacion: "Uso de la instalación", memoria_por: "Memoria por",
  punto_conexion: "Punto de conexión", tipo_acometida: "Tipo de acometida",
  material_acometida: "Material de la acometida", cgp_tipo: "C.G.P. tipo",
  cgp_in_base: "C.G.P. In base", cgp_in_cartucho: "C.G.P. In cartucho",
  cgp_esquema: "C.G.P. esquema", lga_seccion: "L.G.A. sección",
  lga_material: "L.G.A. material", igm_nominal: "I.G.M. nominal",
  igm_poder_corte: "I.G.M. poder de corte",
  num_derivaciones: "Nº de derivaciones", modulo_tipo: "Módulo, tipo",
  modulo_situacion: "Módulo, situación", tierra_tipo: "Tierra, tipo",
  tierra_electrodos: "Tierra, electrodos",
  tierra_linea_enlace: "Tierra, línea de enlace",
  presupuesto_materiales: "Presupuesto, materiales (€)",
  presupuesto_mano_obra: "Presupuesto, mano de obra (€)",
  presupuesto_total: "Presupuesto, total (€)",
  num_suministros_monofasicos: "Nº de suministros monofásicos",
  emplazamiento_planta_baja: "Emplazamiento: planta baja",
  ubicacion_centralizacion_modular: "Ubicación: centralización modular",
  adjunta_esquema_unifilar: "Se adjunta: esquema unifilar",
  adjunta_planos_planta: "Se adjunta: planos de planta",
  adjunta_croquis_trazado: "Se adjunta: croquis del trazado",
  adjunta_otros: "Se adjunta: otros",
  actuacion: "Actuación", tipo_instalacion: "Tipo de instalación",
  aforo: "Aforo", superficie: "Superficie (m²)",
  pot_ampliada: "Potencia ampliada", pot_original: "Potencia original",
  esquema_distribucion: "Esquema de distribución",
  prot_sobretensiones: "Protección de sobretensiones",
  int_diferencial: "Interruptor diferencial", documentacion: "Documentación",
  rd1890: "Aplica el RD 1890/2008", itc_bt_51: "Aplica la ITC-BT-51",
  resistencia_tierra: "Resistencia de puesta a tierra (Ω)",
  resistencia_aislamiento: "Resistencia de aislamiento (MΩ)",
  otras_verificaciones: "Otras verificaciones",
};

const etiquetaFija = k => ETIQUETAS_FIJOS[k]
  || (k.charAt(0).toUpperCase() + k.slice(1)).replace(/_/g, " ");

let DOC_ACTIVO = DOCS_CONFIG[0].id;
let CAMPOS_IMPRESOS = null;

/* La lista de campos de cada impreso, con lo que pone escrito al lado. La
   genera herramientas/indice_campos.py y solo se carga si hace falta, que son
   120 KB y la mayoría de las veces no se abre esta pantalla. */
async function camposDelImpreso(archivo) {
  if (CAMPOS_IMPRESOS === null) {
    try {
      CAMPOS_IMPRESOS = await (await fetch("plantillas/campos.json")).json();
    } catch (e) {
      CAMPOS_IMPRESOS = {};
    }
  }
  return CAMPOS_IMPRESOS[archivo] || [];
}

function pintarPestanasDoc() {
  const caja = $("#pestanas-doc");
  if (!caja) return;
  caja.innerHTML = "";
  DOCS_CONFIG.forEach(d => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = d.titulo;
    b.className = d.id === DOC_ACTIVO ? "activa" : "";
    b.addEventListener("click", () => {
      guardarPanelDoc();          // no perder lo escrito al cambiar de pestaña
      DOC_ACTIVO = d.id;
      pintarPestanasDoc();
      pintarPanelDoc();
    });
    caja.appendChild(b);
  });
}

async function pintarPanelDoc() {
  const caja = $("#panel-doc");
  if (!caja) return;
  const doc = DOCS_CONFIG.find(d => d.id === DOC_ACTIVO) || DOCS_CONFIG[0];
  caja.innerHTML = "";

  // --- lo que la aplicación pone siempre
  if (doc.fijos) {
    const valores = CFG[doc.fijos] || (CFG[doc.fijos] = {});
    const rejilla = document.createElement("div");
    rejilla.className = "rejilla";
    Object.keys(valores).forEach(k => {
      const v = valores[k];
      const l = document.createElement("label");
      if (typeof v === "boolean") {
        l.className = "c4 casilla";
        l.innerHTML = '<input type="checkbox" data-fijo="' + escapar(k) + '"'
          + (v ? " checked" : "") + "> " + escapar(etiquetaFija(k));
      } else {
        l.className = "c4";
        l.innerHTML = escapar(etiquetaFija(k))
          + '<input data-fijo="' + escapar(k) + '" value="' + escapar(v) + '">';
      }
      rejilla.appendChild(l);
    });
    caja.appendChild(rejilla);
  } else {
    const p = document.createElement("p");
    p.className = "ayuda";
    p.textContent = "Este impreso se rellena entero con los datos del cliente. "
      + "Abajo puedes añadir cualquier otro campo suyo.";
    caja.appendChild(p);
  }

  // --- cualquier otro campo del impreso
  const extras = CFG.extras || (CFG.extras = {});
  const mios = extras[doc.id] || (extras[doc.id] = {});
  const campos = doc.id === "CIE" ? [] : await camposDelImpreso(doc.id);
  const porNombre = {};
  campos.forEach(c => { porNombre[c.n] = c; });

  const zona = document.createElement("div");
  zona.className = "extras";
  zona.innerHTML = "<h3>Otros campos de este impreso</h3>"
    + '<p class="ayuda">' + (doc.id === "CIE"
      ? "Escribe la celda del certificado (por ejemplo A28) y lo que quieras "
        + "que ponga."
      : "Elige el campo y escribe lo que quieras que ponga. En una casilla, "
        + "escribe <strong>sí</strong> o <strong>no</strong>.")
    + "</p>";

  Object.keys(mios).forEach(nombre => {
    const valor = mios[nombre];
    const c = porNombre[nombre];
    const fila = document.createElement("div");
    fila.className = "fila-extra";
    fila.innerHTML =
      '<span class="campo">' + escapar(c && c.e ? c.e : nombre) + "</span>"
      + '<span class="nombre">' + escapar(nombre)
      + (c ? " · pág. " + c.p : "") + "</span>"
      + (typeof valor === "boolean"
        ? '<label class="casilla"><input type="checkbox" data-extra="'
          + escapar(nombre) + '"' + (valor ? " checked" : "") + "> marcada</label>"
        : '<input type="text" data-extra="' + escapar(nombre)
          + '" value="' + escapar(valor) + '">')
      + '<button type="button" data-quitar="' + escapar(nombre)
      + '" title="Quitar">×</button>';
    zona.appendChild(fila);
  });

  const anadir = document.createElement("div");
  anadir.className = "anadir-extra";
  if (doc.id === "CIE") {
    anadir.innerHTML = '<input id="extra-nombre" placeholder="Celda, p. ej. A28">'
      + '<input id="extra-valor" placeholder="Lo que debe poner">'
      + '<button type="button" class="secundario" id="btn-anadir-extra">Añadir</button>';
  } else {
    const libres = campos.filter(c => !(c.n in mios) && c.t !== "otro");
    const opciones = libres.map(c => {
      const texto = (c.e ? c.e + " — " : "") + c.n + " · pág. " + c.p
        + (c.t === "casilla" ? " · casilla" : "");
      return '<option value="' + escapar(c.n) + '">' + escapar(texto) + "</option>";
    }).join("");
    // Un impreso puede tener 1.600 campos: sin un buscador no hay quien
    // encuentre el suyo en el desplegable.
    anadir.innerHTML = '<input id="extra-buscar" placeholder="Buscar…">'
      + '<select id="extra-nombre"><option value="">'
      + "Elige un campo (" + libres.length + ")</option>" + opciones + "</select>"
      + '<input id="extra-valor" placeholder="Lo que debe poner">'
      + '<button type="button" class="secundario" id="btn-anadir-extra">Añadir</button>';
  }
  zona.appendChild(anadir);
  caja.appendChild(zona);

  const buscar = $("#extra-buscar");
  if (buscar) {
    const sel = $("#extra-nombre");
    const todas = [...sel.options];
    buscar.addEventListener("input", () => {
      const q = buscar.value.trim().toLowerCase();
      const vistas = q
        ? todas.filter((o, i) => i === 0 || o.textContent.toLowerCase().includes(q))
        : todas;
      sel.innerHTML = "";
      vistas.forEach(o => sel.appendChild(o));
      vistas[0].textContent = q
        ? "Elige un campo (" + (vistas.length - 1) + " de " + (todas.length - 1) + ")"
        : "Elige un campo (" + (todas.length - 1) + ")";
    });
  }

  zona.querySelectorAll("[data-quitar]").forEach(b => {
    b.addEventListener("click", () => {
      guardarPanelDoc();
      delete (CFG.extras[doc.id] || {})[b.dataset.quitar];
      guardarAjustes();
      pintarPanelDoc();
    });
  });

  $("#btn-anadir-extra").addEventListener("click", () => {
    const nombre = ($("#extra-nombre").value || "").trim();
    const valor = ($("#extra-valor").value || "").trim();
    if (!nombre) { avisar("#aviso-doc", "Elige antes un campo."); return; }
    guardarPanelDoc();
    const bajo = valor.toLowerCase();
    const c = porNombre[nombre];
    const esCasilla = (c && c.t === "casilla")
      || ["sí", "si", "no"].indexOf(bajo) !== -1;
    CFG.extras[doc.id][nombre] = esCasilla
      ? ["no", "", "0"].indexOf(bajo) === -1
      : valor;
    guardarAjustes();
    pintarPanelDoc();
    avisar("#aviso-doc", "Añadido.");
  });
}

/* Recoge lo que hay escrito en el panel. Se llama al guardar y también al
   cambiar de pestaña, para no perder nada por el camino. */
function guardarPanelDoc() {
  const doc = DOCS_CONFIG.find(d => d.id === DOC_ACTIVO);
  if (!doc || !$("#panel-doc")) return;
  if (doc.fijos) {
    const valores = CFG[doc.fijos] || (CFG[doc.fijos] = {});
    $$("#panel-doc [data-fijo]").forEach(i => {
      valores[i.dataset.fijo] = i.type === "checkbox" ? i.checked : i.value;
    });
  }
  const extras = CFG.extras || (CFG.extras = {});
  const mios = extras[doc.id] || {};
  $$("#panel-doc [data-extra]").forEach(i => {
    mios[i.dataset.extra] = i.type === "checkbox" ? i.checked : i.value;
  });
  extras[doc.id] = mios;
}

$("#btn-guardar-doc").addEventListener("click", () => {
  guardarPanelDoc();
  avisar("#aviso-doc",
    guardarAjustes() === false ? "No se ha podido guardar." : "Guardado.");
});

/* ══════════════ copia de seguridad ══════════════ */

$("#btn-exportar").addEventListener("click", () => {
  const copia = {
    version: 2,
    empresa: CFG.empresa,
    tecnica: CFG.tecnica,
    codigos_postales: CFG.codigos_postales,
    valores_fijos_mtd: CFG.valores_fijos_mtd,
    valores_fijos_cie: CFG.valores_fijos_cie,
    extras: CFG.extras,
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
    if (c.valores_fijos_mtd)
      CFG.valores_fijos_mtd = { ...CFG.valores_fijos_mtd, ...c.valores_fijos_mtd };
    if (c.valores_fijos_cie)
      CFG.valores_fijos_cie = { ...CFG.valores_fijos_cie, ...c.valores_fijos_cie };
    if (c.extras) CFG.extras = { ...CFG.extras, ...c.extras };
    if (c.codigos_postales) CFG.codigos_postales = { ...CFG.codigos_postales, ...c.codigos_postales };
    if (Array.isArray(c.expedientes)) escribir(CLAVE_EXPEDIENTES, c.expedientes);
    guardarAjustes();
    pintarConfigEmpresa(); pintarPestanasDoc(); pintarPanelDoc();
    pintarCodigosPostales(); pintarLocalidades();
    pintarExpedientes(); aplicarValoresTecnicos(CFG.tecnica); recalcular();
    avisar("#aviso-copia", "Copia restaurada.");
    $("#sin-empresa").hidden = !!(CFG.empresa.razon_social || "").trim();
  } catch (err) {
    avisar("#aviso-copia", "Ese archivo no vale: " + String(err).slice(0, 60));
  }
  e.target.value = "";
});
