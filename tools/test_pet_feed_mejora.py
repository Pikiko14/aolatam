"""El Pet Feed (saciedad > 100) mejora los stats y la velocidad de ataque de la mascota (05/11/2026: "el pet feed no
mejora las estadisticas del pet ... en los stat, velocidad del pet ataque")."""
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import mascotas as ms  # noqa: E402


def test_saciada_pega_mas_rapido_con_poca_agilidad():
    assert app._cadencia_pet(18, True) < app._cadencia_pet(15, False) * 0.8


def test_el_tooltip_de_la_mochila_suma_la_mejora():
    f = {'nombre': 'Egg', 'hp': 100, 'hp_max': 100, 'mp': 105, 'mp_max': 105, 'nivel': 1, 'sprite': 0,
         'atk': 28, 'dfs': 10, 'matk': 18, 'mdef': 19, 'rigor': 15, 'agilidad': 15, 'intimidad': 50}
    def bono(sac, k):
        e = ms.entrada(bytes(ms.TAM_ENTRADA), dict(f, saciedad=sac))
        return struct.unpack_from('<I', e, ms.OFF_BONUS_ENTRADA[k])[0]
    assert bono(100, 'atk') == 0 and bono(500, 'atk') == 11          # 28 -> 39
    assert bono(500, 'agilidad') == 3                                # 15 -> 18
    # y coincide con lo que manda la ficha 0x0065 (valor efectivo)
    assert struct.unpack_from('<I', ms.armar(dict(f, saciedad=500)), 2 + 83 + 4)[0] == 28 + 11
