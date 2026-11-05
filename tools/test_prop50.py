"""Prop de 50 (04/11/2026): casillas 20-44 y 95-119 del Prop, 45.. de la Backpack, y el parche de angel.dat."""
import pathlib
import struct
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))

import app  # noqa: E402
import parche_prop50_exe as pp  # noqa: E402

EXE = RAIZ / 'parches' / 'juego' / 'angel.dat'


def test_sin_backpack_son_50_del_prop(monkeypatch):
    monkeypatch.setattr(app, '_casillas_mochila', lambda bolsa: 0)
    r = app._ranuras_bolsa({})
    assert r == list(range(20, 45)) + list(range(95, 120))
    lleno = {s: 1 for s in range(20, 45)}
    assert app._ranura_libre(lleno) == 95
    assert app._ranura_libre({s: 1 for s in r}) is None


def test_con_backpack_se_suman_sus_casillas(monkeypatch):
    monkeypatch.setattr(app, '_casillas_mochila', lambda bolsa: 15)
    r = app._ranuras_bolsa({})
    assert len(r) == 65 and r[-1] == 59 and 60 not in r
    lleno = {s: 1 for s in list(range(20, 45)) + list(range(95, 120))}
    assert app._ranura_libre(lleno) == 45
    assert app._tope_bolsa({}) == 119


def test_desde_y_hasta_siguen_valiendo(monkeypatch):
    monkeypatch.setattr(app, '_casillas_mochila', lambda bolsa: 0)
    assert app._ranura_libre({}, desde=30) == 30
    assert app._ranura_libre({s: 1 for s in range(20, 45)}, desde=21) == 95
    assert app._ranura_libre({}, desde=617, hasta=620) == 617


def _ejecutar_despacho(d, ventana):
    """Simula el primer caso reescrito de 0x57b320 (solo el camino de eax)."""
    o = pp._off(d, pp.DESPACHO[0])
    codigo = d[o:o + 36]
    eax = (ventana - struct.unpack_from('<I', codigo, 4)[0]) & 0xFFFFFFFF
    if eax <= 24:
        return eax + 20
    eax = (eax - codigo[15]) & 0xFFFFFFFF
    if eax > codigo[18]:
        return None
    return eax + codigo[27] + 20


@pytest.mark.skipif(not EXE.is_file(), reason='sin parches/juego/angel.dat')
def test_parche_del_exe():
    d = EXE.read_bytes()
    if pp.lleva_el_parche(d):
        nuevo = d
    else:
        nuevo = pp.parchear(d)
        assert pp.lleva_el_parche(nuevo)
        with pytest.raises(SystemExit):
            pp.parchear(nuevo)
    assert _ejecutar_despacho(nuevo, 3101) == 20
    assert _ejecutar_despacho(nuevo, 3125) == 44
    assert _ejecutar_despacho(nuevo, 3151) == 95
    assert _ejecutar_despacho(nuevo, 3175) == 119
    assert _ejecutar_despacho(nuevo, 3126) is None
    assert _ejecutar_despacho(nuevo, 3176) is None
    assert _ejecutar_despacho(nuevo, 3801) is None      # sigue al caso de la Backpack
    for _i, _r, _d, tope_va, _v, tope, _de, _a in pp.BUCLES:
        assert nuevo[pp._off(nuevo, tope_va) + 3] == tope
