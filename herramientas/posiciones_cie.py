# -*- coding: utf-8 -*-
"""
Segunda mitad de la preparacion del CIE, esta con el Python normal.

Lee el PDF de sondas que dejo `mapear_cie.py`, localiza cada texto irrepetible
y apunta en que pagina, en que sitio y con que letra hay que escribir ese dato.
El resultado es `plantillas/cie_mapa.json`, que es lo que usa la aplicacion.

    python herramientas/posiciones_cie.py
"""

import json
import os
import re

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "docs", "plantillas")
FUENTE = os.path.join(RAIZ, "fuente")

# Como alinea LibreOffice cada celda (com.sun.star.table.CellHoriJustify)
ALINEACION = {
    "STANDARD": "auto", "LEFT": "izquierda", "CENTER": "centro",
    "RIGHT": "derecha", "BLOCK": "bloque", "REPEAT": "izquierda",
    "0": "auto", "1": "izquierda", "2": "centro", "3": "derecha", "4": "bloque",
}


def main():
    tmp = os.path.join(PLANTILLAS, "cie_mapa.json.tmp")
    with open(tmp, encoding="utf-8") as fh:
        datos = json.load(fh)

    # token -> {"corta": bbox, "larga": bbox}
    cajas = {}
    for ruta, sufijo, _largo in datos["archivos"]:
        doc = pymupdf.open(ruta)
        for pagina, page in enumerate(doc):
            for bloque in page.get_text("dict")["blocks"]:
                for linea in bloque.get("lines", []):
                    for trozo in linea.get("spans", []):
                        texto = trozo["text"].strip()
                        token = texto[:6]
                        if token not in datos["sondas"]:
                            continue
                        cajas.setdefault(token, {})[sufijo] = {
                            "pagina": pagina,
                            "x0": trozo["bbox"][0], "x1": trozo["bbox"][2],
                            "base": trozo["origin"][1],
                            "tam": trozo["size"],
                            "negrita": bool(trozo["flags"] & 2 ** 4),
                        }
        doc.close()

    encontrados = {}
    for token, medidas in cajas.items():
        celda = datos["sondas"][token]
        corta = medidas.get("corta")
        larga = medidas.get("larga")
        if not corta:
            continue
        # Comparando la sonda corta con la larga se sabe por donde crece el
        # texto, y por tanto como esta alineada la celda.
        alineacion = "izquierda"
        ancla = corta["x0"]
        if larga:
            if abs(larga["x0"] - corta["x0"]) < 0.6:
                alineacion, ancla = "izquierda", corta["x0"]
            elif abs(larga["x1"] - corta["x1"]) < 0.6:
                alineacion, ancla = "derecha", corta["x1"]
            else:
                alineacion = "centro"
                ancla = (corta["x0"] + corta["x1"]) / 2
        encontrados[celda] = {
            "pagina": corta["pagina"],
            "x": round(ancla, 2),
            "linea_base": round(corta["base"], 2),
            "tam": round(corta["tam"], 2),
            "negrita": corta["negrita"],
            "alineacion": alineacion,
        }

    # ---- celdas que la sonda no alcanzo -----------------------------------
    # Son celdas estrechas con una etiqueta fija al lado, que recorta el texto
    # antes de llegar al PDF. Se situan por geometria: el ancho de las columnas
    # de la hoja da la posicion, y una celda de la misma fila da la altura.
    MM100_A_PUNTOS = 72.0 / 2540.0
    anchos = datos.get("anchos") or []
    izquierda_mm = [0]
    for a in anchos:
        izquierda_mm.append(izquierda_mm[-1] + a)

    por_celda = {e["celda"]: e for e in datos["entradas"]}

    # La hoja se imprime ajustada al ancho de una pagina, asi que la escala no
    # es la nominal. Se deduce con una recta sobre las celdas que si se han
    # localizado con la sonda.
    def recta(muestras):
        n = len(muestras)
        if n < 2:
            return 1.0, 0.0
        sx = sum(m[0] for m in muestras); sy = sum(m[1] for m in muestras)
        sxx = sum(m[0] * m[0] for m in muestras)
        sxy = sum(m[0] * m[1] for m in muestras)
        den = n * sxx - sx * sx
        a = (n * sxy - sx * sy) / den if den else 1.0
        return a, (sy - a * sx) / n

    muestras_x = []
    for celda, sitio in encontrados.items():
        e = por_celda.get(celda)
        if e and sitio["alineacion"] == "izquierda":
            muestras_x.append((izquierda_mm[e["col"]] * MM100_A_PUNTOS, sitio["x"]))
    ax, bx = recta(muestras_x)

    def x_de(col):
        return ax * izquierda_mm[col] * MM100_A_PUNTOS + bx

    # Altura: se ajusta una recta entre la altura acumulada de cada fila en la
    # hoja y la linea base que se ha medido en el PDF. Con 60 muestras el ajuste
    # es practicamente exacto, y sirve para cualquier fila.
    altos = datos.get("altos") or []
    arriba_mm = [0]
    for a in altos:
        arriba_mm.append(arriba_mm[-1] + a)

    muestras = []
    for celda, sitio in encontrados.items():
        e = por_celda.get(celda)
        if e and e["fila"] < len(arriba_mm):
            muestras.append((arriba_mm[e["fila"]] * MM100_A_PUNTOS, sitio["linea_base"]))
    a, b = recta(muestras)

    def linea_base_de(fila):
        return round(a * arriba_mm[fila] * MM100_A_PUNTOS + b, 2)

    tam_por_fila = {}
    base_por_fila = {}
    for celda, sitio in encontrados.items():
        e = por_celda.get(celda)
        if e:
            tam_por_fila.setdefault(e["fila"], sitio["tam"])
            base_por_fila.setdefault(e["fila"], sitio["linea_base"])
    tam_normal = 7.41
    if tam_por_fila:
        valores = sorted(tam_por_fila.values())
        tam_normal = valores[len(valores) // 2]

    calculadas_por_geometria = 0
    for celda, e in por_celda.items():
        if celda in encontrados or e["fila"] >= len(arriba_mm):
            continue
        alin = ALINEACION.get(str(e["alineacion"]).upper(), "auto")
        x0 = x_de(e["col"])
        x1 = x_de(e["col"] + 1)
        if alin == "centro":
            x = (x0 + x1) / 2
        elif alin == "derecha":
            x = x1 - 1.5
        else:
            alin, x = "izquierda", x0 + 1.5
        encontrados[celda] = {
            "pagina": 0,
            "x": round(x, 2),
            "linea_base": base_por_fila.get(e["fila"], linea_base_de(e["fila"])),
            "tam": tam_por_fila.get(e["fila"], tam_normal),
            "negrita": False,
            "alineacion": alin,
            "por_geometria": True,
        }
        calculadas_por_geometria += 1

    # El libro esta protegido con contrasena y no deja vaciar las celdas de
    # formula, asi que su resultado viejo se quedo impreso en el PDF en blanco.
    # Se localiza por su contenido, que es inconfundible, y se apunta para
    # borrarlo al generar. Asi no se toca nada mas del impreso.
    RESTOS = re.compile(
        r"^(CIE INCOMPLETO|COMPLETADO|CUPS CORRECTO|ERROR: CUPS.*|\d{14,18}[A-Z]{0,2})$")
    base = pymupdf.open(os.path.join(PLANTILLAS, os.path.basename(datos["base_pdf"])))
    tapar = []
    for pag in base:
        for bloque in pag.get_text("dict")["blocks"]:
            for linea in bloque.get("lines", []):
                for trozo in linea.get("spans", []):
                    if RESTOS.match(trozo["text"].strip()):
                        tapar.append([round(v, 2) for v in trozo["bbox"]])
    base.close()

    originales = {e["celda"]: e["original"] for e in datos["entradas"]
                  if e.get("original") and e["celda"] not in datos["calculadas"]}

    mapa = {
        "tapar": tapar,
        "valores_originales": originales,
        "_nota": ("Generado por herramientas/mapear_cie.py y "
                  "herramientas/posiciones_cie.py. No editar a mano."),
        "base_pdf": os.path.basename(datos["base_pdf"]),
        "posiciones": encontrados,
        "controles": datos["controles"],
        "calculadas": datos["calculadas"],
    }

    destino = os.path.join(PLANTILLAS, "cie_mapa.json")
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(mapa, fh, ensure_ascii=False, indent=1)

    sin_sitio = sorted({s for s in datos["sondas"].values() if s not in encontrados})
    print(f"celdas situadas : {len(encontrados)}")
    print(f"sin localizar   : {len(sin_sitio)}  {sin_sitio[:12]}")
    reparto = {}
    for v in encontrados.values():
        reparto[v["alineacion"]] = reparto.get(v["alineacion"], 0) + 1
    print(f"alineaciones    : {reparto}")
    print(f"por geometria   : {calculadas_por_geometria}")
    print(f"rotulos del impreso: {len(originales)}")
    print(f"mapa -> {destino}")
    os.remove(tmp)


if __name__ == "__main__":
    main()
