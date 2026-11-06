"""Las bolsas dan las cartas de EXP, el Ride Feed y los hammers de 1 en 1 (05/11/2026: "toda double skill exp, double
skill, ride feed y hammer para intensificar que den las bag deben ser x1 unidad")."""
import json
import pathlib
import random
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import bolsas  # noqa: E402

DEFS = json.loads((RAIZ / 'server' / 'plantillas' / 'lucky_bags_mall.json').read_text(encoding='utf-8'))


def test_las_plantillas_dan_una_unidad():
    for d in DEFS:
        for it, cant, _p in d['contenido']:
            if bolsas.es_premio_unitario(it):
                assert cant == 1, (d['nombre'], it, cant)
        assert 'Exp Card x' not in d['descripcion'] and 'Ride Feed x' not in d['descripcion'], d['nombre']


def test_abrir_nunca_da_mas_de_una(monkeypatch):
    random.seed(5)
    bolsas_ids = [d['id'] for d in DEFS]
    for iid in bolsas_ids:
        for _ in range(60):
            sale = bolsas.abrir(iid)
            if sale and bolsas.es_premio_unitario(sale[0]):
                assert sale[1] == 1, (iid, sale)


def test_regla_general_para_otras_tablas(monkeypatch):
    monkeypatch.setitem(bolsas.TABLAS_PROPIAS, 999999, [(2017, 3, 1)])
    assert bolsas.abrir(999999) == (2017, 1)
