"""Mundo vivo: clima, mapas que evolucionan, lo salvaje y NPC con memoria (25/11/2026)."""
import datetime as dt
import pathlib
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import mundo_vivo as mv  # noqa: E402
import npc_memoria as nm  # noqa: E402

DIA = dt.datetime(2026, 11, 25, 15, 10)
SPIKE = 6           # Spike Farm, de caza
CIUDAD = 3          # Aurora City, sin monstruos
CUEVA = 35          # Memory Cave


@pytest.fixture(autouse=True)
def limpio(monkeypatch, tmp_path):
    for d in (mv._MUERTES, mv._FASE, mv._VISTO, mv._SALVAJE, mv._CLIMA_DICHO):
        d.clear()
    monkeypatch.setattr(nm, 'DB_PATH', tmp_path / 'npc.db')
    monkeypatch.setattr(mv, 'ESTADO', tmp_path / 'mv.json')


def test_el_clima_es_el_mismo_toda_la_hora_y_cambia():
    assert mv.clima(SPIKE, DIA) is mv.clima(SPIKE, DIA.replace(minute=59))
    assert mv.clima(CIUDAD, DIA) is None and mv.clima(CUEVA, DIA) is None and mv.es_campo(CUEVA)
    vistos = {mv.clima(SPIKE, DIA + dt.timedelta(hours=h))['id'] for h in range(72)}
    assert len(vistos) >= 4
    assert 'until 16:00' in mv.texto_clima(SPIKE, DIA)


def test_los_efectos_del_clima(monkeypatch):
    lluvia = next(c for c in mv.config()['climas'] if c['id'] == 'rain')
    monkeypatch.setattr(mv, 'clima', lambda st, ahora=None: lluvia if st == SPIKE else None)
    assert mv.mult_dano(SPIKE, True) == pytest.approx(1.15) and mv.mult_dano(SPIKE, False) == pytest.approx(0.9)
    assert mv.mult(SPIKE, 'exp') == 1.0 and mv.mult(CIUDAD, 'mag') == 1.0


def test_el_monstruo_pega_segun_el_clima(monkeypatch):
    import combate
    m = combate.Monstruo(1, 1, 'x', [10, 10], 0, stage=SPIKE)
    m.var = 0
    monkeypatch.setattr(mv, 'mult', lambda st, k, ahora=None: 1.0)
    base = m.pegar()
    monkeypatch.setattr(mv, 'mult', lambda st, k, ahora=None: 1.5 if k == 'atk' else 1.0)
    assert m.pegar() == round(base * 1.5)


def test_un_mapa_abandonado_se_vuelve_salvaje_y_se_doma(monkeypatch):
    import presencia
    monkeypatch.setattr(presencia, '_vivas', lambda st: [])
    t0 = DIA.timestamp()
    mv._VISTO[SPIKE] = t0
    mv._marcar_presencia(t0 + 3600)
    assert not mv.salvaje(SPIKE)
    mv._marcar_presencia(t0 + 3 * 3600 + 1)
    assert mv.salvaje(SPIKE) and mv.mult(SPIKE, 'exp', DIA) >= 1.4
    assert any('[Wild]' in l for l in mv.lineas(SPIKE, DIA))
    monkeypatch.setattr(mv, '_a_los_del_mapa', lambda st, t: None)
    for _ in range(mv.config()['domar']):
        mv.al_matar(None, NS(stage=SPIKE, npc_type=1), t0)
    assert not mv.salvaje(SPIKE)


def test_mucha_caza_agita_el_mapa_y_saca_al_jefe(monkeypatch):
    pasos = []
    monkeypatch.setattr(mv, 'agitar', lambda st: (pasos.append('elites'), mv._FASE.__setitem__(st, {'fase': 'agitado'})))
    monkeypatch.setattr(mv, 'sacar_jefe', lambda st: (pasos.append('jefe'), mv._FASE[st].update(fase='jefe')))
    cfg = mv.config()['evolucion']
    t = DIA.timestamp()
    for i in range(cfg['jefe_local']):
        mv.al_matar(None, NS(stage=SPIKE, npc_type=1), t + i)
    assert pasos == ['elites', 'jefe']
    # si se caza despacio no pasa nada
    mv._FASE.clear(); mv._MUERTES.clear(); pasos.clear()
    for i in range(cfg['agitado']):
        mv.al_matar(None, NS(stage=SPIKE, npc_type=1), t + i * 60)
    assert pasos == []


def test_los_comandos():
    assert app._gm_parsear('/weather') == ('clima',) and app._gm_parsear('/favor') == ('favor',)
    assert {'clima', 'favor'} <= app.COMANDOS_DE_JUGADOR
    assert app._gm_parsear('/world boss 6')[0] == 'mundo_vivo'


# ---------------------------------------------------------------- NPC con memoria
@pytest.fixture
def jug(monkeypatch):
    avisos, exp, oro = [], [], []
    monkeypatch.setattr(nm, '_aviso', lambda s, t: avisos.append(t))
    monkeypatch.setattr(app, '_dar_exp_y_creditos', lambda s, exp=0, creditos=0: exp_.append(exp))
    exp_ = exp
    import trade_routes
    monkeypatch.setattr(trade_routes, '_cambiar_oro', lambda s, d: oro.append(d))
    ses = NS(personaje=NS(char_id=7, nombre='Tester', nivel=50, stage=SPIKE))
    return NS(ses=ses, avisos=avisos, exp=exp, oro=oro)


def test_el_mercader_te_recuerda_y_te_rebaja(jug):
    t = DIA.timestamp()
    nm.al_hablar(jug.ses, 'Grocer', 4, DIA)
    assert nm.precio(jug.ses, 1000, t) == 1000 and jug.avisos == []
    nm.al_comprar(jug.ses, 6000, 6000, t)
    assert 'regular' in jug.avisos[-1] and nm.precio(jug.ses, 1000, t) == 970
    nm.al_comprar(jug.ses, 970, 1000, t)
    assert 'saved 30 Gold' in jug.avisos[-2] or 'saved 30 Gold' in jug.avisos[-1]
    # otro NPC no te conoce
    nm.al_hablar(jug.ses, 'Weapon Merchant', 4, DIA)
    assert nm.precio(jug.ses, 1000, t) == 1000
    # ni pasados los minutos de la tienda
    nm.al_hablar(jug.ses, 'Grocer', 4, DIA)
    assert nm.precio(jug.ses, 1000, t + 3600) == 1000


def test_te_olvida_si_no_vuelves(jug):
    t = DIA.timestamp()
    nm.al_hablar(jug.ses, 'Grocer', 4, DIA)
    nm.al_comprar(jug.ses, 30000, 30000, t)
    assert nm.nivel(nm.gasto(7, 'Grocer@4', t))[0] == 5
    assert nm.nivel(nm.gasto(7, 'Grocer@4', t + 15 * 86400))[0] == 3
    assert nm.nivel(nm.gasto(7, 'Grocer@4', t + 29 * 86400))[0] == 0


def test_el_favor(jug, monkeypatch):
    import combate
    monkeypatch.setattr(combate, 'es_jefe', lambda n: False)
    t = DIA.timestamp()
    nm.al_hablar(jug.ses, 'Grocer', 4, DIA)
    nm.al_comprar(jug.ses, 6000, 6000, t)
    jug.ses._npc_saludo = {}
    nm.al_hablar(jug.ses, 'Grocer', 4, DIA + dt.timedelta(hours=1))
    assert any('Welcome back, Tester' in a for a in jug.avisos) and any('favor' in a for a in jug.avisos)
    f = nm.favor(7)
    f.update(tipo='matar', n=3, lvmin=40, lvmax=60)
    nm._guardar_favor(7, f)
    nm.al_matar(jug.ses, NS(npc_type=1, nivel=10))          # muy bajo: no cuenta
    for _ in range(3):
        nm.al_matar(jug.ses, NS(npc_type=1, nivel=50))
    assert nm.favor(7)['cumplido'] and 'Go back to Grocer' in jug.avisos[-1]
    nm.al_hablar(jug.ses, 'Grocer', 4, DIA + dt.timedelta(hours=2))
    assert jug.exp and jug.oro == [400 * 50] and nm.favor(7)['cobrado']
    # al dia siguiente, otro
    jug.ses._npc_saludo = {}
    nm.al_hablar(jug.ses, 'Grocer', 4, DIA + dt.timedelta(days=1))
    assert not nm.favor(7)['cobrado']


# ---------------------------------------------------------------- que se note
def _ses_en(stage, x=100, y=100):
    enviados = []
    return NS(personaje=NS(char_id=7, nombre='Tester', nivel=50, stage=stage, entity_id=555, tile_x=x, tile_y=y),
              enviar=lambda *p: enviados.extend(p), enviados=enviados)


def test_el_icono_del_clima_en_la_barra(monkeypatch):
    import struct
    tormenta = next(c for c in mv.config()['climas'] if c['id'] == 'storm')
    monkeypatch.setattr(mv, 'clima', lambda st, ahora=None: tormenta if st == SPIKE else None)
    ses = _ses_en(SPIKE)
    mv.iconos(ses, DIA)
    assert ses.enviados == [struct.pack('<HIBBII', 0x001D, 555, 1, 4, tormenta['magia'], 50 * 60 * 1000)]
    mv.iconos(ses, DIA)                                   # no se repite
    assert len(ses.enviados) == 1
    ses.personaje.stage = CIUDAD                          # a la ciudad: fuera
    mv.iconos(ses, DIA)
    assert ses.enviados[-1] == struct.pack('<HIBBII', 0x001D, 555, 1, 4, tormenta['magia'], 0)
    import cliente_local
    assert cliente_local.MAGIAS_PROPIAS[tormenta['magia']]['名稱'] == 'Weather: Thunderstorm'
    xml = (RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'magic.xml').read_text(encoding='utf-8')
    assert all('編號="%d"' % k in xml for k in range(23421, 23435))


def test_los_rayos_caen_sobre_los_monstruos_cercanos(monkeypatch):
    import combate
    tormenta = next(c for c in mv.config()['climas'] if c['id'] == 'storm')
    monkeypatch.setattr(mv, 'clima', lambda st, ahora=None: tormenta)
    ses = _ses_en(SPIKE)
    cerca = NS(entity_id=11, tile_x=105, tile_y=98, vivo=True)
    lejos = NS(entity_id=12, tile_x=300, tile_y=300, vivo=True)
    muerto = NS(entity_id=13, tile_x=101, tile_y=101, vivo=False)
    assert mv.paquetes_ambiente(ses, SPIKE, {11: cerca}) == []           # apagado: los mobs no hacen efectos
    cfg = dict(mv.config(), fx_monstruos=True)
    monkeypatch.setattr(mv, 'config', lambda: cfg)
    pk = mv.paquetes_ambiente(ses, SPIKE, {11: cerca, 12: lejos, 13: muerto})
    assert pk == combate.efecto_magia_self(11, 62, 8463, cast_time=100)
    despejado = next(c for c in mv.config()['climas'] if c['id'] == 'clear')
    monkeypatch.setattr(mv, 'clima', lambda st, ahora=None: despejado)
    assert mv.paquetes_ambiente(ses, SPIKE, {11: cerca}) == []


def test_el_cartel_al_entrar(monkeypatch):
    nieve = next(c for c in mv.config()['climas'] if c['id'] == 'snow')
    monkeypatch.setattr(mv, 'clima', lambda st, ahora=None: nieve if st == SPIKE else None)
    carteles = []
    monkeypatch.setattr(mv, '_cartel', lambda s, t: carteles.append(t))
    monkeypatch.setattr(mv, '_aviso', lambda s, t: None)
    mv.al_entrar(_ses_en(SPIKE))
    assert carteles == ['Snowfall in Spike Farm: gold +30%, physical damage -10%']
    mv.al_entrar(_ses_en(CIUDAD))
    assert len(carteles) == 1


def test_el_cielo_de_verdad(monkeypatch):
    """"o genera los efectos e implementalos al cliente" (25/11/2026): el s2c 0x0015 del propio cliente."""
    import struct
    climas = {c['id']: c for c in mv.config()['climas']}
    actual = {'c': climas['snow']}
    monkeypatch.setattr(mv, 'clima', lambda st, ahora=None: actual['c'] if st == SPIKE else None)
    ses = _ses_en(SPIKE)
    mv.cielo(ses, DIA, forzar=True)
    assert ses.enviados == [struct.pack('<HBBB', 0x0015, 2, 4, 2), struct.pack('<HBB', 0x0015, 1, 15)]
    mv.cielo(ses, DIA)                                     # sin cambios, nada
    assert len(ses.enviados) == 2
    actual['c'] = climas['bloodmoon']                      # cambia: noche; sin cielo_propios, sin la ceniza (8)
    mv.cielo(ses, DIA)
    assert ses.enviados[-2:] == [struct.pack('<HBBB', 0x0015, 2, 0, 0), struct.pack('<HBB', 0x0015, 1, 0)]
    cfg = dict(mv.config(), cielo_propios=True)             # con el angel.dat nuevo para todos: la ceniza
    monkeypatch.setattr(mv, 'config', lambda: cfg)
    actual['c'] = climas['storm']
    mv.cielo(ses, DIA)
    actual['c'] = climas['bloodmoon']
    mv.cielo(ses, DIA)
    assert ses.enviados[-2:] == [struct.pack('<HBBB', 0x0015, 2, 8, 2), struct.pack('<HBB', 0x0015, 1, 0)]
    ses.personaje.stage = CIUDAD                           # a la ciudad: cielo normal
    mv.cielo(ses, DIA, forzar=True)
    assert ses.enviados[-2:] == [struct.pack('<HBBB', 0x0015, 2, 0, 0), struct.pack('<HBB', 0x0015, 1, 15)]
    nuevo = _ses_en(CIUDAD)                                # quien nunca tuvo clima no recibe nada en la ciudad
    mv.cielo(nuevo, DIA, forzar=True)
    assert nuevo.enviados == []
    assert {c['cielo'][0] for c in climas.values()} >= {0, 2, 3, 4, 5, 6, 7, 8}


def test_los_climas_propios_del_cliente():
    """"agrega niebla y demas, crea los efectos tu" (25/11/2026): codigos 6+ en angel.dat y sus sprites."""
    sys.path.insert(0, str(RAIZ / 'tools'))
    import clima_sprites
    import parche_clima_exe as pc
    usados = {c['cielo'][0] for c in mv.config()['climas']}
    assert {k for k in usados if k >= pc.PRIMER_CODIGO} <= set(pc.CLIMAS)
    # cada codigo propio tiene su sprite en el parche, con el nombre que carga el exe
    for codigo, (sprite, (_vy, vyr), (_vx, vxr)) in pc.CLIMAS.items():
        assert vyr >= 1 and vxr >= 1
        assert sprite.lower() in clima_sprites.SPRITES
        assert (RAIZ / 'parches' / 'extras' / 'shape' / (sprite.lower() + '.shp')).read_bytes()[:4] == b'TLHS'
    # el exe que reparte el launcher lleva el parche, y el parche entra en el original
    exe = RAIZ / 'parches' / 'juego' / 'angel.dat'
    if exe.exists():
        assert pc.lleva_el_parche(exe.read_bytes())
    sin = RAIZ / 'parches' / 'juego' / 'angel.dat.sin_clima'
    if sin.exists():
        assert pc.parchear(sin.read_bytes()) == exe.read_bytes()
