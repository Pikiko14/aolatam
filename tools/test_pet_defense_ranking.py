"""Pet Defense, fase 4 (22/11/2026): partidas guardadas, ranking por temporadas, rangos y premios
(server/pet_defense_ranking.py y la ventana del ranking)."""
import copy
import json
import pathlib
import sqlite3
import struct
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import canal_lua  # noqa: E402
import cuentas  # noqa: E402
import pet_defense as pd  # noqa: E402
import pet_defense_ranking as rk  # noqa: E402
import pet_defense_ui as ui  # noqa: E402

CFG = copy.deepcopy(pd.config())
INICIO = 1_800_000_000.0                      # una fecha fija para las temporadas de los tests


class Ses:
    def __init__(self, cid, nombre, usuario=None):
        self.personaje = NS(char_id=cid, nombre=nombre, nivel=100, entity_id=500000 + cid, stage=41)
        self.usuario = usuario or ('u%d' % cid)
        self.enviados = []
        self._pd_lua = True

    def enviar(self, *pk):
        self.enviados.extend(pk)


@pytest.fixture(autouse=True)
def bases(tmp_path, monkeypatch):
    cfg = copy.deepcopy(CFG)
    import datetime as dt
    cfg['temporada'] = {'inicio': dt.datetime.fromtimestamp(INICIO).isoformat(), 'dias': 14}
    monkeypatch.setattr(pd, 'config', lambda: cfg)
    monkeypatch.setattr(rk, 'DB_PATH', tmp_path / 'pet_defense.db')
    cuentas_db = tmp_path / 'cuentas.db'
    monkeypatch.setattr(cuentas, '_get_conn', lambda: sqlite3.connect(cuentas_db))
    rk._ULTIMO[:] = [0, 0.0]
    yield cfg, cuentas_db


def _partida(ses, puntos, oleadas=10, segundos=1200, resultado='victoria', cuando=INICIO + 3600):
    return rk.guardar(ses, {'resultado': resultado, 'puntos': puntos, 'oleadas': oleadas, 'segundos': segundos},
                      ahora=cuando)


def test_temporadas_de_14_dias():
    assert rk.temporada(INICIO + 10)[0] == 1
    n, desde, hasta = rk.temporada(INICIO + 15 * 86400)
    assert n == 2 and desde == INICIO + 14 * 86400 and hasta == INICIO + 28 * 86400
    assert rk.temporada(INICIO - 5 * 86400)[0] == 1


def test_el_ranking_es_la_mejor_partida_de_cada_uno(monkeypatch):
    a, b, c = Ses(1, 'Ana'), Ses(2, 'Bea'), Ses(3, 'Ciro')
    _partida(a, 9000)
    _partida(a, 21000, segundos=1400)
    _partida(b, 21000, segundos=1300)                 # mismos puntos, menos tiempo: va delante
    _partida(c, 4000, oleadas=4, resultado='derrota')
    assert not _partida(c, 0, oleadas=0, resultado='abandono')    # abandonar sin pasar ninguna oleada no cuenta
    monkeypatch.setattr(rk, 'temporada', lambda ahora=None: (1, INICIO, INICIO + 14 * 86400))
    filas = rk.ranking()
    assert [f[2] for f in filas] == ['Bea', 'Ana', 'Ciro'] and filas[1][4] == 21000
    assert rk.mi_marca(1)[0] == 2 and rk.mi_marca(99) == (None, None)


def test_rangos():
    r = CFG['rangos']
    assert rk.rango(r['Gold'] + 1, 50) == 'Gold'
    assert rk.rango(r['Silver'], 50) == 'Silver' and rk.rango(r['Bronze'], 50) == 'Bronze'
    assert rk.rango(r['Bronze'] - 1, 50) is None
    assert rk.rango(r['Bronze'], 1) == 'Champion' and rk.rango(r['Bronze'], 7) == 'Angel'
    assert rk.rango(r['Bronze'] - 1, 1) is None                   # el 1o con pocos puntos no es Champion


def test_al_cerrar_la_temporada_se_reparten_los_premios_una_vez(bases):
    cfg, cuentas_db = bases
    for i, puntos in enumerate((23000, 21000, 15000, 13000, 6000, 1000)):
        _partida(Ses(10 + i, 'J%d' % i), puntos)
    hechos = rk.cron(ahora=INICIO + 15 * 86400)                   # empieza la temporada 2: se cierra la 1
    rangos = {nombre: r for nombre, r, _plan in hechos}
    assert rangos == {'J0': 'Champion', 'J1': 'Angel', 'J2': 'Angel', 'J3': 'Angel', 'J4': 'Angel'}   # J5 sin rango
    con = sqlite3.connect(cuentas_db)
    filas = con.execute("SELECT ronda, char_id, estado, plan FROM competiciones_premios ORDER BY char_id").fetchall()
    assert len(filas) == 5 and all(f[0] == 'petdefense-T1' and f[2] == 'pendiente' for f in filas)
    plan = json.loads(filas[0][3])
    assert plan['angel_gold'] == cfg['premios']['Champion']['angel_gold'] and plan['usuario'] == 'u10'
    assert plan['stage'] == rk.STAGE_PREMIO
    rk._ULTIMO[:] = [0, 0.0]
    assert rk.cron(ahora=INICIO + 16 * 86400) == []              # no se reparte dos veces
    assert len(con.execute('SELECT * FROM competiciones_premios').fetchall()) == 5


def test_premios_con_objetos_y_caducidad(bases):
    cfg, _db = bases
    cfg['premios']['Gold'] = {'angel_gold': 0, 'items': [{'id': 66330, 'cantidad': 1, 'dias': 14}]}
    plan = rk.plan_de('Gold', ahora=INICIO)
    assert plan['items'] == [{'id': 66330, 'cantidad': 1, 'caduca_en': INICIO + 14 * 86400}]
    assert rk.plan_de(None) is None


def test_la_ventana_del_ranking(monkeypatch):
    a = Ses(1, 'Ana')
    monkeypatch.setattr(rk, 'temporada', lambda ahora=None: (1, INICIO, INICIO + 14 * 86400))
    _partida(a, 21000)
    assert ui.procesar(a, struct.pack('<BII', ui.CMD_PD, 10, 0))
    textos = [p[2:-1].decode('latin1') for p in a.enviados if struct.unpack_from('<H', p)[0] == canal_lua.OPCODE]
    llamada = [t for t in textos if t.startswith('PDRanking(')][0]
    assert 'Ana' in llamada and '21,000' in llamada and 'Season 1 best: #1' in llamada and 'Champion' in llamada
    assert len(llamada) < 2000


def test_la_partida_se_guarda_al_acabar(monkeypatch):
    import pet_defense_partida as pp
    s = Ses(5, 'Eva')
    s.cerrada = False
    guardadas = []
    monkeypatch.setattr(rk, 'guardar', lambda ses, datos, ahora=None: guardadas.append(datos) or True)
    monkeypatch.setattr(ui, 'fin', lambda pa: None)
    pa = NS(ses=s, enemigos={}, npc_cristal=None, npc_espacio={}, inicio=0, oleada=3, vida=10, vida_max=30,
            muertos=40, fugados=2, resultado=None, total_oleadas=10)
    pp._PARTIDAS[s] = pa
    monkeypatch.setattr(pd, 'quitar', lambda ses=None: 0)
    pp.terminar(s, 'derrota', avisar=False)
    assert guardadas and guardadas[0]['oleadas'] == 2 and guardadas[0]['resultado'] == 'derrota'


def test_tres_partidas_al_dia_por_personaje(bases):
    """"Se puede jugar maximo 3 veces el juego al dia por personaje" (22/11/2026)."""
    dia = INICIO + 3600
    assert rk.quedan_hoy(7, dia) == 3
    for _ in range(3):
        rk.anotar_entrada(7, dia)
    assert rk.quedan_hoy(7, dia) == 0 and rk.quedan_hoy(8, dia) == 3
    assert rk.quedan_hoy(7, dia + 86400) == 3                    # al dia siguiente vuelve a tener 3


def test_sin_partidas_no_deja_empezar(bases, monkeypatch):
    import pet_defense_partida as pp
    s = Ses(9, 'Ivo')
    for _ in range(3):
        rk.anotar_entrada(9)
    viajes = []
    import app
    monkeypatch.setattr(app, '_viajar_por_portal', lambda *a, **k: viajes.append(a))
    msg = pp.empezar(s)
    assert msg.startswith('You already played') and not viajes and not getattr(s, '_pd_pendiente', False)


def test_100_ag_por_oleada_superada(bases):
    """"100 de AG por cada wave superado" (22/11/2026): por la cola de premios, que lo entrega sola."""
    cfg, cuentas_db = bases
    s = Ses(11, 'Lia')
    assert rk.premiar_oleadas(s, 7, ahora=INICIO) == 7 * cfg['ag_por_oleada'] == 700
    assert rk.premiar_oleadas(s, 0, ahora=INICIO + 1) == 0
    filas = sqlite3.connect(cuentas_db).execute('SELECT char_id, estado, plan FROM competiciones_premios').fetchall()
    assert len(filas) == 1 and filas[0][0] == 11 and filas[0][1] == 'pendiente'
    plan = json.loads(filas[0][2])
    assert plan['angel_gold'] == 700 and plan['usuario'] == 'u11' and plan['items'] == []
