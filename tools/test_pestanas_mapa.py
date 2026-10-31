""""ES POSIBLE QUITAR ESTAS PESTANAS EN EL MAPA MIENTRAS ESTE LA EXPANSION FUERA??"."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import parche_pestanas_mapa as ppm


def test_solo_quedan_las_regiones_abiertas():
    cerradas = ppm.regiones_cerradas()
    assert {'atlantis', 'forest', 'desert', 'floating', 'candy', 'jurassic'} <= cerradas
    assert 'heart of eden' not in cerradas and 'dungeon' not in cerradas


def test_al_abrir_una_expansion_su_pestana_vuelve(monkeypatch):
    import configuracion
    atlantis = {84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 101}
    monkeypatch.setattr(configuracion, 'MAPAS_APAGADOS', frozenset(configuracion.MAPAS_APAGADOS - atlantis))
    assert 'atlantis' not in ppm.regiones_cerradas()
