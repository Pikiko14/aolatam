"""Piezas de robot (機甲零件): Producing Fast Gear, Collecting Energy Core..."""
import pathlib
import sys
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import inventario as inv

ROBOT = 19814           # Freshman Cask
GEAR3 = 3789            # Producing Fast Gear Lvl 3: carga 3000, fabricacion +9%, nivel 50
CORE3 = 3788            # Collecting Energy Core Lvl 3: carga 3000, recoleccion +9%
GEAR5 = 7201            # Producing Lvl 5 Fast Gear: fabricacion +15%, nivel 70


def test_las_piezas_salen_del_cliente():
    assert inv.pieza_de_robot(GEAR3) == {'tipo': '33', 'nivel': 50, 'fabricacion_pct': 9, 'recoleccion_pct': 0}
    assert inv.pieza_de_robot(CORE3)['recoleccion_pct'] == 9
    assert inv.pieza_de_robot(2856)['tipo'] == '31'
    assert inv.pieza_de_robot(ROBOT) is None and inv.pieza_de_robot(2024) is None


def test_suman_con_el_robot_puesto():
    con = {10: {'piezas': {'33': GEAR3}}}
    base = inv.bonos_de_equipo({10: ROBOT}, {})
    puesto = inv.bonos_de_equipo({10: ROBOT}, con)
    assert puesto['carga'] == base['carga'] + 3000
    assert puesto['hp'] == base['hp'] + inv._bonus(GEAR3)['hp']
    assert inv.velocidad_de_equipo({10: ROBOT}, con, 'fabricacion_pct') == 9
    assert inv.velocidad_de_equipo({25: ROBOT}, {25: {'piezas': {'33': GEAR3}}}, 'fabricacion_pct') == 0


def test_la_ficha_ensena_sus_stats():
    extras = inv.extras_visibles({'piezas': {'33': GEAR3, '31': CORE3}})
    assert extras['peso'] == 6000
    assert extras['fabricacion'] == 9 and extras['recoleccion'] == 9


def test_la_velocidad_en_la_ficha_se_puede_apagar(monkeypatch):
    monkeypatch.setitem(inv.ID_EXTRA, 'fabricacion', 0)
    assert 'fabricacion' not in inv.extras_visibles({'piezas': {'33': GEAR3}})
    entrada = inv.marcar_extras(bytes(40), {'fabricacion': 9})
    assert entrada == bytes(40)


def test_la_fabricacion_usa_la_pieza_y_los_buffs():
    p = types.SimpleNamespace(buffs={}, mejoras={10: {'piezas': {'33': GEAR3}}})
    assert app._pct_fabricacion(p, {10: ROBOT}) == 9


@pytest.fixture
def ses(monkeypatch):
    monkeypatch.setattr(app, '_refrescar', lambda s, ranuras, con_oro=False: [])
    monkeypatch.setattr(app, '_stats_ses', lambda s: b'stats')
    monkeypatch.setattr(app, '_guardar_bolsa', lambda s, cid: None)
    s = types.SimpleNamespace(inventario={10: ROBOT, 20: GEAR3, 21: GEAR5}, cantidades={20: 2}, paquetes=[],
                              personaje=types.SimpleNamespace(char_id=1, nivel=80, mejoras={}))
    s.enviar = lambda *pk: s.paquetes.extend(pk)
    return s


def instalar(s, ranura, objetivo=10):
    app._usar_pieza_robot(s, 'test', ranura, objetivo, inv.pieza_de_robot(s.inventario[ranura]))


def test_se_instala_y_gasta_una(ses):
    instalar(ses, 20)
    assert ses.personaje.mejoras[10]['piezas'] == {'33': GEAR3} and ses.cantidades[20] == 1


def test_una_por_tipo_la_nueva_reemplaza(ses):
    instalar(ses, 20)
    instalar(ses, 21)
    assert ses.personaje.mejoras[10]['piezas'] == {'33': GEAR5}


def test_reemplaza_tambien_la_que_vino_del_guardado(ses):
    ses.personaje.mejoras = {10: {'piezas': {33: GEAR3}}}
    instalar(ses, 21)
    assert ses.personaje.mejoras[10]['piezas'] == {'33': GEAR5}


def test_el_guardado_conserva_piezas_y_fuel(monkeypatch):
    import cuentas
    guardado = {}
    monkeypatch.setattr(cuentas, '_actualizar_personaje', lambda u, c, mut: mut(guardado))
    cuentas.guardar_mejoras('u', 1, {10: {'piezas': {'33': GEAR3}}, 26: {'fuel': {'carga': 1}}, 30: {}})
    assert set(guardado['mejoras']) == {'10', '26'}


def test_pide_el_nivel_del_personaje(ses):
    ses.personaje.nivel = 40
    instalar(ses, 20)
    assert not ses.personaje.mejoras and ses.cantidades[20] == 2


def test_sin_robot_no_se_gasta(ses):
    ses.inventario = {20: GEAR3}
    instalar(ses, 20, None)
    assert not ses.personaje.mejoras and ses.cantidades[20] == 2
