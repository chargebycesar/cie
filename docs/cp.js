/* Códigos postales.
 *
 * Un municipio puede tener muchos códigos postales -Madrid tiene más de
 * doscientos-, así que guardar «localidad → código» está mal: en cuanto haces
 * dos instalaciones en el mismo pueblo, la segunda hereda el código de la
 * primera y no te enteras.
 *
 * Aquí se hacen dos cosas distintas:
 *
 *   - Recordar por CALLE, no por municipio. La clave es municipio + tipo de
 *     vía + nombre de la vía, que es hasta donde llega el código postal.
 *   - Preguntarlo a CartoCiudad, el callejero oficial del Instituto Geográfico
 *     Nacional, que lo da por calle y número. Eso hay que pedirlo a mano: es
 *     lo único de toda la aplicación que sale del ordenador, y lo que sale es
 *     la dirección, nunca el nombre ni el DNI de nadie.
 */

/* Sin acentos, sin dobles espacios y en mayúsculas: «León Felipe» y
   «LEON  FELIPE» tienen que ser la misma calle. */
export const normalizar = s => String(s ?? "")
  .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
  .replace(/\s+/g, " ").trim().toUpperCase();

/* La clave de una calle. Sin nombre de vía no hay clave: un municipio suelto
   no identifica ningún código postal. */
export function claveCalle(municipio, tipoVia, nombreVia) {
  const m = normalizar(municipio);
  const v = normalizar(nombreVia);
  if (!m || !v) return "";
  return `${m}|${normalizar(tipoVia)} ${v}`.replace(/\|\s+/, "|");
}

export const municipioDe = clave => String(clave || "").split("|")[0];

export const esCodigoPostal = v => /^\d{5}$/.test(String(v || "").trim());

/* Los códigos que ya conoces de un municipio, para ofrecerlos. Salen de lo que
   has usado antes y de lo que ha contestado el callejero oficial. */
export function codigosDe(libreta, municipio) {
  const m = normalizar(municipio);
  if (!m) return [];
  const fuera = new Set();
  for (const [clave, cp] of Object.entries(libreta || {})) {
    if (municipioDe(clave) === m && esCodigoPostal(cp)) fuera.add(cp);
  }
  return [...fuera].sort();
}

/* ─────────────────── el callejero oficial ─────────────────── */

const CARTOCIUDAD =
  "https://www.cartociudad.es/geocoder/api/geocoder/candidatesJsonp";

/* De momento esta aplicación es solo para la Comunidad de Madrid, así que la
   búsqueda se acota a la provincia 28. Sin acotar, una calle con nombre común
   -Real, Mayor, Iglesia- devuelve resultados de media España, y el primero que
   sale puede ser de León. El día que se hagan boletines de otra comunidad, se
   quita de aquí. */
const PROVINCIA = { codigo: "28", nombre: "MADRID" };

/* La respuesta viene envuelta en callback(...), que es como se pedían las
   cosas entre dominios antes de que existiera CORS. Hoy el servicio sí admite
   CORS, así que basta con quitarle la envoltura. */
function desenvolver(texto) {
  const t = String(texto).trim();
  const a = t.indexOf("(");
  const b = t.lastIndexOf(")");
  if (a < 0 || b < a) return JSON.parse(t);
  return JSON.parse(t.slice(a + 1, b));
}

/* El tipo de vía no sirve para comparar: tú pones AVENIDA y el callejero
   contesta CALLE para la misma calle. Se quita, junto con el «de» o «la» que
   viene detrás, y se compara solo el nombre. */
const TIPOS_VIA = new Set([
  "CALLE", "C", "CL", "AVENIDA", "AV", "AVDA", "PLAZA", "PZA", "PL", "PASEO",
  "PS", "PO", "CARRETERA", "CTRA", "CR", "CAMINO", "CM", "TRAVESIA", "TRV",
  "GLORIETA", "GTA", "RONDA", "RD", "CALLEJON", "BULEVAR", "PARQUE", "PQUE",
  "URBANIZACION", "URB", "POLIGONO", "POL", "PG", "SECTOR", "PARCELA", "FINCA",
  "VIA", "AUTOVIA", "CUESTA", "BAJADA", "SUBIDA", "RAMBLA", "PASAJE", "PJE",
  "LUGAR", "BARRIO", "GRUPO", "SENDA", "COLONIA", "OTROS",
]);
const ARTICULOS = new Set(["DE", "DEL", "LA", "EL", "LOS", "LAS"]);

export function nombreDeVia(texto) {
  const t = normalizar(texto).split(" ").filter(Boolean);
  while (t.length > 1 && (TIPOS_VIA.has(t[0]) || ARTICULOS.has(t[0]))) t.shift();
  return t.join(" ");
}

/* ¿Es esta la calle que has escrito? Se compara el nombre entero, no un trozo:
   buscando «Mayor», el callejero ofrece también «Mayorga» y «Miguel Mayor», y
   son otras calles con otro código postal.

   Devuelve el número del portal que ha contestado, o null si no es tu calle. */
export function casaEn(direccionCallejero, nombreBuscado) {
  const puesto = nombreDeVia(String(direccionCallejero || "").split(",")[0]);
  const busco = nombreDeVia(nombreBuscado);
  if (!busco) return null;
  if (puesto === busco) return "";
  if (!puesto.startsWith(busco + " ")) return null;
  const resto = puesto.slice(busco.length + 1);
  if (!/^\d/.test(resto)) return null;     // «Mayor Antigua», no «Mayor 12»
  return resto.split(" ")[0];
}

/* La consulta va SIN provincia. El callejero la rechaza: «calle mayor 1,
   Alcalá de Henares» contesta, y «calle mayor 1, Alcalá de Henares, Madrid» no
   devuelve nada. La provincia se usa después, para descartar resultados. */
export function direccionParaBuscar(d) {
  const via = [d.tipoVia, d.nombreVia].map(x => String(x || "").trim())
    .filter(Boolean).join(" ");
  const numero = String(d.numero || "").trim();
  const municipio = String(d.municipio || "").trim();
  if (!via || !municipio) return "";
  return [numero ? `${via} ${numero}` : via, municipio].join(", ");
}

/* Un municipio se escribe de varias maneras: el callejero usa la del INE, que
   pone el artículo detrás -«Rozas de Madrid, Las»-, y tú escribes «Las Rozas de
   Madrid». Son el mismo sitio. */
const ARTICULOS_MUNICIPIO = ["EL", "LA", "LOS", "LAS", "A", "O", "AS", "OS",
                             "ELS", "SA", "ES"];

export function formasDelMunicipio(nombre) {
  const n = normalizar(nombre);
  if (!n) return [];
  const formas = new Set([n]);
  const coma = n.match(/^(.*),\s*(.+)$/);
  if (coma) formas.add(`${coma[2]} ${coma[1]}`.trim());
  const trozos = n.split(" ");
  if (trozos.length > 1 && ARTICULOS_MUNICIPIO.includes(trozos[0])) {
    formas.add(`${trozos.slice(1).join(" ")}, ${trozos[0]}`);
    formas.add(trozos.slice(1).join(" "));
  }
  return [...formas];
}

export function mismoMunicipio(a, b) {
  const unos = formasDelMunicipio(a);
  const otros = formasDelMunicipio(b);
  return unos.some(x => otros.includes(x));
}

/* Pregunta el código postal de una dirección. Devuelve una lista de opciones,
   porque el callejero puede dar varias -un número que no existe cae en el
   portal de al lado, y a veces la calle cruza dos códigos-.
 *
 * Nunca lanza: si no hay red, o el servicio no contesta, devuelve el motivo y
 * la aplicación sigue funcionando igual que antes. */
export async function buscarCodigoPostal(direccion, buscar = fetch) {
  const consulta = direccionParaBuscar(direccion);
  if (!consulta) return { ok: false, motivo: "falta la calle o la localidad" };

  const suProvincia = normalizar(direccion.provincia);
  if (suProvincia && suProvincia !== PROVINCIA.nombre) {
    return { ok: false,
             motivo: `de momento solo busco en ${PROVINCIA.nombre}` };
  }

  const url = `${CARTOCIUDAD}?q=${encodeURIComponent(consulta)}&limit=15`
    + `&cod_provincia=${PROVINCIA.codigo}`;
  let bruto;
  try {
    // Sin cabecera Accept: el servicio contesta application/x-javascript y
    // si le pides JSON responde 406.
    const r = await buscar(url);
    if (!r.ok) return { ok: false, motivo: `el callejero respondió ${r.status}` };
    bruto = desenvolver(await r.text());
  } catch (e) {
    return { ok: false, motivo: "no he podido conectar con el callejero" };
  }

  const lista = Array.isArray(bruto) ? bruto : [bruto];
  const via = [direccion.tipoVia, direccion.nombreVia].filter(Boolean).join(" ");
  const numero = normalizar(direccion.numero);
  // La provincia es siempre la de la aplicación, se escriba lo que se escriba:
  // de momento esto solo hace boletines de Madrid, y una calle con nombre
  // común existe en media España.
  const provincia = PROVINCIA.nombre;
  const vistos = new Map();
  const otrosSitios = new Set();

  for (const c of lista) {
    if (!c || !esCodigoPostal(c.postalCode)) continue;
    // Las dos comprobaciones juntas, que ninguna basta sola: una misma calle
    // -Mayor, Real, Iglesia- existe en medio país, y dentro de un municipio hay
    // calles que se parecen entre sí. Tiene que ser tu calle Y tu municipio.
    if (!mismoMunicipio(c.muni, direccion.municipio)
        || (provincia && normalizar(c.province) !== provincia)) {
      // La calle es la tuya pero el pueblo no. Se apunta para poder decirlo:
      // «Calle Real» sale en media España, y buscándola en Rivas el callejero
      // contesta con la de Crémenes, en León.
      if (casaEn(c.address, via) !== null) otrosSitios.add(
        [c.muni, c.province].filter(Boolean).join(", "));
      continue;
    }
    const portal = casaEn(c.address, via);
    if (portal === null) continue;          // es otra calle parecida
    const exacto = !!numero && portal === numero;
    const antes = vistos.get(c.postalCode);
    if (!antes || (exacto && !antes.exacto)) {
      vistos.set(c.postalCode, {
        cp: c.postalCode,
        direccion: String(c.address || "").trim(),
        municipio: String(c.muni || "").trim(),
        provincia: String(c.province || "").trim(),
        exacto,
      });
    }
  }
  // Primero el del número que has puesto: una calle larga puede cruzar dos
  // códigos postales, y el que vale es el de tu portal.
  const opciones = [...vistos.values()]
    .sort((a, b) => (b.exacto ? 1 : 0) - (a.exacto ? 1 : 0));
  if (!opciones.length) {
    const fuera = [...otrosSitios];
    return {
      ok: false,
      motivo: fuera.length
        ? `esa calle existe, pero en ${fuera.slice(0, 3).join(" y en ")}, `
          + "no en el municipio que has puesto"
        : `el callejero no encuentra esa dirección en ${PROVINCIA.nombre}`,
      otrosSitios: fuera,
      consulta,
    };
  }
  return { ok: true, opciones, consulta };
}
