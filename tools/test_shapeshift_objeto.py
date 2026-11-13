"""Los objetos de Shapeshifting transforman al usarlos (13/11/2026, "al usar los shape no me transforma de inmediato,
debo pasar a otro mapa"): el buff del objeto lleva es_transform y el sprite del hechizo."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import bolsas  # noqa: E402


def test_el_buff_del_objeto_es_una_transformacion():
    mid, entrada, dur = bolsas.buff_de(69517, 0)                    # Rock-loving Adventurer (1 Day)
    assert mid == 21448 and dur == 86400000
    assert entrada['es_transform'] and entrada['trans_sprite'] == 111318


def test_un_buff_normal_no_transforma():
    r = bolsas.buff_de(3460, 0)                                      # Pet's Double EXP Card
    assert r is None or not r[1].get('es_transform')
