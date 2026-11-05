"""Goring (1284), el proc de Spine Shell al recibir dano, es un sangrado sobre el atacante (05/11/2026).

Se mandaba como un golpe del jugador (0x000A) con el efecto 148, el de Tendon Chop, y el personaje "usaba Tendon
Chop" sin pedirlo: "revisa porque final boss usa tendon chop sin mandarlo a usar".
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import combate as cb  # noqa: E402
import login  # noqa: E402

GORING = 1284


def test_goring_sangra_al_mob_sin_animar_al_jugador(monkeypatch):
    monkeypatch.setattr(cb.random, 'randint', lambda a, b: 100)        # que no lo resista
    p = login.Personaje(hp=20000, hp_max=100000, mp=50000, mp_max=150000)
    p.tile_x, p.tile_y = 100, 100
    mob = cb.Monstruo(9999, 999999, 'Dummy', (101, 100))
    mob.hp = mob.hp_max = 10 ** 6
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, cantidades={},
           monstruos={9999: mob}, usuario=None, muerto=False)
    pk = app._ejecutar_proc_subhechizo(s, p.entity_id, mob, GORING, addr='t')
    assert not [x for x in pk if x[:2] == struct.pack('<H', 0x000A)]   # el jugador no ataca
    assert mob.hp == mob.hp_max                                         # el dano llega por ticks
    assert mob.sangra_hp == 45 and mob.sangra_cada == 2
    assert [x for x in pk if x[:2] == struct.pack('<H', 0x001D)]        # icono del debuff en el mob
