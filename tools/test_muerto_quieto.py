"""Un muerto que pide andar se queda donde murio ("me mataron y puedo caminar", 11/11/2026)."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'proto'))
import app  # noqa: E402


def _ses():
    enviados = []
    p = NS(entity_id=1014, nombre='Zetha', tile_x=285, tile_y=7, hp=0)
    return NS(personaje=p, muerto=True, fantasma=False, monstruos={77: object()},
              enviar=lambda *a: enviados.extend(a), enviados=enviados, inventario={})


def test_el_muerto_vuelve_a_su_casilla_y_se_le_repite_la_muerte_sin_inundar():
    s = _ses()
    app._muerto_quieto(s)
    ops = [struct.unpack_from('<H', bytes(x))[0] for x in s.enviados]
    assert ops[:2] == [0x006D, 0x0005] and 0x000A in ops
    s.enviados.clear()
    app._muerto_quieto(s)                                   # al momento: solo devolverlo, sin repetir la muerte
    assert [struct.unpack_from('<H', bytes(x))[0] for x in s.enviados] == [0x006D, 0x0005]
