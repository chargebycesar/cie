# -*- coding: utf-8 -*-
"""
Servidor local de la aplicacion de boletines IRVE.

Arranca en http://localhost:8123 y no sale de tu ordenador: no hay nube, no hay
cuentas y los datos de los clientes se quedan en la carpeta salida/.
"""

import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import nucleo

PUERTO = 8123
RAIZ = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(RAIZ, "web")

TIPOS = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *args):
        if "/api/" in str(args[0] if args else ""):
            sys.stderr.write("  %s\n" % (formato % args))

    # ---------------- utilidades de respuesta ----------------

    def _enviar(self, cuerpo, tipo="application/json; charset=utf-8", codigo=200):
        if isinstance(cuerpo, str):
            cuerpo = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, obj, codigo=200):
        self._enviar(json.dumps(obj, ensure_ascii=False), codigo=codigo)

    def _leer_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    # ---------------- rutas ----------------

    def do_GET(self):
        ruta = self.path.split("?", 1)[0]

        if ruta == "/api/config":
            cfg = nucleo.cargar_config()
            cfg["_expedientes"] = self._listar_expedientes()
            return self._json(cfg)

        if ruta.startswith("/api/expediente/"):
            nombre = ruta.split("/api/expediente/", 1)[1]
            destino = os.path.join(nucleo.SALIDA, nombre, "datos.json")
            if not os.path.isfile(destino):
                return self._json({"error": "No encuentro ese expediente"}, 404)
            with open(destino, encoding="utf-8") as fh:
                return self._json(json.load(fh))

        if ruta == "/":
            ruta = "/index.html"
        archivo = os.path.normpath(os.path.join(WEB, ruta.lstrip("/")))
        if not archivo.startswith(WEB) or not os.path.isfile(archivo):
            return self._enviar("No encontrado", "text/plain; charset=utf-8", 404)
        ext = os.path.splitext(archivo)[1].lower()
        with open(archivo, "rb") as fh:
            self._enviar(fh.read(), TIPOS.get(ext, "application/octet-stream"))

    def do_POST(self):
        ruta = self.path.split("?", 1)[0]
        try:
            cuerpo = self._leer_json()
        except (ValueError, UnicodeDecodeError) as exc:
            return self._json({"error": f"Peticion mal formada: {exc}"}, 400)

        if ruta == "/api/generar":
            try:
                return self._json(nucleo.generar(cuerpo))
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                return self._json({"error": str(exc)}, 500)

        if ruta == "/api/config":
            try:
                nucleo.guardar_config(cuerpo)
                return self._json({"ok": True})
            except Exception as exc:  # noqa: BLE001
                return self._json({"error": str(exc)}, 500)

        if ruta == "/api/abrir":
            carpeta = cuerpo.get("carpeta", nucleo.SALIDA)
            if os.path.isdir(carpeta):
                subprocess.Popen(["explorer", os.path.normpath(carpeta)])
                return self._json({"ok": True})
            return self._json({"error": "Esa carpeta no existe"}, 404)

        return self._json({"error": "Ruta desconocida"}, 404)

    # ---------------- ayudas ----------------

    @staticmethod
    def _listar_expedientes():
        if not os.path.isdir(nucleo.SALIDA):
            return []
        nombres = []
        for n in sorted(os.listdir(nucleo.SALIDA), reverse=True):
            if os.path.isfile(os.path.join(nucleo.SALIDA, n, "datos.json")):
                nombres.append(n)
        return nombres[:40]


class Servidor(ThreadingHTTPServer):
    # En Windows, con allow_reuse_address dos procesos pueden quedarse
    # escuchando en el mismo puerto y gana el mas antiguo, asi que abrir la
    # aplicacion dos veces dejaria una copia vieja atendiendo sin avisar.
    allow_reuse_address = False
    daemon_threads = True


def main():
    os.makedirs(nucleo.SALIDA, exist_ok=True)
    try:
        servidor = Servidor(("127.0.0.1", PUERTO), Manejador)
    except OSError:
        print("=" * 62)
        print("  La aplicacion ya esta abierta en otra ventana.")
        print(f"  Ve a http://localhost:{PUERTO}/ o cierra la otra ventana negra.")
        print("=" * 62)
        webbrowser.open(f"http://localhost:{PUERTO}/")
        return
    url = f"http://localhost:{PUERTO}/"
    print("=" * 62)
    print("  Boletines IRVE - Comunidad de Madrid")
    print(f"  Abriendo {url}")
    print("  Para cerrar la aplicacion, cierra esta ventana negra.")
    print("=" * 62)
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nHasta luego.")


if __name__ == "__main__":
    main()
