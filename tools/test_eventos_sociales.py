"""Eventos sociales (25/11/2026): tesoro, cazador cazado, duelos de apuesta y votacion semanal."""
import datetime as dt
import pathlib
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import cazador  # noqa: E402
import duelos  # noqa: E402
import sociales  # noqa: E402
import tesoro_servidor as ts  # noqa: E402
import votacion  # noqa: E402

SPIKE = 6
CIUDAD = 3


def _ses(cid, nombre, stage=SPIKE, x=100, y=100, oro=100000, nivel=50):
    enviados = []
    return NS(personaje=NS(char_id=cid, nombre=nombre, nivel=nivel, stage=stage, tile_x=x, tile_y=y, entity_id=cid),
              oro=oro, enviar=lambda *p: enviados.extend(p), enviados=enviados, muerto=False)


@pytest.fixture
def mundo(monkeypatch, tmp_path):
    gente = []
    carteles, avisos, premios = [], [], []
    monkeypatch.setattr(sociales, 'sesiones', lambda: list(gente))
    monkeypatch.setattr(sociales, 'cartel', lambda t: carteles.append(t))
    monkeypatch.setattr(sociales, 'cartel_a', lambda s, t: None)
    monkeypatch.setattr(sociales, 'aviso', lambda s, t: avisos.append((s.personaje.nombre, t)))
    monkeypatch.setattr(sociales, 'refrescar', lambda *s: None)
    monkeypatch.setattr(sociales, 'revivir', lambda s, retraso=2.0: None)
    monkeypatch.setattr(sociales, 'premiar', lambda s, pr, mult=1.0, rng=None: premios.append(s.personaje.nombre) or 'x')

    def _oro(s, d):
        s.oro = max(0, s.oro + d)
    monkeypatch.setattr(sociales, 'cambiar_oro', _oro)
    monkeypatch.setattr(votacion, 'ESTADO', tmp_path / 'votacion.json')
    votacion._ESTADO.clear()
    ts._ACTIVO.clear()
    cazador._CAZA.clear()
    cazador.APUNTADOS.clear()
    duelos._DUELOS.clear()
    duelos._RETOS.clear()
    return NS(gente=gente, carteles=carteles, avisos=avisos, premios=premios)


# ---------------------------------------------------------------- tesoro
def test_el_cofre_del_tesoro(mundo, monkeypatch):
    import santa_clausula
    import trade_routes
    monkeypatch.setattr(santa_clausula, '_tile_de_aparicion', lambda st, ms: (120, 80))
    monkeypatch.setattr(app, '_monstruos_de', lambda st: {})
    cerca, lejos, fuera = _ses(1, 'Ana', x=121, y=81), _ses(2, 'Bob', x=10, y=10), _ses(3, 'Cid', stage=CIUDAD)
    monkeypatch.setattr(trade_routes, '_en_mapa', lambda st: [s for s in (cerca, lejos, fuera)
                                                              if s.personaje.stage == st])
    ts.empezar(SPIKE)
    cofre = ts._paquete_cofre(ts._ACTIVO)
    assert cofre in cerca.enviados and cofre in lejos.enviados and cofre not in fuera.enviados
    assert 'Clue 1' in mundo.carteles[-1] and "starts with 'S'" in mundo.carteles[-1]
    assert 'Spike Farm' in ts.pista(1) and '(120, 80)' in ts.pista(4)
    assert ts.pulsar(lejos, ts.EID_COFRE) and ts.activo() and 'Get closer' in mundo.avisos[-1][1]
    assert not ts.pulsar(cerca, 12345)                      # otra entidad: no es el cofre
    assert ts.pulsar(cerca, ts.EID_COFRE) and not ts.activo()
    assert mundo.premios == ['Ana'] and 'Ana found the treasure chest' in mundo.carteles[-1]
    assert ts._paquete_quitar() in lejos.enviados
    ts.al_entrar(lejos)                                     # ya no esta
    assert lejos.enviados.count(cofre) == 1


def test_el_tesoro_da_pistas_y_se_va(mundo, monkeypatch):
    import santa_clausula
    import trade_routes
    monkeypatch.setattr(santa_clausula, '_tile_de_aparicion', lambda st, ms: (50, 50))
    monkeypatch.setattr(app, '_monstruos_de', lambda st: {})
    monkeypatch.setattr(trade_routes, '_en_mapa', lambda st: [])
    ts.empezar(SPIKE)
    t0 = ts._ACTIVO['inicio']
    ts.tick(dt.datetime.fromtimestamp(t0 + 6 * 60 + 1))
    assert 'Clue 2' in mundo.carteles[-1]
    ts.tick(dt.datetime.fromtimestamp(t0 + 31 * 60))
    assert not ts.activo() and 'Nobody opened the chest' in mundo.carteles[-1]


# ---------------------------------------------------------------- cazador cazado
def test_la_presa_y_los_cazadores(mundo, monkeypatch):
    monkeypatch.setattr(sociales, 'es_de_caza', lambda st: st == SPIKE)
    presa, cazador_, mirón = _ses(1, 'Presa'), _ses(2, 'Caza'), _ses(3, 'Miron')
    mundo.gente += [presa, cazador_, mirón]
    cazador.APUNTADOS.update({1, 2})
    assert cazador.empezar(presa) == 'prey Presa'
    assert cazador.puede_atacar(cazador_, presa) and cazador.puede_atacar(presa, cazador_)
    assert not cazador.puede_atacar(mirón, presa) and not cazador.puede_atacar(presa, mirón)
    assert sociales.motivo_pvp(cazador_, presa) == '' and sociales.motivo_pvp(mirón, presa) is None
    assert sociales.baja(cazador_, presa)
    assert mundo.premios == ['Caza'] and not cazador.activa()


def test_la_presa_que_aguanta_gana_y_la_que_se_esconde_pierde(mundo, monkeypatch):
    monkeypatch.setattr(sociales, 'es_de_caza', lambda st: st == SPIKE)
    presa, otro = _ses(1, 'Presa'), _ses(2, 'Caza')
    mundo.gente += [presa, otro]
    cazador.APUNTADOS.update({1, 2})
    cazador.empezar(presa, ahora_ts=1.8e9)
    cazador.tick(dt.datetime.fromtimestamp(1.8e9 + 61))
    assert any('The prey Presa is in Spike Farm' in t for n, t in mundo.avisos if n == 'Caza')
    cazador.tick(dt.datetime.fromtimestamp(1.8e9 + 15 * 60 + 1))
    assert mundo.premios == ['Presa'] and not cazador.activa()
    cazador.empezar(presa, ahora_ts=1.9e9)
    presa.personaje.stage = CIUDAD
    cazador.tick(dt.datetime.fromtimestamp(1.9e9 + 61))
    assert cazador.activa()
    cazador.tick(dt.datetime.fromtimestamp(1.9e9 + 122))
    assert not cazador.activa() and 'lost the hunt' in mundo.carteles[-1]


# ---------------------------------------------------------------- duelos
def test_el_duelo_con_apuestas(mundo):
    a, b = _ses(1, 'Ana', oro=50000), _ses(2, 'Bob', x=105, oro=50000)
    p1, p2, p3 = _ses(3, 'Pepe', stage=CIUDAD, oro=10000), _ses(4, 'Luis', oro=10000), _ses(5, 'Mia', oro=10000)
    mundo.gente += [a, b, p1, p2, p3]
    assert 'Challenge sent' in duelos.retar(a, 'bob', 10000, ahora=100.0)
    assert 'accepted' in duelos.aceptar(b, ahora=101.0)
    assert a.oro == b.oro == 40000
    assert 'You bet 3000 Gold on Ana' in duelos.apostar(p1, 'Ana', 3000)
    assert 'You bet 1000 Gold on Ana' in duelos.apostar(p2, 'Ana', 1000)
    assert 'You bet 2000 Gold on Bob' in duelos.apostar(p3, 'Bob', 2000)
    assert 'own duel' in duelos.apostar(a, 'Bob', 1000)
    assert not duelos.puede_atacar(a, b)                     # aun en apuestas
    duelos.tick(101.0 + 31)
    assert duelos.puede_atacar(a, b) and duelos.puede_atacar(b, a) and not duelos.puede_atacar(a, p2)
    assert 'already bet' in duelos.apostar(p1, 'Ana', 1000) or 'not in a duel open' in duelos.apostar(p1, 'Ana', 1000)
    assert sociales.baja(a, b)
    assert a.oro == 60000 and b.oro == 40000
    # Pepe 3000 y Luis 1000 aciertan; Mia pierde 2000: 1900 tras la comision, 3/4 y 1/4
    assert p1.oro == 10000 - 3000 + 3000 + 1425 and p2.oro == 10000 - 1000 + 1000 + 475 and p3.oro == 8000
    assert not duelos._DUELOS


def test_el_duelo_sin_ganador_devuelve_todo(mundo):
    a, b, p = _ses(1, 'Ana', oro=5000), _ses(2, 'Bob', oro=5000), _ses(3, 'Pepe', oro=5000)
    mundo.gente += [a, b, p]
    assert 'too' not in duelos.retar(a, 'Bob', 2000, ahora=0.0)
    duelos.aceptar(b, ahora=1.0)
    duelos.apostar(p, 'Bob', 1000)
    duelos.tick(1.0 + 31)
    duelos.tick(1.0 + 31 + 181)
    assert a.oro == b.oro == p.oro == 5000 and 'draw' in mundo.carteles[-1]


def test_el_reto_pide_estar_cerca_y_con_oro(mundo):
    a, lejos, pobre = _ses(1, 'Ana'), _ses(2, 'Bob', x=200), _ses(3, 'Cid', x=101, oro=10)
    mundo.gente += [a, lejos, pobre]
    assert 'close to you' in duelos.retar(a, 'Bob', 5000)
    duelos.retar(a, 'Cid', 5000)
    assert 'no longer has' in duelos.aceptar(pobre)
    assert 'between' in duelos.retar(a, 'Cid', 5)


# ---------------------------------------------------------------- votacion
LUNES = dt.datetime(2026, 11, 23, 15, 0)


def test_la_votacion_de_la_semana(mundo, monkeypatch):
    clave = votacion.clave_semana(LUNES)
    ops = votacion.opciones(clave)
    assert ops == votacion.opciones(clave) and len(ops) == 5
    assert [o['tipo'] for o in ops].count('exp') == 3
    a, b, c = _ses(1, 'Ana'), _ses(2, 'Bob'), _ses(3, 'Cid')
    assert 'You voted' in votacion.votar(a, 2, LUNES)
    votacion.votar(b, 2, LUNES)
    votacion.votar(c, 4, LUNES)
    votacion.votar(c, 2, LUNES)                              # cambia el voto
    assert votacion.recuento(clave)[1] == 3
    titulo, l1, l2, pie, filas = votacion.vista(a, LUNES)
    assert 'Voting closes Friday' in titulo and filas[1][1] == '3 votes' and filas[1][2] == 100
    viernes = LUNES + dt.timedelta(days=4, hours=-15)
    assert 'closed' in votacion.votar(a, 1, viernes)
    votacion.tick(viernes)
    assert 'The players have spoken' in mundo.carteles[-1]
    sabado = LUNES + dt.timedelta(days=5)
    st = ops[1]['stage']
    assert votacion.mult_exp(st, sabado) == 2.0 and votacion.mult_exp(st, LUNES) == 1.0
    assert votacion.mult_exp(st + 1, sabado) == 1.0


def test_el_evento_votado_sale_en_el_calendario(mundo, monkeypatch):
    import calendario
    sabado = LUNES + dt.timedelta(days=5)
    clave = votacion.clave_semana(LUNES)
    i = next(i for i, o in enumerate(votacion.opciones(clave)) if o['tipo'] == 'evento')
    votacion.votar(_ses(1, 'Ana'), i + 1, LUNES)
    votacion.cerrar(clave)
    monkeypatch.setattr(votacion, '_ahora', lambda: sabado)
    extra = votacion.slots_extra()
    assert extra and all(d in (5, 6) for d, _h, _c in extra)
    assert all(f in calendario.semana() for f in extra)


def test_los_comandos_y_el_calendario():
    for cmd, clave in (('/hunt join', 'cazador'), ('/duel Bob 1000', 'duelo'), ('/bet Bob 50', 'apuesta'),
                       ('/vote 2', 'votacion')):
        assert app._gm_parsear(cmd)[0] == clave and clave in app.COMANDOS_DE_JUGADOR
    assert app._gm_parsear('/treasure start')[0] == 'tesoro_servidor'
    import calendario
    assert calendario.slots('tesoro') and calendario.slots('caza')
    assert (canal := __import__('canal_lua')).CARPETA.joinpath('votacion.lua').exists()


def test_cada_pista_sale_una_vez(mundo, monkeypatch):
    import santa_clausula
    import trade_routes
    monkeypatch.setattr(santa_clausula, '_tile_de_aparicion', lambda st, ms: (50, 50))
    monkeypatch.setattr(app, '_monstruos_de', lambda st: {})
    monkeypatch.setattr(trade_routes, '_en_mapa', lambda st: [])
    ts.empezar(SPIKE)
    t0 = ts._ACTIVO['inicio']
    for k in range(5):
        ts.tick(dt.datetime.fromtimestamp(t0 + 6 * 60 + 1 + k * 5))
    assert sum('Clue 2' in c for c in mundo.carteles) == 1


# ---------------------------------------------------------------- con botones, sin comandos
def _cmd(a, b=0):
    import struct
    import sociales_ui
    return struct.pack('<BII', sociales_ui.CMD_SO, a, b)


def _nombre_en_trozos(nombre):
    import struct
    b = nombre.encode('latin-1').ljust(16, b'\0')
    return [struct.unpack_from('<I', b, 4 * t)[0] for t in range(4)]


def test_duelo_y_apuestas_desde_las_ventanas(mundo, monkeypatch):
    """"clic en el personaje, duelo, y ahi colocar el monto; un panel de duelos y que se apueste antes" (25/11/2026)."""
    import sociales_ui
    recibidos = []
    monkeypatch.setattr(sociales_ui, 'reto_recibido', lambda s, n, o: recibidos.append((s.personaje.nombre, n, o)))
    a, b, p = _ses(1, 'Ana', oro=50000), _ses(2, 'Bob', x=104, oro=50000), _ses(3, 'Pepe', oro=9000)
    mundo.gente += [a, b, p]
    for t, v in enumerate(_nombre_en_trozos('Bob')):                 # el menu "Duel" sobre Bob y 10000 en la casilla
        assert sociales_ui.procesar(a, _cmd(20 + t, v))
    sociales_ui.procesar(a, _cmd(24, 10000))
    assert recibidos == [('Bob', 'Ana', 10000)]                     # a Bob le sale Accept / Decline
    sociales_ui.procesar(b, _cmd(25))                               # Accept
    assert a.oro == b.oro == 40000 and duelos._DUELOS
    pestana, titulos, _estado, reglas, d = sociales_ui.vista(p)    # el panel de Pepe: el duelo con dos botones
    filas = d[1]
    assert pestana == 1 and titulos[0] == 'Duels (1)' and len(reglas) == 4
    assert filas[0][1:] == ['Ana', 'Bob'] and filas[0][0].startswith('Ana vs Bob  Pot 20,000')
    sociales_ui.procesar(p, _cmd(41, 0))                            # fila que no existe: nada
    sociales_ui.procesar(p, _cmd(40, 4000))                         # 4000 a Bob (fila 0, segundo boton)
    assert p.oro == 5000 and duelos._DUELOS[0]['apuestas'][3] == [2, 4000]
    assert sociales_ui.vista(p)[4][1][0][1:] == ['', '']            # ya aposto: sin botones
    assert sociales_ui.vista(a)[4][1][0][1:] == ['', '']            # los duelistas no apuestan


def test_caza_y_votacion_con_botones(mundo):
    import cazador
    import sociales_ui
    a = _ses(1, 'Ana')
    mundo.gente.append(a)
    sociales_ui.procesar(a, _cmd(2, 2))                              # la pestana Hunted Hunter
    assert sociales_ui.vista(a)[0] == 2 and sociales_ui.vista(a)[4][1] == 'Join'
    sociales_ui.procesar(a, _cmd(50))
    assert cazador.apuntado(a) and sociales_ui.vista(a)[4][1] == 'Leave'
    sociales_ui.procesar(a, _cmd(50))
    assert not cazador.apuntado(a)
    sociales_ui.procesar(a, _cmd(61))                               # segunda opcion
    sociales_ui.procesar(a, _cmd(2, 3))
    _ayuda, opciones, _mio = sociales_ui.vista(a)[4]
    import votacion
    if votacion.abierta(votacion._ahora()):
        assert opciones[1].endswith('[YOUR VOTE]') and len(opciones) == 5
    sociales_ui.procesar(a, _cmd(2, 4))
    assert sociales_ui.vista(a)[0] == 4 and len(sociales_ui.lineas(a)) == 5


def test_ningun_texto_para_jugadores_pide_comandos():
    import re
    textos = ''
    for f in ('cazador.py', 'duelos.py', 'votacion.py', 'tesoro_servidor.py', 'sociales_ui.py', 'npc_memoria.py'):
        fuente = (RAIZ / 'server' / f).read_text(encoding='utf-8')
        cuerpo = fuente.split('"""', 2)[-1]                         # sin el docstring del modulo
        textos += '\n'.join(l for l in cuerpo.splitlines() if not l.strip().startswith('#') and 'GM' not in l)
    assert not re.search(r"'[^'\n]*/(hunt|duel|bet|vote|favor|treasure|dig)\b", textos)


def test_las_ventanas_del_cliente():
    sys.path.insert(0, str(RAIZ / 'tools'))
    import ventana_sociales as vs
    x = vs.bloque()
    assert 'id="58900"' in x and 'id="58920"' in x and x.count('WND_CLASS_EDIT') == 2
    for f in ('OnDueloOk', 'OnDueloNo', 'OnSocialApostarA', 'OnSocialApostarB', 'OnSocialCaza', 'OnSocialVotar',
              'OnSocialPestana'):
        assert '<OnCommand>%s</OnCommand>' % f in x
    w1 = (RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'wnd01.xml').read_text(encoding='utf-8')
    assert vs.wnd01(vs.wnd01(w1)) == vs.wnd01(w1)                                  # idempotente
    assert '<OnCommand>OnClickChatOptionDuelo</OnCommand>' in w1 and '<child>59008</child>' in w1
    lua = (RAIZ / 'server' / 'lua' / 'sociales.lua').read_text(encoding='utf-8')
    for f in ('OnClickChatOptionDuelo', 'DueloAbrir', 'SocialAbrir', 'SocialDatos', 'OnCommandEventos'):
        assert 'function %s(' % f in lua
