"""Los sprites de los climas propios (25/11/2026, "agrega niebla y demas, crea los efectos tu").

Son particulas como las del cliente (SHAPE\\SF_RAINDROP.SHP, SF_SNOWBALL.SHP, SF_SPETAL03.SHP): un .shp paletizado
con transparencia de todo o nada (icono_subasta.a_shp). El cliente las pinta con el blit de la lluvia (0x75c040, modo
de mezcla 4), asi que salen translucidas: la niebla se hace con manchas grandes y bordes tramados, que al mezclarse
quedan suaves. Las carga por nombre (0x75e760 -> "<nombre>.SHP" en los paks), asi que basta con meterlas en el parche:
parches/extras/shape/sf_aolat_*.shp -> SHAPE\\SF_AOLAT_*.SHP. Los codigos de clima que las usan los pone
tools/parche_clima_exe.py en angel.dat.

    python tools/clima_sprites.py [--vista carpeta]
"""
import argparse
import math
import pathlib
import random
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from icono_subasta import a_shp  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = RAIZ / 'parches' / 'extras' / 'shape'


def _tramado(w, h, color, densidad, semilla):
    """Una mancha: opaco donde un ruido ordenado cae por debajo de densidad(x, y) (0..1)."""
    rng = random.Random(semilla)
    bayer = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    px = im.load()
    for y in range(h):
        for x in range(w):
            d = densidad(x, y)
            if d <= 0:
                continue
            umbral = (bayer[y % 4][x % 4] + 0.5) / 16.0
            if d > umbral * 0.85 + rng.random() * 0.15:
                c = tuple(max(0, min(255, int(v + rng.uniform(-8, 8)))) for v in color)
                px[x, y] = c + (255,)
    return im


def niebla():
    w, h = 176, 84

    def dens(x, y):
        dx, dy = (x - w / 2) / (w / 2), (y - h / 2) / (h / 2)
        r = math.sqrt(dx * dx + dy * dy)
        onda = 0.12 * math.sin(x * 0.11) + 0.08 * math.sin(y * 0.23 + x * 0.05)
        return max(0.0, 0.72 - 0.8 * r + onda)
    return _tramado(w, h, (226, 230, 236), dens, 'niebla')


def brasa():
    im = Image.new('RGBA', (5, 5), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.point([(2, 1), (1, 2), (3, 2), (2, 3)], fill=(255, 120, 20, 255))
    d.point([(2, 2)], fill=(255, 236, 120, 255))
    return im


def ceniza():
    im = Image.new('RGBA', (4, 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.point([(0, 1), (1, 0), (1, 1), (2, 1), (3, 2)], fill=(120, 34, 30, 255))
    d.point([(2, 0)], fill=(200, 70, 50, 255))
    return im


def hoja():
    im = Image.new('RGBA', (10, 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(0, 4), (3, 1), (8, 0), (9, 3), (6, 6), (2, 7)], fill=(214, 112, 30, 255))
    d.line([(1, 6), (8, 1)], fill=(150, 66, 18, 255))
    d.point([(9, 0)], fill=(110, 70, 30, 255))
    return im


def luciernaga():
    im = Image.new('RGBA', (5, 5), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.point([(2, 0), (0, 2), (4, 2), (2, 4)], fill=(150, 220, 60, 255))
    d.point([(1, 1), (3, 1), (1, 3), (3, 3)], fill=(190, 240, 80, 255))
    d.rectangle([1, 2, 3, 2], fill=(235, 255, 150, 255))
    d.rectangle([2, 1, 2, 3], fill=(235, 255, 150, 255))
    return im


def arena():
    w, h = 22, 3
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    px = im.load()
    rng = random.Random('arena')
    for x in range(w):
        for y in range(h):
            if rng.random() < (0.85 if y == 1 else 0.35) * (1 - abs(x - w * 0.6) / w):
                px[x, y] = (214, 184, 130, 255)
    return im


def lluvia_sangre():
    im = Image.new('RGBA', (3, 18), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([(1, 0), (1, 17)], fill=(150, 16, 24, 255))
    d.line([(0, 12), (0, 17)], fill=(110, 8, 16, 255))
    d.point([(2, 16)], fill=(200, 40, 40, 255))
    return im


def polvo_estrellas():
    im = Image.new('RGBA', (7, 7), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([(3, 0), (3, 6)], fill=(170, 200, 255, 255))
    d.line([(0, 3), (6, 3)], fill=(170, 200, 255, 255))
    d.point([(2, 2), (4, 2), (2, 4), (4, 4)], fill=(210, 225, 255, 255))
    d.point([(3, 3)], fill=(255, 255, 255, 255))
    return im


# nombre del .shp -> dibujo. El orden no importa: los codigos los fija parche_clima_exe.CLIMAS.
SPRITES = {
    'sf_aolat_fog': niebla,
    'sf_aolat_ember': brasa,
    'sf_aolat_ash': ceniza,
    'sf_aolat_leaf': hoja,
    'sf_aolat_firefly': luciernaga,
    'sf_aolat_sand': arena,
    'sf_aolat_bloodrain': lluvia_sangre,
    'sf_aolat_star': polvo_estrellas,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--vista', help='carpeta donde dejar los .png para mirarlos (x4)')
    a = ap.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, f in SPRITES.items():
        im = f()
        (SALIDA / (nombre + '.shp')).write_bytes(a_shp(im))
        if a.vista:
            v = pathlib.Path(a.vista)
            v.mkdir(parents=True, exist_ok=True)
            fondo = Image.new('RGBA', im.size, (40, 70, 40, 255))
            fondo.alpha_composite(im)
            fondo.resize((im.width * 4, im.height * 4), Image.NEAREST).save(v / (nombre + '.png'))
        print(nombre, im.size)


if __name__ == '__main__':
    main()
