"""Green Angel: "solo debe abrir la opcion exchange for y los item que se pueden cambiar sean pestles, ride feed,
hammer y lucky hammer lvl 3, lvl 4, lvl 5 100 x 1"."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
import app
import canje_straw
import lyceum_services as ly


def test_el_menu_solo_tiene_el_canje():
    assert ly.saludo('Green Angel') == (513638, [513642, 513643])


def test_cada_receta_da_un_item_por_100_straws():
    texto = (RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'exchange.xml').read_bytes().decode('utf-8')
    _texto, numeros = canje_straw.reescribir(texto)
    premios = []
    for n in numeros:
        r = app._obtener_receta_exchange(n)
        assert r['materiales'] == [(ly.STRAW, 100)]
        premios += r['premios']
    assert premios == [(item, 1) for item, _ in canje_straw.PREMIOS]
