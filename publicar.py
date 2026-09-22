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

def sellar_version():
    """Cambia el ?v= de los modulos para que el navegador no reuse los viejos.

    Sin esto, despues de publicar un arreglo el navegador sigue usando la
    version que tenia guardada y el usuario no ve el cambio.
    """
    try:
        import sellar_version as sello
    except Exception as e:  # noqa: BLE001
        print(f"  No he podido sellar ({e}). Se sube igual.")
        return
    try:
        sello.main()
    except SystemExit:
        pass
    except Exception as e:  # noqa: BLE001
        print(f"  No he podido sellar ({e}). Se sube igual.")


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
    # Un correo sin arroba no es un correo: Git lo acepta, pero GitHub no puede
    # enlazar los cambios con tu cuenta y salen como de un desconocido.
    correo_vale = bool(re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", correo or ""))
    if nombre and correo_vale:
        return True

    titulo("Quien firma los cambios")
    aviso("""
        Git apunta un nombre y un correo en cada cambio. Solo se pregunta
        una vez. Pon el correo con el que entras en GitHub, para que los
        cambios salgan a tu nombre.
        """)
    if correo and not correo_vale:
        print(f"  El correo que tienes puesto, {correo!r}, no lleva arroba.")
        print()
    nombre = nombre or preguntar("Tu nombre")
    correo = preguntar("Tu correo", correo if correo_vale else "")
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


def subido_alguna_vez():
    """True si esta rama ya llego a GitHub alguna vez."""
    codigo, _ = git("rev-parse", "--verify", "origin/main", callado=True)
    return codigo == 0


def queda_por_enviar():
    """True si hay confirmaciones aqui que no estan en GitHub."""
    if not subido_alguna_vez():
        codigo, _ = git("rev-parse", "--verify", "HEAD", callado=True)
        return codigo == 0        # hay historia local y no ha salido nunca
    _, cuenta = git("rev-list", "--count", "origin/main..HEAD", callado=True)
    return cuenta.strip() not in ("", "0")


def enviar():
    """Sube la rama. Devuelve True si lo consigue.

    Si GitHub rechaza el envio porque alla ya hay cosas -lo normal la primera
    vez, porque GitHub suele crear un README-, se junta lo de alla con lo de
    aqui y se vuelve a intentar. La direccion del repositorio NO se borra salvo
    que sea ella la que esta mal: si se borrara, habria que volver a pegarla en
    cada actualizacion.
    """
    codigo, salida = git("push", "-u", "origin", "main")
    if codigo == 0:
        return True

    bajo = salida.lower()

    if "not found" in bajo or "does not appear to be a git repository" in bajo:
        git("remote", "remove", "origin", callado=True)
        aviso("""
            GitHub dice que ese repositorio no existe.

            Comprueba la direccion y vuelve a ejecutar esto: te la
            preguntara otra vez. Tus cambios estan guardados aqui.
            """)
        return False

    if "rejected" in bajo or "fetch first" in bajo or "non-fast-forward" in bajo:
        titulo("En GitHub ya habia algo")
        aviso("""
            El repositorio no estaba vacio. Suele pasar la primera vez,
            porque GitHub crea un README al montarlo. Voy a juntar lo que
            hay alla con lo de aqui y a subir otra vez.
            """)
        git("fetch", "origin", "main", callado=True)
        codigo, _ = git("merge", "origin/main", "--allow-unrelated-histories",
                        "-m", "Junta lo que ya habia en GitHub", callado=True)
        if codigo != 0:
            # Algun archivo esta en los dos sitios y no coincide
            _, chocan = git("diff", "--name-only", "--diff-filter=U", callado=True)
            aviso("""
                Hay archivos que estan en los dos sitios y no coinciden:
                """)
            for f in chocan.splitlines()[:10]:
                print(f"     {f}")
            print()
            if not si_o_no("Me quedo con la version de tu ordenador?"):
                git("merge", "--abort", callado=True)
                print()
                print("  No se ha subido nada y tu carpeta se queda como estaba.")
                return False
            git("merge", "--abort", callado=True)
            git("merge", "origin/main", "--allow-unrelated-histories", "-X", "ours",
                "-m", "Junta lo que ya habia en GitHub, mandando lo de aqui")
        codigo, _ = git("push", "-u", "origin", "main")
        if codigo == 0:
            return True

    if "403" in bajo or "denied to" in bajo or "permission to" in bajo:
        return _otra_cuenta(salida)

    aviso("""
        El envio ha fallado. Lo de arriba dice por que. Lo mas normal es
        que no hayas entrado en tu cuenta de GitHub: vuelve a ejecutar
        esto y completa lo que te pida el navegador.

        La direccion del repositorio se queda guardada, no te la volvera
        a pedir. Tus cambios estan aqui: no se ha perdido nada.
        """)
    return False


def _otra_cuenta(salida):
    """GitHub ha dicho 403: la cuenta con la que entras no es la del repositorio.

    Windows guarda UNA sola contrasena de GitHub y Git la reutiliza para todos
    los repositorios. Con dos cuentas -una para tus cosas y otra para los
    boletines de otra empresa- la segunda choca con la primera y GitHub contesta
    que no, aunque el repositorio sea tuyo.

    Se arregla metiendo el usuario dentro de la direccion. Entonces Windows
    guarda una contrasena para cada cuenta y las dos siguen funcionando, sin
    borrar nada ni tener que entrar y salir cada vez.
    """
    titulo("Esa cuenta no puede subir a ese repositorio")

    entrando = re.search(r"denied to ([^\s.]+)", salida, re.I)
    _, url = git("remote", "get-url", "origin", callado=True)
    m = re.search(r"github\.com[/:]([^/@]+)/([^/]+?)(?:\.git)?/?$", url)

    if entrando:
        print(f"  Estas entrando en GitHub como {entrando.group(1)}.")
    if m:
        print(f"  Y el repositorio es de {m.group(1)}.")
    print()
    print("  Windows guarda una sola contrasena de GitHub y Git la usa para")
    print("  todo. Si tienes dos cuentas, la primera le pisa la vez a la otra.")

    if not m:
        return False

    duenno, repo = m.group(1), m.group(2)
    nueva = f"https://{duenno}@github.com/{duenno}/{repo}.git"
    aviso(f"""
        Poniendo el usuario dentro de la direccion, Windows guarda una
        contrasena para cada cuenta y las dos te siguen funcionando:

            {nueva}

        Si vas a entrar con otra cuenta distinta que tambien tenga
        permiso, pon ese nombre en vez de {duenno}.
        """)
    if si_o_no("Lo cambio y lo intento otra vez?"):
        git("remote", "set-url", "origin", nueva)
        print()
        print("  Ahora el navegador te va a pedir entrar. Hazlo con la cuenta")
        print(f"  {duenno}, no con la otra.")
        print()
        codigo, _ = git("push", "-u", "origin", "main")
        if codigo == 0:
            return True
        aviso("""
            Sigue sin dejarte. Si el navegador no te ha llegado a preguntar,
            es que Windows ha vuelto a dar la contrasena guardada: quitala en
            Panel de control > Administrador de credenciales > Credenciales de
            Windows, la que pone git:https://github.com, y vuelve a intentarlo.

            Tus cambios estan aqui: no se ha perdido nada.
            """)
    return False


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

    preparar_repositorio()
    if not preparar_identidad():
        return 1
    # La primera vez es la primera SUBIDA, no la primera vez que se abre esto:
    # si el envio fallo, las instrucciones de encender la pagina hacen falta.
    primera_vez = not subido_alguna_vez()

    # --- sello de version, para que el navegador se baje lo nuevo
    titulo("Poniendo el sello de version")
    sellar_version()

    # --- que ha cambiado
    titulo("Mirando que ha cambiado")
    git("add", "-A")
    _, listado = git("diff", "--cached", "--name-only")
    ficheros = [f for f in listado.splitlines() if f.strip()]
    # Puede no haber nada nuevo y aun asi quedar cosas por enviar: si el envio
    # anterior fallo, el cambio esta confirmado aqui pero no ha llegado alla.
    if not ficheros and not queda_por_enviar():
        print("  No hay nada nuevo que subir. Todo esta ya publicado.")
        return 0
    if not ficheros:
        print("  No hay archivos nuevos, pero quedo un envio a medias.")
    else:
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
    if ficheros:
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
    if not enviar():
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
