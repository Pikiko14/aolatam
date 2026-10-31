"""La zona 71 del editor marca donde se aparece al entrar a un mapa (tools/llegada_mapa.py)."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import llegada_mapa as lm


def test_punto_en_poligono():
    cuadro = [(10, 40), (17, 40), (17, 47), (10, 47)]
    assert lm._dentro((14, 43), cuadro) and lm._dentro((10, 40), cuadro)
    assert not lm._dentro((18, 43), cuadro) and not lm._dentro((14, 39), cuadro)


def test_el_900_aparece_en_su_zona_71_en_casilla_pisable():
    mpc = RAIZ / 'tools' / 'mapas_propios' / 'map900.mpc'
    t = lm.casilla(900, mpc)
    assert t is not None and 10 <= t[0] <= 17 and 40 <= t[1] <= 47
    assert lm._pisa(mpc.read_bytes())(*t)
    assert lm.aplicar(900, mpc, escribir=False) in ([], [(7550010, [14, 44], list(t))])
