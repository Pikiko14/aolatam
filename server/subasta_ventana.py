"""La ventana propia de la casa de subastas (02/11/2026): el tablon 3501 rehecho, con filtros y paginas.

Necesita las dos piezas del cliente: el canal 0x01A0 en angel.dat (tools/parche_canal_lua.py) y la ventana en
wnd03.xml (tools/parche_subasta_ventana.py). Su logica Lua es server/lua/subasta.lua, que se manda entera al
abrirla. Los datos son los de subastas.py: esto es solo otra forma de verla y comprar.

* SALUDO: al entrar al mundo se manda por el canal "game.netcommand2(160, 1, 0)". Un cliente sin el parche ignora
  el 0x01A0 (como ya ignora el 0x0196 del login, que tampoco tiene manejador) y no contesta; el que lo tiene
  contesta y queda marcado (ses.canal_lua). /ah abre esta ventana a los marcados y el puesto de antes a los demas.
* La ventana pide con game.netcommand2, que es el c2s 0x002F [u8 cmd][u32 a][u32 b]:
      160 saludo            a = version del canal
      161 buscar            a = orden << 24 | modo << 16 | categoria << 8 | nivel, b = pagina (1..);
                            orden 0 lo mas nuevo, 1 lo mas barato
      162 comprar           a = id de la publicacion, b = cantidad
      163 retirar lo propio a = id de la publicacion
      164 preparar venta    a = ranura de la mochila soltada en la casilla, b = el item que dice el cliente
      165 publicar          a = ranura << 16 | cantidad, b = precio por unidad
      166 abrir la ventana  (el boton de la barra de abajo)
      167 diagnostico       lo que paso al soltar un objeto, para el log
  El primer byte del 0x002F es el contenedor en los demas usos (10, 11...): estos van muy por encima.
* La respuesta es SubastaLista(modo, pagina, paginas, filas, oro, total) por el canal; cada fila lleva el item
  para que el cliente pinte su icono en la rejilla.
* PUBLICAR desde la propia ventana ("se deben subir los productos desde la misma auction", 02/11/2026): en la
  pestana Mine se arrastra un objeto de la mochila a la casilla (game.getdropdata da su ranura, la misma que usa el
  0x0013 de destruir), el servidor contesta SubastaPreparada con su nombre y cuantos hay, y con la cantidad y el
  precio escritos el boton lo publica. Valen las mismas reglas que en el intercambio: nada equipado, ni
  intransferible (不可交易), ni premio de arena, ni temporal del Item Mall, ni mueble protegido.
"""
import logging

import canal_lua

log = logging.getLogger('subasta_ventana')

CMD_SALUDO, CMD_BUSCAR, CMD_COMPRAR, CMD_RETIRAR, CMD_PREPARAR, CMD_PUBLICAR = 160, 161, 162, 163, 164, 165
CMD_ABRIR, CMD_DIAG = 166, 167
COMANDOS = (CMD_SALUDO, CMD_BUSCAR, CMD_COMPRAR, CMD_RETIRAR, CMD_PREPARAR, CMD_PUBLICAR, CMD_ABRIR, CMD_DIAG)
# Lo que se define en el cliente al contestar el saludo: el boton de la barra (wnd01.xml, 59001) llama a esto.
SALUDO_LUA = ('function OnCommandSubasta(dwID, dwCmdID, dwParam, pParam) '
              'game.netcommand2(%d, 0, 0) return 1 end' % CMD_ABRIR)
POR_PAGINA = 9                      # la lista 3530 tiene 10 filas y la primera es la cabecera
MODO_TODO, MODO_MIO, MODO_VENDER = 0, 1, 2      # pestanas All, Mine y Sell (la mochila)
ORDEN_NUEVO, ORDEN_BARATO = 0, 1

# Las categorias del desplegable: (texto, 物品類別 de item.xml). None = todas; 'resto' = lo que no cae en ninguna.
CATEGORIAS = (
    ('All', None),
    ('Headwear', {'頭飾'}),
    ('Clothes', {'衣服'}),
    ('Gloves', {'手套'}),
    ('Shoes', {'鞋子'}),
    ('Kitbag', {'背包'}),
    ('Mantle', {'披風'}),
    ('Trinket', {'飾品'}),
    ('Sword', {'劍'}),
    ('Blade', {'刀'}),
    ('Hammer', {'錘'}),
    ('Axe', {'斧'}),
    ('Spear', {'槍'}),
    ('Shadow', {'影刃'}),
    ('Wand', {'杖'}),
    ('Bow', {'弓箭'}),
    ('Sling', {'彈弓'}),
    ('Shield', {'盾'}),
    ('Ammo', {'彈藥', '箭矢'}),
    ('Ride', {'座騎'}),
    ('Robot', {'機甲', '機甲零件'}),
    ('Pet', {'寵物', '怪物蛋', '寵物武器', '寵物飾品', '寵物防具', '寵物寶石', '寵物裝備'}),
    ('Gem', {'寶石'}),
    ('Enhance', {'強化道具', '強化飼料', '打孔道具', '附魔', '寵物強化'}),
    ('Scroll', {'卷軸', '經驗卷'}),
    ('Recipe', {'配方'}),
    ('Card', {'卡片', '字卡'}),
    ('Other', 'resto'),
)
_CON_CATEGORIA = set().union(*(c for _, c in CATEGORIAS if isinstance(c, set)))

# El filtro de nivel llega hasta el tope del servidor (configuracion.NIVEL_MAXIMO_PERSONAJE, 60): "valida todo hasta
# el cap 60" (02/11/2026). Es el nivel que pide el objeto (等級限制).
NIVELES = (('All', None, None),) + tuple(('Lv %d-%d' % (a, a + 9), a, a + 9) for a in range(1, 60, 10))


def _lua():
    return (canal_lua.CARPETA / 'subasta.lua').read_text(encoding='utf-8')


def saludo():
    """El 0x01A0 que solo contesta un cliente con el canal."""
    return canal_lua.paquete('game.netcommand2(%d, 1, 0)' % CMD_SALUDO)


def tiene_ventana(ses) -> bool:
    return bool(getattr(ses, 'canal_lua', 0))


def es_comando(cuerpo) -> bool:
    return len(cuerpo) >= 9 and cuerpo[0] in COMANDOS


def oro_corto(n) -> str:
    """El oro en la cajita de abajo, que no cabe mas: 9,999 / 966K / 1.23M."""
    n = int(n or 0)
    if n < 10_000:
        return _miles(n)
    if n < 1_000_000:
        return '%dK' % (n // 1000)
    return ('%.2fM' % (n / 1_000_000.0)).replace('.00M', 'M')


def _miles(n) -> str:
    return '{:,}'.format(int(n))


def _categoria_de(item_id):
    import inventario as iv
    try:
        return iv.categoria_item(int(item_id)) or ''
    except Exception:
        return ''


def _nivel_de(item_id) -> int:
    import inventario as iv
    try:
        return int(iv.nivel_requerido_de_item(int(item_id)) or 0)
    except Exception:
        return 0


def pasa_filtro(item_id, cat: int, niv: int) -> bool:
    if 0 < cat < len(CATEGORIAS):
        quiere = CATEGORIAS[cat][1]
        c = _categoria_de(item_id)
        if quiere == 'resto':
            if c in _CON_CATEGORIA:
                return False
        elif c not in quiere:
            return False
    if 0 < niv < len(NIVELES):
        _, lo, hi = NIVELES[niv]
        if not lo <= max(1, _nivel_de(item_id)) <= hi:
            return False
    return True


def _nombre(fila) -> str:
    import app
    nombre = app._nombre_item(fila['item_id']) or 'Item %d' % fila['item_id']
    veces = int((fila.get('mejoras') or {}).get('veces') or 0)
    if veces:
        nombre += ' +%d' % veces
    if fila.get('mascota') and fila['mascota'].get('nombre'):
        nombre += ' (%s)' % fila['mascota']['nombre']
    return nombre


def filas_mochila(ses, cat: int, niv: int):
    """La pestana Sell: lo que hay en la mochila y se puede subastar, como filas [ranura, nombre, cantidad, '', '',
    item]; la ranura hace de id, que es lo que manda el cliente al elegir una."""
    import app
    salida = []
    for ranura in sorted(int(r) for r in ses.inventario):
        if motivo_no_vendible(ses, ranura):
            continue
        item = int(ses.inventario[ranura])
        if not pasa_filtro(item, cat, niv):
            continue
        veces = int(((getattr(ses.personaje, 'mejoras', None) or {}).get(ranura) or {}).get('veces') or 0)
        nombre = (app._nombre_item(item) or 'Item %d' % item) + (' +%d' % veces if veces else '')
        salida.append([ranura, nombre, int(app._cant_de(ses, ranura)), '', '', item])
    return salida


def filas(ses, modo: int, cat: int, niv: int, orden: int = ORDEN_NUEVO):
    """Todas las publicaciones que ve con esos filtros, ya como filas de la lista: [id, nombre, cantidad, precio,
    vendedor, item]. El listado viene de lo mas nuevo a lo mas viejo; "Cheap" ordena por precio."""
    if modo == MODO_VENDER:
        return filas_mochila(ses, cat, niv)
    import subastas
    p = ses.personaje
    lista = [f for f in subastas.listado(limite=None, char_id=p.char_id if modo == MODO_MIO else None)
             if pasa_filtro(f['item_id'], cat, niv)]
    if orden == ORDEN_BARATO:
        lista.sort(key=lambda f: int(f['precio']))
    return [[int(f['id']), _nombre(f), int(f['cantidad']), _miles(f['precio']), f['vendedor'], int(f['item_id'])]
            for f in lista]


def lista(ses, modo=MODO_TODO, cat=0, niv=0, pagina=1, orden=ORDEN_NUEVO):
    """El SubastaLista(...) de esa pagina."""
    todas = filas(ses, modo, cat, niv, orden)
    paginas = max(1, (len(todas) + POR_PAGINA - 1) // POR_PAGINA)
    pagina = min(max(1, int(pagina)), paginas)
    trozo = todas[(pagina - 1) * POR_PAGINA:pagina * POR_PAGINA]
    return canal_lua.llamar('SubastaLista', modo, pagina, paginas, trozo, oro_corto(getattr(ses, 'oro', 0)), len(todas))


def abrir(ses):
    """Lo que abre la ventana: su Lua y la llamada que la crea (ella misma pide la primera pagina)."""
    return [canal_lua.paquete(_lua()),
            canal_lua.llamar('SubastaAbrir', [c for c, _ in CATEGORIAS], [n for n, _, _ in NIVELES])]


def motivo_no_vendible(ses, ranura):
    """Por que no se puede subastar lo de esa ranura, o None si se puede."""
    import inventario as iv
    if ranura not in ses.inventario:
        return 'That item is no longer in your backpack.'
    if iv.es_equipo(ranura) or ranura == iv.RANURA_ORO:
        return 'Take it off before selling it.'
    item_id = int(ses.inventario[ranura])
    estado = (getattr(ses.personaje, 'mejoras', None) or {}).get(ranura)
    if not iv.puede_transferir(item_id, estado):
        return 'That item is bound: it cannot be traded.'
    if (__import__('arena_premios_compat').es_premio(ses, ranura)
            or __import__('item_mall').es_temporal(ses, ranura)
            or __import__('furniture_items').protegido(ses, ranura)):
        return 'That item cannot be traded.'
    return None


def _ranura_soltada(ses, ranura, item_id):
    """La ranura que dice el cliente; si no tiene ese objeto, la primera que lo tenga."""
    ranura = int(ranura)
    if int(ses.inventario.get(ranura, -1)) == int(item_id):
        return ranura
    import inventario as iv
    return next((int(r) for r, it in ses.inventario.items()
                 if int(it) == int(item_id) and not iv.es_equipo(int(r))), ranura)


def preparar(ses, ranura, item_id):
    """El SubastaPreparada(...) del objeto soltado en la casilla, o un SubastaAviso con el motivo."""
    import app
    ranura = _ranura_soltada(ses, ranura, item_id)
    motivo = motivo_no_vendible(ses, ranura)
    if motivo:
        return canal_lua.llamar('SubastaAviso', motivo)
    item = int(ses.inventario[ranura])
    veces = int(((getattr(ses.personaje, 'mejoras', None) or {}).get(ranura) or {}).get('veces') or 0)
    nombre = (app._nombre_item(item) or 'Item %d' % item) + (' +%d' % veces if veces else '')
    return canal_lua.llamar('SubastaPreparada', ranura, item, nombre, int(app._cant_de(ses, ranura)))


def publicar(ses, ranura, cantidad, precio):
    """Publica desde la ventana. Devuelve los paquetes de respuesta (la lista de Mine y el aviso)."""
    import subastas
    motivo = motivo_no_vendible(ses, ranura)
    if not motivo and not 0 < int(precio) <= subastas.ORO_MAX:
        motivo = 'Write a price for each unit.'
    if not motivo and int(cantidad) <= 0:
        motivo = 'The quantity must be at least 1.'
    if motivo:
        return [canal_lua.llamar('SubastaAviso', motivo)]
    hechas = subastas.publicar(ses, [{'ranura': int(ranura), 'item_id': int(ses.inventario[ranura]),
                                      'cantidad': int(cantidad), 'precio': int(precio)}])
    if not hechas:
        return [canal_lua.llamar('SubastaAviso', 'It could not be listed (see the chat).')]
    ses.subasta_filtro = (MODO_VENDER, 0, 0, 1, ORDEN_NUEVO)
    return [lista(ses, MODO_VENDER), canal_lua.llamar('SubastaPublicada', 'Listed! See it in the Mine tab.')]


def procesar(ses, cuerpo) -> bool:
    """Un 0x002F de la ventana. True si era suyo."""
    import struct
    if not es_comando(cuerpo):
        return False
    cmd = cuerpo[0]
    a, b = struct.unpack_from('<II', cuerpo, 1)
    if cmd == CMD_SALUDO:
        ses.canal_lua = int(a) or 1
        log.info('%s tiene el canal Lua (version %d)', getattr(ses.personaje, 'nombre', '?'), a)
        import arbol_mascotas
        import medidor_dano
        import torre_babel
        ses.enviar(canal_lua.paquete(SALUDO_LUA), canal_lua.paquete(medidor_dano.SALUDO_LUA),
                   canal_lua.paquete(torre_babel.SALUDO_LUA), canal_lua.paquete(arbol_mascotas.SALUDO_LUA),
                   canal_lua.paquete(__import__('raid').SALUDO_LUA))
        # La pestana AOF de System y las teclas de la barra (server/lua/teclas.lua, tools/parche_teclas_aof.py):
        # sin los nativos game.aof* del exe el propio script no hace nada.
        try:
            ses.enviar(canal_lua.paquete((canal_lua.CARPETA / 'teclas.lua').read_text(encoding='utf-8')))
        except Exception:
            log.exception('teclas.lua')
        return True
    if not tiene_ventana(ses):
        return True
    estado = getattr(ses, 'subasta_filtro', None) or (MODO_TODO, 0, 0, 1, ORDEN_NUEVO)
    if cmd == CMD_BUSCAR:
        modo = (a >> 16) & 0xFF
        modo = modo if modo in (MODO_TODO, MODO_MIO, MODO_VENDER) else MODO_TODO
        orden = ORDEN_BARATO if (a >> 24) & 0xFF == ORDEN_BARATO else ORDEN_NUEVO
        cat, niv = (a >> 8) & 0xFF, a & 0xFF
        cat = cat if cat < len(CATEGORIAS) else 0
        niv = niv if niv < len(NIVELES) else 0
        ses.subasta_filtro = (modo, cat, niv, max(1, int(b)), orden)
        ses.enviar(lista(ses, *ses.subasta_filtro))
        return True
    if cmd == CMD_ABRIR:
        ses.enviar(*abrir(ses))
        return True
    if cmd == CMD_DIAG:
        log.info('%s soltar: paso %d, dato %d', getattr(ses.personaje, 'nombre', '?'), a, b)
        return True
    if cmd == CMD_PREPARAR:
        ranura, tipo = a & 0xFFFF, (a >> 16) & 0xFF
        log.info('%s suelta en la casilla: ranura=%d tipo=%d item=%d', getattr(ses.personaje, 'nombre', '?'),
                 ranura, tipo, b)
        if ranura == 0xFFFF:
            ses.enviar(canal_lua.llamar('SubastaAviso', 'Drag the item from your backpack.'))
        else:
            ses.enviar(preparar(ses, ranura, b))
        return True
    if cmd == CMD_PUBLICAR:
        ses.enviar(*publicar(ses, (a >> 16) & 0xFFFF, a & 0xFFFF, b))
        return True
    if cmd in (CMD_COMPRAR, CMD_RETIRAR):
        import subastas
        cant = max(1, int(b)) if cmd == CMD_COMPRAR else 1 << 30
        tocadas, salida = subastas.tomar(ses, [(int(a), cant)], solo_propias=cmd == CMD_RETIRAR)
        if tocadas:
            aviso = 'Done: it is in your backpack.'
        else:
            aviso = 'It could not be done (see the chat).'
        ses.enviar(*salida, lista(ses, *estado), canal_lua.llamar('SubastaAviso', aviso))
        return True
    return True
