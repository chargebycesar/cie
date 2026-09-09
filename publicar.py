# -*- coding: utf-8 -*-
"""
Sube la aplicacion a GitHub y la publica.

Se ejecuta con doble clic en publicar.bat. Hace lo mismo la primera vez y las
siguientes: la primera prepara el repositorio y pregunta lo que hace falta, las
demas solo sube lo que hayas cambiado.

Antes de subir nada comprueba que no se cuela ningun dato personal. Si aparece
alguno, se para y no sube: el repositorio es publico y lo que se sube una vez se
queda en el historial aunque luego lo borres.
"""

import io
import os
import re
import subprocess
import sys
import webbrowser
from datetime import date

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(RAIZ, "herramientas"))

# Ficheros que nunca deben acabar en el repositorio, pase lo que pase con el
# .gitignore. Son la ultima red: si alguno aparece, no se sube nada.
PROHIBIDOS = {"config.json", "prueba.json"}

ANCHO = 68


def titulo(texto):
    print()
    print("  " + texto)
    print("  " + "-" * min(len(texto), ANCHO))


def aviso(texto):
    print()
    for linea in texto.strip().splitlines():
        print("  " + linea.strip())


def preguntar(texto, defecto=""):
    pista = f" [{defecto}]" if defecto else ""
    try:
        r = input(f"  {texto}{pista}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return r or defecto


def si_o_no(texto, defecto=True):
    d = "S/n" if defecto else "s/N"
    r = preguntar(f"{texto} ({d})").lower()
    if not r:
        return defecto
    return r.startswith("s")


def git(*args, callado=False):
    """Ejecuta git y devuelve (codigo, salida)."""
    p = subprocess.run(["git"] + list(args), cwd=RAIZ,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    salida = (p.stdout or "") + (p.stderr or "")
    if not callado and p.returncode != 0:
        print(salida.rstrip())
    return p.returncode, salida.strip()


def hay_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- comprobacion

def identificadores_en(ruta, salvo):
    """Lo que parece un dato personal dentro de un fichero."""
    import rastrear

    if ruta.lower().endswith(".pdf"):
        try:
            return rastrear.restos(os.path.join(RAIZ, ruta), salvo)
        except Exception:
            return []
    try:
        texto = io.open(os.path.join(RAIZ, ruta), encoding="utf-8").read()
    except Exception:
        return []  # binario que no es PDF: no hay nada que leer
    return rastrear.identificadores(texto, salvo)


def revisar(ficheros):
    """Devuelve la lista de problemas encontrados. Vacia si todo esta bien."""
    import rastrear

    problemas = []
    for f in ficheros:
        if os.path.basename(f) in PROHIBIDOS:
            problemas.append((f, "es un fichero con tus datos y los del cliente"))

    salvo = rastrear.permitidos()
    for f in ficheros:
        if os.path.basename(f) in PROHIBIDOS:
            continue
        for x in identificadores_en(f, salvo):
            problemas.append((f, x))
    return problemas


# ------------------------------------------------------------------ el proceso

def preparar_repositorio():
    """git init la primera vez. Devuelve True si acaba de crearlo."""
    if os.path.isdir(os.path.join(RAIZ, ".git")):
        return False
    titulo("Preparando el repositorio por primera vez")
    git("init")
    git("branch", "-M", "main")
    print("  Repositorio creado en esta carpeta.")
    return True


def preparar_identidad():
    """Git necesita saber quien firma los cambios."""
    _, nombre = git("config", "user.name", callado=True)
    _, correo = git("config", "user.email", callado=True)
    if nombre and correo:
        return True

    titulo("Quien firma los cambios")
    aviso("""
        Git apunta un nombre y un correo en cada cambio. Solo se pregunta
        una vez. El correo puede ser el que uses en GitHub.
        """)
    nombre = nombre or preguntar("Tu nombre")
    correo = correo or preguntar("Tu correo")
    if not nombre or not correo:
        print()
        print("  Sin nombre ni correo no se puede continuar.")
        return False
    git("config", "--global", "user.name", nombre)
    git("config", "--global", "user.email", correo)
    return True


def preparar_destino():
    """La direccion del repositorio en GitHub. Devuelve la URL o cadena vacia."""
    codigo, url = git("remote", "get-url", "origin", callado=True)
    if codigo == 0 and url:
        return url

    titulo("A que repositorio de GitHub se sube")
    aviso("""
        Hace falta un repositorio vacio en GitHub. Se crea una sola vez:
        en github.com/new le pones un nombre (por ejemplo boletines-irve),
        lo dejas PUBLICO (las paginas gratis lo exigen) y NO marcas
        ninguna casilla de anadir README, .gitignore ni licencia.
        """)
    if si_o_no("Abro github.com/new en el navegador?"):
        webbrowser.open("https://github.com/new")
        print("  Cuando lo tengas creado, copia la direccion que te da.")

    for intento in range(3):
        print()
        url = preguntar("Pega aqui la direccion "
                        "(https://github.com/usuario/repo)")
        if not url:
            return ""
        if not pagina_de(url):
            print("  Eso no parece una direccion de GitHub. Tiene que ser algo")
            print("  como https://github.com/tu-usuario/boletines-irve")
            continue
        if not url.endswith(".git"):
            url += ".git"
        git("remote", "add", "origin", url)
        return url
    return ""


def pagina_de(url):
    """De https://github.com/usuario/repo.git a la direccion de la web."""
    m = re.search(r"github\.com[/:]([^/]+)/(.+?)(?:\.git)?/?$", url)
    if not m:
        return ""
    return f"https://{m.group(1)}.github.io/{m.group(2)}/"


def main():
    os.chdir(RAIZ)
    print()
    print("  " + "=" * ANCHO)
    print("  PUBLICAR BOLETINES IRVE EN GITHUB")
    print("  " + "=" * ANCHO)

    if not hay_git():
        aviso("""
            No encuentro Git en este ordenador.
            Instalalo desde https://git-scm.com/download/win y vuelve a
            ejecutar este fichero. Vale con darle a Siguiente a todo.
            """)
        return 1

    primera_vez = preparar_repositorio()
    if not preparar_identidad():
        return 1

    # --- que ha cambiado
    titulo("Mirando que ha cambiado")
    git("add", "-A")
    _, listado = git("diff", "--cached", "--name-only")
    ficheros = [f for f in listado.splitlines() if f.strip()]
    if not ficheros:
        print("  No hay nada nuevo que subir. Todo esta ya publicado.")
        return 0
    print(f"  {len(ficheros)} ficheros para subir.")
    for f in ficheros[:12]:
        print(f"     {f}")
    if len(ficheros) > 12:
        print(f"     ... y {len(ficheros) - 12} mas")

    # --- la comprobacion que importa
    titulo("Comprobando que no se cuela ningun dato personal")
    problemas = revisar(ficheros)
    if problemas:
        git("reset", callado=True)
        aviso("""
            NO SE HA SUBIDO NADA.

            Hay datos personales en lo que ibas a publicar. El repositorio
            es publico y lo que se sube se queda en el historial aunque
            luego lo borres, asi que esto se para aqui.
            """)
        print()
        for f, x in problemas[:20]:
            print(f"     {f:<44} {x}")
        if len(problemas) > 20:
            print(f"     ... y {len(problemas) - 20} mas")
        aviso("""
            Si son restos de un trabajo anterior dentro de los impresos:
                python herramientas/limpiar_plantillas.py

            Si es un fichero tuyo que no debe subirse, anadelo al
            .gitignore y vuelve a intentarlo.
            """)
        return 1
    print("  Limpio: ni un DNI, CIF, CUPS, correo ni movil que no toque.")

    # --- a donde se sube
    url = preparar_destino()
    if not url:
        git("reset", callado=True)
        print()
        print("  Sin direccion de repositorio no se puede subir. No se ha")
        print("  subido nada; tus cambios siguen aqui, intactos.")
        return 1

    # --- subir
    titulo("Subiendo")
    if primera_vez:
        mensaje = "Boletines IRVE: primera version"
    else:
        mensaje = preguntar("Que has cambiado",
                            f"Cambios del {date.today():%d/%m/%Y}")
    codigo, _ = git("commit", "-m", mensaje)
    if codigo != 0:
        return 1

    print("  Se abrira el navegador para que entres en tu cuenta de GitHub")
    print("  si es la primera vez. Un momento...")
    print()
    codigo, salida = git("push", "-u", "origin", "main")
    if codigo != 0:
        if primera_vez:
            # Si la direccion estaba mal, que la vuelva a pedir la proxima vez
            git("remote", "remove", "origin", callado=True)
        aviso("""
            El envio ha fallado. Lo de arriba dice por que. Lo mas normal:

            - La direccion estaba mal, o el repositorio de GitHub no esta
              vacio. Crea uno nuevo sin marcar ninguna casilla.
            - No has entrado en tu cuenta. Vuelve a ejecutar esto y
              completa lo que te pida el navegador.

            Tus cambios estan guardados aqui: no se ha perdido nada.
            """)
        return 1

    # --- listo
    web = pagina_de(url)
    titulo("Subido")
    if primera_vez:
        aviso(f"""
            Falta encender la pagina, y esto solo se hace una vez:

            1. Entra en {url[:-4] if url.endswith('.git') else url}
            2. Settings, y en el menu de la izquierda, Pages
            3. En Source elige "Deploy from a branch"
            4. Rama: main    Carpeta: /docs
            5. Save

            En un par de minutos estara en:
                {web or "https://TU-USUARIO.github.io/TU-REPOSITORIO/"}
            """)
    else:
        aviso(f"""
            Ya esta publicado. GitHub tarda un par de minutos en
            actualizar la pagina:
                {web or url}
            """)
    return 0


if __name__ == "__main__":
    try:
        salida = main()
    except KeyboardInterrupt:
        print()
        print("  Cancelado. No se ha subido nada.")
        salida = 1
    print()
    sys.exit(salida)
