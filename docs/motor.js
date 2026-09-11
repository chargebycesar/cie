/* Motor de generación de boletines IRVE · Comunidad de Madrid
 *
 * Portado de nucleo.py. No toca el DOM: recibe los datos y las plantillas y
 * devuelve los PDF ya rellenos, así que sirve igual en el navegador que en
 * Node para las pruebas.
 */

import { t, coma, punto, mayus, sinAcentos, limpiarParaPdf } from "./util.js?v=202609111012";
import { rellenarPdf } from "./relleno.js?v=202609111012";
import { generarCie } from "./cie.js?v=202609111012";

export const MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
  "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"];

const LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE";
const LETRAS_CIF = "ABCDEFGHJKLMNPQRSUVW";
const LETRAS_CUPS = "TRWAGMYFPDXBNJZSQVHLCKE";

/* ══════════════ utilidades ══════════════ */

export function nombreCarpeta(datos) {
  const partes = [datos.titular_apellido1, datos.titular_apellido2, datos.titular_nombre]
    .map(t).filter(Boolean).join(" ") || "SIN NOMBRE";
  const base = sinAcentos(partes).toUpperCase()
    .replace(/[^A-Z0-9 ]+/g, "").trim().replace(/\s+/g, "_");
  return `${base}_${t(datos.fecha) || new Date().toISOString().slice(0, 10)}`;
}

export function direccionUnaLinea(pre, datos) {
  return ["_tipo_via", "_nombre_via", "_numero", "_bloque", "_escalera", "_piso", "_puerta"]
    .map(s => t(datos[pre + s])).filter(Boolean).join(" ");
}

/* Solo la calle y el número. El garaje es el edificio, no un piso: en el anexo
   de la inspección periódica no van ni el portal, ni la escalera, ni el piso ni
   la puerta, que son de la vivienda del cliente. */
export function direccionDelEdificio(pre, datos) {
  return ["_tipo_via", "_nombre_via", "_numero"]
    .map(s => t(datos[pre + s])).filter(Boolean).join(" ");
}

export function textoPlaza(datos) {
  const piezas = [];
  if (t(datos.plaza_numero)) piezas.push(`PLAZA ${t(datos.plaza_numero)}`);
  if (t(datos.plaza_planta)) piezas.push(`PLANTA ${t(datos.plaza_planta)}`);
  return piezas.join(", ");
}

export function emplazamientoConPlaza(datos) {
  const base = direccionUnaLinea("empl", datos);
  const plaza = textoPlaza(datos);
  if (base && plaza) return `${base} · ${plaza}`;
  return base || plaza;
}

export function partesFecha(iso) {
  let d = new Date();
  if (iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso).trim());
    if (m) d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }
  return {
    dia: String(d.getDate()),
    mes: MESES[d.getMonth()],
    anio: String(d.getFullYear()),
    fecha: d,
    corta: `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`,
  };
}

/* ══════════════ comprobaciones ══════════════ */

export function validarNif(nif) {
  const c = t(nif).replace(/[\s.-]/g, "").toUpperCase();
  if (!c) return null;
  if (/^\d{8}[A-Z]$/.test(c)) return c[8] === LETRAS_DNI[Number(c.slice(0, 8)) % 23];
  if (/^[XYZ]\d{7}[A-Z]$/.test(c)) {
    const n = String("XYZ".indexOf(c[0])) + c.slice(1, 8);
    return c[8] === LETRAS_DNI[Number(n) % 23];
  }
  if (/^[A-Z]\d{7}[0-9A-Z]$/.test(c) && LETRAS_CIF.includes(c[0])) {
    let pares = 0, impares = 0;
    for (const i of [2, 4, 6]) pares += Number(c[i]);
    for (const i of [1, 3, 5, 7]) {
      const d = Number(c[i]) * 2;
      impares += Math.floor(d / 10) + (d % 10);
    }
    const resto = (10 - ((pares + impares) % 10)) % 10;
    return c[8] === String(resto) || c[8] === "JABCDEFGHI"[resto];
  }
  return false;
}

export function validarCups(cups) {
  const c = t(cups).replace(/\s/g, "").toUpperCase();
  if (!c) return { valido: null, texto: "" };
  if (!/^ES\d{16}[A-Z]{2}[A-Z0-9]?$/.test(c)) {
    return { valido: false, texto: "ERROR: CUPS NO VÁLIDO" };
  }
  // 16 cifras se pasan del entero seguro de JavaScript: hay que usar BigInt
  const resto = Number(BigInt(c.slice(2, 18)) % 529n);
  const esperado = LETRAS_CUPS[Math.floor(resto / 23)] + LETRAS_CUPS[resto % 23];
  if (esperado !== c.slice(18, 20)) return { valido: false, texto: "ERROR: CUPS NO VÁLIDO" };
  return { valido: true, texto: "CUPS CORRECTO" };
}

export function distribuidoraPorCups(cups, cfg) {
  const m = /^ES(\d{4})/.exec(t(cups).replace(/\s/g, "").toUpperCase());
  return m ? (cfg.distribuidoras[m[1]] || "") : "";
}

/* ══════════════ datos técnicos y cálculos ══════════════ */

export function valoresTecnicos(datos, cfg) {
  const tec = { ...cfg.tecnica };
  for (const k of Object.keys(tec)) {
    if (datos[k] !== undefined && datos[k] !== null && datos[k] !== "") tec[k] = t(datos[k]);
  }
  const cable = (cfg.tipos_cable || {})[tec.tipo_cable] || {};
  tec.aislamiento = cable.aislamiento || "0.45/0.75";
  tec.aislamiento_circuito = tec.aislamiento;

  const fases = tec.fases || "2";
  tec.iga_fases = fases;
  tec.dif_fases = fases;
  tec.conductores_x_seccion = `${fases}X${tec.seccion}`;
  tec.iga_texto = `${fases}X${tec.iga_intensidad}`;
  tec.cable_texto = `${cable.texto || "CONDUCTORES"}, ${fases}*${tec.seccion}mm2`;
  tec.aislamiento_texto = cable.aislamiento_texto || `${tec.aislamiento} kV`;
  // En el unifilar se cuentan también el neutro y la tierra
  tec.conductores_unifilar = String(Number(fases) + 1);
  return tec;
}

export function calcular(datos, tec, cfg) {
  const avisos = [];
  // OJO: Number("") vale 0, asi que hay que descartar la cadena vacia antes,
  // o una tension sin rellenar daria una intensidad infinita.
  const num = (v, x) => {
    const s = String(v ?? "").trim().replace(",", ".");
    if (!s) return x;
    const n = Number(s);
    return Number.isFinite(n) ? n : x;
  };
  const pKw = num(datos.potencia, 7.36);
  const v = num(datos.tension, 230);
  const longitud = num(datos.longitud, 0);
  const seccion = num(tec.seccion, 6);

  const material = t(tec.material).toUpperCase();
  const gamma = Number(material.startsWith("AL")
    ? cfg.calculo.conductividad_al : cfg.calculo.conductividad_cu);
  const trifasico = t(datos.tipo_suministro).toLowerCase().startsWith("tri");
  const w = pKw * 1000;

  const intensidad = v > 0 ? (trifasico ? w / (v * Math.sqrt(3)) : w / v) : 0;
  const caidaV = (longitud > 0 && seccion > 0 && v > 0)
    ? (trifasico ? 1 : 2) * longitud * w / (gamma * v * seccion) : 0;
  const caidaPct = v ? caidaV / v * 100 : 0;
  const limite = Number(cfg.calculo.caida_maxima_porcentaje);

  if (caidaPct > limite) {
    avisos.push(`La caída de tensión calculada es ${caidaPct.toFixed(2)} %, por encima `
      + `del ${limite} % que admite la ITC-BT-52. Sube la sección o acorta la línea.`);
  }
  if (longitud <= 0) {
    avisos.push("No has indicado la longitud de la línea, así que la caída de tensión "
      + "sale 0 y los campos de longitud quedan vacíos.");
  }

  const iProteccion = num(tec.iga_intensidad, 32);
  const potMaxAdm = (trifasico ? Math.sqrt(3) * v * iProteccion : v * iProteccion) / 1000;

  return {
    avisos, potencia_kw: pKw, tension: v, longitud, seccion, gamma, trifasico,
    intensidad, caida_v: caidaV, caida_pct: caidaPct,
    caida_max_v: v * limite / 100,
    intensidad_proteccion: iProteccion,
    pot_max_admisible: potMaxAdm,
  };
}

/* ══════════════ memoria descriptiva ══════════════ */

const RENGLONES_MEMORIA = 23;
const ANCHO_MEMORIA = 74;

function partir(texto, ancho) {
  const palabras = String(texto).split(/\s+/).filter(Boolean);
  const lineas = [];
  let actual = "";
  for (let p of palabras) {
    // una palabra sola mas larga que el renglon se corta, o se saldria del papel
    while (p.length > ancho) {
      if (actual) { lineas.push(actual); actual = ""; }
      lineas.push(p.slice(0, ancho));
      p = p.slice(ancho);
    }
    if (!actual) actual = p;
    else if ((actual + " " + p).length <= ancho) actual += " " + p;
    else { lineas.push(actual); actual = p; }
  }
  if (actual) lineas.push(actual);
  return lineas;
}

export function lineasDescripcion(datos, tec, calc) {
  const plaza = t(datos.plaza_numero);
  const planta = t(datos.plaza_planta);
  const desc = t(datos.descripcion_punto) || "PUNTO DE RECARGA V.E. TIPO 2";
  const origen = t(datos.origen_linea) || "CENTRALIZACIÓN DE CONTADORES";

  let cabecera;
  if (/\d[\d.,]*\s*k\s*w/i.test(desc)) {
    cabecera = `INSTALACIÓN DE ${desc}, DESDE ${origen}`;
  } else {
    cabecera = `INSTALACIÓN DE ${desc}, ${punto(calc.potencia_kw)} kW, DESDE ${origen}`;
  }
  if (plaza) cabecera += `, HASTA PLAZA DE GARAJE Nº ${plaza}`;
  if (planta) cabecera += `, EN PLANTA ${planta}`;
  cabecera += ".";

  let lineas = partir(cabecera.toUpperCase(), ANCHO_MEMORIA);
  lineas = lineas.concat([
    `CONDUCTORES: ${tec.cable_texto}`,
    "CUADRO DE PUNTO DE RECARGA:",
    `IGA: ${tec.iga_fases}*${tec.iga_intensidad}A; 2P CURVA C`,
    `DIF: ${tec.dif_fases}*${tec.dif_intensidad}A/${tec.dif_sensibilidad}mA; `
      + `2P CLASE ${tec.dif_clase} "SI"`,
    "PROTECTOR SOBRETENSIONES TRANSITORIAS Y PERMANENTES",
  ]);

  const extra = t(datos.observaciones);
  if (extra) {
    lineas.push("");
    for (const parrafo of extra.split("\n")) {
      lineas = lineas.concat(partir(parrafo, ANCHO_MEMORIA) || [""]);
    }
  }
  return lineas.slice(0, RENGLONES_MEMORIA);
}

/* ══════════════ mapas de campos ══════════════ */

export function mapaMtd(datos, cfg, tec, calc) {
  const e = cfg.empresa || {};
  const f = cfg.valores_fijos_mtd || {};
  const { dia, mes, anio } = partesFecha(datos.fecha);
  const vacio = calc.caida_v ? punto(calc.caida_v) : "";
  const largo = calc.longitud ? punto(calc.longitud) : "";

  const m = {
    // página 1 · datos administrativos
    Texto1: t(datos.num_expediente),
    Texto2: t(datos.titular_nif),
    Texto3: t(datos.titular_nombre),
    Texto4: t(datos.titular_apellido1),
    Texto5: t(datos.titular_apellido2),
    Texto6: direccionUnaLinea("titular", datos),
    Texto7: t(datos.titular_localidad),
    Texto8: t(datos.titular_cp),
    Texto9: emplazamientoConPlaza(datos),
    Texto10: t(datos.empl_localidad),
    Texto11: t(datos.empl_cp),
    Texto12: f.uso,
    // página 1 · características generales
    Texto13: punto(calc.tension, 0),
    Texto15: f.grado_electrificacion,
    Texto17: f.memoria_por,
    Texto19: f.uso_instalacion,
    Texto21: f.punto_conexion,
    Texto22: f.tipo_acometida,
    Texto24: f.material_acometida,
    Texto25: f.cgp_tipo,
    Texto26: f.cgp_in_base,
    Texto27: f.cgp_in_cartucho,
    Texto28: f.lga_seccion,
    Texto29: f.lga_material,
    Texto30: tec.seccion,
    Texto31: tec.material,
    Texto32: f.igm_nominal,
    Texto33: f.igm_poder_corte,
    Texto34: f.num_derivaciones,
    // Presupuesto. Es obligatorio en el impreso. Dos columnas -Instalaciones
    // Interior y TOTAL- por tres filas: materiales, mano de obra y total.
    Texto217: f.presupuesto_materiales, Texto219: f.presupuesto_materiales,
    Texto224: f.presupuesto_mano_obra, Texto226: f.presupuesto_mano_obra,
    Texto231: f.presupuesto_total, Texto233: f.presupuesto_total,
    // Datos tecnicos del punto de medida. Venian puestos en la plantilla,
    // heredados de otro trabajo; ahora salen porque se han configurado.
    Texto252: f.num_suministros_monofasicos,
    Texto259: f.emplazamiento_planta_baja,
    Texto268: f.ubicacion_centralizacion_modular,
    Texto36: f.modulo_tipo,
    Texto37: f.modulo_situacion,
    Texto38: tec.iga_texto,
    Texto39: tec.dif_intensidad,
    Texto40: tec.dif_sensibilidad,
    Texto41: "X",
    Texto44: f.tierra_electrodos,
    Texto46: f.tierra_linea_enlace,
    Texto47: tec.conductor_proteccion,
    // página 1 · empresa instaladora
    Texto35: e.instalador_nombre,
    Texto49: e.instalador_num_certificado,
    Texto50: `${t(e.tipo_via)} ${t(e.nombre_via)}`.trim(),
    Texto51: e.numero,
    Texto52: e.municipio,
    Texto55: e.cp,
    Texto53: e.telefono,
    Texto56: e.email,
    Texto70: e.instalador_nombre,
    Texto71: e.lugar_firma,
    Texto72: dia,
    Texto73: mes,
    Texto74: anio,
    // página 2 · previsión de cargas
    Texto191: t(datos.descripcion_punto) || "PUNTO DE RECARGA V.E. TIPO 2",
    Texto194: punto(calc.potencia_kw),
    Texto195: punto(calc.potencia_kw),
    Texto211: punto(calc.potencia_kw),
    Texto212: punto(calc.potencia_kw),
    // página 3 · derivaciones individuales
    Texto273: "IRVE",
    Texto274: "1",
    Texto275: punto(calc.potencia_kw),
    Texto276: punto(calc.pot_max_admisible),
    Texto277: tec.iga_fases,
    Texto278: tec.seccion,
    Texto279: tec.material,
    Texto280: tec.aislamiento,
    Texto281: vacio,
    Texto282: tec.fusible_seguridad,
    // página 3 · dispositivos de mando y protección
    Texto313: "IRVE",
    Texto314: tec.iga_fases,
    Texto315: tec.seccion,
    Texto316: "X",
    Texto318: tec.iga_fases,
    Texto319: tec.iga_intensidad,
    Texto320: tec.iga_poder_corte,
    Texto321: tec.dif_fases,
    Texto322: tec.dif_intensidad,
    Texto323: tec.dif_sensibilidad,
    // página 4 · el punto de recarga va en "Otras instalaciones", fila 26
    Texto790: "IRVE",
    Texto791: punto(calc.potencia_kw),
    Texto792: punto(calc.tension, 0),
    Texto793: punto(calc.intensidad, 0),
    Texto794: tec.conductores_x_seccion,
    Texto795: tec.material,
    Texto796: tec.aislamiento,
    Texto797: tec.tipo_instalacion_di,
    Texto799: tec.diametro_tubo,
    Texto800: tec.num_tubos,
    Texto801: largo,
    Texto802: vacio,
    Texto803: punto(calc.pot_max_admisible),
    Texto804: punto(calc.potencia_kw),
    Texto805: tec.fusible_seguridad,
    Texto806: tec.iga_intensidad,
    Texto807: tec.dif_intensidad,
    // página 5 · circuitos internos
    Texto1518: punto(calc.potencia_kw),
    Texto1519: punto(calc.tension, 0),
    Texto1520: punto(calc.intensidad, 0),
    Texto1521: tec.conductores_x_seccion.toLowerCase(),
    Texto1522: tec.material,
    Texto1523: tec.aislamiento_circuito,
    Texto1524: tec.tipo_instalacion_circuito,
    Texto1525: largo,
    Texto1526: vacio,
    Texto1527: punto(calc.pot_max_admisible),
    Texto1528: punto(calc.potencia_kw),
    Texto1529: tec.fusible_seguridad,
  };

  // la plantilla trae la fila 4 rellena: se vacía para que no salga dos veces
  m.Texto416 = "";
  for (let n = 399; n <= 415; n++) m["Texto" + n] = "";

  lineasDescripcion(datos, tec, calc).forEach((linea, i) => {
    m["Texto" + (1590 + i)] = linea;
  });

  return {
    mapa: m,
    casillas: {
      "Casilla de verificación69": true,
      "Casilla de verificación70": false,
      // "Documentación que se adjunta", última página. Venían marcadas en la
      // plantilla, heredadas de otro trabajo; ahora salen porque se han
      // configurado. Fila de arriba: unifilar y planos; abajo: croquis y otros.
      "Casilla de verificación1613": f.adjunta_esquema_unifilar !== false,
      "Casilla de verificación1614": f.adjunta_planos_planta !== false,
      "Casilla de verificación1615": f.adjunta_croquis_trazado !== false,
      "Casilla de verificación1616": f.adjunta_otros === true,
    },
  };
}

export function mapaAnexoIve(datos, cfg, tec, calc) {
  const e = cfg.empresa || {};
  const { dia, mes, anio } = partesFecha(datos.fecha);
  const p1 = "topmostSubform[0].Page1[0].";
  const vacio = calc.caida_v ? punto(calc.caida_v) : "";
  const largo = calc.longitud ? punto(calc.longitud) : "";

  const mapa = {
    "topmostSubform[0].Page5[0].CampoTexto52[0]": e.instalador_nombre,
    "dni DON": e.instalador_nif,
    [p1 + "CampoTexto46[0]"]: e.razon_social,
    CIF: e.nif,
    [p1 + "CampoTexto54[0]"]: e.direccion_una_linea,
    [p1 + "CampoTexto55[0]"]: e.cp,
    [p1 + "CampoTexto56[0]"]: e.municipio,
    [p1 + "CampoTexto57[0]"]: e.provincia,
    [p1 + "CampoTexto26[0]"]: coma(calc.potencia_kw),
    Dropdown2: t(datos.esquema) || "2",
    "Número de puntos de recarga": t(datos.num_puntos) || "1",
    [p1 + "CampoTexto12[0]"]: t(datos.empl_tipo_via),
    [p1 + "CampoTexto13[0]"]: t(datos.empl_nombre_via),
    [p1 + "CampoTexto14[0]"]: t(datos.empl_numero),
    [p1 + "CampoTexto15[0]"]: t(datos.empl_bloque),
    [p1 + "CampoTexto16[0]"]: t(datos.empl_escalera),
    [p1 + "CampoTexto17[0]"]: t(datos.empl_piso),
    [p1 + "CampoTexto18[0]"]: t(datos.empl_puerta),
    [p1 + "CampoTexto69[0]"]: e.lugar_firma,
    [p1 + "CampoTexto70[0]"]: dia,
    [p1 + "CampoTexto71[0]"]: mes,
    [p1 + "CampoTexto72[0]"]: anio,
    // OJO: en la página 2 los nombres de campo NO corresponden a su columna.
    // El orden real, comprobado por coordenada, es el de abajo.
    "P.Cálculo60": punto(calc.potencia_kw),
    "Tensión de Cálculo60": punto(calc.tension, 0),
    "Intensidad de Cálculo60": punto(calc.intensidad, 0),
    "nº Conductores-Sección60": tec.conductores_x_seccion,
    "Material conductor60": tec.material,
    "Asilamiento T.Nominal60": tec.aislamiento,
    "(ITC-BT-26)60": tec.tipo_instalacion_circuito,
    "Tipo de instalación60": largo,                       // Longitud Máxima (m)
    "Intensidad máxima admisible60": vacio,               // Caída de Tensión (V)
    "C/C PIA60": punto(calc.pot_max_admisible),           // Pot. Máx. Admisible
    Longitud60: punto(calc.potencia_kw),                  // Pot. Total Instalada
    "Caída de tensión60": tec.fusible_seguridad,          // Int. Fusible o P.I.A.
  };

  let elegida = "IRVEop4";
  if (calc.potencia_kw > 50) elegida = "IRVEop1";
  else if (t(datos.ubicacion_fisica).toLowerCase().startsWith("ext") && calc.potencia_kw > 10) {
    elegida = "IRVEop2";
  }
  const casillas = {};
  for (const i of [1, 2, 3, 4]) casillas[`IRVEop${i}`] = `IRVEop${i}` === elegida;
  return { mapa, casillas };
}

export const PISTAS_ANEXO_GARAJE = {
  "titular garaje": "Escriba aquí el nombre de la comunidad de propietarios",
  "NIF titular garaje": "CIF de la comunidad",
  "domicilio titular garaje": "Domicilio de la comunidad",
  "localidad tit. garaje": "Localidad",
  "C.P. titular garaje": "C.P.",
  "provincia tit. garaje": "Provincia",
  "nº plaza": "Nº de plaza",
  "planta plaza": "Planta",
};

export function mapaAnexoGaraje(datos, cfg) {
  const { dia, mes, anio } = partesFecha(datos.fecha);
  const nombre = [datos.titular_nombre, datos.titular_apellido1, datos.titular_apellido2]
    .map(t).filter(Boolean).join(" ");
  return {
    mapa: {
      "nombre titular": nombre,
      Texto2: t(datos.titular_nif),
      "domicilop titular": direccionUnaLinea("titular", datos),
      "nº plaza": t(datos.plaza_numero),
      "planta plaza": t(datos.plaza_planta),
      Texto6: direccionDelEdificio("empl", datos),
      "localidad garaje": t(datos.empl_localidad),
      "c.p. garaje": t(datos.empl_cp),
      "provincia garaje": t(datos.empl_provincia) || "MADRID",
      "titular garaje": t(datos.cp_nombre),
      "NIF titular garaje": t(datos.cp_nif),
      "domicilio titular garaje": t(datos.cp_domicilio),
      "localidad tit. garaje": t(datos.cp_localidad),
      "C.P. titular garaje": t(datos.cp_cp),
      "provincia tit. garaje": t(datos.cp_provincia) || "MADRID",
      // El "En ______, a __ de ____" de la firma. Va la localidad del
      // cliente, no la provincia: ese recuadro compartia campo con la
      // provincia del garaje y por eso ponia MADRID.
      "lugar firma": t(datos.titular_localidad) || t(datos.empl_localidad),
      dia, mes, año: anio,
    },
    casillas: {},
    pistas: PISTAS_ANEXO_GARAJE,
  };
}

export function mapaUnifilar(datos, cfg, tec, calc) {
  const e = cfg.empresa || {};
  const { dia, mes, anio } = partesFecha(datos.fecha);
  const p1 = "topmostSubform[0].Page1[0].";
  const titular = [datos.titular_apellido1, datos.titular_apellido2, datos.titular_nombre]
    .map(t).filter(Boolean).join(" ");

  return {
    mapa: {
      // la línea que alimenta el punto de recarga
      "DERIVACION INDIVIDUAL": `${tec.conductores_unifilar} x ${tec.seccion} mm² `
        + `${tec.material} ${tec.aislamiento_texto}`,
      IMG1: `${tec.iga_fases}x${tec.iga_intensidad}`,
      IDG1: `${tec.dif_fases}x${tec.dif_intensidad}`,
      IDG1S: `${tec.dif_sensibilidad} mA`,
      IDG1C: tec.dif_clase,
      // pie del esquema
      NombreEmpresaInstaladora: e.razon_social,
      [p1 + "CampoTexto1[0]"]: titular,
      [p1 + "CampoTexto12[0]"]: t(datos.empl_tipo_via),
      [p1 + "CampoTexto13[0]"]: t(datos.empl_nombre_via),
      [p1 + "CampoTexto14[0]"]: t(datos.empl_numero),
      [p1 + "CampoTexto15[0]"]: t(datos.empl_bloque),
      [p1 + "CampoTexto16[0]"]: t(datos.empl_escalera),
      [p1 + "CampoTexto17[0]"]: t(datos.empl_piso),
      [p1 + "CampoTexto18[0]"]: t(datos.empl_puerta),
      [p1 + "CampoTexto70[0]"]: dia,
      [p1 + "CampoTexto71[0]"]: mes,
      [p1 + "CampoTexto72[0]"]: anio,
    },
    casillas: {},
  };
}

export function mapaAutorizacion(datos, cfg) {
  const e = cfg.empresa || {};
  const nombre = [datos.titular_nombre, datos.titular_apellido1, datos.titular_apellido2]
    .map(t).filter(Boolean).join(" ");
  return {
    mapa: {
      Auto_Text1: nombre,
      Auto_Text2: t(datos.titular_nif),
      Auto_Text3: e.instalador_nombre,
      Auto_Text4: e.instalador_nif,
      Auto_Text5: direccionUnaLinea("empl", datos),
      Auto_Text6: [`${t(datos.empl_cp)} ${t(datos.empl_localidad)}`.trim(), textoPlaza(datos)]
        .filter(Boolean).join(" · "),
    },
    casillas: {},
  };
}

export function mapaSolicitud(datos, cfg) {
  const e = cfg.empresa || {};
  const { dia, mes, anio } = partesFecha(datos.fecha);
  const mapa = {
    NIF: t(datos.titular_nif),
    "Primer Apellido": t(datos.titular_apellido1),
    "Segundo Apellido": t(datos.titular_apellido2),
    "NombreRazón Social": t(datos.titular_nombre),
    "Correo electrónico": t(datos.titular_email),
    "Tipo de vía": t(datos.titular_tipo_via),
    "Nombre vía": t(datos.titular_nombre_via),
    N: t(datos.titular_numero),
    Bloque: t(datos.titular_bloque),
    Escalera: t(datos.titular_escalera),
    Piso: t(datos.titular_piso),
    Puerta: t(datos.titular_puerta),
    Localidad: t(datos.titular_localidad),
    Provincia: t(datos.titular_provincia) || "MADRID",
    CP: t(datos.titular_cp),
    "Teléfono Móvil": t(datos.titular_movil),
    NIF_3: e.nif,
    "NombreRazón Social_2": e.razon_social,
    Correoe: e.email,
    Categoría: t(e.categoria).toUpperCase(),
    "N Registro": e.num_registro,
    "Nombre del instalador": e.instalador_nombre,
    "Tipo de vía_3": e.tipo_via,
    "Nombre vía_3": e.nombre_via,
    N_3: e.numero,
    Localidad_3: e.municipio,
    Provincia_3: e.provincia,
    CP_3: e.cp,
    "Teléfono Móvil_3": e.telefono,
    "Tipo de vía_6": t(datos.empl_tipo_via),
    "Nombre vía_6": t(datos.empl_nombre_via),
    N_6: t(datos.empl_numero),
    CP_6: t(datos.empl_cp),
    Bloque_6: t(datos.empl_bloque),
    Escalera_6: t(datos.empl_escalera),
    Piso_6: t(datos.empl_piso),
    Puerta_6: t(datos.empl_puerta),
    Localidad_6: t(datos.empl_localidad),
    En: e.lugar_firma,
    Dia: dia,
    Mes: mes,
    Año: anio,
    Otros: "AUTORIZACIÓN",
  };
  const nombres = ["Nueva instalación", "Tipo9", "Tipo24", "Tipo25", "Tipo26",
    "Tipo27", "Tipo28", "Tipo34", "Tipo37", "Tipo38"];
  const casillas = {};
  nombres.forEach(n => { casillas[n] = true; });
  return { mapa, casillas };
}

/* ══════════════ celdas del CIE ══════════════ */

export function celdasCie(datos, cfg, tec, calc) {
  const e = cfg.empresa || {};
  const f = cfg.valores_fijos_cie || {};
  const { corta } = partesFecha(datos.fecha);
  const distribuidora = t(datos.distribuidora) || distribuidoraPorCups(datos.cups, cfg);

  const info = [
    `IRVE DE USO ${(t(datos.uso_irve) || "PRIVADO").toUpperCase()} EN GARAJE `
      + `${(t(datos.tipo_garaje) || "COMUNITARIO").toUpperCase()} `
      + `${(t(datos.ubicacion_fisica) || "INTERIOR").toUpperCase()}`,
    `Nº DE PUNTOS DE CONEXIÓN: ${t(datos.num_puntos) || "1"}, `
      + `ESQUEMA ${t(datos.esquema) || "2"}. `
      + `${(t(datos.descripcion_punto) || "CONECTOR TIPO 2 MENNEKES").toUpperCase()}`,
  ].filter(Boolean).join("\n");

  return {
    B7: t(datos.titular_nif), H7: t(datos.titular_apellido1), P7: t(datos.titular_apellido2),
    D8: t(datos.titular_nombre), O8: t(datos.titular_email),
    D9: t(datos.titular_tipo_via), H9: t(datos.titular_nombre_via), U9: t(datos.titular_numero),
    C10: t(datos.titular_bloque), F10: t(datos.titular_escalera),
    H10: t(datos.titular_piso), J10: t(datos.titular_puerta), M10: t(datos.titular_localidad),
    C11: t(datos.titular_provincia) || "MADRID", I11: t(datos.titular_cp),
    M11: t(datos.titular_fijo), S11: t(datos.titular_movil),
    C16: t(datos.empl_tipo_via), G16: t(datos.empl_nombre_via),
    S16: t(datos.empl_numero), U16: t(datos.empl_cp),
    C17: t(datos.empl_bloque), F17: t(datos.empl_escalera),
    H17: t(datos.empl_piso), J17: t(datos.empl_puerta), M17: t(datos.empl_localidad),
    E18: t(datos.ubicacion_contador) || "Local",
    M18: textoPlaza(datos),
    C20: f.actuacion, M20: t(datos.cups).replace(/\s/g, "").toUpperCase(), U20: f.superficie,
    D21: coma(calc.pot_max_admisible), J21: f.tipo_instalacion, U21: f.aforo,
    D22: f.pot_ampliada, J22: t(datos.tipo_suministro) || "Monofásico",
    M22: punto(calc.tension, 0), T22: tec.seccion,
    D23: f.pot_original, T23: f.esquema_distribucion,
    I24: f.punto_conexion, M24: f.tipo_acometida, T24: f.cgp_esquema,
    J25: tec.iga_intensidad, P25: f.prot_sobretensiones, U25: f.int_diferencial,
    F26: distribuidora, A28: info,
    B30: e.nif, H30: e.razon_social, G31: e.categoria, R31: e.num_registro,
    E32: e.instalador_nombre, S32: e.instalador_nif,
    D33: e.tipo_via, H33: e.nombre_via, Q33: e.numero, U33: e.cp,
    C34: e.municipio, I34: e.provincia, M34: e.telefono, R34: e.email,
    L38: f.documentacion, A40: f.rd1890, A42: f.itc_bt_51,
    // El impreso ya trae escrito "En": aqui va el lugar y la fecha
    B43: [t(e.lugar_firma) || t(e.municipio), corta].filter(Boolean).join(" A "),
    S51: f.resistencia_tierra, S52: f.resistencia_aislamiento, S53: f.otras_verificaciones,
  };
}

/* Ajustes por documento: campos que el usuario ha elegido rellenar desde la
   pantalla de Configuración, sin tocar el código. Van encima de lo que pone la
   aplicación, porque si alguien los escribe ahí a mano es que los quiere así.
   Un valor de sí/no es una casilla; cualquier otra cosa, texto. */
export function aplicarExtras(partes, extras) {
  if (!extras) return partes;
  for (const [campo, valor] of Object.entries(extras)) {
    if (valor === true || valor === false) partes.casillas[campo] = valor;
    else if (t(valor) !== "") partes.mapa[campo] = t(valor);
  }
  return partes;
}

/* ══════════════ generar el expediente ══════════════ */

const DOCUMENTOS = [
  // El MTD lleva dos botones y un aviso que el propio impreso marca como
  // "no imprimir": se quitan. Y se entrega aplanado, que es como sale al
  // pulsar Imprimir, con los datos ya fijos.
  { archivo: "MTD.pdf", nombre: "MTD - Memoria Tecnica de Diseno.pdf", tipo: "mtd",
    quitarBotones: true, aplanar: true },
  { archivo: "ANEXO_IVE.pdf", nombre: "Anexo IVE - declaracion ITC-BT-52.pdf", tipo: "anexo_ive" },
  { archivo: "UNIFILAR.pdf", nombre: "Esquema unifilar.pdf", tipo: "unifilar" },
  { archivo: "SOLICITUD.pdf", nombre: "Solicitud de inscripcion BT-1134F1.pdf", tipo: "solicitud" },
  { archivo: "AUTORIZACION.pdf", nombre: "Autorizacion del titular al instalador.pdf", tipo: "autorizacion" },
  { archivo: "ANEXO_GARAJE.pdf", nombre: "Anexo - inspeccion periodica del garaje.pdf", tipo: "anexo_garaje" },
];

/* `opciones.aplanar = false` entrega el MTD con sus campos en vez de aplanado.
   Solo lo usa herramientas/comparar.py: los dos motores aplanan con librerias
   distintas y el dibujo no sale byte a byte igual (Python pierde algun acento
   y recorta alguna palabra larga), asi que la comparacion se hace antes. */
export async function generarExpediente(datos, cfg, cargarPlantilla, lib, opciones) {
  const aplanarMtd = !(opciones && opciones.aplanar === false);
  const tec = valoresTecnicos(datos, cfg);
  const calc = calcular(datos, tec, cfg);
  const avisos = [...calc.avisos];
  const documentos = [];

  const cups = validarCups(datos.cups);
  if (cups.valido === false) {
    avisos.push("El CUPS no pasa la comprobación de las dos letras de control. "
      + "Revísalo antes de presentar el certificado.");
  } else if (cups.valido === null) {
    avisos.push("No has escrito el CUPS, así que el CIE saldrá como incompleto.");
  }
  if (validarNif(datos.titular_nif) === false) {
    avisos.push("El NIF del titular no pasa la comprobación de la letra de control.");
  }
  if (calc.potencia_kw > calc.pot_max_admisible + 0.01) {
    avisos.push(`El punto pide ${coma(calc.potencia_kw)} kW pero las protecciones de `
      + `${punto(calc.intensidad_proteccion, 0)} A solo admiten `
      + `${coma(calc.pot_max_admisible)} kW. Sube la protección o baja la potencia.`);
  }

  // Si el usuario ha pegado algún símbolo que las fuentes del PDF no admiten,
  // se ha quitado al escribirlo. Mejor avisarlo que dejarlo pasar callando.
  const raros = new Set();
  for (const valor of Object.values(datos)) {
    if (typeof valor === "string") {
      limpiarParaPdf(valor).quitados.forEach(c => raros.add(c));
    }
  }
  if (raros.size) {
    avisos.push(`He quitado de los documentos ${[...raros].map(c => `«${c}»`).join(", ")}`
      + ": los impresos oficiales no admiten esos símbolos. Revisa que el texto "
      + "siga diciendo lo que querías.");
  }

  const incluirGaraje = !!datos.incluir_anexo_garaje;
  if (incluirGaraje && !t(datos.cp_nombre)) {
    avisos.push("No has puesto los datos de la comunidad de propietarios. En el anexo "
      + "del garaje esos huecos salen en gris, indicando lo que hay que escribir, "
      + "para que los rellene el cliente desde el PDF. Dile que borre el texto gris "
      + "al escribir encima: si no lo hace, se imprime tal cual.");
  }

  for (const doc of DOCUMENTOS) {
    if (doc.tipo === "anexo_garaje" && !incluirGaraje) continue;
    try {
      let partes;
      if (doc.tipo === "mtd") partes = mapaMtd(datos, cfg, tec, calc);
      else if (doc.tipo === "anexo_ive") partes = mapaAnexoIve(datos, cfg, tec, calc);
      else if (doc.tipo === "unifilar") partes = mapaUnifilar(datos, cfg, tec, calc);
      else if (doc.tipo === "solicitud") partes = mapaSolicitud(datos, cfg);
      else if (doc.tipo === "autorizacion") partes = mapaAutorizacion(datos, cfg);
      else partes = mapaAnexoGaraje(datos, cfg);

      aplicarExtras(partes, (cfg.extras || {})[doc.archivo]);

      const r = await rellenarPdf(
        await cargarPlantilla(doc.archivo),
        partes.mapa, partes.casillas, cfg, partes.pistas, lib,
        { quitarBotones: doc.quitarBotones, aplanar: doc.aplanar && aplanarMtd });
      documentos.push({ nombre: doc.nombre, ok: true, bytes: r.bytes,
                        campos: r.escritos, faltan: r.noEncontrados });
    } catch (err) {
      documentos.push({ nombre: doc.nombre, ok: false, error: String(err).slice(0, 160) });
    }
  }

  // el CIE
  try {
    const celdas = {};
    const crudas = { ...celdasCie(datos, cfg, tec, calc),
                     ...((cfg.extras || {}).CIE || {}) };
    for (const [k, v] of Object.entries(crudas)) celdas[k] = mayus(v, cfg);
    const cie = await generarCie(celdas, mayus(cups.texto, cfg), cargarPlantilla, lib);
    documentos.push({ nombre: "CIE.pdf", ok: true, bytes: cie.bytes,
                      estado: cie.estado, identificador: cie.identificador });
    if (cie.estado && !cie.estado.toUpperCase().includes("COMPLET")) {
      avisos.push(`El CIE sale como «${cie.estado}». Repasa los datos que falten.`);
    }
  } catch (err) {
    documentos.push({ nombre: "CIE.pdf", ok: false, error: String(err).slice(0, 160) });
  }

  return {
    carpeta: nombreCarpeta(datos),
    documentos,
    avisos,
    identificador: (documentos.find(d => d.identificador) || {}).identificador || "",
    calculo: {
      intensidad: Number(calc.intensidad.toFixed(2)),
      caida_v: Number(calc.caida_v.toFixed(2)),
      caida_pct: Number(calc.caida_pct.toFixed(2)),
      pot_max_admisible: Number(calc.pot_max_admisible.toFixed(2)),
    },
  };
}
