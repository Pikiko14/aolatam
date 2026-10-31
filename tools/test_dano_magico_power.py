""""fijate esto hay algo raro con los poderes de mago": Poison Hit I ("Spell power: 34-42") pegaba 4 a nivel 1."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate as cb


def test_el_power_se_suma_al_golpe():
    # Spl Atk 20, power 38 (Poison Hit I): 20 x 38/200 + 38 = 41,8, dentro del 34-42 del tooltip (antes 3,8).
    ataque = cb.spl_atk_con_power(20, 38, 200)
    assert abs(ataque * 38 / 200.0 - 41.8) < 1e-9


def test_a_nivel_alto_casi_no_cambia():
    # Forbidden Curse IV (power 1650) con Spl Atk 57.000: menos de un 1% mas.
    antes, ahora = 57000 * 1650 / 200.0, cb.spl_atk_con_power(57000, 1650, 200) * 1650 / 200.0
    assert 1.0 < ahora / antes < 1.01


def test_sin_power_no_se_toca():
    assert cb.spl_atk_con_power(500, 0, 200) == 500
