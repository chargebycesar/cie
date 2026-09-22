# -*- coding: utf-8 -*-
"""
Comprueba que el CIE que genera la aplicacion sigue siendo el impreso oficial.

La EICI rechaza el certificado si le falta algo del formato. Paso una vez: el
"COMPLETADO" de arriba dejo de escribirse -por un malentendido sobre que parte
de ese recuadro va en blanco- y nadie se entero hasta que lo devolvieron. Esto
esta aqui para que no vuelva a pasar en silencio.

Compara contra dos referencias:

  1. El impreso en blanco, `CIE_base.pdf`. Todo lo que pone ahi tiene que
     seguir estando en el certificado generado. Si alguien tapa medio impreso
     al dibujar encima, salta.
  2. Los rotulos que el impreso trae dentro de celdas editables y que la
     aplicacion vuelve a escribir (`valores_originales` del mapa).

  Y ademas mira que esten las tres celdas de formula: el aviso de arriba
  -COMPLETADO o CIE INCOMPLETO-, el identificador del certificado y el
  resultado de comprobar el CUPS.

    python herramientas/formato_cie.py

Devuelve 1 si falta algo, para poder encadenarlo con las demas comprobaciones.
"""

import io
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "docs", "plantillas")
ANCHO = 68

# Lo que se mide es el texto, no los pixeles: el impreso se dibuja igual pero
# cada impresora lo coloca un pelo distinto, y aqui eso no importa.
LARGO_MINIMO = 12


def plano(texto):
    """Sin acentos, sin dobles espacios y en mayusculas."""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().upper()


def texto_de(ruta):
    doc = pymupdf.open(ruta)
    entero = " ".join(p.get_text() for p in doc)
    doc.close()
    return plano(entero)


def trozos_del_impreso(ruta):
    """Cada linea del impreso en blanco que valga la pena comprobar."""
    doc = pymupdf.open(ruta)
    fuera = []
    for pagina in doc:
        for linea in pagina.get_text().split("\n"):
            t = plano(linea)
            if len(t) >= LARGO_MINIMO:
                fuera.append(t)
    doc.close()
    return sorted(set(fuera))


def main():
    sys.path.insert(0, RAIZ)
    import nucleo

    print()
    print("  " + "=" * ANCHO)
    print("  EL CIE SIGUE SIENDO EL IMPRESO OFICIAL?")
    print("  " + "=" * ANCHO)

    ejemplo = os.path.join(RAIZ, "config.ejemplo.json")
    if os.path.exists(ejemplo):
        nucleo.CONFIG = ejemplo
    with io.open(os.path.join(RAIZ, "prueba.ejemplo.json"), encoding="utf-8") as fh:
        datos = json.load(fh)

    salida = tempfile.mkdtemp(prefix="formato-cie-")
    try:
        nucleo.SALIDA = salida
        resultado = nucleo.generar(datos)
        generado = None
        for raiz, _, ficheros in os.walk(salida):
            for f in ficheros:
                if f.upper().startswith("CIE"):
                    generado = os.path.join(raiz, f)
        if not generado:
            print("\n  No se ha generado ningun CIE. Eso ya es un problema.")
            return 1
        dentro = texto_de(generado)

        fallos = []

        # --- 1 · lo que pone el impreso en blanco
        base = os.path.join(PLANTILLAS, "CIE_base.pdf")
        trozos = trozos_del_impreso(base)
        faltan = [t for t in trozos if t not in dentro]
        print(f"\n  Textos del impreso en blanco  : {len(trozos)}")
        print(f"  Que siguen en el certificado  : {len(trozos) - len(faltan)}")
        fallos += [("el impreso", t) for t in faltan]

        # --- 2 · los rotulos que van dentro de celdas editables
        with io.open(os.path.join(PLANTILLAS, "cie_mapa.json"), encoding="utf-8") as fh:
            mapa = json.load(fh)
        # De lo que el impreso trae dentro de las casillas, unos son rotulos
        # -"C.G.P. (esquema):"- y otros son datos del trabajo de quien hizo la
        # hoja, que la aplicacion sustituye por los del expediente. Solo hay que
        # exigir los primeros, y se reconocen porque acaban en dos puntos.
        rotulos = sorted({plano(v) for v in (mapa.get("valores_originales") or {}).values()
                          if len(plano(v)) >= LARGO_MINIMO and plano(v).endswith(":")})
        faltan = [t for t in rotulos if t not in dentro]
        print(f"  Rotulos dentro de las casillas: {len(rotulos)}"
              f"  ({len(rotulos) - len(faltan)} puestos)")
        fallos += [("un rotulo", t) for t in faltan]

        # --- 3 · las tres celdas que salen de una formula
        estado = ""
        for d in resultado["documentos"]:
            if d.get("estado"):
                estado = d["estado"]
        formulas = [
            ("el aviso de arriba", plano(estado)),
            ("el identificador", plano(resultado_identificador(resultado))),
        ]
        print()
        for nombre, valor in formulas:
            bien = bool(valor) and valor in dentro
            print(f"  {nombre:<30} {valor[:28]:<30} {'bien' if bien else 'NO SALE'}")
            if not bien:
                fallos.append((nombre, valor or "(vacio)"))

        # --- veredicto
        print()
        if fallos:
            print(f"  FALTAN {len(fallos)} COSAS. Asi la EICI lo rechaza:")
            for donde, que in fallos[:20]:
                print(f"     {donde:<16} {que[:60]}")
            if len(fallos) > 20:
                print(f"     ... y {len(fallos) - 20} mas")
            print()
            return 1
        print("  El certificado lleva todo lo que lleva el impreso oficial.")
        print()
        return 0
    finally:
        shutil.rmtree(salida, ignore_errors=True)


def resultado_identificador(resultado):
    for d in resultado["documentos"]:
        if d.get("identificador"):
            return d["identificador"]
    return ""


if __name__ == "__main__":
    sys.exit(main())
