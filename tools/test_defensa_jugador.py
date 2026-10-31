"""La defensa del jugador frente a los golpes de los monstruos (combate.dano_recibido)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))

import combate


def test_un_bicho_con_menos_ataque_que_tu_defensa_no_pega_1():
    """"la lily me baja 1 de dano a mi maguita": Lily tiene 23 de ataque."""
    assert combate.dano_recibido(23, 23) == 22
    assert 1 < combate.dano_recibido(23, 200) < 23


def test_la_defensa_resta_cuando_es_lo_que_mas_pega():
    assert combate.dano_recibido(50000, 30000) == 20000


def test_mas_defensa_nunca_pega_mas():
    for atk in (10, 300, 5000):
        golpes = [combate.dano_recibido(atk, d) for d in range(0, 6000, 50)]
        assert golpes == sorted(golpes, reverse=True) and min(golpes) >= 1


def test_el_elemental_se_suma():
    assert combate.dano_recibido(23, 23, elem_atk=10, elem_def=4) == 28
