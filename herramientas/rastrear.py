# -*- coding: utf-8 -*-
"""
Busca dentro de un PDF datos personales que no deberian estar ahi.

Mira tambien lo que no se ve al abrir el documento: el dibujo viejo de los
campos, los recuadros que quedaron sueltos de otro trabajo y el sello de una
firma electronica anterior.

No lleva dentro ningun dato de nadie: reconoce los identificadores por su forma
(DNI, NIE, CIF, CUPS, correos, moviles) y descuenta los que si tocan, que son
los del expediente que se esta generando y los de la empresa.

    python herramientas/rastrear.py docs/plantillas/*.pdf
    python herramientas/rastrear.py salida/*/*.pdf

Devuelve 1 si encuentra algo, para poder encadenarlo con otras comprobaciones.
"""

import contextlib
import io
import os
import re
import sys

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Como se reconoce cada cosa. Con limites de palabra, para no cazar trozos
# sueltos de los numeros que van por todo el PDF.
FORMAS = {
    "correo": r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b",
    "DNI/NIE": r"\b[XYZ]?\d{8}[A-Za-z]\b",
    "CIF": r"\b[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]\b",
    "CUPS": r"\bES\d{16}[A-Z]{2}\b",
    "movil": r"\b[67]\d{8}\b",
}

# Lo que trae el propio impreso oficial y encaja por casualidad: el correo de
# proteccion de datos de la Comunidad, el de la autoridad de certificacion que
# firmo el PDF y los ejemplos impresos en las casillas.
RUIDO = {
    "PROTECCIONDATOSMAMBIENTE@MADRID.ORG",
    "CPS-REQUESTS@VERISIGN.COM",
    "ES0000000000000000AA",
    "88888888Y",
}

CADENA = re.compile(r"\(((?:[^()\\]|\\.)*)\)")


def legible(cadena):
    """Descarta lo que sale de un flujo binario y solo parece texto.

    Dentro de las fuentes y de las imagenes hay bytes que, leidos como si
    fueran letras, dan cosas con pinta de movil o de correo. Una cadena de
    verdad es casi toda de caracteres imprimibles.
    """
    if not cadena:
        return False
    buenos = sum(1 for c in cadena if c.isprintable() and ord(c) < 384)
    return buenos >= len(cadena) * 0.9


def texto_completo(ruta):
    """Todas las cadenas de texto del PDF, se vean o no.

    Solo cadenas de verdad: las que van entre parentesis en los objetos y en
    los flujos de dibujo. Leer el fichero como si fuera texto plano no sirve,
    porque los bytes comprimidos dan por casualidad cosas con pinta de DNI o de
    movil cada dos por tres.
    """
    partes = []
    with contextlib.redirect_stderr(io.StringIO()):
        doc = pymupdf.open(ruta)
        for pagina in doc:
            partes.append(pagina.get_text())
        for x in range(1, doc.xref_length()):
            try:
                partes.extend(c for c in
                              CADENA.findall(doc.xref_object(x, compressed=False))
                              if legible(c))
            except Exception:
                pass
            if not doc.xref_is_stream(x):
                continue
            # Las imagenes escaneadas y las fuentes incrustadas, fuera: leidas
            # como si fueran letras dan cosas con pinta de movil o de correo.
            cabecera = ""
            try:
                cabecera = doc.xref_object(x, compressed=False)
            except Exception:
                pass
            if re.search(r"/(Image|FontFile\d?|Type1C|TrueType|CIDFontType\w*)",
                         cabecera):
                continue
            try:
                cuerpo = doc.xref_stream(x).decode("latin-1", "replace")
            except Exception:
                continue
            # Solo si parece un flujo de dibujo
            if "Tj" in cuerpo or "TJ" in cuerpo:
                partes.extend(c for c in CADENA.findall(cuerpo) if legible(c))
        doc.close()
    return "\n".join(partes)


# Dominios y nombres que solo se usan para poner ejemplos
DOMINIOS_DE_MENTIRA = {"ejemplo.es", "ejemplo.com", "example.com", "example.org",
                       "dominio.com", "midominio.com", "correo.com"}


def parece_inventado(valor):
    """Si es un ejemplo de los que se ponen en las casillas, no es de nadie.

    Un aviso que salta con cada 12345678Z acaba ignorandose, y entonces ya no
    sirve para lo que esta: para cazar el DNI de verdad de alguien.
    """
    v = valor.strip()
    if "@" in v:
        usuario, _, dominio = v.lower().partition("@")
        return (dominio in DOMINIOS_DE_MENTIRA
                or usuario.startswith("tu-") or usuario in ("prueba", "ejemplo"))
    digitos = "".join(c for c in v if c.isdigit())
    if not digitos:
        return False
    if len(set(digitos)) == 1:
        return True                                   # 00000000, 88888888
    if digitos.count("0") >= len(digitos) * 0.7:
        return True                                   # ES0031000000000000AB
    sube = "0123456789012345678901234567890"
    return digitos in sube or digitos[::-1] in sube   # 12345678, 987654321


def permitidos():
    """Los identificadores que si pueden salir: los tuyos y los del cliente."""
    fuera = set(RUIDO)
    for nombre in ("config.json", "prueba.json"):
        ruta = os.path.join(RAIZ, nombre)
        if not os.path.exists(ruta):
            continue
        crudo = io.open(ruta, encoding="utf-8").read()
        for forma in FORMAS.values():
            fuera.update(m.upper() for m in re.findall(forma, crudo))
    return fuera


def identificadores(texto, salvo=None):
    """Lo que hay en un texto y parece de una persona de verdad."""
    salvo = permitidos() if salvo is None else salvo
    fuera = []
    for etiqueta, forma in FORMAS.items():
        for m in sorted(set(re.findall(forma, texto))):
            if m.upper() in salvo or parece_inventado(m):
                continue
            fuera.append(f"{etiqueta} {m}")
    return fuera


def restos(ruta, salvo=None):
    return identificadores(texto_completo(ruta), salvo)


def main():
    rutas = [r for r in sys.argv[1:] if r.lower().endswith(".pdf")]
    if not rutas:
        print(__doc__)
        return 2
    salvo = permitidos()
    malos = 0
    for r in sorted(rutas):
        h = restos(r, salvo)
        malos += bool(h)
        print(f"  {'SUCIO ' if h else 'limpio'} {os.path.basename(r)[:46]:<48} "
              f"{'; '.join(h[:4])}")
    print()
    if malos:
        print(f"  {malos} de {len(rutas)} llevan datos que no les tocan.")
        print("  Si vienen de un trabajo anterior:"
              "  python herramientas/limpiar_plantillas.py")
        return 1
    print(f"  Los {len(rutas)} limpios: ningun dato ajeno dentro.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
