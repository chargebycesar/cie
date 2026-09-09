import fs from 'fs';
import path from 'path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import * as lib from 'pdf-lib';

const RAIZ = process.argv[2] || path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const DOCS = path.join(RAIZ, 'docs');
const { generarExpediente } = await import(pathToFileURL(path.join(DOCS, 'motor.js')).href);

const cfg = JSON.parse(fs.readFileSync(path.join(RAIZ, 'config.json'), 'utf8'));
const datos = JSON.parse(fs.readFileSync(process.argv[3] || path.join(RAIZ, 'prueba.json'), 'utf8'));

async function cargar(nombre, como) {
  const p = path.join(DOCS, 'plantillas', nombre);
  if (como === 'json') return JSON.parse(fs.readFileSync(p, 'utf8'));
  return new Uint8Array(fs.readFileSync(p));
}

const r = await generarExpediente(datos, cfg, cargar, lib);
const destino = path.join(process.argv[4] || path.join(RAIZ, 'salida'), 'js');
fs.mkdirSync(destino, { recursive: true });
for (const d of r.documentos) {
  if (d.ok) fs.writeFileSync(path.join(destino, d.nombre), d.bytes);
  const extra = d.estado ? ` | ${d.estado}` : (d.campos ? ` | ${d.campos} campos` : '');
  const err = d.error ? ` | ${d.error}` : '';
  const faltan = (d.faltan && d.faltan.length)
    ? ` | sin encontrar: ${d.faltan.slice(0, 6).join(', ')}` : '';
  console.log(`  ${d.ok ? 'OK   ' : 'FALLO'} ${d.nombre}${extra}${err}${faltan}`);
}
console.log('  calculo:', JSON.stringify(r.calculo));
console.log('  avisos:', r.avisos.length ? r.avisos : 'ninguno');
