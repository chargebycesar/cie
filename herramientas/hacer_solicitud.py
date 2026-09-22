# -*- coding: utf-8 -*-
"""
Hace la plantilla rellenable de la solicitud a partir del impreso oficial.

El impreso que publica la Comunidad de Madrid es plano: no trae ni un campo
donde escribir. El que se usaba antes se los habia puesto alguien por su cuenta,
y se quedo caducado -otra Direccion General, otra Consejeria, otro apartado 3 y
otro apartado 6-. Esto coge el oficial de verdad y le pone los campos encima,
para que se rellene igual que los demas impresos.

Las casillas salen de la propia tabla del impreso: en cada fila, lo que hay
detras de un rotulo y hasta el siguiente rotulo es el hueco de ese dato. Asi no
hay coordenadas escritas a mano que se queden viejas en cuanto Industria mueva
una linea.

    python herramientas/hacer_solicitud.py

Lee fuente/SOLICITUD-oficial-15042024.pdf y escribe docs/plantillas/SOLICITUD.pdf.
Hay que volver a ejecutarlo si Industria cambia el impreso.
"""

import os
import re
import sys
import unicodedata

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEN = os.path.join(RAIZ, "fuente", "SOLICITUD-oficial-15042024.pdf")
DESTINO = os.path.join(RAIZ, "docs", "plantillas", "SOLICITUD.pdf")

# El cuadradito de marcar del impreso (una Wingdings metida como texto).
CUADRADO = ""

# Los puntos suspensivos del impreso marcan donde va cada dato de la firma.
PUNTOS = "." + chr(0x2026)

# Letra automatica. Con un tamano fijo, un nombre largo -"SAN SEBASTIAN DE LOS
# REYES"- se corta en el borde del hueco y el impreso sale mal; en automatico,
# los dos motores lo encogen hasta que cabe.
TAM_LETRA = 0
MARGEN = 1.0


def plano(texto):
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


# Que dato va detras de cada rotulo, en cada apartado. El nombre del campo se
# forma con el prefijo del apartado: "titular" + "nif" -> "titular_nif".
ROTULOS = {
    "nif": "nif",
    "primer apellido": "ap1",
    "segundo apellido": "ap2",
    "nombre/razon social": "nombre",
    "nombre": "nombre",
    "correo electronico": "email",
    "correo-e": "email",
    "categoria": "categoria",
    "no registro": "registro",
    "nombre del instalador": "instalador",
    "direccion": None,          # solo es el titulo de la fila
    "tipo de via": "tipo_via",
    "nombre via": "nombre_via",
    "no": "numero",
    "bloque": "bloque",
    "portal": "portal",
    "escalera": "escalera",
    "piso": "piso",
    "puerta": "puerta",
    "localidad": "localidad",
    "provincia": "provincia",
    "cp": "cp",
    "telefono fijo": "fijo",
    "telefono movil": "movil",
}

# Cada tabla de la primera pagina es un apartado de la solicitud.
APARTADOS = ["titular", "repre", "empresa", "proy", "dir", "empl"]


def campos_de_la_tabla(tabla, prefijo):
    """Los huecos de una tabla: lo que va detras de cada rotulo."""
    fuera = []
    rejilla = tabla.extract()
    for r, fila in enumerate(tabla.rows):
        celdas = fila.cells
        textos = [plano(x) for x in rejilla[r]]
        i = 0
        while i < len(celdas):
            nombre = ROTULOS.get(textos[i]) if textos[i] else None
            if not textos[i] or nombre is None:
                i += 1
                continue
            # el hueco llega hasta el siguiente rotulo de la fila
            j = i + 1
            while j < len(celdas) and not textos[j]:
                j += 1
            huecos = [c for c in celdas[i + 1:j] if c]
            if huecos:
                x0 = min(c[0] for c in huecos)
                x1 = max(c[2] for c in huecos)
                y0 = min(c[1] for c in huecos)
                y1 = max(c[3] for c in huecos)
                fuera.append((f"{prefijo}_{nombre}",
                              pymupdf.Rect(x0 + MARGEN, y0 + MARGEN,
                                           x1 - MARGEN, y1 - MARGEN)))
            i = j
    return fuera


def trozos_de(pagina):
    fuera = []
    for bloque in pagina.get_text("dict")["blocks"]:
        for linea in bloque.get("lines", []):
            for tramo in linea.get("spans", []):
                if tramo["text"].strip():
                    fuera.append((tramo["text"], pymupdf.Rect(tramo["bbox"])))
    return fuera


# Los tres grupos de casillas de la pagina 2, por el lado en que caen. El
# nombre lleva el numero de orden y no el rotulo: un rotulo se puede reescribir
# de un ano para otro y entonces el motor dejaria de encontrar su casilla.
GRUPOS = [("expediente", 0, 300), ("tipo", 300, 3000), ("doc", 0, 3000)]


def casillas_de_la_pagina(pagina):
    """Los cuadraditos de marcar, numerados por donde caen en la hoja.

    Arriba, el tipo de expediente. En medio, las dos columnas del tipo de
    instalacion. Abajo, la documentacion que se aporta.
    """
    cuadros = []
    for texto, caja in trozos_de(pagina):
        paso = caja.width / max(len(texto), 1)
        for k, c in enumerate(texto):
            if c == CUADRADO:
                x = caja.x0 + paso * k
                cuadros.append(pymupdf.Rect(x, caja.y0, x + min(paso, 11), caja.y1))

    # el tipo de expediente esta arriba; la documentacion, debajo del todo
    arriba = [c for c in cuadros if c.y0 < 190]
    medio = [c for c in cuadros if 190 <= c.y0 < 400]
    abajo = [c for c in cuadros if c.y0 >= 400]
    fuera = []
    for prefijo, grupo in (("expediente", arriba), ("tipo", medio), ("doc", abajo)):
        # por columnas de izquierda a derecha, y dentro de cada una por altura
        grupo.sort(key=lambda c: (round(c.x0 / 100), c.y0))
        for n, c in enumerate(grupo, 1):
            fuera.append((f"marca_{prefijo}_{n}", c))
    return fuera


def huecos_sueltos(pagina):
    """Lo que hay que rellenar en la pagina 2 y no es una casilla.

    El "Otros:______" de la documentacion y el "En ......, a ... de ... de ..."
    de la firma. Los puntos suspensivos del impreso marcan donde va cada cosa,
    asi que los huecos se sacan de ahi mismo.
    """
    fuera = []
    for texto, caja in trozos_de(pagina):
        plano_txt = texto.strip()
        if plano_txt.lower().startswith("otros:"):
            x = caja.x0 + caja.width * (len("Otros:") / max(len(texto), 1))
            fuera.append(("otros", pymupdf.Rect(x, caja.y0, caja.x1, caja.y1)))
            continue
        if not plano_txt.lower().startswith("en "):
            continue
        # los grupos de puntos: lugar, dia, mes y ano, por ese orden
        paso = caja.width / max(len(texto), 1)
        nombres, ini = ["lugar_firma", "dia", "mes", "anio"], None
        tramos = []
        for k, c in enumerate(texto + " "):
            if c in PUNTOS:
                if ini is None:
                    ini = k
            elif ini is not None:
                if k - ini >= 3:
                    tramos.append((ini, k))
                ini = None
        for (a, b), nombre in zip(tramos, nombres):
            fuera.append((nombre, pymupdf.Rect(caja.x0 + paso * a, caja.y0,
                                               caja.x0 + paso * b, caja.y1)))
    return fuera


def nombre_unico(usados, propuesto):
    nombre, n = propuesto, 2
    while nombre in usados:
        nombre = f"{propuesto}_{n}"
        n += 1
    usados.add(nombre)
    return nombre


def main():
    if not os.path.exists(ORIGEN):
        print(f"\n  No encuentro {os.path.relpath(ORIGEN, RAIZ)}.")
        print("  Bajalo de la sede de la Comunidad de Madrid y dejalo ahi.\n")
        return 1

    doc = pymupdf.open(ORIGEN)
    usados = set()
    textos = casillas = 0

    # --- pagina 1: los apartados, que son tablas
    pagina = doc[0]
    tablas = pagina.find_tables().tables
    for i, tabla in enumerate(tablas):
        if i >= len(APARTADOS):
            break
        for nombre, caja in campos_de_la_tabla(tabla, APARTADOS[i]):
            w = pymupdf.Widget()
            w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
            w.field_name = nombre_unico(usados, nombre)
            w.rect = caja
            w.text_fontsize = TAM_LETRA
            w.field_value = ""
            pagina.add_widget(w)
            textos += 1

    # --- pagina 2: los cuadraditos de marcar, el "Otros:" y la linea de la firma
    pagina = doc[1]
    for nombre, caja in casillas_de_la_pagina(pagina):
        w = pymupdf.Widget()
        w.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
        w.field_name = nombre_unico(usados, nombre)
        w.rect = caja
        w.field_value = False
        pagina.add_widget(w)
        casillas += 1
    for nombre, caja in huecos_sueltos(pagina):
        w = pymupdf.Widget()
        w.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        w.field_name = nombre_unico(usados, nombre)
        w.rect = caja
        w.text_fontsize = TAM_LETRA
        w.field_value = ""
        pagina.add_widget(w)
        textos += 1

    doc.save(DESTINO, garbage=4, deflate=True)
    doc.close()

    print(f"\n  impreso oficial : {os.path.relpath(ORIGEN, RAIZ)}")
    print(f"  huecos de texto : {textos}")
    print(f"  casillas        : {casillas}")
    print(f"  plantilla -> {os.path.relpath(DESTINO, RAIZ)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
