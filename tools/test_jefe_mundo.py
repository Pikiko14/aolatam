"""El jefe de mundo (25/11/2026, server/jefe_mundo.py y plantillas/jefe_mundo.json)."""
import datetime as dt
import pathlib
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import combate  # noqa: E402
import jefe_mundo as jm  # noqa: E402

LUNES = dt.datetime(2026, 11, 23)


@pytest.fixture(autouse=True)
def limpio(tmp_path, monkeypatch):
    carteles = []
    monkeypatch.setattr(jm, '_cartel', carteles.append)
    monkeypatch.setattr(jm, 'ESTADO', tmp_path / 'jefe_mundo.json')
    jm._ACTIVO.clear()
    yield carteles
    if jm._ACTIVO.get('m') is not None:
        jm.retirar('test')


def test_los_jefes_son_del_juego():
    for npc in jm.config()['jefes']:
        nombre, sprite = app._monstruo_bd(npc)
        assert nombre and sprite and combate.es_jefe(npc), npc


def test_sale_a_su_hora_una_sola_vez(limpio):
    assert jm.horas_de_hoy(LUNES) == ['12:00', '19:30', '23:00']
    assert jm.toca(LUNES.replace(hour=11, minute=59)) is None
    jm.tick(LUNES.replace(hour=12, minute=1))
    m = jm.activo()
    assert m is not None and m.hp == m.hp_max == jm.config()['vida'] and m.npc_type in jm.config()['jefes']
    assert app._SALAS_DEL_MUNDO[jm._ACTIVO['stage']].monstruos[m.entity_id] is m
    assert 'appeared' in limpio[-1]
    jm.retirar('test')
    jm.tick(LUNES.replace(hour=12, minute=3))                  # la misma salida no vuelve a salir
    assert jm.activo() is None
    jm.tick(LUNES.replace(hour=19, minute=31))
    assert jm.activo() is not None


def test_se_va_si_nadie_lo_mata(limpio, monkeypatch):
    jm.aparecer(6)
    m = jm.activo()
    jm._ACTIVO['fin'] = 0
    jm.tick(LUNES.replace(hour=15))
    assert jm.activo() is None and not m.vivo and m.entity_id not in app._SALAS_DEL_MUNDO[6].monstruos
    assert 'left' in limpio[-1]


def test_premios_segun_el_puesto_en_el_dano(limpio, monkeypatch):
    jm.aparecer(37)
    m = jm.activo()
    jug = [NS(personaje=NS(char_id=i, nombre='P%d' % i, nivel=50)) for i in range(1, 13)]
    monkeypatch.setattr(app, '_tw_sesiones', lambda: jug)
    dados, exp = [], {}
    monkeypatch.setattr(app, '_gm_dar_item', lambda s, it, n=1: dados.append((s.personaje.char_id, it)))
    monkeypatch.setattr(app, '_dar_exp_y_creditos', lambda s, exp=0, creditos=0: exp_.__setitem__(s.personaje.char_id, exp))
    exp_ = exp
    m.dano_por = {i: 1000 * (20 - i) for i in range(1, 13)}  # el 1 pega mas
    assert jm.al_morir(jug[0], m)
    cajas60 = set(range(89200, 89207))
    assert any(c == 1 and it in cajas60 for c, it in dados)  # el primero, su caja de nivel 60 seguro
    assert sum(1 for c, _ in dados if c == 1) == 2
    assert all(c != 5 or it not in cajas60 for c, it in dados)
    assert exp[1] > exp[2] > exp[5] > exp[12] > 0
    assert 'defeated' in limpio[-1] and '1. P1' in limpio[-1]
    assert jm.activo() is None


def test_comando_gm():
    assert app._gm_parsear('/worldboss status') == ('jefe_mundo', ['worldboss', 'status'])
    assert 'no world boss' in jm.comando(['worldboss'])
