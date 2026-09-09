# -*- coding: utf-8 -*-
"""
Comprueba que el motor del navegador y el de Python dan lo mismo.

Genera el mismo expediente por los dos caminos y compara campo por campo. Si
tocas uno de los dos motores y se te olvida el otro, esto lo canta.

    python herramientas/comparar.py [datos.json]

Hace falta haber hecho `npm install` una vez.
"""

import contextlib
import io
import os
import re
import subprocess
import sys

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

IMPRESOS = [
    "MTD - Memoria Tecnica de Diseno.pdf",
    "Anexo IVE - declaracion ITC-BT-52.pdf",
    "Esquema unifilar.pdf",
    "Solicitud de inscripcion BT-1134F1.pdf",
    "Autorizacion del titular al instalador.pdf",
]


def campos(ruta):
    with contextlib.redirect_stderr(io.StringIO()):
        doc = pymupdf.open(ruta)
        return {w.field_name: (w.field_value or "").strip()
                for p in doc for w in p.widgets()}


def palabras(ruta):
    with contextlib.redirect_stderr(io.StringIO()):
        doc = pymupdf.open(ruta)
        return [x for p in doc for x in p.get_text().split()]


def palabras_cie(ruta):
    identificador = re.compile(r"^\d{16}[A-Z]{2}$")
    texto = pymupdf.open(ruta)[0].get_text().split()
    return [x for x in texto if not identificador.match(x)]


def main():
    datos = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "prueba.json")
    if not os.path.exists(datos):
        print(f"No encuentro {datos}")
        return 1

    import json
    import nucleo

    print("Generando con el motor de Python...")
    with open(datos, encoding="utf-8") as fh:
        resultado = nucleo.generar(json.load(fh), aplanar_mtd=False)
    carpeta_py = resultado["carpeta"]

    print("Generando con el motor del navegador...")
    proc = subprocess.run(
        ["node", os.path.join(RAIZ, "herramientas", "comparar.mjs"), RAIZ, datos],
        capture_output=True, cwd=RAIZ)
    if proc.returncode != 0:
        print((proc.stderr or b"").decode("utf-8", "replace")[-600:])
        print("\nSi falla por falta de pdf-lib, ejecuta antes:  npm install")
        return 1
    carpeta_js = os.path.join(RAIZ, "salida", "js")

    print()
    total = 0
    for nombre in IMPRESOS:
        a, b = os.path.join(carpeta_py, nombre), os.path.join(carpeta_js, nombre)
        if not (os.path.exists(a) and os.path.exists(b)):
            print(f"  {nombre[:40]:<42} FALTA en uno de los dos")
            total += 1
            continue
        A, B = campos(a), campos(b)
        if not A and not B:
            # Documento aplanado: ya no tiene formulario, asi que se comparan
            # las palabras que quedan dibujadas en las paginas.
            pa, pb = palabras(a), palabras(b)
            dif = sorted(set(pa) ^ set(pb))
            total += len(dif)
            print(f"  {nombre[:40]:<42} {len(pa):>4} palabras · {len(dif)} diferencias")
            if dif:
                print(f"      {dif[:8]}")
            continue
        dif = [k for k in set(A) | set(B)
               if A.get(k, "").strip() != B.get(k, "").strip()]
        total += len(dif)
        print(f"  {nombre[:40]:<42} {len(A):>4} campos · {len(dif)} diferencias")
        for k in dif[:5]:
            print(f"      {k}: python={A.get(k, '<falta>')[:28]!r} "
                  f"navegador={B.get(k, '<falta>')[:28]!r}")

    pa = palabras_cie(os.path.join(carpeta_py, "CIE.pdf"))
    pb = palabras_cie(os.path.join(carpeta_js, "CIE.pdf"))
    distintas = set(pa) ^ set(pb)
    total += len(distintas)
    print(f"  {'CIE':<42} {len(pa):>4} palabras · {len(distintas)} diferencias")
    if distintas:
        print(f"      {sorted(distintas)[:8]}")

    print()
    if total:
        print(f"  HAY {total} DIFERENCIAS entre los dos motores. Revisa.")
        return 1
    print("  Los dos motores dan exactamente lo mismo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
