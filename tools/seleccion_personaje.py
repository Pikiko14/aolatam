"""La pantalla de seleccion de personaje con la linea grafica del login nuevo (12/11/2026, "cambiemos toda la interfaz
de seleccion de personaje").

Lo que se cambia (todo en setting/eng/wnd02.xml y shape/log/aolat_sel_*.shp; lo llama tools/ventana_login.py, que es
quien escribe wnd02.xml), en estilo plano ("que se vea moderno"): pizarra oscura y un acento celeste.
  * las tres fichas (2713-2715, 189x426, titulo "Adventurer"): su interior era el del tema (verde con marca de agua);
    ahora es una hija BASE con el icono 60465 (181x402) y las hijas se recolocan segun DISPOSICION;
  * el aro del retrato (2728) y los botones Set / Face (2734);
  * la marca de la ficha elegida (2534, era la flecha roja): contorno de acento y una barra debajo que late;
  * el menu de la derecha (2565), el resaltado de sus opciones (2501) y la flecha de volver (2712, icono 60466).

Las posiciones de los textos de la ficha las pone el juego (las ventanas hijas no se mueven): el dibujo sigue sus
range de wnd02.xml.

    python tools/ventana_login.py        (dibuja tambien esto)
    python tools/generar_parche.py
"""
import re

from PIL import Image, ImageDraw, ImageFilter

import ventana_login as vl
from icono_subasta import a_shp

MARCA = 'aolat seleccion'
FW, FH = 181, 402                        # el interior de la ficha (la 2534, que la cubre entera, es de 181x402)
ICONO_FICHA, ICONO_VOLVER = 60465, 60466
FICHAS = (2713, 2714, 2715)
# 12/11/2026, "se ve horrible cambia toda la distribucion por algo mas moderno y harmonioso". La ficha nueva:
#   arriba a la izquierda el retrato; a su derecha el nivel, el bando y los botones Set / Face; arriba a la derecha el
#   emblema de clase, que lo pinta el juego (no se mueve: se le dibuja un hueco con aro alrededor);
#   el nombre en una banda de oro a todo lo ancho y debajo el sitio;
#   la tabla Title / Job / HP / MP / Sign;
#   el escenario con el pedestal, donde el juego pone al personaje (los pies a ~382, tampoco se mueve).
RETRATO = (6, 6)
EMBLEMA = (158, 24, 21)                  # centro y radio del hueco del emblema (medido en la captura: x 142..174)
COL_X, COL_W = 70, 64
LV_Y, BANDO_Y, BOTONES_Y = 10, 28, 48
NOMBRE_Y, SITIO_Y = 74, 92
STATS_Y = [112 + 14 * i for i in range(5)]
# Cada hija de la ficha: (las tres ids, una por ficha) -> x, y, ancho, alto
DISPOSICION = {
    (2728, 2729, 2730): (RETRATO[0], RETRATO[1], 60, 60),            # aro del retrato
    (2740, 2741, 2742): (RETRATO[0] + 5, RETRATO[1] + 5, 50, 50),    # la cara
    (2719, 2720, 2721): (COL_X, LV_Y, COL_W, 14),                   # LV
    (2722, 2723, 2724): (COL_X, BANDO_Y, COL_W, 14),                # bando
    (2731, 2732, 2733): (COL_X, BOTONES_Y, 31, 17),                 # Set
    (2734, 2735, 2736): (COL_X + 33, BOTONES_Y, 31, 17),            # Face
    (2716, 2717, 2718): (16, NOMBRE_Y, FW - 32, 14),                # nombre
    (2725, 2726, 2727): (16, SITIO_Y, FW - 32, 14),                 # sitio
    (2757, 2758, 2759): (12, STATS_Y[0], 24, 74),                   # rotulos Title..Sign
    (2763, 2764, 2765): (44, STATS_Y[0], 1, 1),
    (2766, 2767, 2768): (44, STATS_Y[1], 1, 1),
    (2769, 2770, 2771): (44, STATS_Y[2], 1, 1),
    (2772, 2773, 2774): (44, STATS_Y[3], 1, 1),
    (2775, 2776, 2777): (44, STATS_Y[4], 1, 1),
    (2760, 2761, 2762): (100, STATS_Y[4] + 1, 1, 1),                # B.T.
    (2778, 2779, 2780): (134, STATS_Y[4] + 1, 1, 1),                # su valor
    (2783, 2784, 2785): (44, 210, 94, 28),                          # Change name (solo si hace falta)
    (2786, 2787, 2788): (44, 242, 94, 28),                          # Edit guild name
}
# El fondo va en una hija BASE de cada ficha, la primera (debajo de todo): el icono puesto en la propia ventana
# DLG_1 no lo pinta el juego en estas fichas (seguian verdes).
FONDOS = (60470, 60471, 60472)
TITULO_FICHA = 'Adventurer'
PIES = (90, 384)                         # donde apoya el personaje (medido en la captura: los pies a ~382)
MW, MH = 120, 143                        # el menu (2565)
OPCIONES_Y = (20, 39, 58, 77, 96)        # 2708, 2709, 2710/2711, 2501/2502, 2503: x 11, 98x17
VOLVER = (26, 18)                        # la 2712, en 46,117

# 12/11/2026, "que se vea moderno": estilo plano. Pizarra oscura, un solo color de acento (celeste), lineas de 1 px,
# esquinas redondeadas y nada de oro, gemas ni estrellas. El .shp solo tiene transparencia de todo o nada (alfa < 128
# es hueco): no hay cristal translucido, todo es opaco y los brillos van horneados sobre el propio fondo.
FONDO_ARRIBA, FONDO_ABAJO = (24, 32, 54), (10, 14, 26)
SUPERFICIE = (30, 41, 64)
SUPERFICIE_2 = (24, 33, 54)
LINEA = (52, 66, 94)
ACENTO = (56, 189, 248)
ACENTO_OSCURO = (3, 105, 161)
TENUE = (120, 136, 162)


def _rgba(c, a=255):
    return tuple(c) + (a,)


def _pastilla(w, h, relleno, borde=None, radio=None):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=radio if radio is not None else h // 2,
                                         fill=_rgba(relleno), outline=_rgba(borde) if borde else None)
    return im


def _barra_acento(d, w):
    d.rectangle((0, 0, w - 1, 1), fill=_rgba(ACENTO))


def _resplandor(im, caja, color, alfa, radio):
    capa = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(capa).ellipse(caja, fill=_rgba(color, alfa))
    im.alpha_composite(capa.filter(ImageFilter.GaussianBlur(radio)))


def ficha() -> Image.Image:
    """El fondo de la ficha (ver DISPOSICION): retrato con el nivel en pastilla y el bando al lado, el nombre con un
    subrayado de acento, una tarjeta para Title..Sign y abajo el escenario con una plataforma de luz."""
    im = vl._degradado(FW, FH, FONDO_ARRIBA, FONDO_ABAJO)
    # EL ESCENARIO, primero (sus brillos quedan debajo de todo lo demas)
    px, py = PIES
    _resplandor(im, (px - 85, py - 170, px + 85, py + 20), ACENTO_OSCURO, 90, 30)
    _resplandor(im, (px - 50, py - 16, px + 50, py + 12), ACENTO, 120, 8)
    d = ImageDraw.Draw(im)
    d.ellipse((px - 58, py - 12, px + 58, py + 12), fill=_rgba(SUPERFICIE), outline=_rgba(LINEA))
    d.ellipse((px - 48, py - 8, px + 48, py + 8), outline=_rgba(ACENTO))
    d.ellipse((px - 30, py - 5, px + 30, py + 5), outline=_rgba(ACENTO_OSCURO))
    # el retrato y el hueco del emblema de clase: circulos de superficie
    x, y = RETRATO
    d.ellipse((x, y, x + 59, y + 59), fill=_rgba(SUPERFICIE_2))
    cx, cy, r = EMBLEMA
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_rgba(SUPERFICIE_2), outline=_rgba(LINEA))
    # el nivel en una pastilla de acento y el bando sobre una linea tenue
    im.alpha_composite(_pastilla(COL_W, 15, ACENTO_OSCURO), (COL_X, LV_Y - 1))
    d = ImageDraw.Draw(im)
    d.line((COL_X + 4, BANDO_Y + 14, COL_X + COL_W - 4, BANDO_Y + 14), fill=_rgba(LINEA))
    # el nombre: sin caja, con un subrayado corto de acento; el sitio debajo
    d.line((8, NOMBRE_Y - 6, FW - 9, NOMBRE_Y - 6), fill=_rgba(LINEA))
    d.rectangle((FW // 2 - 14, NOMBRE_Y + 15, FW // 2 + 13, NOMBRE_Y + 16), fill=_rgba(ACENTO))
    # la tarjeta de Title..Sign: esquinas redondeadas y separadores de 1 px
    y0, y1 = STATS_Y[0] - 3, STATS_Y[-1] + 16
    d.rounded_rectangle((6, y0, FW - 7, y1), radius=6, fill=_rgba(SUPERFICIE), outline=_rgba(LINEA))
    for yy in STATS_Y[1:]:
        d.line((12, yy - 1, FW - 13, yy - 1), fill=_rgba(SUPERFICIE_2))
    # el borde de la ficha: 1 px y una barra de acento arriba
    d.rectangle((0, 0, FW - 1, FH - 1), outline=_rgba(LINEA))
    _barra_acento(d, FW)
    return im


def retrato() -> Image.Image:
    """El aro del retrato (60x60): un anillo de acento de 2 px, transparente por dentro."""
    im = Image.new('RGBA', (60, 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, 59, 59), outline=_rgba(ACENTO), width=2)
    d.ellipse((3, 3, 56, 56), outline=_rgba(FONDO_ABAJO), width=2)
    return im


def mini(estado) -> Image.Image:
    """Set / Face, 31x17: pastilla fantasma (borde de acento); llena con el raton encima o pulsada."""
    relleno, borde = {'n': (SUPERFICIE, LINEA), 'f': (ACENTO_OSCURO, ACENTO), 's': ((2, 80, 124), ACENTO)}[estado]
    return _pastilla(31, 17, relleno, borde, radio=8)


def marca(fotograma) -> Image.Image:
    """La ficha elegida (181x434 desde la esquina de la ficha): un contorno de acento de 2 px por dentro del borde y,
    debajo, una barra de acento con una punta; la barra se estira en el segundo fotograma (late)."""
    im = Image.new('RGBA', (FW, FH + 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, FW - 1, FH - 1), outline=_rgba(ACENTO), width=2)
    ancho = (48, 64)[fotograma]
    cx, y = FW // 2, FH + 8
    d.polygon(((cx - 6, y), (cx + 6, y), (cx, y - 6)), fill=_rgba(ACENTO))
    d.rounded_rectangle((cx - ancho // 2, y, cx + ancho // 2, y + 4), radius=2, fill=_rgba(ACENTO))
    return im


def menu() -> Image.Image:
    im = vl._degradado(MW, MH, FONDO_ARRIBA, FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    f = vl._letra(8)
    texto = 'CHARACTERS'
    caja = d.textbbox((0, 0), texto, font=f)
    d.text(((MW - (caja[2] - caja[0])) // 2 - caja[0], 6 - caja[1]), texto, font=f, fill=_rgba(TENUE))
    for y in OPCIONES_Y[1:]:
        d.line((16, y - 2, MW - 17, y - 2), fill=_rgba(SUPERFICIE))
    d.line((10, 114, MW - 11, 114), fill=_rgba(LINEA))
    d.rectangle((0, 0, MW - 1, MH - 1), outline=_rgba(LINEA))
    _barra_acento(d, MW)
    return im


def opcion(estado) -> Image.Image:
    """El resaltado de una opcion del menu (98x17): pastilla de acento llena."""
    return _pastilla(98, 17, ACENTO_OSCURO if estado == 'f' else (2, 80, 124), ACENTO if estado == 'f' else None,
                     radio=8)


def volver(estado) -> Image.Image:
    w, h = VOLVER
    relleno, borde = {'n': (SUPERFICIE, LINEA), 'f': (ACENTO_OSCURO, ACENTO), 's': ((2, 80, 124), ACENTO)}[estado]
    im = _pastilla(w, h, relleno, borde, radio=9)
    d = ImageDraw.Draw(im)
    o = 1 if estado == 's' else 0
    c = (240, 246, 252, 255)
    d.line((8, 9 + o, 18, 9 + o), fill=c, width=2)
    d.line((8, 9 + o, 12, 5 + o), fill=c, width=2)
    d.line((8, 9 + o, 12, 13 + o), fill=c, width=2)
    return im


PIEZAS = {'aolat_sel_ficha': ficha, 'aolat_sel_retrato': retrato, 'aolat_sel_menu': menu,
          'aolat_sel_marca1': lambda: marca(0), 'aolat_sel_marca2': lambda: marca(1),
          **{'aolat_sel_mini_%s' % e: (lambda e=e: mini(e)) for e in 'nfs'},
          **{'aolat_sel_opcion_%s' % e: (lambda e=e: opcion(e)) for e in 'fs'},
          **{'aolat_sel_volver_%s' % e: (lambda e=e: volver(e)) for e in 'nfs'}}


def dibujar():
    vl.LOG.mkdir(parents=True, exist_ok=True)
    for nombre, f in PIEZAS.items():
        (vl.LOG / (nombre + '.shp')).write_bytes(a_shp(f()))


def _icono(texto, iid, nuevo):
    """Cambia el <icon id=iid ...> (con o sin <attrib> dentro) por la linea nuevo."""
    m = re.search(r'<icon id="%d" [^>]*?(?:/>|>.*?</icon>)' % iid, texto, flags=re.S)
    if not m:
        raise SystemExit('no esta el icono %d' % iid)
    return texto[:m.start()] + nuevo + texto[m.end():]


def _attr(texto, wid, nombre, valor):
    m = vl._ventana(texto, wid)
    tag = m.group(0)
    if re.search(r'\b%s="[^"]*"' % nombre, tag):
        tag = re.sub(r'\b%s="[^"]*"' % nombre, '%s="%s"' % (nombre, valor), tag, count=1)
    else:
        tag = tag[:-1].rstrip('/').rstrip() + ' %s="%s"' % (nombre, valor) + ('/>' if tag.endswith('/>') else '>')
    return texto[:m.start()] + tag + texto[m.end():]


def wnd02(texto, nl):
    """Los cambios de la seleccion sobre el wnd02.xml que esta armando ventana_login.wnd02 (idempotente)."""
    texto = re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\r?\n' % (MARCA, MARCA), '', texto, flags=re.S)
    for wid, fondo in zip(FICHAS, FONDOS):
        texto = re.sub(r'(<window [^>]*\bid="%d"[^>]*?) icon="%d"' % (wid, ICONO_FICHA), r'\1', texto)
        texto = _attr(texto, wid, 'title', TITULO_FICHA)
        # La ULTIMA hija: el juego pinta las hijas de la ultima a la primera (la primera queda encima). Puesta la
        # primera tapaba los textos, el retrato y los botones (12/11/2026, en la 0.0.0.134).
        texto = re.sub(r'[ \t]*<child>%d</child>\r?\n' % fondo, '', texto)
        m = vl._ventana(texto, wid)
        sangria = re.search(r'\n([ \t]*)<child>', texto[m.end():]).group(1)
        cierre = texto.index('</window>', m.end())
        linea = texto.rindex('\n', 0, cierre) + 1                 # el principio de la linea del </window>
        texto = texto[:linea] + sangria + '<child>%d</child>' % fondo + nl + texto[linea:]
    for ids, caja in DISPOSICION.items():
        for wid in ids:
            m = vl._ventana(texto, wid)
            tag = re.sub(r'range="[^"]*"', 'range="%d,%d,%d,%d"' % caja, m.group(0), count=1)
            texto = texto[:m.start()] + tag + texto[m.end():]
    texto = _attr(texto, 2712, 'icon', ICONO_VOLVER)

    def linea(iid, n, f='normal', s='normal'):
        return '<icon id="%d" dir="\\log\\" normal="%s" focus="%s" down="%s" disable="normal" />' % (iid, n, f, s)
    texto = _icono(texto, 2534, linea(2534, 'aolat_sel_marca1, #16, aolat_sel_marca2'))
    texto = _icono(texto, 2728, linea(2728, 'aolat_sel_retrato'))
    texto = _icono(texto, 2734, linea(2734, 'aolat_sel_mini_n', 'aolat_sel_mini_f', 'aolat_sel_mini_s'))
    texto = _icono(texto, 2565, linea(2565, 'aolat_sel_menu'))
    texto = _icono(texto, 2501, linea(2501, 'nullshp', 'aolat_sel_opcion_f', 'aolat_sel_opcion_s'))
    bloque = '    <!-- %s -->%s' % (MARCA, nl)
    bloque += '    %s%s' % (linea(ICONO_FICHA, 'aolat_sel_ficha'), nl)
    bloque += '    %s%s' % (linea(ICONO_VOLVER, 'aolat_sel_volver_n', 'aolat_sel_volver_f', 'aolat_sel_volver_s'), nl)
    for fondo in FONDOS:
        bloque += ('    <window class="WND_CLASS_BASE" id="%d" range="0,0,%d,%d" icon="%d">%s'
                   '        <style wsVisible="" />%s    </window>%s' % (fondo, FW, FH, ICONO_FICHA, nl, nl, nl))
    bloque += '    <!-- /%s -->%s' % (MARCA, nl)
    fin = texto.rindex('</')
    return texto[:fin] + bloque + texto[fin:]


def wndtext02(texto):
    for wid in FICHAS:
        texto = re.sub(r'<window id="%d" title="[^"]*"/>' % wid, '<window id="%d" title="%s"/>' % (wid, TITULO_FICHA),
                       texto)
    return texto
