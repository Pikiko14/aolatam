"""La ventana propia de la casa de subastas (02/11/2026): el tablon 3501 rehecho, con filtros y paginas.

Necesita las dos piezas del cliente: el canal 0x01A0 en angel.dat (tools/parche_canal_lua.py) y la ventana en
wnd03.xml (tools/parche_subasta_ventana.py). Su logica Lua es server/lua/subasta.lua, que se manda entera al
abrirla. Los datos son los de subastas.py: esto es solo otra forma de verla y comprar.

* SALUDO: al entrar al mundo se manda por el canal "game.netcommand2(160, 1, 0)". Un cliente sin el parche ignora
  el 0x01A0 (como ya ignora el 0x0196 del login, que tampoco tiene manejador) y no contesta; el que lo tiene
  contesta y queda marcado (ses.canal_lua). /ah abre esta ventana a los marcados y el puesto de antes a los demas.
* La ventana pide con game.netcommand2, que es el c2s 0x002F [u8 cmd][u32 a][u32 b]:
      160 saludo            a = version del canal
      161 buscar            a = modo << 16 | categoria << 8 | nivel, b = pagina (1..)
      162 comprar           a = id de la publicacion, b = cantidad
      163 retirar lo propio a = id de la publicacion
  El primer byte del 0x002F es el contenedor en los demas usos (10, 11...): estos van muy por encima.
* La respuesta es SubastaLista(modo, pagina, paginas, filas, oro) por el canal.
"""
import logging

import canal_lua

log = logging.getLogger('subasta_ventana')

CMD_SALUDO, CMD_BUSCAR, CMD_COMPRAR, CMD_RETIRAR = 160, 161, 162, 163
COMANDOS = (CMD_SALUDO, CMD_BUSCAR, CMD_COMPRAR, CMD_RETIRAR)
POR_PAGINA = 10                     # las filas de la lista 3530 (rows="10")
MODO_TODO, MODO_MIO = 0, 1

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


def filas(ses, modo: int, cat: int, niv: int):
    """Todas las publicaciones que ve con esos filtros, ya como filas de la lista."""
    import subastas
    p = ses.personaje
    lista = subastas.listado(limite=None, char_id=p.char_id if modo == MODO_MIO else None)
    return [[int(f['id']), _nombre(f), int(f['cantidad']), _miles(f['precio']), f['vendedor']]
            for f in lista if pasa_filtro(f['item_id'], cat, niv)]


def lista(ses, modo=MODO_TODO, cat=0, niv=0, pagina=1):
    """El SubastaLista(...) de esa pagina."""
    todas = filas(ses, modo, cat, niv)
    paginas = max(1, (len(todas) + POR_PAGINA - 1) // POR_PAGINA)
    pagina = min(max(1, int(pagina)), paginas)
    trozo = todas[(pagina - 1) * POR_PAGINA:pagina * POR_PAGINA]
    return canal_lua.llamar('SubastaLista', modo, pagina, paginas, trozo, _miles(getattr(ses, 'oro', 0)))


def abrir(ses):
    """Lo que abre la ventana: su Lua y la llamada que la crea (ella misma pide la primera pagina)."""
    return [canal_lua.paquete(_lua()),
            canal_lua.llamar('SubastaAbrir', [c for c, _ in CATEGORIAS], [n for n, _, _ in NIVELES])]


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
        return True
    if not tiene_ventana(ses):
        return True
    estado = getattr(ses, 'subasta_filtro', None) or (MODO_TODO, 0, 0, 1)
    if cmd == CMD_BUSCAR:
        modo = MODO_MIO if (a >> 16) & 0xFF == MODO_MIO else MODO_TODO
        cat, niv = (a >> 8) & 0xFF, a & 0xFF
        cat = cat if cat < len(CATEGORIAS) else 0
        niv = niv if niv < len(NIVELES) else 0
        ses.subasta_filtro = (modo, cat, niv, max(1, int(b)))
        ses.enviar(lista(ses, *ses.subasta_filtro))
        return True
    if cmd in (CMD_COMPRAR, CMD_RETIRAR):
        import subastas
        cant = max(1, int(b)) if cmd == CMD_COMPRAR else 1 << 30
        tocadas, salida = subastas.tomar(ses, [(int(a), cant)], solo_propias=cmd == CMD_RETIRAR)
        if tocadas:
            aviso = 'Done: the item is in your backpack.'
        else:
            aviso = 'Could not complete it (see the message in the chat).'
        ses.enviar(*salida, lista(ses, *estado), canal_lua.llamar('SubastaAviso', aviso))
        return True
    return True
