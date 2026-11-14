"""El Item Mall nuevo (14/11/2026): ventana 61000, server/mall_nuevo.py y server/lua/mall_nuevo.lua (comando 173)."""
import pathlib
import struct
import sys

from test_competiciones import world  # noqa: F401
import item_mall
import mall_nuevo as mn

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
CARTA_DOBLE_EXP = 30590                 # Double Exp Card (2017) a 35 AG, Function > General


def _cmd(s, a, b=0):
    return mn.procesar(s, struct.pack('<BII', mn.CMD_MALL, a, b), 'test')


def _lua(paquete) -> str:
    return paquete[2:-1].decode('latin1')


def _ir_a(s, producto):
    """Pestana, categoria, pagina y tarjeta del producto; lo deja elegido."""
    for t, (_n, subs) in enumerate(mn.PESTANAS):
        for k, (_c, cats) in enumerate(subs):
            if cats is None:
                continue
            _cmd(s, 2, t)
            _cmd(s, 3, k)
            filas = mn.productos(s)
            ids = [r['id'] for r in filas]
            if producto in ids:
                i = ids.index(producto)
                s._mall['pag'] = i // mn.POR_PAGINA
                return i % mn.POR_PAGINA
    raise AssertionError('producto %d en ninguna pestana' % producto)


def test_las_categorias_y_pestanas_son_las_de_la_ventana():
    import parche_mall_nuevo as pm
    assert mn.CLAVES == tuple(c[0] for c in pm.CATEGORIAS)
    assert tuple(n for n, _ in mn.PESTANAS) == pm.PESTANAS
    assert all(c in mn.CLAVES for _n, subs in mn.PESTANAS + (('', mn.HISTORIAL),) for c, _ in subs)
    assert max(len(subs) for _n, subs in mn.PESTANAS) <= 10


def test_cada_pestana_del_catalogo_tiene_productos(world):
    s = world.player()
    for t, (nombre, subs) in enumerate(mn.PESTANAS):
        if subs[0][1] is None:
            continue
        _cmd(s, 2, t)
        assert mn.productos(s), nombre


def test_abrir_manda_el_lua_y_pinta(world):
    s = world.player()
    enviados = []
    s.enviar = lambda *p: enviados.extend(p)
    assert _cmd(s, 1)
    assert 'function MallPintar' in _lua(enviados[0]) and _lua(enviados[1]) == 'MallAbrir()'
    pintado = _lua(enviados[2])
    assert pintado.startswith('MallPintar(') and '["ag"]="1,000,000"' in pintado
    assert len(mn.datos(s)['cartas']) == mn.POR_PAGINA


def test_comprar_pide_confirmar_y_va_a_mi_compra(world):
    s = world.player()
    c = _ir_a(s, CARTA_DOBLE_EXP)
    _cmd(s, 6, c)
    assert item_mall.saldo(s.usuario) == 1000000 and 'again to confirm' in s._mall['msg']
    _cmd(s, 6, c)
    assert item_mall.saldo(s.usuario) == 1000000 - 35
    assert mn.datos(s)['cab'] == [[2017, 1]] and 'Mi Compra' in s._mall['msg']
    _cmd(s, 7, 0)                                   # pulsar la casilla: a la mochila
    assert 2017 in s.inventario.values() and mn.datos(s)['cab'] == []


def test_otra_tarjeta_no_confirma_la_compra_pendiente(world):
    s = world.player()
    c = _ir_a(s, CARTA_DOBLE_EXP)
    _cmd(s, 6, c)
    _cmd(s, 6, (c + 1) % mn.POR_PAGINA)
    assert item_mall.saldo(s.usuario) == 1000000


def test_regalar_cobra_al_que_regala_y_llega_al_otro(world):
    a, b = world.player(), world.player()
    c = _ir_a(a, CARTA_DOBLE_EXP)
    _cmd(a, 5, c)
    _cmd(a, 9)
    assert a._mall['regalo']
    nombre = b.personaje.nombre.encode().ljust(16, b'\0')
    for t in range(4):
        _cmd(a, 20 + t, struct.unpack_from('<I', nombre, 4 * t)[0])
    _cmd(a, 8)
    assert item_mall.saldo(a.usuario) == 1000000 - 35 and item_mall.saldo(b.usuario) == 1000000
    assert mn.datos(b)['cab'] == [[2017, 1]] and mn.datos(a)['cab'] == []


def test_favoritos_e_historial(world):
    s = world.player()
    c = _ir_a(s, CARTA_DOBLE_EXP)
    _cmd(s, 5, c)
    _cmd(s, 12)
    _cmd(s, 2, [n for n, _ in mn.PESTANAS].index('Favorite'))
    assert [r['id'] for r in mn.productos(s)] == [CARTA_DOBLE_EXP]
    _cmd(s, 10)
    assert mn.productos(s) == [] and mn.datos(s)['tab'] == -1
    c = _ir_a(s, CARTA_DOBLE_EXP)
    _cmd(s, 6, c)
    _cmd(s, 6, c)
    _cmd(s, 10)
    assert [r['id'] for r in mn.productos(s)] == [CARTA_DOBLE_EXP]


def test_el_gm_lo_abre_con_mall(world):
    import app
    s = world.player()
    enviados = []
    s.enviar = lambda *p: enviados.extend(p)
    assert app._probar_gm(s, b'/mall', 'test')
    assert any(_lua(p) == 'MallAbrir()' for p in enviados)
