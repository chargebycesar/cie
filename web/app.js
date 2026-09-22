/* Boletines IRVE · Comunidad de Madrid — interfaz local */

let CFG = null;

const $ = (s, raiz = document) => raiz.querySelector(s);
const $$ = (s, raiz = document) => [...raiz.querySelectorAll(s)];

const form = $("#formulario");

/* Los campos técnicos que se guardan como valores por defecto. */
const CAMPOS_TECNICOS = [
  "seccion", "material", "fases", "tipo_cable", "diametro_tubo", "num_tubos",
  "conductor_proteccion", "iga_intensidad", "iga_poder_corte",
  "dif_intensidad", "dif_sensibilidad", "dif_clase", "fusible_seguridad",
  "tipo_instalacion_di", "tipo_instalacion_circuito",
];

/* ══════════════ hablar con el programa ══════════════ */

/* Toda la comunicación pasa por aquí para poder avisar de una sola manera
   cuando se ha cerrado la ventana negra del servidor. */
async function pedir(ruta, opciones) {
  try {
    const r = await fetch(ruta, opciones);
    if (!r.ok && r.status >= 500) {
      const cuerpo = await r.json().catch(() => ({}));
      throw new Error(cuerpo.error || `El programa respondió con un error ${r.status}`);
    }
    sinServidor(false);
    return await r.json();
  } catch (e) {
    if (e instanceof TypeError) {        // fetch no llegó al servidor
      sinServidor(true);
      throw new Error("No hay contacto con el programa.");
    }
    throw e;
  }
}

function sinServidor(caido) {
  const caja = $("#sin-servidor");
  if (caja) caja.hidden = !caido;
}

/* ══════════════ arranque ══════════════ */

document.addEventListener("DOMContentLoaded", async () => {
  try {
    CFG = await pedir("/api/config");
  } catch (e) {
    sinServidor(true);
    return;
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
});

/* ══════════════ pestañas ══════════════ */

$$(".pestana").forEach(b => b.addEventListener("click", () => {
  $$(".pestana").forEach(x => x.classList.remove("activa"));
  $$(".panel").forEach(x => x.classList.remove("activa"));
  b.classList.add("activa");
  $("#panel-" + b.dataset.panel).classList.add("activa");
}));

/* ══════════════ listas desplegables ══════════════ */

/* Acepta "tipos_via" y también rutas con punto como "opciones.seccion". */
function porRuta(ruta) {
  return ruta.split(".").reduce((o, k) => (o == null ? o : o[k]), CFG);
}

function rellenarListas() {
  $$("[data-lista]").forEach(sel => {
    const origen = porRuta(sel.dataset.lista);
    if (!origen) return;
    sel.innerHTML = "";
    if (Array.isArray(origen)) {
      origen.forEach(v => sel.add(new Option(v, v)));
    } else {
      Object.entries(origen).forEach(([k, v]) => {
        // tipos_cable guarda un objeto por entrada; el resto, texto suelto
        sel.add(new Option(typeof v === "object" ? v.etiqueta : v, k));
      });
    }
  });
  if (form.elements.esquema) form.elements.esquema.value = "2";
}

function aplicarValoresTecnicos(valores) {
  CAMPOS_TECNICOS.forEach(k => {
    const c = form.elements[k];
    const v = valores[k];
    if (!c || v == null || v === "") return;
    if (c.options && ![...c.options].some(o => o.value === String(v))) {
      c.add(new Option(v, v));          // valor guardado que no está en la lista
    }
    c.value = v;
  });
}

/* Al cambiar la sección se ajustan las protecciones que van con ella.
   Siguen siendo editables: esto solo evita tener que tocarlas cada vez. */
form.elements.seccion.addEventListener("change", e => {
  const ajuste = (CFG.por_seccion || {})[e.target.value];
  if (!ajuste) return;
  Object.entries(ajuste).forEach(([k, v]) => {
    const c = form.elements[k];
    if (c && [...c.options].some(o => o.value === v)) c.value = v;
  });
  recalcular();
  guardarBorrador();
});

/* ══════════════ códigos postales ══════════════ */

function pintarLocalidades() {
  const lista = $("#lista-localidades");
  lista.innerHTML = "";
  Object.keys(CFG.codigos_postales || {}).sort().forEach(n => {
    lista.appendChild(new Option(n, n));
  });
}

/* Al escribir una localidad conocida, se pone su código postal si está vacío. */
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
  if (c) {
    c.addEventListener("change", () => { completarCodigoPostal(pre); guardarBorrador(); });
    c.addEventListener("blur", () => completarCodigoPostal(pre));
  }
});

/* ══════════════ mostrar / ocultar bloques ══════════════ */

$("#mismo_domicilio").addEventListener("change", e => {
  $("#bloque-emplazamiento").hidden = e.target.checked;
});
$("#incluir_anexo_garaje").addEventListener("change", e => {
  $("#bloque-cp").hidden = !e.target.checked;
  $("#pista-cp").hidden = !e.target.checked;
});
$("#btn-reintentar").addEventListener("click", () => window.location.reload());

/* ══════════════ cálculo en vivo ══════════════ */

const num = v => {
  const n = parseFloat(String(v ?? "").replace(",", "."));
  return Number.isFinite(n) ? n : 0;
};

function recalcular() {
  const d = form.elements;
  const pkW = num(d.potencia.value) || 7.36;
  const v = num(d.tension.value) || 230;
  const L = num(d.longitud.value);
  const S = num(d.seccion.value) || 6;
  const trif = (d.tipo_suministro.value || "").toLowerCase().startsWith("tri");
  const gamma = String(d.material.value).toUpperCase().startsWith("AL")
    ? CFG.calculo.conductividad_al : CFG.calculo.conductividad_cu;

  const W = pkW * 1000;
  const I = trif ? W / (v * Math.sqrt(3)) : W / v;
  const caidaV = (L > 0 && S > 0 && v > 0) ? (trif ? 1 : 2) * L * W / (gamma * v * S) : 0;
  const pct = v ? caidaV / v * 100 : 0;
  const limite = CFG.calculo.caida_maxima_porcentaje;

  const iProt = num(d.iga_intensidad.value) || 32;
  const potAdm = (trif ? Math.sqrt(3) * v * iProt : v * iProt) / 1000;

  const es = (n, u) => n.toFixed(2).replace(".", ",") + " " + u;
  $("#calc-i").textContent = I ? es(I, "A") : "—";
  $("#calc-adm").textContent = es(potAdm, "kW");
  $("#calc-v").textContent = caidaV ? es(caidaV, "V") : "—";
  $("#calc-p").textContent = caidaV ? es(pct, "%") : "—";

  const excedido = pct > limite;
  const flojo = pkW > potAdm + 0.01;
  $("#calculo").classList.toggle("pasado", excedido || flojo);
  $("#calc-limite").textContent = flojo
    ? `El cargador pide más de lo que admite una protección de ${iProt} A`
    : excedido
      ? `Pasa del ${limite} % que admite la ITC-BT-52`
      : `Límite ITC-BT-52: ${limite} %`;
}

form.addEventListener("input", e => {
  recalcular();
  if (e.target.name === "cups") ponerDistribuidora();
  guardarBorrador();
});
form.addEventListener("change", () => { recalcular(); guardarBorrador(); });

function ponerDistribuidora() {
  const c = (form.elements.cups.value || "").replace(/\s/g, "").toUpperCase();
  const m = c.match(/^ES(\d{4})/);
  form.elements.distribuidora.value = m ? (CFG.distribuidoras[m[1]] || "") : "";
}

/* ══════════════ borrador en el navegador ══════════════ */

const CLAVE = "boletines-irve-borrador";

function datosFormulario() {
  const d = {};
  new FormData(form).forEach((v, k) => { d[k] = v; });
  d.incluir_anexo_garaje = $("#incluir_anexo_garaje").checked;
  if ($("#mismo_domicilio").checked) {
    ["tipo_via", "nombre_via", "numero", "bloque", "escalera", "piso", "puerta",
      "localidad", "cp", "provincia"].forEach(k => { d["empl_" + k] = d["titular_" + k] || ""; });
  }
  return d;
}

function guardarBorrador() {
  try { localStorage.setItem(CLAVE, JSON.stringify(datosFormulario())); } catch (e) { /* nada */ }
}

function restaurarBorrador() {
  let d;
  try { d = JSON.parse(localStorage.getItem(CLAVE) || "null"); } catch (e) { return; }
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
  const mismo = !d.empl_nombre_via || d.empl_nombre_via === d.titular_nombre_via;
  $("#mismo_domicilio").checked = mismo;
  $("#bloque-emplazamiento").hidden = mismo;
  ponerDistribuidora();
  recalcular();
  if (avisar) {
    $$(".pestana")[0].click();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
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
  btn.textContent = "Generando… (el CIE tarda unos segundos)";
  $("#resultado").hidden = true;

  let r;
  try {
    r = await pedir("/api/generar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datosFormulario()),
    });
  } catch (err) {
    r = { error: err.message };
  }
  btn.disabled = false;
  btn.textContent = "Generar documentos";
  mostrarResultado(r);

  // recargar la configuración: puede haber aprendido un código postal nuevo
  try {
    CFG = await pedir("/api/config");
    pintarLocalidades();
    pintarCodigosPostales();
    pintarExpedientes();
  } catch (e) { /* ya avisado */ }
});

function mostrarResultado(r) {
  const caja = $("#resultado");
  caja.hidden = false;
  caja.classList.toggle("fallo", !!r.error);

  if (r.error) {
    caja.innerHTML = `<h3>No he podido generar el expediente</h3><p>${r.error}</p>`;
    return;
  }

  const docs = r.documentos.map(d => {
    const marca = d.ok ? '<span class="marca-ok">✓</span>' : '<span class="marca-no">✗</span>';
    const extra = d.estado ? ` — <em>${d.estado}</em>`
      : d.error ? ` — ${d.error}`
        : d.campos ? ` — ${d.campos} campos` : "";
    return `<li>${marca} ${d.nombre}${extra}</li>`;
  }).join("");

  const avisos = (r.avisos && r.avisos.length)
    ? `<div class="avisos"><strong>Revisa esto:</strong><ul>${
      r.avisos.map(a => `<li>${a}</li>`).join("")}</ul></div>` : "";

  const c = r.calculo || {};
  caja.innerHTML = `
    <h3>Expediente generado</h3>
    <p class="ruta">${r.carpeta}</p>
    <p class="pista">Intensidad ${String(c.intensidad).replace(".", ",")} A ·
       caída ${String(c.caida_v).replace(".", ",")} V
       (${String(c.caida_pct).replace(".", ",")} %)</p>
    <ul>${docs}</ul>
    ${avisos}
    <div class="barra-accion" style="margin-top:16px">
      <button class="secundario" id="btn-abrir-esta">Abrir la carpeta</button>
    </div>`;
  $("#btn-abrir-esta").addEventListener("click", () => abrirCarpeta(r.carpeta));
  caja.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function abrirCarpeta(carpeta) {
  try {
    await pedir("/api/abrir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ carpeta }),
    });
  } catch (e) { /* el aviso ya lo pone pedir() */ }
}

$("#btn-limpiar").addEventListener("click", () => {
  if (!confirm("¿Vaciar todos los campos del formulario?")) return;
  form.reset();
  localStorage.removeItem(CLAVE);
  rellenarListas();
  aplicarValoresTecnicos(CFG.tecnica);
  form.elements.titular_provincia.value = "MADRID";
  ponerFechaHoy();
  $("#resultado").hidden = true;
  recalcular();
});

/* ══════════════ expedientes ══════════════ */

function pintarExpedientes() {
  const ul = $("#lista-expedientes");
  const lista = (CFG && CFG._expedientes) || [];
  ul.innerHTML = lista.length ? "" : '<li class="pista">Todavía no has generado ninguno.</li>';
  lista.forEach(n => {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.textContent = n.replace(/_/g, " ");
    b.addEventListener("click", async () => {
      try {
        const d = await pedir("/api/expediente/" + encodeURIComponent(n));
        if (d.error) return alert(d.error);
        cargarDatos(d);
      } catch (e) { /* ya avisado */ }
    });
    li.appendChild(b);
    ul.appendChild(li);
  });
}

$("#btn-abrir-salida").addEventListener("click", () => abrirCarpeta(""));

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
    l.className = ["razon_social", "direccion_una_linea", "instalador_nombre"].includes(k) ? "c6" : "c3";
    l.innerHTML = `${etiqueta}<input data-empresa="${k}" value="${(CFG.empresa[k] ?? "").replace(/"/g, "&quot;")}">`;
    caja.appendChild(l);
  });
}

function pintarCodigosPostales() {
  const caja = $("#bloque-cps");
  const libreta = CFG.codigos_postales || {};
  const claves = Object.keys(libreta).sort();
  caja.innerHTML = claves.length
    ? claves.map(k => `<span class="cp"><b>${k}</b> ${libreta[k]}</span>`).join("")
    : '<span class="pista">Todavía no ha aprendido ninguno.</span>';
}

async function guardarConfig(dondeAvisar, texto = "Guardado.") {
  const copia = { ...CFG };
  delete copia._expedientes;
  const aviso = $(dondeAvisar);
  try {
    const r = await pedir("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(copia),
    });
    if (aviso) aviso.textContent = r.ok ? texto : ("No se ha guardado: " + r.error);
  } catch (e) {
    if (aviso) aviso.textContent = "No se ha guardado: " + e.message;
    return false;
  }
  setTimeout(() => { if (aviso) aviso.textContent = ""; }, 5000);
  return true;
}

$("#btn-guardar-config").addEventListener("click", async () => {
  $$("[data-empresa]").forEach(i => { CFG.empresa[i.dataset.empresa] = i.value; });
  await guardarConfig("#aviso-config");
});

/* Guardar lo que hay en pantalla como valores técnicos de partida. */
$("#btn-guardar-preset").addEventListener("click", async () => {
  CAMPOS_TECNICOS.forEach(k => {
    const c = form.elements[k];
    if (c) CFG.tecnica[k] = c.value;
  });
  await guardarConfig("#aviso-preset", "Guardado como valores por defecto.");
});
