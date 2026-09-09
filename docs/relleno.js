/* Relleno de los impresos con formulario, con pdf-lib.
 *
 * Equivale a rellenar_pdf() de nucleo.py. Las casillas de estos impresos usan
 * el estado «Sí» en vez del habitual «Yes»; pdf-lib lo maneja bien.
 */

import { mayus } from "./util.js";

const GRIS_PISTA = [0.55, 0.58, 0.62];

/* El MTD trae dos botones ("Limpiar Campos" e "Imprimir") y el aviso amarillo
 * de cabecera marcados como "no imprimir". Al darle al botón de imprimir no
 * salen, y el MTD que aprueba la OCA tampoco los lleva. Se quitan aquí para no
 * tener que pasar por el trámite de imprimir a mano. */
function quitarNoImprimibles(doc, form, lib) {
  const { PDFName } = lib;
  const paginas = doc.getPages();
  let quitados = 0;

  for (const campo of form.getFields()) {
    const widgets = campo.acroField.getWidgets();
    const seImprime = widgets.some(w => {
      const f = w.dict.get(PDFName.of("F"));
      return f && (f.asNumber() & 4);
    });
    if (seImprime) continue;

    const suyos = new Set(widgets.map(w => w.dict));
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
        campo.setText(texto);
        // Fondo blanco en lo que ya va escrito: el sombreado del impreso marca
        // lo que queda por rellenar. Ojo, el widget no tiene setBackgroundColor:
        // hay que pasar por sus características de apariencia.
        for (const w of campo.acroField.getWidgets()) {
          try {
            w.getOrCreateAppearanceCharacteristics().setBackgroundColor([1, 1, 1]);
          } catch (e) { /* si el visor no lo admite, se queda como estaba */ }
        }
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

  // save() vuelve a generar las apariencias por su cuenta, asi que si algo
  // falló arriba volvería a fallar aquí y se perdería el documento entero.
  const salida = { bytes: await doc.save({ updateFieldAppearances: false }),
                   escritos, noEncontrados };

  // La versión impresa: lo que saldría al pulsar el botón Imprimir y elegir
  // "imprimir a PDF". Se saca del mismo documento, sin volver a abrirlo, que
  // abrir el MTD otra vez cuesta varios segundos. Si fallase, se pierde solo
  // esta versión: la otra ya está hecha.
  if (opciones && opciones.tambienImpresa) {
    try {
      form.flatten();
      salida.impresa = await doc.save({ updateFieldAppearances: false });
    } catch (e) {
      salida.avisoImpresa = String(e).slice(0, 140);
    }
  }
  return salida;
}
