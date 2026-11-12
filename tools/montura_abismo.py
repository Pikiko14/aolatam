"""La montura Abyss Taurus (11/11/2026): "podriamos crear una nueva montura??", un toro alado de la hoja del usuario.

LO QUE ES UNA MONTURA EN EL CLIENTE. El objeto (item.xml, 物品類別 座騎) lleva un 原型外觀 N: la entrada N (desde 1)
de la lista <騎乘 號碼=... 高度=...> de setting/chardef.xml, que da el objeto de char.obd (Sequence) y la altura a la que
va el jinete. NO es 1200 + N: asi salio con el 714 un robot gato (el 67042 de esa lista, 11/11/2026). El caballo blanco
(White Horse, 原型外觀 1) es la primera: el 1201 de \\chr\\h001\\, altura 0, con dos animaciones (Wait 3 poses, Run 6 poses) x 5 direcciones en <sequence>_Wait.spr y _Run.spr, frames hw013.. y
hr013.. (h montado, w/r, pose, direccion 3 espalda .. 7 frente; la derecha va en espejo). El jinete NO esta en la
montura: cada pieza de su equipo tiene sus frames de montado (el sprite +5000: 36001 frente a 31001 a pie) y el cliente
los pone encima, en el mismo punto de los pies. Por eso la montura tiene que tener la altura de lomo de un caballo.

LA HOJA (docs/sprites_montura/abyss_taurus/hoja.webp, sin versionar): 9 filas x 5 columnas con fondo transparente;
las filas 1-6 son Run y las 7-9 Wait, las columnas las 5 direcciones en el orden del juego. Cada frame se saca por
manchas conectadas (las alas se salen de su casilla) y el punto de los pies sale de la pose de espera de cada
direccion, el mismo para todas sus poses (asi no baila).

Deja:
  parches/extras/shape/chr/h714/1914_{Wait,Run}.spr     los sprites
  parches/extras/shape/item/i9301.shp                   el icono (36x36)
  parches/extras/setting/char.obd                       el objeto 1914 (como el H001)
  parches/extras/setting/chardef.xml                    su <騎乘> al final de la lista: el 原型外觀 ASPECTO
  parches/extras/setting/itemicon4.xml                  el icono 59301
  parches/extras/setting/eng/item.xml                   la fila del objeto 83301
y con --db RUTA mete el objeto en esa content.db. Nivel 60, la velocidad de las mas rapidas (move_speed 70) y los
stats de las S de nivel 60 un poco mejores. Sale del ultimo jefe de la Flamefang (server/raid.py, MONTURA_RAID).

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
import fondos_interfaz as fi  # noqa: E402
import mascota_abismo as ma  # noqa: E402
import spr_ewsp  # noqa: E402

HOJA = RAIZ / 'docs' / 'sprites_montura' / 'abyss_taurus' / 'hoja.webp'
EXTRAS = RAIZ / 'parches' / 'extras'
SEQUENCE = 1914                    # el objeto de char.obd (libre en char*.obd)
CARPETA = 'h714'                   # su carpeta de sprites (libre en los paks)
ASPECTO = 1548                     # su <騎乘> en chardef.xml: la lista del cliente trae 1547 y va la siguiente
ALTURA = 5                         # el 高度 del jinete (negativo lo baja): medido en vertical sobre el ancla, el lomo
                                   # del toro queda igual o 3-7 px mas alto que el del caballo. Con -17 se hundia en
                                   # el toro ("parece que estoy en medio de la montura", 12/11/2026).
ITEM = 83301
ICONO, ARCHIVO_ICONO = 59301, 'i9301'
NOMBRE = 'Abyss Taurus'
ESCALA = 0.68                      # la altura de lomo del caballo blanco (h001): el jinete queda sentado encima
FILAS, COLUMNAS = 9, 5
POSES = {'run': range(0, 6), 'wait': range(6, 9)}
MARCA_INI, MARCA_FIN = 'aolat abyss taurus', '/aolat abyss taurus'
STATS = dict(平均攻擊=55, 防禦=55, 魔攻=55, 魔防=55, 精準=8, 靈敏=16, 移動速度=70)
DESCRIPCION = ('An armored bull born in the abyss beneath Flamefang. Only raiders who defeat Satrixia '
               'have been able to tame it.')


def celdas():
    """[fila][columna] -> (imagen RGBA recortada, (x, y) de su esquina dentro de su casilla)."""
    from scipy import ndimage
    im = np.array(Image.open(HOJA).convert('RGBA'))
    if im[:, :, 3].min() == 255:
        # Hoja con fondo blanco (11/11/2026, el toro sin alas): fuera el blanco casi puro que toca el borde de la hoja;
        # el que queda dentro del dibujo (brillos de los cuernos y del oro) se conserva.
        rgb = im[:, :, :3].astype(int)
        blanco = (rgb.min(axis=2) > 232) & (rgb.max(axis=2) - rgb.min(axis=2) < 18)
        manchas, _n = ndimage.label(blanco)
        borde = set(np.unique(np.concatenate([manchas[0], manchas[-1], manchas[:, 0], manchas[:, -1]]))) - {0}
        fondo = np.isin(manchas, list(borde))
        fondo = ndimage.binary_dilation(fondo, iterations=1) & (rgb.min(axis=2) > 205)    # el halo claro del borde
        im[fondo, 3] = 0
    mascara = im[:, :, 3] > 16
    etiquetas, n = ndimage.label(mascara, structure=np.ones((3, 3)))
    alto, ancho = mascara.shape
    cw, ch = ancho / COLUMNAS, alto / FILAS
    tam = ndimage.sum(mascara, etiquetas, range(1, n + 1))
    centros = ndimage.center_of_mass(mascara, etiquetas, range(1, n + 1))
    de = {}
    for i, (t, (cy, cx)) in enumerate(zip(tam, centros), 1):
        if t >= 30:
            de.setdefault((min(FILAS - 1, int(cy // ch)), min(COLUMNAS - 1, int(cx // cw))), []).append(i)
    tabla = []
    for f in range(FILAS):
        fila = []
        for c in range(COLUMNAS):
            m = np.isin(etiquetas, de.get((f, c), []))
            ys, xs = np.where(m)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            trozo = im[y0:y1, x0:x1].copy()
            trozo[~m[y0:y1, x0:x1]] = 0
            fila.append((Image.fromarray(trozo, 'RGBA'), (x0 - c * cw, y0 - f * ch)))
        tabla.append(fila)
    return tabla


def frames():
    """{'wait'|'run': [(imagen, (ox, oy))] en el orden del .spr (pose * 5 + direccion)}."""
    tabla = celdas()
    salida = {}
    for anim, filas in POSES.items():
        lista = []
        for f in filas:
            for c in range(COLUMNAS):
                im, (x, y) = tabla[f][c]
                # El punto de los pies de cada direccion sale de las poses de ESA animacion (el centro y el suelo
                # mas bajo de todas): en la hoja las de correr estan mas abajo en su casilla que las de espera, y con
                # el suelo de la espera el toro corria hundido bajo el jinete.
                propias = [tabla[g][c] for g in filas]
                pie_x = sum(p[1][0] + p[0].width / 2 for p in propias) / len(propias)
                pie_y = max(p[1][1] + p[0].height for p in propias)
                im = im.resize((max(1, round(im.width * ESCALA)), max(1, round(im.height * ESCALA))), Image.LANCZOS)
                lista.append((im, (round((pie_x - x) * ESCALA), round((pie_y - y) * ESCALA))))
        # "Parece que esta flotando" (12/11/2026): el ancla de una montura NO va en los cascos. En el caballo blanco
        # (h001) el dibujo baja PIES_BAJO_EL_ANCLA px por debajo del ancla segun la direccion (de espaldas y de frente
        # mas). Con el ancla en los cascos el toro quedaba ~15 px por encima del suelo. Se corre cada direccion para
        # que sus pies queden igual que los del caballo.
        for c in range(COLUMNAS):
            mios = [lista[k] for k in range(c, len(lista), COLUMNAS)]
            bajo = max(_suelo(im) - oy for im, (_ox, oy) in mios)
            delta = PIES_BAJO_EL_ANCLA[c] - bajo
            for k in range(c, len(lista), COLUMNAS):
                im, (ox, oy) = lista[k]
                lista[k] = (im, (ox, oy - delta))
        salida[anim] = lista
    return salida


PIES_BAJO_EL_ANCLA = (13, 12, 7, 14, 16)       # h001 (1201_Wait), por direccion: espalda .. frente


def _suelo(im):
    """La fila mas baja con dibujo (sin el halo casi transparente)."""
    caja = im.getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox()
    return caja[3] if caja else im.height


def icono() -> bytes:
    im, _ = celdas()[POSES['wait'][0]][2]                  # de perfil
    return ma._tlhs_suelto(ma._cuadrado(im, 36), r'shape\item\i0004.shp', 0, 0)


def bloque_char_obd() -> str:
    return '\r\n'.join((
        '[OBJECT]',
        'Name = %s %s' % (CARPETA.upper(), NOMBRE),
        'Sequence = %d' % SEQUENCE,
        'Directory = \\chr\\%s\\' % CARPETA,
        'Sprite = Wait, hw013*, #12, hw023*, hw033*, hw023*',
        'Sprite = Run, hr013*, #7, !CharSmokeTwo, hr023*, hr033*, hr043*, hr053*, hr063*',
        'SpriteFile = Wait, %d_Wait.spr' % SEQUENCE,
        'SpriteFile = Run, %d_Run.spr' % SEQUENCE,
        '', ''))


def char_obd():
    texto, bom, nl = ma._texto_base(r'setting\char.obd')
    texto = ma._sin_bloque(texto, '; ' + MARCA_INI, '; ' + MARCA_FIN)
    bloque = '; %s%s%s; %s%s' % (MARCA_INI, nl, bloque_char_obd().replace('\r\n', nl), MARCA_FIN, nl)
    ma._guardar(r'setting\char.obd', texto.rstrip() + nl + nl + bloque, bom, latin=True)


def chardef_xml():
    """Su <騎乘> justo detras del ultimo de la lista: el cliente los cuenta en orden y el 原型外觀 es esa cuenta."""
    texto, bom, nl = ma._texto_base(r'setting\chardef.xml')
    texto = ma._sin_bloque(texto, '<!-- %s -->' % MARCA_INI, '<!-- %s -->' % MARCA_FIN)
    filas = list(re.finditer(r'<騎乘 [^>]*/>[^\n]*\n?', texto))
    if len(filas) + 1 != ASPECTO:
        raise SystemExit('chardef.xml trae %d monturas: el aspecto seria %d, no %d' % (len(filas), len(filas) + 1, ASPECTO))
    fin = filas[-1].end()
    bloque = ('\t<!-- %s -->%s\t<騎乘 號碼="%d" 高度="%d" 層級="DOLL_LAYER_RIDE" 種類="0"/>%s\t<!-- %s -->%s'
              % (MARCA_INI, nl, SEQUENCE, ALTURA, nl, MARCA_FIN, nl))
    ma._guardar(r'setting\chardef.xml', texto[:fin] + bloque + texto[fin:], bom)


def _xml_con(relativa, lineas, cierre='</'):
    texto, bom, nl = ma._texto_base(relativa)
    texto = ma._sin_bloque(texto, '<!-- %s -->' % MARCA_INI, '<!-- %s -->' % MARCA_FIN)
    bloque = ('\t<!-- %s -->%s' % (MARCA_INI, nl) + ''.join('\t%s%s' % (l, nl) for l in lineas)
              + '\t<!-- %s -->%s' % (MARCA_FIN, nl))
    fin = texto.rindex(cierre)
    ma._guardar(relativa, texto[:fin] + bloque + texto[fin:], bom)


def fila_item() -> str:
    stats = ' '.join('%s="%d"' % kv for kv in STATS.items())
    return ('<道具 編號="%d" 原型介面="%d" 原型外觀="%d" 基本名稱="%s" 物品類別="座騎" 物品等級="60" 等級限制="60" %s '
            '重量="160" 價格="3000000" 綁定次數="3" 顏色="黃" log等級="80" 說明定義="%s" 寵物座騎裝備="是" 裝備綁定="是" '
            '抽中廣播="是" 收購價格="6000" />' % (ITEM, ICONO, ASPECTO, NOMBRE, stats, DESCRIPCION))


def content_db(ruta):
    """El objeto en la tabla item de content.db: copia de la Flame Eagle (5128) con lo suyo."""
    con = sqlite3.connect(ruta)
    cols = [c[1] for c in con.execute('pragma table_info(item)')]
    fila = dict(zip(cols, con.execute("select * from item where id='5128'").fetchone()))
    fila.update({'id': str(ITEM), '原型介面': str(ICONO), '原型外觀': str(ASPECTO), '基本名稱': NOMBRE,
                 '原型名稱': None, 'move_speed': str(STATS['移動速度'])})
    nombres = {'平均攻擊': ('atk_avg', 'atk'), '防禦': ('def',), '魔攻': ('matk',), '魔防': ('mdef',),
               '精準': ('accuracy',), '靈敏': ('agility',)}
    for k, v in STATS.items():
        for col in (k,) + nombres.get(k, ()):
            if col in fila:
                fila[col] = str(v)
    if '說明定義' in fila:
        fila['說明定義'] = DESCRIPCION
    con.execute('delete from item where id=?', (str(ITEM),))
    con.execute('insert into item (%s) values (%s)' % (','.join('"%s"' % c for c in cols), ','.join('?' * len(cols))),
                [fila[c] for c in cols])
    con.commit()
    con.close()
    print('content.db: %s (%d) en %s' % (NOMBRE, ITEM, ruta))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', help='solo meter el objeto en esa content.db')
    a = ap.parse_args()
    if a.db:
        content_db(pathlib.Path(a.db))
        return
    carpeta = EXTRAS / 'shape' / 'chr' / CARPETA
    carpeta.mkdir(parents=True, exist_ok=True)
    for anim, lista in frames().items():
        (carpeta / ('%d_%s.spr' % (SEQUENCE, anim.capitalize()))).write_bytes(
            spr_ewsp.escribir(lista, anim, prefijo='h'))
    (EXTRAS / 'shape' / 'item').mkdir(parents=True, exist_ok=True)
    (EXTRAS / 'shape' / 'item' / ('%s.shp' % ARCHIVO_ICONO)).write_bytes(icono())
    char_obd()
    chardef_xml()
    _xml_con(r'setting\itemicon4.xml', ['<icon id="%d" dir="\\item\\" normal="%s" focus="normal" down="normal" '
                                        'disable="normal"/>' % (ICONO, ARCHIVO_ICONO)])
    _xml_con(r'setting\eng\item.xml', [fila_item()])
    content_db(RAIZ / 'corpus' / 'content.db')
    print('%s lista: %s, Sequence %d, objeto %d' % (NOMBRE, CARPETA, SEQUENCE, ITEM))


if __name__ == '__main__':
    main()
