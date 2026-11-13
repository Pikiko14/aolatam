"""La creacion de personaje con la linea grafica del login nuevo (13/11/2026, "reharemos la pestana de creacion de
personaje, debe ser moderna y harmoniosa, redistribuye todo"; y luego "cambia la distribucion y los borders esos
grises, que se vea mas moderno y bonito").

Son dos ventanas de wnd02.xml, las dos WND_CLASS_DLG_1 (el marco suma 8 de ancho y 24 de alto al interior):
  * 2566 "Character Shape" (interior 486x274, log/w038_17): sexo, pelo, estatura, color de pelo y de piel;
  * 2548 "Character Info" (interior 362x251, log/w038_23): nombre, nacimiento, signo, grupo y lo opcional.
Su interior era un dibujo verde con ICON_ATTRIB_THEME (el cliente lo tine con el tema). Ahora es azul noche con
estrellas y tarjetas de borde dorado con su cabecera, sin tinte; los valores van en casillas hundidas con letra clara.

Lo que pinta el juego y aqui no se dibuja: las cabezas del pelo (lista 2581 y la imagen 2587 con las doce cabezas),
las muestras de color (2781/2782, imagenes detras de las listas 2575/2576) y el muneco (en la 2566 fijo hacia x 183,
y 98..178 del interior; en la 2548 a la derecha). Por eso la tarjeta del medio de la 2566 es su escenario: arriba el
sexo, a los lados las flechas de girar y abajo la estatura.

Los botones grises del juego (btn128/129 del sexo, 133/134 de las flechas, 135/136 de girar, 137 de las listas,
138/139 de atras/siguiente y el 1072 de terminar) se cambian por iconos propios con ids nuevos (ICONOS), sin tocar
sus archivos, que usan otras ventanas. Los marcos de lo elegido (w038_27/28, que comparte wnd05) igual: archivo propio.
Lo llama tools/ventana_login.py, que es quien escribe wnd02.xml.
"""
import random
import re

from PIL import Image, ImageDraw, ImageFilter

import ventana_login as vl
from icono_subasta import a_shp

MARCA = 'aolat creacion'
ORO, ORO_OSCURO = vl.ORO, vl.ORO_OSCURO
TEXTO_CLARO = 103
GENERO_W, GENERO_H, FLECHA, GIRO, NAV_W, NAV_H, LISTA = 42, 20, 16, 24, 30, 20, 14

# ---- Character Shape (2566) --------------------------------------------------------------------------------------
SW, SH = 486, 274
# tarjetas: (x0, y0, x1, y1, titulo)
TARJETAS_FORMA = (
    (5, 5, 131, 243, 'Hair'),
    (136, 5, 232, 243, 'Preview'),
    (237, 5, 481, 129, 'Hair Color'),
    (237, 134, 481, 243, 'Complexion'),
)
# id: (x, y, ancho, alto)
POS_FORMA = {
    2582: (1, 1, 1, 1), 2583: (1, 1, 1, 1), 2584: (1, 1, 1, 1), 2585: (1, 1, 1, 1), 2586: (1, 1, 1, 1),
    2567: (140, 30, GENERO_W, GENERO_H), 2568: (186, 30, GENERO_W, GENERO_H),
    2588: (139, 126, GIRO, GIRO), 2589: (205, 126, GIRO, GIRO),
    2569: (141, 214, FLECHA, FLECHA), 2570: (159, 215, 50, 14), 2571: (211, 214, FLECHA, FLECHA),
    2581: (15, 44, 106, 142), 2587: (17, 46, 102, 138),
    2572: (23, 203, FLECHA, FLECHA), 2573: (43, 204, 50, 14), 2574: (97, 203, FLECHA, FLECHA),
    2575: (246, 30, 226, 96), 2781: (246, 31, 1, 1),
    2576: (246, 160, 226, 70), 2782: (246, 161, 1, 1),
    2591: (414, 250, 1, 1), 2577: (0, 0, NAV_W, NAV_H), 2578: (36, 0, NAV_W, NAV_H),
}
OCULTAR_FORMA = (2582, 2583, 2584, 2585, 2586)      # sus titulos los lleva la cabecera de cada tarjeta
CASILLAS_FORMA = ((159, 215, 50, 14), (43, 204, 50, 14))   # estatura y pagina del pelo: el valor en casilla hundida
ROTULOS_FORMA = ((184, 200, 'Stature'),)

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
VALOR_X, VALOR_W = 48, 92                      # la casilla de cada valor (48..140); el boton de lista en 126
POS_INFO_ABAJO = {2613: (290, 228, 1, 1), 2563: (0, 0, NAV_W, NAV_H), 2564: (36, 0, NAV_W, NAV_H)}

# ---- los iconos nuevos ---------------------------------------------------------------------------------------------
ICONOS = {60480: 'aolat_crea_hombre', 60481: 'aolat_crea_hombre_si', 60482: 'aolat_crea_mujer',
          60483: 'aolat_crea_mujer_si', 60484: 'aolat_crea_izq', 60485: 'aolat_crea_der',
          60486: 'aolat_crea_giro_izq', 60487: 'aolat_crea_giro_der', 60488: 'aolat_crea_atras',
          60489: 'aolat_crea_sigue', 60490: 'aolat_crea_lista', 60491: 'aolat_crea_listo'}
SOLO_NORMAL = (60481, 60483)                   # lo elegido del sexo (atributo check): una sola imagen
# id de ventana: (icono, check o None)
ICONO_DE = {2567: (60480, 60481), 2568: (60482, 60483), 2569: (60484, None), 2572: (60484, None),
            2571: (60485, None), 2574: (60485, None), 2588: (60486, None), 2589: (60487, None),
            2577: (60488, None), 2578: (60489, None), 2563: (60488, None), 2564: (60491, None),
            2551: (60490, None), 2553: (60490, None), 2556: (60490, None), 2606: (60490, None),
            2608: (60490, None), 2610: (60490, None), 2612: (60490, None)}
# los marcos de lo elegido: icono de la lista -> (archivo, lado)
MARCOS_ELEGIDO = {2581: ('aolat_crea_sel34', 34), 2575: ('aolat_crea_sel18', 18)}


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
    ImageDraw.Draw(capa).rounded_rectangle((x0, y0, x1, y1), radius=8, fill=(8, 16, 46, 215))
    im.alpha_composite(capa)
    halo = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).rounded_rectangle((x0 - 1, y0 - 1, x1 + 1, y1 + 1), radius=9, outline=(110, 180, 255, 90),
                                           width=2)
    im.alpha_composite(halo.filter(ImageFilter.GaussianBlur(2)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, x1, y1), radius=8, outline=(176, 136, 60, 255))
    # la cabecera: una pastilla un poco mas clara con el titulo en oro y una linea dorada que se apaga a los lados
    d.rounded_rectangle((x0 + 3, y0 + 3, x1 - 3, y0 + 16), radius=6, fill=(28, 54, 124, 255))
    cx = (x0 + x1) // 2
    medio = max(1, (x1 - x0) // 2 - 8)
    for k in range(medio):
        a = max(0, 255 - k * 255 // medio)
        for x in (cx - k, cx + k):
            d.point((x, y0 + 18), fill=ORO + (a,))
    vl._rotulo(d, titulo, cx, y0 + 5, color=(255, 226, 140, 255), tam=10)


def _casilla(d, x, y, w, h=14):
    d.rounded_rectangle((x - 1, y - 1, x + w, y + h), radius=4, fill=(4, 8, 28, 255), outline=(120, 96, 40, 255))


def _marco(im):
    d = ImageDraw.Draw(im)
    w, h = im.size
    for k in range(w // 2 - 10):                                  # la franja de abajo: una linea que se apaga
        a = max(0, 220 - k * 220 // (w // 2 - 10))
        for x in (w // 2 - k, w // 2 + k):
            d.point((x, h - 27), fill=ORO_OSCURO + (a,))
    d.rectangle((0, 0, w - 1, h - 1), outline=ORO)
    d.rectangle((1, 1, w - 2, h - 2), outline=ORO_OSCURO)


def fondo_forma() -> Image.Image:
    im = _fondo(SW, SH, 2566)
    for t in TARJETAS_FORMA:
        _tarjeta(im, *t)
    d = ImageDraw.Draw(im)
    # las doce celdas del pelo (3x4 de 34 con 2 de hueco desde la lista), oscuras y con borde azul suave
    lx, ly = POS_FORMA[2581][:2]
    for fila in range(4):
        for col in range(3):
            x, y = lx + col * 36, ly + fila * 36
            d.rounded_rectangle((x, y, x + 33, y + 33), radius=5, fill=(16, 32, 80, 255), outline=(52, 84, 156, 255))
    # el escenario: un halo detras del muneco y un pedestal de luz a sus pies
    luz = Image.new('RGBA', im.size, (0, 0, 0, 0))
    dl = ImageDraw.Draw(luz)
    dl.ellipse((146, 70, 220, 170), fill=(90, 150, 255, 60))
    dl.ellipse((148, 166, 218, 190), fill=(130, 210, 255, 130))
    im.alpha_composite(luz.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(im)
    d.ellipse((154, 171, 212, 185), outline=(230, 196, 110, 255))
    d.ellipse((162, 174, 204, 182), outline=(150, 200, 255, 200))
    for x, y, w, h in CASILLAS_FORMA:
        _casilla(d, x, y, w, h)
    for cx, y, texto in ROTULOS_FORMA:
        vl._rotulo(d, texto, cx, y, color=(190, 210, 255, 255), tam=9)
    for x, y, w, h in ((246, 30, 226, 96), (246, 160, 226, 70)):
        d.rounded_rectangle((x - 4, y - 4, x + w + 2, y + h + 2), radius=6, fill=(10, 20, 56, 255),
                            outline=(52, 84, 156, 255))
    _marco(im)
    return im


def fondo_info() -> Image.Image:
    im = _fondo(IW, IH, 2548)
    for t in TARJETAS_INFO:
        _tarjeta(im, *t)
    d = ImageDraw.Draw(im)
    for y, _r, _valor, _b in FILAS_INFO_REQ + FILAS_INFO_OPC:
        if y == 50:                                # nacimiento: mes y dia, cada uno con su boton
            _casilla(d, 47, y, 28)
            _casilla(d, 95, y, 28)
        else:
            _casilla(d, VALOR_X - 1, y, VALOR_W + 2)
    # el texto de bienvenida en su recuadro y el suelo de los tres munecos
    d.rounded_rectangle((176, 22, 354, 94), radius=6, fill=(14, 28, 74, 255), outline=(52, 84, 156, 255))
    luz = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(luz).ellipse((186, 186, 346, 212), fill=(120, 200, 255, 90))
    im.alpha_composite(luz.filter(ImageFilter.GaussianBlur(7)))
    _marco(im)
    return im


# ---- los botones ---------------------------------------------------------------------------------------------------
def _cristal(w, h, estado, radio, oro=False):
    """El cuerpo de un boton: cristal azul (o dorado si esta elegido) con borde de oro y reflejo."""
    if oro:
        arriba, abajo = (255, 226, 140), (196, 132, 40)
    else:
        arriba, abajo = {'n': ((52, 104, 200), (14, 34, 104)), 'f': ((96, 170, 255), (30, 74, 180)),
                         's': ((14, 34, 104), (48, 100, 200))}[estado]
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    mascara = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w - 1, h - 1), radius=radio, fill=255)
    im.paste(vl._degradado(w, h, arriba, abajo), (0, 0), mascara)
    reflejo = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(reflejo).rounded_rectangle((2, 1, w - 3, h // 2), radius=max(1, radio - 2),
                                              fill=(255, 255, 255, 40 if estado != 's' else 12))
    im = Image.alpha_composite(im, reflejo)
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=radio,
                                         outline=(255, 240, 190) if oro else ORO, width=1)
    return im


def _simbolo(d, cx, cy, mujer, color):
    """El signo de Venus o de Marte, con trazo de 2 px."""
    r = 4
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=2)
    if mujer:
        d.line((cx, cy + r, cx, cy + r + 5), fill=color, width=2)
        d.line((cx - 3, cy + r + 3, cx + 3, cy + r + 3), fill=color, width=2)
    else:
        d.line((cx + 3, cy - 3, cx + 7, cy - 7), fill=color, width=2)
        d.line((cx + 3, cy - 7, cx + 7, cy - 7), fill=color, width=2)
        d.line((cx + 7, cy - 7, cx + 7, cy - 3), fill=color, width=2)


def _punta(d, cx, cy, tam, derecha, color):
    k = 1 if derecha else -1
    d.polygon(((cx - k * tam // 2, cy - tam), (cx + k * tam, cy), (cx - k * tam // 2, cy + tam)), fill=color)


def icono_genero(mujer, estado, elegido=False):
    im = _cristal(GENERO_W, GENERO_H, estado, 6, oro=elegido)
    color = (40, 24, 4, 255) if elegido else ((255, 170, 210, 255) if mujer else (150, 215, 255, 255))
    _simbolo(ImageDraw.Draw(im), GENERO_W // 2 - (0 if mujer else 2), GENERO_H // 2 - (3 if mujer else -1), mujer,
             color)
    return im


def icono_flecha(derecha, estado, lado=FLECHA):
    im = _cristal(lado, lado, estado, lado // 2)
    _punta(ImageDraw.Draw(im), lado // 2 + (1 if derecha else -1), lado // 2, max(3, lado // 5), derecha,
           (255, 236, 170, 255))
    return im


def icono_lista(estado):
    """La flecha de los desplegables: un cuadradito con un triangulo hacia abajo."""
    im = _cristal(LISTA, LISTA, estado, 4)
    c = (255, 236, 170, 255)
    ImageDraw.Draw(im).polygon(((3, 5), (LISTA - 4, 5), (LISTA // 2 - 0.5, LISTA - 4)), fill=c)
    return im


def icono_giro(derecha, estado):
    """Girar el muneco: un circulo con un arco y su punta."""
    im = _cristal(GIRO, GIRO, estado, GIRO // 2)
    d = ImageDraw.Draw(im)
    c = (255, 236, 170, 255)
    if derecha:
        d.arc((5, 5, GIRO - 6, GIRO - 6), 180, 360, fill=c, width=2)
        d.polygon(((GIRO - 10, 10), (GIRO - 3, 10), (GIRO - 6, 15)), fill=c)
    else:
        d.arc((5, 5, GIRO - 6, GIRO - 6), 180, 360, fill=c, width=2)
        d.polygon(((3, 10), (10, 10), (6, 15)), fill=c)
    return im


def icono_nav(derecha, estado):
    im = _cristal(NAV_W, NAV_H, estado, 6)
    d = ImageDraw.Draw(im)
    c = (255, 250, 230, 255)
    cx, cy = NAV_W // 2, NAV_H // 2
    d.line((cx - 6, cy, cx + 5, cy), fill=c, width=2)
    _punta(d, cx + (5 if derecha else -5), cy, 4, derecha, c)
    return im


def icono_listo(estado):
    """Terminar: la marca de verificacion en un boton dorado."""
    im = _cristal(NAV_W, NAV_H, estado, 6, oro=estado != 's')
    d = ImageDraw.Draw(im)
    c = (40, 24, 4, 255)
    d.line(((9, 10), (13, 14), (21, 5)), fill=c, width=2)
    return im


def marco_elegido(lado):
    """Lo elegido (una cabeza o un color): borde dorado de 2 px y un filo claro, el centro transparente."""
    im = Image.new('RGBA', (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, lado - 1, lado - 1), radius=5 if lado > 20 else 2, outline=(255, 206, 80, 255),
                        width=2)
    d.rounded_rectangle((2, 2, lado - 3, lado - 3), radius=3 if lado > 20 else 1, outline=(255, 248, 210, 255))
    return im


def imagenes():
    """{archivo: imagen} de todo lo nuevo de wnd01 (los botones con sus estados n, f y s)."""
    out = {}
    for e in 'nfs':
        out['aolat_crea_hombre_' + e] = icono_genero(False, e)
        out['aolat_crea_mujer_' + e] = icono_genero(True, e)
        out['aolat_crea_izq_' + e] = icono_flecha(False, e)
        out['aolat_crea_der_' + e] = icono_flecha(True, e)
        out['aolat_crea_giro_izq_' + e] = icono_giro(False, e)
        out['aolat_crea_giro_der_' + e] = icono_giro(True, e)
        out['aolat_crea_atras_' + e] = icono_nav(False, e)
        out['aolat_crea_sigue_' + e] = icono_nav(True, e)
        out['aolat_crea_lista_' + e] = icono_lista(e)
        out['aolat_crea_listo_' + e] = icono_listo(e)
    out['aolat_crea_hombre_si'] = icono_genero(False, 'n', elegido=True)
    out['aolat_crea_mujer_si'] = icono_genero(True, 'n', elegido=True)
    for archivo, lado in MARCOS_ELEGIDO.values():
        out[archivo] = marco_elegido(lado)
    return out


def dibujar():
    vl.LOG.mkdir(parents=True, exist_ok=True)
    vl.WND01.mkdir(parents=True, exist_ok=True)
    (vl.LOG / 'w038_17.shp').write_bytes(a_shp(fondo_forma()))
    (vl.LOG / 'w038_23.shp').write_bytes(a_shp(fondo_info()))
    for archivo, im in imagenes().items():
        (vl.WND01 / (archivo + '.shp')).write_bytes(a_shp(im))


# ---- wnd02.xml -----------------------------------------------------------------------------------------------------
def _rango(texto, wid, caja):
    m = vl._ventana(texto, wid)
    return texto[:m.start()] + re.sub(r'range="[^"]*"', 'range="%d,%d,%d,%d"' % caja, m.group(0), count=1) \
        + texto[m.end():]


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


def _icono_xml(icono, archivo, nl):
    barra = chr(92)
    if icono in SOLO_NORMAL:
        return '    <icon id="%d" dir="%swnd01%s" normal="%s" focus="normal" down="normal" disable="normal" />%s' % (
            icono, barra, barra, archivo, nl)
    return '    <icon id="%d" dir="%swnd01%s" normal="%s_n" focus="%s_f" down="%s_s" disable="%s_n" />%s' % (
        icono, barra, barra, archivo, archivo, archivo, archivo, nl)


def wnd02(texto, nl):
    texto = re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\r?\n' % (MARCA, MARCA), '', texto, flags=re.S)
    texto = _sin_tema(texto, 2566)
    texto = _sin_tema(texto, 2548)
    # Character Shape
    for wid, caja in POS_FORMA.items():
        texto = _rango(texto, wid, caja)
    for wid in OCULTAR_FORMA + OCULTAR_INFO:
        texto = _ocultar(texto, wid)
    # Character Info
    for wid, (x, y) in POS_INFO.items():
        texto = _mover(texto, wid, x, y)
    for y, rotulo, valor, boton in FILAS_INFO_REQ + FILAS_INFO_OPC:
        texto = _mover(texto, rotulo, 13, y + 1)
        if valor:
            texto = _mover(texto, valor, VALOR_X + (0 if valor == 2549 else 2), y + (0 if valor == 2549 else 1))
        if boton:
            texto = _rango(texto, boton, (126, y, LISTA, LISTA))
    # nacimiento: mes (2550 + boton 2551, "M" 2603) y dia (2552 + boton 2553, "D" 2602)
    for wid, x, dy in ((2550, 50, 1), (2603, 64, 1), (2552, 98, 1), (2602, 112, 1)):
        texto = _mover(texto, wid, x, 50 + dy)
    texto = _rango(texto, 2551, (76, 50, LISTA, LISTA))
    texto = _rango(texto, 2553, (124, 50, LISTA, LISTA))
    # las listas desplegables siguen a su fila: mes/dia (2560), signo... (2561) y grupo (2562)
    texto = _mover(texto, 2560, 45, 65)
    texto = _mover(texto, 2561, 45, 65)
    texto = _mover(texto, 2562, 45, 105)
    for wid, caja in POS_INFO_ABAJO.items():
        texto = _rango(texto, wid, caja)
    for wid in (2549, 2550, 2552, 2554, 2555, 2605, 2607, 2609, 2611, 2570, 2573):
        texto = _attr(texto, wid, 'fcolor', TEXTO_CLARO)
    # los iconos propios y los marcos dorados de lo elegido
    for wid, (icono, check) in ICONO_DE.items():
        texto = _attr(texto, wid, 'icon', icono)
        if check:
            texto = _attr(texto, wid, 'check', check)
    for wid, (archivo, _lado) in MARCOS_ELEGIDO.items():
        nuevo = '<icon id="%d" dir="%swnd01%s" normal="%s"' % (wid, chr(92), chr(92), archivo)
        texto = re.sub(r'<icon id="%d" dir="[^"]*" normal="[^"]*"' % wid, lambda _m: nuevo, texto, count=1)
    bloque = '    <!-- %s -->%s' % (MARCA, nl)
    for icono, archivo in ICONOS.items():
        bloque += _icono_xml(icono, archivo, nl)
    bloque += '    <!-- /%s -->%s' % (MARCA, nl)
    fin = texto.rindex('</')
    return texto[:fin] + bloque + texto[fin:]


def wndtext02(texto):
    """wndtext02.xml pisa los title de wnd02.xml: los rotulos que van dibujados, vacios."""
    for wid in OCULTAR_FORMA + OCULTAR_INFO:
        texto = re.sub(r'<window id="%d" title="[^"]*"/>' % wid, '<window id="%d" title=""/>' % wid, texto)
    return texto
