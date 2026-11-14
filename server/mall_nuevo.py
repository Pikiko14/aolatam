"""El Item Mall nuevo (14/11/2026): la ventana 61000 de wnd05.xml (tools/parche_mall_nuevo.py, con el diseno de
docs/item_mall_diseno.png) y su logica server/lua/mall_nuevo.lua, que el servidor manda por el canal Lua al abrirla.
De momento la abre el GM con /mall ("de momento que se abra con un comando GM").

Lo que vende, cobra y entrega es el Item Mall de siempre (item_mall.py): el mismo catalogo (item_mall.json), el mismo
Angel Gold de la cuenta y el mismo Store Cabinet. Esta ventana solo lo ensena de otra forma.

    c2s 0x002F [u8 173][u32 a][u32 b]:
      a = 1 abrir                 2 pestana b               3 categoria b            4 pagina (b 0 atras, 1 adelante)
          5 elegir la tarjeta b   6 Comprar de la tarjeta b (dos veces: la primera pide confirmar)
          7 sacar la casilla b del Store Cabinet a la mochila
          8 regalar lo elegido al nombre escrito (llega antes en 20..23, cuatro letras cada uno)
          9 Regalar sin nombre: ensena la casilla del nombre     10 Historial     11 Ordenar la mochila
          12 la estrella: anadir o quitar lo elegido de Favorite
"""
import logging
import struct
import time

import canal_lua

log = logging.getLogger('app')

CMD_MALL = 173
POR_PAGINA = 6
NOMBRE_MAX = 18                      # lo que cabe en la tira del nombre de una tarjeta
CASILLAS_MOCHILA = 35
CONFIRMAR_SEGUNDOS = 15

# Las categorias, en el mismo orden que CATEGORIAS de tools/parche_mall_nuevo.py: el indice k es su imagen
# (icono 61540 + 2k normal, + 1 elegida).
CLAVES = ('top', 'sale', 'lb_hot', 'lb_equip', 'lb_armor', 'lb_mount', 'sp_general', 'sp_potion', 'sp_teleport', 'pet',
          'fn_general', 'fn_mini', 'fu_floor', 'fu_wall', 'fu_carpet', 'fu_gacha', 'fa_male', 'fa_female', 'fa_robot',
          'fa_bubble', 'intro', 'favorite', 'history')
# Las pestanas con sus categorias, las del Item Mall del juego (setting/eng/malllayout.xml: 功能類 11 一般 / 12 小遊戲,
# 特殊類 13 / 16 藥水 / 27 傳送, 福袋類 28 熱門 / 29 裝備 / 30 / 31 座騎, 寵物類 19, 裝扮機甲 24 男裝 / 25 女裝 /
# 17 機甲 / 40 對話泡泡, 傢俱類 32..35, 熱賣商品 22, 搶購區 23, 商城說明, 我的最愛), en el orden del diseno:
# (clave, tipos de item_mall.json). None = no sale del catalogo.
PESTANAS = (
    ('Top Sale', (('top', (22,)),)),
    ('On Sale', (('sale', (23,)),)),
    ('LuckyBag', (('lb_hot', (28,)), ('lb_equip', (29,)), ('lb_armor', (30,)), ('lb_mount', (31,)))),
    ('Special', (('sp_general', (13,)), ('sp_potion', (16,)), ('sp_teleport', (27,)))),
    ('Pet', (('pet', (19,)),)),
    ('Function', (('fn_general', (11,)), ('fn_mini', (12,)))),
    ('Furniture', (('fu_floor', (32,)), ('fu_wall', (33,)), ('fu_carpet', (34,)), ('fu_gacha', (35,)))),
    ('Fashion', (('fa_male', (24,)), ('fa_female', (25,)), ('fa_robot', (17,)), ('fa_bubble', (40,)))),
    ('Intro', (('intro', None),)),
    ('Favorite', (('favorite', None),)),
)
# La pestana Intro: lo del texto 12406 del Item Mall del juego, con lo de este servidor.
# El MSTATIC del juego salta de linea con la barra y la n escritas (asi esta el texto 12406 de wnd05.xml).
INTRO = ('[Angel Gold]\\n'
         '1. Everything in the Item Mall is bought with Angel Gold. Every account starts with 1,000,000 and you earn '
         'more from bosses and events.\\n'
         '2. Angel Gold belongs to your account: it cannot be traded.\\n\\n'
         '[How to use the Mall]\\n'
         '1. Pick a tab and a category, then click an item to select it.\\n'
         '2. Comprar buys it (press it twice to confirm). It waits in Mi Compra: click it to move it to your '
         'backpack.\\n'
         '3. Regalar sends the selected item to another player: write the name and press Regalar again.\\n'
         '4. The star keeps the selected item in Favorite. Historial shows what you bought.\\n'
         '5. Mi Compra holds 10 deliveries at most. Make sure your backpack has room before you claim them.')
HISTORIAL = (('history', None),)
_LUA = None


def _lua() -> str:
    global _LUA
    if _LUA is None:
        import pathlib
        _LUA = (pathlib.Path(__file__).parent / 'lua' / 'mall_nuevo.lua').read_text(encoding='utf-8')
    return _LUA


def _estado(ses) -> dict:
    m = getattr(ses, '_mall', None)
    if m is None:
        m = ses._mall = {'tab': 0, 'sub': 0, 'pag': 0, 'sel': None, 'confirmar': None, 'regalo': False,
                         'historial': False, 'msg': '', 'nombre': {}}
    return m


def _miles(n) -> str:
    return '{:,}'.format(int(n))


def _nombre_item(item) -> str:
    try:
        import misiones
        return misiones.nombre_item(int(item))
    except Exception:
        return 'Item %d' % int(item)


def precio(fila) -> int:
    return int(fila.get('special_price') or fila.get('price') or 0)


def subcategorias(m):
    """Las categorias de lo que se ve: las de la pestana o la del Historial."""
    return HISTORIAL if m['historial'] else PESTANAS[m['tab']][1]


# ---- lo que se guarda: favoritos y compras --------------------------------------------------------------------------
def _con():
    import cuentas
    import item_mall
    con = cuentas._get_conn()
    item_mall._schema(con)
    con.execute('CREATE TABLE IF NOT EXISTS item_mall_favoritos (usuario TEXT COLLATE NOCASE, producto INTEGER, '
                'fecha REAL, PRIMARY KEY(usuario, producto))')
    return con


def favoritos(usuario) -> list:
    import cuentas
    with cuentas._LOCK, _con() as con:
        return [int(r[0]) for r in con.execute('SELECT producto FROM item_mall_favoritos WHERE usuario=? '
                                               'ORDER BY fecha DESC', (usuario,))]


def cambiar_favorito(usuario, producto) -> bool:
    """Lo pone o lo quita. True si ahora es favorito."""
    import cuentas
    with cuentas._LOCK, _con() as con:
        if con.execute('SELECT 1 FROM item_mall_favoritos WHERE usuario=? AND producto=?',
                       (usuario, producto)).fetchone():
            con.execute('DELETE FROM item_mall_favoritos WHERE usuario=? AND producto=?', (usuario, producto))
            return False
        con.execute('INSERT INTO item_mall_favoritos VALUES(?,?,?)', (usuario, producto, time.time()))
        return True


def comprados(usuario, tope=30) -> list:
    """Los productos que compro la cuenta, del ultimo al primero, sin repetir."""
    import cuentas
    with cuentas._LOCK, _con() as con:
        filas = con.execute("SELECT referencia FROM item_mall_movimientos WHERE usuario=? COLLATE NOCASE "
                            "AND motivo='purchase' ORDER BY fecha DESC LIMIT 200", (usuario,)).fetchall()
    out = []
    for (p,) in filas:
        if p is not None and int(p) not in out:
            out.append(int(p))
    return out[:tope]


# Top Sale: el catalogo no trae nada en la categoria 22, asi que son los productos mas comprados en el servidor los
# ultimos 30 dias y, mientras haya pocas compras, los de estas categorias (On Sale, Special, Function, Potion).
TOP_SALE, TOP_SALE_DIAS, TOP_SALE_RELLENO = 12, 30, (23, 13, 11, 16)


def mas_vendidos(filas) -> list:
    import cuentas
    with cuentas._LOCK, _con() as con:
        cuenta = dict(con.execute("SELECT referencia, COUNT(*) FROM item_mall_movimientos WHERE motivo='purchase' "
                                  "AND fecha>=? GROUP BY referencia", (time.time() - TOP_SALE_DIAS * 86400,)))
    vendidos = sorted((r for r in filas if cuenta.get(r['id'])), key=lambda r: (-cuenta[r['id']], r['id']))
    relleno = sorted((r for r in filas if r['category'] in TOP_SALE_RELLENO and r not in vendidos),
                     key=lambda r: (TOP_SALE_RELLENO.index(r['category']), r['sort'], r['id']))
    return (vendidos + relleno)[:TOP_SALE]


def cabinet(usuario) -> list:
    """[(id, item, cantidad)] del Store Cabinet, como item_mall.almacen."""
    import cuentas
    with cuentas._LOCK, _con() as con:
        con.execute('DELETE FROM item_mall_cabinet WHERE usuario=? AND fin IS NOT NULL AND fin<=?',
                    (usuario, time.time()))
        return [(int(a), int(b), int(c)) for a, b, c in
                con.execute('SELECT id,item,cantidad FROM item_mall_cabinet WHERE usuario=? ORDER BY id LIMIT 10',
                            (usuario,))]


# ---- lo que se ensena -----------------------------------------------------------------------------------------------
def productos(ses, m=None) -> list:
    """Las filas del catalogo de la categoria elegida."""
    import item_mall
    m = m or _estado(ses)
    clave, cats = subcategorias(m)[m['sub']]
    filas = item_mall.disponibles()
    por_id = {int(r['id']): r for r in filas}
    if clave == 'favorite':
        return [por_id[p] for p in favoritos(ses.usuario) if p in por_id]
    if clave == 'history':
        return [por_id[p] for p in comprados(ses.usuario) if p in por_id]
    if clave == 'intro':
        return []
    if clave == 'top' and not any(r['category'] == 22 for r in filas):
        return mas_vendidos(filas)
    orden = {c: i for i, c in enumerate(cats)}
    return sorted((r for r in filas if r['category'] in orden),
                  key=lambda r: (orden[r['category']], r['sort'], r['id']))


def paginas(n) -> int:
    return max(1, (n + POR_PAGINA - 1) // POR_PAGINA)


def _mochila(ses):
    import app
    bolsa = getattr(ses, 'inventario', None) or {}
    cant = app._cantidades(ses)
    ranuras = app._ranuras_bolsa(bolsa)
    llenas = [r for r in ranuras if bolsa.get(r)]
    casillas = [[int(bolsa[r]), int(cant.get(r, 1) or 1)] for r in llenas[:CASILLAS_MOCHILA]]
    return casillas, '%d / %d' % (len(llenas), len(ranuras))


def datos(ses) -> dict:
    import item_mall
    m = _estado(ses)
    subs = subcategorias(m)
    m['sub'] = min(m['sub'], len(subs) - 1)
    filas = productos(ses, m)
    m['pag'] = max(0, min(m['pag'], paginas(len(filas)) - 1))
    cartas = []
    for r in filas[m['pag'] * POR_PAGINA:(m['pag'] + 1) * POR_PAGINA]:
        nombre = _nombre_item(r['item'])
        if int(r['quantity']) > 1:
            nombre = '%s x%d' % (nombre, int(r['quantity']))
        if len(nombre) > NOMBRE_MAX:
            nombre = nombre[:NOMBRE_MAX - 2] + '..'
        cartas.append([int(r['item']), nombre, _miles(precio(r)), 1 if r['id'] == m['sel'] else 0])
    moch, espacio = _mochila(ses)
    return {
        'ag': _miles(item_mall.saldo(ses.usuario)),
        'oro': _miles(getattr(ses, 'oro', 0) or 0),
        'tab': -1 if m['historial'] else m['tab'],
        'subs': [CLAVES.index(clave) for clave, _ in subs],
        'sub': m['sub'],
        'pag': '%d/%d' % (m['pag'] + 1, paginas(len(filas))),
        'cartas': cartas,
        'cab': [[item, cant] for _id, item, cant in cabinet(ses.usuario)],
        'moch': moch,
        'espacio': espacio,
        'msg': m['msg'],
        'regalo': bool(m['regalo']),
        'intro': INTRO if subs[m['sub']][0] == 'intro' else '',
    }


def pintar(ses) -> bytes:
    return canal_lua.llamar('MallPintar', datos(ses))


def abrir(ses) -> list:
    m = _estado(ses)
    m.update(regalo=False, confirmar=None, msg='Welcome to the Item Mall! Click an item to select it.')
    return [canal_lua.paquete(_lua()), canal_lua.llamar('MallAbrir'), pintar(ses)]


# ---- las acciones ---------------------------------------------------------------------------------------------------
def _fila_de_carta(ses, m, c):
    filas = productos(ses, m)
    k = m['pag'] * POR_PAGINA + int(c)
    return filas[k] if 0 <= int(c) < POR_PAGINA and k < len(filas) else None


def _comprar(ses, m, fila, receptor=None, addr='?'):
    import app
    import item_mall
    try:
        _ident, destino = item_mall.comprar(ses, int(fila['id']), receptor)
    except item_mall.Rechazo as exc:
        m['msg'] = str(exc)
        return
    nombre = _nombre_item(fila['item'])
    if receptor:
        m['msg'] = 'Gift sent: %s to %s.' % (nombre, receptor)
        for s in app._tw_sesiones():
            if s is not ses and getattr(s, 'usuario', '').casefold() == destino.casefold():
                s.enviar(item_mall.almacen(destino))
                if getattr(s, '_mall', None) is not None:
                    s.enviar(pintar(s))
    else:
        m['msg'] = 'You bought %s! It is waiting in Mi Compra: click it to move it to your backpack.' % nombre
    log.info('[%s] mall nuevo: %s compra el producto %s%s', addr, ses.usuario, fila['id'],
             ' para %s' % receptor if receptor else '')
    ses.enviar(item_mall.almacen(ses.usuario), struct.pack('<HI', 0x0062, item_mall.saldo(ses.usuario)))


def accion(ses, a, b, addr='?'):
    import item_mall
    m = _estado(ses)
    if a in (20, 21, 22, 23):
        m['nombre'][a - 20] = struct.pack('<I', b & 0xFFFFFFFF)
        return False
    m['msg'] = ''
    if a not in (6,):
        m['confirmar'] = None
    if a == 2 and 0 <= b < len(PESTANAS):
        m.update(tab=b, sub=0, pag=0, historial=False, sel=None, regalo=False)
    elif a == 3 and 0 <= b < len(subcategorias(m)):
        m.update(sub=b, pag=0, sel=None)
    elif a == 4:
        m['pag'] += 1 if b else -1
    elif a == 5:
        fila = _fila_de_carta(ses, m, b)
        if fila:
            m['sel'] = fila['id']
            m['msg'] = ('%s: %s Angel Gold. Comprar to buy, Regalar to gift, the star to keep it in Favorite.'
                        % (_nombre_item(fila['item']), _miles(precio(fila))))
    elif a == 6:
        fila = _fila_de_carta(ses, m, b)
        if fila:
            m['sel'] = fila['id']
            pendiente = m.get('confirmar')
            if pendiente and pendiente[0] == fila['id'] and time.time() - pendiente[1] <= CONFIRMAR_SEGUNDOS:
                m['confirmar'] = None
                _comprar(ses, m, fila, addr=addr)
            else:
                m['confirmar'] = (fila['id'], time.time())
                m['msg'] = 'Buy %s for %s Angel Gold? Press Comprar again to confirm.' % (
                    _nombre_item(fila['item']), _miles(precio(fila)))
    elif a == 7:
        filas = cabinet(ses.usuario)
        if 0 <= b < len(filas):
            try:
                item_mall.retirar(ses, filas[b][0])
                m['msg'] = '%s moved to your backpack.' % _nombre_item(filas[b][1])
            except item_mall.Rechazo as exc:
                m['msg'] = str(exc)
    elif a in (8, 9):
        fila = next((r for r in item_mall.disponibles() if r['id'] == m['sel']), None)
        nombre = b''.join(m['nombre'].get(i, b'') for i in range(4)).split(b'\0')[0].decode('latin-1').strip()
        m['nombre'] = {}
        if not fila:
            m['msg'] = 'Click an item first, then press Regalar.'
        elif a == 9 or not nombre:
            m['regalo'] = True
            m['msg'] = 'Gift %s: write the name and press Regalar.' % _nombre_item(fila['item'])
        else:
            m['regalo'] = False
            _comprar(ses, m, fila, receptor=nombre, addr=addr)
    elif a == 10:
        m.update(historial=not m['historial'], sub=0, pag=0, sel=None, regalo=False)
        if m['historial'] and not comprados(ses.usuario):
            m['msg'] = 'You have not bought anything yet.'
    elif a == 11:
        import app
        app._ordenar_bolsa(ses, addr, 1)
        m['msg'] = 'Backpack sorted.'
    elif a == 12:
        if m['sel'] is None:
            m['msg'] = 'Click an item first, then the star to keep it in Favorite.'
        else:
            fila = next((r for r in item_mall.disponibles() if r['id'] == m['sel']), None)
            nombre = _nombre_item(fila['item']) if fila else 'Item'
            m['msg'] = ('%s added to Favorite.' if cambiar_favorito(ses.usuario, m['sel'])
                        else '%s removed from Favorite.') % nombre
    return True


def procesar(ses, cuerpo, addr='?') -> bool:
    """El 0x002F de la ventana. True si era suyo."""
    if len(cuerpo) < 9 or cuerpo[0] != CMD_MALL:
        return False
    if not getattr(ses, 'personaje', None) or not getattr(ses, 'usuario', None):
        return True
    a, b = struct.unpack_from('<II', cuerpo, 1)
    if a == 1:
        ses.enviar(*abrir(ses))
        return True
    try:
        if accion(ses, int(a), int(b), addr):
            ses.enviar(pintar(ses))
    except Exception:
        log.exception('[%s] mall nuevo: accion %s %s', addr, a, b)
    return True
