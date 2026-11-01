"""La vida en el retrato del grupo (u32) y la de los totems de Totem War (01/11/2026)."""
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))

import equipos
import login
import totem_war


class _S:
    def __init__(self, hp):
        self.personaje = login.Personaje(char_id=1, entity_id=1001, nombre='Baco', stage=41, hp=hp, hp_max=2500)
        self.inventario = {}


def test_la_vida_del_miembro_va_en_cuatro_bytes():
    """El cliente la lee como u32 en +33: con el mana detras, la barra salia siempre llena."""
    b = equipos.serializar_miembro(_S(1000))
    assert struct.unpack_from('<I', b, 33)[0] == equipos._vida_pct(_S(1000)) < 100


def test_los_totems_tienen_10k_por_nivel(monkeypatch):
    st = sorted(totem_war.TOTEM_CAMPO)[0]
    for nivel in (1, 4, 8):
        monkeypatch.setattr(totem_war, 'nivel_totem', lambda s, n=nivel: (n, 0))
        m = totem_war.crear_totem(st)
        assert m.hp_max == m.hp == 10_000 * nivel
