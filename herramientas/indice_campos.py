# -*- coding: utf-8 -*-
"""
Hace la lista de campos de cada impreso, para poder elegirlos desde la pantalla.

Los impresos oficiales tienen los campos con nombres que no dicen nada
(`Texto354`, `CampoTexto26[0]`). Aqui se recorre cada uno y se apunta, ademas
del nombre, en que pagina esta, de que tipo es y **que pone escrito al lado**,
que es lo unico por lo que una persona puede reconocerlo.

La etiqueta se busca en el texto de la pagina: primero lo que hay justo a la
izquierda en la misma linea, y si no hay nada, lo que queda encima. En el MTD
muchos rotulos son dibujos y no texto, asi que se queda sin etiqueta y se
identifica por pagina y posicion.

    python herramientas/indice_campos.py

Escribe docs/plantillas/campos.json. Hay que volver a ejecutarlo si cambia un
impreso oficial.
"""

import contextlib
import io
import json
import os
import sys

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "docs", "plantillas")
SALIDA = os.path.join(PLANTILLAS, "campos.json")

TIPOS = {
    pymupdf.PDF_WIDGET_TYPE_TEXT: "texto",
    pymupdf.PDF_WIDGET_TYPE_CHECKBOX: "casilla",
    pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON: "casilla",
    pymupdf.PDF_WIDGET_TYPE_COMBOBOX: "lista",
    pymupdf.PDF_WIDGET_TYPE_LISTBOX: "lista",
}

# Distancias en puntos: lo que se considera "al lado"
A_LA_IZQUIERDA = 220
ENCIMA = 26


def trozos_de_texto(pagina):
    """Los cachos de texto de la pagina con su sitio."""
    fuera = []
    for bloque in pagina.get_text("dict")["blocks"]:
        for linea in bloque.get("lines", []):
            texto = "".join(t["text"] for t in linea["spans"]).strip()
            if not texto or len(texto) > 90:
                continue
            x0, y0, x1, y1 = linea["bbox"]
            fuera.append({"t": texto, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    return fuera


def etiqueta_de(rect, textos):
    """Lo que hay escrito al lado del campo, que es como lo reconoce una persona."""
    centro = (rect.y0 + rect.y1) / 2

    # A la izquierda, en la misma linea
    izquierda = [t for t in textos
                 if t["x1"] <= rect.x0 + 2
                 and t["y0"] - 3 <= centro <= t["y1"] + 3
                 and rect.x0 - t["x1"] < A_LA_IZQUIERDA]
    if izquierda:
        return max(izquierda, key=lambda t: t["x1"])["t"]

    # Justo encima
    arriba = [t for t in textos
              if t["y1"] <= rect.y0 + 2 and rect.y0 - t["y1"] < ENCIMA
              and t["x1"] > rect.x0 - 40 and t["x0"] < rect.x1 + 40]
    if arriba:
        return max(arriba, key=lambda t: t["y1"])["t"]

    # A la derecha: las casillas suelen llevar el rotulo detras
    derecha = [t for t in textos
               if t["x0"] >= rect.x1 - 2
               and t["y0"] - 3 <= centro <= t["y1"] + 3
               and t["x0"] - rect.x1 < 60]
    if derecha:
        return min(derecha, key=lambda t: t["x0"])["t"]

    return ""


def limpiar(etiqueta):
    """Quita los puntos suspensivos y los dos puntos de los impresos."""
    e = etiqueta.strip(" .:·… ")
    return " ".join(e.split())


def campos_de(ruta):
    with contextlib.redirect_stderr(io.StringIO()):
        doc = pymupdf.open(ruta)
        fuera, vistos = [], set()
        for pagina in doc:
            textos = trozos_de_texto(pagina)
            for w in pagina.widgets():
                nombre = w.field_name
                if not nombre or nombre in vistos:
                    continue
                vistos.add(nombre)
                fuera.append({
                    "n": nombre,
                    "p": pagina.number + 1,
                    "t": TIPOS.get(w.field_type, "otro"),
                    "e": limpiar(etiqueta_de(w.rect, textos)),
                    # Para ordenarlos como se leen: de arriba abajo y de
                    # izquierda a derecha
                    "y": round(w.rect.y0, 1),
                    "x": round(w.rect.x0, 1),
                })
        doc.close()
    fuera.sort(key=lambda c: (c["p"], c["y"], c["x"]))
    return fuera


def main():
    indice = {}
    for archivo in sorted(os.listdir(PLANTILLAS)):
        if not archivo.lower().endswith(".pdf") or archivo == "CIE_base.pdf":
            continue
        campos = campos_de(os.path.join(PLANTILLAS, archivo))
        indice[archivo] = campos
        con = sum(1 for c in campos if c["e"])
        print(f"  {archivo:<18} {len(campos):>4} campos · {con} con etiqueta")

    with io.open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(indice, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"\n  {os.path.relpath(SALIDA, RAIZ)}: "
          f"{os.path.getsize(SALIDA) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
