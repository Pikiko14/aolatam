"""La tienda de honor (26/11/2026): "que salga toda la lista de fashion PD sin bonus y se compre con honor point".

Seis tiendas en Event Overview > Exchange (exchangegroup.xml, filas 4..9) con TODO el fashion PD (物品類別 紙娃娃)
que no da nada: sin HP/MP/ataque/defensa/velocidad/hechizo..., sin set (一階組合), permanente (sin 持續時間 /
使用計時) y con nombre en ingles. Uno por nombre. Se paga con Honor Points (cliente_local.ITEM_HONOR, server/honor.py).

Reescribe exchange.xml y exchangegroup.xml en extracted_paks/update26/setting/eng (lo lee el servidor) y en
parches/extras/setting/eng (va en el parche). Las recetas de estos grupos reusan sus numeros; las nuevas van al final,
seguidas (el cliente se para en el primer hueco: app._obtener_receta_exchange); las que sobran pasan al grupo 0.

    python tools/tienda_honor.py
"""
import glob
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.stdout.reconfigure(encoding='utf-8')

import cliente_local  # noqa: E402

HONOR = cliente_local.ITEM_HONOR
CARPETAS = (RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng', RAIZ / 'parches' / 'extras' / 'setting' / 'eng')
# (fila de exchangegroup, grupo, nombre de la tienda, precio en Honor Points)
TIENDAS = {
    'cabeza': (4, 660, 'Honor: Hats', 20),
    'cuerpo': (5, 661, 'Honor: Outfits', 40),
    'manos_pies': (6, 662, 'Honor: Gloves and Shoes', 15),
    'armas': (7, 663, 'Honor: Weapon Looks', 30),
    'alas': (8, 664, 'Honor: Wings', 120),
    'monturas': (9, 665, 'Honor: Mounts', 150),
}
# Lo que no es un bonus.
NEUTRAS = {'編號', '原型介面', '原型外觀', '基本名稱', '物品類別', 'log等級', '綁定次數', '裝備綁定', '說明定義', '男女裝備',
           '原型名稱', '顏色', '動態資料1', '動態資料2', '身體裝備', '頭部裝備', '腳部裝備', '不可交易', '右手裝備',
           '左手裝備', '手部裝備', '身體袍', '背部裝備', '頭部半罩', '頭部全罩', '抽中廣播', '不可存倉庫', '重量',
           '寵物座騎裝備', '背部另一層', '兌換廣播', '等級限制', '轉盤廣播', '價格', '不打折扣', '收購價格', '物品等級',
           '發光外觀', '可堆疊', '耐久', 'HP定義', 'MP定義'}
FUERA = {'一階組合', '持續時間', '使用計時'}


def tienda_de(a):
    if a.get('寵物座騎裝備'):
        return 'monturas'
    if a.get('背部裝備') or a.get('背部另一層'):
        return 'alas'
    if a.get('右手裝備') or a.get('左手裝備'):
        return 'armas'
    if a.get('身體裝備') or a.get('身體袍'):
        return 'cuerpo'
    if a.get('頭部裝備') or a.get('頭部半罩') or a.get('頭部全罩'):
        return 'cabeza'
    if a.get('手部裝備') or a.get('腳部裝備'):
        return 'manos_pies'
    return None


def sin_bonus(a):
    if FUERA & set(a):
        return False
    for k, v in a.items():
        if k in NEUTRAS:
            continue
        try:
            if float(v) != 0:
                return False
        except ValueError:
            return False
    return True


def catalogo():
    """{tienda: [(id, nombre), ...]} ordenado por nombre."""
    vistos, out = set(), {k: [] for k in TIENDAS}
    archivos = sorted(glob.glob(str(CARPETAS[0] / 'item*.xml')),
                      key=lambda f: int(re.sub(r'\D', '', pathlib.Path(f).stem) or 1))
    for f in archivos:
        t = pathlib.Path(f).read_text(encoding='utf-8', errors='ignore')
        for m in re.finditer(r'<道具 ([^>]*物品類別="紙娃娃"[^>]*?)/?>', t):
            a = dict(re.findall(r'(\S+?)="([^"]*)"', m.group(1)))
            nombre = a.get('基本名稱', '').strip()
            if not nombre or not all(32 <= ord(c) < 127 for c in nombre) or nombre.lower() in vistos:
                continue
            k = tienda_de(a)
            if k is None or not sin_bonus(a):
                continue
            vistos.add(nombre.lower())
            out[k].append((int(a['編號']), nombre))
    for k in out:
        out[k].sort(key=lambda x: (x[1].lower(), x[0]))
    return out


def _esc(t):
    return t.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')


def reescribir_exchange(texto, cat):
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = texto.replace('\r\n', '\n')
    grupos = {g: k for k, (_f, g, _n, _p) in TIENDAS.items()}
    filas = list(re.finditer(r'\t?<exchange 編號="(\d+)" 群組="(\d+)"[^>]*/>', texto))
    ids_max = max(int(f.group(1)) for f in filas)
    recetas = []
    for k, (_f, g, _n, precio) in TIENDAS.items():
        recetas += [(g, iid, nombre, precio) for iid, nombre in cat[k]]
    libres = sorted(int(f.group(1)) for f in filas if int(f.group(2)) in grupos)
    ids = libres[:len(recetas)] + list(range(ids_max + 1, ids_max + 1 + max(0, len(recetas) - len(libres))))
    nuevas = {}
    for num, (g, iid, nombre, precio) in zip(ids, recetas):
        nuevas[num] = ('\t<exchange 編號="%d" 群組="%d" 獎賞說明="%s" 獎賞1="%d" 獎賞1數量="1" 材料1="%d" 材料1數量="%d"/>'
                       % (num, g, _esc(nombre), iid, HONOR, precio))
    sobran = set(libres[len(recetas):])               # las que sobran: grupo 0 (no las abre nadie)
    for f in filas:
        if int(f.group(1)) in sobran:
            nuevas[int(f.group(1))] = re.sub(r'群組="\d+"', '群組="0"', f.group(0), count=1)
    partes, pos = [], 0
    for f in filas:
        num = int(f.group(1))
        if num in nuevas:
            partes.append(texto[pos:f.start()])
            partes.append(nuevas.pop(num))
            pos = f.end()
    partes.append(texto[pos:])
    texto = ''.join(partes)
    if nuevas:
        ultimo = list(re.finditer(r'<exchange [^>]*/>', texto))[-1]
        texto = texto[:ultimo.end()] + ''.join('\n' + nuevas[n] for n in sorted(nuevas)) + texto[ultimo.end():]
    return texto.replace('\n', nl), len(recetas)


def reescribir_grupos(texto):
    nl = '\r\n' if '\r\n' in texto else '\n'
    lineas = texto.replace('\r\n', '\n').split('\n')
    filas = [i for i, l in enumerate(lineas) if l.strip().startswith('<兌換商店')]
    for _k, (fila, g, nombre, _p) in TIENDAS.items():
        i = filas[fila - 1]
        lineas[i] = '\t<兌換商店 編號="%d" 名稱="%s" 群組="%d"/>' % (fila, nombre, g)
    return '\n'.join(lineas).replace('\n', nl)


def main():
    cat = catalogo()
    for k, (_f, g, nombre, precio) in TIENDAS.items():
        print('%-24s grupo %d  %4d objetos  a %d Honor' % (nombre, g, len(cat[k]), precio))
    for carpeta in CARPETAS:
        ex = carpeta / 'exchange.xml'
        texto, n = reescribir_exchange(ex.read_bytes().decode('utf-8'), cat)
        ex.write_bytes(texto.encode('utf-8'))
        eg = carpeta / 'exchangegroup.xml'
        eg.write_bytes(reescribir_grupos(eg.read_bytes().decode('utf-8')).encode('utf-8'))
        print(carpeta, n, 'recetas')


if __name__ == '__main__':
    main()
