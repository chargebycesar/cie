/* Relleno de los impresos con formulario, con pdf-lib.
 *
 * Equivale a rellenar_pdf() de nucleo.py. Las casillas de estos impresos usan
 * el estado «Sí» en vez del habitual «Yes»; pdf-lib lo maneja bien.
 */

import { mayus } from "./util.js";

const GRIS_PISTA = [0.55, 0.58, 0.62];

/* Saca del documento los campos que cumplan la condición: fuera de las páginas
 * y fuera del formulario. */
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
    form.removeField(campo);
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
    try {
      if (texto) {
        // Solo el texto, sin tocar el fondo. Antes se pintaba de blanco para
        // que un campo ya relleno no pareciera un hueco pendiente, pero ese
        // blanco se comía las líneas de las tablas del impreso. Y el /MK del
        // campo no se toca: ahí vive el giro de 90° de las celdas estrechas.
        campo.setText(texto);
      } else if (pistas && pistas[nombre]) {
        // Hueco que rellena el cliente: se le deja escrito en gris qué poner.
        campo.setText(mayus(pistas[nombre], cfg));
        campo.acroField.setDefaultAppearance(
          `/Helv 0 Tf ${GRIS_PISTA.join(" ")} rg`);
      } else {
        campo.setText("");
      }
      escritos += 1;
    } catch (e) {
      noEncontrados.push(nombre);
    }
  }

  // Genera la apariencia de cada campo para que se vea en cualquier visor.
  try {
    form.updateFieldAppearances(helvetica);
  } catch (e) {
    // Si algún campo suelto no se puede dibujar, se deja al visor
    form.acroForm.dict.set(lib.PDFName.of("NeedAppearances"), lib.PDFBool.True);
  }

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
