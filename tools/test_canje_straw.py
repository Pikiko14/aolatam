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


def test_el_canje_de_tickets_pide_20_de_su_tipo():
    """"aca igual los mismos lvl de items de intensificar, agrega runas ... cada pestle cuesta 20"."""
    for item, nombre, material, cuantos in canje_straw.CANJES[canje_straw.GRUPO_TICKETS]:
        assert cuantos == 20 and material in (20228, 20229, 20230, 20231)
    r = app._obtener_receta_exchange(21282)
    assert r['materiales'] == [(20228, 20)] and r['premios'] == [(6897, 1)]


def test_el_jefe_de_dark_cavern_suelta_de_2_a_5_tickets():
    """"que esos ticket los drope el jefe de la instance"."""
    import instancia_oscura as io

    class Jefe:
        npc_type = 209                                                 # Dragonkin Moowad

    for _ in range(200):
        salen = io.tickets_del_jefe(io.STAGE, Jefe())
        assert 2 <= sum(c for _i, c in salen) <= 5 and {i for i, _c in salen} <= set(io.TICKETS)
    assert io.tickets_del_jefe(41, Jefe()) == []
