# -*- coding: utf-8 -*-
"""
Genera el CIE escribiendo encima del impreso, sin necesitar LibreOffice.

El libro oficial `CIE.xls` calcula por formula tres cosas: el identificador del
certificado, el aviso "FALTAN DATOS"/"COMPLETADO" y la comprobacion del CUPS.
Aqui estan reimplementadas esas tres formulas, y los datos se dibujan sobre
`plantillas/CIE_base.pdf`, que es el impreso en blanco exportado una sola vez.

El sitio exacto de cada dato esta en `plantillas/cie_mapa.json`, que produjeron
`herramientas/mapear_cie.py` y `herramientas/posiciones_cie.py`.
"""

import json
import os
import random
import re
from datetime import datetime

import pymupdf

RAIZ = os.path.dirname(os.path.abspath(__file__))
PLANTILLAS = os.path.join(RAIZ, "docs", "plantillas")

LETRAS = "TRWAGMYFPDXBNJZSQVHLCKE"

# El dia 0 de las hojas de calculo es el 30 de diciembre de 1899.
ORIGEN_SERIE = datetime(1899, 12, 30)

TIPO_LETRA = "helv"
TIPO_LETRA_NEGRITA = "hebo"


def cargar_mapa():
    with open(os.path.join(PLANTILLAS, "cie_mapa.json"), encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# Las tres formulas del libro
# --------------------------------------------------------------------------

def identificador(momento=None):
    """
    Reproduce el IDENTIFICADOR DEL CIE del libro oficial:

        B13 = (ROUND(RAND()*5)+1) * 1.000.000.000.000.000
        B14 = ROUND((AHORA()-40000)*10000) * 10.000.000
        B15 = ROUND(RAND()*10000000)
        numero = B13 + B14 + B15
        letras = tabla[numero//23 % ...]  sobre numero modulo 529

    Son 16 cifras y dos letras de control, igual que las que venia sacando la
    hoja de calculo.
    """
    momento = momento or datetime.now()
    serie = (momento - ORIGEN_SERIE).total_seconds() / 86400.0

    b13 = (round(random.random() * 5) + 1) * 10 ** 15
    b14 = round((serie - 40000) * 10000) * 10 ** 7
    b15 = round(random.random() * 10 ** 7)
    numero = b13 + b14 + b15

    resto = numero % 529
    return f"{numero}{LETRAS[resto // 23]}{LETRAS[resto % 23]}"


def _requeridos(formula, celdas):
    """Evalua la casilla de control que dice cuantos datos hace falta que haya."""
    f = (formula or "").strip()
    if not f:
        return 0
    if f.isdigit():
        return int(f)
    # =+IF(C20="Nueva";6;7)  ó  =2+IF(L38="...";1;0)
    m = re.match(r"^=\+?(\d*)\+?IF\(([A-Z]+\d+)\s*=\s*\"(.*?)\";\s*(\d+);\s*(\d+)\)$", f)
    if m:
        base = int(m.group(1) or 0)
        valor = str(celdas.get(m.group(2), "")).strip().lower()
        esperado = m.group(3).strip().lower()
        return base + int(m.group(4) if valor == esperado else m.group(5))
    m = re.match(r"^=\+?(\d+)$", f)
    if m:
        return int(m.group(1))
    return 0


def estado(mapa, celdas):
    """"COMPLETADO" si no falta ningun dato obligatorio, si no "CIE INCOMPLETO"."""
    celdas = {**mapa.get("valores_originales", {}), **celdas}
    for control in mapa["controles"]:
        llenos = control["fijos"] + sum(
            1 for c in control["celdas_entrada"] if str(celdas.get(c, "")).strip())
        if llenos - _requeridos(control["formula_x"], celdas) < 0:
            return "CIE INCOMPLETO", control["rango"]
    return "COMPLETADO", None


def filas_incompletas(mapa, celdas):
    """Las filas del impreso a las que todavia les falta algun dato."""
    celdas = {**mapa.get("valores_originales", {}), **celdas}
    faltan = []
    for control in mapa["controles"]:
        llenos = control["fijos"] + sum(
            1 for c in control["celdas_entrada"] if str(celdas.get(c, "")).strip())
        if llenos - _requeridos(control["formula_x"], celdas) < 0:
            faltan.append(control["rango"].split(":")[0].lstrip("A") or control["rango"])
    return faltan


# --------------------------------------------------------------------------
# Dibujar
# --------------------------------------------------------------------------

def _escribir(page, sitio, texto, color=(0, 0, 0)):
    if not texto:
        return
    tam = sitio.get("tam") or 7.41
    fuente = TIPO_LETRA_NEGRITA if sitio.get("negrita") else TIPO_LETRA
    lineas = str(texto).split("\n")
    alto_linea = tam * 1.25
    # Con varias lineas el bloque se reparte arriba y abajo de la linea medida
    inicio = sitio["linea_base"] - alto_linea * (len(lineas) - 1) / 2

    for i, linea in enumerate(lineas):
        ancho = pymupdf.get_text_length(linea, fontname=fuente, fontsize=tam)
        alin = sitio.get("alineacion", "izquierda")
        if alin == "centro":
            x = sitio["x"] - ancho / 2
        elif alin == "derecha":
            x = sitio["x"] - ancho
        else:
            x = sitio["x"]
        page.insert_text((x, inicio + i * alto_linea), linea,
                         fontname=fuente, fontsize=tam, color=color)


def generar_cie_pdf(celdas, destino, texto_cups="", mapa=None, momento=None):
    """
    Escribe el CIE en `destino` a partir del diccionario celda -> valor.
    Devuelve (identificador, estado).
    """
    mapa = mapa or cargar_mapa()
    base = os.path.join(PLANTILLAS, mapa.get("base_pdf", "CIE_base.pdf"))
    doc = pymupdf.open(base)

    # El impreso trae texto dentro de algunas casillas editables (rotulos como
    # "C.G.P. (esquema):"). Se recuperan aqui, y lo que escriba la aplicacion
    # manda sobre ellos.
    celdas = {**mapa.get("valores_originales", {}), **celdas}

    # El impreso en blanco arrastra el resultado viejo de las formulas, porque
    # el libro esta protegido con contrasena y no deja vaciarlas. Se tapa.
    zonas = mapa.get("tapar", [])
    if zonas:
        pagina = doc[0]
        for x0, y0, x1, y1 in zonas:
            pagina.add_redact_annot(pymupdf.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1))
        # Borrado de verdad: el texto viejo desaparece del PDF, no se tapa.
        pagina.apply_redactions()

    posiciones = mapa["posiciones"]
    ident = identificador(momento)
    texto_estado, _ = estado(mapa, celdas)

    # R4 es el "COMPLETADO" de arriba. Va en el documento, y va en el sitio
    # exacto donde lo pone la hoja de calculo: sin el, la EICI rechaza el
    # certificado. Lo que queda en blanco es el hueco grande de al lado, que es
    # donde ellos sellan y firman; son dos cosas distintas dentro del mismo
    # recuadro y confundirlas costo un rechazo.
    calculadas = {
        mapa["calculadas"].get("R4", "estado"): ("R4", texto_estado),
        mapa["calculadas"].get("R6", "identificador"): ("R6", ident),
        mapa["calculadas"].get("M19", "cups_ok"): ("M19", texto_cups),
    }

    for celda, valor in celdas.items():
        sitio = posiciones.get(celda)
        if sitio and str(valor).strip():
            _escribir(doc[sitio["pagina"]], sitio, valor)

    for _, (celda, valor) in calculadas.items():
        sitio = posiciones.get(celda)
        if sitio and str(valor).strip():
            _escribir(doc[sitio["pagina"]], sitio, valor)

    doc.set_metadata({"title": os.path.basename(destino),
                      "producer": "Boletines IRVE"})
    doc.save(destino, garbage=3, deflate=True)
    doc.close()
    return ident, texto_estado


def disponible():
    """True si estan los dos ficheros que hacen falta para trabajar sin Calc."""
    return (os.path.exists(os.path.join(PLANTILLAS, "cie_mapa.json"))
            and os.path.exists(os.path.join(PLANTILLAS, "CIE_base.pdf")))
