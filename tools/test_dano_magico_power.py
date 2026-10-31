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


def test_el_golpe_va_del_minimo_al_maximo_del_power():
    """"no tendria que contar el ataque minimo y maximo de la spell o aoe??": Poison Hit I es 38 +- 4."""
    import random
    random.seed(3)
    var = cb.variacion_power(38, 4)
    assert abs(var - 4 / 38) < 1e-9
    m = cb.Monstruo(1, 1, 'Dummy', (0, 0))
    m.defensa = m.mdef = 0
    golpes = []
    for _ in range(400):
        m.hp = m.hp_max = 10 ** 6
        golpes.append(m.recibir(cb.spl_atk_con_power(20, 38, 200), es_magico=True, mult=38 / 200, var_pct=var))
    # power 34 -> 37,4 y power 42 -> 46,2 (con la mitigacion suave de recibir, algo menos)
    assert max(golpes) - min(golpes) >= 6
