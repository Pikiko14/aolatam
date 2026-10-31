"""Item Mall: habilita TODAS las ofertas del mall.xml del cliente que faltaban y anade sets PD.

    python tools/habilitar_mall_completo.py            # dice lo que haria
    python tools/habilitar_mall_completo.py --write    # escribe server/plantillas/item_mall.json

1. Las filas del mall.xml mas nuevo (extracted_paks/*/setting/eng/mall.xml) cuyo (objeto, categoria, cantidad)
   no esta ya en el catalogo entran con su precio, cantidad y duracion originales. Se les quitan las
   fechas de alta/baja (eran promociones de 2008-2012: con fecha no saldrian nunca) y los regalos de
   "compra y llevate" (gift), que el mall local no da. Los objetos de `excluded` no entran.
2. Dos maletas de traje al azar (cliente_local.MALETAS_PD), una en Ropa de hombre (24) y otra en
   Ropa de mujer (25): cada una da UNA maleta de set PD de los 10 sets exoticos (cliente_local.
   SETS_PD_AL_AZAR), que al abrirse da el traje entero. Su tabla va a plantillas/drops_bolsas.json.
   Antes se vendian los 10 sets sueltos (20 filas); se quitan.

3. ON SALE (搶購區, categoria 23) lleva SOLO lo que pidio el usuario: los Maple (Mark y
   Teleportation Scroll) y Mark Stone y Mark Portal Scroll, con los precios y cantidades de la
   pestana de teletransporte (27). Todo lo demas se quita de ahi.

Las filas ya publicadas no se tocan. Se puede volver a correr: no duplica nada.
"""
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'server'))
JSON = RAIZ / 'server' / 'plantillas' / 'item_mall.json'

DROPS = RAIZ / 'server' / 'plantillas' / 'drops_bolsas.json'
CAT_HOMBRE, CAT_MUJER = 24, 25
PRECIO_MALETA_PD = 599        # un traje al azar: por debajo de los trajes enteros del mall (699-989)
PRIMER_ID_PD = 32700
# Las filas que anadimos nosotros van de la 32000 en adelante, justo despues de las del cliente (la mas alta
# es la 31447). Con ids de 36100 o de 40000 el cliente no las pintaba: los packs de 11/110 de Weapon y Armor,
# los Mark de On Sale y los huevos PD no salian aunque el servidor los mandara.
PRIMER_ID_LOCAL = 32000
PUBLICACION_PD = 'set PD (tools/habilitar_mall_completo.py)'
CAT_ON_SALE, CAT_TELEPORTE = 23, 27
# Maple Mark, Maple Teleportation Scroll, Mark Stone, Mark Portal Scroll.
ON_SALE = (20565, 20566, 3693, 3694)
PUBLICACION_ON_SALE = 'On Sale (tools/habilitar_mall_completo.py)'


# Quitadas por el usuario de la pestana Lucky Bag (28): las 2013 Taurus de las 7 clases.
QUITADAS = {31441: '2013 Taurus Swordman Lucky Bag', 31442: '2013 Taurus Axeman Lucky Bag',
            31443: '2013 Taurus Spearman Lucky Bag', 31444: '2013 Taurus Archer Lucky Bag',
            31445: '2013 Taurus Master Lucky Bag', 31446: '2013 Taurus Assassin Lucky Bag',
            31447: '2013 Taurus Artisan Lucky Bag',
            # y de la pestana Lucky Weapon (29):
            9422: 'Hero Lucky Bag', 9423: 'Devil Lucky Bag', 9424: 'Knights Spirit Lucky Bag',
            9425: 'Star Illusion Lucky Bag', 9426: 'Holy Lord Lucky Bag', 14502: 'Hell Lucky Bag',
            14545: "Adam's Power Lucky Bag", 14546: "Elar's Leaf Lucky Bag", 14547: "Namila's Soul Lucky Bag",
            14548: "Jiabli's Nail Lucky Bag", 14549: "Libelice's Torture Lucky Bag",
            14550: 'Carved Sin Blade Lucky Bag', 9427: 'Secret Sword Lucky Bag', 9428: 'Nemesis Axe Lucky Bag',
            9429: 'Thunder King Lucky Bag', 9430: 'Fire Tooth Lucky Bag', 9431: 'Mage Staff Lucky Bag',
            14503: 'Life Aurora Lucky Bag',
            14556: 'Minaca Attacker Lucky Bag', 14557: "Shalio's Bone Lucky Bag", 14558: "Shaer's Will Lucky Bag",
            14559: "Xilios's Soul Lucky Bag", 14560: "Selini's Direction Lucky Bag", 14561: 'Rage Claw Lucky Bag',
            # y de la pestana de armaduras (30):
            14563: 'Fane Armor Lucky Bag', 14562: 'Walker Armor Lucky Bag', 14564: 'Lucky Jack Gown Lucky Bag',
            14552: 'Embrace Armor Lucky Bag', 14551: 'Forest Armor Lucky Bag', 14553: 'Spring Gown Lucky Bag',
            9450: 'Holy Palace Armor Lucky Bag', 9451: 'Hermit Light Armor Lucky Bag',
            9452: 'Sound Gown Lucky Bag',
            # y de Ride (31) las que dan monturas de nivel > 55 (el usuario deja hasta 55):
            11259: 'Mage Lucky Bag( 2 )', 11257: 'Spearman Lucky Bag( 2 )', 11256: 'Axeman Lucky Bag( 2 )',
            11255: 'Swordsman Lucky Bag( 2 )', 11437: 'Rehael lucky bag',
            14565: 'Raymond Seabed Steed Lucky Bag', 14566: 'Round Mini Seal Lucky Bag',
            14554: 'RedNoble Elephant Lucky Bag', 14555: 'RedScarab Lucky Bag', 9453: 'Circus Elephant Lucky Bag',
            9454: 'Stiff Beetle Lucky Bag', 9448: 'SwiftTurtle Lucky Bag', 9449: 'IronLand Bird Lucky Bag',
            # y de Lucky Bag (28):
            26312: 'Lucky Wish Bag', 12876: 'Dragon Egg Lucky Bag', 12877: 'Elf Egg Lucky Bag',
            # y de Special Potion (16) todo lo que no es Low-effect ni Common:
            1354: 'Mid-effect Red Potion 3', 1355: 'Mid-effect Blue Potion 3', 8101: 'Potent Red Potion',
            8102: 'Potent Blue Potion', 23470: 'Potent Purple Potion', 18955: 'Effective Orange Potion',
            # de Fashion (24/25):
            29857: 'Enchanted-Wild Wolf Voucher Egg', 8531: 'Lucky Bag (Boys)', 8532: 'Lucky Bag (Girls)',
            # y de Robot (17) los de nivel > 60 (el usuario deja hasta 60):
            9305: 'Little Red-cap Robot', 9306: 'Grape Kaz cayman Robot'}

# PACKS DE 11 Y 110 en Lucky Weapon (29), Lucky Armor (30) y Ride (31), como los que ya hay en la
# pestana Lucky Bag. Precio fijo para todas las bolsas, como en la Lucky Bag: 300 el de 11 y 3000 el de 110
# (pedido del usuario el 31/10/2026; antes era 10 y 100 veces el precio de la bolsa).
CATS_CON_PACKS = (29, 30, 31)
PACKS = ((11, 10), (110, 100))
PRECIO_PACK = {11: 300, 110: 3000}
PUBLICACION_PACK = 'pack 11/110 (tools/habilitar_mall_completo.py)'


def packs(rows):
    for r in rows:
        if r['category'] in CATS_CON_PACKS and r['quantity'] in PRECIO_PACK and r.get('publication') == PUBLICACION_PACK:
            r['price'], r['special_price'] = PRECIO_PACK[r['quantity']], 0
            r['price_source'] = 'local: pack de %d a precio fijo' % r['quantity']
    hay = {(r['category'], r['item'], r['quantity']) for r in rows}
    ids = {r['id'] for r in rows}
    nuevas = []
    for r in rows:
        if r['category'] not in CATS_CON_PACKS or r['quantity'] != 1:
            continue
        for cant, veces in PACKS:
            if (r['category'], r['item'], cant) in hay:
                continue
            hay.add((r['category'], r['item'], cant))
            sig = max(ids | {PRIMER_ID_LOCAL - 1}) + 1
            ids.add(sig)
            nuevas.append(dict(r, id=sig, quantity=cant, price=PRECIO_PACK[cant], special_price=0,
                               price_source='local: pack de %d a precio fijo' % cant,
                               publication=PUBLICACION_PACK))
    return rows + nuevas


# Special > General (13): los Divine Scroll pasan a ser los primeros scrolls (+200 ataque/defensa,
# +160 magicos), en el mismo sitio, cantidad y precio.
REEMPLAZOS = {19406: (3805, 'DivineAttack Scroll -> Attack Scroll'),
              19407: (3806, 'DivineDefense Scroll -> Defense Scroll'),
              19408: (3807, 'DivineM.Attack Scroll -> Spell Attack Scroll'),
              19409: (3808, 'DivineM.Defense Scroll -> Spell Defense Scroll')}
# Quitadas solo de una pestana (en otras siguen): {categoria: {objeto: nombre}}.
QUITADAS_DE_PESTANA = {13: {16073: 'Blessed Fusion Potion', 12612: "Haven's Favor Bag"},
                       # Pet (19), pedido del usuario el 31/10/2026: piedras y diamante de EXP, Poke Egg,
                       # pociones de fusion y de forma, y las pociones de mascota marcadas.
                       19: {8643: 'Phantom Exp Stone', 8644: 'Phantom Exp Stone', 8645: 'Phantom Exp Diamond',
                            16982: 'Luxurious Poke Egg', 16073: 'Blessed Fusion Potion',
                            16074: 'Shape Fusion Potion', 16241: "Pet's Shapeshift Preview Scroll",
                            3451: "Mid-effect Pet's Red Potion", 3452: "Mid-effect Pet's Blue Potion",
                            3453: "High-effect Pet's Red Potion", 3454: "High-effect Pet's Blue Potion",
                            3465: "Pet's Assault Potion", 3466: "Pet's Defence Potion",
                            3467: "Pet's Evil Potion", 3468: "Pet's Demon Potion"},
                       # Function > General (11): granja, Cottage, jabones, Ball Ticket, huevos de monstruo
                       # y los Canister.
                       11: {23821: 'Farm-Fertilizer Truck', 23822: 'Farm-Super Fertilizer',
                            23823: 'Farm-Sprinkler', 23824: 'Farm-Pesticide', 23825: 'Farm-Harvester',
                            10115: 'Cottage', 10603: 'Liquid Soap', 10626: 'Super Liquid Soap',
                            9953: 'Ball Ticket', 10915: 'Lvl 90 Monster Egg', 10914: 'Lvl 80 Monster Egg',
                            10913: 'Lvl 70 Monster Egg', 10912: 'Lvl 60 Monster Egg',
                            10911: 'Lvl 50 Monster Egg', 10910: 'Lvl 40 Monster Egg',
                            4177: 'Happy Canister', 4178: 'Love Canister', 4179: 'Couples Canister',
                            4180: 'Pigeon Canister'}}
# Pestanas que solo llevan estos objetos: Special > Teleport (27) con los Maple, los Mark normales
# y Summon / Fly Book.
SOLO_EN_PESTANA = {CAT_TELEPORTE: {20565, 20566, 3693, 3694, 1333, 2987},
                   # Furniture (32-35): fuera todos los huevos de muebles; en la 32 solo los huevos PD.
                   32: {4978, 4979, 7471, 7472}, 33: set(), 34: set(), 35: set()}


# Huevos de traje (PD) que el usuario pidio en Fashion: Roll y Halloween Tricky, de hombre (24) y de
# mujer (25). Dan una pieza al azar. Precio y packs como la Lucky Bag (Boys): 1/11/110 a 30/300/3000.
AGREGADOS = {CAT_HOMBRE: (4978, 7471), CAT_MUJER: (4979, 7472),
             # y en Furniture (32), que el usuario vacio para dejar solo estos (31/10/2026):
             32: (4978, 4979, 7471, 7472)}
PACKS_AGREGADOS = ((1, 30), (11, 300), (110, 3000))
PUBLICACION_AGREGADO = 'pedido del usuario (tools/habilitar_mall_completo.py)'


def agregar(rows):
    hay = {(r['category'], r['item'], r['quantity']) for r in rows}
    ids = {r['id'] for r in rows}
    nuevas = []
    for cat, items in AGREGADOS.items():
        for orden, iid in enumerate(items):
            for cant, precio in PACKS_AGREGADOS:
                if (cat, iid, cant) in hay:
                    continue
                hay.add((cat, iid, cant))
                sig = max(ids | {PRIMER_ID_LOCAL - 1}) + 1
                ids.add(sig)
                nuevas.append(dict(id=sig, item=iid, flags=0x1, sort=orden, category=cat, quantity=cant,
                                   price=precio, special_price=0, duration=0, start='', end='', limit=0,
                                   gift=0, gift_quantity=0, price_source='local: como Lucky Bag (Boys)',
                                   publication=PUBLICACION_AGREGADO))
    return rows + nuevas


def fuera_de_pestana(r):
    c = r['category']
    return r['item'] in QUITADAS_DE_PESTANA.get(c, {}) or (c in SOLO_EN_PESTANA
                                                          and r['item'] not in SOLO_EN_PESTANA[c])


def quitar(d):
    ya = {int(e['item']) for e in d.setdefault('excluded', [])}
    d['excluded'] += [dict(item=i, name=n, reason='Removed from the Mall by user')
                      for i, n in QUITADAS.items() if i not in ya]
    d['excluded'] += [dict(item=i, name=n, reason='Replaced in the Mall by user')
                      for i, (_, n) in REEMPLAZOS.items() if i not in ya]
    for r in d['rows']:
        if r['item'] in REEMPLAZOS:
            r['item'] = REEMPLAZOS[r['item']][0]
            r['price_source'] = 'local: ' + REEMPLAZOS_NOMBRE.get(r['item'], '')
    d['rows'] = [r for r in d['rows'] if r['item'] not in QUITADAS and not fuera_de_pestana(r)]


REEMPLAZOS_NOMBRE = {nuevo: n for nuevo, n in REEMPLAZOS.values()}


def on_sale(rows):
    """Deja en On Sale solo ON_SALE; las que falten se copian de la pestana de teletransporte."""
    rows = [r for r in rows if r['category'] != CAT_ON_SALE or r['item'] in ON_SALE]
    ids = {r['id'] for r in rows}
    hay = {(r['item'], r['quantity']) for r in rows if r['category'] == CAT_ON_SALE}
    nuevas = []
    for r in sorted((r for r in rows if r['category'] == CAT_TELEPORTE and r['item'] in ON_SALE),
                    key=lambda r: (ON_SALE.index(r['item']), r['quantity'])):
        if (r['item'], r['quantity']) in hay:
            continue
        hay.add((r['item'], r['quantity']))
        sig = max(ids | {PRIMER_ID_LOCAL - 1}) + 1
        ids.add(sig)
        nuevas.append(dict(r, id=sig, category=CAT_ON_SALE, publication=PUBLICACION_ON_SALE))
    return rows + nuevas
# Solo se conservan los flags que tienen sentido sin fechas ni regalos: "nuevo" y "cuenta desde ya".
FLAGS_UTILES = {'最新商品': 0x1, '立即計時': 0x8}


def _mall_xml():
    from mapa_del_cliente import _orden  # noqa: F401  (orden de los parches, como audit_item_mall_sources)
    return max((RAIZ / 'extracted_paks').glob('*/setting/eng/mall.xml'), key=lambda p: _orden(p.parents[2]))


def _mall_xml_simple():
    try:
        sys.path.insert(0, str(RAIZ / 'tools'))
        return _mall_xml()
    except Exception:
        return sorted((RAIZ / 'extracted_paks').glob('*/setting/eng/mall.xml'))[-1]


def filas_originales():
    src = _mall_xml_simple()
    raiz = ET.parse(src).getroot()
    defs = {k: int(v) for n in raiz if n.tag == 'DEFINE' for k, v in n.attrib.items() if v.isdigit()}
    out = []
    for n in raiz:
        a = n.attrib
        if n.tag != '商城' or '道具編號' not in a:
            continue
        out.append(dict(id=int(a['編號']), item=int(a['道具編號']),
                        flags=sum(v for k, v in FLAGS_UTILES.items() if a.get(k) == '是'),
                        sort=int(a.get('排序') or 0), category=defs[a['分類類別']],
                        quantity=int(a['數量']), price=int(a['售價']), special_price=0,
                        duration=int(a.get('有效期限') or 0), start='', end='', limit=0, gift=0, gift_quantity=0,
                        price_source='original %s' % src.relative_to(RAIZ).as_posix()))
    return out


def orden_unico(rows):
    """Cada fila de una pestana con su propio `sort`. Los packs de 11/110 copiaban el sort de la de 1 y el
    cliente solo pintaba una por sort: en Weapon y Armor no salian los packs. Se numera 1, 2, 3... sin
    cambiar el orden (sort de antes, luego cantidad), como la pestana Pet, que ya iba asi."""
    por_cat = {}
    for i, r in enumerate(rows):
        por_cat.setdefault(r['category'], []).append((r['sort'], i, r))
    for cat, filas in por_cat.items():
        if cat == 22 or len({s for s, _, _ in filas}) == len(filas):
            continue                                   # Top Sale (22) lo ordena el servidor
        primero = {}
        for s, i, r in filas:
            primero.setdefault((s, r['item']), i)
        filas.sort(key=lambda f: (f[0], primero[(f[0], f[2]['item'])], f[2]['quantity'], f[1]))
        for n, (_, _, r) in enumerate(filas, 1):
            r['sort'] = n
    return rows


def completar(d):
    import bolsas
    rows = d['rows']
    ids = {r['id'] for r in rows}
    hay = {(r['item'], r['category'], r['quantity']) for r in rows}
    fuera = {int(e['item']) for e in d.get('excluded', [])}
    nuevas = []
    for r in filas_originales():
        if (r['item'], r['category'], r['quantity']) in hay or r['item'] in fuera or fuera_de_pestana(r):
            continue
        if r['id'] in ids:
            r['id'] = max(ids | {PRIMER_ID_LOCAL - 1}) + 1          # choca con una local: va despues de las nativas
        ids.add(r['id'])
        hay.add((r['item'], r['category'], r['quantity']))
        r['publication'] = 'habilitado: todo el mall.xml (tools/habilitar_mall_completo.py)'
        nuevas.append(r)
    import cliente_local as cl
    for _, m, f in cl.SETS_PD_AL_AZAR:
        for caja in (m, f):
            c = bolsas.contenido_descrito(caja)
            if not c or c[0] != 'todo':
                raise ValueError('la caja %d no da el set completo' % caja)
    # Fuera los sets sueltos de la version anterior y las maletas, que se vuelven a poner.
    maletas = set(cl.MALETAS_PD)
    rows = [r for r in rows if r.get('publication') != PUBLICACION_PD and r['item'] not in maletas]
    ids = {r['id'] for r in rows} | {r['id'] for r in nuevas}
    pd = []
    sig = PRIMER_ID_PD
    for iid, cat in ((cl.ITEM_MALETA_PD_M, CAT_HOMBRE), (cl.ITEM_MALETA_PD_F, CAT_MUJER)):
        while sig in ids:
            sig += 1
        ids.add(sig)
        nombre, cajas = cl.MALETAS_PD[iid]
        pd.append(dict(id=sig, item=iid, flags=0x1, sort=0, category=cat, quantity=1, price=PRECIO_MALETA_PD,
                       special_price=0, duration=0, start='', end='', limit=0, gift=0, gift_quantity=0,
                       price_source='local: %s, 1 de %d sets PD al azar' % (nombre, len(cajas)),
                       publication=PUBLICACION_PD))
    d['rows'] = orden_unico(agregar(packs(on_sale(rows + nuevas + pd))))
    if 6 + 57 * len(d['rows']) > 65500:
        raise ValueError('el catalogo no cabe en el paquete 0x005F')
    return nuevas, pd


def main():
    texto = JSON.read_bytes()
    d = json.loads(texto)
    # Mismo formato que el archivo: indent 4, ascii y CRLF.
    fmt = lambda x: (json.dumps(x, indent=4, ensure_ascii=True) + '\n').replace('\n', '\r\n').encode('ascii')
    quitar(d)
    nuevas, pd = completar(d)
    print('ofertas del mall.xml que faltaban: %d; maletas PD: %d filas; total %d' % (len(nuevas), len(pd), len(d['rows'])))
    # La tabla de cada maleta: sus 10 maletas de set, mismo peso. drops_bolsas.json va con indent 4,
    # CRLF y sin salto final.
    import cliente_local as cl
    drops = json.loads(DROPS.read_bytes())
    for iid, (_, cajas) in cl.MALETAS_PD.items():
        drops[str(iid)] = [[c, 1, 1] for c in cajas]
    if '--write' in sys.argv:
        JSON.write_bytes(fmt(d))
        DROPS.write_bytes(json.dumps(drops, indent=4, ensure_ascii=False).replace('\n', '\r\n').encode('utf-8'))
        print('escrito', JSON.relative_to(RAIZ), 'y', DROPS.relative_to(RAIZ))


if __name__ == '__main__':
    main()
