"""Al sentarse, los demas le ven sentado y no tumbado (05/11/2026: "porque baco sale muerto si esta sentado??").

El 0x000A con el 8 es "sentado" para el propio personaje; reenviado a los demas era la pose tumbada. A ellos va el 7.
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import login  # noqa: E402
import presencia  # noqa: E402


def _ses(nombre):
    p = login.Personaje(hp=100, hp_max=100)
    p.nombre, p.stage = nombre, 41
    r = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, usuario=None, muerto=False,
           recibido=r, _mapa_presencia=41, enviar=lambda *pk: r.extend(pk),
           enviar_inmediato=lambda *pk: r.extend(pk), enviar_sin_espejo=lambda *pk: r.extend(pk))
    return s


def _accion(paquetes, eid):
    return [struct.unpack_from('<III', x, 2)[2] for x in paquetes
            if x[:2] == struct.pack('<H', 0x000A) and struct.unpack_from('<I', x, 2)[0] == eid]


def test_sentarse_8_para_mi_7_para_los_demas():
    presencia._POR_MAPA.clear()
    baco, zetha = _ses('Baco'), _ses('Zetha')
    presencia._POR_MAPA[41] = [baco, zetha]
    srv = app.Servidor.__new__(app.Servidor)
    srv.manejar(baco, 0x0016, None, None, 't', struct.pack('<BI', 4, 0))
    assert _accion(baco.recibido, baco.personaje.entity_id) == [8]
    assert _accion(zetha.recibido, presencia.entidad_de(baco)) == [7]
    srv.manejar(baco, 0x0016, None, None, 't', struct.pack('<BI', 4, 0))       # se levanta
    assert _accion(zetha.recibido, presencia.entidad_de(baco)) == [7, 0]
