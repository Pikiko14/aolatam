"""Abandonar misiones: la cadena del Lyceum no se borra, pero se avisa (05/11/2026)."""
import pathlib
import sys
from types import SimpleNamespace

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import login  # noqa: E402
import misiones  # noqa: E402


def _ses(quests):
    pk = []
    p = login.Personaje(nombre='Prueba')
    p.quests = list(quests)
    return SimpleNamespace(personaje=p, usuario=None, addr='t', enviar=lambda *a: pk.extend(a)), pk


def test_la_101_no_se_borra_y_se_avisa():
    s, pk = _ses([(101, 1)])
    assert not misiones.abandonar_mision(s, 101)
    assert s.personaje.quests == [(101, 1)]
    assert any(b'cannot be abandoned' in x for x in pk if isinstance(x, (bytes, bytearray)))


def test_una_normal_si_se_borra():
    s, pk = _ses([(101, 1), (558, 2)])
    assert misiones.abandonar_mision(s, 558)
    assert s.personaje.quests == [(101, 1)]
