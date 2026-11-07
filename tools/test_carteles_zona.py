"""Carteles con los bichos de cada zona (06/11/2026)."""
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import carteles_zona as cz  # noqa: E402
import marcas_npc  # noqa: E402


def test_spike_farm_tiene_sus_bichos_con_nivel():
    textos = [t for _e, t, _p in cz.carteles(6)]
    assert 'Field Mouse Lv9' in textos and all(len(t) <= 16 for t in textos)


def test_paquete_cartel(monkeypatch):
    monkeypatch.setattr(cz, 'ACTIVOS', True)
    pk = cz.poblar(6)[0]
    assert pk[:2] == b'\x08\x00' and struct.unpack_from('<I', pk, 2 + 34)[0] == cz.SPRITE
    assert cz.es_cartel(struct.unpack_from('<I', pk, 2)[0])
    assert not marcas_npc._es_npc(pk)          # no lleva [!]


def test_texto_corto():
    assert cz._texto('Jackstraw Mige', [17]) == 'Jackstraw M Lv17'
    assert cz._texto('Slarm', [1, 3]) == 'Slarm Lv1-3'


def test_solo_gm_mientras_se_prueba(monkeypatch):
    from types import SimpleNamespace as NS
    monkeypatch.setattr(cz, 'ACTIVOS', True)
    pk = cz.poblar(6)[0]
    p = NS(stage=6, nivel=1, rango=1, faction='Aurora', quests=[])
    otro = NS(personaje=p, rol='mundo', usuario='alguien')
    gm = NS(personaje=p, rol='mundo', usuario='baco01')
    assert marcas_npc.marcar(otro, (pk,)) == ()
    assert marcas_npc.marcar(gm, (pk,)) == (pk,)


def test_apagados_no_se_mandan():
    assert cz.ACTIVOS is False and cz.poblar(6) == []
