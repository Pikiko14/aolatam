"""Lv50 Mount Lucky Bag (17/11/2026): monturas Lv50-55 5% entre las normales, las 4 mas fuertes al 3% cada una aparte,
monturas Lv10-49 15% y el resto Ride Feed (tools/generar_lucky_bags.py)."""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import generar_lucky_bags as g  # noqa: E402


def _bolsa():
    return next(d for d in json.loads((RAIZ / 'server/plantillas/lucky_bags_mall.json').read_text(encoding='utf-8'))
                if d['nombre'] == 'Lv50 Mount Lucky Bag')


def test_los_porcentajes_de_la_lv50():
    items = g._items()
    d = _bolsa()
    peso = {i: w / 1000.0 for i, _c, w in d['contenido']}
    propias = sorted(g._monturas(items, 50, 55), key=lambda f: (-g._fuerza(f), int(f['id'])))
    fuertes = [int(f['id']) for f in propias[:4]]
    normales = [int(f['id']) for f in propias[4:]]
    bajas = [int(f['id']) for f in g._monturas(items, 10, 49)]
    assert all(abs(peso[i] - 3.0) < 0.01 for i in fuertes)
    assert abs(sum(peso[i] for i in normales) - 5.0) < 0.1
    assert abs(sum(peso[i] for i in bajas) - 15.0) < 0.1
    assert abs(peso[g.RIDE_FEED] - 68.0) < 0.1
    assert 'Lv50-55' in d['descripcion'] and 'strongest 3.0% each' in d['descripcion']


def test_las_fuertes_salen_por_sus_stats_no_por_el_id():
    items = g._items()
    propias = sorted(g._monturas(items, 50, 55), key=lambda f: (-g._fuerza(f), int(f['id'])))
    assert g._fuerza(propias[0]) > 0
    assert {f['基本名稱'] for f in propias[:2]} == {'SKY-Fish Bu55', 'SKY-Fish Re55'}
