"""Sin SP suficiente el hechizo se cortaba sin avisar, y en otros caminos se cobraba el SP
antes de mirar el mana (sin mana se perdia el SP). Ahora SP y mana se comprueban antes de
gastar nada. Reportado por el usuario: "debe validar si tenemos sp para usar un spell"."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate as cb
import login

CROSS_CHOP = 605   # Sword, cuesta 2000 SP y 0 MP


def _lanzar(sp, mp=50000, magic=CROSS_CHOP):
    p = login.Personaje(hp=20000, hp_max=100000, mp=mp, mp_max=150000)
    p.tile_x, p.tile_y = 100, 100
    p.habilidades = [(9, 50, 0)]   # Sword
    m = cb.Monstruo(9999, 999999, 'Dummy', (100, 100))
    m.hp = m.hp_max = 10 ** 9
    packets = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={3: 10}, sp=sp,
           monstruos={9999: m}, usuario=None, muerto=False, objetivo_actual=None,
           enviar=lambda *pk: packets.extend(pk), enviar_inmediato=lambda *pk: packets.extend(pk))
    app.Servidor.__new__(app.Servidor).manejar(s, 0x0006, None, None, 'test',
                                                struct.pack('<HI', magic, 9999))
    return s, m, packets


def test_cross_chop_cuesta_sp():
    assert cb.datos_magia(CROSS_CHOP)['cost_sp'] == 2000


def test_sin_sp_avisa_y_no_pega():
    s, m, packets = _lanzar(sp=500)
    assert any(b'Not enough SP' in p for p in packets)
    assert m.hp == m.hp_max and s.sp == 500
    assert CROSS_CHOP not in (getattr(s, 'ultimo_uso', None) or {})   # sin cooldown


def test_con_sp_pega_y_lo_cobra():
    s, m, packets = _lanzar(sp=5000)
    assert not any(b'Not enough SP' in p for p in packets)
    assert s.sp < 5000
