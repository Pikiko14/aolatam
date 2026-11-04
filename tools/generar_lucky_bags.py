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
# usuario la ajusto (03/11/2026): "que de toda la armadura rara 1%, 5% las gemas que sean lvl 40, los map pieces
# quitalos, las skill exp y exp card sean double no triple", y "que el arma sea 55 o 50, la 55 1% la 50 5%": el arma
# del nivel de la bolsa (N a N+4) al 5% y la de cinco niveles mas (N+5 a N+9) al 1%, azules y amarillas. Esas van
# exactas; lo demas (armadura azul 10, las dos cartas 6 y 6, Super Broadcasting 7, Summon Book 7, Fly Book 8) se reparte
# lo que queda en proporcion. Si a una bolsa le falta un tipo de pieza, su parte se reparte entre las demas al sortear.
_RESTO = 88.0 / 44
PLANTILLA = (  # (texto, % de la bolsa, que)
    ('weapon (bag level)', 5.0, 'arma_baja'), ('weapon (+5 levels)', 1.0, 'arma_alta'),
    ('rare armor', 1.0, 'ropa_rara'), ('quality armor', 10 * _RESTO, 'ropa_azul'),
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
            armas_todas = arma['黃'] + arma['藍']
            corte = desde + 5
            opciones_de = {'arma_baja': _mejores([f for f in armas_todas if _n(f['物品等級']) < corte]),
                           'arma_alta': _mejores([f for f in armas_todas if _n(f['物品等級']) >= corte]),
                           'ropa_rara': _mejores(ropa['黃']), 'ropa_azul': _mejores(ropa['藍']),
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
        contenido, texto = bolsa_de_monturas(items, lo, min(hi, TOPE))
        salida.append({'id': siguiente, 'nombre': 'Lv%d Mount Lucky Bag' % nivel, 'nivel': nivel,
                       'pestana': PESTANA_MONTURA, 'cantidades': True,
                       'descripcion': 'Open it to get one of the following: %s.' % texto,
                       'contenido': contenido})
        siguiente += 1
    # La de Craftsman (03/11/2026): "lo de robot lvl 40-50-60, den cartas de x2 recoleccion 1 o cartas de
    # manufactura 1, set de recolector" (ver set_recolector). Ya no da recetas.
    contenido = [[498, 1, 30000], [499, 1, 30000]]                     # Collecting / Facture Speedup Card (30 M.)
    piezas = set_recolector()
    contenido += [[p['id'], 1, 30000 // len(piezas)] for p in piezas]
    for pct, robots in ((5000, (7344, 7345)), (3500, (6715, 6716, 3730, 3731)), (1500, (9100, 9101))):
        contenido += [[r, 1, pct // len(robots)] for r in robots]
    salida.append({'id': siguiente, 'nombre': 'Lv1-60 Craftsman Lucky Bag', 'nivel': 1, 'pestana': PESTANA_EQUIPO,
                   'descripcion': 'Open it to get one of the following: Collecting Speedup Card 30%, Facture Speedup '
                                  "Card 30%, a Gatherer's set piece (Lv40/50/60, +Maximum Weight) 30%, a craftsman "
                                  'robot Lv40 5%, Lv50 3.5%, Lv60 1.5%.',
                   'contenido': contenido})
    return salida


# LAS MOUNT LUCKY BAG (04/11/2026): "con solo 22 bags me salieron cosas rotas"; "que salga por cada item 5% para abajo,
# a los mas rotos 0.1%"; "en las monturas mete ride feed y monturas bajas, las lvl 50+ 5% para abajo"; sin subir el
# precio. Antes cada bolsa daba SIEMPRE una montura de su nivel. Ahora (en % de la bolsa):
#   las monturas de su nivel   MONTURAS_PROPIAS (10% la Lv35; 5% la Lv50 y la Lv60, que son de nivel 45+/55+), y dentro
#                              las mas fuertes (el FUERTES de arriba por ataque+defensa+agilidad+velocidad) al 0.1% cada una
#   monturas mas bajas         MONTURAS_BAJAS en total (niveles 10 hasta el de la bolsa - 1), 5% como mucho cada una
#   Ride Feed x5               el resto
# Las pesos van en milesimas de % (100000 = 100%) y la bolsa da las cantidades de su plantilla ('cantidades').
RIDE_FEED, RIDE_FEED_CUANTOS = 4457, 5
MONTURAS_PROPIAS = {35: 10.0, 50: 5.0, 60: 5.0}
MONTURAS_BAJAS = 25.0
FUERTES, PCT_FUERTE, TOPE_CADA = 0.15, 0.1, 5.0
STATS_MONTURA = ('atk_avg', 'matk', 'def', 'mdef', 'accuracy', 'agility', 'move_speed')


def _fuerza(f):
    return sum(_n(f.get(c)) for c in STATS_MONTURA)


def _monturas(items, lo, hi):
    return _sin_repetir([f for f in items.values()
                         if f['物品類別'] in ('座騎', '機甲') and lo <= _n(f['等級限制']) <= hi and _vale(f)])


def bolsa_de_monturas(items, lo, hi):
    """(contenido [[item, cantidad, peso]], texto del tooltip) de la Mount Lucky Bag de niveles lo..hi."""
    nivel = next(n for n, a, b in MONTURAS if a == lo)
    propias = sorted(_monturas(items, lo, hi), key=lambda f: (-_fuerza(f), int(f['id'])))
    bajas = _monturas(items, 10, lo - 1)
    n_fuertes = max(1, int(round(len(propias) * FUERTES))) if len(propias) > 1 else 0
    fuertes, normales = propias[:n_fuertes], propias[n_fuertes:]
    pct = {}
    total_propias = MONTURAS_PROPIAS[nivel]
    for f in fuertes:
        pct[int(f['id'])] = PCT_FUERTE
    if normales:
        cada = min(TOPE_CADA, (total_propias - PCT_FUERTE * len(fuertes)) / len(normales))
        for f in normales:
            pct[int(f['id'])] = cada
    if bajas:
        cada = min(TOPE_CADA, MONTURAS_BAJAS / len(bajas))
        for f in bajas:
            pct.setdefault(int(f['id']), cada)
    feed = 100.0 - sum(pct.values())
    contenido = [[RIDE_FEED, RIDE_FEED_CUANTOS, int(round(feed * 1000))]]
    contenido += [[iid, 1, max(1, int(round(p * 1000)))] for iid, p in pct.items()]
    suma_propias = sum(pct[int(f['id'])] for f in propias)
    suma_bajas = sum(pct[int(f['id'])] for f in bajas)
    texto = ('Ride Feed x%d %.1f%%, a lower-level mount or robot (Lv10-%d) %.1f%% (%.2f%% each), a Lv%d-%d mount or '
             'robot %.1f%% (the strongest %.1f%% each)') % (RIDE_FEED_CUANTOS, feed, lo - 1, suma_bajas,
                                                            suma_bajas / max(1, len(bajas)), lo, hi, suma_propias,
                                                            PCT_FUERTE)
    return contenido, texto


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


# EL SET DE RECOLECTOR (03/11/2026): "set de recolector, valida si hay algun set que suba la carga que sea de ese lvl,
# sino crealo". No hay ninguno (solo los Gathering Gloves de nivel 1 y 5, sin carga), asi que se crea: cuatro piezas por
# nivel clonadas de la armadura ligera sencilla de ese nivel (su icono, su apariencia y su ranura), sin restriccion de
# clase, con la mitad de su defensa y la carga (負重) de CARGA_SET por pieza. Items propios de item9.xml como las bolsas.
SET_RECOLECTOR = SALIDA.with_name('set_recolector.json')
ID_SET = 89130
XML_ITEMS = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng'
PIEZAS_SET = (  # nivel, carga por pieza, (base, nombre) de gorro, ropa, guantes y botas
    (40, 500, ((1666, 'Cap'), (1696, 'Vest'), (1630, 'Gloves'), (1650, 'Boots'))),
    (50, 750, ((1667, 'Cap'), (1697, 'Vest'), (1631, 'Gloves'), (1651, 'Boots'))),
    (60, 1000, ((1668, 'Cap'), (1698, 'Vest'), (1632, 'Gloves'), (1652, 'Boots'))),
)


def set_recolector():
    import re
    lineas = {}
    for f in sorted(XML_ITEMS.glob('item*.xml')):
        for m in re.finditer(r'<道具 編號="(\d+)"[^>]*/>', f.read_bytes().decode('utf-8', 'replace')):
            lineas.setdefault(int(m.group(1)), m.group(0))
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    salida, siguiente = [], ID_SET
    for nivel, carga, piezas in PIEZAS_SET:
        for base, pieza in piezas:
            nombre = "Lv%d Gatherer's %s" % (nivel, pieza)
            desc = "Gatherer's set: +%d Maximum Weight (+%d with the 4 pieces). Any class." % (carga, carga * 4)
            tag = lineas[base]
            tag = re.sub(r'編號="\d+"', '編號="%d"' % siguiente, tag, count=1)
            tag = re.sub(r'基本名稱="[^"]*"', '基本名稱="%s"' % nombre.replace('"', "'"), tag, count=1)
            tag = re.sub(r'物品等級="\d+"', '物品等級="%d"' % nivel, tag, count=1)
            tag = re.sub(r' 技能限制1="[^"]*"| 技能等限="[^"]*"| 原型名稱="[^"]*"', '', tag)
            for attr in ('防禦', '魔防'):
                tag = re.sub(r'%s="(\d+)"' % attr, lambda m: '%s="%d"' % (attr, max(1, int(m.group(1)) // 2)), tag, 1)
            tag = tag[:-2].rstrip() + ' 等級限制="%d" 負重="%d" 說明定義="%s" />' % (nivel, carga, desc)
            fila = None
            for t in ['item'] + ['item%d' % i for i in range(2, 10)]:
                fila = con.execute('select * from %s where id=?' % t, (str(base),)).fetchone()
                if fila:
                    fila = dict(fila)
                    break
            fila.update({'id': str(siguiente), '基本名稱': nombre, '物品等級': str(nivel), '等級限制': str(nivel),
                         '技能限制1': None, '技能等限': None, '原型名稱': None, '負重': str(carga), '說明定義': desc,
                         'def': str(max(1, _n(fila.get('def')) // 2)), 'mdef': str(max(1, _n(fila.get('mdef')) // 2)),
                         '_pak': 'update26'})
            salida.append({'id': siguiente, 'nombre': nombre, 'nivel': nivel, 'linea': '    ' + tag.strip(),
                           'fila': fila})
            siguiente += 1
    con.close()
    return salida


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
    SET_RECOLECTOR.write_text(json.dumps(set_recolector(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
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
