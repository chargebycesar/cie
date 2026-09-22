# -*- coding: utf-8 -*-
"""
Repara el diccionario de formulario del anexo IVE.

Ese impreso viene con el AcroForm apuntando a un objeto que no existe, asi que
la lista de campos esta vacia. PyMuPDF se lo salta porque recorre las
anotaciones de cada pagina, pero las librerias de navegador (pdf-lib) miran la
lista de campos y no encuentran nada.

Aqui se reconstruye esa lista a partir de los campos que realmente hay en las
paginas. El impreso no se toca en nada mas.

    python herramientas/reparar_anexo.py
"""

import os
import shutil
import sys

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "docs", "plantillas")
FUENTE = os.path.join(RAIZ, "fuente")


def raiz_del_campo(doc, xref, visto=None):
    """Sube por la cadena de padres hasta el campo de primer nivel."""
    visto = visto or set()
    while True:
        if xref in visto:
            return xref
        visto.add(xref)
        tipo, valor = doc.xref_get_key(xref, "Parent")
        if tipo != "xref":
            return xref
        xref = int(valor.split()[0])


def reparar(ruta):
    doc = pymupdf.open(ruta)
    catalogo = doc.pdf_catalog()

    tipo, valor = doc.xref_get_key(catalogo, "AcroForm")
    campos_actuales = None
    if tipo == "xref":
        campos_actuales = doc.xref_get_key(int(valor.split()[0]), "Fields")
    if campos_actuales and campos_actuales[0] not in ("null", "unknown"):
        print(f"  {os.path.basename(ruta)}: ya tiene lista de campos, no toco nada")
        doc.close()
        return False

    raices, orden = set(), []
    for pagina in doc:
        for w in pagina.widgets():
            r = raiz_del_campo(doc, w.xref)
            if r not in raices:
                raices.add(r)
                orden.append(r)

    if not orden:
        print(f"  {os.path.basename(ruta)}: no encuentro campos")
        doc.close()
        return False

    lista = " ".join(f"{x} 0 R" for x in orden)
    nuevo = doc.get_new_xref()
    doc.update_object(nuevo, f"<< /Fields [ {lista} ] "
                             f"/DA (/Helv 0 Tf 0 g) /NeedAppearances true >>")
    doc.xref_set_key(catalogo, "AcroForm", f"{nuevo} 0 R")

    copia = ruta + ".tmp"
    doc.save(copia, garbage=3, deflate=True)
    doc.close()
    shutil.move(copia, ruta)
    print(f"  {os.path.basename(ruta)}: lista reconstruida con {len(orden)} campos")
    return True


def main():
    objetivos = sys.argv[1:] or ["ANEXO_IVE.pdf"]
    for nombre in objetivos:
        ruta = os.path.join(PLANTILLAS, nombre)
        respaldo = ruta + ".original"
        if not os.path.exists(respaldo):
            shutil.copy(ruta, respaldo)
        reparar(ruta)


if __name__ == "__main__":
    main()
