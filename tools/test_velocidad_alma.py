"""El alma anda a pie ("porque cuando estoy en modo alma camina rapido", 27/11/2026)."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402


def test_el_alma_no_lleva_la_velocidad_de_la_montura():
    ses = NS(personaje=NS(buffs={}, nombre='x'), inventario={app.RANURA_MONTURA: 3722}, fantasma=False, muerto=False)
    assert app._velocidad_de(ses) > app.VELOCIDAD_JUGADOR             # montado
    ses.fantasma = ses.muerto = True
    assert app._velocidad_de(ses) == app.VELOCIDAD_JUGADOR
    ses.fantasma = ses.muerto = False                                  # revive: vuelve la montura
    assert app._velocidad_de(ses) > app.VELOCIDAD_JUGADOR
