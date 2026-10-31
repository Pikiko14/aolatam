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


def test_el_canje_de_tickets_pide_20_30_40_50_segun_el_nivel():
    """"los item lvl 3 piden 20 los 4 piden 30 y los 5 piden 40 tambien habilita lvl 6 solo ride feed y lucky hammer
    y pircien y enhgacement"; las gemas, de nivel 40."""
    recetas = canje_straw.CANJES[canje_straw.GRUPO_TICKETS]
    for item, nombre, material, cuantos in recetas:
        assert material in (20228, 20229, 20230, 20231)
        nivel = next((n for n in (3, 4, 5, 6) if nombre.startswith(('%d-star' % n, 'Lvl %d ' % n))), None)
        assert cuantos == (20 if nivel is None else {3: 20, 4: 30, 5: 40, 6: 50}[nivel])
    assert {6900, 7042, 6910, 7088} <= {r[0] for r in recetas}
    assert {3093, 3098, 3103, 3108, 3113, 3118} <= {r[0] for r in recetas}
    r = app._obtener_receta_exchange(15340)
    assert r['materiales'] == [(20228, 20)] and r['premios'] == [(6897, 1)]
    r = app._obtener_receta_exchange(15343)
    assert r['materiales'] == [(20228, 50)] and r['premios'] == [(6900, 1)]


def test_el_jefe_de_dark_cavern_suelta_de_2_a_5_tickets():
    """"que esos ticket los drope el jefe de la instance"."""
    import instancia_oscura as io

    class Jefe:
        npc_type = 209                                                 # Dragonkin Moowad

    for _ in range(200):
        salen = io.tickets_del_jefe(io.STAGE, Jefe())
        assert 2 <= sum(c for _i, c in salen) <= 5 and {i for i, _c in salen} <= set(io.TICKETS)
    assert io.tickets_del_jefe(41, Jefe()) == []


def test_ride_and_robots_solo_monturas_raras_50_60_por_mount_coins():
    """"que solo salgan aca las monturas lvl 60 ... monturas raras que no vendan los npc ... un mount coin"."""
    for item, nombre, material, cuantos in canje_straw.CANJES[canje_straw.GRUPO_MONTURAS]:
        assert material == canje_straw.MOUNT_COIN and cuantos in (30, 50)
    assert (RAIZ / 'tools' / 'respaldos' / 'exchange_538_ride_and_robots.xml').exists()


def test_dark_cavern_suelta_mount_coins():
    import instancia_oscura as io

    class Jefe:
        npc_type = 209

    monedas = dict(io.botin_instancia(io.STAGE, Jefe())).get(canje_straw.MOUNT_COIN, 0)
    assert 3 <= monedas <= 5
