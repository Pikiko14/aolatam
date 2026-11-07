"""Power Shield (法力護盾): el dano se paga con MP hasta el tope del nivel y anula Silence (06/11/2026)."""
import pathlib
import sys
import time
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import avatar_clones as ac  # noqa: E402


def _ses(mp, buffs):
    enviados = []
    pj = NS(entity_id=1001, mp=mp, hp=2000, buffs=buffs)
    return NS(personaje=pj, enviar=lambda *p: enviados.extend(p), avatar_clon=None), enviados


def test_paga_con_mp_hasta_el_tope():
    ses, env = _ses(5000, {416: {'fin': time.time() + 30}})      # Power Shield I: 1350
    assert ac.absorber(ses, 1000) == 0 and ses.personaje.mp == 4000
    assert ac.absorber(ses, 1000) == 650 and ses.personaje.mp == 3650
    assert 416 not in ses.personaje.buffs                           # se gasto
    assert ac.absorber(ses, 100) == 100


def test_sin_mp_pasa_a_la_vida():
    ses, _ = _ses(300, {420: {'fin': time.time() + 30}})
    assert ac.absorber(ses, 1000) == 700 and ses.personaje.mp == 0


def test_sin_escudo_no_toca_el_mp():
    ses, _ = _ses(500, {3: {'fin': time.time() + 30}})              # Silver Shield
    assert ac.absorber(ses, 200) == 200 and ses.personaje.mp == 500
    assert ac.escudo_mp_activo(ses) == (None, None)
