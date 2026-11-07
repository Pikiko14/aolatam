"""Los monstruos usan sus 攻擊法術 (06/11/2026: "hay mob que usan spell pero no los veo que lo usen")."""
import pathlib
import random
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import hechizos_mob as hm  # noqa: E402


def test_evil_fire_elf_tiene_phoenix_fire():
    prob, lista = hm.hechizos(203)
    assert prob == hm.PROB_POR_DEFECTO and lista == [(2055, 170, 2)]


def test_sin_hechizos_no_elige():
    assert hm.elegir(NS(npc_type=0), random.Random(1)) is None


def test_dano_magico_usa_matk_y_defensa_magica():
    m = NS(npc_type=203, matk=333, pegar=lambda: 387)
    d = hm.dano((2055, 170, 2), m, 0, 0, random.Random(1))
    assert d > 0
    assert hm.dano((2055, 170, 2), m, 0, 5000, random.Random(1)) < d


def test_fisica_pega_mas_que_el_golpe():
    m = NS(npc_type=0, matk=0, pegar=lambda: 400)
    assert hm.dano((701, 0, 0), m, 100, 0) > hm.dano((701, 0, 0), NS(npc_type=0, matk=0, pegar=lambda: 300), 100, 0)


def test_usa_hechizo_a_veces():
    m = NS(npc_type=203)
    r = random.Random(7)
    usos = sum(1 for _ in range(1000) if hm.elegir(m, r))
    assert 150 < usos < 350
