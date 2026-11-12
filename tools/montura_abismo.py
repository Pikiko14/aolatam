"""Las monturas propias: la Abyss Taurus (11/11/2026) y las cuatro de las raids (12/11/2026).

"podriamos crear una nueva montura??" (el toro de la hoja del usuario) y "agregaremos estas 4 monturas como premios en
la raid lvl 50 y 60, 2 y 2, que tengan 10% de darla el jefe final".

LO QUE ES UNA MONTURA EN EL CLIENTE. El objeto (item.xml, 物品類別 座騎) lleva un 原型外觀 N: la entrada N (desde 1)
de la lista <騎乘 號碼=... 高度=...> de setting/chardef.xml, que da el objeto de char.obd (Sequence) y la altura a la que
va el jinete (高度: positivo lo sube). NO es 1200 + N: asi salio con el 714 un robot gato (el 67042 de esa lista). El
caballo blanco (White Horse, 原型外觀 1) es la primera: el 1201 de \\chr\\h001\\, altura 0, con dos animaciones (Wait 3
poses, Run 6 poses) x 5 direcciones en <sequence>_Wait.spr y _Run.spr, frames hw013.. y hr013.. (h montado, w/r,
pose, direccion 3 espalda .. 7 frente; la derecha va en espejo). El jinete NO esta en la montura: cada pieza de su
equipo tiene sus frames de montado y el cliente los pone encima, en el mismo punto de los pies.

EL ANCLA. El de la montura no va en los cascos: en el caballo el dibujo baja PIES_BAJO_EL_ANCLA px por debajo, segun
la direccion. Con el ancla en los cascos el toro flotaba ("parece que esta flotando"). Y en espera cada pose se clava
por los pies y por el centro: si no, la montura bailaba ("porque se mueve tanto cuando esta en wait").

LAS HOJAS (docs/sprites_montura/<clave>/, sin versionar):
  taurus  9 filas x 5 columnas: filas 1-6 Run y 7-9 Wait, columnas las 5 direcciones del juego (la hoja del toro).
  las otras cuatro: 4 columnas (fotogramas) y dos filas por direccion (la primera, de espera; la segunda, de correr),
          en el orden frente, frente-izquierda, izquierda, espalda-izquierda, espalda y las de la derecha. Cada
          montura dice que filas son cada direccion del juego (FILAS) y si alguna hay que voltearla (la del leon que
          mira al frente-izquierda no esta: sale de la del frente-derecha en espejo). Espera 3 poses, correr 4.

Deja, para cada una: parches/extras/shape/chr/<carpeta>/<sequence>_{Wait,Run}.spr, su icono shape/item/<archivo>.shp
y, en un solo bloque cada uno, char.obd, chardef.xml, itemicon4.xml, eng/item.xml; con --db RUTA, los objetos en esa
content.db. Los premios, en server/raid.py (MONTURA_RAID).

    python tools/montura_abismo.py [--db corpus/content.db]
"""
import argparse
import pathlib
import re
import sqlite3
import sys

import numpy as np
from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import fondos_interfaz as fi  # noqa: E402,F401
import mascota_abismo as ma  # noqa: E402
import spr_ewsp  # noqa: E402

EXTRAS = RAIZ / 'parches' / 'extras'
HOJAS = RAIZ / 'docs' / 'sprites_montura'
DESCARGAS = pathlib.Path.home() / 'Downloads'
PRIMER_ASPECTO = 1548              # la lista de chardef.xml del cliente trae 1547: las nuestras van detras, en orden
PIES_BAJO_EL_ANCLA = (13, 12, 7, 14, 16)       # h001 (1201_Wait), por direccion: espalda .. frente
MARCA_INI, MARCA_FIN = 'aolat monturas', '/aolat monturas'
ALTO_OBJETIVO = 105                # alto en px de la pose de frente de las de 8 direcciones (el toro: ~107)
LOMO_TORO = 73                     # el lomo del toro de perfil sobre su ancla (con altura 0 el jinete va sentado;
                                   # con 4 quedaba flotando, 12/11/2026)

S60 = dict(平均攻擊=55, 防禦=55, 魔攻=55, 魔防=55, 精準=8, 靈敏=16, 移動速度=70)
S50 = dict(平均攻擊=45, 防禦=45, 魔攻=45, 魔防=45, 精準=7, 靈敏=14, 移動速度=60)

MONTURAS = [
    dict(clave='taurus', nombre='Abyss Taurus', item=83301, icono=59301, sequence=1914, carpeta='h714', nivel=60,
         stats=S60, altura=0, hoja='abyss_taurus/hoja.webp', tipo='rejilla', escala=0.68,
         descripcion='An armored bull born in the abyss beneath Flamefang. Only raiders who defeat Satrixia have '
                     'been able to tame it.'),
    dict(clave='lion', nombre='Blazemane Lion', item=83302, icono=59302, sequence=1915, carpeta='h715', nivel=60,
         altura=0, stats=S60, hoja='leon/hoja.png', descarga='leon', tipo='ocho',
         filas=((9, 9), (7, 8), (5, 6), (3, 4), (1, 2)), espejo=(False,) * 5,
         descripcion='A lion with a mane of living fire, tamed in the depths of Flamefang.'),
    dict(clave='turtle', nombre='Coral Fortress Turtle', item=83303, icono=59303, sequence=1916, carpeta='h716',
         nivel=60, altura=4, stats=S60, hoja='tortuga/hoja.png', descarga='tortuga', tipo='ocho',
         filas=((9, 10), (7, 8), (5, 6), (3, 4), (1, 2)), espejo=(False,) * 5,
         descripcion='An ancient turtle that carries a coral fortress on its shell.'),
    # Las hojas caricaturescas (12/11/2026, "cambia los sprites por estos mas caricaturescos"): 5 fotogramas por fila
    # y dos filas por direccion, en el orden frente, frente-izq., izquierda, espalda-izq., espalda y las de la derecha.
    dict(clave='ram', nombre='Frostcrown Ram', item=83304, icono=59304, sequence=1917, carpeta='h717', nivel=50,
         altura=0, stats=S50, hoja='carnero/hoja.png', descarga='carnero', tipo='ocho',
         filas=((9, 10), (7, 8), (5, 6), (3, 4), (1, 2)), espejo=(False,) * 5,
         descripcion='A ram crowned with ice from the Warring Realm.'),
    dict(clave='stag', nombre='Aurora Stag', item=83305, icono=59305, sequence=1918, carpeta='h718', nivel=50,
         altura=-14, stats=S50, hoja='ciervo/hoja.png', descarga='ciervo', tipo='ocho',
         filas=((9, 9), (7, 7), (5, 6), (3, 4), (1, 2)), espejo=(False,) * 5,
         descripcion='A stag whose antlers shine like the aurora.'),
]


# ---------------------------------------------------------------------------------------------- recortes
def _sin_fondo(ruta) -> np.ndarray:
    from scipy import ndimage
    im = np.array(Image.open(ruta).convert('RGBA'))
    if im[:, :, 3].min() == 255:
        # fondo blanco: fuera el blanco casi puro que toca el borde de la hoja (el de dentro del dibujo se queda)
        rgb = im[:, :, :3].astype(int)
        blanco = (rgb.min(axis=2) > 232) & (rgb.max(axis=2) - rgb.min(axis=2) < 18)
        manchas, _n = ndimage.label(blanco)
        borde = set(np.unique(np.concatenate([manchas[0], manchas[-1], manchas[:, 0], manchas[:, -1]]))) - {0}
        fondo = np.isin(manchas, list(borde))
        fondo = ndimage.binary_dilation(fondo, iterations=1) & (rgb.min(axis=2) > 205)
        im[fondo, 3] = 0
    return im


def _hoja(m):
    ruta = HOJAS / m['hoja']
    if not ruta.is_file() and m.get('descarga'):
        raise SystemExit('falta %s (copiala de Descargas)' % ruta)
    return ruta


def celdas_rejilla(m, filas=9, columnas=5):
    """La hoja del toro: [fila][columna] -> (imagen recortada, (x, y) de su esquina dentro de su casilla)."""
    from scipy import ndimage
    im = _sin_fondo(_hoja(m))
    mascara = im[:, :, 3] > 16
    etiquetas, n = ndimage.label(mascara, structure=np.ones((3, 3)))
    alto, ancho = mascara.shape
    cw, ch = ancho / columnas, alto / filas
    tam = ndimage.sum(mascara, etiquetas, range(1, n + 1))
    centros = ndimage.center_of_mass(mascara, etiquetas, range(1, n + 1))
    de = {}
    for i, (t, (cy, cx)) in enumerate(zip(tam, centros), 1):
        if t >= 30:
            de.setdefault((min(filas - 1, int(cy // ch)), min(columnas - 1, int(cx // cw))), []).append(i)
    tabla = []
    for f in range(filas):
        fila = []
        for c in range(columnas):
            mm = np.isin(etiquetas, de.get((f, c), []))
            ys, xs = np.where(mm)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            trozo = im[y0:y1, x0:x1].copy()
            trozo[~mm[y0:y1, x0:x1]] = 0
            fila.append((Image.fromarray(trozo, 'RGBA'), (x0 - c * cw, y0 - f * ch)))
        tabla.append(fila)
    return tabla


def filas_ocho(m):
    """Las hojas de 8 direcciones: [fila] -> [4 imagenes recortadas], filas por su altura y fotogramas por su x."""
    from scipy import ndimage
    im = _sin_fondo(_hoja(m))
    mascara = im[:, :, 3] > 20
    etiquetas, n = ndimage.label(ndimage.binary_closing(mascara, iterations=2), structure=np.ones((3, 3)))
    cajas = ndimage.find_objects(etiquetas)
    tam = ndimage.sum(mascara, etiquetas, range(1, n + 1))
    trozos = []
    for i, (caja, t) in enumerate(zip(cajas, tam), 1):
        if t < 800:
            continue
        trozo = im[caja].copy()
        trozo[etiquetas[caja] != i] = 0
        trozos.append(((caja[0].start + caja[0].stop) / 2, caja[1].start, Image.fromarray(trozo, 'RGBA')))
    trozos.sort(key=lambda t: t[0])
    filas = []
    for y, x, t in trozos:
        if filas and abs(filas[-1][0] - y) < 35:
            filas[-1][1].append((x, t))
        else:
            filas.append([y, [(x, t)]])
    return [[t for _x, t in sorted(f[1], key=lambda a: a[0])] for f in filas]


def _suelo(im):
    """La fila mas baja con dibujo (sin el halo casi transparente)."""
    caja = im.getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox()
    return caja[3] if caja else im.height


def _clavar(im, c):
    """El ancla de una pose: el centro del dibujo y sus pies PIES_BAJO_EL_ANCLA[c] por debajo."""
    caja = im.getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox() or (0, 0, im.width, im.height)
    return (round((caja[0] + caja[2]) / 2), _suelo(im) - PIES_BAJO_EL_ANCLA[c])


def _escalar(im, k):
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)


def frames_rejilla(m):
    """El toro: Run de las filas 1-6 con el ancla de su casilla; Wait de las 7-9 clavada por los pies."""
    tabla = celdas_rejilla(m)
    k = m['escala']
    salida = {}
    for anim, filas in (('run', range(0, 6)), ('wait', range(6, 9))):
        lista = []
        for f in filas:
            for c in range(5):
                im, (x, y) = tabla[f][c]
                im2 = _escalar(im, k)
                if anim == 'wait':
                    lista.append((im2, _clavar(im2, c)))
                    continue
                propias = [tabla[g][c] for g in filas]
                pie_x = sum(p[1][0] + p[0].width / 2 for p in propias) / len(propias)
                pie_y = max(p[1][1] + p[0].height for p in propias)
                lista.append((im2, (round((pie_x - x) * k), round((pie_y - y) * k))))
        if anim == 'run':
            for c in range(5):
                mios = [lista[i] for i in range(c, len(lista), 5)]
                delta = PIES_BAJO_EL_ANCLA[c] - max(_suelo(im) - oy for im, (_ox, oy) in mios)
                for i in range(c, len(lista), 5):
                    im, (ox, oy) = lista[i]
                    lista[i] = (im, (ox, oy - delta))
        salida[anim] = lista
    return salida


# El alto de la pose de espera del toro en cada direccion (espalda .. frente). Las hojas de 8 direcciones traen
# algunas direcciones mas pequenas (el leon de perfil 82 px y de frente 105: "el leon no se ve del mismo tamano en
# todas las direcciones", 12/11/2026): cada direccion se escala a la del toro.
ALTOS_TORO = (111, 114, 103, 97, 107)


def frames_ocho(m):
    filas = filas_ocho(m)
    salida = {}
    # Una sola escala por montura (12/11/2026, "se ven mal algunos tamanos en ciertas direcciones"): las hojas
    # caricaturescas ya traen las direcciones a la misma escala (de perfil es mas baja porque se ve de lado); forzar
    # cada una al alto del toro las deformaba. El alto medio de sus 5 direcciones, el del toro.
    altos = []
    for c in range(5):
        espera = filas[m['filas'][c][0] - 1][0]
        caja = espera.getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox()
        altos.append(caja[3] - caja[1])
    escala = [sum(ALTOS_TORO) / sum(altos)] * 5
    for anim, cual, poses in (('wait', 0, (0, 1, 2)), ('run', 1, (0, 1, 2, 3, 4))):
        lista = []
        for p in poses:
            for c in range(5):
                fila = filas[m['filas'][c][cual] - 1]
                im = _escalar(fila[p % len(fila)], escala[c])
                if m['espejo'][c]:
                    im = im.transpose(Image.FLIP_LEFT_RIGHT)
                lista.append((im, _clavar(im, c)))
        salida[anim] = lista
    return salida


def frames(m):
    return frames_rejilla(m) if m['tipo'] == 'rejilla' else frames_ocho(m)


def lomo(fr):
    """El alto del lomo de perfil (direccion 5) sobre el ancla: lo mas alto del dibujo cerca del ancla."""
    im, (ox, oy) = fr['wait'][2]
    a = im.getchannel('A').load()
    altos = []
    for dx in (-6, -3, 0, 3, 6):
        x = ox + dx
        if 0 <= x < im.width:
            y = next((y for y in range(im.height) if a[x, y] > 100), None)
            if y is not None:
                altos.append(oy - y)
    return sorted(altos)[len(altos) // 2] if altos else LOMO_TORO


def icono(m, fr) -> bytes:
    im, _ = fr['wait'][2]                                   # de perfil
    return ma._tlhs_suelto(ma._cuadrado(im, 36), r'shape\item\i0004.shp', 0, 0)


# ---------------------------------------------------------------------------------------------- datos del cliente
def bloque_char_obd(m) -> str:
    s = m['sequence']
    if m['tipo'] == 'rejilla':
        run = 'hr013*, #7, !CharSmokeTwo, hr023*, hr033*, hr043*, hr053*, hr063*'
    else:
        run = 'hr013*, #7, !CharSmokeTwo, hr023*, hr033*, hr043*, hr053*'
    return '\r\n'.join((
        '[OBJECT]',
        'Name = %s %s' % (m['carpeta'].upper(), m['nombre']),
        'Sequence = %d' % s,
        'Directory = \\chr\\%s\\' % m['carpeta'],
        'Sprite = Wait, hw013*, #12, hw023*, hw033*, hw023*',
        'Sprite = Run, %s' % run,
        'SpriteFile = Wait, %d_Wait.spr' % s,
        'SpriteFile = Run, %d_Run.spr' % s,
        '', ''))


def _quitar_viejos(texto, *marcas):
    for ini, fin in marcas:
        texto = ma._sin_bloque(texto, ini, fin)
    return texto


VIEJAS = ('aolat abyss taurus', '/aolat abyss taurus')       # el bloque de cuando solo estaba el toro


def char_obd():
    texto, bom, nl = ma._texto_base(r'setting\char.obd')
    texto = _quitar_viejos(texto, ('; ' + MARCA_INI, '; ' + MARCA_FIN), ('; ' + VIEJAS[0], '; ' + VIEJAS[1]))
    cuerpo = ''.join(bloque_char_obd(m).replace('\r\n', nl) for m in MONTURAS)
    bloque = '; %s%s%s; %s%s' % (MARCA_INI, nl, cuerpo, MARCA_FIN, nl)
    ma._guardar(r'setting\char.obd', texto.rstrip() + nl + nl + bloque, bom, latin=True)


def chardef_xml(alturas):
    """Sus <騎乘> justo detras del ultimo de la lista: el cliente los cuenta en orden y el 原型外觀 es esa cuenta."""
    texto, bom, nl = ma._texto_base(r'setting\chardef.xml')
    texto = _quitar_viejos(texto, ('<!-- %s -->' % MARCA_INI, '<!-- %s -->' % MARCA_FIN),
                           ('<!-- %s -->' % VIEJAS[0], '<!-- %s -->' % VIEJAS[1]))
    filas = list(re.finditer(r'<騎乘 [^>]*/>[^\n]*\n?', texto))
    if len(filas) + 1 != PRIMER_ASPECTO:
        raise SystemExit('chardef.xml trae %d monturas: la primera nuestra seria %d, no %d'
                         % (len(filas), len(filas) + 1, PRIMER_ASPECTO))
    fin = filas[-1].end()
    lineas = ''.join('\t<騎乘 號碼="%d" 高度="%d" 層級="DOLL_LAYER_RIDE" 種類="0"/>%s' % (m['sequence'], alturas[m['clave']], nl)
                     for m in MONTURAS)
    bloque = '\t<!-- %s -->%s%s\t<!-- %s -->%s' % (MARCA_INI, nl, lineas, MARCA_FIN, nl)
    ma._guardar(r'setting\chardef.xml', texto[:fin] + bloque + texto[fin:], bom)


def aspecto(m):
    return PRIMER_ASPECTO + MONTURAS.index(m)


def _xml_con(relativa, lineas, cierre='</'):
    texto, bom, nl = ma._texto_base(relativa)
    texto = _quitar_viejos(texto, ('<!-- %s -->' % MARCA_INI, '<!-- %s -->' % MARCA_FIN),
                           ('<!-- %s -->' % VIEJAS[0], '<!-- %s -->' % VIEJAS[1]))
    bloque = ('\t<!-- %s -->%s' % (MARCA_INI, nl) + ''.join('\t%s%s' % (l, nl) for l in lineas)
              + '\t<!-- %s -->%s' % (MARCA_FIN, nl))
    fin = texto.rindex(cierre)
    ma._guardar(relativa, texto[:fin] + bloque + texto[fin:], bom)


def fila_item(m) -> str:
    stats = ' '.join('%s="%d"' % kv for kv in m['stats'].items())
    return ('<道具 編號="%d" 原型介面="%d" 原型外觀="%d" 基本名稱="%s" 物品類別="座騎" 物品等級="%d" 等級限制="%d" %s '
            '重量="160" 價格="3000000" 綁定次數="3" 顏色="黃" log等級="80" 說明定義="%s" 寵物座騎裝備="是" 裝備綁定="是" '
            '抽中廣播="是" 收購價格="6000" />' % (m['item'], m['icono'], aspecto(m), m['nombre'], m['nivel'], m['nivel'],
                                              stats, m['descripcion']))


def content_db(ruta):
    """Los objetos en la tabla item de content.db: copias de la Flame Eagle (5128) con lo suyo."""
    con = sqlite3.connect(ruta)
    cols = [c[1] for c in con.execute('pragma table_info(item)')]
    base = dict(zip(cols, con.execute("select * from item where id='5128'").fetchone()))
    nombres = {'平均攻擊': ('atk_avg', 'atk'), '防禦': ('def',), '魔攻': ('matk',), '魔防': ('mdef',),
               '精準': ('accuracy',), '靈敏': ('agility',)}
    for m in MONTURAS:
        fila = dict(base)
        fila.update({'id': str(m['item']), '原型介面': str(m['icono']), '原型外觀': str(aspecto(m)),
                     '基本名稱': m['nombre'], '原型名稱': None, 'move_speed': str(m['stats']['移動速度'])})
        for k in ('物品等級', '等級限制'):
            if k in fila:
                fila[k] = str(m['nivel'])
        for k, v in m['stats'].items():
            for col in (k,) + nombres.get(k, ()):
                if col in fila:
                    fila[col] = str(v)
        if '說明定義' in fila:
            fila['說明定義'] = m['descripcion']
        con.execute('delete from item where id=?', (str(m['item']),))
        con.execute('insert into item (%s) values (%s)' % (','.join('"%s"' % c for c in cols), ','.join('?' * len(cols))),
                    [fila[c] for c in cols])
    con.commit()
    con.close()
    print('content.db: %d monturas en %s' % (len(MONTURAS), ruta))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', help='solo meter los objetos en esa content.db')
    a = ap.parse_args()
    if a.db:
        content_db(pathlib.Path(a.db))
        return
    alturas = {}
    for m in MONTURAS:
        fr = frames(m)
        carpeta = EXTRAS / 'shape' / 'chr' / m['carpeta']
        carpeta.mkdir(parents=True, exist_ok=True)
        for anim, lista in fr.items():
            (carpeta / ('%d_%s.spr' % (m['sequence'], anim.capitalize()))).write_bytes(
                spr_ewsp.escribir(lista, anim, prefijo='h'))
        (EXTRAS / 'shape' / 'item').mkdir(parents=True, exist_ok=True)
        (EXTRAS / 'shape' / 'item' / ('i%d.shp' % (m['icono'] - 50000))).write_bytes(icono(m, fr))
        # la altura del jinete: la del toro (probada en el juego) corregida por lo que su lomo sube o baja
        # la altura del jinete, a ojo contra la silla del toro (altura 0): medir el lomo engania con melenas,
        # cuernos y lana (el carnero salia con 17 y el jinete flotaba, 12/11/2026)
        alturas[m['clave']] = m['altura']
        print('%-22s %s seq %d aspecto %d altura %d' % (m['nombre'], m['carpeta'], m['sequence'], aspecto(m),
                                                        alturas[m['clave']]))
    char_obd()
    chardef_xml(alturas)
    _xml_con(r'setting\itemicon4.xml', ['<icon id="%d" dir="\\item\\" normal="i%d" focus="normal" down="normal" '
                                        'disable="normal"/>' % (m['icono'], m['icono'] - 50000) for m in MONTURAS])
    _xml_con(r'setting\eng\item.xml', [fila_item(m) for m in MONTURAS])
    content_db(RAIZ / 'corpus' / 'content.db')


if __name__ == '__main__':
    main()
