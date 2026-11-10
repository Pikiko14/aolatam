"""La mascota Abyss (09/11/2026): huevo -> Abyss Cub (lv 15) -> Abyss Fiend (MBC, 35) -> Abyss Lord (ABC, 55).

"para las 3 etapas cambia el color y tamano, implementa": las tres etapas salen de las mismas hojas
(docs/sprites_pet/abismo, una por direccion, 5 filas x 6 poses: wait, run, att, hurt, dead), cada una con su tamano y
su tono. El huevo sale de huevo.png.

Las direcciones del cliente miran todas a la izquierda (la derecha va en espejo) y van 3 espalda, 4 espalda-izquierda,
5 perfil izquierdo, 6 frente-izquierda, 7 frente: comprobado pintando el Blood Wolf (44005). En el .spr cada animacion
son 6 poses x 5 direcciones, frame = pose * 5 + direccion (tools/spr_ewsp.py).

Stats, habilidades, tipo y tabla de experiencia son los de la linea Fuzz Ball Egg (3339) -> Purple Fuzz Ball (3340) ->
Swamp Devil (3342) -> Hell Spawn (3346): demonios de ataque cuerpo a cuerpo, como este bicho. Las dos ramas de cada
etapa llevan a la misma siguiente.

Deja:
  parches/extras/shape/mon/p990..p993/<sprite>_{wait,...}.spr          los 4 sprites, cada uno en su carpeta
  parches/extras/shape/pet/p990..p993.shp                              los retratos (44x44)
  parches/extras/shape/item/i9300.shp                                  el icono del huevo (36x36)
  parches/extras/setting/npc.obd, peticon.xml, itemicon4.xml             sus entradas
  parches/extras/setting/eng/pet.xml, item.xml                         las filas de la mascota y del huevo
  server/plantillas/mascotas.json                                      lo que lee el servidor
y con --db RUTA mete el huevo en esa corpus/content.db (la del servidor). Se puede correr las veces que haga falta.

    python tools/mascota_abismo.py [--db corpus/content.db]
"""
import argparse
import json
import pathlib
import re
import sqlite3
import sys

import numpy as np
from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import fondos_interfaz as fi  # noqa: E402
import spr_ewsp  # noqa: E402

ORIGEN = RAIZ / 'docs' / 'sprites_pet' / 'abismo'
EXTRAS = RAIZ / 'parches' / 'extras'
MASCOTAS_JSON = RAIZ / 'server' / 'plantillas' / 'mascotas.json'
# Una carpeta por sprite (p990..p993), como en el juego (44078 en \mon\p078\): los frames se llaman igual en todos
# (w013.SHP...) y el cliente los guarda por carpeta y nombre. Con los cuatro en p990 el Abyss Lord salia con el dibujo
# del Cub y volvia a verse como huevo (09/11/2026).

HOJAS = {3: 'dir3_espalda.png', 4: 'dir4_espalda_izquierda.png', 5: 'dir5_izquierda.png',
         6: 'dir6_frente_izquierda.png', 7: 'dir7_frente.png'}
ANIMS = ('wait', 'run', 'att', 'hurt', 'dead')
POSES = 6

ITEM_HUEVO = 83300
ICONO_HUEVO = 59300
ARCHIVO_ICONO_HUEVO = 'i9300'

# pet (pet.xml), sprite (圖號1), retrato (頭像編號 + su archivo), plantilla de la linea Fuzz Ball, nombre, alto de la
# pose de espera en pixeles y tono (grados que gira el color, brillo).
ETAPAS = (
    dict(pet=3990, sprite=44990, retrato=11990, archivo='p990', plantilla=3339, nombre='Abyss Egg',
         alto=46, tono=0, brillo=1.0),
    dict(pet=3991, sprite=44991, retrato=11991, archivo='p991', plantilla=3340, nombre='Abyss Cub',
         alto=62, tono=-45, brillo=1.1),      # azul violeta, el mas pequeno
    dict(pet=3992, sprite=44992, retrato=11992, archivo='p992', plantilla=3342, nombre='Abyss Fiend',
         alto=80, tono=0, brillo=1.0),        # el morado de las hojas
    dict(pet=3993, sprite=44993, retrato=11993, archivo='p993', plantilla=3346, nombre='Abyss Lord',
         alto=98, tono=50, brillo=0.9),       # carmesi oscuro, el mas grande
)


# ----------------------------------------------------------------------------------------------- arte
def tenir(im: Image.Image, grados: float, brillo: float) -> Image.Image:
    """Gira el tono y cambia el brillo sin tocar la transparencia."""
    if not grados and brillo == 1.0:
        return im
    alfa = im.getchannel('A')
    hsv = np.array(im.convert('RGB').convert('HSV'), dtype=np.int32)
    hsv[..., 0] = (hsv[..., 0] + int(round(grados * 256 / 360))) % 256
    hsv[..., 2] = np.clip(hsv[..., 2] * brillo, 0, 255)
    out = Image.fromarray(hsv.astype(np.uint8), 'HSV').convert('RGB').convert('RGBA')
    out.putalpha(alfa)
    return out


def _caja(im: Image.Image):
    return im.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()


MARGEN = 0.5      # lo que se mira alrededor de cada casilla, en casillas


def celdas(hoja: Image.Image):
    """[[celda RGBA]] por fila (animacion) y columna (pose) de la cuadricula de 6 x 5.

    El rastro de los zarpazos y el humo se salen de su casilla ("algunos sprite de ataque se ven cortados",
    10/11/2026): cortando la cuadricula a ras quedaban partidos. Ahora cada mancha de la hoja (lo que esta unido) va
    entera a la casilla donde tiene mas pixeles, y cada casilla es su cuadro mas MARGEN alrededor, con solo sus
    manchas: el golpe sale completo y no se cuela nada de las vecinas. Todas las casillas miden lo mismo, asi que el
    ancla de los pies sigue valiendo para todas.
    """
    from scipy import ndimage
    w, h = hoja.size
    cw, ch = w / POSES, h / len(ANIMS)
    arr = np.array(hoja)
    # 64 y no menos: un velo casi transparente entre figuras unia dos bichos en una sola mancha y una casilla se quedaba
    # con los dos y la vecina vacia. El .spr solo guarda alfa >= 128, asi que no se pierde nada que se vea.
    visible = arr[..., 3] >= 64
    etiquetas, n = ndimage.label(visible, structure=np.ones((3, 3)))
    filas_px = np.minimum((np.arange(h) / ch).astype(int), len(ANIMS) - 1)
    cols_px = np.minimum((np.arange(w) / cw).astype(int), POSES - 1)
    casilla_px = filas_px[:, None] * POSES + cols_px[None, :]
    n_cas = POSES * len(ANIMS)
    cuenta = np.zeros((n + 1, n_cas), dtype=np.int64)
    np.add.at(cuenta, (etiquetas[visible], casilla_px[visible]), 1)
    duena = cuenta.argmax(axis=1)[etiquetas]          # a que casilla va cada pixel, por su mancha
    # Una mancha que reparte buena parte de si entre varias casillas son dos poses que se tocan (el zarpazo de una
    # pisa el cuerpo de la vecina): esa se parte pixel a pixel hacia el cuerpo mas cercano. El centro de cada cuerpo
    # es el de sus pixeles mas opacos dentro de su casilla.
    fuerte = arr[..., 3] >= 200
    ys, xs = np.nonzero(fuerte)
    cas_f = casilla_px[ys, xs]
    sumas = np.bincount(cas_f, minlength=n_cas).astype(float)
    centros = np.stack([np.bincount(cas_f, xs, n_cas), np.bincount(cas_f, ys, n_cas)], axis=1) / np.maximum(sumas, 1)[:, None]
    for l in range(1, n + 1):
        total = cuenta[l].sum()
        cand = np.nonzero(cuenta[l] >= 0.15 * total)[0]
        if len(cand) < 2:
            continue
        py, px = np.nonzero(etiquetas == l)
        d = (px[:, None] - centros[cand, 0][None, :]) ** 2 + (py[:, None] - centros[cand, 1][None, :]) ** 2
        duena[py, px] = cand[d.argmin(axis=1)]
    mx, my = round(cw * MARGEN), round(ch * MARGEN)
    tabla = []
    for f in range(len(ANIMS)):
        fila = []
        for c in range(POSES):
            x0, y0 = round(c * cw) - mx, round(f * ch) - my
            x1, y1 = x0 + round(cw) + 2 * mx, y0 + round(ch) + 2 * my
            sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
            trozo = arr[sy0:sy1, sx0:sx1].copy()
            trozo[~(visible[sy0:sy1, sx0:sx1] & (duena[sy0:sy1, sx0:sx1] == f * POSES + c))] = 0
            lienzo = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
            lienzo[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = trozo
            fila.append(Image.fromarray(lienzo, 'RGBA'))
        tabla.append(fila)
    return tabla


def _recortar(celda, escala, ancla):
    """La celda a su escala, recortada a lo que se ve, con el punto de los pies (ox, oy) dentro del recorte."""
    w, h = celda.size
    celda = celda.resize((max(1, round(w * escala)), max(1, round(h * escala))), Image.LANCZOS)
    caja = _caja(celda)
    if not caja:
        return Image.new('RGBA', (1, 1)), (0, 0)
    return celda.crop(caja), (ancla[0] - caja[0], ancla[1] - caja[1])


def frames_de_etapa(etapa) -> dict:
    """{anim: [(imagen, (ox, oy))] en el orden del .spr} para una etapa del bicho."""
    por_dir = {}
    for d, archivo in HOJAS.items():
        hoja = tenir(Image.open(ORIGEN / archivo).convert('RGBA'), etapa['tono'], etapa['brillo'])
        tabla = celdas(hoja)
        espera = _caja(tabla[0][0])
        escala = etapa['alto'] / (espera[3] - espera[1])
        # El ancla sale de la pose de espera y vale para todas: asi el bicho no baila de una pose a otra.
        ancla = (round((espera[0] + espera[2]) / 2 * escala), round(espera[3] * escala))
        por_dir[d] = [[_recortar(c, escala, ancla) for c in fila] for fila in tabla]
    return {anim: [por_dir[d][i][p] for p in range(POSES) for d in sorted(HOJAS)] for i, anim in enumerate(ANIMS)}


def frames_del_huevo(etapa) -> dict:
    """El huevo: la misma imagen en las 5 direcciones, con un vaiven de pocos pixeles en cada animacion."""
    im = Image.open(ORIGEN / 'huevo.png').convert('RGBA')
    im = im.crop(_caja(im))
    base = im.resize((max(1, round(im.size[0] * etapa['alto'] / im.size[1])), etapa['alto']), Image.LANCZOS)

    def pose(dy=0, ancho=1.0, alto=1.0, giro=0, alfa=1.0):
        w, h = base.size
        p = base.resize((max(1, round(w * ancho)), max(1, round(h * alto))), Image.LANCZOS)
        if giro:
            p = p.rotate(giro, resample=Image.BICUBIC, expand=True)
        if alfa < 1.0:
            p.putalpha(p.getchannel('A').point(lambda a: int(a * alfa)))
        caja = _caja(p) or (0, 0, 1, 1)
        p = p.crop(caja)
        return p, (p.size[0] // 2, p.size[1] + dy)      # dy hacia ARRIBA: los pies quedan debajo del dibujo

    # Como los huevos del juego (44033): se mueve y ataca A SALTOS. En su Att los pies quedan hasta 66 px por debajo
    # del dibujo y en el Run hasta 65 ("no hace el efecto de atacar el huevo", 09/11/2026).
    poses = {
        'wait': [pose(dy) for dy in (0, 2, 4, 5, 3, 1)],
        'run': [pose(dy, giro=g) for dy, g in ((0, 0), (14, 6), (40, 10), (52, 8), (36, 4), (10, 0))],
        'att': [pose(dy, giro=g) for dy, g in ((0, 0), (22, 10), (58, 18), (66, 14), (34, -6), (6, 0))],
        'hurt': [pose(ancho=a, alto=b) for a, b in ((1, 1), (1.08, .92), (1.04, .96), (1, 1), (1, 1), (1, 1))],
        'dead': [pose(alto=b, alfa=t) for b, t in ((1, 1), (.9, 1), (.75, .9), (.55, .75), (.35, .55), (.2, .3))],
    }
    return {anim: [poses[anim][p] for p in range(POSES) for _d in HOJAS] for anim in ANIMS}


def _tlhs_suelto(im: Image.Image, plantilla: str, ox: int, oy: int) -> bytes:
    """Una imagen como .shp de 8 bits con paleta propia, con la cabecera de `plantilla` (un retrato o un icono)."""
    cab, bpp, _filas, _pal = fi.leer(fi.del_cliente(plantilla))
    q = im.convert('RGB').quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()[:768]
    pal += [0] * (768 - len(pal))
    paleta = b''.join(((pal[3 * i] >> 3) << 11 | (pal[3 * i + 1] >> 2) << 5 | (pal[3 * i + 2] >> 3)).to_bytes(2, 'little')
                      for i in range(256))
    idx = q.load()
    alfa = im.getchannel('A').load()
    w, h = im.size
    filas = []
    for y in range(h):
        tramos, x = [], 0
        while x < w:
            if alfa[x, y] < 128:
                x += 1
                continue
            ini = x
            while x < w and alfa[x, y] >= 128:
                x += 1
            tramos.append((ini, bytes(idx[i, y] for i in range(ini, x))))
        filas.append(tramos)
    cab = list(cab)
    cab[5], cab[7], cab[8] = w, ox, oy
    return fi.escribir(cab, bpp, filas, paleta)


def _cuadrado(im: Image.Image, lado: int, margen: int = 1) -> Image.Image:
    im = im.crop(_caja(im))
    k = (lado - 2 * margen) / max(im.size)
    im = im.resize((max(1, round(im.size[0] * k)), max(1, round(im.size[1] * k))), Image.LANCZOS)
    lienzo = Image.new('RGBA', (lado, lado))
    lienzo.paste(im, ((lado - im.size[0]) // 2, lado - margen - im.size[1]), im)
    return lienzo


def retrato(etapa) -> bytes:
    """44x44 como los de shape/pet (p001: origen 21,43): la cara de frente de la pose de espera."""
    if etapa['pet'] == ETAPAS[0]['pet']:
        im = Image.open(ORIGEN / 'huevo.png').convert('RGBA')
    else:
        im = tenir(celdas(Image.open(ORIGEN / HOJAS[7]).convert('RGBA'))[0][0], etapa['tono'], etapa['brillo'])
    return _tlhs_suelto(_cuadrado(im, 44), r'shape\pet\p001.shp', 21, 43)


def icono_huevo() -> bytes:
    return _tlhs_suelto(_cuadrado(Image.open(ORIGEN / 'huevo.png').convert('RGBA'), 36), r'shape\item\i0004.shp', 0, 0)


# ----------------------------------------------------------------------------------------------- datos
def bloque_npc_obd(etapa) -> str:
    s = etapa['sprite']
    sec = lambda letra: ', '.join('%s0%d3*' % (letra, p) for p in range(2, POSES + 1))  # noqa: E731
    return '\r\n'.join((
        '[OBJECT]',
        'Name = %s - %s' % (etapa['archivo'].upper(), etapa['nombre']),
        'Sequence = %d' % s,
        'Space = 25, 80, 0',
        'Flags = SP_ATTRIB_DISTURB, SP_ATTRIB_HITTEST, SP_ATTRIB_SHADOW',
        'Process = SERV_CLASS_PETOBJ',
        'Directory = \\mon\\%s\\' % etapa['archivo'],
        'Sprite = Wait, w013*, #8, !SoundWait, %s' % sec('w'),
        'Sprite = Run, r013*, #7, %s' % sec('r'),
        'Sprite = Att, a013*, #6, !SoundAttack, %s, @SP_EVENT_ACT_WAIT, SCROVER' % sec('a'),
        'Sprite = Cast, a013*, #6, %s' % sec('a'),
        'Sprite = Hurt, h013*, #4, %s, @SP_EVENT_ACT_WAIT, SCROVER' % sec('h'),
        'Sprite = Dead, d013*, #6, !SoundDie, %s, SCROVER' % sec('d'),
        'SpriteFile = Wait, %d_Wait.spr' % s,
        'SpriteFile = Run, %d_Run.spr' % s,
        'SpriteFile = Att, %d_Att.spr' % s,
        'SpriteFile = Cast, %d_Att.spr' % s,
        'SpriteFile = Hurt, %d_Hurt.spr' % s,
        'SpriteFile = Dead, %d_Dead.spr' % s,
        '', ''))


def _texto_base(relativa: str) -> tuple:
    """(texto, bom, salto) del fichero de parches/extras si ya esta, si no el vigente del cliente."""
    propio = EXTRAS / relativa.replace('\\', '/')
    crudo = propio.read_bytes() if propio.is_file() else fi.del_cliente(relativa)
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig' if bom else 'latin-1' if relativa.endswith('.obd') else 'utf-8')
    return texto, bom, '\r\n' if '\r\n' in texto else '\n'


def _guardar(relativa: str, texto: str, bom: bool, latin=False):
    destino = EXTRAS / relativa.replace('\\', '/')
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes((b'\xef\xbb\xbf' if bom else b'') + texto.encode('latin-1' if latin else 'utf-8'))


MARCA_INI, MARCA_FIN = 'aolat abismo', '/aolat abismo'


def _sin_bloque(texto: str, ini: str, fin: str) -> str:
    return re.sub(r'%s.*?%s[^\n]*\n?' % (re.escape(ini), re.escape(fin)), '', texto, flags=re.S)


def npc_obd():
    texto, bom, nl = _texto_base(r'setting\npc.obd')
    texto = _sin_bloque(texto, '; ' + MARCA_INI, '; ' + MARCA_FIN)
    bloque = ('; %s%s' % (MARCA_INI, nl) + ''.join(bloque_npc_obd(e).replace('\r\n', nl) for e in ETAPAS)
              + '; %s%s' % (MARCA_FIN, nl))
    _guardar(r'setting\npc.obd', texto.rstrip() + nl + nl + bloque, bom, latin=True)


def _xml_con(relativa: str, lineas, cierre: str):
    texto, bom, nl = _texto_base(relativa)
    texto = _sin_bloque(texto, '<!-- %s -->' % MARCA_INI, '<!-- %s -->' % MARCA_FIN)
    bloque = ('\t<!-- %s -->%s' % (MARCA_INI, nl) + ''.join('\t%s%s' % (l, nl) for l in lineas)
              + '\t<!-- %s -->%s' % (MARCA_FIN, nl))
    fin = texto.rindex(cierre)
    _guardar(relativa, texto[:fin] + bloque + texto[fin:], bom)


def peticon_xml():
    _xml_con(r'setting\peticon.xml', [
        '<icon id="%d" pos="12,23" dir="\\pet\\" normal="%s" focus="normal" down="normal" disable="normal"/>'
        % (e['retrato'], e['archivo']) for e in ETAPAS], '</')


def itemicon_xml():
    # El cliente en ingles carga itemicon1..4 (system_eng.xml), no itemicon.xml: alli no salia el icono.
    _xml_con(r'setting\itemicon4.xml', [
        '<icon id="%d" dir="\\item\\" normal="%s" focus="normal" down="normal" disable="normal"/>'
        % (ICONO_HUEVO, ARCHIVO_ICONO_HUEVO)], '</')


def _fila_pet(texto: str, pid: int) -> str:
    return re.search(r'<pet 編號="%d"[^>]*/>' % pid, texto).group(0)


def filas_pet_xml(base: str) -> list:
    filas = []
    for i, e in enumerate(ETAPAS):
        f = _fila_pet(base, e['plantilla'])
        f = re.sub(r'編號="\d+"', '編號="%d"' % e['pet'], f, count=1)
        f = re.sub(r'頭像編號="\d+"', '頭像編號="%d"' % e['retrato'], f)
        f = re.sub(r'圖號1="\d+"', '圖號1="%d"' % e['sprite'], f)
        f = re.sub(r'名稱="[^"]*"', '名稱="%s"' % e['nombre'], f)
        f = re.sub(r' 升階變化[12]="\d+"', '', f)
        if i + 1 < len(ETAPAS):
            sig = ETAPAS[i + 1]['pet']
            f = f.replace(' 階段=', ' 升階變化1="%d" 升階變化2="%d" 階段=' % (sig, sig), 1)
        filas.append(f)
    return filas


def pet_xml():
    texto, bom, nl = _texto_base(r'setting\eng\pet.xml')
    texto = _sin_bloque(texto, '<!-- %s -->' % MARCA_INI, '<!-- %s -->' % MARCA_FIN)
    _xml_con(r'setting\eng\pet.xml', filas_pet_xml(texto), '</')


FILA_HUEVO = ('<道具 編號="%d" 原型介面="%d" 基本名稱="Abyss Egg" 物品類別="寵物" 物品等級="20" 重量="10" 動態資料1="%d" '
              '動態資料2="10" 綁定次數="3" log等級="80" 說明定義="An egg wrapped in purple smoke. The creature inside '
              'grows from Abyss Cub to Abyss Fiend and Abyss Lord." 可使用="是" 裝備綁定="是" 使用不扣="是" 抽中廣播="是" />'
              % (ITEM_HUEVO, ICONO_HUEVO, ETAPAS[0]['pet']))


def item_xml():
    _xml_con(r'setting\eng\item.xml', [FILA_HUEVO], '</')


def mascotas_json():
    tabla = json.loads(MASCOTAS_JSON.read_text(encoding='utf-8'))
    for i, e in enumerate(ETAPAS):
        f = dict(tabla[str(e['plantilla'])])
        f.update(sprite=e['pet'], tipo=e['sprite'], nombre=e['nombre'], retrato=e['retrato'])
        f.pop('rama1', None)
        f.pop('rama2', None)
        if i + 1 < len(ETAPAS):
            f['rama1'] = f['rama2'] = ETAPAS[i + 1]['pet']
        tabla[str(e['pet'])] = f
    MASCOTAS_JSON.write_text(json.dumps(tabla, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def content_db(ruta: pathlib.Path):
    """El huevo en la tabla item de content.db: copia de la fila del Fuzz Ball Egg (15088) con lo suyo."""
    con = sqlite3.connect(ruta)
    cols = [c[1] for c in con.execute('pragma table_info(item)')]
    fila = dict(zip(cols, con.execute("select * from item where id='15088'").fetchone()))
    fila.update({'id': str(ITEM_HUEVO), '原型介面': str(ICONO_HUEVO), '基本名稱': 'Abyss Egg',
                 '動態資料1': str(ETAPAS[0]['pet'])})
    for k in ('說明定義', '不可交易', '不可存倉庫'):
        if k in fila:
            fila[k] = None
    if '說明定義' in fila:
        fila['說明定義'] = re.search(r'說明定義="([^"]*)"', FILA_HUEVO).group(1)
    if '綁定次數' in fila:
        fila['綁定次數'] = '3'
    con.execute('delete from item where id=?', (str(ITEM_HUEVO),))
    con.execute('insert into item (%s) values (%s)' % (','.join('"%s"' % c for c in cols), ','.join('?' * len(cols))),
                [fila[c] for c in cols])
    con.commit()
    con.close()
    print('content.db: huevo', ITEM_HUEVO, 'en', ruta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', help='solo meter el huevo en esa content.db')
    a = ap.parse_args()
    if a.db:
        content_db(pathlib.Path(a.db))
        return
    for i, e in enumerate(ETAPAS):
        sprites = EXTRAS / 'shape' / 'mon' / e['archivo']
        sprites.mkdir(parents=True, exist_ok=True)
        for viejo in sprites.glob('*.spr'):          # de cuando estaban los cuatro juntos en p990
            if not viejo.name.startswith(str(e['sprite'])):
                viejo.unlink()
        frames = frames_del_huevo(e) if i == 0 else frames_de_etapa(e)
        for anim in ANIMS:
            (sprites / ('%d_%s.spr' % (e['sprite'], anim))).write_bytes(spr_ewsp.escribir(frames[anim], anim))
        (EXTRAS / 'shape' / 'pet').mkdir(parents=True, exist_ok=True)
        (EXTRAS / 'shape' / 'pet' / ('%s.shp' % e['archivo'])).write_bytes(retrato(e))
        print(e['nombre'], e['sprite'], 'listo')
    (EXTRAS / 'shape' / 'item').mkdir(parents=True, exist_ok=True)
    (EXTRAS / 'shape' / 'item' / ('%s.shp' % ARCHIVO_ICONO_HUEVO)).write_bytes(icono_huevo())
    npc_obd()
    peticon_xml()
    itemicon_xml()
    pet_xml()
    item_xml()
    mascotas_json()
    content_db(RAIZ / 'corpus' / 'content.db')
    print('mascota Abyss lista')


if __name__ == '__main__':
    main()
