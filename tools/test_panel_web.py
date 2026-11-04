"""Back office de la web (server/panel_web.py), llamando al Handler de web_registro sin red."""
import io
import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))


class _Peticion:
    def __init__(self, metodo, ruta, cuerpo=b'', cabeceras=None):
        self.metodo, self.ruta, self.cuerpo, self.cabeceras = metodo, ruta, cuerpo, cabeceras or {}

    def makefile(self, modo, *a, **k):
        if 'r' not in modo:
            return io.BytesIO()
        cab = dict(self.cabeceras)
        if self.cuerpo:
            cab['Content-Length'] = str(len(self.cuerpo))
        texto = '%s %s HTTP/1.1\r\n' % (self.metodo, self.ruta) + ''.join('%s: %s\r\n' % kv for kv in cab.items()) + '\r\n'
        return io.BytesIO(texto.encode() + self.cuerpo)


@pytest.fixture
def web(tmp_path, monkeypatch):
    import cuentas
    import configuracion
    import panel_web
    import web_registro
    monkeypatch.setattr(cuentas, 'DB_PATH', tmp_path / 'cuentas.db')
    monkeypatch.setattr(cuentas, 'ARCHIVO', tmp_path / 'cuentas.json')
    monkeypatch.setattr(configuracion, 'USUARIOS_GM', frozenset({'elgm'}))
    cuentas._init_db()
    panel_web._SESIONES.clear()
    panel_web._FALLOS.clear()
    cuentas.reservar_usuario('Jugador1', 'clave1')
    cuentas.reservar_usuario('ElGM', 'clavegm')

    def llamar(metodo, ruta, datos=None, cookie=None, origen='https://aoforever.tech', ip='1.2.3.4'):
        cab = {'Host': 'aoforever.tech', 'X-Real-IP': ip}
        if cookie:
            cab['Cookie'] = cookie
        cuerpo = b''
        if datos is not None:
            cuerpo = json.dumps(datos).encode()
            cab['Content-Type'] = 'application/json'
            if origen:
                cab['Origin'] = origen
        p = _Peticion(metodo, ruta, cuerpo, cab)
        h = web_registro.Handler.__new__(web_registro.Handler)
        h.rfile, h.wfile = p.makefile('rb'), io.BytesIO()
        h.client_address = ('127.0.0.1', 0)
        h.raw_requestline = h.rfile.readline()
        h.parse_request()
        getattr(h, 'do_' + metodo)()
        crudo = h.wfile.getvalue().decode()
        cabeza, _, resto = crudo.partition('\r\n\r\n')
        codigo = int(cabeza.split()[1])
        galleta = next((l.split(':', 1)[1].strip() for l in cabeza.split('\r\n') if l.lower().startswith('set-cookie:')), None)
        return codigo, json.loads(resto), galleta

    def entrar(usuario, pw):
        codigo, r, galleta = llamar('POST', '/api/panel/login', {'usuario': usuario, 'password': pw})
        assert r['ok'], r
        assert 'HttpOnly' in galleta and 'Secure' in galleta and 'SameSite=Strict' in galleta
        return galleta.split(';')[0]

    return type('W', (), {'llamar': staticmethod(llamar), 'entrar': staticmethod(entrar)})


def test_login_y_mis_datos(web):
    cookie = web.entrar('jugador1', 'clave1')            # el usuario es NOCASE
    codigo, r, _ = web.llamar('GET', '/api/panel/yo', cookie=cookie)
    assert codigo == 200 and r['usuario'] == 'Jugador1' and r['admin'] is False
    assert isinstance(r['ag'], int) and r['personajes'] == []


def test_contrasena_mala_y_sin_sesion(web):
    _, r, galleta = web.llamar('POST', '/api/panel/login', {'usuario': 'Jugador1', 'password': 'otra', 'lang': 'es'})
    assert r['ok'] is False and r['mensaje'] == 'Usuario o contraseña incorrectos.' and galleta is None
    codigo, r, _ = web.llamar('GET', '/api/panel/yo')
    assert codigo == 401


def test_freno_de_intentos(web):
    for _ in range(5):
        web.llamar('POST', '/api/panel/login', {'usuario': 'Jugador1', 'password': 'mal'})
    _, r, _ = web.llamar('POST', '/api/panel/login', {'usuario': 'Jugador1', 'password': 'clave1'})
    assert r['ok'] is False and 'Too many' in r['mensaje']


def test_post_sin_origen_del_sitio_se_rechaza(web):
    codigo, r, _ = web.llamar('POST', '/api/panel/login', {'usuario': 'Jugador1', 'password': 'clave1'},
                              origen='https://malo.example')
    assert codigo == 403 and r['ok'] is False


def test_cambiar_mi_contrasena(web):
    import cuentas
    cookie = web.entrar('Jugador1', 'clave1')
    _, r, _ = web.llamar('POST', '/api/panel/contrasena', {'actual': 'mal', 'nueva': 'nueva1', 'confirmar': 'nueva1'}, cookie)
    assert r['ok'] is False
    _, r, _ = web.llamar('POST', '/api/panel/contrasena', {'actual': 'clave1', 'nueva': 'nueva1', 'confirmar': 'nueva1'}, cookie)
    assert r['ok'] is True
    guardado = cuentas._get_conn().execute("SELECT password FROM cuentas WHERE usuario='Jugador1'").fetchone()[0]
    assert cuentas.contrasena_ok(guardado, 'nueva1')     # la misma que valida el juego


def test_un_jugador_no_usa_el_admin(web):
    cookie = web.entrar('Jugador1', 'clave1')
    codigo, r, _ = web.llamar('POST', '/api/panel/admin/ag', {'usuario': 'Jugador1', 'cantidad': 999999}, cookie)
    assert codigo == 403 and r['ok'] is False


def test_admin_da_y_quita_ag_con_auditoria(web):
    import cuentas
    import item_mall
    cookie = web.entrar('ElGM', 'clavegm')
    antes = item_mall.saldo('Jugador1')
    _, r, _ = web.llamar('POST', '/api/panel/admin/ag', {'usuario': 'jugador1', 'cantidad': 5000, 'motivo': 'premio'}, cookie)
    assert r['ok'] and r['ag'] == antes + 5000 == item_mall.saldo('Jugador1')
    _, r, _ = web.llamar('POST', '/api/panel/admin/ag', {'usuario': 'Jugador1', 'cantidad': -(antes + 10**9)}, cookie)
    assert r['ok'] is False and item_mall.saldo('Jugador1') == antes + 5000      # no deja saldo negativo
    con = cuentas._get_conn()
    fila = con.execute("SELECT admin, accion, objetivo, detalle FROM panel_auditoria").fetchone()
    assert fila[:3] == ('ElGM', 'ag', 'Jugador1') and json.loads(fila[3])['cantidad'] == 5000
    assert con.execute("SELECT delta FROM item_mall_movimientos WHERE motivo='panel:ElGM'").fetchone()[0] == 5000


def test_admin_busca_por_personaje_y_resetea_contrasena(web):
    import cuentas
    cuentas.guardar_personaje_nuevo('Jugador1', {'char_id': 777, 'ranura': 0, 'nombre': 'Heroina', 'nivel': 42,
                                                 'class_id': 3, 'faction': 'Beasts', 'stage_id': 29, 'oro': 1234})
    cookie = web.entrar('ElGM', 'clavegm')
    _, r, _ = web.llamar('GET', '/api/panel/admin/cuenta?q=heroina', cookie=cookie)
    assert r['ok'] and r['usuario'] == 'Jugador1'
    pj = r['personajes'][0]
    assert (pj['nombre'], pj['nivel'], pj['faccion'], pj['oro']) == ('Heroina', 42, 'Beasts', 1234)
    _, r, _ = web.llamar('POST', '/api/panel/admin/contrasena', {'usuario': 'Jugador1', 'nueva': 'reset99'}, cookie)
    assert r['ok']
    assert web.entrar('Jugador1', 'reset99')


def test_calendario_de_eventos(web):
    _, r, _ = web.llamar('GET', '/api/panel/eventos')
    claves = {e['evento'] for e in r['eventos']}
    assert 'totem_war' in claves and 'holy' in claves
    assert all(e['inicio'] > r['ahora'] - 4 * 3600 for e in r['eventos'])


def test_banear_y_desbanear(web):
    import cuentas
    gm = web.entrar('ElGM', 'clavegm')
    jugador = web.entrar('Jugador1', 'clave1')
    _, r, _ = web.llamar('POST', '/api/panel/admin/banear', {'usuario': 'jugador1', 'dias': 7, 'motivo': 'trampas'}, gm)
    assert r['ok'] and r['baneo']['motivo'] == 'trampas' and r['baneo']['hasta']
    # fuera del panel al instante, y no puede volver a entrar
    codigo, _, _ = web.llamar('GET', '/api/panel/yo', cookie=jugador)
    assert codigo == 401
    _, r, _ = web.llamar('POST', '/api/panel/login', {'usuario': 'Jugador1', 'password': 'clave1'})
    assert r['ok'] is False and 'banned until' in r['mensaje']
    # ni al juego: validar() lo rechaza antes de mirar la contrasena
    assert cuentas.validar('Jugador1', b'\x00' * 73) == (None, 'cuenta baneada')
    _, r, _ = web.llamar('GET', '/api/panel/admin/cuenta?q=Jugador1', cookie=gm)
    assert r['baneo'] and r['baneo']['por'] == 'ElGM'
    _, r, _ = web.llamar('POST', '/api/panel/admin/desbanear', {'usuario': 'Jugador1'}, gm)
    assert r['ok']
    assert web.entrar('Jugador1', 'clave1')
    con = cuentas._get_conn()
    assert [a for (a,) in con.execute("SELECT accion FROM panel_auditoria ORDER BY id")] == ['banear', 'desbanear']


def test_baneo_temporal_vence_y_validaciones(web, monkeypatch):
    import cuentas
    import time as _t
    gm = web.entrar('ElGM', 'clavegm')
    _, r, _ = web.llamar('POST', '/api/panel/admin/banear', {'usuario': 'ElGM', 'dias': 1}, gm)
    assert r['ok'] is False                                   # a si mismo no
    _, r, _ = web.llamar('POST', '/api/panel/admin/banear', {'usuario': 'Jugador1', 'dias': 5}, gm)
    assert r['ok'] is False                                   # solo 0, 1, 3, 7 o 30 dias
    cuentas.banear('Jugador1', _t.time() - 1, 'vencido', 'ElGM')
    assert cuentas.baneo('Jugador1') is None and 'jugador1' not in cuentas.baneados()
    _, r, _ = web.llamar('POST', '/api/panel/admin/banear', {'usuario': 'Jugador1', 'dias': 0}, gm)
    assert r['ok'] and r['baneo']['hasta'] is None             # permanente
    assert 'jugador1' in cuentas.baneados()


def test_el_juego_saca_al_baneado_que_esta_dentro(web):
    import asyncio
    import cuentas
    import app
    from types import SimpleNamespace
    cerradas, avisos = [], []
    dentro = SimpleNamespace(usuario='Jugador1', addr=('x', 1), desconectado=False,
                             enviar_inmediato=lambda *p: avisos.extend(p),
                             writer=SimpleNamespace(close=lambda: cerradas.append('Jugador1')))
    otro = SimpleNamespace(usuario='ElGM', addr=('y', 2), desconectado=False, enviar_inmediato=lambda *p: None,
                           writer=SimpleNamespace(close=lambda: cerradas.append('ElGM')))
    srv = app.Servidor.__new__(app.Servidor)
    srv.mundos = [dentro, otro]
    cuentas.banear('Jugador1', None, 'x', 'ElGM')

    async def una_vuelta():
        tarea = asyncio.create_task(srv.vigilar_baneos(cada=0.01))
        await asyncio.sleep(0.05)
        tarea.cancel()
    asyncio.run(una_vuelta())
    assert 'Jugador1' in cerradas and 'ElGM' not in cerradas and avisos
