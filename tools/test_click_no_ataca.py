"""Cualquier clic sobre un bicho le pegaba: el clic (0x0005) llevaba un ataque forzado, aunque
el ataque basico lo pide el cliente aparte con el 0x0016 accion 0x0C (medido en Celestia).
Reportado por el usuario: "cualquier click ataca los moobs"."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate as cb
import login


def _sesion():
    p = login.Personaje(hp=20000, hp_max=100000, mp=50000, mp_max=150000)
    p.tile_x, p.tile_y = 100, 100
    m = cb.Monstruo(9999, 999999, 'Dummy', (100, 100))
    m.hp = m.hp_max = 10 ** 9
    packets = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={3: 10}, cantidades={},
           monstruos={9999: m}, usuario=None, muerto=False, objetivo_actual=None,
           enviar=lambda *pk: packets.extend(pk), enviar_inmediato=lambda *pk: packets.extend(pk))
    return s, m, packets


def _golpes(packets):
    return [pk for pk in packets if pk[:2] == struct.pack('<H', 0x000A)]


def test_el_clic_solo_selecciona():
    s, m, packets = _sesion()
    app.Servidor.__new__(app.Servidor).manejar(s, 0x0005, None, None, 'test', struct.pack('<IH', 9999, 0))
    assert s.objetivo_actual == 9999
    assert not _golpes(packets) and m.hp == m.hp_max


def test_el_ataque_basico_sigue_por_0x0016():
    s, m, packets = _sesion()
    s.objetivo_actual = 9999
    app.Servidor.__new__(app.Servidor).manejar(s, 0x0016, None, None, 'test', struct.pack('<BI', 0x0C, 9999))
    assert _golpes(packets)
