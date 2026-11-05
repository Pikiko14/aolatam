"""Pestle y Ride Feed normales: al fallar desde +3, 30% de perder la pieza (05/11/2026)."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import mejoras as m  # noqa: E402


class Dados:
    def __init__(self, *valores):
        self.v = list(valores)

    def random(self):
        return self.v.pop(0)


def _probar(veces, dados, prob=m.PROB_PERDER):
    estado = {10: {'veces': veces, 'gemas': [], 'extra': {}, 'huecos': 0}}
    ok, msg = m.aplicar(estado, 10, 4457, 1, 'montura', rng=Dados(*dados), prob_perder=prob)
    return ok, msg, estado[10]['veces']


def test_falla_en_mas_3_y_se_pierde():
    assert _probar(3, (0.99, 0.10))[1] == m.PERDIDA


def test_falla_en_mas_3_y_solo_baja():
    ok, msg, veces = _probar(3, (0.99, 0.50))
    assert not ok and msg != m.PERDIDA and veces == 2


def test_lucky_nunca_pierde():
    ok, msg, veces = _probar(5, (0.99, 0.0), prob=0.0)
    assert msg != m.PERDIDA and veces == 4


def test_solo_los_normales():
    assert m.es_normal(3121) and m.es_normal(4457)
    assert not m.es_normal(6895) and not m.es_normal(7037)
