# -*- coding: utf-8 -*-
"""
Hace la lista de campos de cada impreso, para poder elegirlos desde la pantalla,
y las imagenes de sus paginas, para poder pinchar cada hueco sobre la hoja.

Los impresos oficiales tienen los campos con nombres que no dicen nada
(`Texto354`, `CampoTexto26[0]`). Aqui se recorre cada uno y se apunta, ademas
del nombre, en que pagina esta, de que tipo es, **donde esta y que tamano tiene**
(para dibujarlo encima de la hoja) y **que pone escrito al lado**.

La etiqueta se busca en el texto de la pagina: primero lo que hay justo a la
izquierda en la misma linea, y si no hay nada, lo que queda encima. En el MTD
muchos rotulos son dibujos y no texto, asi que se queda sin etiqueta; por eso la
pantalla muestra la hoja: ahi se reconoce el hueco por donde esta.

Tambien se marca (`a`) que huecos rellena la aplicacion sola, llamando a los
mismos mapas del motor Python con los datos de ejemplo. Asi la pantalla los
pinta distintos y avisa antes de dejar que se escriba encima.

    python herramientas/indice_campos.py

Escribe docs/plantillas/campos.json y docs/plantillas/img/*.png. Hay que volver
a ejecutarlo si cambia un impreso oficial.
"""

import contextlib
import io
import json
import os
import sys

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "docs", "plantillas")
IMAGENES = os.path.join(PLANTILLAS, "img")
SALIDA = os.path.join(PLANTILLAS, "campos.json")

# Escala de las imagenes: 1,6 veces los 72 ppp del PDF, unos 950 px de ancho.
# Suficiente para leer los rotulos y encontrar el hueco sin que pesen mucho.
ESCALA = 1.6

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

# Que impreso rellena cada mapa del motor (los tipos de nucleo.DOCUMENTOS)
MAPAS = {
    "MTD.pdf": "mtd", "ANEXO_IVE.pdf": "anexo_ive", "UNIFILAR.pdf": "unifilar",
    "SOLICITUD.pdf": "solicitud", "AUTORIZACION.pdf": "autorizacion",
    "ANEXO_GARAJE.pdf": "anexo_garaje",
}


def trozos_de_texto(pagina):
    """Los cachos de texto de la pagina con su sitio."""
    fuera = []
    for bloque in pagina.get_text("dict")["blocks"]:
        for linea in bloque.get("lines", []):
            for tramo in linea.get("spans", []):
                texto = tramo["text"].strip()
                if texto:
                    x0, y0, x1, y1 = tramo["bbox"]
                    fuera.append({"t": texto, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    return fuera


def etiqueta_de(rect, textos):
    """Lo que hay escrito junto al campo: a la izquierda, encima o a la derecha."""
    centro = (rect.y0 + rect.y1) / 2
    izquierda = [t for t in textos
                 if t["x1"] <= rect.x0 + 2
                 and t["y0"] - 3 <= centro <= t["y1"] + 3
                 and rect.x0 - t["x1"] < A_LA_IZQUIERDA]
    if izquierda:
        izquierda.sort(key=lambda t: rect.x0 - t["x1"])
        return izquierda[0]["t"]
    encima = [t for t in textos
              if t["y1"] <= rect.y0 + 2 and rect.y0 - t["y1"] < ENCIMA
              and t["x1"] > rect.x0 - 40 and t["x0"] < rect.x1 + 40]
    if encima:
        encima.sort(key=lambda t: (rect.y0 - t["y1"], abs(t["x0"] - rect.x0)))
        return encima[0]["t"]
    derecha = [t for t in textos
               if t["x0"] >= rect.x1 - 2
               and t["y0"] - 3 <= centro <= t["y1"] + 3
               and t["x0"] - rect.x1 < 60]
    if derecha:
        derecha.sort(key=lambda t: t["x0"] - rect.x1)
        return derecha[0]["t"]
    return ""


def limpiar(etiqueta):
    e = " ".join(etiqueta.split())
    return e.rstrip(":").strip()[:80]


def huecos_que_rellena_la_app():
    """Nombres de campo que el motor escribe solo, por impreso.

    Se usa el motor Python con los datos y la configuracion de ejemplo (nunca los
    reales: aqui solo hacen falta los nombres, no los valores). Si algo falla,
    se sigue sin esta marca: la lista y las imagenes valen igual.
    """
    try:
        sys.path.insert(0, RAIZ)
        import nucleo  # noqa: E402
        with io.open(os.path.join(RAIZ, "prueba.ejemplo.json"), encoding="utf-8") as fh:
            datos = json.load(fh)
        ejemplo = os.path.join(RAIZ, "config.ejemplo.json")
        if os.path.exists(ejemplo):
            nucleo.CONFIG = ejemplo
        cfg = nucleo.cargar_config()
        preset = nucleo.valores_tecnicos(datos, cfg)
        calc = nucleo.calcular(datos, preset, cfg)
        mapas = {
            "mtd": lambda: nucleo.mapa_mtd(datos, cfg, preset, calc),
            "anexo_ive": lambda: nucleo.mapa_anexo_ive(datos, cfg, preset, calc),
            "unifilar": lambda: nucleo.mapa_unifilar(datos, cfg, preset, calc),
            "solicitud": lambda: nucleo.mapa_solicitud(datos, cfg),
            "autorizacion": lambda: nucleo.mapa_autorizacion(datos, cfg),
            "anexo_garaje": lambda: nucleo.mapa_anexo_garaje(datos, cfg),
        }
        fuera = {}
        for archivo, tipo in MAPAS.items():
            mapa, casillas = mapas[tipo]()
            fuera[archivo] = set(mapa) | set(casillas)
        return fuera
    except Exception as e:  # pragma: no cover
        print(f"  (sin marca de 'lo rellena la app': {e})")
        return {}


def transformacion(pagina, pix):
    """Como pasar de las coordenadas de los campos a las de la imagen.

    Algunas paginas vienen giradas (la 4 del MTD es apaisada). Los campos estan
    en las coordenadas sin girar y la imagen se dibuja girada, asi que hay que
    girar los rectangulos igual. Se prueban las dos opciones y se queda con la
    que deja todos los campos dentro de la hoja.
    """
    ancho, alto = pix.width / ESCALA, pix.height / ESCALA
    candidatas = [pymupdf.Matrix(1, 1), pagina.rotation_matrix]
    mejor, mejor_fuera = candidatas[0], None
    for m in candidatas:
        fuera = 0
        for w in pagina.widgets():
            r = w.rect * m
            r.normalize()
            if r.x0 < -1 or r.y0 < -1 or r.x1 > ancho + 1 or r.y1 > alto + 1:
                fuera += 1
        if mejor_fuera is None or fuera < mejor_fuera:
            mejor, mejor_fuera = m, fuera
    return mejor, ancho, alto


def campos_de(ruta, marca_app, base):
    with contextlib.redirect_stderr(io.StringIO()):
        doc = pymupdf.open(ruta)
        fuera, vistos, paginas = [], set(), []
        for pagina in doc:
            pix = pagina.get_pixmap(matrix=pymupdf.Matrix(ESCALA, ESCALA))
            pix.save(os.path.join(IMAGENES, f"{base}-{pagina.number + 1}.png"))
            m, ancho, alto = transformacion(pagina, pix)
            paginas.append([round(ancho, 1), round(alto, 1)])
            textos = trozos_de_texto(pagina)
            for w in pagina.widgets():
                nombre = w.field_name
                if not nombre or nombre in vistos:
                    continue
                vistos.add(nombre)
                r = w.rect * m
                r.normalize()
                campo = {
                    "n": nombre,
                    "p": pagina.number + 1,
                    "t": TIPOS.get(w.field_type, "otro"),
                    "e": limpiar(etiqueta_de(w.rect, textos)),
                    # Donde esta en la hoja, en puntos, ya girado como la imagen
                    "x": round(r.x0, 1),
                    "y": round(r.y0, 1),
                    "w": round(r.width, 1),
                    "h": round(r.height, 1),
                }
                if nombre in marca_app:
                    campo["a"] = 1
                fuera.append(campo)
        doc.close()
    fuera.sort(key=lambda c: (c["p"], c["y"], c["x"]))
    return fuera, paginas


def main():
    os.makedirs(IMAGENES, exist_ok=True)
    marcas = huecos_que_rellena_la_app()
    indice = {"_paginas": {}}
    for archivo in sorted(os.listdir(PLANTILLAS)):
        if not archivo.lower().endswith(".pdf") or archivo == "CIE_base.pdf":
            continue
        base = os.path.splitext(archivo)[0]
        campos, paginas = campos_de(os.path.join(PLANTILLAS, archivo),
                                    marcas.get(archivo, set()), base)
        indice[archivo] = campos
        indice["_paginas"][archivo] = paginas
        con = sum(1 for c in campos if c["e"])
        app = sum(1 for c in campos if c.get("a"))
        print(f"  {archivo:<18} {len(campos):>4} campos · {con} con etiqueta · "
              f"{app} los pone la app · {len(paginas)} pág.")

    with io.open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(indice, fh, ensure_ascii=False, separators=(",", ":"))
    peso_img = sum(os.path.getsize(os.path.join(IMAGENES, f))
                   for f in os.listdir(IMAGENES)) / 1024
    print(f"\n  {os.path.relpath(SALIDA, RAIZ)}: "
          f"{os.path.getsize(SALIDA) / 1024:.0f} KB · imágenes: {peso_img:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
