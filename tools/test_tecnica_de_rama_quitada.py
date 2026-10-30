"""Al cambiar de rama de arma en el Skill Angel (Axe -> Spear), los iconos de
la rama vieja seguian en la barra y el servidor dejaba lanzarlos: nunca
comprobaba que esa rama siguiera puesta. Reportado por el usuario: "Si soy
axe, y me cambio a spear 1 no me quita los poderes de axe y 2 me deja usarlos
siendo spear"."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate as cb
import login
import skills

BASIC_BEATING = 701   # Basic Beating I, tecnica de Axe (rama 10)


def _atacar(habilidades):
    p = login.Personaje(hp=20000, hp_max=100000, mp=50000, mp_max=150000)
    p.tile_x, p.tile_y = 100, 100
    p.habilidades = habilidades
    m = cb.Monstruo(9999, 999999, 'Dummy', (100, 100))
    m.hp = m.hp_max = 10 ** 9   # que no muera: aqui solo importa si el golpe entra
    packets = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={3: 19832},
           monstruos={9999: m}, usuario=None, muerto=False, objetivo_actual=None, sp=5000,
           enviar=lambda *pk: packets.extend(pk), enviar_inmediato=lambda *pk: packets.extend(pk))
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s, 0x0006, None, None, 'test', struct.pack('<HI', BASIC_BEATING, 9999))
    return packets, m


def test_basic_beating_es_de_axe():
    assert skills.skill_de_magia(BASIC_BEATING) == 10


def test_con_spear_ya_no_se_puede_usar_la_tecnica_de_axe():
    packets, m = _atacar([(11, 30, 0), (12, 1, 0)])   # Spear + Enhance, sin Axe
    assert not packets
    assert m.hp == m.hp_max


def test_con_axe_puesto_la_tecnica_sigue_funcionando():
    packets, _ = _atacar([(10, 30, 0), (12, 1, 0)])   # Axe + Enhance
    assert packets
