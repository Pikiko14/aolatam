"""Las Backpack de item2..item9.xml tambien dan casillas (17/11/2026: "me dice la mochila esta llena si tengo el
backpack vacio")."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import house_services  # noqa: E402


def _mochila_de(nombre):
    return next(int(i) for i, f in house_services.xml_rows(nombre).items()
                if f.get('物品類別') == '背包' and int(f.get('動態資料1') or 0) > 0)


def test_una_mochila_de_item2_da_sus_casillas():
    mochila = _mochila_de('item2.xml')
    casillas = int(house_services.xml_rows('item2.xml')[mochila]['動態資料1'])
    assert app._casillas_mochila({7: mochila}) == min(app.MAX_MOCHILA, casillas) > 0


def test_con_el_prop_lleno_y_la_mochila_vacia_hay_hueco():
    mochila = _mochila_de('item8.xml')
    bolsa = {7: mochila}
    bolsa.update({r: 20 for r in list(range(20, app.TOPE_SIN_MOCHILA + 1)) + list(app.PROP_EXTRA)})
    assert app._ranura_libre(bolsa) == app.PRIMERA_MOCHILA
