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


def test_una_habilidad_de_un_golpe_pega_1_35_el_basico():
    """Tendon Chop y PK IV contra el basico del mismo personaje, mismo mob (03/11/2026)."""
    assert abs(combate.mult_fisico(904) - 1.35) < 0.01         # Slow Snipe I
    assert abs(combate.mult_fisico(943) - 1.35) < 0.01         # Basic Shot IV
    assert combate.MULT_GOLPE_BASICO == 1.0
    assert combate.mult_fisico(15523) == combate.MULT_SIN_RAMA     # Holy Guard I: no 18x


def test_el_golpe_del_jugador_a_un_mob_es_el_medido():
    """Swordsman con R.Atk 2076 contra un Rock Slarm (Def 635): 883 de golpe basico en el juego (03/11/2026). Sale un
    ~6% por debajo, como sus otros cuatro golpes (ver K_GOLPE_A_MONSTRUO)."""
    class RockSlarm(combate.Monstruo):
        defensa_efectiva = mdef_efectiva = 635

        def __init__(self):
            self.hp, self.debuffs, self.panico = 10 ** 9, {}, False
    d = RockSlarm().recibir(2076, mult=combate.MULT_GOLPE_BASICO, var_pct=0)
    assert abs(d - 883) <= 883 * 0.08, d


def test_el_fisico_sin_recorte():
    """El -30% (\"sigue pegando mucho el fisico\") se quito: FACTOR_DANO_FISICO 1.0."""
    assert combate.FACTOR_DANO_FISICO == 1.0


def test_a_nivel_bajo_la_defensa_del_mob_pesa_mas():
    """"porque pegamos tanto": nivel 1 con R.Atk 45 contra un Slarm (Def 25) hace 26 en su servidor (03/11/2026)."""
    from types import SimpleNamespace

    class Slarm(combate.Monstruo):
        defensa_efectiva = mdef_efectiva = 25

        def __init__(self):
            self.hp, self.debuffs, self.panico = 10 ** 9, {}, False
    antes = combate.ATACANTE[0]
    try:
        combate.ATACANTE[0] = SimpleNamespace(personaje=SimpleNamespace(nivel=1, char_id=None))
        assert abs(Slarm().recibir(45, var_pct=0) - 26) <= 1
        combate.ATACANTE[0] = SimpleNamespace(personaje=SimpleNamespace(nivel=79, char_id=None))
        assert combate.k_golpe_a_monstruo() == combate.K_TOPE
    finally:
        combate.ATACANTE[0] = antes
