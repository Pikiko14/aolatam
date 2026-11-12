"""Los puzles de las raids (server/raid_puzles.py, 11/11/2026: "que tengas uno que otro puzzle")."""
import itertools
import os
import sys
from types import SimpleNamespace as NS

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'server'))

import raid  # noqa: E402
import raid_puzles  # noqa: E402


def test_las_pistas_dan_un_solo_orden():
    for orden in itertools.permutations(range(4)):
        assert raid_puzles._resuelve(orden) == [orden]
        assert len(raid_puzles.pistas(orden)) == 3


def test_cada_zona_tiene_su_puzle_en_casillas_que_se_pisan():
    import transitable
    for d in raid.CATALOGO:
        p = raid.datos(d['clave'])
        tipos = [z['puzle']['tipo'] for z in p['zonas']]
        assert len(set(tipos)) == 3, (d['clave'], tipos)
        for z in p['zonas']:
            pz = z['puzle']
            casillas = pz.get('casillas') or [pz['origen'], pz['destino']]
            for x, y in casillas:
                assert transitable.se_pisa(d['stage'], x, y), (d['clave'], z['nombre'], (x, y))
            assert len(z['patrullas']) == 2 and all(pt['ruta'] for pt in z['patrullas'])
            assert z['ambiente']['entrar'] and z['ambiente']['cerca']
    # entre las cuatro raids salen los cuatro tipos
    assert {z['puzle']['tipo'] for d in raid.CATALOGO for z in raid.datos(d['clave'])['zonas']} == {
        'placas', 'totems', 'sellos', 'antorcha'}


def _montaje(monkeypatch, tipo, jugadores=2):
    """Una corrida falsa en una zona con el puzle `tipo` y `jugadores` vivos en la copia."""
    import app
    gente = [NS(personaje=NS(tile_x=0, tile_y=0, hp=100, entity_id=i + 1, nombre='P%d' % i), muerto=False,
                enviar=lambda *a: None) for i in range(jugadores)]
    r = {'id': 1, 'clave': 'warring'}
    c = {'zona': 0, 'vivos': set(), 'adds': set(), 'jefe': None}
    r['corrida'] = c
    hechos = {'jefe': 0, 'carteles': [], 'monstruos': []}
    sig = itertools.count(1000)

    def sacar(ses, npc, casilla, r_, c_):
        m = NS(entity_id=next(sig), npc_type=npc, raid=1, agro=0)
        hechos['monstruos'].append(m)
        return m
    monkeypatch.setattr(raid, '_en_la_copia', lambda r_: gente)
    monkeypatch.setattr(raid, '_cartel', lambda r_, t: hechos['carteles'].append(t))
    monkeypatch.setattr(raid, '_sacar_jefe', lambda *a: hechos.__setitem__('jefe', hechos['jefe'] + 1))
    monkeypatch.setattr(raid, '_sacar_bicho', sacar)
    monkeypatch.setattr(raid, '_quitar', lambda r_, eid: None)
    monkeypatch.setattr(raid, '_marcar', lambda s, seg: None)
    monkeypatch.setattr(raid, 'herir', lambda s, m, pct: None)
    monkeypatch.setattr(raid_puzles, '_diferido', lambda seg, fn, *a: fn(*a))
    monkeypatch.setattr(app, '_npc_de_npc_xml', lambda n: ('Altar', 42212))
    zona = next(z for d in raid.CATALOGO for z in raid.datos(d['clave'])['zonas'] if z['puzle']['tipo'] == tipo)
    return gente, r, c, zona, hechos


def _ir(s, casilla):
    s.personaje.tile_x, s.personaje.tile_y = casilla


def test_placas_hace_falta_uno_en_cada_una_a_la_vez(monkeypatch):
    gente, r, c, zona, hechos = _montaje(monkeypatch, 'placas', jugadores=2)
    assert raid_puzles.empezar(gente[0], r, c, zona)
    cas = zona['puzle']['casillas']
    _ir(gente[0], cas[0])
    raid_puzles.tic(gente[0], r, c, 100.0)
    raid_puzles.tic(gente[0], r, c, 105.0)
    assert hechos['jefe'] == 0                          # con dos vivos hacen falta dos placas
    _ir(gente[1], cas[1])
    raid_puzles.tic(gente[0], r, c, 106.0)
    raid_puzles.tic(gente[0], r, c, 109.5)
    assert hechos['jefe'] == 1 and c['puzle']['hecho']


def test_totems_en_orden_y_fuera_de_orden(monkeypatch):
    gente, r, c, zona, hechos = _montaje(monkeypatch, 'totems')
    raid_puzles.empezar(gente[0], r, c, zona)
    pz = c['puzle']
    pilares = {m.pilar: m for m in hechos['monstruos']}
    malo = pz['orden'][1]
    assert raid_puzles.al_morir(gente[0], r, c, pilares[malo])
    assert any('Wrong order' in t for t in hechos['carteles']) and pz['caidos'] == []
    pilares = {m.pilar: m for m in hechos['monstruos'][-4:]}         # se levantaron otra vez
    for i in pz['orden']:
        raid_puzles.al_morir(gente[0], r, c, pilares[i])
    assert hechos['jefe'] == 1


def test_sellos_caen_con_sus_guardianes(monkeypatch):
    gente, r, c, zona, hechos = _montaje(monkeypatch, 'sellos')
    raid_puzles.empezar(gente[0], r, c, zona)
    for m in list(hechos['monstruos']):
        raid_puzles.al_morir(gente[0], r, c, m)
    assert hechos['jefe'] == 1 and len(c['puzle']['rotos']) == 3


def test_la_antorcha_se_apaga_y_se_entrega(monkeypatch):
    gente, r, c, zona, hechos = _montaje(monkeypatch, 'antorcha')
    raid_puzles.empezar(gente[0], r, c, zona)
    d = zona['puzle']
    _ir(gente[0], d['origen'])
    raid_puzles.tic(gente[0], r, c, 0.0)
    assert c['puzle']['portador'] is gente[0]
    raid_puzles.tic(gente[0], r, c, d['segundos'] + 1.0)             # se le apago
    assert c['puzle']['portador'] is None or c['puzle']['hasta'] > d['segundos']
    for vuelta in range(d['entregas']):
        t = 100.0 * (vuelta + 1)
        _ir(gente[0], d['origen'])
        raid_puzles.tic(gente[0], r, c, t)
        _ir(gente[0], d['destino'])
        raid_puzles.tic(gente[0], r, c, t + 5)
    assert hechos['jefe'] == 1
