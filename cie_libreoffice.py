# -*- coding: utf-8 -*-
"""
Rellena el CIE.xls oficial y lo exporta a PDF.

IMPORTANTE: este script NO se ejecuta con el Python del sistema, sino con el
que trae LibreOffice, que es el unico que tiene las librerias UNO:

    "C:\\Program Files\\LibreOffice\\program\\python.exe" cie_libreoffice.py peticion.json

Se hace asi porque el libro CIE.xls calcula por formula el IDENTIFICADOR DEL CIE
y los avisos "FALTAN DATOS" / "COMPLETADO". Escribir las celdas con una libreria
de Python normal romperia esas formulas; abriendolo con LibreOffice se recalculan
igual que cuando lo rellenas a mano.

La peticion JSON tiene esta forma:
    {"plantilla": "...CIE.xls", "xls_destino": "...", "pdf_destino": "...",
     "celdas": {"B7": "12345678Z", ...}}
"""

import json
import os
import random
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import uno  # noqa: F401  (lo aporta LibreOffice)
from com.sun.star.beans import PropertyValue
from com.sun.star.connection import NoConnectException

# El perfil NO puede vivir dentro del proyecto: la carpeta se llama
# "CLAUDE CODE" y LibreOffice no arranca si la ruta de -env:UserInstallation
# lleva espacios. Se guarda en AppData, que no los tiene.
PERFIL = os.path.join(
    os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(),
    "BoletinesIRVE", "perfil-libreoffice")


def prop(nombre, valor):
    p = PropertyValue()
    p.Name = nombre
    p.Value = valor
    return p


def puerto_libre():
    for _ in range(30):
        p = random.randint(2100, 2999)
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 2199


def arrancar_libreoffice(espera=120):
    """
    Arranca LibreOffice en segundo plano con un perfil propio y se conecta.

    Usa un perfil aparte, y no el del usuario, por dos motivos: puedes tener
    LibreOffice abierto mientras generas expedientes, y si alguna vez se cierra
    mal, el dialogo de "recuperar documentos" no deja la aplicacion colgada
    esperando a que alguien pulse un boton.
    """
    os.makedirs(PERFIL, exist_ok=True)
    perfil_url = Path(PERFIL).as_uri()
    puerto = puerto_libre()
    soffice = os.path.join(os.path.dirname(sys.executable), "soffice.exe")
    if not os.path.exists(soffice):
        soffice = os.path.join(os.path.dirname(sys.executable), "soffice")

    subprocess.Popen(
        [soffice,
         f"-env:UserInstallation={perfil_url}",
         "--headless", "--invisible", "--norestore", "--nologo",
         "--nodefault", "--nolockcheck",
         f"--accept=socket,host=127.0.0.1,port={puerto};urp;"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local)
    destino = (f"uno:socket,host=127.0.0.1,port={puerto};urp;"
               "StarOffice.ComponentContext")

    plazo = time.time() + espera
    while True:
        try:
            return resolver.resolve(destino)
        except NoConnectException:
            if time.time() > plazo:
                raise RuntimeError(
                    "LibreOffice no respondio a tiempo. Cierra LibreOffice "
                    "del todo y vuelve a intentarlo.")
            time.sleep(0.4)


def url(ruta):
    return "file:///" + os.path.abspath(ruta).replace("\\", "/")


def buscar_estado(hoja):
    """
    Localiza el indicador que el propio libro escribe junto a la cabecera:
    "CIE INCOMPLETO" mientras falten datos, "COMPLETADO" cuando esta listo.
    """
    for fila in range(0, 8):
        for col in range(0, 24):
            try:
                texto = hoja.getCellByPosition(col, fila).getString().strip()
            except Exception:  # noqa: BLE001
                continue
            if "COMPLET" in texto.upper():
                return texto
    return ""


def contar_faltan(hoja):
    """Cuenta cuantas celdas siguen diciendo FALTAN DATOS."""
    faltan = []
    for fila in range(0, 60):
        for col in range(0, 24):
            try:
                texto = hoja.getCellByPosition(col, fila).getString().strip()
            except Exception:  # noqa: BLE001
                continue
            if texto.upper().startswith("FALTAN DATOS"):
                faltan.append(f"fila {fila + 1}")
    return faltan


def main():
    with open(sys.argv[1], encoding="utf-8") as fh:
        pet = json.load(fh)

    ctx = arrancar_libreoffice()
    desktop = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", ctx)

    doc = desktop.loadComponentFromURL(
        url(pet["plantilla"]), "_blank", 0,
        (prop("Hidden", True), prop("UpdateDocMode", 1), prop("MacroExecutionMode", 0)))

    try:
        hojas = doc.Sheets
        cie = hojas.getByName("CIE")

        for celda, valor in pet["celdas"].items():
            valor = "" if valor is None else str(valor)
            if not valor:
                continue
            rango = cie.getCellRangeByName(celda)
            # Los desplegables y los codigos con ceros a la izquierda deben
            # entrar como texto; el resto, si es numero, como numero.
            try:
                numero = float(valor.replace(",", "."))
                es_numero = (
                    valor.replace(",", ".").replace("-", "").replace(".", "").isdigit()
                    and not valor.startswith("0")
                    and len(valor) < 12
                )
            except ValueError:
                es_numero = False
            if es_numero:
                rango.setValue(numero)
            else:
                rango.setString(valor)

        doc.calculateAll()

        estado = buscar_estado(cie)
        faltan = contar_faltan(cie)

        # Guardar la copia del libro con los datos, por si hay que retocar.
        # Se guarda ANTES de limpiar nada, para que conserve sus formulas.
        doc.storeToURL(url(pet["xls_destino"]), (prop("FilterName", "MS Excel 97"),))

        # El libro comprueba el CUPS con una funcion que solo existe en Excel.
        # LibreOffice la deja como "#¿MACRO?" y eso no puede salir impreso en
        # un documento oficial, asi que se vacian esas celdas de aviso. Son
        # ayudas para quien rellena, no campos del certificado.
        limpiadas = 0
        for fila in range(0, 57):
            for col in range(0, 26):
                celda = cie.getCellByPosition(col, fila)
                if celda.getError():
                    # setFormula("") vacia de verdad; setString("") no borra la formula
                    celda.setFormula("")
                    limpiadas += 1

        # Y se vuelve a escribir el aviso del CUPS, ya calculado en Python.
        for celda, valor in (pet.get("textos") or {}).items():
            cie.getCellRangeByName(celda).setString(str(valor))

        if limpiadas:
            print(f"LIMPIADAS={limpiadas}")

        # Para el PDF dejamos visible solo la hoja del certificado
        for nombre in hojas.ElementNames:
            if nombre != "CIE":
                try:
                    hojas.getByName(nombre).IsVisible = False
                except Exception:  # noqa: BLE001
                    pass

        # El libro no trae area de impresion, asi que saldrian tambien las
        # columnas W y X, que son las auxiliares de control ("FALTAN DATOS" y
        # la validacion del CUPS). El certificado ocupa de la columna A a la V.
        try:
            from com.sun.star.table import CellRangeAddress
            area = CellRangeAddress()
            area.Sheet = cie.RangeAddress.Sheet
            area.StartColumn, area.EndColumn = 0, 21
            area.StartRow, area.EndRow = 0, 56
            cie.setPrintAreas((area,))
        except Exception:  # noqa: BLE001
            pass

        doc.storeToURL(url(pet["pdf_destino"]), (prop("FilterName", "calc_pdf_Export"),))

        print(f"ESTADO={estado}")
        if faltan:
            print(f"FALTAN={len(faltan)}")
    finally:
        try:
            doc.close(False)
        except Exception:  # noqa: BLE001
            pass
        # Se cierra la instancia que hemos arrancado, para no dejarla suelta.
        try:
            desktop.terminate()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
