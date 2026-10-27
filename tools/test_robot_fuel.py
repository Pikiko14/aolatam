"""Mighty Fuel sobre robots (使用目標="目標機甲"): carga extra mientras dura."""
import pathlib
import sys
import time
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import inventario as inv

ROBOT = 19814          # Freshman Cask, el robot de productor


@pytest.mark.parametrize('item,carga,segundos', [
    (1961, 2000, 8 * 3600), (2022, 5000, 86400), (2023, 5000, 7 * 86400), (2024, 5000, 30 * 86400),
    (6053, 10000, 86400), (6054, 10000, 7 * 86400), (6055, 10000, 30 * 86400), (8820, 5000, 86400)])
def test_cada_fuel_trae_la_carga_y_duracion_de_su_magia(item, carga, segundos):
    uso = inv.uso_en_robot(item)
    assert (uso['carga'], uso['segundos']) == (carga, segundos)


def test_los_fuel_de_ataque_y_defensa_no_son_de_carga():
    assert inv.uso_en_robot(235) is None and inv.uso_en_robot(236) is None


def carga(bolsa, mejoras):
    return inv.bonos_de_equipo(bolsa, mejoras)['carga']


def test_la_carga_solo_suma_con_el_robot_puesto_y_sin_caducar():
    base = carga({10: ROBOT}, {})
    vivo = {'fuel': {'carga': 5000, 'fin': time.time() + 60}}
    assert carga({10: ROBOT}, {10: vivo}) == base + 5000
    assert carga({10: ROBOT}, {10: {'fuel': {'carga': 5000, 'fin': time.time() - 1}}}) == base
    assert carga({25: ROBOT}, {25: vivo}) == carga({25: ROBOT}, {})


def test_la_ficha_del_robot_ensena_la_carga_del_fuel_mientras_dura():
    vivo = {10: {'fuel': {'carga': 5000, 'fin': time.time() + 60}}}
    muerto = {10: {'fuel': {'carga': 5000, 'fin': time.time() - 1}}}
    entrada = lambda mej: inv.actualizar_ranuras(1, [(10, ROBOT, 1, None)], mejoras=mej)[6:]
    assert inv.leer_extras(entrada(vivo)) == {'peso': 5000}
    assert inv.leer_extras(entrada(muerto)) == {}


def test_se_suma_al_peso_verde_del_martillo():
    m = {'extra': {'peso': 300}, 'fuel': {'carga': 5000, 'fin': time.time() + 60}}
    assert inv.extras_visibles(m) == {'peso': 5300}
    assert m['extra'] == {'peso': 300}


@pytest.fixture
def ses(monkeypatch):
    monkeypatch.setattr(app, '_refrescar', lambda s, ranuras, con_oro=False: [])
    monkeypatch.setattr(app, '_stats_ses', lambda s: b'stats')
    monkeypatch.setattr(app, '_guardar_bolsa', lambda s, cid: None)
    s = types.SimpleNamespace(inventario={10: ROBOT, 20: 2024}, cantidades={20: 2}, paquetes=[],
                              personaje=types.SimpleNamespace(char_id=1, mejoras={}))
    s.enviar = lambda *pk: s.paquetes.extend(pk)
    return s


def usar(s, objetivo):
    app._usar_fuel_robot(s, 'test', 20, objetivo, inv.uso_en_robot(s.inventario[20]))


def test_se_aplica_al_robot_y_gasta_una(ses):
    usar(ses, 10)
    fuel = ses.personaje.mejoras[10]['fuel']
    assert fuel['carga'] == 5000 and fuel['fin'] > time.time() + 29 * 86400
    assert ses.cantidades[20] == 1


def test_no_se_acumula_con_otro_activo(ses):
    usar(ses, 10)
    usar(ses, 10)
    assert ses.cantidades[20] == 1


def test_sirve_en_un_robot_de_la_mochila(ses):
    ses.inventario = {30: ROBOT, 20: 2024}
    usar(ses, 30)
    assert 'fuel' in ses.personaje.mejoras[30]


def test_sin_robot_no_se_gasta(ses):
    ses.inventario = {20: 2024}
    usar(ses, None)
    assert ses.cantidades[20] == 2 and not ses.personaje.mejoras
