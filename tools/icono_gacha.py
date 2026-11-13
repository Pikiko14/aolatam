"""El icono de las Gear Gacha (13/11/2026, "para los gachas podemos usar estos iconos"): la capsula roja de las
Level 70/80 Gear Gacha del juego oficial (captura del usuario). Nuestro cliente no la trae (las nuestras usaban el 5172
de la Summer Wear Gachapon), asi que se dibuja: 36x36 como los iconos de objeto (shape/item/i0004), la capsula
inclinada, arriba roja con brillo y abajo blanca, con contorno oscuro.

Escribe parches/extras/shape/item/i9310.shp, la linea del icono 59310 en setting/itemicon4.xml (bloque propio) y el
icono en las gachas de server/plantillas/lucky_bags_mall.json (y en tools/generar_lucky_bags.py, ICONO_GACHA).

    python tools/icono_gacha.py
    python tools/generar_parche.py
"""
import json
import pathlib
import re
import sys

from PIL import Image, ImageDraw, ImageFilter

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import mascota_abismo as ma  # noqa: E402

ICONO = 59310
ARCHIVO = 'i%d' % (ICONO - 50000)
SALIDA = RAIZ / 'parches' / 'extras' / 'shape' / 'item' / (ARCHIVO + '.shp')
BOLSAS = RAIZ / 'server' / 'plantillas' / 'lucky_bags_mall.json'
MARCA_INI, MARCA_FIN = 'aolat icono gacha', '/aolat icono gacha'
LADO, K = 36, 8                     # el icono y el sobremuestreo con el que se dibuja


def capsula() -> Image.Image:
    n = LADO * K
    im = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, r = n / 2, n * 0.40
    caja = (c - r, c - r, c + r, c + r)
    # el cuerpo: abajo blanco con un gris por dentro, arriba rojo
    d.ellipse(caja, fill=(236, 236, 240, 255))
    d.pieslice(caja, 180, 360, fill=(235, 45, 55, 255))
    # sombra de la mitad roja y del blanco (volumen)
    sombra = Image.new('L', (n, n), 0)
    ImageDraw.Draw(sombra).ellipse((c - r * 0.55, c - r * 0.85, c + r * 1.25, c + r * 1.1), fill=60)
    sombra = sombra.filter(ImageFilter.GaussianBlur(n * 0.06))
    oscuro = Image.new('RGBA', (n, n), (90, 0, 10, 255))
    mascara = Image.new('L', (n, n), 0)
    ImageDraw.Draw(mascara).ellipse(caja, fill=255)
    oscuro.putalpha(Image.composite(sombra, Image.new('L', (n, n), 0), mascara))
    im.alpha_composite(oscuro)
    d = ImageDraw.Draw(im)
    # lo de dentro de la mitad blanca: un gris con un toque de color, como la de la captura
    d.chord((c - r * 0.72, c + r * 0.05, c + r * 0.72, c + r * 0.8), 0, 180, fill=(170, 170, 185, 255))
    d.chord((c - r * 0.5, c + r * 0.12, c + r * 0.5, c + r * 0.6), 0, 180, fill=(200, 160, 175, 255))
    # la junta: una banda oscura con su brillo
    d.rectangle((c - r, c - n * 0.018, c + r, c + n * 0.018), fill=(60, 20, 25, 255))
    d.rectangle((c - r, c + n * 0.018, c + r, c + n * 0.03), fill=(250, 250, 250, 255))
    # el brillo de la mitad roja
    brillo = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse((c - r * 0.8, c - r * 0.85, c + r * 0.1, c - r * 0.2),
                                   fill=(255, 220, 220, 230))
    im.alpha_composite(brillo.filter(ImageFilter.GaussianBlur(n * 0.02)))
    d = ImageDraw.Draw(im)
    # el contorno
    d.ellipse(caja, outline=(70, 10, 15, 255), width=int(n * 0.035))
    im = im.rotate(28, resample=Image.BICUBIC, center=(c, c))
    im = im.resize((LADO, LADO), Image.LANCZOS)
    a = im.getchannel('A').point(lambda v: 255 if v >= 110 else 0)   # el .shp solo tiene todo o nada
    im.putalpha(a)
    return im


def _itemicon():
    """La linea del icono en setting/itemicon4.xml, en su bloque (se rehace cada vez)."""
    texto, bom, nl = ma._texto_base(r'setting\itemicon4.xml')
    texto = ma._sin_bloque(texto, '<!-- %s -->' % MARCA_INI, '<!-- %s -->' % MARCA_FIN)
    linea = ('<icon id="%d" dir="\\item\\" normal="%s" focus="normal" down="normal" disable="normal"/>'
             % (ICONO, ARCHIVO))
    bloque = '\t<!-- %s -->%s\t%s%s\t<!-- %s -->%s' % (MARCA_INI, nl, linea, nl, MARCA_FIN, nl)
    fin = texto.rindex('</')
    ma._guardar(r'setting\itemicon4.xml', texto[:fin] + bloque + texto[fin:], bom)


def _bolsas():
    bolsas = json.loads(BOLSAS.read_text(encoding='utf-8'))
    n = 0
    for b in bolsas:
        if b.get('gacha'):
            b['icono'] = ICONO
            n += 1
    BOLSAS.write_text(json.dumps(bolsas, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    gen = RAIZ / 'tools' / 'generar_lucky_bags.py'
    t = gen.read_text(encoding='utf-8')
    t2 = re.sub(r'^ICONO_GACHA = \d+ .*$', 'ICONO_GACHA = %d                 # la capsula roja (tools/icono_gacha.py)' % ICONO,
                t, count=1, flags=re.M)
    if t2 != t:
        gen.write_text(t2, encoding='utf-8', newline='')
    return n


def main():
    im = capsula()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes(ma._tlhs_suelto(im, r'shape\item\i0004.shp', 0, 0))
    im.resize((LADO * 4, LADO * 4), Image.NEAREST).save(RAIZ / 'docs' / 'icono_gacha.png')
    _itemicon()
    print('icono %d en %s; %d gachas con el icono' % (ICONO, SALIDA.relative_to(RAIZ), _bolsas()))


if __name__ == '__main__':
    main()
