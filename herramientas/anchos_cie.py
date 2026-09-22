# -*- coding: utf-8 -*-
"""
Apunta en `cie_mapa.json` hasta donde llega cada celda del CIE.

El mapa dice DONDE empieza cada dato. Lo que no decia es hasta donde puede
llegar, y por eso un valor largo se salia de su casilla y se montaba encima del
rotulo de al lado: "URBANIZACION" pisaba el "Nombre via:" que tiene detras. En
la hoja de calculo eso no pasa, porque la celda tiene un ancho y el texto se
parte dentro. Un CIE con el texto salido del recuadro no vale.

El limite se saca del propio impreso en blanco: en la linea de cada celda, lo
siguiente que hay impreso a la derecha es donde se acaba el sitio. Donde no hay
nada impreso, manda la rejilla de columnas de la hoja.

    python herramientas/anchos_cie.py

Escribe el "izq" y el "der" de cada celda en docs/plantillas/cie_mapa.json.
Hay que volver a ejecutarlo si cambia el impreso.
"""

import io
import json
import os
import re
import sys

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "docs", "plantillas")
MAPA = os.path.join(PLANTILLAS, "cie_mapa.json")

# Cuanto puede separarse una celda de la linea de un texto para considerarlos
# de la misma fila. Las lineas base no caen al milimetro.
MISMA_LINEA = 2.5

# Un respiro entre el dato y lo que venga detras, para que no se peguen.
MARGEN = 1.5


def columna(celda):
    """De "H7" a 8. La columna en numero, para poder ordenar."""
    m = re.match(r"^([A-Z]+)(\d+)$", celda)
    if not m:
        return None
    n = 0
    for c in m.group(1):
        n = n * 26 + ord(c) - 64
    return n


def rotulos_del_impreso(ruta):
    """Lo que ya viene impreso: texto, donde empieza, donde acaba y su linea."""
    doc = pymupdf.open(ruta)
    fuera = []
    for pagina in doc:
        for bloque in pagina.get_text("dict")["blocks"]:
            for linea in bloque.get("lines", []):
                for tramo in linea.get("spans", []):
                    if tramo["text"].strip():
                        x0, _, x1, base = tramo["bbox"]
                        fuera.append({"pagina": pagina.number, "x0": x0, "x1": x1,
                                      "base": base})
    doc.close()
    return fuera


def rejilla(posiciones):
    """Donde empieza cada columna, medido en las celdas alineadas a la izquierda."""
    izquierda = {}
    for celda, sitio in posiciones.items():
        col = columna(celda)
        if col is None or sitio.get("alineacion") != "izquierda":
            continue
        x = sitio["x"] - 1.5
        if col not in izquierda or x < izquierda[col]:
            izquierda[col] = x
    sabidas = sorted(izquierda)
    if not sabidas:
        return lambda col: None
    ancho = ((izquierda[sabidas[-1]] - izquierda[sabidas[0]])
             / (sabidas[-1] - sabidas[0])) if len(sabidas) > 1 else 20.0

    def borde(col):
        if col in izquierda:
            return izquierda[col]
        if col < sabidas[0]:
            return izquierda[sabidas[0]] - (sabidas[0] - col) * ancho
        if col > sabidas[-1]:
            return izquierda[sabidas[-1]] + (col - sabidas[-1]) * ancho
        antes, despues = sabidas[0], sabidas[-1]
        for s in sabidas:
            if s < col:
                antes = s
            else:
                despues = s
                break
        t = (col - antes) / (despues - antes)
        return izquierda[antes] + t * (izquierda[despues] - izquierda[antes])

    return borde


def main():
    with io.open(MAPA, encoding="utf-8") as fh:
        mapa = json.load(fh)
    posiciones = mapa["posiciones"]
    base_pdf = os.path.join(PLANTILLAS, mapa.get("base_pdf", "CIE_base.pdf"))
    rotulos = rotulos_del_impreso(base_pdf)
    borde = rejilla(posiciones)

    # las celdas de cada fila, ordenadas, para saber quien va detras de quien
    por_fila = {}
    for celda, sitio in posiciones.items():
        col = columna(celda)
        if col is None:
            continue
        por_fila.setdefault(round(sitio["linea_base"], 1), []).append((col, celda))
    for fila in por_fila.values():
        fila.sort()

    estrechas = 0
    for celda, sitio in posiciones.items():
        col = columna(celda)
        if col is None:
            continue
        x = sitio["x"]
        # el hueco que deja el impreso a un lado y a otro, en su misma linea
        cerca = [r for r in rotulos
                 if r["pagina"] == sitio.get("pagina", 0)
                 and abs(r["base"] - sitio["linea_base"]) <= MISMA_LINEA]
        izq = max([r["x1"] for r in cerca if r["x1"] <= x + 0.5] or [0.0])
        der = min([r["x0"] for r in cerca if r["x0"] >= x - 0.5] or [10_000.0])

        # Si en esa linea no hay nada impreso a la derecha, no hay limite:
        # es lo que hace la hoja de calculo cuando las celdas de al lado
        # estan vacias, y es como se ve la empresa distribuidora o la
        # informacion adicional, que ocupan media hoja. Poner aqui el ancho
        # de una columna dejaria esos datos encogidos hasta no leerse.
        if izq <= 0:
            izq = borde(col) or x

        sitio["izq"] = round(max(0.0, min(izq, x)), 2)
        sitio["der"] = round(max(x, der) - MARGEN, 2)
        if sitio["der"] - sitio["izq"] < 12:
            estrechas += 1

    mapa["_nota"] = (mapa.get("_nota", "").rstrip(".")
                     + ". El izq y el der de cada celda los pone "
                       "herramientas/anchos_cie.py: son el sitio que tiene el "
                       "dato antes de pisar lo de al lado.")
    with io.open(MAPA, "w", encoding="utf-8") as fh:
        json.dump(mapa, fh, ensure_ascii=False, indent=1)

    anchos = sorted(s["der"] - s["izq"] for s in posiciones.values())
    print(f"  celdas con sitio apuntado : {len(posiciones)}")
    print(f"  la mas estrecha           : {anchos[0]:.1f} pt")
    print(f"  la de en medio            : {anchos[len(anchos) // 2]:.1f} pt")
    print(f"  la mas ancha              : {anchos[-1]:.1f} pt")
    print(f"  mas estrechas de 12 pt    : {estrechas}")
    print(f"  mapa -> {os.path.relpath(MAPA, RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
