"""Los jefes (王) reaparecen a los 20 minutos; el resto a los 20 s (06/11/2026)."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate as cb  # noqa: E402


def _un_jefe():
    cb.es_jefe(0)
    return next(iter(cb._JEFES))


def test_jefe_20_minutos():
    assert cb.segundos_reaparicion(NS(npc_type=_un_jefe())) == 20 * 60


def test_bicho_normal_20_segundos():
    normal = next(i for i in range(1, 5000) if not cb.es_jefe(i))
    assert cb.segundos_reaparicion(NS(npc_type=normal)) == 20


def test_el_evento_manda():
    assert cb.segundos_reaparicion(NS(npc_type=_un_jefe(), daily_respawn=30)) == 30
