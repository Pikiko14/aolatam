"""Pet Defense, fase 2 (21/11/2026): la partida (server/pet_defense_partida.py) con un jugador de mentira."""
import copy
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import combate  # noqa: E402
import pet_defense as pd  # noqa: E402
import pet_defense_partida as pp  # noqa: E402
import transitable  # noqa: E402

CFG = copy.deepcopy(pd.config())
STAGE = CFG['mapa']['stage']


class Ses:
    def __init__(self):
        self.personaje = NS(entity_id=500001, nombre='Tester', stage=STAGE, tile_x=9, tile_y=35)
        self.monstruos = {}
        self.enviados = []
        self.cerrada = False
        self._pd_pendiente = True

    def enviar(self, *pk):
        self.enviados.extend(pk)

    enviar_inmediato = enviar


@pytest.fixture
def ses(monkeypatch):
    s = Ses()
    cfg = copy.deepcopy(CFG)
    cfg['partida'].update({'pausa_inicial': 1, 'pausa_entre_oleadas': 1, 'separacion_enemigos': 0.5})
    cfg['oleadas'] = [{'enemigos': [['normal', 2]]}, {'enemigos': [['rapido', 1]]}]
    monkeypatch.setattr(pd, 'config', lambda: cfg)
    monkeypatch.setattr(pd, '_sesiones_del_mapa', lambda stage: [s])
    monkeypatch.setattr(pd, '_arrancar', lambda: None)
    monkeypatch.setattr(app, '_pet_puede_atacar', lambda ss, m: True)

    def poner(ss, eid, npc_type, tile, zona):
        nombre, sprite = app._monstruo_bd(npc_type)
        if nombre == '?':
            return None
        m = combate.Monstruo(eid, npc_type, nombre, list(tile), sprite, stage=STAGE)
        m.generado = True
        ss.monstruos[eid] = m
        return m
    monkeypatch.setattr(app, '_poner_generado', poner)
    pd._TORRES.clear()
    pp._PARTIDAS.clear()
    pp.al_entrar(s)
    pa = pp.partida(s)
    pa.inicio, pa.proxima_oleada = 1000.0, 1000.5        # reloj simulado desde t=1000
    yield s
    pp._PARTIDAS.clear()
    pd._TORRES.clear()


def _correr(pa, desde, hasta, paso=0.2):
    t = desde
    while t < hasta and pa.resultado is None:
        pp.tick_partida(pa, t)
        t += paso
    return t


def test_camino_y_espacios():
    mp = CFG['mapa']
    ruta = pp.camino(STAGE, mp['portal'], mp['cristal'])
    assert ruta[0] == tuple(mp['portal']) and ruta[-1] == tuple(mp['cristal']) and len(ruta) > 100
    assert all(transitable.se_pisa(STAGE, *c) for c in ruta)
    esp = pp.espacios(STAGE, ruta, mp['separacion_espacios'], mp['distancia_espacio'])
    assert len(esp) >= 6
    en_camino = set(ruta)
    assert all(transitable.se_pisa(STAGE, *e) and e not in en_camino for e in esp)


def test_empieza_con_cristal_espacios_y_essence(ses):
    pa = pp.partida(ses)
    assert pa is not None and pa.vida == CFG['partida']['vida_cristal']
    assert pa.essence == CFG['partida']['essence_inicial']
    assert len(pa.npc_espacio) == len(pa.espacios)


def test_construir_mejorar_y_vender_cuestan_essence(ses):
    pa = pp.partida(ses)
    coste = CFG['torres']['guardian']['coste']
    ok, msg = pp.construir(pa, 0, 'guardian')
    assert ok and 'built' in msg and pa.essence == CFG['partida']['essence_inicial'] - coste
    assert not pp.construir(pa, 0, 'lobo')[0]                 # la piedra ya tiene torre
    t = pa.torres[0]
    ataque = t.ataque
    pa.essence = 10_000
    ok, msg = pp.mejorar(pa, 0)
    assert ok and 'level 2' in msg
    assert t.nivel == 2 and t.ataque > ataque and pa.essence == 10_000 - coste * 2
    pp.mejorar(pa, 0)
    ok, msg = pp.mejorar(pa, 0)
    assert not ok and 'max level' in msg
    gastado = coste * (1 + 2 + 3)
    antes = pa.essence
    ok, msg = pp.vender(pa, 0)
    assert ok and pa.essence == antes + int(gastado * CFG['venta_reembolso']) and 0 not in pa.torres
    assert t.entidad not in pd._TORRES
    pa.essence = 0
    ok, msg = pp.construir(pa, 1, 'dragon')
    assert not ok and 'Not enough Essence' in msg


def test_clic_en_la_piedra_abre_elegir_o_la_ficha(ses):
    import canal_lua
    pa = pp.partida(ses)
    eid = next(iter(pa.npc_espacio))
    ses.enviados.clear()
    assert pp.pulsar(ses, eid)
    lua = [p[2:-1].decode('latin1') for p in ses.enviados if struct.unpack_from('<H', p)[0] == canal_lua.OPCODE]
    assert any(t.startswith('PDElegir(') for t in lua) and not pa.torres
    pp.construir(pa, pa.npc_espacio[eid], 'lobo')
    ses.enviados.clear()
    pp.pulsar(ses, eid)
    lua = [p[2:-1].decode('latin1') for p in ses.enviados if struct.unpack_from('<H', p)[0] == canal_lua.OPCODE]
    assert any(t.startswith('PDTorre(') for t in lua)
    assert not pp.pulsar(ses, 123)


def test_essence_extra_al_limpiar_la_oleada(ses):
    pa = pp.partida(ses)
    pa.essence = 10_000
    pp.construir(pa, 0, 'bebe')
    pp.mejorar(pa, 0)                                         # nivel 2: el doble
    antes = pa.essence
    t = 1000.0
    for _ in range(2000):                                     # el heroe mata a la primera oleada en cuanto sale
        pp.tick_partida(pa, t)
        for m in list(pa.enemigos.values()):
            m.hp = 0
            pp.al_morir(ses, m)
        t += 0.2
        if pa.oleada == 1 and not pa.cola and not pa.enemigos and pa.proxima_oleada > t:
            break
    ganada = CFG['enemigos']['normal']['essence'] * 2 + CFG['enemigos']['jefe']['essence']   # y el jefe de la oleada
    assert pa.essence == antes + ganada + CFG['torres']['bebe']['essence_por_oleada'] * 2


def test_los_que_llegan_quitan_vida_y_se_pierde(ses):
    pa = pp.partida(ses)
    pa.vida = 2
    _correr(pa, 1000.0, 1400.0)
    assert pa.resultado == 'derrota' and pp.partida(ses) is None
    assert pa.fugados == 2


def test_matar_da_essence_sin_botin(ses):
    pa = pp.partida(ses)
    _correr(pa, 1000.0, 1001.5)
    m = next(iter(pa.enemigos.values()))
    antes = pa.essence
    m.hp = 0
    assert pp.al_morir(ses, m) is True
    assert pa.essence == antes + CFG['enemigos']['normal']['essence'] and m.entity_id not in pa.enemigos


def test_se_gana_al_acabar_las_oleadas(ses):
    pa = pp.partida(ses)
    t = 1000.0
    for _ in range(4000):
        pp.tick_partida(pa, t)
        for m in list(pa.enemigos.values()):      # el heroe los mata en cuanto salen
            m.hp = 0
            pp.al_morir(ses, m)
        t += 0.2
        if pa.resultado:
            break
    assert pa.resultado == 'victoria' and pa.resultado_datos['oleadas'] == 2
    assert pa.resultado_datos['puntos'] > 0


def test_salir_del_mapa_acaba_la_partida(ses):
    pa = pp.partida(ses)
    pp.construir(pa, 0)
    ses.personaje.stage = 41
    pp.tick_partida(pa, 1000.0)
    assert pa.resultado == 'abandono' and not pd._TORRES


def test_comando_pd():
    import gm
    assert 'pd' in gm.PALABRAS_DELEGADAS and 'pd' in gm.RESULTADOS_DELEGADOS
    assert gm.parsear('/pd start') == ('pd', 'start', '')
    assert gm.parsear('/pd tipo fuego') == ('pd', 'tipo', 'fuego')


def test_el_cristal_es_el_de_la_holy_battlefield(ses):
    """"Que el cristal sea 1 crystal de holybattlefield" (21/11/2026): un objeto de mapa 0x000E con su sprite."""
    import login
    pa = pp.partida(ses)
    mp = CFG['mapa']
    esperado = login._map_object_spawn(pa.npc_cristal, mp['objeto_cristal'], tuple(mp['cristal']))
    assert mp['objeto_cristal'] in (60368, 60367) and esperado and esperado in ses.enviados


@pytest.fixture(autouse=True)
def rk_tmp(tmp_path, monkeypatch):
    """Las partidas que acaban no van a la base de datos de verdad (data/pet_defense.db)."""
    import pet_defense_ranking
    monkeypatch.setattr(pet_defense_ranking, 'DB_PATH', tmp_path / 'pet_defense.db')

