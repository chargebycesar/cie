# -*- coding: utf-8 -*-
"""
Pone un sello de version a los ficheros de la aplicacion.

El navegador guarda en cache los .js y los .json, y GitHub Pages le dice que
puede quedarselos un rato. Sin esto, despues de publicar un arreglo el usuario
sigue usando la version de antes sin enterarse -paso el 10 sept 2026: un anexo
salio sin el NIF ni el domicilio porque el motor era el viejo-.

Se le pega ?v=<sello> a la etiqueta <script>, a los import de unos modulos a
otros y a los ficheros de datos que se piden con fetch. El sello es la fecha y
la hora, asi que cada publicacion trae uno nuevo y el navegador se lo baja.

Es idempotente: si ya hay sello, lo cambia. Lo llama publicar.py antes de subir.

    python herramientas/sellar_version.py [sello]
"""

import io
import os
import re
import sys
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(RAIZ, "docs")

# Lo que hay que sellar: los modulos que se importan entre si, el script del
# HTML y los ficheros que la aplicacion se baja por su cuenta.
PATRONES = [
    # import ... from "./motor.js"
    re.compile(r'(from\s+"\./[\w.-]+\.js)(\?v=[\w.-]+)?(")'),
    # <script type="module" src="app.js">
    re.compile(r'(src="[\w.-]+\.js)(\?v=[\w.-]+)?(")'),
    # <link rel="stylesheet" href="estilos.css">, que tambien se cachea: sin
    # esto un cambio de estilo no se ve hasta que el navegador se digna.
    re.compile(r'(href="[\w.-]+\.css)(\?v=[\w.-]+)?(")'),
    # fetch("config-inicial.json") y fetch("plantillas/campos.json")
    re.compile(r'(fetch\("[\w./-]+\.json)(\?v=[\w.-]+)?(")'),
]


def sellar(ruta, sello):
    texto = io.open(ruta, encoding="utf-8").read()
    nuevo = texto
    for patron in PATRONES:
        nuevo = patron.sub(lambda m: f"{m.group(1)}?v={sello}{m.group(3)}", nuevo)
    if nuevo == texto:
        return 0
    io.open(ruta, "w", encoding="utf-8").write(nuevo)
    return sum(len(p.findall(nuevo)) for p in PATRONES)


def main():
    sello = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d%H%M")
    total = 0
    for nombre in sorted(os.listdir(DOCS)):
        if not nombre.endswith((".js", ".html")):
            continue
        n = sellar(os.path.join(DOCS, nombre), sello)
        if n:
            print(f"  {nombre:<16} {n} referencias")
        total += n
    print(f"\n  sello {sello} · {total} referencias" if total
          else f"\n  sello {sello} · nada que cambiar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
