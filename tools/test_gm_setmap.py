"""/setmap <nombre> <stage> [x] [y]: manda a otro jugador a un mapa y casilla, este o no
conectado. Pedido por el usuario: antes no habia forma de mover a un jugador OFFLINE."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import cuentas
import gm


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(cuentas, 'DB_PATH', tmp_path / 'cuentas.db')
    monkeypatch.setattr(cuentas, 'ARCHIVO', tmp_path / 'cuentas.json')
    cuentas._init_db()


def _crear_offline(nombre, stage=41, tx=150, ty=100):
    ficha = {'nombre': nombre, 'ranura': 0, 'habilidades': [], 'barra': [], 'quests': [],
            'stage_id': stage, 'tile_x': tx, 'tile_y': ty, 'inventario': {}}
    cuentas.guardar_personaje_nuevo('u_' + nombre.lower(), ficha)


def test_el_parser_entiende_el_comando():
    assert gm.parsear('setmap Karma 41') == ('setmap', 'Karma', 41, None, None)
    assert gm.parsear('setmap Karma 900 24 62') == ('setmap', 'Karma', 900, 24, 62)
    assert gm.parsear('setmap') == ('err', 'usage: /setmap <name> <stage> [x] [y]')
    assert gm.parsear('setmap Karma noesnumero') == (
        'err', 'usage: /setmap <name> <stage> [x] [y]  (stage/x/y son numeros)')


def test_no_se_puede_mandar_a_todo_el_mundo_de_una(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    gm_ses = NS(personaje=NS(nombre='GM'))
    for quien in ('all', 'ALL', 'todos'):
        msg = gm.cambiar_mapa_jugador(gm_ses, quien, 41)
        assert 'un jugador a la vez' in msg


def test_mueve_a_un_jugador_offline(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    _crear_offline('Karma', stage=41, tx=150, ty=100)
    monkeypatch.setattr(gm, '_app', lambda: NS(_tw_sesiones=lambda: []))
    gm_ses = NS(personaje=NS(nombre='GM'), enviar=lambda *a: None)
    msg = gm.cambiar_mapa_jugador(gm_ses, 'karma', 900, 24, 62)  # NOCASE: 'karma' encuentra a 'Karma'
    assert 'offline' in msg and 'stage 900' in msg
    usuario, char_id, datos = cuentas.personaje_por_nombre('Karma')
    assert (datos['stage_id'], datos['tile_x'], datos['tile_y']) == (900, 24, 62)


def test_quien_no_existe_da_error(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(gm, '_app', lambda: NS(_tw_sesiones=lambda: []))
    gm_ses = NS(personaje=NS(nombre='GM'))
    assert gm.cambiar_mapa_jugador(gm_ses, 'NoExiste', 41) == 'character not found: NoExiste'


def test_mueve_a_un_jugador_conectado_y_lo_avisa():
    enviados_jugador, enviados_gm, viajes, guardados = [], [], [], []

    def _sincronizar(ses, stage, x, y):
        viajes.append((ses.personaje.nombre, stage, x, y))
        ses.personaje.stage, ses.personaje.tile_x, ses.personaje.tile_y = stage, x, y

    jugador = NS(personaje=NS(nombre='Karma', char_id=7, tile_x=150, tile_y=100, stage=41),
                usuario='u7', enviar=lambda *a: enviados_jugador.extend(a))
    gm_ses = NS(personaje=NS(nombre='GM'), enviar=lambda *a: enviados_gm.extend(a))

    fake_app = NS(_tw_sesiones=lambda: [jugador], _sincronizar_cambio_mapa=_sincronizar)
    import unittest.mock
    with unittest.mock.patch.object(gm, '_app', lambda: fake_app), \
         unittest.mock.patch.object(cuentas, 'guardar_mapa', lambda *a: guardados.append(a)):
        msg = gm.cambiar_mapa_jugador(gm_ses, 'Karma', 900, 24, 62)

    assert viajes == [('Karma', 900, 24, 62)]
    assert jugador.personaje.stage == 900 and (jugador.personaje.tile_x, jugador.personaje.tile_y) == (24, 62)
    assert guardados == [('u7', 7, 900, 24, 62)]
    assert enviados_jugador  # se le aviso al jugador
    assert 'online' in msg and 'stage 900' in msg


def test_sin_casilla_se_queda_en_la_que_tenia(tmp_path, monkeypatch):
    """Sin x/y, la casilla actual del jugador se conserva (ajustada si en el mapa nuevo
    no se pisa)."""
    _db(tmp_path, monkeypatch)
    import transitable
    monkeypatch.setattr(transitable, 'conocido', lambda stage: False)  # mapa sin datos: se confia tal cual
    _crear_offline('Karma', stage=41, tx=150, ty=100)
    monkeypatch.setattr(gm, '_app', lambda: NS(_tw_sesiones=lambda: []))
    gm_ses = NS(personaje=NS(nombre='GM'))
    gm.cambiar_mapa_jugador(gm_ses, 'Karma', 900)
    _, _, datos = cuentas.personaje_por_nombre('Karma')
    assert (datos['stage_id'], datos['tile_x'], datos['tile_y']) == (900, 150, 100)
