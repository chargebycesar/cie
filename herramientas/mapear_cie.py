# -*- coding: utf-8 -*-
"""
Prepara el CIE para que la aplicacion no necesite LibreOffice.

Esto se ejecuta UNA SOLA VEZ, en el ordenador de quien mantiene el programa, y
produce dos ficheros que ya viajan con la aplicacion:

    plantillas/CIE_base.pdf    el impreso en blanco, tal cual lo imprime Calc
    plantillas/cie_mapa.json   donde cae cada dato dentro de ese PDF

A partir de ahi, generar un CIE es escribir texto encima del PDF con PyMuPDF,
sin LibreOffice de por medio.

Se ejecuta con el Python de LibreOffice:

    "C:\\Program Files\\LibreOffice\\program\\python.exe" herramientas/mapear_cie.py
"""

import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import uno  # noqa: F401  (lo aporta LibreOffice)
from com.sun.star.beans import PropertyValue
from com.sun.star.connection import NoConnectException

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "docs", "plantillas")
FUENTE = os.path.join(RAIZ, "fuente")
PERFIL = os.path.join(os.environ.get("LOCALAPPDATA") or "/tmp",
                      "BoletinesIRVE", "perfil-libreoffice")

# Zona del impreso: columnas A..V, filas 1..57. Lo de la derecha son columnas
# auxiliares de control que no se imprimen.
COL_MAX, FILA_MAX = 21, 56

# Celdas de formula cuyo resultado tambien hay que saber colocar.
CELDAS_CALCULADAS = {
    "R4": "estado",           # COMPLETADO / CIE INCOMPLETO
    "R6": "identificador",    # IDENTIFICADOR DEL CIE
    "M19": "cups_ok",         # CUPS CORRECTO / ERROR
}


def prop(nombre, valor):
    p = PropertyValue()
    p.Name = nombre
    p.Value = valor
    return p


def arrancar():
    os.makedirs(PERFIL, exist_ok=True)
    puerto = random.randint(2100, 2999)
    soffice = os.path.join(os.path.dirname(sys.executable), "soffice.exe")
    if not os.path.exists(soffice):
        soffice = os.path.join(os.path.dirname(sys.executable), "soffice")
    subprocess.Popen(
        [soffice, f"-env:UserInstallation={Path(PERFIL).as_uri()}",
         "--headless", "--invisible", "--norestore", "--nologo",
         "--nodefault", "--nolockcheck",
         f"--accept=socket,host=127.0.0.1,port={puerto};urp;"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    local = uno.getComponentContext()
    res = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local)
    destino = f"uno:socket,host=127.0.0.1,port={puerto};urp;StarOffice.ComponentContext"
    plazo = time.time() + 120
    while True:
        try:
            return res.resolve(destino)
        except NoConnectException:
            if time.time() > plazo:
                raise RuntimeError("LibreOffice no arranco")
            time.sleep(0.4)


def nombre_celda(col, fila):
    letra = chr(65 + col) if col < 26 else "A" + chr(65 + col - 26)
    return f"{letra}{fila + 1}"


def area_impresion(hoja):
    from com.sun.star.table import CellRangeAddress
    a = CellRangeAddress()
    a.Sheet = hoja.RangeAddress.Sheet
    a.StartColumn, a.EndColumn = 0, COL_MAX
    a.StartRow, a.EndRow = 0, FILA_MAX
    hoja.setPrintAreas((a,))


def solo_cie(doc):
    for nombre in doc.Sheets.ElementNames:
        if nombre != "CIE":
            try:
                doc.Sheets.getByName(nombre).IsVisible = False
            except Exception:  # noqa: BLE001
                pass


def exportar(doc, destino):
    doc.storeToURL(Path(destino).as_uri(), (prop("FilterName", "calc_pdf_Export"),))


def main():
    plantilla = os.path.join(FUENTE, "CIE.xls")
    base_pdf = os.path.join(PLANTILLAS, "CIE_base.pdf")
    mapa_json = os.path.join(PLANTILLAS, "cie_mapa.json")

    ctx = arrancar()
    desktop = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL(
        Path(plantilla).as_uri(), "_blank", 0,
        (prop("Hidden", True), prop("UpdateDocMode", 1)))

    try:
        cie = doc.Sheets.getByName("CIE")

        # ---- 1. localizar las celdas de entrada (las desbloqueadas) --------
        entradas = []
        for fila in range(FILA_MAX + 1):
            for col in range(COL_MAX + 1):
                cel = cie.getCellByPosition(col, fila)
                try:
                    if cel.CellProtection.IsLocked:
                        continue
                except Exception:  # noqa: BLE001
                    continue
                entradas.append({
                    "celda": nombre_celda(col, fila),
                    "col": col, "fila": fila,
                    "alineacion": str(cel.HoriJustify),
                    # Algunas casillas editables traen ya texto del impreso
                    # ("C.G.P. (esquema):"). Hay que conservarlo.
                    "original": cel.getString().strip(),
                })
        print(f"celdas de entrada: {len(entradas)}")

        # ---- 1b. geometria de la hoja -------------------------------------
        # Sirve para situar las celdas estrechas, cuyo texto de sonda queda
        # recortado por la etiqueta que tienen al lado y no llega al PDF.
        anchos = [cie.Columns.getByIndex(c).Width for c in range(COL_MAX + 1)]
        altos = [cie.Rows.getByIndex(f).Height for f in range(FILA_MAX + 1)]
        for e in entradas:
            cel = cie.getCellByPosition(e["col"], e["fila"])
            try:
                e["combinada"] = bool(cel.getIsMerged())
            except Exception:  # noqa: BLE001
                e["combinada"] = False

        # ---- 2. filas de control del "FALTAN DATOS" -----------------------
        controles = []
        for fila in range(FILA_MAX + 20):
            cel = cie.getCellByPosition(22, fila)          # columna W
            f = cel.getFormula()
            if "FALTAN DATOS" not in f:
                continue
            import re
            m = re.search(r"COUNTA\(([A-Z]+\d+):([A-Z]+\d+)\)", f)
            if not m:
                continue
            controles.append({
                "rango": f"{m.group(1)}:{m.group(2)}",
                "x": nombre_celda(23, fila),
                "formula_x": cie.getCellByPosition(23, fila).getFormula(),
            })
        print(f"filas de control: {len(controles)}")

        # ---- 3. vaciar todo y contar lo que queda fijo en cada control -----
        for e in entradas:
            cie.getCellRangeByName(e["celda"]).setFormula("")
        doc.calculateAll()

        for c in controles:
            rango = cie.getCellRangeByName(c["rango"])
            dirs = rango.RangeAddress
            fijos = 0
            for fila in range(dirs.StartRow, dirs.EndRow + 1):
                for col in range(dirs.StartColumn, dirs.EndColumn + 1):
                    if cie.getCellByPosition(col, fila).getString().strip():
                        fijos += 1
            c["fijos"] = fijos
            c["celdas_entrada"] = [
                e["celda"] for e in entradas
                if dirs.StartRow <= e["fila"] <= dirs.EndRow
                and dirs.StartColumn <= e["col"] <= dirs.EndColumn
            ]

        # ---- 4. el PDF en blanco ------------------------------------------
        solo_cie(doc)
        area_impresion(cie)
        # las celdas calculadas tambien se vacian: las escribe la aplicacion
        formulas_guardadas = {}
        for celda in CELDAS_CALCULADAS:
            formulas_guardadas[celda] = cie.getCellRangeByName(celda).getFormula()
            cie.getCellRangeByName(celda).setFormula("")
        doc.calculateAll()
        if os.path.exists(base_pdf):
            os.remove(base_pdf)
        exportar(doc, base_pdf)
        print(f"PDF en blanco -> {base_pdf}")

        # ---- 5. sondas ----------------------------------------------------
        # Una celda estrecha recorta su texto si la de al lado tiene contenido,
        # asi que no se puede sondear todo a la vez. Se hacen pasadas dejando
        # una sola celda escrita por fila, y dos tamanos de sonda para deducir
        # despues si el texto va pegado a la izquierda, centrado o a la derecha.
        from collections import defaultdict
        por_fila = defaultdict(list)
        for e in entradas:
            por_fila[e["fila"]].append(e)
        for celda, nombre in CELDAS_CALCULADAS.items():
            fila = int("".join(ch for ch in celda if ch.isdigit())) - 1
            por_fila[fila].append({"celda": celda, "fila": fila, "calculada": True})

        pasadas = max(len(v) for v in por_fila.values())
        print(f"celdas por fila (maximo): {pasadas}")

        # Cada celda tiene SIEMPRE el mismo testigo, en las dos pasadas, para
        # poder emparejar la sonda corta con la larga.
        todas = [e["celda"] for e in entradas] + list(CELDAS_CALCULADAS)
        sondas = {f"Z{n:04d}Z": celda for n, celda in enumerate(todas)}
        testigo_de = {celda: token for token, celda in sondas.items()}

        def vaciar_todo():
            for celda in todas:
                cie.getCellRangeByName(celda).setFormula("")

        archivos = []
        for i in range(pasadas):
            lote = [v[i]["celda"] for v in por_fila.values() if len(v) > i]
            for largo, sufijo in ((0, "corta"), (9, "larga")):
                vaciar_todo()
                for celda in lote:
                    cie.getCellRangeByName(celda).setString(
                        testigo_de[celda] + "W" * largo)
                doc.calculateAll()
                ruta = os.path.join(PERFIL, f"sonda_{i:02d}_{sufijo}.pdf")
                if os.path.exists(ruta):
                    os.remove(ruta)
                exportar(doc, ruta)
                archivos.append([ruta, sufijo, largo])
            print(f"  pasada {i + 1}/{pasadas}  ({len(lote)} celdas)")
        vaciar_todo()

        datos = {
            "entradas": entradas,
            "controles": controles,
            "calculadas": CELDAS_CALCULADAS,
            "sondas": sondas,
            "archivos": archivos,
            "anchos": anchos,
            "altos": altos,
            "base_pdf": base_pdf,
        }
        with open(mapa_json + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=1)
        print(f"datos intermedios -> {mapa_json}.tmp")
        print("Ahora ejecuta:  python herramientas/posiciones_cie.py")
    finally:
        try:
            doc.close(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            desktop.terminate()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
