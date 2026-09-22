/* Cosas pequeñas que usan todos los módulos. */

export const t = v => (v === null || v === undefined ? "" : String(v).trim());

export function coma(v, decimales = 2) {
  if (v === "" || v === null || v === undefined) return "";
  const n = Number(String(v).replace(",", "."));
  // Nunca dejar que un NaN o un Infinity acabe escrito en un documento oficial
  if (!Number.isFinite(n)) return "";
  let s = n.toFixed(decimales);
  if (s.includes(".")) s = s.replace(/0+$/, "").replace(/\.$/, "");
  return s.replace(".", ",");
}

export function punto(v, decimales = 2) {
  if (v === "" || v === null || v === undefined) return "";
  const n = Number(String(v).replace(",", "."));
  // Nunca dejar que un NaN o un Infinity acabe escrito en un documento oficial
  if (!Number.isFinite(n)) return "";
  let s = n.toFixed(decimales);
  if (s.includes(".")) s = s.replace(/0+$/, "").replace(/\.$/, "");
  return s;
}

/* Las letras que admiten los PDF con las fuentes de siempre son las del
   alfabeto latino occidental. Un símbolo raro pegado desde otro sitio (una
   flecha, un emoji, una letra griega) haría fallar la generación entera, así
   que se cambian por su equivalente o se quitan. */
const SUSTITUCIONES = {
  "≤": "<=", "≥": ">=", "≠": "!=", "≈": "~", "→": "->", "←": "<-",
  "↔": "<->", "∅": "diam.", "Ω": "ohm", "µ": "u", "∞": "infinito",
  "±": "+/-", "√": "raiz", "⋅": "·", "−": "-", "‑": "-", "‒": "-",
  "″": '"', "′": "'", "␣": " ", "\t": " ",
  // Los cuadros de texto del navegador entregan los saltos de línea como CRLF.
  // Sin esto, el retorno de carro se contaría como un símbolo raro y saldría un
  // aviso con un carácter invisible dentro que no hay quien entienda.
  "\r\n": "\n", "\r": "\n",
};

// WinAnsi admite el latín 1 y un puñado de signos tipográficos sueltos
const EXTRAS = new Set([0x20ac, 0x201a, 0x0192, 0x201e, 0x2026, 0x2020, 0x2021,
  0x02c6, 0x2030, 0x0160, 0x2039, 0x0152, 0x017d, 0x2018, 0x2019, 0x201c,
  0x201d, 0x2022, 0x2013, 0x2014, 0x02dc, 0x2122, 0x0161, 0x203a, 0x0153,
  0x017e, 0x0178]);

const admitido = cp =>
  (cp >= 32 && cp <= 126) || (cp >= 160 && cp <= 255) || EXTRAS.has(cp);

/* Devuelve el texto listo para escribir en un PDF, y qué se ha tenido que
   quitar por el camino. */
export function limpiarParaPdf(v) {
  let texto = t(v).normalize("NFC");
  for (const [malo, bueno] of Object.entries(SUSTITUCIONES)) {
    if (texto.includes(malo)) texto = texto.split(malo).join(bueno);
  }
  const quitados = new Set();
  let salida = "";
  for (const letra of texto) {
    const cp = letra.codePointAt(0);
    if (admitido(cp)) salida += letra;
    else if (letra === "\n") salida += letra;
    else quitados.add(letra);
  }
  return { texto: salida, quitados: [...quitados] };
}

/* Todo lo que se escribe en los impresos va en mayúsculas, salvo los correos:
   en mayúsculas ocupan más y se salen de la casilla. */
export function mayus(v, cfg) {
  const texto = limpiarParaPdf(v).texto;
  if (cfg && cfg.todo_mayusculas === false) return texto;
  if (texto.includes("@")) return texto.toLowerCase();
  return texto.toUpperCase();
}

export const sinAcentos = s =>
  String(s).normalize("NFKD").replace(/[̀-ͯ]/g, "");
