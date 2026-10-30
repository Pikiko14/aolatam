"""Item Mall: habilita TODAS las ofertas del mall.xml del cliente que faltaban y anade sets PD.

    python tools/habilitar_mall_completo.py            # dice lo que haria
    python tools/habilitar_mall_completo.py --write    # escribe server/plantillas/item_mall.json

1. Las filas del mall.xml mas nuevo (extracted_paks/*/setting/eng/mall.xml) cuyo (objeto, categoria, cantidad)
   no esta ya en el catalogo entran con su precio, cantidad y duracion originales. Se les quitan las
   fechas de alta/baja (eran promociones de 2008-2012: con fecha no saldrian nunca) y los regalos de
   "compra y llevate" (gift), que el mall local no da. Los objetos de `excluded` no entran.
2. SETS_PD: 10 sets de ropa (紙娃娃) completos, en Ropa de hombre (24) y de mujer (25). Son cajas que
   al abrirse dan TODAS las piezas (bolsas.contenido_descrito, modo 'todo').

Las filas ya publicadas no se tocan. Se puede volver a correr: no duplica nada.
"""
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'server'))
JSON = RAIZ / 'server' / 'plantillas' / 'item_mall.json'

CAT_HOMBRE, CAT_MUJER = 24, 25
# (tema, caja (M), caja (F), precio AG). Precios en la banda de los trajes del mall original (259-989).
SETS_PD = [
    ('Dark Wizard / Dark Witch', 61598, 61599, 899),
    ('Grand Imperial', 35671, 35672, 989),
    ('Lucky Cat', 42129, 42130, 799),
    ('Roman Officer', 57884, 57885, 899),
    ('Fiery Onmyouji', 52424, 52425, 799),
    ('Exion Military', 47699, 47700, 899),
    ('Redheart', 54288, 54289, 799),
    ('Xmas Bunny', 40069, 40070, 699),
    ('Holy Priest / Priestess', 69732, 69733, 899),
    ('Red Kimono', 72513, 72514, 699),
]
PRIMER_ID_PD = 36100
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
    pd = []
    sig = PRIMER_ID_PD
    for i, (tema, m, f, precio) in enumerate(SETS_PD):
        for caja, cat in ((m, CAT_HOMBRE), (f, CAT_MUJER)):
            c = bolsas.contenido_descrito(caja)
            if not c or c[0] != 'todo':
                raise ValueError('la caja %d (%s) no da el set completo' % (caja, tema))
            if (caja, cat, 1) in hay:
                continue
            while sig in ids:
                sig += 1
            ids.add(sig)
            hay.add((caja, cat, 1))
            pd.append(dict(id=sig, item=caja, flags=0x1, sort=i, category=cat, quantity=1, price=precio,
                           special_price=0, duration=0, start='', end='', limit=0, gift=0, gift_quantity=0,
                           price_source='local: set PD exotico (%s, %d piezas)' % (tema, len(c[1])),
                           publication='set PD (tools/habilitar_mall_completo.py)'))
    d['rows'] = rows + nuevas + pd
    if 6 + 57 * len(d['rows']) > 65500:
        raise ValueError('el catalogo no cabe en el paquete 0x005F')
    return nuevas, pd


def main():
    texto = JSON.read_bytes()
    d = json.loads(texto)
    # Mismo formato que el archivo: indent 4, ascii y CRLF.
    fmt = lambda x: (json.dumps(x, indent=4, ensure_ascii=True) + '\n').replace('\n', '\r\n').encode('ascii')
    nuevas, pd = completar(d)
    print('ofertas del mall.xml que faltaban: %d; sets PD: %d filas; total %d' % (len(nuevas), len(pd), len(d['rows'])))
    if '--write' in sys.argv:
        JSON.write_bytes(fmt(d))
        print('escrito', JSON.relative_to(RAIZ))


if __name__ == '__main__':
    main()
