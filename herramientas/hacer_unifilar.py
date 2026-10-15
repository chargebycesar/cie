# -*- coding: utf-8 -*-
"""
Hace sitio en el esquema unifilar para las protecciones que se anadan.

El esquema traia el magnetotermico general y el diferencial pegados al
recuadro del punto de recarga: entre uno y otro quedaban 36 puntos, lo justo
para un aparato mas y pegado. Pero un cuadro de verdad lleva a menudo el DPN de
la linea del cargador, y a veces ademas un DPN con su base schuko.

Encima de la linea de la derivacion individual habia 150 puntos sin usar. Esto
sube ese bloque -la linea, el general y el diferencial- y alarga la vertical,
con lo que debajo del diferencial quedan 96 puntos: caben dos aparatos mas con
su separacion.

No se redibuja nada: se calca el bloque del propio esquema y se estampa mas
arriba, asi que el trazo es exactamente el mismo.

    python herramientas/hacer_unifilar.py

Lee fuente/UNIFILAR-original.pdf y escribe docs/plantillas/UNIFILAR.pdf.
"""

import os
import sys

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEN = os.path.join(RAIZ, "fuente", "UNIFILAR-original.pdf")
DESTINO = os.path.join(RAIZ, "docs", "plantillas", "UNIFILAR.pdf")

# El bloque que sube: la linea de la derivacion individual, el general con
# sobretensiones y el diferencial. Los margenes del marco -las letras de fila y
# sus marcas- quedan fuera a proposito.
BLOQUE = pymupdf.Rect(128, 205, 472, 318)
SUBIDA = 60.0

# La vertical del cuadro y donde empieza el recuadro del punto de recarga.
BUS_X = 420.7
BUS_HASTA = 345.0
GROSOR = 0.9


def main():
    if not os.path.exists(ORIGEN):
        print(f"\n  No encuentro {os.path.relpath(ORIGEN, RAIZ)}.\n")
        return 1

    doc = pymupdf.open(ORIGEN)
    fuente = pymupdf.open(ORIGEN)        # el mismo papel, para calcar de el
    pagina = doc[0]

    # 1 - se tapa el bloque donde estaba
    pagina.draw_rect(BLOQUE, color=None, fill=(1, 1, 1), width=0)

    # 2 - y se vuelve a estampar mas arriba, del mismo tamano
    destino = pymupdf.Rect(BLOQUE.x0, BLOQUE.y0 - SUBIDA,
                           BLOQUE.x1, BLOQUE.y1 - SUBIDA)
    pagina.show_pdf_page(destino, fuente, 0, clip=BLOQUE)

    # 3 - la vertical, desde donde acaba ahora el diferencial hasta el recuadro
    abajo_del_diferencial = 309.0 - SUBIDA
    pagina.draw_line((BUS_X, abajo_del_diferencial), (BUS_X, BUS_HASTA),
                     color=(0, 0, 0), width=GROSOR)

    # 4 - los rotulos del general y del diferencial suben con su dibujo
    movidos = 0
    for w in pagina.widgets():
        if w.field_name in ("IMG1", "IDG1", "IDG1S", "IDG1C", "DERIVACION INDIVIDUAL"):
            r = w.rect
            w.rect = pymupdf.Rect(r.x0, r.y0 - SUBIDA, r.x1, r.y1 - SUBIDA)
            w.update()
            movidos += 1

    doc.save(DESTINO, garbage=4, deflate=True)
    doc.close()
    fuente.close()

    libre = BUS_HASTA - abajo_del_diferencial
    print(f"\n  bloque subido      : {SUBIDA:.0f} pt")
    print(f"  rotulos movidos    : {movidos}")
    print(f"  sitio bajo el dif. : {libre:.0f} pt (antes 36)")
    print(f"  plantilla -> {os.path.relpath(DESTINO, RAIZ)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
