"""Estilo moderno para las ventanas propias (25/11/2026): "que se vean mas amigables y modernas esas ventanas".

Lo comparten tools/ventana_sociales.py y tools/ventana_mecanicas.py. Mismos sitios que antes (el XML y el Lua no
cambian), otro dibujo:
  * fondo azul noche con un resplandor arriba y un borde fino;
  * cada seccion es una TARJETA redondeada con una barra de color a la izquierda y su cabecera con icono;
  * botones con degradado, brillo arriba y sombra: verde (accion), azul pizarra (navegar, pestanas) y rojo (cancelar);
  * pestanas: apagada (pizarra) y elegida (verde con subrayado), el Lua cambia el icono al cambiar de pestana;
  * casillas de texto redondeadas con borde suave.
Los .shp son de paleta con transparencia de si o no: lo suave se pinta sobre el fondo, nunca con alfa.
"""
import math

from PIL import Image, ImageDraw, ImageFilter

import ventana_pet_defense as vp

NOCHE_ARRIBA, NOCHE_ABAJO = (24, 33, 56), (11, 15, 27)
BORDE = (58, 74, 110)
TARJETA, TARJETA_BORDE, FILA = (21, 29, 48), (44, 58, 90), (30, 40, 64)
TEXTO_TENUE = (148, 163, 184)
ORO = (251, 211, 104)
COLORES = {
    'verde': ((52, 211, 153), (5, 150, 105), (16, 185, 129)),        # arriba, abajo, borde
    'azul': ((100, 116, 160), (51, 65, 101), (86, 102, 146)),
    'rojo': ((248, 113, 113), (185, 28, 28), (220, 60, 60)),
    'oro': ((253, 224, 130), (202, 138, 4), (234, 179, 8)),
    'cielo': ((96, 165, 250), (29, 78, 216), (59, 130, 246)),
    'gris': ((71, 85, 105), (30, 41, 59), (51, 65, 85)),
}
ACENTOS = {'duelo': (248, 113, 113), 'caza': (251, 146, 60), 'voto': (96, 165, 250), 'tesoro': (251, 211, 104),
           'contrato': (52, 211, 153), 'mascota': (232, 121, 249), 'hardcore': (239, 68, 68)}


def _mezcla(a, b, t):
    return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))


def fondo(w, h):
    """El fondo de una ventana: degradado vertical, resplandor arriba y borde fino."""
    im = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        d.line((0, y, w, y), fill=_mezcla(NOCHE_ARRIBA, NOCHE_ABAJO, y / max(1, h - 1)) + (255,))
    brillo = Image.new('L', (w, h), 0)
    ImageDraw.Draw(brillo).ellipse((w * 0.15, -h * 0.35, w * 0.85, h * 0.25), fill=60)
    brillo = brillo.filter(ImageFilter.GaussianBlur(28))
    im = Image.composite(Image.new('RGBA', (w, h), (70, 110, 190, 255)), im, brillo)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=BORDE + (255,))
    return im


def tarjeta(im, caja, acento=None, radio=8):
    """Una seccion: rectangulo redondeado con su borde y una barra de color a la izquierda."""
    x0, y0, x1, y1 = caja
    sombra = Image.new('L', im.size, 0)
    ImageDraw.Draw(sombra).rounded_rectangle((x0 + 1, y0 + 2, x1 + 1, y1 + 2), radius=radio, fill=120)
    sombra = sombra.filter(ImageFilter.GaussianBlur(2))
    im.paste(Image.composite(Image.new('RGBA', im.size, (4, 6, 12, 255)), im, sombra), (0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(caja, radius=radio, fill=TARJETA + (255,), outline=TARJETA_BORDE + (255,))
    if acento:
        d.rounded_rectangle((x0, y0 + 4, x0 + 3, y1 - 4), radius=2, fill=tuple(acento) + (255,))
    return d


def fila(d, caja, radio=5):
    d.rounded_rectangle(caja, radius=radio, fill=FILA + (255,))


def cabecera(im, xy, texto, icono=None, color=ORO, tam=12):
    """Titulo de seccion con su icono delante."""
    d = ImageDraw.Draw(im)
    x, y = xy
    if icono:
        icono(d, x + 7, y + 7, color)
        x += 18
    d.text((x, y - 1), texto, font=vp._fuente('segoeuib.ttf', tam), fill=color)
    return d


def boton(w, h, color='verde', estado='n', radio=6):
    """Boton con degradado, brillo arriba y sombra. estado: n normal, f encima (mas claro), s pulsado."""
    arriba, abajo, borde = COLORES[color]
    if estado == 'f':
        arriba, abajo = _mezcla(arriba, (255, 255, 255), 0.18), _mezcla(abajo, (255, 255, 255), 0.12)
    elif estado == 's':
        arriba, abajo = _mezcla(abajo, (0, 0, 0), 0.1), arriba
    k = 4
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    grad = Image.new('RGBA', (w * k, h * k))
    gd = ImageDraw.Draw(grad)
    for y in range(h * k):
        gd.line((0, y, w * k, y), fill=_mezcla(arriba, abajo, y / max(1, h * k - 1)) + (255,))
    mascara = Image.new('L', (w * k, h * k), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w * k - 1, h * k - 1 - (0 if estado == 's' else k)),
                                              radius=radio * k, fill=255)
    if estado != 's':                                       # la sombra de abajo
        sombra = Image.new('L', (w * k, h * k), 0)
        ImageDraw.Draw(sombra).rounded_rectangle((0, k, w * k - 1, h * k - 1), radius=radio * k, fill=255)
        im.paste(Image.new('RGBA', im.size, _mezcla(abajo, (0, 0, 0), 0.5) + (255,)), (0, 0), sombra)
    im.paste(grad, (0, 0), mascara)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * k - 1, h * k - 1 - (0 if estado == 's' else k)), radius=radio * k,
                        outline=borde + (255,), width=k)
    if estado != 's':                                       # el brillo de arriba
        d.line((radio * k, 2 * k, w * k - radio * k, 2 * k), fill=_mezcla(arriba, (255, 255, 255), 0.45) + (255,),
               width=k)
    return im.resize((w, h), Image.LANCZOS)


def pestana(w, h, elegida, estado='n'):
    im = boton(w, h, 'verde' if elegida else 'azul', estado)
    if elegida:
        d = ImageDraw.Draw(im)
        d.line((10, h - 1, w - 10, h - 1), fill=ORO + (255,), width=2)
    return im


def casilla(w, h=18):
    """Una casilla de texto: oscura, redondeada, con borde azul suave y una linea de luz abajo."""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=5, fill=(8, 11, 20, 255), outline=(71, 95, 145, 255))
    d.line((5, h - 2, w - 6, h - 2), fill=(40, 52, 80, 255))
    return im


# ------------------------------------------------------------------------------------------- iconos (centro cx, cy)
def ic_espadas(d, cx, cy, c):
    for s in (-1, 1):
        d.line((cx - 5 * s, cy - 5, cx + 5 * s, cy + 5), fill=c, width=2)
        d.line((cx + 3 * s, cy + 1, cx + 1 * s, cy + 3), fill=c, width=2)


def ic_diana(d, cx, cy, c):
    d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), outline=c, width=2)
    d.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=c)


def ic_urna(d, cx, cy, c):
    d.rectangle((cx - 6, cy - 1, cx + 6, cy + 6), outline=c, width=2)
    d.polygon((cx - 3, cy - 7, cx + 3, cy - 7, cx + 3, cy, cx - 3, cy), fill=c)


def ic_cofre(d, cx, cy, c):
    d.rounded_rectangle((cx - 6, cy - 5, cx + 6, cy + 6), radius=2, outline=c, width=2)
    d.line((cx - 6, cy - 1, cx + 6, cy - 1), fill=c, width=2)
    d.rectangle((cx - 1, cy - 2, cx + 1, cy + 1), fill=c)


def ic_pergamino(d, cx, cy, c):
    d.rectangle((cx - 5, cy - 6, cx + 5, cy + 6), outline=c, width=2)
    for y in (-2, 1, 4):
        d.line((cx - 2, cy + y, cx + 3, cy + y), fill=c)


def ic_pata(d, cx, cy, c):
    d.ellipse((cx - 4, cy - 1, cx + 4, cy + 6), fill=c)
    for dx, dy in ((-5, -4), (-2, -7), (2, -7), (5, -4)):
        d.ellipse((cx + dx - 2, cy + dy - 2, cx + dx + 2, cy + dy + 2), fill=c)


def ic_calavera(d, cx, cy, c):
    d.ellipse((cx - 6, cy - 7, cx + 6, cy + 4), fill=c)
    d.rectangle((cx - 3, cy + 2, cx + 3, cy + 7), fill=c)
    for dx in (-3, 2):
        d.ellipse((cx + dx - 1, cy - 3, cx + dx + 2, cy), fill=NOCHE_ABAJO)


def ic_estrella(d, cx, cy, c):
    pts = []
    for i in range(10):
        r = 7 if i % 2 == 0 else 3
        a = -math.pi / 2 + i * math.pi / 5
        pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    d.polygon(pts, fill=c)
