"""Las cartas por tiempo (EXP, skill EXP, Lucky, recoleccion, fabricacion) no se apilaban: cada duracion es
un hechizo distinto y quedaban todas puestas. Pedido del usuario: "Los items que son por dia no se
solapan es decir no pisa el que esta previamente en uso"."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import bolsas


def _usar(buffs, item):
    mid, entrada, _ = bolsas.buff_de(item, 0)
    for k in bolsas.cartas_pisadas(buffs, mid, entrada):
        buffs.pop(k)
    buffs[mid] = entrada
    return mid


def test_la_carta_nueva_pisa_a_la_de_su_familia():
    buffs = {}
    _usar(buffs, 4525)                 # Collection Speedup (30 days)
    _usar(buffs, 17646)                # Collection Speedup (3 days)
    assert list(buffs) == [6691]
    _usar(buffs, 498)                  # Collection Speedup (30 Minutes)
    assert list(buffs) == [1835]


def test_familias_distintas_conviven():
    buffs = {}
    _usar(buffs, 4524)                 # Double EXP (30 days)
    _usar(buffs, 17650)                # Double Skill Exp (30 days)
    _usar(buffs, 2019)                 # Lucky / Triple Loot
    _usar(buffs, 4526)                 # Make Speedup (30 days)
    _usar(buffs, 4525)                 # Collection Speedup (30 days)
    assert len(buffs) == 5


def test_una_carta_guardada_sin_campo_carta_tambien_se_pisa():
    buffs = {}
    _usar(buffs, 4524)
    buffs[1935].pop('carta')           # como las guardadas antes de este cambio
    _usar(buffs, 27057)                # Double EXP (15 days)
    assert list(buffs) == [1886]
