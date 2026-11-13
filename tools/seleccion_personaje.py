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
FW, FH = 189, 426                        # la ficha entera (la ventana 2713..2715): ya no es un DLG_1 con marco
ICONO_FICHA, ICONO_VOLVER = 60465, 60466
FICHAS = (2713, 2714, 2715)
# 12/11/2026, "distribuyelo de otra forma, esas 3 columnas se ven feas, debe verse diferente al juego original".
# El juego pone las tres fichas el solo, en fila (angel.dat 0x4bfbfd: x = (ancho-800)/2 + 25 + 209*i,
# y = (alto-600)/2 + 140) y al personaje en su sitio fijo: eso no se toca. Lo que cambia es que ya no son columnas:
# la ficha pasa a WND_CLASS_BASE (sin marco ni barra de titulo) con fondo transparente, y en ella solo hay
#   una placa flotante compacta arriba: retrato, nivel en pastilla, bando, Set / Face, el nombre y una tabla corta;
#   y abajo un pedestal de luz donde se para el personaje, sobre el paisaje.
# Con BASE las hijas van desde la esquina de la ventana (con el DLG_1 iban desde el interior, 4,20 mas adentro).
PLACA = (4, 22, FW - 5, 214)
RETRATO = (12, 30)
EMBLEMA = (158, 26, 22)                  # el emblema del bando: lo pinta la ficha misma hacia x 142..174, y 5..45;
                                         # la placa lleva ahi un hueco redondo (transparente) con su aro
COL_X, COL_W = 78, 62
LV_Y, BANDO_Y, BOTONES_Y = 36, 54, 72
NOMBRE_Y, SITIO_Y = 100, 117
STATS_Y = [138 + 14 * i for i in range(5)]
# Cada hija de la ficha: (las tres ids, una por ficha) -> x, y, ancho, alto
DISPOSICION = {
    (2534, 2535, 2536): (0, 0, FW, FH),                              # la marca de la elegida (y el clic) cubre todo
    (2728, 2729, 2730): (RETRATO[0], RETRATO[1], 60, 60),            # aro del retrato
    (2740, 2741, 2742): (RETRATO[0] + 5, RETRATO[1] + 5, 50, 50),    # la cara
    (2719, 2720, 2721): (COL_X, LV_Y, COL_W, 14),                   # LV
    (2722, 2723, 2724): (COL_X, BANDO_Y, COL_W, 14),                # bando
    (2731, 2732, 2733): (COL_X, BOTONES_Y, 31, 17),                 # Set
    (2734, 2735, 2736): (COL_X + 33, BOTONES_Y, 31, 17),            # Face
    (2716, 2717, 2718): (14, NOMBRE_Y, FW - 28, 14),                # nombre
    (2725, 2726, 2727): (14, SITIO_Y, FW - 28, 14),                 # sitio
    (2757, 2758, 2759): (14, STATS_Y[0], 24, 74),                   # rotulos Title..Sign
    (2763, 2764, 2765): (46, STATS_Y[0], 1, 1),
    (2766, 2767, 2768): (46, STATS_Y[1], 1, 1),
    (2769, 2770, 2771): (46, STATS_Y[2], 1, 1),
    (2772, 2773, 2774): (46, STATS_Y[3], 1, 1),
    (2775, 2776, 2777): (46, STATS_Y[4], 1, 1),
    (2760, 2761, 2762): (104, STATS_Y[4] + 1, 1, 1),                # B.T.
    (2778, 2779, 2780): (138, STATS_Y[4] + 1, 1, 1),                # su valor
    (2783, 2784, 2785): (47, 228, 94, 28),                          # Change name (solo si hace falta)
    (2786, 2787, 2788): (47, 260, 94, 28),                          # Edit guild name
}
# El fondo es el icono de la propia ficha (BASE): una BASE sin icono pinta la textura verde del tema ("y lo verde,
# quita todo indicio del selector antiguo"). Antes iba en una hija aparte (60470..60472), que ya no hace falta.
FONDOS = (60470, 60471, 60472)
TITULO_FICHA = 'Adventurer'
PIES = (94, 404)                         # donde apoya el personaje (medido en la captura)
# EL MENU (2565): era una columna a la derecha; ahora es una barra horizontal centrada bajo las fichas (su sitio lo
# pone angel.dat: tools/seleccion_angel_dat.py, MENU_X / MENU_Y). Las opciones, de 98x17, en fila; las que se turnan
# comparten hueco (Delete / Recover, Set PIN / Change PIN).
MW, MH = 580, 30
OPCION_Y = 7
OPCIONES_X = (8, 112, 216, 320, 424)     # Enter, Create, Delete/Recover, Set/Change PIN, Delete PIN
VOLVER = (26, 18)
VOLVER_XY = (540, 6)
MENU_DISPOSICION = {
    (2708,): (OPCIONES_X[0], OPCION_Y, 98, 17),
    (2709,): (OPCIONES_X[1], OPCION_Y, 98, 17),
    (2710, 2711): (OPCIONES_X[2], OPCION_Y, 98, 17),
    (2501, 2502): (OPCIONES_X[3], OPCION_Y, 98, 17),
    (2503,): (OPCIONES_X[4], OPCION_Y, 98, 17),
    (2712,): VOLVER_XY + VOLVER,
    (2565,): (0, 0, MW, MH),
}

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


def _pedestal(d, px, py, aro):
    d.ellipse((px - 62, py - 13, px + 62, py + 13), fill=_rgba(FONDO_ABAJO), outline=_rgba(LINEA))
    d.ellipse((px - 56, py - 10, px + 56, py + 10), fill=_rgba(SUPERFICIE_2), outline=_rgba(aro))
    d.ellipse((px - 40, py - 6, px + 40, py + 6), outline=_rgba(ACENTO_OSCURO))
    d.ellipse((px - 20, py - 3, px + 20, py + 3), fill=_rgba(SUPERFICIE), outline=_rgba(ACENTO_OSCURO))


def ficha() -> Image.Image:
    """La ficha (189x426, transparente salvo la placa y el pedestal): ver DISPOSICION."""
    im = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    # LA PLACA: pizarra con esquinas redondeadas, borde de 1 px y la barra de acento arriba
    x0, y0, x1, y1 = PLACA
    mascara = Image.new('L', im.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle(PLACA, radius=10, fill=255)
    im.paste(vl._degradado(FW, FH, FONDO_ARRIBA, FONDO_ABAJO), (0, 0), mascara)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(PLACA, radius=10, outline=_rgba(LINEA))
    d.rounded_rectangle((x0 + 24, y0, x1 - 24, y0 + 2), radius=1, fill=_rgba(ACENTO))
    # el retrato y el hueco del emblema del bando
    x, y = RETRATO
    d.ellipse((x, y, x + 59, y + 59), fill=_rgba(SUPERFICIE_2))
    cx, cy, r = EMBLEMA
    d.ellipse((cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3), fill=_rgba(FONDO_ARRIBA), outline=_rgba(LINEA))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=_rgba(ACENTO_OSCURO), width=2)
    hueco = Image.new('L', im.size, 255)
    ImageDraw.Draw(hueco).ellipse((cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2), fill=0)
    im.putalpha(Image.composite(im.getchannel('A'), Image.new('L', im.size, 0), hueco))
    d = ImageDraw.Draw(im)
    # el nivel en pastilla y el bando sobre una linea tenue
    im.alpha_composite(_pastilla(COL_W, 15, ACENTO_OSCURO), (COL_X, LV_Y - 1))
    d = ImageDraw.Draw(im)
    d.line((COL_X + 4, BANDO_Y + 14, COL_X + COL_W - 4, BANDO_Y + 14), fill=_rgba(LINEA))
    # el nombre con su subrayado de acento y el sitio debajo
    d.line((x0 + 10, NOMBRE_Y - 6, x1 - 10, NOMBRE_Y - 6), fill=_rgba(LINEA))
    d.rectangle((FW // 2 - 14, NOMBRE_Y + 14, FW // 2 + 13, NOMBRE_Y + 15), fill=_rgba(ACENTO))
    # la tabla corta
    t0, t1 = STATS_Y[0] - 3, STATS_Y[-1] + 16
    d.rounded_rectangle((x0 + 6, t0, x1 - 6, t1), radius=6, fill=_rgba(SUPERFICIE), outline=_rgba(LINEA))
    for yy in STATS_Y[1:]:
        d.line((x0 + 12, yy - 1, x1 - 12, yy - 1), fill=_rgba(SUPERFICIE_2))
    # una pestana bajo la placa que apunta al personaje
    cx = FW // 2
    d.polygon(((cx - 8, y1), (cx + 8, y1), (cx, y1 + 7)), fill=_rgba(FONDO_ABAJO), outline=_rgba(LINEA))
    d.line((cx - 7, y1, cx + 7, y1), fill=_rgba(FONDO_ABAJO))
    # EL PEDESTAL, sobre el paisaje
    _pedestal(d, PIES[0], PIES[1], ACENTO_OSCURO)
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
    """La ficha elegida (189x426, desde la esquina de la ficha): la placa con contorno de acento y el pedestal
    encendido, con un aro de luz que se abre en el segundo fotograma (late)."""
    im = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(PLACA, radius=10, outline=_rgba(ACENTO), width=2)
    px, py = PIES
    _pedestal(d, px, py, ACENTO)
    d.ellipse((px - 40, py - 6, px + 40, py + 6), outline=_rgba(ACENTO))
    k = (4, 9)[fotograma]
    d.ellipse((px - 62 - k, py - 13 - k // 2, px + 62 + k, py + 13 + k // 2), outline=_rgba(ACENTO))
    return im


def menu() -> Image.Image:
    """La barra (580x30): pizarra con esquinas redondeadas, borde de 1 px, barra de acento arriba y un separador fino
    entre opcion y opcion; la flecha de volver, aparte a la derecha."""
    im = Image.new('RGBA', (MW, MH), (0, 0, 0, 0))
    mascara = Image.new('L', im.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, MW - 1, MH - 1), radius=8, fill=255)
    im.paste(vl._degradado(MW, MH, FONDO_ARRIBA, FONDO_ABAJO), (0, 0), mascara)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, MW - 1, MH - 1), radius=8, outline=_rgba(LINEA))
    d.rounded_rectangle((40, 0, MW - 41, 1), radius=1, fill=_rgba(ACENTO))
    for x in OPCIONES_X[1:]:
        d.line((x - 3, 8, x - 3, MH - 9), fill=_rgba(LINEA))
    d.line((VOLVER_XY[0] - 7, 6, VOLVER_XY[0] - 7, MH - 7), fill=_rgba(LINEA))
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
        m = vl._ventana(texto, wid)
        texto = texto[:m.start()] + m.group(0).replace('WND_CLASS_DLG_1', 'WND_CLASS_BASE') + texto[m.end():]
        texto = _attr(texto, wid, 'title', TITULO_FICHA)
        texto = re.sub(r'[ \t]*<child>%d</child>\r?\n' % fondo, '', texto)
        texto = _attr(texto, wid, 'icon', ICONO_FICHA)
    for ids, caja in list(DISPOSICION.items()) + list(MENU_DISPOSICION.items()):
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
    bloque += '    <!-- /%s -->%s' % (MARCA, nl)
    fin = texto.rindex('</')
    return texto[:fin] + bloque + texto[fin:]


def wndtext02(texto):
    for wid in FICHAS:
        texto = re.sub(r'<window id="%d" title="[^"]*"/>' % wid, '<window id="%d" title="%s"/>' % (wid, TITULO_FICHA),
                       texto)
    return texto
