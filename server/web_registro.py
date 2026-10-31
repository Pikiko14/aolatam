"""Servidor HTTP chico para la web: comprobar nombres de cuenta y crear cuentas con su contrasena.

LA CONTRASENA DE LA WEB ES LA DEL JUEGO. El cliente manda la suya cifrada con Blowfish y una clave fija
(server/clave_cliente.py, descifrado el 31/10/2026); el servidor la descifra y la compara con el PBKDF2 que
se guarda aqui al crear la cuenta (cuentas.contrasena_hash). Antes no se sabia descifrar y la web solo
reservaba el nombre: la contrasena quedaba fijada en el primer ingreso del juego.

Expone, solo en 127.0.0.1 (nginx hace de proxy_pass en /api/cuenta/*):

    GET  /api/cuenta/disponible?usuario=X      -> {"disponible": true/false, "motivo": "..."}
    POST /api/cuenta/registrar {"usuario": X, "password": P, "confirmar": P}  -> {"ok": true/false, "mensaje": "..."}

    python server/web_registro.py            # puerto 8281 (AO_WEB_REGISTRO_PUERTO lo cambia)
"""
import json
import logging
import os
import pathlib
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import cuentas

log = logging.getLogger('web_registro')

PUERTO = int(os.environ.get('AO_WEB_REGISTRO_PUERTO', '8281'))
USUARIO_VALIDO = re.compile(r'^[A-Za-z][A-Za-z0-9_]{3,15}$')


# Lo que el cliente de Windows puede mandar: ASCII visible sin espacios (clave_cliente.contrasena), y su campo
# de contrasena no admite mas de 16.
CONTRASENA_VALIDA = re.compile(r'^[\x21-\x7e]{4,16}$')


def _validar(usuario: str):
    if not usuario:
        return 'Escribe un nombre de usuario.'
    if not USUARIO_VALIDO.fullmatch(usuario):
        return 'De 4 a 16 caracteres: empieza por una letra y usa solo letras, numeros y guion bajo.'
    return None


def _validar_contrasena(pw: str, confirmar: str):
    if not pw:
        return 'Escribe una contraseña.'
    if not CONTRASENA_VALIDA.fullmatch(pw):
        return 'La contraseña debe tener de 4 a 16 caracteres, sin espacios ni acentos.'
    if pw != confirmar:
        return 'Las contraseñas no coinciden.'
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = 'AngelsOnlineWebRegistro/1.0'

    def log_message(self, fmt, *args):
        log.info('%s - %s', self.address_string(), fmt % args)

    def _json(self, codigo: int, cuerpo: dict):
        datos = json.dumps(cuerpo, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(datos)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(datos)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        ruta = urlsplit(self.path)
        if ruta.path != '/api/cuenta/disponible':
            return self._json(404, {'error': 'no encontrado'})
        usuario = (parse_qs(ruta.query).get('usuario') or [''])[0].strip()
        error = _validar(usuario)
        if error:
            return self._json(200, {'disponible': False, 'motivo': error})
        libre = cuentas.usuario_disponible(usuario)
        self._json(200, {'disponible': libre, 'motivo': '' if libre else 'Ese usuario ya existe.'})

    def do_POST(self):
        ruta = urlsplit(self.path)
        if ruta.path != '/api/cuenta/registrar':
            return self._json(404, {'error': 'no encontrado'})
        largo = int(self.headers.get('Content-Length') or 0)
        if largo <= 0 or largo > 4096:
            return self._json(400, {'ok': False, 'mensaje': 'Peticion invalida.'})
        try:
            cuerpo = json.loads(self.rfile.read(largo).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {'ok': False, 'mensaje': 'Peticion invalida.'})
        usuario = str(cuerpo.get('usuario', '')).strip()
        pw, confirmar = str(cuerpo.get('password', '')), str(cuerpo.get('confirmar', ''))
        error = _validar(usuario) or _validar_contrasena(pw, confirmar)
        if error:
            return self._json(200, {'ok': False, 'mensaje': error})
        nuevo = cuentas.reservar_usuario(usuario, pw)
        if not nuevo:
            return self._json(200, {'ok': False, 'mensaje': 'Ese usuario ya existe. Prueba con otro.'})
        log.info('cuenta creada desde la web: %s', usuario)
        self._json(200, {'ok': True, 'mensaje':
                         '¡Cuenta "%s" creada! Descarga el juego y entra con tu usuario y tu contraseña.' % usuario})


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    srv = ThreadingHTTPServer(('127.0.0.1', PUERTO), Handler)
    log.info('escuchando en 127.0.0.1:%d (pensado para un proxy_pass de nginx en /api/cuenta/)', PUERTO)
    srv.serve_forever()


if __name__ == '__main__':
    main()
