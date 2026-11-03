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
            assert combate.mult_fisico(m) == pct / 100.0
            assert combate.stance_de(m) == 0      # el % no se suma ademas como ataque plano


def test_tienen_dos_segundos_de_cooldown():
    for m in PANTHER + FROZEN:
        assert combate.datos_magia(m)['cd_ms'] == 2000


def test_una_habilidad_con_stance_en_numero_sigue_sumandolo():
    assert combate.pct_del_arma(801) == 0
    assert combate.stance_de(801) == abs(int(combate.datos_magia(801).get('hp') or 0))
