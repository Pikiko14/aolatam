""""ES POSIBLE QUITAR ESTAS PESTANAS EN EL MAPA MIENTRAS ESTE LA EXPANSION FUERA??"."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import parche_pestanas_mapa as ppm


def test_solo_quedan_las_regiones_abiertas(mapas_apagados_configurados):
    cerradas = ppm.regiones_cerradas()
    assert {'atlantis', 'forest', 'desert', 'floating', 'candy', 'jurassic'} <= cerradas
    assert 'heart of eden' not in cerradas and 'dungeon' in cerradas


def test_al_abrir_una_expansion_su_pestana_vuelve(monkeypatch, mapas_apagados_configurados):
    import configuracion
    atlantis = {84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 101}
    monkeypatch.setattr(configuracion, 'MAPAS_APAGADOS', frozenset(configuracion.MAPAS_APAGADOS - atlantis))
    assert 'atlantis' not in ppm.regiones_cerradas()


def test_dungeon_cerrada_por_sus_mapas(mapas_apagados_configurados):
    """"dungeon tambien debe estar apagado": sus mapas 67-72 estan en MAPAS_APAGADOS."""
    assert {67, 68, 69, 70, 71, 72} <= set(mapas_apagados_configurados)
    assert 'dungeon' in ppm.regiones_cerradas()
