# -*- coding: utf-8 -*-
"""
Hace la lista de municipios de la Comunidad de Madrid con sus codigos postales.

Se ejecuta UNA VEZ, aqui, en el ordenador del desarrollador. La aplicacion no
pregunta nada a nadie: se lleva la lista dentro y la usa sin red, que es lo que
manda el principio II de la constitucion del proyecto -los datos del cliente no
salen del navegador, y la unica llamada fuera es el callejero del IGN, solo con
boton-.

Con esta lista:
  - el desplegable de Localidad sale lleno desde el primer dia, sin haber
    escrito nada antes;
  - en los municipios que tienen un solo codigo postal, el codigo se pone solo.

    python herramientas/hacer_municipios.py

Escribe docs/datos/municipios-madrid.json.

Fuente: Callejero del Censo Electoral del INE, publicado en
https://github.com/inigoflores/ds-codigos-postales-ine-es
Son datos publicos de referencia -nombres de pueblo y codigos postales-, sin
relacion con ninguna persona.
"""

import io
import json
import os
import re
import sys
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "docs", "datos", "municipios-madrid.json")

ORIGEN = ("https://raw.githubusercontent.com/inigoflores/"
          "ds-codigos-postales-ine-es/master/data/codigos_postales_municipios.csv")

# El codigo INE de la provincia de Madrid y el rango de sus codigos postales.
PROVINCIA = "28"
# El 28000 no es de nadie: en el callejero sale como cajon de sastre de Madrid.
NO_VALE = {"28000"}


def natural(nombre):
    """"Alamo, El" se lee "El Alamo", que es como lo escribe la gente.

    El callejero guarda el articulo detras para poder ordenar alfabeticamente.
    En un impreso y en un desplegable estorba.
    """
    if "," in nombre:
        cuerpo, articulo = nombre.rsplit(",", 1)
        articulo = articulo.strip()
        if articulo and len(articulo) <= 3:
            return f"{articulo} {cuerpo.strip()}"
    return nombre.strip()


def main():
    print(f"\n  Bajando {ORIGEN.split('/')[-1]}...")
    try:
        with urllib.request.urlopen(ORIGEN, timeout=60) as r:
            crudo = r.read().decode("utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"  No he podido bajarlo ({e}).\n")
        return 1

    municipios = {}
    for linea in crudo.splitlines()[1:]:
        # El nombre puede llevar comas y viene entre comillas
        m = re.match(r'^(\d{5}),(\d{5}),(?:"(.*)"|(.*))$', linea.strip())
        if not m:
            continue
        cp, ine, nombre = m.group(1), m.group(2), m.group(3) or m.group(4)
        if not ine.startswith(PROVINCIA) or cp in NO_VALE:
            continue
        nombre = natural(nombre).upper()
        municipios.setdefault(nombre, set()).add(cp)

    if len(municipios) < 150:
        print(f"  Solo han salido {len(municipios)} municipios y Madrid tiene 179."
              "  Algo ha cambiado en el origen: revisalo antes de usarlo.\n")
        return 1

    lista = {n: sorted(cps) for n, cps in sorted(municipios.items())}
    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    io.open(DESTINO, "w", encoding="utf-8", newline="").write(
        json.dumps(lista, ensure_ascii=False, indent=0, sort_keys=True) + "\n")

    unicos = sum(1 for cps in lista.values() if len(cps) == 1)
    tamano = os.path.getsize(DESTINO) / 1024
    print(f"  municipios            : {len(lista)}")
    print(f"  con un solo codigo    : {unicos}")
    print(f"  con varios            : {len(lista) - unicos}")
    print(f"  fichero               : {tamano:.1f} KB")
    print(f"  escrito en {os.path.relpath(DESTINO, RAIZ)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
