"""El boton de ordenar del Prop y la Backpack (09/11/2026: "que ordene por categorias de items")."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import ordenar_bolsa as ob  # noqa: E402

CAT = {1: '衣服', 2: '一般', 3: '頭飾', 9: '寵物'}


def _plan(objetos, apilables=(), fijas=()):
    return ob.plan(list(range(20, 30)), objetos, lambda i: CAT[i], lambda c: c in apilables, lambda c: c in fijas)


def test_ordena_por_la_categoria_del_cliente():
    nuevo = _plan({20: (1, 1), 22: (3, 1), 25: (2, 4)})
    assert [nuevo[c][1] for c in sorted(nuevo)] == [2, 3, 1]          # 一般 0, 頭飾 2, 衣服 3
    assert sorted(nuevo) == [20, 21, 22]


def test_junta_montones_hasta_999():
    nuevo = _plan({20: (2, 600), 23: (2, 700), 26: (2, 5)}, apilables={20, 23, 26})
    assert [(u[1], u[2]) for _c, u in sorted(nuevo.items())] == [(2, 999), (2, 306)]


def test_las_mascotas_no_se_mueven():
    nuevo = _plan({20: (1, 1), 21: (9, 1), 24: (2, 1)}, fijas={21})
    assert 21 not in nuevo and nuevo[20][1] == 2 and nuevo[22][1] == 1


def _ses(bolsa, cant, mejoras, monkeypatch):
    monkeypatch.setattr(app, '_refrescar', lambda ses, r, **k: [])
    monkeypatch.setattr(app, '_guardar_bolsa', lambda ses, cid: None)
    monkeypatch.setattr(app, '_instancias', lambda ses: ses.instancias)
    p = NS(char_id=1, mejoras=mejoras)
    return NS(personaje=p, inventario=bolsa, cantidades=cant, instancias={c: b'%d' % c for c in bolsa},
              trade=None, puesto=None, enviar=lambda *a: None)


def test_las_mejoras_y_la_instancia_viajan_con_el_objeto(monkeypatch):
    import inventario
    cat = {500: '衣服', 600: '一般'}
    monkeypatch.setattr(inventario, 'categoria_item', lambda i: cat[i])
    monkeypatch.setattr(inventario, 'es_apilable', lambda i: i == 600)
    monkeypatch.setattr(inventario, 'es_mascota', lambda i: False)
    ses = _ses({20: 500, 30: 600, 31: 600}, {30: 10, 31: 5}, {20: {'veces': 7}}, monkeypatch)
    app._ordenar_bolsa(ses, 'a', ob.PROP)
    assert ses.inventario == {20: 600, 21: 500}
    assert ses.cantidades == {20: 15, 21: 1}
    assert ses.personaje.mejoras == {21: {'veces': 7}}
    assert ses.instancias[21] == b'20' and ses.instancias[20] == b'30' and 31 not in ses.instancias


def test_con_comercio_abierto_no_ordena(monkeypatch):
    ses = _ses({20: 1}, {}, {}, monkeypatch)
    ses.trade = object()
    app._ordenar_bolsa(ses, 'a', ob.PROP)
    assert ses.inventario == {20: 1}
