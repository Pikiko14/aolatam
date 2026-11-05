"""Christmas Box (3861): vales de canje para pestles, ride feed y monturas (05/11/2026).

"que de los items de scroll para cambiar por ride, pestles y mount". Tiene tabla propia: la 3806 la comparte el 8300.
"""
import collections
import pathlib
import random
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import bolsas  # noqa: E402


def test_la_caja_da_vales_de_canje():
    random.seed(7)
    salen = collections.Counter(bolsas.abrir(3861) for _ in range(4000))
    assert salen[(bolsas.TICKET_PESTLE, 5)] > 1000 and salen[(bolsas.TICKET_RIDE, 5)] > 1000
    assert salen[(bolsas.MOUNT_COIN, 3)] > 600
    assert not [s for s in salen if s[0] in (1585, 1588, 1577, 1581, 1907)]        # ya no pan ni sopa


def test_la_tabla_3806_sigue_igual_para_el_8300():
    assert 1585 in {i for i, _c, _p in bolsas._opciones('3806')}
