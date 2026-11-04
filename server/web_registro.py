"""Servidor HTTP chico para la web: comprobar nombres de cuenta y crear cuentas con su contrasena.

LA CONTRASENA DE LA WEB ES LA DEL JUEGO. El cliente manda la suya cifrada con Blowfish y una clave fija
(server/clave_cliente.py, descifrado el 31/10/2026); el servidor la descifra y la compara con el PBKDF2 que
se guarda aqui al crear la cuenta (cuentas.contrasena_hash). Antes no se sabia descifrar y la web solo
reservaba el nombre: la contrasena quedaba fijada en el primer ingreso del juego.

Expone, solo en 127.0.0.1 (nginx hace de proxy_pass en /api/cuenta/*):

    GET  /api/cuenta/disponible?usuario=X[&lang=es]      -> {"disponible": true/false, "motivo": "..."}
    POST /api/cuenta/registrar {"usuario": X, "password": P, "confirmar": P[, "lang": "es"]}  -> {"ok": true/false, "mensaje": "..."}

La web es bilingue (tools/web_sitio/i18n.js): los mensajes salen en ingles, o en espanol con lang=es.

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


# (ingles, espanol)
MENSAJES = {
    'sin_usuario': ('Enter a username.', 'Escribe un nombre de usuario.'),
    'usuario_malo': ('4 to 16 characters: start with a letter and use only letters, numbers and underscores.',
                     'De 4 a 16 caracteres: empieza por una letra y usa solo letras, números y guion bajo.'),
    'sin_contrasena': ('Enter a password.', 'Escribe una contraseña.'),
    'contrasena_mala': ('The password must be 4 to 16 characters, with no spaces or accented letters.',
                        'La contraseña debe tener de 4 a 16 caracteres, sin espacios ni acentos.'),
    'no_coinciden': ("The passwords don't match.", 'Las contraseñas no coinciden.'),
    'ocupado': ('That username is already taken.', 'Ese usuario ya existe.'),
    'ocupado_otro': ('That username is already taken. Try another one.', 'Ese usuario ya existe. Prueba con otro.'),
    'invalida': ('Invalid request.', 'Petición inválida.'),
    'creada': ('Account "%s" created! Download the game and log in with your username and password.',
               '¡Cuenta "%s" creada! Descarga el juego y entra con tu usuario y tu contraseña.'),
}


def _msg(clave: str, lang: str = 'en') -> str:
    return MENSAJES[clave][1 if lang == 'es' else 0]


def _validar(usuario: str, lang: str = 'en'):
    if not usuario:
        return _msg('sin_usuario', lang)
    if not USUARIO_VALIDO.fullmatch(usuario):
        return _msg('usuario_malo', lang)
    return None


def _validar_contrasena(pw: str, confirmar: str, lang: str = 'en'):
    if not pw:
        return _msg('sin_contrasena', lang)
    if not CONTRASENA_VALIDA.fullmatch(pw):
        return _msg('contrasena_mala', lang)
    if pw != confirmar:
        return _msg('no_coinciden', lang)
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
        consulta = parse_qs(ruta.query)
        usuario = (consulta.get('usuario') or [''])[0].strip()
        lang = (consulta.get('lang') or ['en'])[0]
        error = _validar(usuario, lang)
        if error:
            return self._json(200, {'disponible': False, 'motivo': error})
        libre = cuentas.usuario_disponible(usuario)
        self._json(200, {'disponible': libre, 'motivo': '' if libre else _msg('ocupado', lang)})

    def do_POST(self):
        ruta = urlsplit(self.path)
        if ruta.path != '/api/cuenta/registrar':
            return self._json(404, {'error': 'no encontrado'})
        largo = int(self.headers.get('Content-Length') or 0)
        if largo <= 0 or largo > 4096:
            return self._json(400, {'ok': False, 'mensaje': _msg('invalida')})
        try:
            cuerpo = json.loads(self.rfile.read(largo).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {'ok': False, 'mensaje': _msg('invalida')})
        if not isinstance(cuerpo, dict):
            return self._json(400, {'ok': False, 'mensaje': _msg('invalida')})
        lang = str(cuerpo.get('lang', 'en'))
        usuario = str(cuerpo.get('usuario', '')).strip()
        pw, confirmar = str(cuerpo.get('password', '')), str(cuerpo.get('confirmar', ''))
        error = _validar(usuario, lang) or _validar_contrasena(pw, confirmar, lang)
        if error:
            return self._json(200, {'ok': False, 'mensaje': error})
        nuevo = cuentas.reservar_usuario(usuario, pw)
        if not nuevo:
            return self._json(200, {'ok': False, 'mensaje': _msg('ocupado_otro', lang)})
        log.info('cuenta creada desde la web: %s', usuario)
        self._json(200, {'ok': True, 'mensaje': _msg('creada', lang) % usuario})


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    srv = ThreadingHTTPServer(('127.0.0.1', PUERTO), Handler)
    log.info('escuchando en 127.0.0.1:%d (pensado para un proxy_pass de nginx en /api/cuenta/)', PUERTO)
    srv.serve_forever()


if __name__ == '__main__':
    main()
