"""La defensa del jugador frente a los golpes de los monstruos (combate.dano_recibido)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))

import combate


def test_cuadra_con_lo_medido_en_la_captura():
    """"porque los mobs pegan tanto": Thunder Rabbit (Atk 173 + Fuego 15) contra el jugador de la captura del
    servidor privado, segun su Dfs. Con la formula de antes salian 94 a 125."""
    medido = {241: 29, 343: 21, 421: 16, 444: 14, 478: 12, 502: 11}
    for dfs, dano in medido.items():
        assert abs(combate.dano_recibido(173, dfs, elem_atk=15) - dano) <= 1, dfs


def test_un_bicho_flojo_pega_poco_pero_pega():
    """La Lily (Atk 23) a una maga con 23 de defensa: algo, no 1 ni 22."""
    assert 1 < combate.dano_recibido(23, 23) < 10
    assert combate.dano_recibido(23, 5000) == 1


def test_mas_defensa_nunca_pega_mas():
    for atk in (10, 300, 5000):
        golpes = [combate.dano_recibido(atk, d) for d in range(0, 6000, 50)]
        assert golpes == sorted(golpes, reverse=True) and min(golpes) >= 1


def test_el_elemental_que_pasa_suma_como_ataque():
    assert combate.dano_recibido(23, 23, elem_atk=10, elem_def=4) > combate.dano_recibido(23, 23)
    assert combate.dano_recibido(23, 23, elem_atk=10, elem_def=40) == combate.dano_recibido(23, 23)


def test_las_fisicas_usan_su_poder_y_nunca_pasan_de_1_35():
    """"con mi arquero pego 2k con slow snipe eso esta roto": la formula 15 da 0,76 (medido con Thunder Sword III)."""
    assert combate.mult_fisico(904) == 0.76            # Slow Snipe I
    assert combate.mult_fisico(943) == 0.76            # Basic Shot IV
    assert combate.mult_fisico(15523) == combate.MULT_SIN_RAMA     # Holy Guard I: no 18x


def test_el_fisico_sin_recorte():
    """El -30% (\"sigue pegando mucho el fisico\") se quito: FACTOR_DANO_FISICO 1.0."""
    assert combate.FACTOR_DANO_FISICO == 1.0
