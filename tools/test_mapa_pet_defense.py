"""El mapa propio de Pet Defense, el 917 (tools/mapa_pet_defense.py): la Training Cave retocada (21/11/2026)."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
sys.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))
import mpcio  # noqa: E402
import mapa_pet_defense as mpd  # noqa: E402
import pet_defense as pd  # noqa: E402
import pet_defense_partida as pp  # noqa: E402
import transitable  # noqa: E402

MAPA = RAIZ / 'tools' / 'mapas_propios' / 'map917.mpc'
CFG = pd.config()


def _m():
    return mpcio.leer(MAPA.read_bytes())


def test_pet_defense_juega_en_el_917():
    mp = CFG['mapa']
    assert mp['stage'] == mpd.STAGE == 917 and transitable.conocido(917)
    ruta = pp.camino(917, mp['portal'], mp['cristal'])
    assert ruta and len(ruta) > 150
    assert transitable.se_pisa(917, *mp['llegada'])


def test_el_suelo_y_la_colision_son_los_de_la_cueva():
    m = _m()
    # "Que el piso se vea armonioso" (21/11/2026): el suelo es el de la cueva tal cual, sin texturas de fuera
    orig = mpcio.leer(mpd.original())
    assert m['celdas'] == orig['celdas'] and not mpd.PINTAR_SUELO
    for y in range(m['h']):
        for x in range(m['w']):
            assert transitable.se_pisa(917, x, y) == (m['celdas'][mpd._celda(m, x, y) + 1] == 0)
    assert transitable.se_pisa(917, 30, 40) == transitable.se_pisa(45, 30, 40)


def test_portal_luces_y_plaza():
    m = _m()
    mp = CFG['mapa']
    por_casilla = {}
    for o in m['objetos']:
        por_casilla.setdefault(mpd._casilla_obj(m, o), []).append(o[0])
    assert mpd.OBJ_PORTAL in por_casilla.get(tuple(mp['portal']), [])
    ids = [o[0] for o in m['objetos']]
    assert sum(1 for i in ids if i in mpd.OBJ_LUCES) >= 20 and mpd.OBJ_PILAR in ids


def test_fila_de_stage_xml():
    texto = (RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'stage.xml').read_text(encoding='utf-8-sig')
    assert '編號="917" 名稱="Pet Defense" 地圖檔="map\\map917.mpc"' in texto and 'smap\\045' in texto
    assert mpd.fila_stage(texto) == texto
