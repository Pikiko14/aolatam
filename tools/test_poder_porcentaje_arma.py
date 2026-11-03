"""Panther Killing y Frozen Snipe pegan un % del ataque: 50, 60, 70, 80 y 100 del I al V, con 2 s de cooldown.

"El PK5 tiene 100 de stance power, quiere decir que pega el 100% del arma; ajusta los otros PK y sube el cooldown a
2 seg de uso; lo mismo en FS5" (02/11/2026)."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import combate

PANTHER = (710, 721, 732, 743, 754)
FROZEN = (906, 918, 932, 946, 960)


def test_del_i_al_v_pegan_50_60_70_80_y_100_por_ciento_del_ataque():
    for fam in (PANTHER, FROZEN):
        assert [combate.pct_del_arma(m) for m in fam] == [50, 60, 70, 80, 100]
        for m, pct in zip(fam, (50, 60, 70, 80, 100)):
            # % del ataque del personaje: el peso del golpe fisico por el multiplicador da justo el %.
            assert abs(combate.PESO_GOLPE_FISICO * combate.mult_fisico(m) - pct / 100.0) < 1e-9
            assert combate.stance_de(m) == 0      # el % no se suma ademas como ataque plano


def test_fs_iv_pega_el_80_por_ciento_del_ataque():
    """"debe ser el 80% del ataque del personaje incluyendo verde, buff y demas": con 1000 de ataque y sin defensa,
    800."""
    class Blanco(combate.Monstruo):
        defensa_efectiva = mdef_efectiva = 0

        def __init__(self):
            self.hp, self.debuffs, self.panico = 10 ** 9, {}, False
    assert Blanco().recibir(1000, mult=combate.mult_fisico(946), var_pct=0) == 800


def test_tienen_dos_segundos_de_cooldown():
    for m in PANTHER + FROZEN:
        assert combate.datos_magia(m)['cd_ms'] == 2000


def test_una_habilidad_con_stance_en_numero_sigue_sumandolo():
    assert combate.pct_del_arma(801) == 0
    assert combate.stance_de(801) == abs(int(combate.datos_magia(801).get('hp') or 0))
