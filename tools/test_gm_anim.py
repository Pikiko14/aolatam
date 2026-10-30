"""/anim <tipo> <animacion>: prueba en vivo el golpe basico (0x000A) de la propia sesion.
Las animaciones de arco y de arma+escudo no estan medidas: asi se eligen en el juego."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate as cb
import gm
import login


def _golpe(prueba=None):
    p = login.Personaje(hp=20000, hp_max=100000, mp=50000, mp_max=150000)
    p.tile_x, p.tile_y = 100, 100
    m = cb.Monstruo(9999, 999999, 'Dummy', (100, 100))
    m.hp = m.hp_max = 10 ** 9
    packets = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={3: 10},
           monstruos={9999: m}, usuario=None, muerto=False, objetivo_actual=None,
           enviar=lambda *pk: packets.extend(pk), enviar_inmediato=lambda *pk: packets.extend(pk))
    if prueba is not None:
        gm.aplicar(s, gm.parsear(prueba))
    app.Servidor.__new__(app.Servidor).manejar(
        s, 0x0006, None, None, 'test', struct.pack('<HI', cb.ATAQUE_NORMAL, 9999))
    pk = next(x for x in packets if x[:2] == struct.pack('<H', 0x000A))
    return struct.unpack_from('<HH', pk, 10)


def test_sin_prueba_va_lo_de_la_tabla():
    assert _golpe() == cb.golpe_de_arma(10)


def test_anim_cambia_el_golpe_de_esa_sesion():
    assert _golpe('anim 2 827') == (2, 827)


def test_anim_off_vuelve_a_la_tabla():
    assert _golpe('anim off') == cb.golpe_de_arma(10)
