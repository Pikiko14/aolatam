"""Evento de Navidad: "que se dropeen con mob lvl 21 + ... 5%" y "el suitcase voucher tenga un 0.01 en las bolsas
de pd actuales"."""
import collections
import pathlib
import random
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import bolsas
import configuracion
import lyceum_services as ly


def test_el_pd_voucher_cae_al_5_por_ciento_en_mobs_21_o_mas():
    assert configuracion.DROPS_EVENTO[82665] == 0.05
    random.seed(4)
    n = 20000
    sale = sum(1 for _ in range(n) for it, _c in ly.straw_drop(3, 30) if it == 82665)
    assert 0.04 < sale / n < 0.06
    assert not ly.straw_drop(3, 20)                                    # nivel 20: nada


def test_las_maletas_pd_dan_el_suitcase_voucher_al_1_por_ciento():
    random.seed(6)
    n = 40000
    sale = collections.Counter(bolsas.abrir(89056)[0] for _ in range(n))
    assert 0.007 < sale[82664] / n < 0.013 and len(sale) == 11
