"""Honor Points por PvP y su tienda (26/11/2026)."""
import pathlib
import re
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
import app  # noqa: E402
import honor  # noqa: E402
import sociales  # noqa: E402


def _ses(cid, nombre, nivel=60):
    return NS(personaje=NS(char_id=cid, nombre=nombre, nivel=nivel, stage=6), mochila=[], llena=False)


@pytest.fixture
def mundo(monkeypatch, tmp_path):
    gente, avisos = [], []
    monkeypatch.setattr(honor, 'DB_PATH', tmp_path / 'honor.db')
    honor._HOY.clear()
    monkeypatch.setattr(sociales, 'sesiones', lambda: list(gente))
    monkeypatch.setattr(sociales, 'aviso', lambda s, t: avisos.append((s.personaje.nombre, t)))

    def dar_item(s, iid, n=1):
        if s.llena:
            return 'Your backpack is full.'
        s.mochila.append((iid, n))
        return 'dado %dx' % n
    monkeypatch.setattr(app, '_gm_dar_item', dar_item)
    return NS(gente=gente, avisos=avisos)


def _honor(s):
    return sum(n for i, n in s.mochila if i == honor.item())


def test_duelo_con_topes(mundo):
    a, b, c = _ses(1, 'Ana'), _ses(2, 'Bob'), _ses(3, 'Cid')
    mundo.gente += [a, b, c]
    cf = honor.cfg()['duelo']
    assert honor.duelo(1, 2, cf['oro_min'] - 1) == 0                 # apuesta chica: nada
    for _ in range(cf['tope_rival_dia'] + 2):
        honor.duelo(1, 2, cf['oro_min'])
    assert _honor(a) == cf['victoria'] * cf['tope_rival_dia']      # tope contra el mismo rival
    assert 'duel won' in mundo.avisos[-1][1] and 'Event Overview' in mundo.avisos[-1][1]
    honor.duelo(1, 3, cf['oro_min'])
    assert _honor(a) == cf['victoria'] * (cf['tope_rival_dia'] + 1)
    assert honor.total(1) == _honor(a)


def test_baja_suelta_no_vale_contra_mucho_mas_bajos(mundo):
    a, novato, par = _ses(1, 'Ana', 80), _ses(2, 'Bob', 20), _ses(3, 'Cid', 78)
    mundo.gente += [a, novato, par]
    assert honor.baja(a, novato) == 0
    assert honor.baja(a, par) == honor.cfg()['baja']['puntos']


def test_pendiente_si_no_esta_o_mochila_llena(mundo):
    a = _ses(1, 'Ana')
    honor.dar(1, 10, 'x')                                            # no esta conectada
    a.llena = True
    mundo.gente.append(a)
    honor.dar(a, 5, 'y')
    assert _honor(a) == 0 and 'next login' in mundo.avisos[-1][1]
    a.llena = False
    honor.al_conectar(a)
    assert _honor(a) == 15
    honor.al_conectar(a)                                             # ya no queda nada
    assert _honor(a) == 15


def test_competicion_holy_y_arena(mundo, monkeypatch):
    import competicion_premios
    monkeypatch.setattr(competicion_premios, 'seleccionar', lambda r, cid, m: (None, 'pendiente'))
    a, b = _ses(1, 'Ana'), _ses(2, 'Bob')
    mundo.gente += [a, b]
    c = honor.cfg()
    honor.competicion({'stage': 112, 'ganador': 1, 'miembros': {'1': {'equipo': 1}, '2': {'equipo': 2}}})
    assert _honor(a) == c['holy']['ganador'] and _honor(b) == c['holy']['perdedor']
    honor.competicion({'stage': 159, 'clasificacion': ['2', '1'], 'miembros': {'1': {}, '2': {}}})
    assert _honor(b) == c['holy']['perdedor'] + c['arena']['campeon']


def test_tienda_solo_pd_sin_bonus():
    import tienda_honor as th
    assert th.sin_bonus({'物品類別': '紙娃娃', '頭部裝備': '是', 'HP': '0'})
    assert not th.sin_bonus({'物品類別': '紙娃娃', '頭部裝備': '是', 'HP': '50'})
    assert not th.sin_bonus({'物品類別': '紙娃娃', '寵物座騎裝備': '是', '移動速度': '20'})
    assert not th.sin_bonus({'物品類別': '紙娃娃', '頭部裝備': '是', '持續時間': '7'})
    t = (th.CARPETAS[1] / 'exchange.xml').read_text(encoding='utf-8')
    ids = [int(x) for x in re.findall(r'<exchange 編號="(\d+)"', t)]
    assert ids == list(range(1, len(ids) + 1))                      # sin huecos
    for _k, (_f, g, _n, precio) in th.TIENDAS.items():
        filas = re.findall(r'<exchange [^>]*群組="%d"[^>]*/>' % g, t)
        assert filas and all('材料1="%d" 材料1數量="%d"' % (honor.item(), precio) in f for f in filas)
