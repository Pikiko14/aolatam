"""Un solo monstruo encantado por jugador (09/11/2026: "ahora puedo encantar a 3 mobs xd, no deberia poderse")."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402


def test_encantar_otro_suelta_el_anterior():
    viejo = NS(entity_id=7, nombre='Mob', encantado=True, charmed_objetivo=object(), encantado_expira=9e9,
               encanto_tipo=4321)
    enviados = []
    ses = NS(monstruo_encantado=viejo, enviar=lambda *a: enviados.extend(a))
    nuevo = NS(entity_id=8)
    app._soltar_encantado(ses, nuevo)
    assert not viejo.encantado and viejo.charmed_objetivo is None and ses.monstruo_encantado is None
    assert len(enviados) == 3


def test_reencantar_el_mismo_no_lo_suelta():
    m = NS(entity_id=7, encantado=True)
    ses = NS(monstruo_encantado=m, enviar=lambda *a: None)
    app._soltar_encantado(ses, m)
    assert m.encantado and ses.monstruo_encantado is m
