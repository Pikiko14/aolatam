"""Seccion de stats del martillo verde en el tooltip (16/11/2026): tools/parche_tooltip_verde.py."""
import pathlib
import struct
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
sys.path.insert(0, str(RAIZ / 'server'))
import parche_tooltip_verde as pv  # noqa: E402
from parche_canal_lua import _off, _secciones  # noqa: E402

ANGEL = RAIZ / 'parches' / 'juego' / 'angel.dat'
SIN = RAIZ / 'parches' / 'juego' / 'angel.dat.sin_verde'


def _base():
    for ruta in (SIN, ANGEL):
        if ruta.exists():
            d = ruta.read_bytes()
            if not pv.lleva_el_parche(d):
                return d
    pytest.skip('no hay un angel.dat sin el parche del tooltip verde')


def test_el_gancho_salta_a_la_seccion_nueva_y_vuelve():
    d = _base()
    nuevo = pv.parchear(d)
    assert pv.lleva_el_parche(nuevo)
    sec = [s for s in _secciones(nuevo)[2] if s['nombre'] == pv.NOMBRE_SECCION][0]
    va = 0x400000 + sec['va']
    o = _off(nuevo, pv.GANCHO_EN)
    assert nuevo[o] == 0xE9
    assert pv.GANCHO_EN + 5 + struct.unpack_from('<i', nuevo, o + 1)[0] == va
    assert nuevo[o + 5:o + 7] == b'\x90\x90'
    # Despues del gancho el exe de antes no cambia (delante si: la cabecera PE lleva la seccion nueva).
    assert nuevo[o + 7:len(d)] == d[o + 7:]
    codigo = nuevo[sec['rptr']:sec['rptr'] + sec['vsz']]
    assert pv.GANCHO_ORIGINAL in codigo
    assert pv.CABECERA in codigo and pv.LINEA in codigo


def test_no_se_aplica_dos_veces():
    d = pv.parchear(_base())
    with pytest.raises(SystemExit):
        pv.parchear(d)


def _valido(registros):
    """Lo mismo que mira el codigo del parche antes de pintar nada."""
    for r in registros:
        if not r:
            continue
        if r & 0x00FF0000 or not (1 <= r >> 26 <= pv.ID_MAX):
            return False
    return True


def test_los_registros_del_servidor_pasan_y_el_nombre_de_una_mascota_no():
    import inventario as inv
    entrada = bytes(120)
    e = inv.marcar_extras(entrada, {'hp': 53, 'atk': 144, 'velocidad': 40, 'ranuras': 9, 'fabricacion': 3})
    regs = list(struct.unpack_from('<5I', e, inv.OFF_EXTRAS))
    assert all(regs) and _valido(regs)
    assert [r & 0x3FFFFFF for r in regs] == [53, 144, 40, 9, 3]
    nombre = b'Water Elf\0' + bytes(10)
    assert not _valido(struct.unpack_from('<5I', nombre, 0))
