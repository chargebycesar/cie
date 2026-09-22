/* El CIE, dibujado encima del impreso en blanco.
 *
 * Equivale a cie_pdf.py. Las tres fórmulas del libro oficial están aquí:
 * el identificador del certificado, el aviso FALTAN DATOS / COMPLETADO y el
 * resultado de la comprobación del CUPS.
 */

const LETRAS = "TRWAGMYFPDXBNJZSQVHLCKE";

/* El día 0 de las hojas de cálculo es el 30 de diciembre de 1899. */
const ORIGEN_SERIE = Date.UTC(1899, 11, 30);

/* ══════════════ las tres fórmulas ══════════════ */

export function identificador(momento) {
  const ahora = momento || new Date();
  // serie de la hoja de cálculo, en días con decimales de la hora local
  const local = new Date(ahora.getTime() - ahora.getTimezoneOffset() * 60000);
  const serie = (local.getTime() - ORIGEN_SERIE) / 86400000;

  const b13 = (Math.round(Math.random() * 5) + 1) * 1e15;
  const b14 = Math.round((serie - 40000) * 10000) * 1e7;
  const b15 = Math.round(Math.random() * 1e7);
  const numero = BigInt(Math.round(b13)) + BigInt(Math.round(b14)) + BigInt(b15);

  const resto = Number(numero % 529n);
  return `${numero}${LETRAS[Math.floor(resto / 23)]}${LETRAS[resto % 23]}`;
}

function requeridos(formula, celdas) {
  const f = String(formula || "").trim();
  if (!f) return 0;
  if (/^\d+$/.test(f)) return Number(f);
  // =+IF(C20="Nueva";6;7)   ó   =2+IF(L38="...";1;0)
  const m = /^=\+?(\d*)\+?IF\(([A-Z]+\d+)\s*=\s*"(.*?)";\s*(\d+);\s*(\d+)\)$/.exec(f);
  if (m) {
    const base = Number(m[1] || 0);
    const valor = String(celdas[m[2]] ?? "").trim().toLowerCase();
    return base + Number(valor === m[3].trim().toLowerCase() ? m[4] : m[5]);
  }
  const s = /^=\+?(\d+)$/.exec(f);
  return s ? Number(s[1]) : 0;
}

export function estado(mapa, celdas) {
  const todas = { ...(mapa.valores_originales || {}), ...celdas };
  for (const control of mapa.controles) {
    const llenos = control.fijos + control.celdas_entrada
      .filter(c => String(todas[c] ?? "").trim()).length;
    if (llenos - requeridos(control.formula_x, todas) < 0) {
      return { texto: "CIE INCOMPLETO", donde: control.rango };
    }
  }
  return { texto: "COMPLETADO", donde: null };
}

/* ══════════════ dibujar ══════════════ */

function escribir(page, sitio, texto, fuentes, altoPagina, lib) {
  if (!texto) return;
  const tam = sitio.tam || 7.41;
  const fuente = sitio.negrita ? fuentes.negrita : fuentes.normal;
  const lineas = String(texto).split("\n");
  const altoLinea = tam * 1.25;
  // Con varias líneas el bloque se reparte arriba y abajo de la línea medida
  const inicio = sitio.linea_base - altoLinea * (lineas.length - 1) / 2;

  lineas.forEach((linea, i) => {
    if (!linea) return;
    const ancho = fuente.widthOfTextAtSize(linea, tam);
    let x = sitio.x;
    if (sitio.alineacion === "centro") x -= ancho / 2;
    else if (sitio.alineacion === "derecha") x -= ancho;
    // pdf-lib mide desde abajo; el mapa está medido desde arriba
    page.drawText(linea, {
      x, y: altoPagina - (inicio + i * altoLinea),
      size: tam, font: fuente, color: lib.rgb(0, 0, 0),
    });
  });
}

export async function generarCie(celdas, textoCups, cargarPlantilla, lib, momento) {
  const { PDFDocument, StandardFonts } = lib;
  const mapa = await cargarPlantilla("cie_mapa.json", "json");
  const bytes = await cargarPlantilla(mapa.base_pdf || "CIE_base.pdf");

  const doc = await PDFDocument.load(bytes, { updateMetadata: false });
  const fuentes = {
    normal: await doc.embedFont(StandardFonts.Helvetica),
    negrita: await doc.embedFont(StandardFonts.HelveticaBold),
  };

  // El impreso trae texto dentro de algunas casillas editables (rótulos como
  // "C.G.P. (esquema):"). Se recuperan aquí, y los datos mandan sobre ellos.
  const todas = { ...(mapa.valores_originales || {}), ...celdas };

  const ident = identificador(momento);
  const { texto: textoEstado } = estado(mapa, todas);

  // R4 es el «COMPLETADO» de arriba. Va en el documento, y va en el sitio
  // exacto donde lo pone la hoja de cálculo: sin él, la EICI rechaza el
  // certificado. Lo que queda en blanco es el hueco grande de al lado, que es
  // donde ellos sellan y firman; son dos cosas distintas dentro del mismo
  // recuadro y confundirlas costó un rechazo.
  const calculadas = { R4: textoEstado, R6: ident, M19: textoCups };
  const paginas = doc.getPages();

  for (const [celda, valor] of Object.entries({ ...todas, ...calculadas })) {
    const sitio = mapa.posiciones[celda];
    if (!sitio || !String(valor).trim()) continue;
    const page = paginas[sitio.pagina] || paginas[0];
    escribir(page, sitio, valor, fuentes, page.getHeight(), lib);
  }

  return { bytes: await doc.save(), identificador: ident, estado: textoEstado };
}
