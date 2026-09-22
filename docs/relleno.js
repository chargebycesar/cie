/* Relleno de los impresos con formulario, con pdf-lib.
 *
 * Equivale a rellenar_pdf() de nucleo.py. Las casillas de estos impresos usan
 * el estado «Sí» en vez del habitual «Yes»; pdf-lib lo maneja bien.
 */

import { mayus } from "./util.js?v=202609221438";

const GRIS_PISTA = [0.55, 0.58, 0.62];

/* Ningún dato de estos impresos necesita letra más grande que esto, ni se lee
   por debajo de esto otro. */
const TAM_MAXIMO = 9;
const TAM_MINIMO = 4;

/* Ajusta la letra de los campos que vienen con tamaño «automático».
 *
 * Son trece en total, y en ellos la librería elige el tamaño por su cuenta:
 * cuando el recuadro es alto se va a una letra enorme y el dato se sale por los
 * lados. En el esquema unifilar, «BUFALA TECH SL» salía a lo ancho del papel.
 * Aquí se le pone un tamaño que quepa de verdad: se mide lo más largo que hay
 * que meter en una línea -la palabra más larga si el campo admite varias- y se
 * reduce hasta que entre. Los campos con tamaño puesto por el impreso no se
 * tocan. */
function ajustarTamano(campo, texto, helvetica, color = "0 g") {
  const widgets = campo.acroField.getWidgets();
  if (!widgets.length || !texto) return;
  // El tamaño se lee de la apariencia por defecto del campo: pdf-lib 1.17.1 no
  // tiene getFontSize(), solo setFontSize().
  //
  // Si el campo no dice tamaño, lo hereda del formulario, y en estos impresos
  // el del formulario es «/Helv 0 Tf», o sea automático. Entonces la librería
  // se lo inventa: en el anexo del garaje eligió 19 puntos para recuadros de
  // 20, el texto se salía por arriba y el visor lo recortaba entero -el NIF y
  // el domicilio del cliente salían en blanco-. Así que «sin tamaño» cuenta
  // como automático y se le pone uno que quepa.
  let da = "";
  try { da = campo.acroField.getDefaultAppearance() || ""; } catch (e) { da = ""; }
  const puesto = /([\d.]+)\s+Tf/.exec(da);
  if (puesto && Number(puesto[1]) > 0) return;    // el impreso ya dice el tamaño
  let tam;

  // En valor absoluto: algunos recuadros de estos impresos vienen con el
  // rectángulo del revés -el anexo del garaje trae dos con alto -20-, y el
  // tamaño salía en negativo, o sea el mínimo, y el dato en letra diminuta.
  const caja = widgets[0].getRectangle();
  const ancho = Math.max(6, Math.abs(caja.width) - 4);
  const alto = Math.max(6, Math.abs(caja.height) - 2);
  let multi = false;
  try { multi = campo.isMultiline(); } catch (e) { /* no todos lo dicen */ }

  tam = Math.min(TAM_MAXIMO, multi ? TAM_MAXIMO : alto);
  const piezas = multi ? texto.split(/\s+/).filter(Boolean) : [texto];
  let mayor = 1;
  for (const p of piezas) {
    try { mayor = Math.max(mayor, helvetica.widthOfTextAtSize(p, tam)); }
    catch (e) { return; }               // alguna letra que la fuente no tiene
  }
  if (mayor > ancho) tam = tam * ancho / mayor;
  tam = Math.max(TAM_MINIMO, Math.floor(tam * 10) / 10);
  // El tamaño va en el recuadro, no en el campo: la librería mira primero el
  // del recuadro y solo si no lo hay baja al del campo. Puesto en el campo lo
  // ignora y se inventa uno para llenar el hueco, que es el problema de raíz.
  for (const w of widgets) {
    try { w.setDefaultAppearance(`/Helv ${tam} Tf ${color}`); }
    catch (e) { /* si no se deja, se queda como estaba */ }
  }
  try { campo.setFontSize(tam); } catch (e) { /* si no se deja, da igual */ }
}

/* Deja el campo en negro para lo que se escriba después, sin tocar el dibujo
   que ya está hecho. El dibujo es lo que el visor enseña; el /DA es lo que usa
   cuando alguien teclea dentro. */
function devolverElNegro(campo) {
  for (const w of campo.acroField.getWidgets()) {
    try {
      const da = w.getDefaultAppearance() || "";
      w.setDefaultAppearance(
        da.replace(/[\d.]+\s+[\d.]+\s+[\d.]+\s+rg/, "0 g") || "/Helv 9 Tf 0 g");
    } catch (e) { /* si no se deja, se queda como estaba */ }
  }
  try { campo.acroField.setDefaultAppearance("/Helv 9 Tf 0 g"); } catch (e) { /* igual */ }
}

/* Saca del documento los campos que cumplan la condición: fuera de las páginas
 * y fuera del formulario.
 *
 * No se usa form.removeField() de pdf-lib: ese, para localizar la anotación,
 * pide el dibujo del campo, y en el MTD 1.611 de los 1.631 campos no tienen
 * ninguno -son huecos vacíos que el visor dibuja al vuelo-. Con el primero que
 * se encuentra se para y el documento se queda a medias. Aquí se quitan las
 * anotaciones de la página por su objeto, que es lo que hace falta, y luego el
 * campo de la lista del formulario. */
function quitarCampos(doc, form, lib, sobra) {
  const paginas = doc.getPages();
  let quitados = 0;

  for (const campo of form.getFields()) {
    if (!sobra(campo)) continue;
    const suyos = new Set(campo.acroField.getWidgets().map(w => w.dict));
    for (const pagina of paginas) {
      const anotaciones = pagina.node.Annots();
      if (!anotaciones) continue;
      for (let i = anotaciones.size() - 1; i >= 0; i--) {
        if (suyos.has(doc.context.lookup(anotaciones.get(i)))) anotaciones.remove(i);
      }
    }
    try {
      form.acroForm.removeField(campo.acroField);
    } catch (e) { /* si ya no estaba en la lista, mejor */ }
    quitados += 1;
  }
  return quitados;
}

/* El MTD trae dos botones ("Limpiar Campos" e "Imprimir") y el aviso amarillo
 * de cabecera marcados como "no imprimir". Al darle al botón de imprimir no
 * salen, y el MTD que aprueba la OCA tampoco los lleva. Se quitan aquí para no
 * tener que pasar por el trámite de imprimir a mano. */
function quitarNoImprimibles(doc, form, lib) {
  const { PDFName } = lib;
  return quitarCampos(doc, form, lib, campo =>
    !campo.acroField.getWidgets().some(w => {
      const f = w.dict.get(PDFName.of("F"));
      return f && (f.asNumber() & 4);
    }));
}

/* Un campo vacío de estos impresos no es transparente: su dibujo es un
 * rectángulo blanco que tapa lo que hay debajo. En la versión editable da
 * igual, porque el visor lo redibuja; pero al aplanar queda estampado y se
 * come la rejilla de las tablas, que sale a trozos. Como un campo sin texto no
 * aporta nada al documento impreso, se quita entero antes de aplanar. */
function quitarVacios(doc, form, lib) {
  return quitarCampos(doc, form, lib, campo => {
    try {
      if (typeof campo.getText === "function") return !(campo.getText() || "").trim();
      if (typeof campo.isChecked === "function") return !campo.isChecked();
    } catch (e) { /* si no se puede leer, mejor dejarlo */ }
    return false;
  });
}

export async function rellenarPdf(bytes, mapa, casillas, cfg, pistas, lib, opciones) {
  const { PDFDocument, StandardFonts } = lib;
  const doc = await PDFDocument.load(bytes, { updateMetadata: false });
  const form = doc.getForm();
  const helvetica = await doc.embedFont(StandardFonts.Helvetica);

  const noEncontrados = [];
  let escritos = 0;

  // ---- casillas ----------------------------------------------------------
  for (const [nombre, encendida] of Object.entries(casillas || {})) {
    try {
      const c = form.getCheckBox(nombre);
      if (encendida) c.check(); else c.uncheck();
      // Su dibujo no se regenera: el aspa de estos impresos vive en la
      // apariencia que ya traen, con el estado «Sí» en vez del habitual «Yes».
      escritos += 1;
    } catch (e) {
      noEncontrados.push(nombre);
    }
  }

  // ---- campos de texto ---------------------------------------------------
  for (const [nombre, valor] of Object.entries(mapa)) {
    let campo;
    try {
      campo = form.getTextField(nombre);
    } catch (e) {
      noEncontrados.push(nombre);
      continue;
    }
    const texto = mayus(valor, cfg);
    let esPista = false;
    try {
      if (texto) {
        // Solo el texto, sin tocar el fondo. Antes se pintaba de blanco para
        // que un campo ya relleno no pareciera un hueco pendiente, pero ese
        // blanco se comía las líneas de las tablas del impreso. Y el /MK del
        // campo no se toca: ahí vive el giro de 90° de las celdas estrechas.
        campo.setText(texto);
        ajustarTamano(campo, texto, helvetica);
      } else if (pistas && pistas[nombre]) {
        // Hueco que rellena el cliente: se le deja escrito en gris qué poner.
        // Con su tamaño ajustado, como los demás: si no, la librería elige uno
        // enorme y la leyenda no se ve hasta que pinchas en la casilla.
        const pista = mayus(pistas[nombre], cfg);
        campo.setText(pista);
        ajustarTamano(campo, pista, helvetica, `${GRIS_PISTA.join(" ")} rg`);
        esPista = true;
      } else {
        campo.setText("");
      }
      // Solo se redibuja este campo. Regenerar el formulario entero se lleva
      // por delante la apariencia de los que no tocamos, y algunos la
      // necesitan: el aviso legal de la ultima pagina del MTD lleva un fondo
      // opaco que tapa la version antigua impresa debajo. Sin el, los dos
      // textos salen uno encima del otro.
      try {
        campo.updateAppearances(helvetica);
      } catch (e) { /* si no se puede, queda el NeedAppearances de abajo */ }

      // El gris de la leyenda es solo para el dibujo. En cuanto está hecho, se
      // le devuelve el negro al campo: así, cuando el cliente escriba encima,
      // lo suyo sale del mismo color que el resto del documento y no en gris
      // de aviso. El visor usa el dibujo para enseñarlo y el /DA para lo que
      // se teclea, así que valen los dos a la vez.
      if (esPista) devolverElNegro(campo);
      escritos += 1;
    } catch (e) {
      noEncontrados.push(nombre);
    }
  }

  // Cada campo escrito ya se ha redibujado arriba. Los demás conservan la
  // apariencia que trae el impreso oficial, que es lo que queremos.

  if (opciones && opciones.quitarBotones) quitarNoImprimibles(doc, form, lib);

  // El documento aplanado es lo que sale al pulsar Imprimir y elegir "imprimir
  // a PDF": los datos quedan fijos y ya no hay formulario. Si el aplanado
  // fallase se entrega el documento con sus campos, que es peor pero es algo.
  if (opciones && opciones.aplanar) {
    try {
      quitarVacios(doc, form, lib);
      form.flatten();
    } catch (e) {
      noEncontrados.push(`(no se ha podido aplanar: ${String(e).slice(0, 90)})`);
    }
  }

  // save() vuelve a generar las apariencias por su cuenta, asi que si algo
  // falló arriba volvería a fallar aquí y se perdería el documento entero.
  return { bytes: await doc.save({ updateFieldAppearances: false }),
           escritos, noEncontrados };
}
