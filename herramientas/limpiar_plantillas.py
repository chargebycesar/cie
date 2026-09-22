# -*- coding: utf-8 -*-
"""
Deja los impresos oficiales realmente en blanco.

Los PDF de partida no eran impresos vacios: eran expedientes ya rellenados de
otros trabajos. Ademas de los campos que se ven, arrastraban por dentro:

  - campos de formulario que no cuelgan de ninguna pagina, invisibles al abrir
    el documento pero recuperables con cualquier extractor de formularios, con
    nombres, DNI, direcciones y telefonos de terceros;
  - el dibujo (la apariencia) del texto anterior, que sobrevive aunque se
    cambie el valor del campo.

Esto se arregla una sola vez, sobre las plantillas, no en cada generacion:

  1. Se busca que campos cuelgan de verdad de una pagina.
  2. A los demas se les quita valor y dibujo, y se sacan de la lista del
     formulario, para que la recoleccion de basura del guardado los borre.
  3. A los que si cuelgan de una pagina se les vacia el valor, salvo los que
     son del propio impreso (cabeceras, aviso legal, valores fijos), que se
     reconocen porque el motor no los escribe nunca.
  4. Las casillas se ponen en Off, pero conservando su dibujo: ahi vive el
     estado "Si" y sin el no se pueden marcar.

    python herramientas/limpiar_plantillas.py

Deja copia de lo anterior en fuente/respaldo-plantillas/.
"""

import contextlib
import io
import json
import os
import re
import shutil
import sys

import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "docs", "plantillas")
RESPALDO = os.path.join(RAIZ, "fuente", "respaldo-plantillas")
sys.path.insert(0, RAIZ)


def clave(doc, xref, k):
    """Lee una clave del objeto. Devuelve (None, None) si no esta.

    Ojo: xref_get_key no devuelve None cuando falta la clave, devuelve la
    cadena "null". Si no se traduce aqui, cualquier comprobacion del estilo
    "esta la clave?" sale que si siempre.
    """
    try:
        tipo, valor = doc.xref_get_key(xref, k)
    except Exception:
        return (None, None)
    if tipo in (None, "null"):
        return (None, None)
    return (tipo, valor)


def poner(doc, xref, k, v):
    """Escribe una clave sin protestar: no todo objeto es un diccionario."""
    try:
        doc.xref_set_key(xref, k, v)
        return True
    except Exception:
        return False


# Recuadros que el impreso metio en un campo que ya existia, y que en realidad
# son otra cosa. Como comparten nombre, escribir en uno escribe en el otro.
# Aqui se les da nombre propio.
#
# En el anexo del garaje, el "En ______, a __ de ____" de la firma cuelga del
# mismo campo que la provincia del garaje, asi que salia MADRID donde tiene que
# ir la localidad del cliente.
SEPARAR = {
    "ANEXO_GARAJE.pdf": [
        {"campo": "provincia garaje", "desde_y": 600, "nuevo": "lugar firma"},
    ],
}


def separar_campo(doc, campo, desde_y, nuevo):
    """Saca de un campo el recuadro que esta por debajo de `desde_y` y le pone
    nombre propio, para poder escribir en el algo distinto."""
    for pagina in doc:
        for w in pagina.widgets():
            if w.field_name != campo or w.rect.y0 < desde_y:
                continue
            # Se despega del padre y pasa a ser un campo de texto con su nombre
            tipo, valor = clave(doc, w.xref, "Parent")
            if tipo == "xref":
                padre = int(valor.split()[0])
                _, kids = clave(doc, padre, "Kids")
                quedan = [x for x in re.findall(r"(\d+)\s+\d+\s+R", kids or "")
                          if int(x) != w.xref]
                poner(doc, padre, "Kids",
                      "[ " + " ".join(f"{x} 0 R" for x in quedan) + " ]")
                # Se hereda lo que hacia falta antes de cortar el cordon
                for k in ("FT", "DA", "Ff"):
                    t, v = clave(doc, padre, k)
                    if t is not None and clave(doc, w.xref, k)[0] is None:
                        poner(doc, w.xref, k, v)
                poner(doc, w.xref, "Parent", "null")
            poner(doc, w.xref, "T", pymupdf.get_pdf_str(nuevo))
            if clave(doc, w.xref, "FT")[0] is None:
                poner(doc, w.xref, "FT", "/Tx")
            return w.xref
    return None


def enderezar_recuadros(doc):
    """Pone del derecho los recuadros que el impreso trae del reves.

    Un /Rect con la y de abajo mayor que la de arriba es valido segun la norma
    -son dos esquinas, en cualquier orden- pero **hay visores que no dibujan
    ese campo**: sale en blanco aunque tenga su texto dentro. En el anexo del
    garaje son cuatro, y son justo los que al usuario le salian vacios: el NIF,
    su domicilio, el domicilio de la comunidad y el lugar de la firma. MuPDF
    los pone del derecho al leerlos y por eso aqui se veian bien, que fue lo
    que despisto.
    """
    enderezados = 0
    for pagina in doc:
        for w in pagina.widgets():
            tipo, valor = clave(doc, w.xref, "Rect")
            if tipo is None:
                continue
            n = [float(x) for x in re.findall(r"-?[\d.]+", valor or "")]
            if len(n) != 4 or (n[2] >= n[0] and n[3] >= n[1]):
                continue
            x0, x1 = sorted((n[0], n[2]))
            y0, y1 = sorted((n[1], n[3]))
            poner(doc, w.xref, "Rect",
                  "[ %.4f %.4f %.4f %.4f ]" % (x0, y0, x1, y1))
            enderezados += 1
    return enderezados


def lineas_horizontales(pagina):
    """Las rayas horizontales dibujadas en la pagina, con su tramo de x."""
    ys = []
    for dib in pagina.get_drawings():
        for it in dib["items"]:
            if it[0] == "l" and abs(it[1].y - it[2].y) < 0.6:
                ys.append((min(it[1].x, it[2].x), max(it[1].x, it[2].x), it[1].y))
            elif it[0] == "re":
                r = it[1]
                if r.height < 1.5:      # una raya dibujada como rectangulo fino
                    ys.append((r.x0, r.x1, (r.y0 + r.y1) / 2))
                else:
                    ys.append((r.x0, r.x1, r.y0))
                    ys.append((r.x0, r.x1, r.y1))
    return ys


def centrar_en_su_casilla(doc, pagina):
    """Sube los campos que el impreso dejo descolgados dentro de su casilla.

    En el anexo IVE, los tres valores de la derecha -potencia maxima, esquema y
    numero de puntos- estan puestos pegados al fondo de su casilla, y el de
    numero de puntos doce puntos por debajo del centro, asi que el dato sale
    abajo con un hueco grande encima. Los rotulos de esas casillas estan en la
    columna de al lado, no dentro, asi que el sitio del dato es el centro.

    Ojo con generalizarlo: en el esquema unifilar los campos tambien van bajos,
    pero ahi es a proposito, porque el rotulo esta dentro de la casilla, arriba.
    Por eso esto se aplica solo al impreso donde hace falta.
    """
    movidos = 0
    ys = lineas_horizontales(pagina)
    for w in pagina.widgets():
        r = w.rect
        cx = (r.x0 + r.x1) / 2
        arriba = [y for x0, x1, y in ys if x0 - 2 <= cx <= x1 + 2 and y <= r.y0 + 1]
        abajo = [y for x0, x1, y in ys if x0 - 2 <= cx <= x1 + 2 and y >= r.y1 - 1]
        if not arriba or not abajo:
            continue
        alta, baja = max(arriba), min(abajo)
        if not (15 <= baja - alta <= 45):
            continue
        desvio = (r.y0 + r.y1) / 2 - (alta + baja) / 2
        if abs(desvio) <= 4:
            continue
        w.rect = pymupdf.Rect(r.x0, r.y0 - desvio, r.x1, r.y1 - desvio)
        w.update()
        movidos += 1
    return movidos


def vaciar_dibujo(doc, xref):
    """Borra el texto dibujado de un campo dejando el objeto en su sitio.

    No vale con quitar la clave /AP: PyMuPDF deja escrito un `null` literal y
    a partir de ahi MuPDF ya no sabe redibujar el campo, asi que el impreso se
    queda mudo. Lo que si funciona es dejar la apariencia en blanco.
    """
    tipo, valor = clave(doc, xref, "AP/N")
    if tipo != "xref":
        return False
    try:
        doc.update_stream(int(valor.split()[0]), b"")
        return True
    except Exception:
        return False


def vaciar_firma(doc, xref, visto=None):
    """Borra el sello de una firma electronica anterior.

    El campo de firma puede estar vacio y aun asi conservar su dibujo, que dice
    quien firmo, cuando y con que certificado. El dibujo se monta con formularios
    XObject encadenados, asi que hay que bajar por todos.
    """
    visto = visto or set()
    if xref in visto:
        return 0
    visto.add(xref)
    n = 0
    if doc.xref_is_stream(xref):
        try:
            doc.update_stream(xref, b"")
            n += 1
        except Exception:
            pass
    for camino in ("AP/N", "Resources/XObject"):
        tipo, valor = clave(doc, xref, camino)
        if tipo == "xref":
            n += vaciar_firma(doc, int(valor.split()[0]), visto)
        elif tipo == "dict":
            for x in re.findall(r"(\d+)\s+\d+\s+R", valor or ""):
                n += vaciar_firma(doc, int(x), visto)
    return n


def texto_de(valor):
    v = (valor or "").strip()
    if v.startswith("(") and v.endswith(")"):
        v = v[1:-1]
    return v


def raiz_del_campo(doc, xref):
    """Sube por la cadena de padres hasta el campo de primer nivel."""
    visto = set()
    while xref not in visto:
        visto.add(xref)
        tipo, valor = clave(doc, xref, "Parent")
        if tipo != "xref":
            return xref
        xref = int(valor.split()[0])
    return xref


def cadena_hasta_pagina(doc, xref):
    """Todos los xref desde un widget hasta su campo raiz, ambos incluidos."""
    cadena, visto = [], set()
    while xref not in visto:
        visto.add(xref)
        cadena.append(xref)
        tipo, valor = clave(doc, xref, "Parent")
        if tipo != "xref":
            break
        xref = int(valor.split()[0])
    return cadena


def limpiar(archivo, escritos):
    ruta = os.path.join(PLANTILLAS, archivo)
    os.makedirs(RESPALDO, exist_ok=True)
    resp = os.path.join(RESPALDO, archivo)
    if not os.path.exists(resp):
        shutil.copy(ruta, resp)

    with contextlib.redirect_stderr(io.StringIO()):
        doc = pymupdf.open(ruta)

        # 1) Recuadros que comparten campo con otro y no deberian.
        #    Va lo primero: al separarlo pasa a ser un campo mas, y los
        #    pasos de despues cuentan los campos que hay
        separados = 0
        for aparte in SEPARAR.get(archivo, []):
            if separar_campo(doc, aparte["campo"], aparte["desde_y"],
                             aparte["nuevo"]):
                separados += 1

        # 2) Recuadros del reves, que algunos visores no dibujan
        enderezados = enderezar_recuadros(doc)

        # 3) Que campos cuelgan de una pagina, y cuales son casillas
        enganchados, raices, orden, casillas = set(), set(), [], set()
        for pagina in doc:
            for w in pagina.widgets():
                enganchados.update(cadena_hasta_pagina(doc, w.xref))
                r = raiz_del_campo(doc, w.xref)
                if r not in raices:
                    raices.add(r)
                    orden.append(r)
                if w.field_type in (pymupdf.PDF_WIDGET_TYPE_CHECKBOX,
                                    pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON):
                    casillas.update(cadena_hasta_pagina(doc, w.xref))

        # 4) Apariencias mal formadas. En el MTD hay tres campos de la
        #    cabecera oficial ("Direccion General de", "Etiqueta de Registro",
        #    "Comunidad de Madrid") cuyo dibujo no declara /Type /XObject
        #    /Subtype /Form. Los visores lo perdonan mientras siga siendo un
        #    campo de formulario, pero en cuanto se aplana el documento ese
        #    dibujo pasa al contenido de la pagina y ya no vale: desaparece.
        #    Se completa aqui, que es un arreglo del impreso, no del relleno.
        remendadas = 0
        for pagina in doc:
            for w in pagina.widgets():
                tipo, valor = clave(doc, w.xref, "AP/N")
                if tipo != "xref":
                    continue
                x = int(valor.split()[0])
                objeto = ""
                try:
                    objeto = doc.xref_object(x, compressed=False)
                except Exception:
                    continue
                if "/Subtype" in objeto:
                    continue
                poner(doc, x, "Type", "/XObject")
                poner(doc, x, "Subtype", "/Form")
                remendadas += 1

        # 5) Campos del impreso que tienen que tapar lo que hay debajo.
        #     En la ultima pagina del MTD, el impreso lleva dibujado el aviso de
        #     proteccion de datos antiguo y encima un campo con el nuevo. El
        #     campo no tapa nada -su dibujo solo traza el recuadro y escribe-,
        #     asi que mientras es un formulario el visor lo disimula, pero al
        #     aplanar salen los dos textos uno encima del otro. Y el de abajo no
        #     se puede borrar: no es texto, son curvas, como el resto de los
        #     rotulos del MTD.
        #
        #     Se reconocen porque el propio impreso les pone color de borde
        #     (/MK /BC): son recuadros que van solos, no huecos para escribir.
        #     A esos se les pinta el fondo blanco delante de su dibujo.
        tapadores = 0
        for pagina in doc:
            for w in pagina.widgets():
                if not (w.field_value or "").strip():
                    continue
                _, mk = clave(doc, w.xref, "MK")
                if not mk or "/BC" not in mk or "/BG" in mk:
                    continue
                tipo, valor = clave(doc, w.xref, "AP/N")
                if tipo != "xref":
                    continue
                x = int(valor.split()[0])
                try:
                    cuerpo = doc.xref_stream(x)
                except Exception:
                    continue
                if cuerpo.lstrip().startswith(b"1 1 1 rg"):
                    continue                    # ya lo tiene
                ancho = w.rect.width
                alto = w.rect.height
                fondo = ("1 1 1 rg 0 0 %.2f %.2f re f" % (ancho, alto)
                         + chr(10)).encode("latin-1")
                try:
                    doc.update_stream(x, fondo + cuerpo)
                    poner(doc, w.xref, "MK/BG", "[ 1 1 1 ]")
                    tapadores += 1
                except Exception:
                    pass

        # 6) Campos descolgados dentro de su casilla (solo el anexo IVE)
        descolgados = 0
        if archivo == "ANEXO_IVE.pdf":
            for pagina in doc:
                descolgados += centrar_en_su_casilla(doc, pagina)

        # 7) Anotaciones sobrantes pegadas a la pagina. Son los recuadros del
        #     trabajo anterior: ya no son campos de formulario (nadie los
        #     nombra), pero siguen en la lista de anotaciones de la pagina y
        #     por eso siguen dibujando su texto. Vaciar el campo no las quita:
        #     hay que sacarlas de /Annots. Se van solo las que son /Widget y
        #     no aparecen como campo; los enlaces y demas se quedan.
        sobrantes = 0
        for pagina in doc:
            suyos = {w.xref for w in pagina.widgets()}
            tipo, valor = clave(doc, pagina.xref, "Annots")
            if tipo != "array":
                continue
            quedan = []
            for trozo in re.findall(r"(\d+)\s+\d+\s+R", valor):
                x = int(trozo)
                _, sub = clave(doc, x, "Subtype")
                if sub == "/Widget" and x not in suyos:
                    sobrantes += 1
                    continue
                quedan.append(x)
            doc.xref_set_key(pagina.xref, "Annots",
                             "[ " + " ".join(f"{x} 0 R" for x in quedan) + " ]")

        # 8) Las anotaciones que no son campos se quedan -pueden ser parte del
        #     impreso, como el esquema de la segunda pagina del anexo IVE, que
        #     es un sello-, pero sin el rastro de quien las puso.
        firmantes = 0
        for pagina in doc:
            tipo, valor = clave(doc, pagina.xref, "Annots")
            if tipo != "array":
                continue
            for trozo in re.findall(r"(\d+)\s+\d+\s+R", valor):
                x = int(trozo)
                _, sub = clave(doc, x, "Subtype")
                if sub is None or sub == "/Widget":
                    continue
                for k in ("T", "Contents", "NM", "CreationDate", "M"):
                    if clave(doc, x, k)[0] is not None:
                        poner(doc, x, k, "null")
                        firmantes += 1

        # 9) Campos sueltos: los que tienen valor pero no cuelgan de nada.
        #    Un campo se reconoce por tener /FT o nombre /T. Ojo con no
        #    confundirlos con los nodos del arbol de paginas, que tambien
        #    llevan /Kids y /Parent; por eso se descarta todo lo que sea /Page
        #    o /Pages, y no se tocan ni /Kids ni /Parent: basta con dejarlos
        #    fuera de la lista del formulario para que la basura se los lleve.
        sueltos = 0
        for x in range(1, doc.xref_length()):
            if x in enganchados:
                continue
            _, tipo = clave(doc, x, "Type")
            if tipo in ("/Page", "/Pages"):
                continue
            t_ft, _ = clave(doc, x, "FT")
            t_t, _ = clave(doc, x, "T")
            _, sub = clave(doc, x, "Subtype")
            # Las anotaciones que no son campos -un sello, una nota- tambien
            # llevan /T, que ahi es el nombre de quien la puso, no un nombre de
            # campo. Si se cuelan aqui se les borra el dibujo, y en el anexo IVE
            # el esquema de la segunda pagina es justo eso: un sello.
            if sub is not None and sub != "/Widget":
                continue
            es_campo = t_ft is not None or t_t is not None
            # Los recuadros sueltos no llevan ni /FT ni nombre: son solo el
            # dibujo, y ahi es donde queda el texto del trabajo anterior. Hay
            # que vaciarlos aunque no sean campos, porque no basta con dejarlos
            # sin apuntar: la limpieza del guardado no siempre se los lleva.
            if not es_campo and sub != "/Widget":
                continue
            t_v, v = clave(doc, x, "V")
            if t_v == "string" and texto_de(v):
                sueltos += 1
            if es_campo:
                poner(doc, x, "V", "null")
            vaciar_dibujo(doc, x)

        # 10) Campos de pagina que rellena el motor: fuera valor y fuera dibujo.
        #    El valor no siempre esta en el widget: en los impresos con nombres
        #    del tipo topmostSubform[0].Page1[0].Campo[0] vive en un padre y el
        #    widget solo lo hereda, asi que hay que subir la cadena. Pero solo
        #    se toca el valor donde hay nombre de campo (/T): si se le pone /V
        #    al widget suelto, que es solo un dibujo, el impreso deja de
        #    aceptar valores y sale en blanco. El dibujo si se vacia entero.
        vaciados = 0
        for pagina in doc:
            for w in pagina.widgets():
                if w.field_name not in escritos:
                    continue  # es del impreso, no nuestro
                es_casilla = w.xref in casillas
                for x in cadena_hasta_pagina(doc, w.xref):
                    tiene_nombre = clave(doc, x, "T")[0] is not None
                    if es_casilla:
                        # La casilla conserva su dibujo: ahi vive el estado "Si"
                        if tiene_nombre:
                            poner(doc, x, "V", "/Off")
                        poner(doc, x, "AS", "/Off")
                    else:
                        if tiene_nombre:
                            poner(doc, x, "V", "()")
                        vaciar_dibujo(doc, x)
                vaciados += 1

        # 11) Firmas electronicas de trabajos anteriores. El campo esta vacio
        #     pero su sello sigue diciendo quien firmo y cuando.
        firmas = 0
        for x in range(1, doc.xref_length()):
            _, ft = clave(doc, x, "FT")
            if ft == "/Sig":
                firmas += bool(vaciar_firma(doc, x))

        # 12) La lista del formulario, solo con lo que cuelga de una pagina.
        #    Se cambia la lista dentro del AcroForm que ya hay, sin sustituirlo
        #    entero: ahi vive /DR, el catalogo de fuentes del impreso. Si se
        #    pierde, el visor no sabe con que letra escribir y los campos se
        #    quedan mudos aunque tengan valor.
        catalogo = doc.pdf_catalog()
        lista = "[ " + " ".join(f"{x} 0 R" for x in orden) + " ]"
        tipo, valor = clave(doc, catalogo, "AcroForm")
        if tipo == "xref":
            doc.xref_set_key(int(valor.split()[0]), "Fields", lista)
        elif tipo == "dict":
            # Algunos impresos lo llevan escrito dentro del catalogo en vez de
            # apuntar a un objeto aparte
            doc.xref_set_key(catalogo, "AcroForm/Fields", lista)
        else:
            # El impreso no tenia AcroForm utilizable: se hace uno de cero
            nuevo = doc.get_new_xref()
            doc.update_object(nuevo, f"<< /Fields {lista} "
                                     f"/DA (/Helv 0 Tf 0 g) /NeedAppearances true >>")
            doc.xref_set_key(catalogo, "AcroForm", f"{nuevo} 0 R")

        tmp = ruta + ".tmp"
        # garbage=4 borra lo que ya no apunta nadie: ahi se van los restos
        doc.save(tmp, garbage=4, deflate=True, clean=True)
        doc.close()

    antes = os.path.getsize(ruta)
    shutil.move(tmp, ruta)
    print(f"  {archivo:<18} {enderezados} enderezados · {remendadas:>2} apariencias · {tapadores} tapados · "
          f"{descolgados} recolocados · {firmantes} rastros · "
          f"{sobrantes:>3} recuadros · "
          f"{sueltos:>3} sueltos · {vaciados:>3} vaciados · {firmas} firmas · "
          f"{antes/1024:.0f} -> {os.path.getsize(ruta)/1024:.0f} KB")


def main():
    import nucleo
    datos = json.load(io.open(os.path.join(RAIZ, "prueba.json"), encoding="utf-8"))
    cfg = nucleo.cargar_config()
    preset = nucleo.valores_tecnicos(datos, cfg)
    calc = nucleo.calcular(datos, preset, cfg)
    mapas = {
        "MTD.pdf": nucleo.mapa_mtd(datos, cfg, preset, calc),
        "ANEXO_IVE.pdf": nucleo.mapa_anexo_ive(datos, cfg, preset, calc),
        "UNIFILAR.pdf": nucleo.mapa_unifilar(datos, cfg, preset, calc),
        "SOLICITUD.pdf": nucleo.mapa_solicitud(datos, cfg),
        "AUTORIZACION.pdf": nucleo.mapa_autorizacion(datos, cfg),
        "ANEXO_GARAJE.pdf": nucleo.mapa_anexo_garaje(datos, cfg),
    }
    for archivo, (mapa, cas) in mapas.items():
        limpiar(archivo, set(mapa) | set(cas))


if __name__ == "__main__":
    main()
