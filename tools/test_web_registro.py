"""Pruebas de cuentas.usuario_disponible / reservar_usuario y de server/web_registro.py (sin red: llama al Handler directo)."""
import importlib
import io
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))


def test_reservar_usuario_y_disponibilidad(tmp_path, monkeypatch):
    import cuentas
    monkeypatch.setattr(cuentas, 'DB_PATH', tmp_path / 'cuentas.db')
    monkeypatch.setattr(cuentas, 'ARCHIVO', tmp_path / 'cuentas.json')
    cuentas._init_db()
    assert cuentas.usuario_disponible('HeroeDePrueba')
    assert cuentas.reservar_usuario('HeroeDePrueba') is True
    assert not cuentas.usuario_disponible('heroedeprueba')          # NOCASE: coincide con 'HeroeDePrueba'
    assert cuentas.reservar_usuario('heroedeprueba') is False        # ya existia
    # el login real pisa la fila vacia sin problema (mismo mecanismo que ya usa validar())
    datos, motivo = cuentas.validar('heroedeprueba', b'\x00' * 73)
    assert "'heroedeprueba' creada" in motivo or motivo == 'ok' or 'registrada' in motivo


def test_validar_usuario_del_servidor_web():
    import web_registro
    assert web_registro._validar('') == 'Escribe un nombre de usuario.'
    assert web_registro._validar('ab') is not None            # muy corto
    assert web_registro._validar('1abc') is not None           # no empieza por letra
    assert web_registro._validar('abc def') is not None        # espacio
    assert web_registro._validar('Karma_2') is None


class _Peticion:
    """Falsea lo que BaseHTTPRequestHandler.__init__ necesita, sin abrir sockets."""
    def __init__(self, metodo, ruta, cuerpo=b''):
        self.metodo, self.ruta, self.cuerpo = metodo, ruta, cuerpo

    def makefile(self, modo, *a, **k):
        if 'r' in modo:
            linea = f'{self.metodo} {self.ruta} HTTP/1.1\r\n'
            cabeceras = f'Content-Length: {len(self.cuerpo)}\r\n\r\n' if self.cuerpo else '\r\n'
            return io.BytesIO((linea + cabeceras).encode() + self.cuerpo)
        return io.BytesIO()


def _llamar(monkeypatch, tmp_path, metodo, ruta, cuerpo=b''):
    import cuentas
    import web_registro
    monkeypatch.setattr(cuentas, 'DB_PATH', tmp_path / 'cuentas.db')
    monkeypatch.setattr(cuentas, 'ARCHIVO', tmp_path / 'cuentas.json')
    cuentas._init_db()
    peticion = _Peticion(metodo, ruta, cuerpo)
    h = web_registro.Handler.__new__(web_registro.Handler)
    h.rfile = peticion.makefile('rb')
    h.wfile = io.BytesIO()
    h.client_address = ('127.0.0.1', 0)
    h.raw_requestline = h.rfile.readline()
    h.parse_request()
    getattr(h, 'do_' + metodo)()
    h.wfile.seek(0)
    resp = h.wfile.read().decode()
    cuerpo_resp = resp.split('\r\n\r\n', 1)[1]
    return json.loads(cuerpo_resp)


def test_endpoint_disponible(tmp_path, monkeypatch):
    r = _llamar(monkeypatch, tmp_path, 'GET', '/api/cuenta/disponible?usuario=NuevoHeroe')
    assert r == {'disponible': True, 'motivo': ''}
    r2 = _llamar(monkeypatch, tmp_path, 'GET', '/api/cuenta/disponible?usuario=a')
    assert r2['disponible'] is False and r2['motivo']


def test_endpoint_registrar(tmp_path, monkeypatch):
    cuerpo = json.dumps({'usuario': 'NuevoHeroe'}).encode()
    r = _llamar(monkeypatch, tmp_path, 'POST', '/api/cuenta/registrar', cuerpo)
    assert r['ok'] is True and 'NuevoHeroe' in r['mensaje']
    r2 = _llamar(monkeypatch, tmp_path, 'POST', '/api/cuenta/registrar', cuerpo)
    assert r2['ok'] is False
