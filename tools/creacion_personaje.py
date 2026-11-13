"""La creacion de personaje con la linea grafica del login nuevo (13/11/2026, "reharemos la pestana de creacion de
personaje, debe ser moderna y harmoniosa, redistribuye todo").

Son dos ventanas de wnd02.xml, las dos WND_CLASS_DLG_1 (el marco suma 8 de ancho y 24 de alto al interior):
  * 2566 "Character Shape" (interior 486x274, log/w038_17): sexo, pelo, estatura, color de pelo y de piel;
  * 2548 "Character Info" (interior 362x251, log/w038_23): nombre, nacimiento, signo, grupo y lo opcional.
Su interior era un dibujo verde con ICON_ATTRIB_THEME (el cliente lo tine con el tema). Ahora es azul noche con
estrellas y tarjetas de borde dorado con su cabecera, sin tinte; los valores (que iban en letra oscura sobre
casillas claras) van en casillas hundidas con letra clara (fcolor 103).

Lo que pinta el juego y aqui no se dibuja: las cabezas del pelo (lista 2581, con el marco de celdas 2587), las
muestras de color (2781/2782, imagenes de 224x94 detras de las listas 2575/2576) y el personaje (en el centro de la
2566 y a la derecha de la 2548, en sitios fijos: la columna del medio y la tarjeta derecha no se mueven).

Las posiciones salen de CAJAS (x, y, ancho, alto, en coordenadas del interior) y el dibujo de las mismas cajas.
Lo llama tools/ventana_login.py, que es quien escribe wnd02.xml.
"""
import random
import re

from PIL import Image, ImageDraw, ImageFilter

import ventana_login as vl
from icono_subasta import a_shp

MARCA = 'aolat creacion'
ORO, ORO_OSCURO = vl.ORO, vl.ORO_OSCURO
CELESTE = (150, 205, 255, 255)
TEXTO_CLARO = 103

# ---- Character Shape (2566) --------------------------------------------------------------------------------------
SW, SH = 486, 274
# tarjetas: (x0, y0, x1, y1, titulo)
TARJETAS_FORMA = (
    (5, 5, 131, 243, 'Gender & Hair'),
    (136, 5, 232, 243, 'Body'),
    (237, 5, 481, 129, 'Hair Color'),
    (237, 134, 481, 243, 'Complexion'),
)
# id: (x, y) nuevos (el ancho y alto se conservan del original)
POS_FORMA = {
    2582: (13, 26),            # "Gender"
    2567: (52, 24), 2568: (90, 24),
    2583: (1, 1),              # "Hair": el titulo va en la cabecera dibujada
    2581: (15, 48), 2587: (17, 50),
    2572: (28, 200), 2573: (43, 200), 2574: (94, 200),
    2585: (1, 1),              # "Stature": dibujado
    2569: (145, 44), 2570: (159, 44), 2571: (209, 44),
    2588: (145, 220), 2589: (187, 220),
    2584: (1, 1), 2586: (1, 1),
    2575: (246, 30), 2781: (246, 31),
    2576: (246, 160), 2782: (246, 161),
}
OCULTAR_FORMA = (2583, 2584, 2585, 2586)      # sus titulos los lleva la cabecera de cada tarjeta
CASILLAS_FORMA = ((159, 44, 50, 14), (43, 200, 50, 14))   # estatura y pagina del pelo: el valor en casilla hundida
ROTULOS_FORMA = ((184, 30, 'Stature'), (184, 206, 'Turn'))

# ---- Character Info (2548) ---------------------------------------------------------------------------------------
IW, IH = 362, 251
TARJETAS_INFO = (
    (5, 5, 167, 113, 'Required'),
    (5, 118, 167, 221, 'Optional'),
    (172, 5, 357, 221, 'Your Angel'),
)
# filas: (y, id del rotulo, id del valor o edit, id del boton o None)
FILAS_INFO_REQ = ((30, 2593, 2549, None), (50, 2594, None, None), (70, 2595, 2554, None), (90, 2596, 2555, 2556))
FILAS_INFO_OPC = ((140, 2598, 2605, 2606), (160, 2599, 2607, 2608), (180, 2600, 2609, 2610), (200, 2601, 2611, 2612))
OCULTAR_INFO = (2592, 2597)                   # "Required" / "Optional": dibujados
POS_INFO = {2604: (180, 26)}
VALOR_X, VALOR_W = 48, 92                      # la casilla de cada valor (48..140); el boton de lista en 125


def _fondo(w, h, semilla):
    im = vl._degradado(w, h, (24, 48, 120), vl.NOCHE_HONDA)
    brillo = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse((-w // 4, -h // 2, w + w // 4, h // 3), fill=(100, 170, 255, 60))
    im.alpha_composite(brillo.filter(ImageFilter.GaussianBlur(24)))
    d = ImageDraw.Draw(im)
    rnd = random.Random(semilla)
    for _ in range(w * h // 900):
        d.point((rnd.uniform(0, w), rnd.uniform(0, h)),
                fill=rnd.choice(((255, 236, 180), (210, 230, 255))) + (rnd.randint(90, 220),))
    return im


def _tarjeta(im, x0, y0, x1, y1, titulo):
    capa = Image.new('RGBA', im.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(capa)
    dc.rounded_rectangle((x0, y0, x1, y1), radius=7, fill=(8, 16, 46, 200))
    im.alpha_composite(capa)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, x1, y1), radius=7, outline=ORO_OSCURO)
    # la cabecera: una franja un poco mas clara con el titulo en oro y una linea dorada que se apaga a los lados
    d.rounded_rectangle((x0 + 2, y0 + 2, x1 - 2, y0 + 16), radius=5, fill=(26, 50, 118, 255))
    cx = (x0 + x1) // 2
    for k in range(0, (x1 - x0) // 2 - 6):
        a = max(0, 255 - k * 255 // max(1, (x1 - x0) // 2 - 6))
        for x in (cx - k, cx + k):
            d.point((x, y0 + 17), fill=ORO + (a,))
    vl._rotulo(d, titulo, cx, y0 + 5, color=(255, 226, 140, 255), tam=10)


def _casilla(d, x, y, w, h=14):
    d.rounded_rectangle((x - 1, y - 1, x + w, y + h), radius=3, fill=(4, 8, 28, 255), outline=(120, 96, 40, 255))


def _marco(im):
    d = ImageDraw.Draw(im)
    w, h = im.size
    d.line((8, h - 27, w - 9, h - 27), fill=ORO_OSCURO)          # la franja de los botones de abajo
    d.rectangle((0, 0, w - 1, h - 1), outline=ORO)
    d.rectangle((1, 1, w - 2, h - 2), outline=ORO_OSCURO)


def fondo_forma() -> Image.Image:
    im = _fondo(SW, SH, 2566)
    for t in TARJETAS_FORMA:
        _tarjeta(im, *t)
    d = ImageDraw.Draw(im)
    # el pedestal del personaje: un ovalo de luz en el centro de la tarjeta del medio
    luz = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(luz).ellipse((150, 160, 218, 188), fill=(120, 200, 255, 110))
    im.alpha_composite(luz.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(im)
    d.ellipse((156, 166, 212, 182), outline=(200, 170, 90, 255))
    for x, y, w, h in CASILLAS_FORMA:
        _casilla(d, x, y, w, h)
    for cx, y, texto in ROTULOS_FORMA:
        vl._rotulo(d, texto, cx, y, color=(190, 210, 255, 255), tam=9)
    # los huecos de las muestras de color, con borde fino
    for x, y, w, h in ((245, 29, 228, 96), (245, 159, 228, 72)):
        d.rounded_rectangle((x - 2, y - 2, x + w + 1, y + h + 1), radius=4, outline=(60, 90, 160, 255))
    _marco(im)
    return im


def fondo_info() -> Image.Image:
    im = _fondo(IW, IH, 2548)
    for t in TARJETAS_INFO:
        _tarjeta(im, *t)
    d = ImageDraw.Draw(im)
    for y, _r, valor, _b in FILAS_INFO_REQ + FILAS_INFO_OPC:
        if y == 50:                                # nacimiento: mes y dia, cada uno con su boton
            _casilla(d, 47, y, 28)
            _casilla(d, 95, y, 28)
        else:
            _casilla(d, VALOR_X - 1, y, VALOR_W + 2)
    # el texto de bienvenida en su recuadro y el suelo de los tres muñecos
    d.rounded_rectangle((178, 22, 352, 92), radius=5, fill=(14, 28, 74, 255), outline=(60, 90, 160, 255))
    luz = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(luz).ellipse((186, 186, 346, 212), fill=(120, 200, 255, 90))
    im.alpha_composite(luz.filter(ImageFilter.GaussianBlur(7)))
    _marco(im)
    return im


def dibujar():
    vl.LOG.mkdir(parents=True, exist_ok=True)
    (vl.LOG / 'w038_17.shp').write_bytes(a_shp(fondo_forma()))
    (vl.LOG / 'w038_23.shp').write_bytes(a_shp(fondo_info()))


def _mover(texto, wid, x, y):
    m = vl._ventana(texto, wid)
    tag = re.sub(r'range="(-?\d+),(-?\d+)', 'range="%d,%d' % (x, y), m.group(0), count=1)
    return texto[:m.start()] + tag + texto[m.end():]


def _attr(texto, wid, nombre, valor):
    m = vl._ventana(texto, wid)
    tag = m.group(0)
    if re.search(r'\b%s="[^"]*"' % nombre, tag):
        tag = re.sub(r'\b%s="[^"]*"' % nombre, '%s="%s"' % (nombre, valor), tag, count=1)
    else:
        tag = tag.rstrip('>').rstrip('/').rstrip() + ' %s="%s">' % (nombre, valor)
    return texto[:m.start()] + tag + texto[m.end():]


def _sin_tema(texto, icono):
    m = re.search(r'(<icon id="%d" [^>]*>)\s*<attrib [^>]*/>\s*(</icon>)' % icono, texto)
    if m:
        texto = texto[:m.start()] + m.group(1).rstrip('>') + ' />' + texto[m.end():]
    return texto


def _ocultar(texto, wid):
    """Fuera wsVisible: el juego no la pinta (sus titulos van dibujados en la cabecera)."""
    m = vl._ventana(texto, wid)
    fin = texto.index('</window>', m.end())
    bloque = texto[m.end():fin].replace('wsVisible="" ', '').replace(' wsVisible=""', '').replace('wsVisible=""', '')
    return texto[:m.end()] + bloque + texto[fin:]


def wnd02(texto, nl):
    texto = _sin_tema(texto, 2566)
    texto = _sin_tema(texto, 2548)
    for wid, (x, y) in POS_FORMA.items():
        texto = _mover(texto, wid, x, y)
    for wid in OCULTAR_FORMA + OCULTAR_INFO:
        texto = _ocultar(texto, wid)
    for wid, (x, y) in POS_INFO.items():
        texto = _mover(texto, wid, x, y)
    for y, rotulo, valor, boton in FILAS_INFO_REQ + FILAS_INFO_OPC:
        texto = _mover(texto, rotulo, 13, y + 1)
        if valor:
            texto = _mover(texto, valor, VALOR_X + (0 if valor == 2549 else 2), y + (0 if valor == 2549 else 1))
        if boton:
            texto = _mover(texto, boton, 126, y)
    # nacimiento: mes (2550 + boton 2551, "M" 2603) y dia (2552 + boton 2553, "D" 2602)
    for wid, x, dy in ((2550, 50, 1), (2603, 64, 1), (2551, 76, 0), (2552, 98, 1), (2602, 112, 1), (2553, 124, 0)):
        texto = _mover(texto, wid, x, 50 + dy)
    # las listas desplegables siguen a su fila: mes/dia (2560), signo... (2561) y grupo (2562)
    texto = _mover(texto, 2560, 45, 65)
    texto = _mover(texto, 2561, 45, 65)
    texto = _mover(texto, 2562, 45, 105)
    for wid in (2549, 2550, 2552, 2554, 2555, 2605, 2607, 2609, 2611, 2570, 2573):
        texto = _attr(texto, wid, 'fcolor', TEXTO_CLARO)
    return texto


def wndtext02(texto):
    """wndtext02.xml pisa los title de wnd02.xml: los rotulos que van dibujados, vacios."""
    for wid in OCULTAR_FORMA + OCULTAR_INFO:
        texto = re.sub(r'<window id="%d" title="[^"]*"/>' % wid, '<window id="%d" title=""/>' % wid, texto)
    return texto
