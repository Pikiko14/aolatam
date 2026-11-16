"""Hardiness del equipo (server/durabilidad.py, 16/11/2026): se gasta peleando, rota no da stats, se repara con oro."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import durabilidad as dur
import inventario as inv

ARMADURA, ARMA = 1488, 19832          # Ice Stone Armor (耐久 50, 價格 62806), FreshmanStick (耐久 30)


def _ses(oro=100000):
    return NS(personaje=NS(nombre='T', mejoras={}), inventario={inv.RANURA_CUERPO: ARMADURA, inv.RANURA_DERECHA: ARMA},
              oro=oro)


def _nada(*a, **k):
    pass


def test_el_arma_se_gasta_cada_GOLPES_ARMA_golpes_y_la_armadura_cada_GOLPES_ARMADURA_recibidos():
    s = _ses()
    for _ in range(dur.GOLPES_ARMA * 3):
        dur.golpe_dado(s, _nada, _nada)
    assert dur.actual(s, inv.RANURA_DERECHA) == inv.durabilidad(ARMA) - 3
    for _ in range(dur.GOLPES_ARMADURA * 2):
        dur.golpe_recibido(s, _nada, _nada)
    assert dur.actual(s, inv.RANURA_CUERPO) == 48


def test_rota_no_da_stats_y_reparar_cobra_lo_que_ensena_el_cliente():
    s = _ses()
    entera = inv.bonos_de_equipo(s.inventario, s.personaje.mejoras)['def']
    s.personaje.mejoras[inv.RANURA_CUERPO] = {'dur': 0}
    assert inv.bonos_de_equipo(s.inventario, s.personaje.mejoras)['def'] < entera
    assert dur.coste(s, inv.RANURA_CUERPO) == int(50 / 50 * 62806 * 0.05)
    hechas, oro, falta = dur.reparar(s, dur.reparables(s))
    assert hechas == [inv.RANURA_CUERPO] and oro == 3140 and not falta and s.oro == 100000 - 3140
    assert 'dur' not in (s.personaje.mejoras.get(inv.RANURA_CUERPO) or {})
    assert inv.bonos_de_equipo(s.inventario, s.personaje.mejoras)['def'] == entera


def test_sin_oro_no_repara():
    s = _ses(oro=10)
    s.personaje.mejoras[inv.RANURA_CUERPO] = {'dur': 25}
    assert dur.reparar(s, dur.reparables(s)) == ([], 0, True)
    assert dur.actual(s, inv.RANURA_CUERPO) == 25


def test_la_entrada_lleva_el_hardiness_gastado():
    e = inv.actualizar_ranura(1, inv.RANURA_CUERPO, ARMADURA, 1, b'\0' * 8, 1)
    e = inv.marcar_durabilidad(e, {'dur': 7})
    assert struct.unpack_from('<I', e, 6 + inv.OFF_DURABILIDAD)[0] == 7
