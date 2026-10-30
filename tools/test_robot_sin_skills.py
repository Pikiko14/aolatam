"""Con un robot (機甲) en la ranura de montura se podian lanzar habilidades de rama.
Reportado por el usuario: "me deja usar skill con robot puestos no deberia"."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate as cb
import inventario as iv
import login

ROBOT = 19814          # FreshmanCask, categoria 機甲
BASIC_BEATING = 701    # tecnica de Axe


def _atacar(tipo, montura):
    p = login.Personaje(hp=20000, hp_max=100000, mp=50000, mp_max=150000)
    p.tile_x, p.tile_y = 100, 100
    p.habilidades = [(10, 30, 0)]   # Axe
    m = cb.Monstruo(9999, 999999, 'Dummy', (100, 100))
    m.hp = m.hp_max = 10 ** 9
    inv = {3: 19832}
    if montura:
        inv[app.RANURA_MONTURA] = montura
    packets = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario=inv, sp=5000,
           monstruos={9999: m}, usuario=None, muerto=False, objetivo_actual=None,
           enviar=lambda *pk: packets.extend(pk), enviar_inmediato=lambda *pk: packets.extend(pk))
    app.Servidor.__new__(app.Servidor).manejar(s, 0x0006, None, None, 'test',
                                                struct.pack('<HI', tipo, 9999))
    return packets, m


def test_el_cask_es_un_robot():
    assert iv.categoria_item(ROBOT) == '機甲'


def test_con_robot_no_hay_tecnicas():
    packets, m = _atacar(BASIC_BEATING, ROBOT)
    assert m.hp == m.hp_max
    assert any(b'robot' in pk for pk in packets)


def test_con_robot_el_golpe_normal_sigue():
    packets, _ = _atacar(cb.ATAQUE_NORMAL, ROBOT)
    assert any(pk[:2] == struct.pack('<H', 0x000A) for pk in packets)


def test_sin_robot_la_tecnica_funciona():
    _, m = _atacar(BASIC_BEATING, None)
    assert m.hp < m.hp_max
