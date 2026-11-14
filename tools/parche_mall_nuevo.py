"""El Item Mall nuevo: una ventana propia con el diseno que paso el usuario (14/11/2026, "podriamos crear el itemmal con
este estilo y usar los iconos que aca salen?? ... y si hacemos una ventana propia?? ... de momento que se abra con un
comando GM"). El diseno esta en docs/item_mall_diseno.png (1402 x 1122).

La imagen del diseno ES la piel de la ventana: se limpia lo que cambia (textos de las pestanas y las categorias, los
productos de ejemplo de las tarjetas, los objetos de "Mis Objetos", los numeros) y se reduce a 760 x 608, que cabe en
la pantalla de 1024 x 768. Encima van los controles de verdad, recortados del mismo diseno:
  * 9 pestanas (Top Sale ... Favorite), con su texto pintado: azul, y oro la elegida;
  * hasta 10 filas de categorias (las de la pestana) con el icono del diseno que les toca;
  * 6 tarjetas: nombre, icono del objeto (game.getitemicon), precio y "Comprar";
  * "Mi Compra" = el Store Cabinet (10 casillas): pulsar una pasa el objeto a la mochila;
  * "Mis Objetos" = la mochila (35 casillas, solo para ver), "Espacio" y "Ordenar";
  * abajo, el mensaje y Historial, Regalar (con la casilla del nombre) y Cerrar; arriba el Angel Gold, el oro y la X.
La logica es server/lua/mall_nuevo.lua y server/mall_nuevo.py (comando 173). La abre el GM con /mall.

    python tools/parche_mall_nuevo.py
"""
import pathlib
import re
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import marcos_modernos as mm  # noqa: E402

DISENO = RAIZ / 'docs' / 'item_mall_diseno.png'
ENG = RAIZ / 'parches' / 'extras' / 'setting' / 'eng'
SHAPES = RAIZ / 'parches' / 'extras' / 'shape' / 'wnd01'
XML = 'wnd05.xml'
MARCA = 'aolat mall nuevo'

ANCHO_DISENO = 1402
W = 760
ESCALA = W / ANCHO_DISENO
H = round(1122 * ESCALA)                            # 608


def g(v) -> int:
    """Una medida del diseno (1402 de ancho) en la ventana."""
    return int(round(v * ESCALA))


def caja(x0, y0, x1, y1):
    """(x, y, ancho, alto) en la ventana de una caja del diseno."""
    return g(x0), g(y0), g(x1) - g(x0), g(y1) - g(y0)


# ---- ids ------------------------------------------------------------------------------------------------------------
VENTANA = 61000
CERRAR_X, AG, ORO = 61001, 61002, 61003
TAB = 61010                                         # 10
SUB = 61020                                         # 10
PAG_ANT, PAG_TXT, PAG_SIG = 61030, 61031, 61032
C_NOMBRE, C_ICONO, C_PRECIO, C_COMPRAR = 61040, 61050, 61060, 61070      # 6 de cada
CAB = 61080                                         # 10
MOCH = 61100                                        # 35
ESPACIO, ORDENAR = 61140, 61141
MENSAJE, REGALO_NOMBRE, HISTORIAL, REGALAR, CERRAR = 61150, 61151, 61152, 61153, 61154
FAVORITO = 61155                                    # la estrella de "Productos Destacados"
INTRO = 61156                                       # el texto de la pestana Intro, sobre las tarjetas
ARTE = 61190                                        # 3: logo, banner y chica, sin el tinte del tema
FONDO = 61199

I_FONDO = 61500
I_TAB = 61510                                       # 2 por pestana: la normal y la elegida
I_SUB = 61540                                       # 2 por categoria
I_COMPRAR, I_ANT, I_SIG, I_CERRAR_X, I_ORDENAR, I_HISTORIAL, I_REGALAR, I_CERRAR = range(61600, 61608)
I_ARTE = 61610                                      # 3

# Las pestanas y sus categorias son las del Item Mall del juego (setting/eng/malllayout.xml, "debe funcionar tal cual
# el IM actual", 14/11/2026), en el orden del diseno. Cada categoria: (clave, texto, icono del diseno); las mismas
# claves, con sus tipos de item_mall.json, en server/mall_nuevo.py.
PESTANAS = ('Top Sale', 'On Sale', 'LuckyBag', 'Special', 'Pet', 'Function', 'Furniture', 'Fashion', 'Intro',
            'Favorite')
ICONOS_DISENO = ('newest', 'hot', 'avatar', 'accessories', 'pets', 'mounts', 'consumables', 'upgrade', 'furniture',
                 'others')
CATEGORIAS = (
    ('top', 'Top Sale', 'hot'), ('sale', 'On Sale', 'newest'),
    ('lb_hot', 'Hot', 'hot'), ('lb_equip', 'Equipment', 'upgrade'), ('lb_armor', 'Armor', 'avatar'),
    ('lb_mount', 'Mounts', 'mounts'),
    ('sp_general', 'General', 'others'), ('sp_potion', 'Potions', 'consumables'), ('sp_teleport', 'Teleport', 'upgrade'),
    ('pet', 'Pets', 'pets'),
    ('fn_general', 'General', 'accessories'), ('fn_mini', 'Mini Games', 'newest'),
    ('fu_floor', 'Floor Decor', 'furniture'), ('fu_wall', 'Wall & Outdoor', 'furniture'),
    ('fu_carpet', 'Floor & Carpet', 'furniture'), ('fu_gacha', 'Furniture Gacha', 'furniture'),
    ('fa_male', 'Male', 'avatar'), ('fa_female', 'Female', 'avatar'), ('fa_robot', 'Robots', 'mounts'),
    ('fa_bubble', 'Bubbles', 'others'),
    ('intro', 'Mall Guide', 'newest'), ('favorite', 'Favorites', 'hot'), ('history', 'History', 'furniture'),
)

# ---- el diseno (medidas en el diseno de 1402 x 1122) -----------------------------------------------------------------
BARRA_TABS = (44, 128, 1298, 178)
TAB_AZUL, TAB_ORO = (186, 132, 300, 175), (57, 132, 173, 175)
TAB_X0, TAB_X1, TAB_Y0, TAB_Y1, TAB_HUECO = 52, 1292, 132, 175, 9
CATS = (30, 254, 250, 714)                           # las 10 filas de Categories
FILA_NORMAL, FILA_ELEGIDA = (30, 258, 250, 298), (32, 304, 248, 350)
CENTROS_ICONOS = (277, 327, 378, 427, 474, 519, 563, 607, 650, 691)
TARJETAS_X, TARJETAS_Y = (290, 545, 799), (535, 785)
# Las dos filas de tarjetas del diseno no miden lo mismo (la de abajo es mas baja): lo de cada una, desde su borde de
# arriba: la tira del nombre, el hueco del dibujo, el precio y el boton Comprar (y0, y1).
PARTES = {535: {'nombre': (5, 32), 'arte': (37, 155), 'precio': (161, 190), 'comprar': (192, 227)},
          785: {'nombre': (5, 33), 'arte': (35, 140), 'precio': (146, 174), 'comprar': (173, 208)}}
SLOT_LIMPIO = (1058, 795, 1120, 857)
MOCH_X = (1088, 1152, 1216, 1281, 1344)
MOCH_Y = (505, 567, 632, 695, 760, 822, 885)
CAB_X = (1095, 1159, 1223, 1285, 1345)
CAB_Y = (288, 352)


# EL COLOR DEL TEMA ("que se vea harmonioso si es posible tenga el color del tema", 14/11/2026). Las ventanas del juego
# son turquesa (shape/wnd01/w050_01: el color 0x024b, (0, 72, 90)). El lila y el azul del diseno pasan a esa gama; el
# oro, la piel y los dibujos no se tocan. El fondo lleva ademas ICON_ATTRIB_THEME, y el logo, el banner y la chica van
# aparte, sin tinte, para que otro tema no los manche.
TONO_JUEGO = 192 / 360                               # el turquesa de (0, 72, 90)
TONOS_DISENO = (200 / 360, 300 / 360)                # del azul al lila
ARTE_DISENO = {'logo': (0, 0, 262, 118), 'banner': (276, 194, 1032, 458), 'chica': (14, 716, 268, 1014)}


def turquesa(im, excluir=()):
    """Los azules y lilas de im pasados al turquesa del juego, salvo en las cajas de excluir."""
    import numpy as np
    hsv = np.array(im.convert('RGB').convert('HSV'), dtype=np.float32) / 255.0
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    lo, hi = TONOS_DISENO
    medio = (lo + hi) / 2
    cambia = (h >= lo) & (h <= hi) & (s > 0.06)
    for x0, y0, x1, y1 in excluir:
        cambia[y0:y1, x0:x1] = False
    h = np.where(cambia, (TONO_JUEGO + (h - medio) * 0.35) % 1.0, h)
    s = np.where(cambia, np.clip(s * 1.25 + 0.08, 0, 1), s)
    out = Image.fromarray((np.stack([h, s, v], -1) * 255).round().astype(np.uint8), 'HSV').convert('RGBA')
    out.putalpha(im.getchannel('A') if im.mode == 'RGBA' else Image.new('L', im.size, 255))
    return out


def nitido(im):
    """Tras reducir: el contorno marcado ("no se ve nitido, que se vea mas nitido", 14/11/2026)."""
    alfa = im.getchannel('A')
    rgb = im.convert('RGB').filter(ImageFilter.UnsharpMask(radius=1.1, percent=110, threshold=1))
    rgb.putalpha(alfa)
    return rgb


def reducir(im, tam):
    return nitido(im.resize(tam, Image.LANCZOS))


def _franja(im, dst, x_src):
    """Tapa la caja dst con la columna x_src (3 px) estirada: borra textos en barras de degradado horizontal."""
    x0, y0, x1, y1 = dst
    tira = im.crop((x_src, y0, x_src + 3, y1)).resize((x1 - x0, y1 - y0), Image.BILINEAR)
    im.paste(tira, (x0, y0))


def _tarjeta_arte(im, x0, y0):
    """El hueco del dibujo de una tarjeta, sin el producto de ejemplo: el degradado de su fondo y un brillo suave."""
    a0, a1 = PARTES[y0]['arte']
    a = (x0 + 12, y0 + a0, x0 + 224, y0 + a1)
    arriba, abajo = im.getpixel((a[0] + 4, a[1] + 3)), im.getpixel((a[0] + 4, a[3] - 4))
    w, h = a[2] - a[0], a[3] - a[1]
    capa = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(capa)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line((0, y, w, y), fill=tuple(int(arriba[k] + (abajo[k] - arriba[k]) * t) for k in range(3)) + (255,))
    brillo = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse((w * 0.25, h * 0.12, w * 0.75, h * 0.92), fill=(190, 240, 255, 80))
    capa.alpha_composite(brillo.filter(ImageFilter.GaussianBlur(18)))
    mascara = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w - 1, h - 1), radius=10, fill=255)
    im.paste(capa, (a[0], a[1]), mascara)


def limpio() -> Image.Image:
    """El diseno sin lo que cambia, a tamano completo."""
    im = Image.open(DISENO).convert('RGBA')
    _franja(im, BARRA_TABS, 178)
    # Categories: las 10 filas vacias.
    fila = _fila_vacia(im, FILA_NORMAL, CATS[2] - CATS[0], 42)
    paso = (CATS[3] - CATS[1]) / 10
    _franja(im, CATS, 26)
    for k in range(10):
        im.alpha_composite(fila, (CATS[0], int(CATS[1] + k * paso)))
    _franja(im, (890, 482, 1032, 524), 870)                       # "Ver Todos" -> paginas
    for y0 in TARJETAS_Y:
        for x0 in TARJETAS_X:
            pt = PARTES[y0]
            _franja(im, (x0 + 14, y0 + pt['nombre'][0], x0 + 222, y0 + pt['nombre'][1]), x0 + 16)
            _tarjeta_arte(im, x0, y0)
            _franja(im, (x0 + 110, y0 + pt['precio'][0], x0 + 200, y0 + pt['precio'][1]), x0 + 202)
    hueco = im.crop(SLOT_LIMPIO)
    for y in MOCH_Y:
        for x in MOCH_X:
            im.alpha_composite(hueco, (x - 31, y - 31))
    _franja(im, (1128, 934, 1236, 972), 1236)                     # "20 / 100"
    _franja(im, (96, 1046, 840, 1086), 836)                       # el mensaje de abajo
    _franja(im, (944, 60, 1034, 98), 1034)                        # los numeros del Angel Gold y del oro
    _franja(im, (1146, 60, 1264, 98), 1142)
    return im


def _fila_vacia(im, src, ancho, alto):
    """Una fila de Categories sin icono ni texto: sus dos bordes y el centro estirado."""
    x0, y0, x1, y1 = src
    pieza = im.crop(src)
    w = x1 - x0
    izq, der, medio = pieza.crop((0, 0, 14, pieza.height)), pieza.crop((w - 12, 0, w, pieza.height)), \
        pieza.crop((w - 26, 0, w - 22, pieza.height))
    fila = Image.new('RGBA', (ancho, pieza.height))
    fila.paste(medio.resize((ancho - 26, pieza.height)), (14, 0))
    fila.paste(izq, (0, 0))
    fila.paste(der, (ancho - 12, 0))
    return fila.resize((ancho, alto), Image.LANCZOS)


def fondo() -> Image.Image:
    return reducir(turquesa(limpio(), [c for n, c in ARTE_DISENO.items() if n != 'logo']), (W, H))


def arte():
    """{nombre: (imagen, (x, y))}: el logo, el banner y la chica a su color, encima del fondo con tinte."""
    im = Image.open(DISENO).convert('RGBA')
    res = {}
    for nombre, (x0, y0, x1, y1) in ARTE_DISENO.items():
        pieza = im.crop((x0, y0, x1, y1))
        if nombre == 'logo':
            pieza = solo_logo(pieza)
        res[nombre] = (reducir(pieza, (g(x1) - g(x0), g(y1) - g(y0))), (g(x0), g(y0)))
    return res


def solo_logo(pieza):
    """Del recorte del logo, solo el logo (letras azules, contornos y alas blancas, halo dorado): el cielo lila de
    detras se queda en el fondo, que ya es turquesa."""
    import numpy as np
    hsv = np.array(pieza.convert('RGB').convert('HSV'), dtype=np.float32) / 255.0
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    logo = (s > 0.55) | ((v > 0.86) & (s < 0.28)) | ((h > 0.08) & (h < 0.18) & (s > 0.35))
    mascara = Image.fromarray((logo * 255).astype(np.uint8), 'L').filter(ImageFilter.MaxFilter(3))
    out = pieza.copy()
    out.putalpha(mascara.filter(ImageFilter.GaussianBlur(1)))
    return out


# ---- piezas ---------------------------------------------------------------------------------------------------------
def _letra(tam, peso='SemiBold Condensed'):
    f = ImageFont.truetype('bahnschrift.ttf', tam)
    try:
        f.set_variation_by_name(peso)
    except (OSError, ValueError):
        pass
    return f


def _texto(im, texto, x, y, tam, color, sombra=(10, 12, 40, 200), centrado=True):
    d = ImageDraw.Draw(im)
    f = _letra(tam)
    c = d.textbbox((0, 0), texto, font=f)
    if centrado:
        x -= (c[2] - c[0]) // 2 + c[0]
    y -= (c[3] - c[1]) // 2 + c[1]
    if sombra:
        d.text((x + 1, y + 1), texto, font=f, fill=sombra)
    d.text((x, y), texto, font=f, fill=color)


def _estados(im):
    """(normal, encima, pulsado): mas luz con el raton, mas oscuro y un pixel abajo al pulsar."""
    def luz(f):
        rgb = ImageEnhance.Brightness(im.convert('RGB')).enhance(f)
        rgb.putalpha(im.getchannel('A'))
        return rgb
    d = luz(0.82)
    d = d.transform(d.size, Image.AFFINE, (1, 0, 0, 0, 1, -1))
    return im, luz(1.18), d


def _boton(src, tam=None, tinte=True):
    im = Image.open(DISENO).convert('RGBA').crop(src)
    if tinte:
        im = turquesa(im)
    return reducir(im, tam or (g(src[2]) - g(src[0]), g(src[3]) - g(src[1])))


def _redondear(im, radio):
    m = Image.new('L', im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radio, fill=255)
    out = im.copy()
    out.putalpha(Image.composite(im.getchannel('A'), Image.new('L', im.size, 0), m))
    return out


def _tab_vacia(src, ancho, alto, tinte=True):
    im = Image.open(DISENO).convert('RGBA').crop(src)
    if tinte:
        im = turquesa(im)
    w = im.width
    izq, der, medio = im.crop((0, 0, 12, im.height)), im.crop((w - 12, 0, w, im.height)), im.crop((10, 0, 14, im.height))
    t = Image.new('RGBA', (ancho * 3, im.height))
    t.paste(medio.resize((ancho * 3 - 24, im.height)), (12, 0))
    t.paste(izq, (0, 0))
    t.paste(der, (ancho * 3 - 12, 0))
    return _redondear(reducir(t, (ancho, alto)), 4)


def tab_rect(i):
    ancho = (TAB_X1 - TAB_X0 - TAB_HUECO * (len(PESTANAS) - 1)) / len(PESTANAS)
    x0 = TAB_X0 + i * (ancho + TAB_HUECO)
    return x0, TAB_Y0, x0 + ancho, TAB_Y1


def tabs():
    """{archivo: imagen}: cada pestana en azul (normal, encima, pulsada) y en oro (elegida)."""
    res = {}
    x0, y0, x1, y1 = caja(*tab_rect(0))[0], 0, 0, 0
    _, _, w, h = caja(*tab_rect(0))
    azul, oro = _tab_vacia(TAB_AZUL, w, h), _tab_vacia(TAB_ORO, w, h, tinte=False)
    for i, nombre in enumerate(PESTANAS):
        a = azul.copy()
        _texto(a, nombre, w // 2, h // 2, 12, (240, 244, 255, 255))
        n, f, d = _estados(a)
        o = oro.copy()
        _texto(o, nombre, w // 2, h // 2, 12, (70, 34, 4, 255), sombra=(255, 236, 170, 160))
        res['aolat_mall_tab%d_n' % i], res['aolat_mall_tab%d_f' % i] = n, f
        res['aolat_mall_tab%d_d' % i], res['aolat_mall_tab%d_s' % i] = o, o
    return res


def icono_diseno(cual) -> Image.Image:
    """El icono de una categoria del diseno, sin el fondo de su fila, a 22 px."""
    im = Image.open(DISENO).convert('RGBA')
    yc = CENTROS_ICONOS[ICONOS_DISENO.index(cual)]
    pieza = im.crop((62 - 22, yc - 22, 62 + 22, yc + 22))
    ref = im.getpixel((92, yc - 15)) if cual != 'hot' else im.getpixel((92, yc - 15))
    px = pieza.load()
    for y in range(pieza.height):
        for x in range(pieza.width):
            r, gg, b, a = px[x, y]
            dist = abs(r - ref[0]) + abs(gg - ref[1]) + abs(b - ref[2])
            px[x, y] = (r, gg, b, max(0, min(255, (dist - 40) * 4)))
    return reducir(pieza, (22, 22))


def filas():
    """{archivo: imagen}: cada categoria (icono y texto) en su fila normal y en la elegida (oro)."""
    res = {}
    paso = (CATS[3] - CATS[1]) / 10
    w, h = g(CATS[2]) - g(CATS[0]), g(CATS[1] + paso) - g(CATS[1]) - 1
    im = Image.open(DISENO).convert('RGBA')
    normal = reducir(turquesa(_fila_vacia(im, FILA_NORMAL, CATS[2] - CATS[0], 42)), (w, h))
    elegida = reducir(_fila_vacia(im, FILA_ELEGIDA, CATS[2] - CATS[0], 42), (w, h))
    for k, (clave, texto, icono) in enumerate(CATEGORIAS):
        ic = icono_diseno(icono)
        for estado, base in (('n', normal), ('s', elegida)):
            f = base.copy()
            f.alpha_composite(ic, (8, (h - 22) // 2))
            color = (70, 34, 4, 255) if estado == 's' else (240, 244, 255, 255)
            _texto(f, texto, 38, h // 2, 13, color, sombra=None if estado == 's' else (10, 12, 40, 200),
                   centrado=False)
            res['aolat_mall_cat%d_%s' % (k, estado)] = f
        n, fo, d = _estados(res['aolat_mall_cat%d_n' % k])
        res['aolat_mall_cat%d_f' % k] = fo
    return res


BOTONES = {
    'comprar': (I_COMPRAR, (332, 727, 492, 762)),
    'ant': (I_ANT, (560, 430, 597, 467)),
    'sig': (I_SIG, (758, 430, 795, 467)),
    'cerrarx': (I_CERRAR_X, (1331, 43, 1391, 103)),
    'ordenar': (I_ORDENAR, (1242, 930, 1372, 977)),
    'historial': (I_HISTORIAL, (876, 1041, 1040, 1094)),
    'regalar': (I_REGALAR, (1054, 1041, 1214, 1094)),
    'cerrar': (I_CERRAR, (1226, 1041, 1362, 1094)),
}


def botones():
    res = {}
    for nombre, (_icono, src) in BOTONES.items():
        n, f, d = _estados(_boton(src, tinte=nombre != 'comprar'))
        for e, im in (('n', n), ('f', f), ('d', d)):
            res['aolat_mall_%s_%s' % (nombre, e)] = im
    return res


def piezas():
    res = {'aolat_mall_fondo': fondo()}
    for nombre, (im, _xy) in arte().items():
        res['aolat_mall_arte_' + nombre] = im
    res.update(tabs())
    res.update(filas())
    res.update(botones())
    return res


# ---- la ventana -----------------------------------------------------------------------------------------------------
def _w(clase, wid, rango, extra='', estilo='wsVisible=""', cuerpo=''):
    x, y, w, h = rango
    return ('    <window class="%s" id="%d" range="%d,%d,%d,%d"%s>\n        <style %s />\n%s    </window>\n'
            % (clase, wid, x, y, w, h, extra, estilo, cuerpo))


def _static(wid, rango, titulo='', color=103, derecha=False, centro=False):
    estilo = 'wsVisible="" ssVCenter=""' + (' ssRight=""' if derecha else '') + (' ssHCenter=""' if centro else '')
    return _w('WND_CLASS_STATIC', wid, rango, ' title="%s" fcolor="%d" font="1"' % (titulo, color), estilo)


def _btn(wid, rango, icono, funcion, appdata=None, texto='', tip='', tooltip_item=False, visible=True):
    extra = ' icon="%d"' % icono
    if appdata is not None:
        extra += ' appdata="%d"' % appdata
    if texto:
        extra += ' title="%s" fcolor="103" font="1"' % texto
    cuerpo = '        <OnCommand>%s</OnCommand>\n' % funcion if funcion else ''
    if tooltip_item:
        extra += ' tooltip="10041" tooldelay="5"'
        cuerpo += '        <OnTooltip>OnMallTip</OnTooltip>\n'
    elif tip:
        extra += ' tooltip="10040" tooltext="%s"' % tip
    estilo = ('wsVisible="" ' if visible else '') + 'bsHCenter="" bsVBottom="" wsTab=""'
    return _w('WND_CLASS_BUTTON', wid, rango, extra, estilo, cuerpo)


def _icono(iid, archivo, estados=True):
    if estados:
        return ('    <icon id="%d" dir="\\wnd01\\" normal="%s_n" focus="%s_f" down="%s_d" disable="%s_n" />\n'
                % (iid, archivo, archivo, archivo, archivo))
    return ('    <icon id="%d" dir="\\wnd01\\" normal="%s" focus="normal" down="normal" disable="normal" />\n'
            % (iid, archivo))


def tarjeta(c):
    """(x0, y0) en el diseno de la tarjeta c (0..5)."""
    return TARJETAS_X[c % 3], TARJETAS_Y[c // 3]


def bloque() -> str:
    hijos, ventanas = [], []

    def poner(wid, xml):
        hijos.append(wid)
        ventanas.append(xml)

    # Lo que va encima de todo primero (el juego pinta los hijos del ultimo al primero).
    poner(REGALO_NOMBRE, _w('WND_CLASS_EDIT', REGALO_NOMBRE, caja(560, 1050, 830, 1080),
                            ' icon="2353" fcolor="105" font="1" tpos="2,2" limit="16"', 'wsTab=""'))
    poner(MENSAJE, _static(MENSAJE, caja(100, 1048, 840, 1084)))
    poner(HISTORIAL, _btn(HISTORIAL, caja(*BOTONES['historial'][1]), I_HISTORIAL, 'OnMallHistorial',
                          tip='Your recent purchases'))
    poner(REGALAR, _btn(REGALAR, caja(*BOTONES['regalar'][1]), I_REGALAR, 'OnMallRegalar',
                        tip='Send the selected item as a gift'))
    poner(CERRAR, _btn(CERRAR, caja(*BOTONES['cerrar'][1]), I_CERRAR, 'OnMallCerrar'))
    poner(CERRAR_X, _btn(CERRAR_X, caja(*BOTONES['cerrarx'][1]), I_CERRAR_X, 'OnMallCerrar'))
    poner(AG, _static(AG, caja(946, 60, 1034, 98), color=103))
    poner(ORO, _static(ORO, caja(1146, 60, 1262, 98), color=105, derecha=True))
    for i in range(len(PESTANAS)):
        poner(TAB + i, _btn(TAB + i, caja(*tab_rect(i)), I_TAB + 2 * i, 'OnMallTab', appdata=i))
    paso = (CATS[3] - CATS[1]) / 10
    for k in range(10):
        y = CATS[1] + k * paso
        x, yy, w, _ = caja(CATS[0], y, CATS[2], y + paso)
        poner(SUB + k, _btn(SUB + k, (x, yy, w, g(y + paso) - g(y) - 1), I_SUB, 'OnMallSub', appdata=k,
                            visible=False))
    poner(FAVORITO, _btn(FAVORITO, caja(282, 480, 326, 524), 0, 'OnMallFavorito',
                         tip='Add or remove the selected item from Favorite'))
    poner(INTRO, _w('WND_CLASS_MSTATIC', INTRO, caja(300, 540, 1026, 1000), ' title="" fcolor="103" font="1"',
                    'ssLeft=""'))
    poner(PAG_ANT, _btn(PAG_ANT, caja(900, 486, 934, 520), I_ANT, 'OnMallPag', appdata=0, tip='Previous page'))
    poner(PAG_TXT, _static(PAG_TXT, caja(936, 486, 990, 520), centro=True))
    poner(PAG_SIG, _btn(PAG_SIG, caja(992, 486, 1026, 520), I_SIG, 'OnMallPag', appdata=1, tip='Next page'))
    for c in range(6):
        x0, y0 = tarjeta(c)
        pt = PARTES[y0]
        centro_arte = (pt['arte'][0] + pt['arte'][1]) // 2
        poner(C_COMPRAR + c, _btn(C_COMPRAR + c, caja(x0 + 42, y0 + pt['comprar'][0], x0 + 202,
                                                      y0 + pt['comprar'][1]), I_COMPRAR,
                                  'OnMallComprar', appdata=c, visible=False))
        poner(C_ICONO + c, _btn(C_ICONO + c, (g(x0 + 118) - 18, g(y0 + centro_arte) - 18, 36, 36), 0, 'OnMallCarta',
                                appdata=c, tooltip_item=True, visible=False))
        poner(C_NOMBRE + c, _static(C_NOMBRE + c, caja(x0 + 12, y0 + pt['nombre'][0], x0 + 224,
                                                        y0 + pt['nombre'][1]), centro=True))
        poner(C_PRECIO + c, _static(C_PRECIO + c, caja(x0 + 112, y0 + pt['precio'][0], x0 + 200,
                                                        y0 + pt['precio'][1]), color=105))
    for k in range(10):
        x, y = CAB_X[k % 5], CAB_Y[k // 5]
        poner(CAB + k, _btn(CAB + k, (g(x) - 16, g(y) - 16, 32, 32), 0, 'OnMallCab', appdata=100 + k,
                            tooltip_item=True))
    for k in range(35):
        x, y = MOCH_X[k % 5], MOCH_Y[k // 5]
        poner(MOCH + k, _btn(MOCH + k, (g(x) - 16, g(y) - 16, 32, 32), 0, '', appdata=200 + k, tooltip_item=True))
    poner(ESPACIO, _static(ESPACIO, caja(1130, 934, 1236, 972)))
    poner(ORDENAR, _btn(ORDENAR, caja(*BOTONES['ordenar'][1]), I_ORDENAR, 'OnMallOrdenar', tip='Sort your backpack'))
    for k, (nombre, (im, (x, y))) in enumerate(arte().items()):
        poner(ARTE + k, _w('WND_CLASS_BASE', ARTE + k, (x, y, im.width, im.height), ' icon="%d"' % (I_ARTE + k)))
    poner(FONDO, _w('WND_CLASS_BASE', FONDO, (0, 0, W, H), ' icon="%d"' % I_FONDO))

    iconos = ['    <icon id="%d" dir="\\wnd01\\" normal="aolat_mall_fondo" focus="normal" down="normal" '
              'disable="normal">\n        <attrib ICON_ATTRIB_THEME="" ICON_ATTRIB_FAST="" />\n    </icon>\n' % I_FONDO]
    for k, nombre in enumerate(ARTE_DISENO):
        iconos.append(_icono(I_ARTE + k, 'aolat_mall_arte_' + nombre, False))
    for i in range(len(PESTANAS)):
        iconos.append(_icono(I_TAB + 2 * i, 'aolat_mall_tab%d' % i))
        iconos.append(_icono(I_TAB + 2 * i + 1, 'aolat_mall_tab%d_s' % i, False))
    for k in range(len(CATEGORIAS)):
        iconos.append('    <icon id="%d" dir="\\wnd01\\" normal="aolat_mall_cat%d_n" focus="aolat_mall_cat%d_f" '
                      'down="aolat_mall_cat%d_s" disable="aolat_mall_cat%d_n" />\n' % (I_SUB + 2 * k, k, k, k, k))
        iconos.append(_icono(I_SUB + 2 * k + 1, 'aolat_mall_cat%d_s' % k, False))
    for nombre, (iid, _src) in BOTONES.items():
        iconos.append(_icono(iid, 'aolat_mall_%s' % nombre))
    cab = ('    <window class="WND_CLASS_BASE" range="0,0,%d,%d" id="%d" title="Item Mall">\n'
           '        <style wsVisible="" wsMoveable="" />\n%s    </window>\n'
           % (W, H, VENTANA, ''.join('        <child>%d</child>\n' % h for h in hijos)))
    return '    <!-- %s -->\n%s%s%s    <!-- /%s -->\n' % (MARCA, cab, ''.join(ventanas), ''.join(iconos), MARCA)


def _guardar_xml():
    ruta = ENG / XML
    crudo = ruta.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\r?\n' % (MARCA, MARCA), '', texto, flags=re.S)
    texto = texto.replace('\r\n', '\n')
    fin = texto.rindex('</root>')
    texto = (texto[:fin] + bloque() + texto[fin:]).replace('\n', nl)
    ruta.write_bytes((b'\xef\xbb\xbf' if bom else b'') + texto.encode('utf-8'))


def main():
    SHAPES.mkdir(parents=True, exist_ok=True)
    for nombre, im in piezas().items():
        (SHAPES / (nombre + '.shp')).write_bytes(mm.a_shp32(im))
    _guardar_xml()
    print('Item Mall nuevo: ventana %d (%dx%d) en %s' % (VENTANA, W, H, XML))


if __name__ == '__main__':
    main()
