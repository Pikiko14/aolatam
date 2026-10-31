"""Bloody Storm sin vida suficiente no se lanza, y el ritmo del paso de la mascota."""
import pathlib
import sys
from types import SimpleNamespace

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate as cb


def _ses(hp, mp=10_000):
    enviados = []
    p = SimpleNamespace(hp=hp, mp=mp, hp_max=1000, mp_max=mp, nivel=80, buffs={}, habilidades=[],
                        entity_id=7)
    return SimpleNamespace(personaje=p, enviar=lambda *a: enviados.extend(a), enviados=enviados), enviados


def test_bloody_storm_sin_vida_no_se_lanza(monkeypatch):
    monkeypatch.setattr(app, '_vida_max', lambda p: 1000)
    mag = cb.datos_magia(611)                         # Bloody Storm I: 20% de la vida
    assert mag['hp'] == -20 and mag['sp_gana']
    ses, enviados = _ses(hp=200)                      # justo el coste: no alcanza
    assert not app._puede_pagar(ses, mag)
    assert enviados, 'avisa al jugador'
    ses, _ = _ses(hp=201)
    assert app._puede_pagar(ses, mag)


def test_sin_mana_no_cobra_la_vida(monkeypatch):
    monkeypatch.setattr(app, '_vida_max', lambda p: 1000)
    mag = cb.datos_magia(655)                         # Bloody Storm V: 93 de MP
    ses, _ = _ses(hp=1000, mp=10)
    assert not app._puede_pagar(ses, mag)
    assert ses.personaje.hp == 1000


def test_una_habilidad_normal_no_mira_la_vida():
    ses, _ = _ses(hp=1)
    assert app._puede_pagar(ses, {'mp': 0, 'hp': 0})


def test_el_tramo_dura_lo_que_tarda_el_cliente():
    # speed 110 son 275 px/s: 8 casillas (256 px) en ~0,93 s, no en 2,3 s.
    assert abs(cb.segundos_de_tramo(8, 110) - 256 / 275) < 1e-9
    assert cb.segundos_de_tramo(1, 275) < cb.segundos_de_tramo(1, 110)
