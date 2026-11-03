"""Panther Killing y Frozen Snipe con el Stance power ORIGINAL del juego y 2 s de cooldown.

Estuvieron en 50/60/70/80/100% del ataque (02/11/2026); "deja los stance power originales de fs y pk" (03/11/2026):
PK 129/166/208/257 y PK V el 100% que trae el juego, FS 120/155/196/249/350. Un % del ataque sigue funcionando para
las filas que lo traen asi (HP定義 = 百分比: PK V, Web Trap)."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import combate

PANTHER = (710, 721, 732, 743, 754)
FROZEN = (906, 918, 932, 946, 960)


def test_tienen_su_stance_original():
    assert [combate.stance_de(m) for m in PANTHER] == [129, 166, 208, 257, 0]
    assert [combate.stance_de(m) for m in FROZEN] == [120, 155, 196, 249, 350]
    assert combate.pct_del_arma(754) == 100 and combate.mult_fisico(754) == 1.0     # PK V: el 100% del juego


def test_un_porcentaje_es_del_ataque_del_personaje():
    """Las filas en % (PK V) pegan ese % del ataque, con verdes y buffs, y luego la defensa: sin defensa, todo."""
    class Blanco(combate.Monstruo):
        defensa_efectiva = mdef_efectiva = 0

        def __init__(self):
            self.hp, self.debuffs, self.panico = 10 ** 9, {}, False
    assert Blanco().recibir(1000, mult=combate.mult_fisico(754), var_pct=0) == 1000


def test_tienen_dos_segundos_de_cooldown():
    for m in PANTHER + FROZEN:
        assert combate.datos_magia(m)['cd_ms'] == 2000


def test_una_habilidad_con_stance_en_numero_sigue_sumandolo():
    assert combate.pct_del_arma(801) == 0
    assert combate.stance_de(801) == abs(int(combate.datos_magia(801).get('hp') or 0))
