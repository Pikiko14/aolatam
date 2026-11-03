"""Las Lucky Bags del Item Mall por clase, montura y craftsman hasta nivel 60 (03/11/2026).

"Podemos cambiar nuestras lucky bag por estos homologos hasta el lvl que manejamos, claro que sera 60 ... lo mismo
con las monturas y los craftsman". El cliente no trae bolsas por clase de nivel 30-60 (solo las Lv70 y Lv210+), asi
que son objetos PROPIOS (item9.xml, como la Lvl 55 Equipment Box de cliente_local), con su contenido sacado de
content.db:

  Lv30/40/50/60 <Clase> Lucky Bag   una pieza de esa clase de nivel N a N+9, azul o amarilla: su arma, su armadura
                                    (pesada 33 Swordsman/Axeman/Lancer, ligera 32 Archer/Assassin, tunica 34 Mage),
                                    y escudo las de espada, hacha y lanza
  Lv35/50/60 Mount Lucky Bag        una montura o robot que pida ese nivel (-5 / +4)
  Lv1-60 Craftsman Lucky Bag        una receta de artesano (armas, armaduras, costura, tecnica, cocina) o un robot de
                                    artesano de nivel 60 o menos

Las amarillas (raras) salen con menos peso que las azules. Escribe server/plantillas/lucky_bags_mall.json (lo leen
cliente_local, para el item9.xml del parche y content.db, y bolsas, para abrirlas: drops_bolsas.json) y cambia en
server/plantillas/item_mall.json las pestanas de Lucky Bag Hot (28) y Monturas (31): 1 por 50 AG, 11 por 500 y
110 por 5000.

    python tools/generar_lucky_bags.py
    python tools/generar_parche.py
"""
import json
import pathlib
import sqlite3
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DB = RAIZ / 'corpus' / 'content.db'
SALIDA = RAIZ / 'server' / 'plantillas' / 'lucky_bags_mall.json'
DROPS = RAIZ / 'server' / 'plantillas' / 'drops_bolsas.json'
MALL = RAIZ / 'server' / 'plantillas' / 'item_mall.json'
sys.stdout.reconfigure(encoding='utf-8')

ID_BASE = 89100
TABLA_BASE = 28900                 # su tabla de premios (動態資料1): libre en drop_table y drop.xml, como las del juego
DROP_XML = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'drop.xml'
MAX_DROP_XML = 40                  # el cliente lee item1..item40 por fila: las de mas premios van sin lista en el tooltip
ICONO = 8747                       # el de las Lv70 <Clase> Lucky Bag
FILA_MALL_BASE = 31000                # el cliente no pinta filas de id 32768 o mas (test_item_mall)
PESTANA_EQUIPO, PESTANA_MONTURA = 28, 31      # Hot ("deben ir en hot", 03/11/2026) y Ride
PACKS = ((1, 50), (11, 500), (110, 5000))      # "debe tener opciones 1, 11 y 110 con precios 50, 500, 5000"
PESO = {'藍': 10, '黃': 3}
TOPE = 60                          # el nivel maximo del servidor: nada que pida mas

CLASES = (                         # nombre, armas, armadura, escudo
    ('Swordsman', ('劍', '刀'), '33', True),
    ('Axeman', ('斧', '錘'), '33', True),
    ('Lancer', ('槍',), '33', True),
    ('Archer', ('弓箭', '彈弓'), '32', False),
    ('Mage', ('杖',), '34', False),
    ('Assassin', ('影刃',), '32', False),
)
NIVELES_CLASE = (60, 50, 40, 30)
# Las de clase Lv60 no se venden ("quita los lvl 60", 03/11/2026): siguen existiendo, para que las que ya se compraron
# se abran, pero no tienen fila en el Item Mall.
FUERA_DEL_MALL = {'Lv60 %s Lucky Bag' % c for c, *_ in CLASES} | {'Lv60 Mount Lucky Bag'}   # "saca todos los lvl 60"
ARMADURA = ('衣服', '頭飾', '手套', '鞋子')
MONTURAS = ((60, 55, 60), (50, 45, 54), (35, 30, 39))
RECETAS = ('26', '27', '28', '29', '31')   # armas, armaduras, costura, tecnica, cocina

# LA PLANTILLA DE LAS BOLSAS DE CLASE. Partio de la Lv60 Axeman Lucky Bag de su captura (sin los Upgrade Coin) y el
# usuario la ajusto (03/11/2026): "que de toda la armadura rara 1%, el arma amarilla 1%, 5% las gemas que sean lvl 40,
# los map pieces quitalos, las skill exp y exp card sean double no triple". Esas tres van exactas; lo demas (arma y
# armadura azul 10, las dos cartas 6 y 6, Super Broadcasting 7, Summon Book 7, Fly Book 8) se reparte el 93% que queda
# en proporcion. Si a una bolsa le falta un tipo de pieza, su parte se reparte entre las demas al sortear.
_RESTO = 93.0 / 54
PLANTILLA = (  # (texto, % de la bolsa, que)
    ('rare weapon', 1.0, 'arma_rara'), ('rare armor', 1.0, 'ropa_rara'),
    ('quality weapon', 10 * _RESTO, 'arma_azul'), ('quality armor', 10 * _RESTO, 'ropa_azul'),
    ('gems x2', 5.0, 'gemas'),
    ('Double Exp Card x3', 6 * _RESTO, (2017, 3)), ('Double Skill Exp Card x3', 6 * _RESTO, (2018, 3)),
    ('Super Broadcasting x2', 7 * _RESTO, (2003, 2)), ('Summon Book x2', 7 * _RESTO, (1333, 2)),
    ('Fly Book x2', 8 * _RESTO, (2987, 2)),
)
GEMAS = ('Ruby', 'Orange Gem', 'Yellow Gem', 'Emerald', 'Sapphire', 'Purple Gem')   # las de nivel 40, sin prefijo


POR_HUECO = 7                      # piezas por hueco de equipo: 4 x 7 + 11 fijos caben en las 40 de una fila de drop.xml


def _mejores(filas):
    """Las POR_HUECO piezas de mas nivel (sin repetir nombre): asi la bolsa cabe en una fila de drop.xml."""
    filas = sorted(_sin_repetir(filas), key=lambda f: (-_n(f['物品等級']), int(f['id'])))
    return [(int(f['id']), 1) for f in filas[:POR_HUECO]]


def _gemas(items):
    nombres = set(GEMAS)
    return sorted({min(int(f['id']) for f in items.values() if f['物品類別'] == '寶石'
                       and (f['基本名稱'] or '').strip() == n) for n in nombres})


def _n(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def _items():
    con = sqlite3.connect(DB)
    filas = {}
    for t in ['item'] + ['item%d' % i for i in range(2, 10)]:
        cols = {c[1] for c in con.execute('pragma table_info(%s)' % t)}
        quiero = ['id', '基本名稱', '物品類別', '物品等級', '等級限制', '技能限制1', '顏色', '持續時間', '動態資料1']
        sel = ','.join(c if c in cols else 'NULL' for c in quiero)
        for r in con.execute('select %s from %s' % (sel, t)):
            filas.setdefault(int(r[0]), dict(zip(quiero, r)))
    con.close()
    return filas


def _vale(f):
    """Un objeto de verdad: nombre en ingles, sin (Trial) ni de tiempo limitado, y no de nuestros ids propios."""
    nombre = (f['基本名稱'] or '').strip()
    return (nombre and nombre.isascii() and 'trial' not in nombre.lower() and 'day' not in nombre.lower()
            and not _n(f['持續時間']) and int(f['id']) < 89000)


def _sin_repetir(filas):
    """Una de cada nombre y color (el juego trae copias del mismo objeto con otros ids)."""
    vistos, out = set(), []
    for f in sorted(filas, key=lambda f: int(f['id'])):
        clave = ((f['基本名稱'] or '').strip(), f['顏色'])
        if clave not in vistos:
            vistos.add(clave)
            out.append(f)
    return out


def bolsas():
    items = _items()
    salida, siguiente = [], ID_BASE
    for nivel in NIVELES_CLASE:
        desde, hasta = (nivel, nivel + 9) if nivel + 9 <= TOPE else (TOPE - 5, TOPE)   # la del tope: 55-60
        for clase, armas, armadura, escudo in CLASES:
            arma = {'黃': [], '藍': []}
            ropa = {'黃': [], '藍': []}
            for f in items.values():
                lv, cat, color = _n(f['物品等級']), f['物品類別'], f['顏色']
                if not (desde <= lv <= hasta) or color not in arma or not _vale(f):
                    continue
                if cat in armas:
                    arma[color].append(f)
                elif (cat in ARMADURA and str(f['技能限制1']) == armadura) or (escudo and cat == '盾'):
                    ropa[color].append(f)
            opciones_de = {'arma_rara': _mejores(arma['黃']), 'ropa_rara': _mejores(ropa['黃']),
                           'arma_azul': _mejores(arma['藍']), 'ropa_azul': _mejores(ropa['藍']),
                           'gemas': [(g, 2) for g in _gemas(items)]}
            huecos = [(txt, pct, opciones_de[que] if isinstance(que, str) else [que]) for txt, pct, que in PLANTILLA]
            contenido = []
            for _txt, pct, opciones in huecos:
                for iid, cuantos in opciones:
                    contenido.append([iid, cuantos, max(1, int(round(pct * 1000 / len(opciones))))])
            total = sum(pct for _txt, pct, opciones in huecos if opciones)
            partes = ['%s %.1f%%' % (txt, 100.0 * pct / total) for txt, pct, opciones in huecos if opciones]
            salida.append({'id': siguiente, 'nombre': 'Lv%d %s Lucky Bag' % (nivel, clase), 'nivel': nivel,
                           'pestana': PESTANA_EQUIPO, 'cantidades': True,
                           'descripcion': 'Open it to get one of the following (Lv%d-%d %s gear): %s.'
                                          % (desde, hasta, clase, ', '.join(partes)),
                           'contenido': contenido})
            siguiente += 1
    for nivel, lo, hi in MONTURAS:
        pool = _sin_repetir([f for f in items.values()
                             if f['物品類別'] in ('座騎', '機甲') and lo <= _n(f['等級限制']) <= min(hi, TOPE) and _vale(f)])
        salida.append({'id': siguiente, 'nombre': 'Lv%d Mount Lucky Bag' % nivel, 'nivel': nivel,
                       'pestana': PESTANA_MONTURA,
                       'descripcion': 'Open it to get one random mount or robot for Lv%d-%d.' % (lo, min(hi, TOPE)),
                       'contenido': [[int(f['id']), 1, PESO.get(f['顏色'], 10)] for f in pool]})
        siguiente += 1
    pool = _sin_repetir([f for f in items.values() if _vale(f) and _n(f['物品等級']) <= 60 and (
        (f['物品類別'] == '配方' and str(f['技能限制1']) in RECETAS)
        or (f['物品類別'] == '機甲' and str(f['技能限制1']) == '25'))])
    salida.append({'id': siguiente, 'nombre': 'Lv1-60 Craftsman Lucky Bag', 'nivel': 1, 'pestana': PESTANA_EQUIPO,
                   'descripcion': 'Open it to get one random craftsman recipe (weapons, armor, sewing, technics or '
                                  'cooking) or craftsman robot up to Lv60.',
                   'contenido': [[int(f['id']), 1, 10] for f in pool]})
    return salida


def filas_mall(defs, base):
    """Las filas del Item Mall: cada bolsa de 1 y de 10, en su pestana."""
    out, orden = [], {PESTANA_EQUIPO: 0, PESTANA_MONTURA: 0}
    for d in defs:
        if d['nombre'] in FUERA_DEL_MALL:
            continue
        for cuantas, precio in PACKS:
            orden[d['pestana']] += 1
            fila = dict(base, id=FILA_MALL_BASE + len(out), item=d['id'], category=d['pestana'],
                        sort=orden[d['pestana']], quantity=cuantas, price=precio, special_price=0,
                        price_source='Lucky Bag por clase (tools/generar_lucky_bags.py)',
                        publication='pedido del usuario 03/11/2026')
            out.append(fila)
    return out


def escribir_drop_xml(defs):
    """Las filas <drop> de las bolsas en el drop.xml del parche: de ahi saca el cliente la lista con los porcentajes del
    tooltip ("Open to get one of the following: ... * 2  14.00000%")."""
    import re
    txt = DROP_XML.read_bytes().decode('utf-8')
    for d in defs:
        txt = re.sub(r'\s*<drop 編號="%d" [^>]*/>' % d['tabla'], '', txt)
    filas = []
    for d in defs:
        if len(d['contenido']) > MAX_DROP_XML:
            continue
        total = sum(w for _, _, w in d['contenido'])
        attrs = ''.join(' item%d="%d" count%d="%d" prob%d="%d"' % (n, it, n, ct, n, w)
                        for n, (it, ct, w) in enumerate(d['contenido'], 1))
        filas.append('    <drop 編號="%d" 怪物名稱="%s" 個數="1" adv_factor="100" factor="%d"%s />'
                     % (d['tabla'], d['nombre'], total, attrs))
    txt = txt.replace('</root>', '\r\n'.join(filas) + '\r\n</root>', 1)
    DROP_XML.write_bytes(txt.encode('utf-8'))


def main():
    defs = bolsas()
    vacias = [d['nombre'] for d in defs if not d['contenido']]
    if vacias:
        raise SystemExit('bolsas sin contenido: %s' % vacias)
    drops = json.loads(DROPS.read_text(encoding='utf-8'))
    for i, d in enumerate(defs):
        d['tabla'] = TABLA_BASE + i
        drops.pop(str(d['id']), None)
        drops[str(d['tabla'])] = d['contenido']
    SALIDA.write_text(json.dumps(defs, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    escribir_drop_xml(defs)
    DROPS.write_bytes(json.dumps(drops, ensure_ascii=False, indent=4).replace('\n', '\r\n').encode('utf-8'))
    mall = json.loads(MALL.read_text(encoding='utf-8'))
    viejas = [r for r in mall['rows'] if r['category'] in (PESTANA_EQUIPO, PESTANA_MONTURA)]
    base = {k: v for k, v in (viejas[0] if viejas else mall['rows'][0]).items()
            if k not in ('price_source', 'publication')}
    base['flags'] = 1
    mall['rows'] = [r for r in mall['rows'] if r['category'] not in (PESTANA_EQUIPO, PESTANA_MONTURA)
                    and not (FILA_MALL_BASE <= int(r['id']) < FILA_MALL_BASE + 1000)] + filas_mall(defs, base)
    MALL.write_bytes((json.dumps(mall, ensure_ascii=False, indent=4) + '\n').replace('\n', '\r\n').encode('utf-8'))
    for d in defs:
        print('%5d %-30s %3d objetos' % (d['id'], d['nombre'], len(d['contenido'])))
    print('Item Mall: %d filas viejas fuera, %d nuevas' % (len(viejas), len(PACKS) * sum(d['nombre'] not in FUERA_DEL_MALL for d in defs)))


if __name__ == '__main__':
    main()
