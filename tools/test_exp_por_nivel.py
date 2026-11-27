"""EXP segun la diferencia de nivel entre quien gana (jugador o mascota) y el mob (27/11/2026)."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate as c  # noqa: E402


def test_factor():
    assert c.factor_exp_nivel(57, 18) == c.EXP_PISO                   # le lleva 39: lo minimo
    assert c.factor_exp_nivel(57, 52) == 1.0                          # 5 de margen: entera
    assert abs(c.factor_exp_nivel(57, 50) - 0.8) < 1e-9
    assert abs(c.factor_exp_nivel(57, 60) - 1.12) < 1e-9              # mob mas alto: un poco mas
    assert c.factor_exp_nivel(57, 90) == c.EXP_TECHO
    assert c.factor_exp_nivel(0, 18) == 1.0 and c.factor_exp_nivel(57, 0) == 1.0   # sin nivel: sin cambio
