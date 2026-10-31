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
PRIMER_ID_PD = 36100
PUBLICACION_PD = 'set PD (tools/habilitar_mall_completo.py)'
CAT_ON_SALE, CAT_TELEPORTE = 23, 27
# Maple Mark, Maple Teleportation Scroll, Mark Stone, Mark Portal Scroll.
ON_SALE = (20565, 20566, 3693, 3694)
PUBLICACION_ON_SALE = 'On Sale (tools/habilitar_mall_completo.py)'


# Quitadas por el usuario de la pestana Lucky Bag (28): las 2013 Taurus de las 7 clases.
QUITADAS = {31441: '2013 Taurus Swordman Lucky Bag', 31442: '2013 Taurus Axeman Lucky Bag',
            31443: '2013 Taurus Spearman Lucky Bag', 31444: '2013 Taurus Archer Lucky Bag',
            31445: '2013 Taurus Master Lucky Bag', 31446: '2013 Taurus Assassin Lucky Bag',
            31447: '2013 Taurus Artisan Lucky Bag'}


def quitar(d):
    ya = {int(e['item']) for e in d.setdefault('excluded', [])}
    d['excluded'] += [dict(item=i, name=n, reason='Removed from Lucky Bag tab by user')
                      for i, n in QUITADAS.items() if i not in ya]
    d['rows'] = [r for r in d['rows'] if r['item'] not in QUITADAS]


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
        sig = max(ids | {40000}) + 1
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


def completar(d):
    import bolsas
    rows = d['rows']
    ids = {r['id'] for r in rows}
    hay = {(r['item'], r['category'], r['quantity']) for r in rows}
    fuera = {int(e['item']) for e in d.get('excluded', [])}
    nuevas = []
    for r in filas_originales():
        if (r['item'], r['category'], r['quantity']) in hay or r['item'] in fuera:
            continue
        if r['id'] in ids:
            r['id'] = max(ids | {40000}) + 1          # choca con una local: va despues de las nativas
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
    d['rows'] = on_sale(rows + nuevas + pd)
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
