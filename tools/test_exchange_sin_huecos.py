"""exchange.xml sin huecos en los 編號 (09/11/2026).

El cliente (0x6702b0, la lista de la ventana Exchange) recorre las filas por id desde 1 y se para en el PRIMER id que
no existe. Al borrar 4 filas del Login Rewarder (18977, 18987-18989) los canjes con id mayor salieron vacios: "los 2
de arriba no salen, el ultimo no sale completo" (Winter Holiday PD, Ride and Robots, Enhanced Pestle and Ride). Las
recetas que se retiran se quedan con 群組="0", y el servidor no las acepta.
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402

EXCHANGE = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'exchange.xml'


def test_exchange_xml_no_tiene_huecos():
    ids = [int(x) for x in re.findall(r'<exchange 編號="(\d+)"', EXCHANGE.read_text(encoding='utf-8'))]
    faltan = sorted(set(range(1, max(ids) + 1)) - set(ids))
    assert not faltan, 'el cliente deja de listar canjes desde el id %d' % faltan[0]
    assert len(ids) == len(set(ids))


def test_una_receta_de_grupo_0_no_se_canjea():
    assert app._obtener_receta_exchange(18987) is None          # Olympic Heart retirado del Login Rewarder
    assert app._obtener_receta_exchange(22490)                   # Winter Holiday PD (grupo 622) si
