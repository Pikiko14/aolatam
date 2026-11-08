"""El Angel de una ciudad manda a sus ciudadanos al Angel Lyceum (08/11/2026: "no nos envia a lyceum").

La opcion 18 (20018 Aurora, 30018 Dark City, 40018 Iron Castle, 50018 Breeze Woods) reventaba con UnboundLocalError:
la rama del Director Wolay reconstruia CIUDAD_POR_FACCION con el mismo nombre y lo hacia local en todo manejar().
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import dialogos  # noqa: E402
import login  # noqa: E402

AURORA_ANGEL = 121613
OPCIONES = [20003, 20004, 20018, 20005]


def _ses(faccion):
    p = login.Personaje(hp=500, hp_max=500, mp=300, mp_max=300)
    p.nombre, p.stage, p.tile_x, p.tile_y, p.faction = 'Zetha', 3, 200, 120, faccion
    recibido = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, cantidades={}, monstruos={},
           usuario=None, muerto=False, viaje_pendiente=None,
           enviar=lambda *pk: recibido.extend(pk), enviar_inmediato=lambda *pk: recibido.extend(pk))
    s.dlg_ent = AURORA_ANGEL
    s.dlg_val = 112
    s.dlg_guion = [dialogos.armar_linea(20001, 112, OPCIONES)[2:]]
    s.dlg_paso = 1
    return s, recibido


def _elegir(s, opcion):
    srv = app.Servidor.__new__(app.Servidor)
    valor = dialogos.PRIMERA_OPCION + OPCIONES.index(opcion)
    srv.manejar(s, 0x000B, None, {'valor': valor}, 't', struct.pack('<B', valor))


def test_el_angel_de_aurora_manda_a_su_ciudadano_al_lyceum():
    s, _ = _ses('Aurora')
    _elegir(s, 20018)
    assert s.viaje_pendiente and s.viaje_pendiente[0] == 41


def test_el_angel_de_aurora_no_manda_a_un_ciudadano_de_otra_ciudad():
    s, _ = _ses('Beasts')
    _elegir(s, 20018)
    assert not s.viaje_pendiente
