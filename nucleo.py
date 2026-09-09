# -*- coding: utf-8 -*-
"""
Motor de generacion de boletines IRVE para la Comunidad de Madrid.

Rellena los formularios oficiales a partir de un unico juego de datos de cliente.
Todo se hace con PyMuPDF y sin programas de por medio: los cinco impresos con
formulario se rellenan campo a campo, y el CIE se dibuja sobre el impreso en
blanco (ver cie_pdf.py), con sus tres formulas reescritas en Python.

Queda el camino antiguo, que abre el CIE.xls con LibreOffice (cie_libreoffice.py),
por si hiciera falta: se activa con "cie_con_libreoffice": true en config.json.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import unicodedata
from datetime import date

import pymupdf

import cie_pdf

RAIZ = os.path.dirname(os.path.abspath(__file__))
PLANTILLAS = os.path.join(RAIZ, "docs", "plantillas")
SALIDA = os.path.join(RAIZ, "salida")
CONFIG = os.path.join(RAIZ, "config.json")

MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
         "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]

SOFFICE_CANDIDATOS = [
    r"C:\Program Files\LibreOffice\program\python.exe",
    r"C:\Program Files (x86)\LibreOffice\program\python.exe",
]


# --------------------------------------------------------------------------
# Configuracion
# --------------------------------------------------------------------------

def cargar_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def guardar_config(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def t(v):
    """Devuelve el valor como texto limpio, nunca None."""
    if v is None:
        return ""
    return str(v).strip()


def coma(v, decimales=2):
    """Numero con coma decimal, como espera la administracion espanola."""
    if v in (None, ""):
        return ""
    try:
        s = f"{float(v):.{decimales}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s.replace(".", ",")
    except (TypeError, ValueError):
        return str(v)


def punto(v, decimales=2):
    """Numero con punto decimal, como esta escrito el MTD master del usuario."""
    if v in (None, ""):
        return ""
    try:
        s = f"{float(v):.{decimales}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s
    except (TypeError, ValueError):
        return str(v)


# Las letras que admiten los PDF con las fuentes de siempre son las del alfabeto
# latino occidental. Un simbolo pegado desde otro sitio (una flecha, un emoji,
# una letra griega) saldria como un hueco, asi que se cambia o se quita.
SUSTITUCIONES = {
    "≤": "<=", "≥": ">=", "≠": "!=", "≈": "~", "→": "->", "←": "<-",
    "↔": "<->", "∅": "diam.", "Ω": "ohm", "µ": "u", "∞": "infinito",
    "±": "+/-", "√": "raiz", "⋅": "·", "−": "-", "‑": "-", "‒": "-",
    "″": '"', "′": "'", "\t": " ",
}
EXTRAS_WINANSI = {0x20AC, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021,
                  0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0x017D, 0x2018,
                  0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC,
                  0x2122, 0x0161, 0x203A, 0x0153, 0x017E, 0x0178}


def _admitido(cp):
    return 32 <= cp <= 126 or 160 <= cp <= 255 or cp in EXTRAS_WINANSI


def limpiar_para_pdf(v):
    """Devuelve (texto listo para el PDF, lista de lo que se ha quitado)."""
    texto = unicodedata.normalize("NFC", t(v))
    for malo, bueno in SUSTITUCIONES.items():
        if malo in texto:
            texto = texto.replace(malo, bueno)
    quitados, salida = [], []
    for letra in texto:
        if letra == "\n" or _admitido(ord(letra)):
            salida.append(letra)
        elif letra not in quitados:
            quitados.append(letra)
    return "".join(salida), quitados


def mayus(v, cfg=None):
    """
    Todo lo que se escribe en los impresos va en mayusculas, para que no se
    cuele un dato a medio escribir. Se puede desactivar poniendo
    "todo_mayusculas": false en config.json.
    """
    texto, _ = limpiar_para_pdf(v)
    if cfg is not None and cfg.get("todo_mayusculas") is False:
        return texto
    # Los correos van siempre en minusculas: en mayusculas ocupan mas y se
    # salen de la casilla del CIE.
    if "@" in texto:
        return texto.lower()
    return texto.upper()


def sin_acentos(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def nombre_carpeta(datos):
    partes = [t(datos.get("titular_apellido1")), t(datos.get("titular_apellido2")),
              t(datos.get("titular_nombre"))]
    base = " ".join(p for p in partes if p) or "SIN NOMBRE"
    base = sin_acentos(base).upper()
    base = re.sub(r"[^A-Z0-9 ]+", "", base).strip()
    base = re.sub(r"\s+", "_", base)
    return f"{base}_{t(datos.get('fecha')) or date.today().isoformat()}"


def direccion_una_linea(pre, datos):
    """Monta 'CALLE MAYOR 2 3 IZQ' a partir de los campos sueltos."""
    piezas = [t(datos.get(pre + "_tipo_via")), t(datos.get(pre + "_nombre_via")),
              t(datos.get(pre + "_numero")), t(datos.get(pre + "_bloque")),
              t(datos.get(pre + "_escalera")), t(datos.get(pre + "_piso")),
              t(datos.get(pre + "_puerta"))]
    return " ".join(p for p in piezas if p)


def texto_plaza(datos):
    """'PLAZA 5, PLANTA -1' a partir de los campos de la plaza de garaje."""
    plaza = t(datos.get("plaza_numero"))
    planta = t(datos.get("plaza_planta"))
    piezas = []
    if plaza:
        piezas.append(f"PLAZA {plaza}")
    if planta:
        piezas.append(f"PLANTA {planta}")
    return ", ".join(piezas)


def emplazamiento_con_plaza(datos):
    """Direccion del emplazamiento con la plaza y la planta detras."""
    base = direccion_una_linea("empl", datos)
    plaza = texto_plaza(datos)
    if base and plaza:
        return f"{base} · {plaza}"
    return base or plaza


def partes_fecha(iso):
    if not iso:
        d = date.today()
    else:
        try:
            a, m, dd = (int(x) for x in iso.split("-"))
            d = date(a, m, dd)
        except (ValueError, AttributeError):
            d = date.today()
    return str(d.day), MESES[d.month - 1], str(d.year), d


# --------------------------------------------------------------------------
# Datos tecnicos de la instalacion
# --------------------------------------------------------------------------

def valores_tecnicos(datos, cfg):
    """
    Reune los datos tecnicos de la instalacion.

    Se parte de los valores de `tecnica` en config.json, gana cualquier valor
    que venga del formulario, y al final se calculan los que son combinacion de
    otros (el texto del cable, "2X10", "2X40"...) para no pedirlos dos veces.
    """
    tec = dict(cfg["tecnica"])
    for k in list(tec):
        v = datos.get(k)
        if v not in (None, ""):
            tec[k] = t(v)

    # El tipo de cable decide la tension nominal de aislamiento: el unipolar
    # H07Z1-K es 450/750 V y la manguera RZ1-K es 0,6/1 kV.
    cable = (cfg.get("tipos_cable") or {}).get(tec.get("tipo_cable"), {})
    tec["aislamiento"] = cable.get("aislamiento", "0.45/0.75")
    tec["aislamiento_circuito"] = tec["aislamiento"]

    fases = tec.get("fases", "2")
    tec["iga_fases"] = fases
    tec["dif_fases"] = fases
    tec["conductores_x_seccion"] = f"{fases}X{tec['seccion']}"
    tec["iga_texto"] = f"{fases}X{tec['iga_intensidad']}"
    tec["cable_texto"] = (f"{cable.get('texto', 'CONDUCTORES')}, "
                          f"{fases}*{tec['seccion']}mm2")
    tec["aislamiento_texto"] = cable.get("aislamiento_texto",
                                         f"{tec['aislamiento']} kV")
    # En el unifilar se cuentan tambien el neutro y la tierra
    tec["conductores_unifilar"] = str(int(fases) + 1)
    return tec


def aprender_codigo_postal(datos, cfg):
    """
    Guarda la pareja localidad -> codigo postal de este expediente para que la
    proxima vez se rellene sola. No inventa nada: solo recuerda lo que escribes.
    """
    libreta = cfg.setdefault("codigos_postales", {})
    cambiado = False
    for pre in ("titular", "empl"):
        localidad = t(datos.get(pre + "_localidad")).upper()
        cp = re.sub(r"\D", "", t(datos.get(pre + "_cp")))
        if localidad and len(cp) == 5 and libreta.get(localidad) != cp:
            libreta[localidad] = cp
            cambiado = True
    if cambiado:
        guardar_config(cfg)
    return cambiado


# --------------------------------------------------------------------------
# Calculos electricos (ITC-BT-52 e ITC-BT-19)
# --------------------------------------------------------------------------

def calcular(datos, preset, cfg):
    """
    Intensidad de calculo y caida de tension de la linea del punto de recarga.

    Monofasico:  e(V) = 2 * L * P / (gamma * V * S)
    Trifasico:   e(V) =     L * P / (gamma * V * S)

    gamma por defecto 48 para cobre, el mismo valor que usa la hoja
    CAIDA DE TENSION.xlsx del usuario.
    """
    salida = {"avisos": []}

    try:
        p_kw = float(str(datos.get("potencia", "7.36")).replace(",", "."))
    except ValueError:
        p_kw = 7.36
    try:
        v = float(str(datos.get("tension", "230")).replace(",", "."))
    except ValueError:
        v = 230.0
    try:
        long_m = float(str(datos.get("longitud", "0")).replace(",", "."))
    except ValueError:
        long_m = 0.0
    try:
        seccion = float(str(preset.get("seccion", "6")).replace(",", "."))
    except ValueError:
        seccion = 6.0

    material = t(preset.get("material", "Cu")).upper()
    gamma = float(cfg["calculo"]["conductividad_al" if material.startswith("AL")
                                 else "conductividad_cu"])
    trifasico = t(datos.get("tipo_suministro", "Monofásico")).lower().startswith("tri")

    p_w = p_kw * 1000.0

    # Intensidad de calculo
    if trifasico:
        intensidad = p_w / (v * 1.7320508075688772)
    else:
        intensidad = p_w / v

    # Caida de tension
    if long_m > 0 and seccion > 0 and v > 0:
        factor = 1.0 if trifasico else 2.0
        caida_v = factor * long_m * p_w / (gamma * v * seccion)
    else:
        caida_v = 0.0
    caida_pct = (caida_v / v * 100.0) if v else 0.0

    limite = float(cfg["calculo"]["caida_maxima_porcentaje"])
    if caida_pct > limite:
        salida["avisos"].append(
            f"La caida de tension calculada es {caida_pct:.2f} %, por encima del "
            f"{limite:g} % que admite la ITC-BT-52. Sube la seccion o acorta la linea."
        )
    if long_m <= 0:
        salida["avisos"].append(
            "No has indicado la longitud de la linea, asi que la caida de tension "
            "sale 0 y los campos de longitud quedan vacios."
        )

    # Limite de caida de tension en voltios, solo para avisar en pantalla.
    # OJO: la columna "Caida de Tension Maxima (V)" de los impresos NO lleva
    # este limite, sino la caida real calculada.
    caida_max_v = v * limite / 100.0

    # Potencia maxima admisible: la que dejan pasar las protecciones y la
    # seccion instalada. Con 32 A a 230 V son 7,36 kW; con 40 A, 9,2 kW.
    try:
        i_proteccion = float(str(preset.get("iga_intensidad", "32")).replace(",", "."))
    except ValueError:
        i_proteccion = 32.0
    if trifasico:
        pot_max_adm = 1.7320508075688772 * v * i_proteccion / 1000.0
    else:
        pot_max_adm = v * i_proteccion / 1000.0

    salida.update({
        "potencia_kw": p_kw,
        "tension": v,
        "longitud": long_m,
        "seccion": seccion,
        "gamma": gamma,
        "trifasico": trifasico,
        "intensidad": intensidad,
        "caida_v": caida_v,
        "caida_pct": caida_pct,
        "caida_max_v": caida_max_v,
        "intensidad_proteccion": i_proteccion,
        "pot_max_admisible": pot_max_adm,
    })
    return salida


LETRAS_CUPS = "TRWAGMYFPDXBNJZSQVHLCKE"


def validar_cups(cups):
    """
    Comprueba las dos letras de control del CUPS.

    El propio CIE.xls hace esta comprobacion, pero con una funcion que solo
    entiende Excel; en LibreOffice queda como "#¿MACRO?". Se replica aqui para
    poder escribir en el certificado el mismo aviso que veria el usuario.

    Devuelve (valido, texto). `valido` es None si no se ha escrito ningun CUPS.
    """
    c = re.sub(r"\s+", "", t(cups)).upper()
    if not c:
        return None, ""
    if not re.fullmatch(r"ES\d{16}[A-Z]{2}[A-Z0-9]?", c):
        return False, "ERROR: CUPS NO VÁLIDO"
    resto = int(c[2:18]) % 529
    esperado = LETRAS_CUPS[resto // 23] + LETRAS_CUPS[resto % 23]
    if esperado != c[18:20]:
        return False, "ERROR: CUPS NO VÁLIDO"
    return True, "CUPS CORRECTO"


LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"
LETRAS_CIF = "ABCDEFGHJKLMNPQRSUVW"


def validar_nif(nif):
    """
    Comprueba la letra de control de un DNI, un NIE o un CIF.
    Devuelve None si no hay nada escrito, True si cuadra y False si no.
    """
    c = re.sub(r"[\s.-]", "", t(nif)).upper()
    if not c:
        return None

    # DNI: 8 digitos + letra
    if re.fullmatch(r"\d{8}[A-Z]", c):
        return c[8] == LETRAS_DNI[int(c[:8]) % 23]

    # NIE: X, Y o Z + 7 digitos + letra
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", c):
        numero = str("XYZ".index(c[0])) + c[1:8]
        return c[8] == LETRAS_DNI[int(numero) % 23]

    # CIF: letra + 7 digitos + digito o letra de control
    if re.fullmatch(r"[A-Z]\d{7}[0-9A-Z]", c) and c[0] in LETRAS_CIF:
        pares = sum(int(c[i]) for i in (2, 4, 6))
        impares = 0
        for i in (1, 3, 5, 7):
            doble = int(c[i]) * 2
            impares += doble // 10 + doble % 10
        resto = (10 - (pares + impares) % 10) % 10
        return c[8] in (str(resto), "JABCDEFGHI"[resto])

    return False


def distribuidora_por_cups(cups, cfg):
    """El CUPS espanol empieza por ES + 4 digitos de distribuidora."""
    c = re.sub(r"\s+", "", t(cups)).upper()
    m = re.match(r"^ES(\d{4})", c)
    if not m:
        return ""
    return cfg["distribuidoras"].get(m.group(1), "")


# --------------------------------------------------------------------------
# Relleno de PDF
# --------------------------------------------------------------------------

def _estado_encendido(doc, xref):
    """
    Devuelve el nombre del estado "marcado" de una casilla, tal cual esta
    escrito dentro del PDF. Estos impresos oficiales no usan el habitual /Yes
    sino /S#ED, que es "Si" con acento codificado, y por eso PyMuPDF no puede
    marcarlas con el atajo de siempre.
    """
    tipo, valor = doc.xref_get_key(xref, "AP/N")
    if tipo != "dict":
        return None
    for nombre in re.findall(r"/([^\s/<>\[\]()]+)", valor):
        if nombre != "Off":
            return nombre
    return None


def _poner_casilla(doc, xref, encendida):
    estado = _estado_encendido(doc, xref) if encendida else None
    destino = "/" + estado if estado else "/Off"
    doc.xref_set_key(xref, "AS", destino)
    doc.xref_set_key(xref, "V", destino)
    return bool(estado) or not encendida


GRIS_PISTA = (0.55, 0.58, 0.62)


def _quitar_no_imprimibles(doc):
    """
    Quita los campos que el propio impreso marca como "no imprimir".

    En el MTD son los dos botones (Limpiar Campos e Imprimir) de cada pagina y
    el aviso amarillo de la cabecera. Al darle al boton de imprimir no salen, y
    el MTD que aprueba la OCA tampoco los lleva, asi que se quitan de raiz y no
    hay que pasar por el tramite de imprimir a mano.
    """
    quitados = 0
    for pagina in doc:
        for w in list(pagina.widgets()):
            tipo, valor = doc.xref_get_key(w.xref, "F")
            banderas = int(valor) if tipo == "int" else 0
            if banderas & 4:
                continue
            try:
                pagina.delete_widget(w)
            except AttributeError:
                pagina.delete_annot(w)
            quitados += 1
    return quitados


def _quitar_campos_vacios(doc):
    """Saca del documento los campos que se quedan sin texto.

    Un campo vacio de estos impresos no es transparente: su dibujo es un
    rectangulo blanco que tapa lo que hay debajo. En la version editable da
    igual, porque el visor lo redibuja; pero al aplanar queda estampado y se
    come la rejilla de las tablas, que sale a trozos. Como un campo sin texto
    no aporta nada al documento impreso, se quita entero.
    """
    quitados = 0
    for page in doc:
        for w in list(page.widgets()):
            if w.field_type in (pymupdf.PDF_WIDGET_TYPE_CHECKBOX,
                                pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON):
                if (w.field_value or "") not in ("", "Off", False, None):
                    continue
            elif (w.field_value or "").strip():
                continue
            try:
                page.delete_widget(w)
                quitados += 1
            except Exception:  # noqa: BLE001
                pass
    return quitados


def rellenar_pdf(plantilla, mapa, destino, casillas=None, cfg=None, pistas=None,
                 quitar_botones=False, aplanar=False):
    """
    Escribe los valores de `mapa` (nombre_campo -> texto) en el PDF plantilla y
    marca o desmarca las casillas de `casillas` (nombre -> True/False).
    El PDF resultante sigue siendo editable, con las apariencias regeneradas.
    """
    casillas = casillas or {}
    doc = pymupdf.open(plantilla)
    escritos, no_encontrados = 0, set(mapa) | set(casillas)
    pendientes, vaciar = [], []

    # Primera pasada: campos de texto.
    for page in doc:
        for w in page.widgets():
            nombre = w.field_name
            if nombre in casillas:
                pendientes.append((w.xref, casillas[nombre], nombre))
                no_encontrados.discard(nombre)
            elif nombre in mapa:
                valor = mayus(mapa[nombre], cfg)
                if valor:
                    # Solo el texto, sin tocar el fondo. Antes se pintaba de
                    # blanco para que un campo relleno no pareciera un hueco
                    # pendiente, pero ese blanco se comia las lineas de las
                    # tablas del impreso al aplanarlo.
                    w.field_value = valor
                    w.update()
                elif (pistas or {}).get(nombre):
                    # Hueco que rellena el cliente: se le deja escrito en gris
                    # que es lo que tiene que poner ahi.
                    w.field_value = mayus(pistas[nombre], cfg)
                    w.text_color = GRIS_PISTA
                    w.update()
                    try:
                        doc.xref_set_key(w.xref, "TU",
                                         pymupdf.get_pdf_str(t(pistas[nombre])))
                    except Exception:  # noqa: BLE001
                        pass
                else:
                    # PyMuPDF ignora field_value = "", asi que un campo que
                    # viene relleno en la plantilla hay que vaciarlo a mano.
                    vaciar.append(w.xref)
                escritos += 1
                no_encontrados.discard(nombre)

    # Segunda pasada: casillas, por referencia directa al objeto.
    for xref, encendida, nombre in pendientes:
        if _poner_casilla(doc, xref, encendida):
            escritos += 1
        else:
            no_encontrados.add(nombre)

    # Tercera pasada: borrar el valor y la apariencia de los campos vacios.
    for xref in vaciar:
        doc.xref_set_key(xref, "V", "()")
        doc.xref_set_key(xref, "AP", "null")

    if quitar_botones:
        _quitar_no_imprimibles(doc)

    if aplanar:
        _quitar_campos_vacios(doc)
        # bake() pasa los campos al contenido de la pagina: es lo que hace el
        # visor al imprimir a PDF. Los datos quedan fijos y ya no hay formulario.
        doc.bake(annots=False, widgets=True)

    doc.set_metadata({"title": os.path.basename(destino),
                      "producer": "Boletines IRVE Madrid"})
    doc.save(destino, garbage=3, deflate=True)
    doc.close()
    return escritos, sorted(no_encontrados)


# --------------------------------------------------------------------------
# Mapas de campos por documento
# --------------------------------------------------------------------------

def mapa_mtd(datos, cfg, preset, calc):
    """Memoria Tecnica de Diseno (6 paginas). Nombres Texto### del master."""
    e = cfg["empresa"]
    fijos = cfg["valores_fijos_mtd"]
    dia, mes, anio, _ = partes_fecha(datos.get("fecha"))

    dir_titular = direccion_una_linea("titular", datos)
    dir_empl = emplazamiento_con_plaza(datos)

    m = {
        # --- pagina 1: datos administrativos ---
        "Texto1": t(datos.get("num_expediente")),
        "Texto2": t(datos.get("titular_nif")),
        "Texto3": t(datos.get("titular_nombre")),
        "Texto4": t(datos.get("titular_apellido1")),
        "Texto5": t(datos.get("titular_apellido2")),
        "Texto6": dir_titular,
        "Texto7": t(datos.get("titular_localidad")),
        "Texto8": t(datos.get("titular_cp")),
        "Texto9": dir_empl,
        "Texto10": t(datos.get("empl_localidad")),
        "Texto11": t(datos.get("empl_cp")),
        "Texto12": fijos["uso"],

        # --- pagina 1: caracteristicas generales ---
        "Texto13": punto(calc["tension"], 0),
        "Texto15": fijos["grado_electrificacion"],
        "Texto17": fijos["memoria_por"],
        "Texto19": fijos["uso_instalacion"],
        "Texto21": fijos["punto_conexion"],
        "Texto22": fijos["tipo_acometida"],
        "Texto24": fijos["material_acometida"],
        "Texto25": fijos["cgp_tipo"],
        "Texto26": fijos["cgp_in_base"],
        "Texto27": fijos["cgp_in_cartucho"],
        "Texto28": fijos["lga_seccion"],
        "Texto29": fijos["lga_material"],
        "Texto30": preset["seccion"],
        "Texto31": preset["material"],
        "Texto32": fijos["igm_nominal"],
        "Texto33": fijos["igm_poder_corte"],
        "Texto34": fijos["num_derivaciones"],
        # Presupuesto. Es obligatorio en el impreso. Dos columnas
        # -Instalaciones Interior y TOTAL- por tres filas: materiales,
        # mano de obra y total.
        "Texto217": fijos.get("presupuesto_materiales", ""),
        "Texto219": fijos.get("presupuesto_materiales", ""),
        "Texto224": fijos.get("presupuesto_mano_obra", ""),
        "Texto226": fijos.get("presupuesto_mano_obra", ""),
        "Texto231": fijos.get("presupuesto_total", ""),
        "Texto233": fijos.get("presupuesto_total", ""),
        # Datos tecnicos del punto de medida. Venian puestos en la
        # plantilla, heredados de otro trabajo; ahora salen porque se
        # han configurado.
        "Texto252": fijos.get("num_suministros_monofasicos", ""),
        "Texto259": fijos.get("emplazamiento_planta_baja", ""),
        "Texto268": fijos.get("ubicacion_centralizacion_modular", ""),
        "Texto36": fijos["modulo_tipo"],
        "Texto37": fijos["modulo_situacion"],
        "Texto38": preset["iga_texto"],
        "Texto39": preset["dif_intensidad"],
        "Texto40": preset["dif_sensibilidad"],
        "Texto41": "X",
        "Texto44": fijos["tierra_electrodos"],
        "Texto46": fijos["tierra_linea_enlace"],
        "Texto47": preset["conductor_proteccion"],

        # --- pagina 1: empresa instaladora ---
        "Texto35": e["instalador_nombre"],
        "Texto49": e["instalador_num_certificado"],
        "Texto50": f"{e['tipo_via']} {e['nombre_via']}".strip(),
        "Texto51": e["numero"],
        "Texto52": e["municipio"],
        "Texto55": e["cp"],
        "Texto53": e["telefono"],
        "Texto56": e["email"],
        "Texto70": e["instalador_nombre"],
        "Texto71": e["lugar_firma"],
        "Texto72": dia,
        "Texto73": mes,
        "Texto74": anio,

        # --- pagina 2: prevision de cargas ---
        "Texto191": t(datos.get("descripcion_punto")) or "PUNTO DE RECARGA V.E. TIPO 2",
        "Texto194": punto(calc["potencia_kw"]),
        "Texto195": punto(calc["potencia_kw"]),
        "Texto211": punto(calc["potencia_kw"]),
        "Texto212": punto(calc["potencia_kw"]),

        # --- pagina 3: derivaciones individuales ---
        "Texto273": "IRVE",
        "Texto274": "1",
        "Texto275": punto(calc["potencia_kw"]),
        "Texto276": punto(calc["pot_max_admisible"]),
        "Texto277": preset["iga_fases"],
        "Texto278": preset["seccion"],
        "Texto279": preset["material"],
        "Texto280": preset["aislamiento"],
        "Texto281": punto(calc["caida_v"]) if calc["caida_v"] else "",
        "Texto282": preset["fusible_seguridad"],

        # --- pagina 3: dispositivos generales de mando y proteccion ---
        "Texto313": "IRVE",
        "Texto314": preset["iga_fases"],
        "Texto315": preset["seccion"],
        "Texto316": "X",
        "Texto318": preset["iga_fases"],
        "Texto319": preset["iga_intensidad"],
        "Texto320": preset["iga_poder_corte"],
        "Texto321": preset["dif_fases"],
        "Texto322": preset["dif_intensidad"],
        "Texto323": preset["dif_sensibilidad"],

        # --- pagina 4: resumen calculo instalaciones de enlace ---
        # La fila 4 del impreso pertenece a "Grado de electrificacion / Basica";
        # un punto de recarga va en el bloque "Otras instalaciones", que empieza
        # en la fila 26 (campos Texto790 a Texto807). La fila 4 se vacia.
        "Texto790": "IRVE",
        "Texto791": punto(calc["potencia_kw"]),
        "Texto792": punto(calc["tension"], 0),
        "Texto793": punto(calc["intensidad"], 0),
        "Texto794": preset["conductores_x_seccion"],
        "Texto795": preset["material"],
        "Texto796": preset["aislamiento"],
        "Texto797": preset["tipo_instalacion_di"],
        "Texto799": preset["diametro_tubo"],
        "Texto800": preset["num_tubos"],
        "Texto801": punto(calc["longitud"]) if calc["longitud"] else "",
        "Texto802": punto(calc["caida_v"]) if calc["caida_v"] else "",
        "Texto803": punto(calc["pot_max_admisible"]),
        "Texto804": punto(calc["potencia_kw"]),
        "Texto805": preset["fusible_seguridad"],
        "Texto806": preset["iga_intensidad"],
        "Texto807": preset["dif_intensidad"],

        # --- pagina 5: circuitos internos ---
        "Texto1518": punto(calc["potencia_kw"]),
        "Texto1519": punto(calc["tension"], 0),
        "Texto1520": punto(calc["intensidad"], 0),
        "Texto1521": preset["conductores_x_seccion"].lower(),
        "Texto1522": preset["material"],
        "Texto1523": preset["aislamiento_circuito"],
        "Texto1524": preset["tipo_instalacion_circuito"],
        "Texto1525": punto(calc["longitud"]) if calc["longitud"] else "",
        "Texto1526": punto(calc["caida_v"]) if calc["caida_v"] else "",
        "Texto1527": punto(calc["pot_max_admisible"]),
        "Texto1528": punto(calc["potencia_kw"]),
        "Texto1529": preset["fusible_seguridad"],
    }

    # La plantilla trae la fila 4 rellena. Se vacia para que el punto de recarga
    # aparezca una sola vez, en "Otras instalaciones".
    for campo in ["Texto416"] + [f"Texto{n}" for n in range(399, 416)]:
        m[campo] = ""

    # --- pagina 6: descripcion de los trabajos ---
    for i, linea in enumerate(lineas_descripcion(datos, preset, calc), start=1590):
        m[f"Texto{i}"] = linea

    # Casilla "MEMORIA REALIZADA POR INSTALADOR AUTORIZADO"
    return m, {
        "Casilla de verificación69": True,
        "Casilla de verificación70": False,
        # "Documentacion que se adjunta", ultima pagina. Venian marcadas
        # en la plantilla, heredadas de otro trabajo; ahora salen porque
        # se han configurado. Arriba: unifilar y planos; abajo: croquis
        # y otros.
        "Casilla de verificación1613": fijos.get("adjunta_esquema_unifilar", True) is not False,
        "Casilla de verificación1614": fijos.get("adjunta_planos_planta", True) is not False,
        "Casilla de verificación1615": fijos.get("adjunta_croquis_trazado", True) is not False,
        "Casilla de verificación1616": fijos.get("adjunta_otros", False) is True,
    }


# La memoria descriptiva del MTD son 23 renglones sueltos (Texto1590 a
# Texto1612) de unos 428 puntos de ancho, donde caben unos 74 caracteres.
RENGLONES_MEMORIA = 23
ANCHO_MEMORIA = 74


def lineas_descripcion(datos, preset, calc):
    """Memoria descriptiva de la ultima pagina del MTD, un renglon por linea."""
    plaza = t(datos.get("plaza_numero"))
    planta = t(datos.get("plaza_planta"))
    desc = t(datos.get("descripcion_punto")) or "PUNTO DE RECARGA V.E. TIPO 2"
    origen = t(datos.get("origen_linea")) or "CENTRALIZACIÓN DE CONTADORES"

    # Si en la marca y modelo ya has escrito la potencia, no se repite detras.
    if re.search(r"\d[\d.,]*\s*k\s*w", desc, re.IGNORECASE):
        cabecera = f"INSTALACIÓN DE {desc}, DESDE {origen}"
    else:
        cabecera = (f"INSTALACIÓN DE {desc}, {punto(calc['potencia_kw'])} kW, "
                    f"DESDE {origen}")
    if plaza:
        cabecera += f", HASTA PLAZA DE GARAJE Nº {plaza}"
    if planta:
        cabecera += f", EN PLANTA {planta}"
    cabecera += "."

    lineas = textwrap.wrap(cabecera.upper(), width=ANCHO_MEMORIA) or [cabecera]
    lineas += [
        f"CONDUCTORES: {preset['cable_texto']}",
        "CUADRO DE PUNTO DE RECARGA:",
        f"IGA: {preset['iga_fases']}*{preset['iga_intensidad']}A; 2P CURVA C",
        f"DIF: {preset['dif_fases']}*{preset['dif_intensidad']}A/"
        f"{preset['dif_sensibilidad']}mA; 2P CLASE {preset['dif_clase']} \"SI\"",
        "PROTECTOR SOBRETENSIONES TRANSITORIAS Y PERMANENTES",
    ]

    extra = t(datos.get("observaciones"))
    if extra:
        lineas.append("")
        for parrafo in extra.splitlines():
            lineas += textwrap.wrap(parrafo, width=ANCHO_MEMORIA) or [""]

    return lineas[:RENGLONES_MEMORIA]


def mapa_anexo_ive(datos, cfg, preset, calc):
    """Anexo de declaracion sobre montaje de IVE (ITC-BT-52)."""
    e = cfg["empresa"]
    dia, mes, anio, _ = partes_fecha(datos.get("fecha"))
    p1 = "topmostSubform[0].Page1[0]."

    m = {
        "topmostSubform[0].Page5[0].CampoTexto52[0]": e["instalador_nombre"],
        "dni DON": e["instalador_nif"],
        p1 + "CampoTexto46[0]": e["razon_social"],
        "CIF": e["nif"],
        p1 + "CampoTexto54[0]": e["direccion_una_linea"],
        p1 + "CampoTexto55[0]": e["cp"],
        p1 + "CampoTexto56[0]": e["municipio"],
        p1 + "CampoTexto57[0]": e["provincia"],

        # potencia maxima admisible de la IVE y esquema
        p1 + "CampoTexto26[0]": coma(calc["potencia_kw"]),
        "Dropdown2": t(datos.get("esquema", "2")),
        "Número de puntos de recarga": t(datos.get("num_puntos", "1")),

        # instalacion existente a la que se conecta la IVE
        p1 + "CampoTexto12[0]": t(datos.get("empl_tipo_via")),
        p1 + "CampoTexto13[0]": t(datos.get("empl_nombre_via")),
        p1 + "CampoTexto14[0]": t(datos.get("empl_numero")),
        p1 + "CampoTexto15[0]": t(datos.get("empl_bloque")),
        p1 + "CampoTexto16[0]": t(datos.get("empl_escalera")),
        p1 + "CampoTexto17[0]": t(datos.get("empl_piso")),
        p1 + "CampoTexto18[0]": t(datos.get("empl_puerta")),

        # fecha (aparece en las dos paginas con el mismo nombre de campo)
        p1 + "CampoTexto69[0]": e["lugar_firma"],
        p1 + "CampoTexto70[0]": dia,
        p1 + "CampoTexto71[0]": mes,
        p1 + "CampoTexto72[0]": anio,

        # --- pagina 2: justificacion de prevision de cargas y esquema unifilar
        #
        # CUIDADO: en este impreso los nombres de campo NO se corresponden con
        # la columna sobre la que estan. Comprobado por posicion (coordenada x)
        # contra las cabeceras impresas. El orden real de las columnas es:
        #
        #   x134 P.Cálculo60 .................. Potencia de Cálculo (kW)
        #   x170 Tensión de Cálculo60 ......... Tensión de Cálculo (V)
        #   x205 Intensidad de Cálculo60 ...... Intensidad de Cálculo (A)
        #   x240 nº Conductores-Sección60 ..... Nº conductores x Sección (mm2)
        #   x276 Material conductor60 ......... Material (Cu o Al)
        #   x312 Asilamiento T.Nominal60 ...... Tensión nominal Aislamiento (kV)
        #   x347 (ITC-BT-26)60 ................ Tipo Instalación (ITC-BT-26)
        #   x382 Tipo de instalación60 ........ Longitud Máxima (m)
        #   x417 Intensidad máxima admisible60  Caída de Tensión Máxima (V) -> la calculada
        #   x453 C/C PIA60 .................... Potencia Máxima Admisible (kW)
        #   x490 Longitud60 ................... Potencia Total Instalada (kW)
        #   x521 Caída de tensión60 ........... Intensidad Fusible o P.I.A. (A)
        "P.Cálculo60": punto(calc["potencia_kw"]),
        "Tensión de Cálculo60": punto(calc["tension"], 0),
        "Intensidad de Cálculo60": punto(calc["intensidad"], 0),
        "nº Conductores-Sección60": preset["conductores_x_seccion"],
        "Material conductor60": preset["material"],
        "Asilamiento T.Nominal60": preset["aislamiento"],
        "(ITC-BT-26)60": preset["tipo_instalacion_circuito"],
        "Tipo de instalación60": punto(calc["longitud"]) if calc["longitud"] else "",
        "Intensidad máxima admisible60": punto(calc["caida_v"]) if calc["caida_v"] else "",
        "C/C PIA60": punto(calc["pot_max_admisible"]),
        "Longitud60": punto(calc["potencia_kw"]),
        "Caída de tensión60": preset["fusible_seguridad"],
    }

    # Tipo de IVE segun la ITC-BT-52. La cuarta opcion, "resto de
    # infraestructuras", es la habitual en un punto de recarga domestico.
    elegida = "IRVEop4"
    if calc["potencia_kw"] > 50:
        elegida = "IRVEop1"
    elif (t(datos.get("ubicacion_fisica")).lower().startswith("ext")
          and calc["potencia_kw"] > 10):
        elegida = "IRVEop2"
    casillas = {f"IRVEop{i}": (f"IRVEop{i}" == elegida) for i in (1, 2, 3, 4)}
    return m, casillas


# Lo que se escribe en gris dentro de los huecos que deja el instalador para
# que los rellene el cliente. Se ve en el PDF y tambien al pasar el raton.
PISTAS_ANEXO_GARAJE = {
    "titular garaje": "Escriba aquí el nombre de la comunidad de propietarios",
    "NIF titular garaje": "CIF de la comunidad",
    "domicilio titular garaje": "Domicilio de la comunidad",
    "localidad tit. garaje": "Localidad",
    "C.P. titular garaje": "C.P.",
    "provincia tit. garaje": "Provincia",
    "nº plaza": "Nº de plaza",
    "planta plaza": "Planta",
}


def mapa_anexo_garaje(datos, cfg):
    """Declaracion sobre inspeccion periodica del garaje (Acta XII GTREBT)."""
    dia, mes, anio, _ = partes_fecha(datos.get("fecha"))
    nombre = " ".join(x for x in [t(datos.get("titular_nombre")),
                                  t(datos.get("titular_apellido1")),
                                  t(datos.get("titular_apellido2"))] if x)
    m = {
        "nombre titular": nombre,
        "Texto2": t(datos.get("titular_nif")),
        "domicilop titular": direccion_una_linea("titular", datos),
        "nº plaza": t(datos.get("plaza_numero")),
        "planta plaza": t(datos.get("plaza_planta")),
        "Texto6": direccion_una_linea("empl", datos),
        "localidad garaje": t(datos.get("empl_localidad")),
        "c.p. garaje": t(datos.get("empl_cp")),
        "provincia garaje": t(datos.get("empl_provincia")) or "MADRID",
        "titular garaje": t(datos.get("cp_nombre")),
        "NIF titular garaje": t(datos.get("cp_nif")),
        "domicilio titular garaje": t(datos.get("cp_domicilio")),
        "localidad tit. garaje": t(datos.get("cp_localidad")),
        "C.P. titular garaje": t(datos.get("cp_cp")),
        "provincia tit. garaje": t(datos.get("cp_provincia")) or "MADRID",
        "dia": dia,
        "mes": mes,
        "año": anio,
    }
    return m, {}


def mapa_unifilar(datos, cfg, preset, calc):
    """Esquema unifilar de la instalacion."""
    e = cfg.get("empresa") or {}
    dia, mes, anio, _ = partes_fecha(datos.get("fecha"))
    p1 = "topmostSubform[0].Page1[0]."
    titular = " ".join(x for x in [t(datos.get("titular_apellido1")),
                                   t(datos.get("titular_apellido2")),
                                   t(datos.get("titular_nombre"))] if x)
    m = {
        # la linea que alimenta el punto de recarga
        "DERIVACION INDIVIDUAL": (f"{preset['conductores_unifilar']} x "
                                  f"{preset['seccion']} mm² {preset['material']} "
                                  f"{preset['aislamiento_texto']}"),
        "IMG1": f"{preset['iga_fases']}x{preset['iga_intensidad']}",
        "IDG1": f"{preset['dif_fases']}x{preset['dif_intensidad']}",
        "IDG1S": f"{preset['dif_sensibilidad']} mA",
        "IDG1C": preset["dif_clase"],
        # pie del esquema
        "NombreEmpresaInstaladora": e.get("razon_social", ""),
        p1 + "CampoTexto1[0]": titular,
        p1 + "CampoTexto12[0]": t(datos.get("empl_tipo_via")),
        p1 + "CampoTexto13[0]": t(datos.get("empl_nombre_via")),
        p1 + "CampoTexto14[0]": t(datos.get("empl_numero")),
        p1 + "CampoTexto15[0]": t(datos.get("empl_bloque")),
        p1 + "CampoTexto16[0]": t(datos.get("empl_escalera")),
        p1 + "CampoTexto17[0]": t(datos.get("empl_piso")),
        p1 + "CampoTexto18[0]": t(datos.get("empl_puerta")),
        p1 + "CampoTexto70[0]": dia,
        p1 + "CampoTexto71[0]": mes,
        p1 + "CampoTexto72[0]": anio,
    }
    return m, {}


def mapa_autorizacion(datos, cfg):
    """Autorizacion del titular al instalador para gestionar el expediente."""
    e = cfg["empresa"]
    nombre = " ".join(x for x in [t(datos.get("titular_nombre")),
                                  t(datos.get("titular_apellido1")),
                                  t(datos.get("titular_apellido2"))] if x)
    m = {
        "Auto_Text1": nombre,
        "Auto_Text2": t(datos.get("titular_nif")),
        "Auto_Text3": e["instalador_nombre"],
        "Auto_Text4": e["instalador_nif"],
        "Auto_Text5": direccion_una_linea("empl", datos),
        "Auto_Text6": " · ".join(x for x in [
            f"{t(datos.get('empl_cp'))} {t(datos.get('empl_localidad'))}".strip(),
            texto_plaza(datos),
        ] if x),
    }
    return m, {}


def mapa_solicitud(datos, cfg):
    """Solicitud de inscripcion BT-1134F1."""
    e = cfg["empresa"]
    dia, mes, anio, _ = partes_fecha(datos.get("fecha"))
    m = {
        # 1. titular
        "NIF": t(datos.get("titular_nif")),
        "Primer Apellido": t(datos.get("titular_apellido1")),
        "Segundo Apellido": t(datos.get("titular_apellido2")),
        "NombreRazón Social": t(datos.get("titular_nombre")),
        "Correo electrónico": t(datos.get("titular_email")),
        "Tipo de vía": t(datos.get("titular_tipo_via")),
        "Nombre vía": t(datos.get("titular_nombre_via")),
        "N": t(datos.get("titular_numero")),
        "Bloque": t(datos.get("titular_bloque")),
        "Escalera": t(datos.get("titular_escalera")),
        "Piso": t(datos.get("titular_piso")),
        "Puerta": t(datos.get("titular_puerta")),
        "Localidad": t(datos.get("titular_localidad")),
        "Provincia": t(datos.get("titular_provincia")) or "MADRID",
        "CP": t(datos.get("titular_cp")),
        "Teléfono Móvil": t(datos.get("titular_movil")),

        # 3. empresa instaladora
        "NIF_3": e["nif"],
        "NombreRazón Social_2": e["razon_social"],
        "Correoe": e["email"],
        "Categoría": e["categoria"].upper(),
        "N Registro": e["num_registro"],
        "Nombre del instalador": e["instalador_nombre"],
        "Tipo de vía_3": e["tipo_via"],
        "Nombre vía_3": e["nombre_via"],
        "N_3": e["numero"],
        "Localidad_3": e["municipio"],
        "Provincia_3": e["provincia"],
        "CP_3": e["cp"],
        "Teléfono Móvil_3": e["telefono"],

        # 6. emplazamiento
        "Tipo de vía_6": t(datos.get("empl_tipo_via")),
        "Nombre vía_6": t(datos.get("empl_nombre_via")),
        "N_6": t(datos.get("empl_numero")),
        "CP_6": t(datos.get("empl_cp")),
        "Bloque_6": t(datos.get("empl_bloque")),
        "Escalera_6": t(datos.get("empl_escalera")),
        "Piso_6": t(datos.get("empl_piso")),
        "Puerta_6": t(datos.get("empl_puerta")),
        "Localidad_6": t(datos.get("empl_localidad")),

        # firma
        "En": e["lugar_firma"],
        "Dia": dia,
        "Mes": mes,
        "Año": anio,
        "Otros": "AUTORIZACIÓN",
    }
    # Casillas: nueva instalacion, tipo de instalacion IRVE y documentacion
    # aportada (tasa, tarifa EICI, MTD, CIE, dossier, contrato, autorizacion).
    nombres = ["Nueva instalación", "Tipo9",
               "Tipo24", "Tipo25", "Tipo26", "Tipo27", "Tipo28",
               "Tipo34", "Tipo37", "Tipo38"]
    return m, {n: True for n in nombres}


# --------------------------------------------------------------------------
# CIE.xls -> celdas
# --------------------------------------------------------------------------

def celdas_cie(datos, cfg, preset, calc):
    """Celdas de entrada de la hoja CIE del libro oficial de la EICI."""
    e = cfg["empresa"]
    f = cfg["valores_fijos_cie"]
    _, _, _, d = partes_fecha(datos.get("fecha"))

    distribuidora = (t(datos.get("distribuidora"))
                     or distribuidora_por_cups(datos.get("cups"), cfg))

    info = "\n".join(x for x in [
        f"IRVE DE USO {t(datos.get('uso_irve', 'PRIVADO')).upper()} EN GARAJE "
        f"{t(datos.get('tipo_garaje', 'COMUNITARIO')).upper()} "
        f"{t(datos.get('ubicacion_fisica', 'INTERIOR')).upper()}",
        f"Nº DE PUNTOS DE CONEXIÓN: {t(datos.get('num_puntos', '1'))}, "
        f"ESQUEMA {t(datos.get('esquema', '2'))}. "
        f"{t(datos.get('descripcion_punto', 'CONECTOR TIPO 2 MENNEKES')).upper()}",
    ] if x)

    return {
        # --- titular ---
        "B7": t(datos.get("titular_nif")),
        "H7": t(datos.get("titular_apellido1")),
        "P7": t(datos.get("titular_apellido2")),
        "D8": t(datos.get("titular_nombre")),
        "O8": t(datos.get("titular_email")),
        "D9": t(datos.get("titular_tipo_via")),
        "H9": t(datos.get("titular_nombre_via")),
        "U9": t(datos.get("titular_numero")),
        "C10": t(datos.get("titular_bloque")),
        "F10": t(datos.get("titular_escalera")),
        "H10": t(datos.get("titular_piso")),
        "J10": t(datos.get("titular_puerta")),
        "M10": t(datos.get("titular_localidad")),
        "C11": t(datos.get("titular_provincia")) or "MADRID",
        "I11": t(datos.get("titular_cp")),
        "M11": t(datos.get("titular_fijo")),
        "S11": t(datos.get("titular_movil")),

        # --- emplazamiento ---
        "C16": t(datos.get("empl_tipo_via")),
        "G16": t(datos.get("empl_nombre_via")),
        "S16": t(datos.get("empl_numero")),
        "U16": t(datos.get("empl_cp")),
        "C17": t(datos.get("empl_bloque")),
        "F17": t(datos.get("empl_escalera")),
        "H17": t(datos.get("empl_piso")),
        "J17": t(datos.get("empl_puerta")),
        "M17": t(datos.get("empl_localidad")),
        "E18": t(datos.get("ubicacion_contador")) or "Local",
        # Direccion del punto de suministro: la plaza y la planta del garaje
        "M18": texto_plaza(datos),

        # --- caracteristicas tecnicas ---
        "C20": f["actuacion"],
        "M20": re.sub(r"\s+", "", t(datos.get("cups"))).upper(),
        "U20": f["superficie"],
        # Pot. Max. Adm. es la que dejan pasar las protecciones, no la del
        # cargador: 32 A dan 7,36 kW y 40 A dan 9,2 kW.
        "D21": coma(calc["pot_max_admisible"]),
        "J21": f["tipo_instalacion"],
        "U21": f["aforo"],
        "D22": f["pot_ampliada"],
        "J22": t(datos.get("tipo_suministro")) or "Monofásico",
        "M22": punto(calc["tension"], 0),
        "T22": preset["seccion"],
        "D23": f["pot_original"],
        "T23": f["esquema_distribucion"],
        "I24": f["punto_conexion"],
        "M24": f["tipo_acometida"],
        "T24": f["cgp_esquema"],
        "J25": preset["iga_intensidad"],
        "P25": f["prot_sobretensiones"],
        "U25": f["int_diferencial"],
        "F26": distribuidora,
        "A28": info,

        # --- empresa instaladora ---
        "B30": e["nif"],
        "H30": e["razon_social"],
        "G31": e["categoria"],
        "R31": e["num_registro"],
        "E32": e["instalador_nombre"],
        "S32": e["instalador_nif"],
        "D33": e["tipo_via"],
        "H33": e["nombre_via"],
        "Q33": e["numero"],
        "U33": e["cp"],
        "C34": e["municipio"],
        "I34": e["provincia"],
        "M34": e["telefono"],
        "R34": e["email"],

        # --- certificacion y verificaciones ---
        "L38": f["documentacion"],
        "A40": f["rd1890"],
        "A42": f["itc_bt_51"],
        # El impreso ya trae escrito "En": aqui va el lugar y la fecha
        "B43": " A ".join(x for x in [t(e.get("lugar_firma"))
                                      or t(e.get("municipio")),
                                      d.strftime("%d/%m/%Y")] if x),
        "S51": f["resistencia_tierra"],
        "S52": f["resistencia_aislamiento"],
        "S53": f["otras_verificaciones"],
    }


def python_libreoffice():
    for ruta in SOFFICE_CANDIDATOS:
        if os.path.exists(ruta):
            return ruta
    return None


def generar_cie(datos, cfg, preset, calc, carpeta):
    """
    Genera el CIE en PDF.

    Por defecto lo dibuja directamente sobre el impreso en blanco, sin
    LibreOffice (ver cie_pdf.py). Si faltasen los ficheros preparados, o si en
    config.json se pone "cie_con_libreoffice": true, se cae al camino antiguo,
    que abre el .xls con LibreOffice.
    """
    crudas = dict(celdas_cie(datos, cfg, preset, calc))
    crudas.update((cfg.get("extras") or {}).get("CIE") or {})
    celdas = {k: mayus(v, cfg) for k, v in crudas.items()}
    _valido, texto_cups = validar_cups(datos.get("cups"))
    pdf_destino = os.path.join(carpeta, "CIE.pdf")

    if not cfg.get("cie_con_libreoffice") and cie_pdf.disponible():
        try:
            ident, texto_estado = cie_pdf.generar_cie_pdf(
                celdas, pdf_destino, mayus(texto_cups, cfg))
            return True, texto_estado, {"pdf": pdf_destino, "identificador": ident}
        except Exception as exc:  # noqa: BLE001
            return (False,
                    f"No he podido dibujar el CIE ({exc}). "
                    "Prueba a poner \"cie_con_libreoffice\": true en config.json.",
                    {})

    return _generar_cie_con_libreoffice(datos, cfg, preset, calc, carpeta,
                                        celdas, texto_cups)


def _generar_cie_con_libreoffice(datos, cfg, preset, calc, carpeta,
                                 celdas, texto_cups):
    """Camino antiguo: rellenar el .xls y exportarlo con LibreOffice."""
    py_lo = python_libreoffice()
    xls_destino = os.path.join(carpeta, "CIE.xls")
    pdf_destino = os.path.join(carpeta, "CIE.pdf")

    peticion = {
        "plantilla": os.path.join(PLANTILLAS, "CIE.xls"),
        "xls_destino": xls_destino,
        "pdf_destino": pdf_destino,
        "celdas": celdas,
        "textos": {"M19": mayus(texto_cups, cfg)} if texto_cups else {},
    }
    ruta_json = os.path.join(carpeta, "_cie_peticion.json")
    with open(ruta_json, "w", encoding="utf-8") as fh:
        json.dump(peticion, fh, ensure_ascii=False)

    if not py_lo:
        shutil.copy(peticion["plantilla"], xls_destino)
        os.remove(ruta_json)
        return (False,
                "No encuentro LibreOffice, asi que he copiado el CIE.xls en blanco. "
                "Instala LibreOffice o rellena el CIE a mano.",
                {"xls": xls_destino})

    try:
        proc = subprocess.run(
            [py_lo, os.path.join(RAIZ, "cie_libreoffice.py"), ruta_json],
            capture_output=True, timeout=240,
        )
        salida = (proc.stdout or b"").decode("utf-8", "replace").strip()
        error = (proc.stderr or b"").decode("utf-8", "replace").strip()
    except subprocess.TimeoutExpired:
        return (False, "LibreOffice tardo demasiado en responder.", {})
    finally:
        if os.path.exists(ruta_json):
            os.remove(ruta_json)

    if proc.returncode != 0 or not os.path.exists(pdf_destino):
        shutil.copy(peticion["plantilla"], xls_destino)
        # De la traza de LibreOffice solo interesa la ultima linea util.
        detalle = ""
        for linea in reversed((error or salida or "").splitlines()):
            linea = linea.strip()
            if linea and not linea.startswith(("File ", "^", "Traceback", "During")):
                detalle = linea.split(": ", 1)[-1][:180]
                break
        return (False,
                f"LibreOffice no pudo generar el CIE. {detalle} "
                "Te dejo el CIE.xls en blanco para rellenarlo a mano.",
                {"xls": xls_destino})

    estado = ""
    for linea in salida.splitlines():
        if linea.startswith("ESTADO="):
            estado = linea.split("=", 1)[1].strip()
    return True, estado, {"xls": xls_destino, "pdf": pdf_destino}


# --------------------------------------------------------------------------
# Generacion del expediente completo
# --------------------------------------------------------------------------

# (plantilla, nombre de salida, tipo, siempre, quitar los botones del impreso)
# plantilla, nombre de salida, tipo, siempre, quitar botones, aplanar
DOCUMENTOS = [
    ("MTD.pdf", "MTD - Memoria Tecnica de Diseno.pdf", "mtd", True, True, True),
    ("ANEXO_IVE.pdf", "Anexo IVE - declaracion ITC-BT-52.pdf", "anexo_ive", True, False, False),
    ("UNIFILAR.pdf", "Esquema unifilar.pdf", "unifilar", True, False, False),
    ("SOLICITUD.pdf", "Solicitud de inscripcion BT-1134F1.pdf", "solicitud", True, False, False),
    ("AUTORIZACION.pdf", "Autorizacion del titular al instalador.pdf", "autorizacion", True, False, False),
    ("ANEXO_GARAJE.pdf", "Anexo - inspeccion periodica del garaje.pdf", "anexo_garaje", False, False, False),
]


def aplicar_extras(mapa, casillas, extras):
    """Ajustes por documento elegidos desde la pantalla de Configuracion.

    Van encima de lo que pone la aplicacion, porque si alguien los escribe ahi
    a mano es que los quiere asi. Un valor de si/no es una casilla; cualquier
    otra cosa, texto.
    """
    if not extras:
        return mapa, casillas
    mapa, casillas = dict(mapa), dict(casillas)
    for campo, valor in extras.items():
        if isinstance(valor, bool):
            casillas[campo] = valor
        elif t(valor) != "":
            mapa[campo] = t(valor)
    return mapa, casillas


def generar(datos, aplanar_mtd=True):
    """Genera el expediente entero.

    `aplanar_mtd=False` deja el MTD con sus campos en vez de aplanado. Solo lo
    usa herramientas/comparar.py: los dos motores aplanan con librerias
    distintas y el dibujo no sale igual, asi que se comparan antes de aplanar.
    """
    cfg = cargar_config()
    preset = valores_tecnicos(datos, cfg)
    calc = calcular(datos, preset, cfg)

    carpeta = os.path.join(SALIDA, nombre_carpeta(datos))
    os.makedirs(carpeta, exist_ok=True)

    resultado = {"carpeta": carpeta, "documentos": [], "avisos": list(calc["avisos"]),
                 "calculo": {
                     "intensidad": round(calc["intensidad"], 2),
                     "caida_v": round(calc["caida_v"], 2),
                     "caida_pct": round(calc["caida_pct"], 2),
                 }}

    valido_cups, _ = validar_cups(datos.get("cups"))
    if valido_cups is False:
        resultado["avisos"].append(
            "El CUPS no pasa la comprobacion de las dos letras de control. "
            "Revisalo antes de presentar el certificado.")
    elif valido_cups is None:
        resultado["avisos"].append(
            "No has escrito el CUPS, asi que el CIE saldra como incompleto.")

    if validar_nif(datos.get("titular_nif")) is False:
        resultado["avisos"].append(
            "El NIF del titular no pasa la comprobacion de la letra de control.")

    # El cargador no puede pedir mas de lo que dejan pasar las protecciones.
    if calc["potencia_kw"] > calc["pot_max_admisible"] + 0.01:
        resultado["avisos"].append(
            f"El punto pide {coma(calc['potencia_kw'])} kW pero las protecciones "
            f"de {punto(calc['intensidad_proteccion'], 0)} A solo admiten "
            f"{coma(calc['pot_max_admisible'])} kW. Sube la proteccion o baja la "
            "potencia del cargador.")

    # Si se ha pegado algun simbolo que las fuentes del PDF no admiten, se ha
    # quitado al escribirlo. Mejor avisarlo que dejarlo pasar callando.
    raros = []
    for valor in datos.values():
        if isinstance(valor, str):
            for c in limpiar_para_pdf(valor)[1]:
                if c not in raros:
                    raros.append(c)
    if raros:
        resultado["avisos"].append(
            "He quitado de los documentos " + ", ".join(f"«{c}»" for c in raros)
            + ": los impresos oficiales no admiten esos simbolos. Revisa que el "
            "texto siga diciendo lo que querias.")

    incluir_garaje = bool(datos.get("incluir_anexo_garaje"))
    if incluir_garaje and not t(datos.get("cp_nombre")):
        resultado["avisos"].append(
            "No has puesto los datos de la comunidad de propietarios. En el "
            "anexo del garaje esos huecos salen en gris, indicando lo que hay "
            "que escribir, para que los rellene el cliente desde el PDF. Dile "
            "que borre el texto gris al escribir encima: si no lo hace, se "
            "imprime tal cual.")

    for plantilla, nombre_salida, tipo, siempre, quitar, aplanar in DOCUMENTOS:
        if tipo == "anexo_garaje" and not incluir_garaje:
            continue
        origen = os.path.join(PLANTILLAS, plantilla)
        destino = os.path.join(carpeta, nombre_salida)
        if tipo == "mtd":
            mapa, casillas = mapa_mtd(datos, cfg, preset, calc)
        elif tipo == "anexo_ive":
            mapa, casillas = mapa_anexo_ive(datos, cfg, preset, calc)
        elif tipo == "unifilar":
            mapa, casillas = mapa_unifilar(datos, cfg, preset, calc)
        elif tipo == "solicitud":
            mapa, casillas = mapa_solicitud(datos, cfg)
        elif tipo == "autorizacion":
            mapa, casillas = mapa_autorizacion(datos, cfg)
        else:
            mapa, casillas = mapa_anexo_garaje(datos, cfg)
        mapa, casillas = aplicar_extras(mapa, casillas,
                                        (cfg.get("extras") or {}).get(plantilla))
        pistas = PISTAS_ANEXO_GARAJE if tipo == "anexo_garaje" else None
        try:
            escritos, faltan = rellenar_pdf(origen, mapa, destino, casillas,
                                            cfg, pistas, quitar,
                                            aplanar and aplanar_mtd)
            resultado["documentos"].append(
                {"nombre": nombre_salida, "ok": True, "campos": escritos})
            if faltan:
                resultado["avisos"].append(
                    f"{nombre_salida}: no encontre los campos {', '.join(faltan[:6])}"
                    + (" ..." if len(faltan) > 6 else ""))
        except Exception as exc:  # noqa: BLE001
            resultado["documentos"].append(
                {"nombre": nombre_salida, "ok": False, "error": str(exc)})

    ok_cie, estado_cie, rutas = generar_cie(datos, cfg, preset, calc, carpeta)
    resultado["documentos"].append({
        "nombre": "CIE - Certificado de Instalacion Electrica",
        "ok": ok_cie,
        "estado": estado_cie,
    })
    if estado_cie and "COMPLET" not in estado_cie.upper():
        resultado["avisos"].append(
            f"El CIE sale como «{estado_cie}». Abre CIE.xls y mira que celdas "
            "siguen marcadas como FALTAN DATOS.")
    if not ok_cie and estado_cie:
        resultado["avisos"].append(estado_cie)

    # Copia de los datos, para reabrir el expediente o rehacerlo
    with open(os.path.join(carpeta, "datos.json"), "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2)

    # La libreta de codigos postales aprende de este expediente
    aprender_codigo_postal(datos, cfg)

    return resultado


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as fh:
        print(json.dumps(generar(json.load(fh)), ensure_ascii=False, indent=2))
