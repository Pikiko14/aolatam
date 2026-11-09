"""Parche defensivo (08/11/2026): al cargar un mapa normal se apagan las marcas de aro del propio personaje.

"acabo de transportarme de aurora a shadow y me sale ese aro azul" ... "sali y entre y ya no esta pero no deberia
pasar eso". En los mapas donde alguna le puede tocar (Totem War, outpost, competiciones...) o con Trade Routes en
disputa no se manda nada: esas marcas las ponen sus modulos.
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import login  # noqa: E402
import totem_war  # noqa: E402
import trade_routes  # noqa: E402


def _ses(stage):
    p = login.Personaje()
    p.stage = stage
    return NS(personaje=p)


def _codigos(pk):
    return sorted(x[7] for x in pk if x[:2] == struct.pack('<H', 0x001D))


def test_en_un_mapa_normal_apaga_las_cuatro_marcas(monkeypatch):
    monkeypatch.setattr(trade_routes, '_ENCARGOS', {})
    pk = app._paquetes_aros_apagados(_ses(26))                 # Dark City
    assert _codigos(pk) == [22, 36, 38, 42]
    pvp = [x for x in pk if x[7] == 22][0]
    assert struct.unpack_from('<I', pvp, 8)[0] == 0           # apagado


def test_en_totem_war_no_toca_nada(monkeypatch):
    monkeypatch.setattr(trade_routes, '_ENCARGOS', {})
    st = next(s for s in range(1, 400) if totem_war.es_mapa_tw(s))
    assert app._paquetes_aros_apagados(_ses(st)) == ()


def test_con_trade_routes_en_disputa_no_toca_nada(monkeypatch):
    monkeypatch.setattr(trade_routes, '_ENCARGOS', {1: {'portador': 5}})
    assert app._paquetes_aros_apagados(_ses(26)) == ()
