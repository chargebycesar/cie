/* Casos límite del motor: lo que puede llegar de un usuario real. */
import fs from 'fs';
import path from 'path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import * as lib from 'pdf-lib';

const RAIZ = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const DOCS = path.join(RAIZ, 'docs');
const motor = await import(pathToFileURL(path.join(DOCS, 'motor.js')).href);
const cfgBase = JSON.parse(fs.readFileSync(path.join(RAIZ, 'config.json'), 'utf8'));

const cargar = async (n, como) => {
  const p = path.join(DOCS, 'plantillas', n);
  return como === 'json' ? JSON.parse(fs.readFileSync(p, 'utf8'))
    : new Uint8Array(fs.readFileSync(p));
};

const base = JSON.parse(fs.readFileSync(process.argv[2] || path.join(RAIZ, 'prueba.json'), 'utf8'));

const casos = {
  'formulario vacío del todo': {},
  'sin CUPS': { ...base, cups: '' },
  'CUPS mal': { ...base, cups: 'ES0031000000000000XX' },
  'NIF mal': { ...base, titular_nif: '12345678A' },
  'sin longitud': { ...base, longitud: '' },
  'longitud 0': { ...base, longitud: '0' },
  'longitud enorme': { ...base, longitud: '9999' },
  'trifásico 400 V': { ...base, tipo_suministro: 'Trifásico', tension: '400', fases: '4' },
  'aluminio': { ...base, material: 'Al' },
  'potencia con coma': { ...base, potencia: '11,04' },
  'potencia mayor que la protección': { ...base, potencia: '22', iga_intensidad: '32' },
  'anexo garaje sin comunidad': { ...base, incluir_anexo_garaje: true, cp_nombre: '' },
  'texto con guion largo y comillas': { ...base,
    descripcion_punto: 'Cargador “Trydan” — modelo A' },
  'texto con emoji': { ...base, descripcion_punto: 'Cargador ⚡ rápido' },
  'nombre con signos de HTML': { ...base, titular_nombre: 'Ana <b>"Pepa"</b> & Cía' },
  'observaciones muy largas': { ...base,
    observaciones: 'Linea de prueba muy larga. '.repeat(60) },
  'valor larguísimo en un campo corto': { ...base,
    plaza_numero: '1234567890123456789012345678901234567890' },
  'config sin empresa': { ...base, __sinEmpresa: true },
};

for (const [nombre, datos] of Object.entries(casos)) {
  const cfg = JSON.parse(JSON.stringify(cfgBase));
  if (datos.__sinEmpresa) { cfg.empresa = {}; }
  let r, fallo = null;
  try {
    r = await motor.generarExpediente(datos, cfg, cargar, lib);
  } catch (e) {
    fallo = String(e).split('\n')[0].slice(0, 110);
  }
  if (fallo) {
    console.log(`  ROMPE   ${nombre.padEnd(38)} ${fallo}`);
    continue;
  }
  const malos = r.documentos.filter(d => !d.ok);
  const estado = r.documentos.find(d => d.estado)?.estado || '';
  const marca = malos.length ? 'FALLO  ' : 'ok     ';
  console.log(`  ${marca} ${nombre.padEnd(38)} ${r.documentos.length} docs` +
    (estado ? ` · ${estado}` : '') +
    (malos.length ? ` · ${malos.map(d => d.nombre + ': ' + d.error).join(' | ').slice(0, 140)}` : '') +
    (r.avisos.length ? ` · ${r.avisos.length} avisos` : ''));
}
