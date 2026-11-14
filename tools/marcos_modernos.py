"""Los avisos y los marcos grises, con la linea nueva (14/11/2026, "podemos rehacer las alertas por algo mas moderno y
cambiar esos bordes grises de ciertas pestanas").

Dos juegos de piezas de shape\\wnd01 que pinta el propio cliente:
  * w006_01..09 (iconos 10021..10029 de wnd01.xml): el panel gris oscuro de 9 piezas. Es el cuadro de aviso
    (window.msgbox: "Please enter your password.", "The character name is unavailable."...) y el fondo de las 78
    ventanas con puzzle9="10029". Son de 32 bits (tipo 4, BGRA con alfa de verdad): aqui pasan a azul noche
    translucido con ribete dorado y esquinas redondeadas. Esquinas 7x7, bordes 128x7 / 7x128, centro 120x120.
  * w001_01..09 (iconos 10011..10018): el marco gris de las DLG_1 (barra de titulo con el pin, lados, esquinas de
    abajo). Se conserva la forma de cada pieza y su gris pasa a la gama azul / oro de la creacion de personaje.

    python tools/marcos_modernos.py         (escribe parches/extras/shape/wnd01/w006_*.shp y w001_*.shp)
    python tools/generar_parche.py
"""
import pathlib
import struct
import sys
import zlib

from PIL import Image, ImageDraw

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
sys.path.insert(0, str(RAIZ / 'server'))
import fondos_interfaz as fi  # noqa: E402
import paks_cliente  # noqa: E402
from icono_subasta import a_shp  # noqa: E402

DESTINO = RAIZ / 'parches' / 'extras' / 'shape' / 'wnd01'
B = chr(92)

# ---- colores (los de ventana_login / creacion_personaje) ----------------------------------------------------------
FONDO = (12, 24, 58, 222)            # el relleno: azul noche, translucido como el gris de antes (242)
SOMBRA = (4, 8, 22, 235)             # el pixel de fuera
ORO = (222, 180, 92, 255)            # el ribete
BRILLO = (96, 140, 220, 150)         # la linea de luz de dentro
RADIO = 6

# Piezas del panel w006: nombre -> (recorte en el lienzo de 142x142)
L, C = 7, 128                         # lado del borde y tramo que se repite
PIEZAS_W006 = {
    'w006_01': (0, 0, L, L), 'w006_02': (L, 0, L + C, L), 'w006_03': (L + C, 0, 2 * L + C, L),
    'w006_04': (0, L, L, L + C), 'w006_05': (L + C, L, 2 * L + C, L + C),
    'w006_06': (0, L + C, L, 2 * L + C), 'w006_07': (L, L + C, L + C, 2 * L + C), 'w006_08': (L + C, L + C, 2 * L + C, 2 * L + C),
    'w006_09': (L + 4, L + 4, L + 4 + 120, L + 4 + 120),
}


# 14/11/2026, segunda version ("ese cuadrito no me cuadra que sea bonito, moderno"): casi opaco (se transparentaba
# el texto de detras), marco de cuatro lineas de fuera adentro y un fondo con alguna estrella muy tenue.
CAPAS = ((SOMBRA, RADIO), ((236, 196, 104, 255), RADIO), ((140, 100, 44, 255), RADIO - 1),
         ((70, 118, 210, 255), RADIO - 2), ((22, 42, 96, 250), RADIO - 3))
FONDO_PANEL = (14, 28, 66, 250)


def centro() -> Image.Image:
    """La pieza 09 (120 x 120, se repite): el azul con unas pocas estrellas tenues, sin costuras."""
    im = Image.new('RGBA', (120, 120), FONDO_PANEL)
    px = im.load()
    for x, y, luz in ((17, 23, 46), (64, 9, 30), (101, 41, 52), (38, 77, 34), (88, 96, 44), (8, 108, 28),
                      (113, 70, 26), (52, 50, 22)):
        r, g, b, a = px[x, y]
        px[x, y] = (min(255, r + luz), min(255, g + luz), min(255, b + luz), a)
    return im


def panel() -> Image.Image:
    """El panel entero (142 x 142) del que se recortan las nueve piezas."""
    lado = 2 * L + C
    im = Image.new('RGBA', (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, (color, radio) in enumerate(CAPAS):
        d.rounded_rectangle((i, i, lado - 1 - i, lado - 1 - i), radius=max(1, radio), fill=color)
    d.rectangle((len(CAPAS), len(CAPAS), lado - 1 - len(CAPAS), lado - 1 - len(CAPAS)), fill=FONDO_PANEL)
    return im


def a_shp32(im: Image.Image) -> bytes:
    """Un RGBA como .shp de 32 bits (tipo 4, BGRA), con el alfa tal cual: el formato de las w006 originales."""
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    filas = []
    for y in range(h):
        tramos, x = [], 0
        while x < w:
            if px[x, y][3] == 0:
                x += 1
                continue
            ini = x
            while x < w and px[x, y][3] > 0:
                x += 1
            tramos.append((ini, [px[i, y] for i in range(ini, x)]))
        filas.append(tramos)
    n_tramos = sum(len(t) + 1 for t in filas)
    ini_tramos = 80 + 4 * h
    ini_pixeles = ini_tramos + 8 * n_tramos
    tramos_b, pixeles, offs = bytearray(), bytearray(), []
    for tramos in filas:
        offs.append(ini_tramos + len(tramos_b))
        for x, colores in tramos:
            tramos_b += struct.pack('<HHI', len(colores), x, ini_pixeles + len(pixeles))
            for r, g, b, a in colores:
                pixeles += bytes((b, g, r, a))
        tramos_b += struct.pack('<HHI', 0, 0xFFFF, 0)
    cab = struct.pack('<4s19I', b'TLHS', 1, 4, 512, 0xFFFFFFFF, w, h, 0, 0, n_tramos, len(pixeles) // 4,
                      ini_pixeles, 0, 0, 0, 0, 0, 0, 0, 0)
    return cab + b''.join(struct.pack('<I', o) for o in offs) + bytes(tramos_b) + bytes(pixeles)


# ---- el marco w001 de las DLG_1: el mismo dibujo, otra gama ---------------------------------------------------------
# Luminancia del gris original -> color. Lo oscuro es el fondo de la barra y el bisel, lo claro las lineas de luz.
GAMA = ((0, (6, 12, 30)), (70, (16, 32, 78)), (120, (30, 58, 128)), (175, (84, 124, 196)), (215, (214, 170, 84)),
        (255, (250, 226, 150)))


def _gama(lum: int):
    for (l0, c0), (l1, c1) in zip(GAMA, GAMA[1:]):
        if lum <= l1:
            t = (lum - l0) / max(1, l1 - l0)
            return tuple(int(round(a + (b - a) * t)) for a, b in zip(c0, c1))
    return GAMA[-1][1]


def recolorear(im: Image.Image) -> Image.Image:
    out = im.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a:
                px[x, y] = _gama(int(0.299 * r + 0.587 * g + 0.114 * b)) + (a,)
    return out


def leer8(d: bytes) -> Image.Image:
    """Un .shp paletizado (tipo 2, el de las w001) a RGBA."""
    cab, bpp, filas, pal = fi.leer(d)
    colores = [struct.unpack_from('<H', pal, 2 * i)[0] for i in range(256)]
    rgb = [(((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31) for c in colores]
    im = Image.new('RGBA', (cab[5], cab[6]), (0, 0, 0, 0))
    px = im.load()
    for y, tramos in enumerate(filas):
        for x, datos in tramos:
            for i, v in enumerate(datos):
                px[x + i, y] = rgb[v] + (255,)
    return im


def originales(nombres):
    """Los .shp del cliente (el pak de numero mas alto, sus .bak sin parches nuestros), leyendo cada pak una vez."""
    buscados = {('shape' + B + 'wnd01' + B + n + '.shp').lower() for n in nombres}
    mejor = {}
    for pak in fi.CLIENTE.glob('*'):
        # update27 en adelante es nuestro parche (sin .bak): leerlo seria recolorear lo ya recoloreado en cada pasada.
        if pak.suffix.lower() != '.pak' or not -1 <= paks_cliente.numero(pak.name) < 27:
            continue
        fuente = pak.with_name(pak.name + '.bak')
        datos = (fuente if fuente.exists() else pak).read_bytes()
        num = paks_cliente.numero(pak.name)
        for n, _crc, cs, _us, off in paks_cliente._directorio(datos):
            k = n.lower()
            if k in buscados and (k not in mejor or num > mejor[k][0]):
                crudo = datos[off:off + cs]
                try:
                    crudo = zlib.decompress(crudo, -15)
                except zlib.error:
                    pass
                mejor[k] = (num, crudo)
    return {k.rsplit(B, 1)[-1][:-4]: v[1] for k, v in mejor.items()}


NOMBRES_W001 = ['w001_%02d' % i for i in range(1, 10)]

# ---- los botones viejos de check y X (iconos 1154 / 1155, shape\game\02\btn067_* y btn069_*, 26 x 18) -------------
# Los del aviso y los de confirmar de toda la interfaz (Store, Bulk Sell...). Con el cristal de la creacion de
# personaje: el check dorado como "terminar", la X en azul. Estados: n normal, f raton encima, d pulsado.
BOTON_W, BOTON_H = 26, 18
DESTINO_BOTONES = RAIZ / 'parches' / 'extras' / 'shape' / 'game' / '02'


def boton(cual: str, estado: str) -> Image.Image:
    import creacion_personaje as cp
    e = {'n': 'n', 'f': 'f', 'd': 's'}[estado]
    if cual == 'si':
        im = cp._cristal(BOTON_W, BOTON_H, e, 6, oro=True)
        # el dorado no cambia con el estado en _cristal: mas luz con el raton, mas oscuro pulsado
        factor = {'n': 1.0, 'f': 1.18, 'd': 0.78}[estado]
        if factor != 1.0:
            from PIL import ImageEnhance
            rgb = ImageEnhance.Brightness(im.convert('RGB')).enhance(factor)
            rgb.putalpha(im.getchannel('A'))
            im = rgb
        d = ImageDraw.Draw(im)
        d.line(((8, 9), (11, 12), (18, 5)), fill=(40, 24, 4, 255), width=2)
    else:
        im = cp._cristal(BOTON_W, BOTON_H, e, 6)
        d = ImageDraw.Draw(im)
        c = (255, 236, 170, 255)
        d.line(((9, 5), (16, 12)), fill=c, width=2)
        d.line(((16, 5), (9, 12)), fill=c, width=2)
    if estado == 'd':                            # pulsado: medio pixel abajo, como hundido
        im = im.transform(im.size, Image.AFFINE, (1, 0, 0, 0, 1, -1))
    return im


def botones():
    res = {}
    for cual, archivo in (('si', 'btn067'), ('no', 'btn069')):
        for estado in ('n', 'f', 'd'):
            im = boton(cual, estado)
            res['%s_%s' % (archivo, estado)] = (im, a_shp(im))
    return res


# ---- los botones de la barra de titulo de las DLG_1 (14 x 14, shape\wnd01) -----------------------------------------
# btn001 chincheta, btn002 cerrar, btn003 ayuda, btn004 bloquear, btn149 minimizar. Eran grises y naranjas al pulsar.
TITULO = 14


def boton_titulo(cual: str, estado: str) -> Image.Image:
    import creacion_personaje as cp
    e = {'n': 'n', 'f': 'f', 'd': 's'}[estado]
    im = cp._cristal(TITULO, TITULO, e, 4, oro=(estado == 'd'))
    d = ImageDraw.Draw(im)
    c = (40, 24, 4, 255) if estado == 'd' else (255, 236, 170, 255)
    if cual == 'btn002':                         # cerrar
        d.line(((4, 4), (9, 9)), fill=c, width=2)
        d.line(((9, 4), (4, 9)), fill=c, width=2)
    elif cual == 'btn149':                       # minimizar
        d.line(((4, 9), (9, 9)), fill=c, width=2)
    elif cual == 'btn003':                       # ayuda: un "?"
        d.arc((4, 2, 9, 7), 180, 90, fill=c, width=1)
        d.line(((7, 7), (7, 8)), fill=c, width=1)
        d.point((7, 10), fill=c)
    elif cual == 'btn004':                       # bloquear: candado
        d.arc((4, 2, 9, 8), 180, 360, fill=c, width=1)
        d.line(((4, 5), (4, 6)), fill=c)
        d.line(((9, 5), (9, 6)), fill=c)
        d.rectangle((3, 6, 10, 10), fill=c)
    elif cual == 'ordenar':                      # ordenar la mochila: barras de mayor a menor
        for y, x1 in ((3, 10), (6, 8), (9, 6)):
            d.line(((3, y), (x1, y)), fill=c, width=2)
    else:                                        # btn001 chincheta
        d.ellipse((5, 2, 10, 7), fill=c)
        d.line(((6, 7), (3, 10)), fill=c, width=1)
    return im


def botones_titulo():
    res = {}
    for cual in ('btn001', 'btn002', 'btn003', 'btn004', 'btn149'):
        for estado in ('n', 'f', 'd'):
            im = boton_titulo(cual, estado)
            res['%s_%s' % (cual, estado)] = (im, a_shp(im))
    return res


# ---- los botones de la mochila (Prop 3031: btn042 borrar, btn218 bolsa de moda, btn115 mochila, btn043 equipo,
# btn044 comercio, btn045 puesto; btn041 el del almacen, 17 x 17) y el de ordenar del titulo -------------------------
# "cambia los botones del backpack incluyendo el de filtro por unos acordes a los nuevos" (14/11/2026). El dibujo es
# el del original (lo casi blanco dentro del marco gris) sobre el cristal de los demas: crema en azul, oscuro en oro
# al pulsar.
BOTONES_MOCHILA = ('btn041', 'btn042', 'btn043', 'btn044', 'btn045', 'btn115', 'btn218')
# "lo mismo en el angel baby y en el item mall" (14/11/2026). Son los botones grises de toda la interfaz:
# btn095 (43 x 18: Set, Check, Add, Update, Buy, Gift, Try, Delete), btn111 (55 x 18: pestanas del Mall y Reset),
# btn178 (81 x 18: Add Favorite), btn089 (47 x 16: pestanas de Angel Baby), btn112 (70 x 18: Backpack, Deposit...),
# btn093 (la flecha), btn090 / btn091 (paginas) y btn077 (desplegable). El _d (pulsado o pestana elegida) en oro.
BOTONES_VENTANAS = ('btn095', 'btn111', 'btn178', 'btn089', 'btn112', 'btn093', 'btn090', 'btn091', 'btn077')


def leer16(d: bytes) -> Image.Image:
    """Un .shp de tipo 2 sin paleta (2 bytes RGB565 por pixel, cab[3] = 512), como los botones de la mochila."""
    cab = struct.unpack_from('<4s19I', d)
    w, h = cab[5], cab[6]
    offs = struct.unpack_from('<%dI' % h, d, 80)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    px = im.load()
    for y in range(h):
        p = offs[y]
        while True:
            n, x, src = struct.unpack_from('<HHI', d, p)
            p += 8
            if x == 0xFFFF:
                break
            for i in range(n):
                c = struct.unpack_from('<H', d, src + 2 * i)[0]
                px[x + i, y] = (((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31, 255)
    return im


def leer_cualquiera(d: bytes) -> Image.Image:
    cab = struct.unpack_from('<4s19I', d)
    if cab[2] == 4:                              # indice de la paleta + alfa
        import parche_venta_masiva as pvm
        return pvm.leer_indice_alfa(d)
    return leer16(d) if cab[16] == 0 else leer8(d)   # sin paleta: RGB565 directo


def glifo(im: Image.Image, borde: int = 2):
    """Los pixeles del dibujo: lo casi blanco, sin el marco de fuera."""
    px = im.load()
    puntos = []
    for y in range(borde, im.height - borde):
        for x in range(borde, im.width - borde):
            r, g, b, a = px[x, y]
            if a and 0.299 * r + 0.587 * g + 0.114 * b > 215:
                puntos.append((x, y))
    return puntos


# ---- iconos nuevos para los botones de la mochila ("los iconos los puedes cambiar por unos mas modernos??",
# 14/11/2026). Se dibujan a 4x con trazo redondeado y se reducen con suavizado: lineas finas, sin pixel duro.
ESCALA = 4


def _icono_almacen(d, w, h, c):       # btn041: un almacen (tejado y puerta de persiana)
    s = ESCALA
    d.polygon(((2 * s, 7 * s), (w * s // 2, 2 * s), (w * s - 2 * s, 7 * s)), fill=c)
    d.rectangle((4 * s, 7 * s, w * s - 4 * s, h * s - 3 * s), outline=c, width=s + s // 2)
    for y in (10, 12):
        d.line((6 * s, y * s, w * s - 6 * s, y * s), fill=c, width=s)


def _icono_papelera(d, w, h, c):      # btn042: papelera
    s, cx = ESCALA, w * ESCALA // 2
    d.rounded_rectangle((cx - 5 * s, 4 * s, cx + 5 * s, 5 * s + s // 2), radius=s // 2, fill=c)
    d.rectangle((cx - 2 * s, 2 * s + s // 2, cx + 2 * s, 4 * s), outline=c, width=s)
    d.polygon(((cx - 4 * s, 6 * s + s // 2), (cx + 4 * s, 6 * s + s // 2), (cx + 3 * s, 15 * s), (cx - 3 * s, 15 * s)),
              outline=c, width=s + s // 2)
    for x in (-1, 1):
        d.line((cx + x * s * 3 // 2, 8 * s + s // 2, cx + x * s * 3 // 2, 13 * s), fill=c, width=s)


def _icono_percha(d, w, h, c):        # btn218: percha (moda, cartas, muebles, burbujas)
    s, cx = ESCALA, w * ESCALA // 2
    d.arc((cx - 2 * s, 2 * s, cx + 2 * s, 6 * s), 180, 400, fill=c, width=s + s // 2)
    d.line((cx, 6 * s, cx, 8 * s), fill=c, width=s + s // 2)
    d.line((cx, 8 * s, cx - 8 * s, 13 * s), fill=c, width=s + s // 2)
    d.line((cx, 8 * s, cx + 8 * s, 13 * s), fill=c, width=s + s // 2)
    d.line((cx - 8 * s, 13 * s, cx + 8 * s, 13 * s), fill=c, width=s + s // 2)


def _icono_mochila(d, w, h, c):       # btn115: mochila
    s, cx = ESCALA, w * ESCALA // 2
    d.arc((cx - 3 * s, 1 * s + s // 2, cx + 3 * s, 6 * s), 180, 360, fill=c, width=s + s // 2)
    d.rounded_rectangle((cx - 5 * s, 4 * s, cx + 5 * s, 15 * s), radius=3 * s, outline=c, width=s + s // 2)
    d.rounded_rectangle((cx - 3 * s, 9 * s, cx + 3 * s, 13 * s), radius=s, outline=c, width=s)
    d.line((cx - 3 * s, 11 * s, cx + 3 * s, 11 * s), fill=c, width=s)


def _icono_escudo(d, w, h, c):        # btn043: equipo (escudo con una espada)
    s, cx = ESCALA, w * ESCALA // 2
    d.polygon(((cx - 5 * s, 3 * s), (cx + 5 * s, 3 * s), (cx + 5 * s, 9 * s), (cx, 15 * s + s // 2), (cx - 5 * s, 9 * s)),
              outline=c, width=s + s // 2)
    d.line((cx, 5 * s, cx, 12 * s), fill=c, width=s)
    d.line((cx - 2 * s, 7 * s, cx + 2 * s, 7 * s), fill=c, width=s)


def _icono_comercio(d, w, h, c):      # btn044: comercio (dos flechas que se cruzan)
    s, cx = ESCALA, w * ESCALA // 2
    for y, k in ((6, 1), (12, -1)):
        x0, x1 = cx - 6 * s * k, cx + 6 * s * k
        d.line((x0, y * s, x1, y * s), fill=c, width=s + s // 2)
        d.polygon(((x1 + k * s, y * s), (x1 - k * 3 * s, y * s - 3 * s), (x1 - k * 3 * s, y * s + 3 * s)), fill=c)


def _icono_puesto(d, w, h, c):        # btn045: puesto (toldo y mostrador)
    s, cx = ESCALA, w * ESCALA // 2
    d.polygon(((cx - 8 * s, 6 * s), (cx - 6 * s, 2 * s), (cx + 6 * s, 2 * s), (cx + 8 * s, 6 * s)), fill=c)
    for i in range(4):
        x = cx - 8 * s + i * 4 * s
        d.chord((x, 4 * s, x + 4 * s, 8 * s), 0, 180, fill=c)
    d.line((cx - 6 * s, 8 * s, cx - 6 * s, 15 * s), fill=c, width=s)
    d.line((cx + 6 * s, 8 * s, cx + 6 * s, 15 * s), fill=c, width=s)
    d.rounded_rectangle((cx - 8 * s, 11 * s, cx + 8 * s, 15 * s), radius=s, fill=c)


ICONOS_NUEVOS = {'btn041': _icono_almacen, 'btn042': _icono_papelera, 'btn218': _icono_percha,
                 'btn115': _icono_mochila, 'btn043': _icono_escudo, 'btn044': _icono_comercio,
                 'btn045': _icono_puesto}


def icono_nuevo(cual: str, w: int, h: int, color) -> Image.Image:
    grande = Image.new('L', (w * ESCALA, h * ESCALA), 0)
    ICONOS_NUEVOS[cual](ImageDraw.Draw(grande), w, h, 255)
    alfa = grande.resize((w, h), Image.LANCZOS)
    im = Image.new('RGBA', (w, h), color[:3] + (0,))
    im.putalpha(alfa.point(lambda a: a * color[3] // 255))
    return im


def boton_con_glifo(puntos, w: int, h: int, estado: str, cual: str = '') -> Image.Image:
    import creacion_personaje as cp
    e = {'n': 'n', 'f': 'f', 'd': 's', 'b': 'n'}[estado]
    im = cp._cristal(w, h, e, 5 if w > 16 else 4, oro=(estado == 'd'))
    c = (40, 24, 4, 255) if estado == 'd' else (255, 236, 170, 255)
    if cual in ICONOS_NUEVOS:
        im.alpha_composite(icono_nuevo(cual, w, h, c))
    else:
        px = im.load()
        for x, y in puntos:
            px[x, y] = c
    if estado == 'b':
        # apagado (el del almacen lejos del almacen): el mismo cristal azul, mas oscuro; en gris parecia el viejo
        # ("aca falto cambiar", 14/11/2026)
        from PIL import ImageEnhance
        rgb = ImageEnhance.Brightness(im.convert('RGB')).enhance(0.62)
        rgb.putalpha(im.getchannel('A'))
        im = rgb
    return im


def botones_mochila():
    todos = BOTONES_MOCHILA + BOTONES_VENTANAS
    orig = originales(['%s_%s' % (b, e) for b in todos for e in 'nb'])
    res = {}
    for b in todos:
        base = leer_cualquiera(orig['%s_n' % b])
        puntos = glifo(base)
        for estado in ('n', 'f', 'd') + (('b',) if '%s_b' % b in orig else ()):
            im = boton_con_glifo(puntos, base.width, base.height, estado, b)
            res['%s_%s' % (b, estado)] = (im, a_shp(im))
    for estado in 'nfd':
        im = boton_titulo('ordenar', estado)
        res['aolat_ordenar_%s' % estado] = (im, a_shp(im))
    return res


def piezas():
    """{nombre: (imagen, bytes del .shp)} de las 18 piezas de marco nuevas."""
    res = {}
    lienzo = panel()
    for nombre, caja in PIEZAS_W006.items():
        if nombre == 'w006_09':
            im = centro()
        else:
            im = lienzo.crop(caja)
        res[nombre] = (im, a_shp32(im))
    orig = originales(NOMBRES_W001)
    for nombre in NOMBRES_W001:
        im = recolorear(leer8(orig[nombre]))
        res[nombre] = (im, a_shp(im))
    return res


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nombre, (_im, datos) in piezas().items():
        (DESTINO / (nombre + '.shp')).write_bytes(datos)
        print(nombre, len(datos), 'bytes')
    DESTINO_BOTONES.mkdir(parents=True, exist_ok=True)
    for nombre, (_im, datos) in botones().items():
        # El check y la X estan dos veces: \game\02\ (iconos 1154/1155) y \wnd01\ (10006/10007, los del aviso).
        (DESTINO_BOTONES / (nombre + '.shp')).write_bytes(datos)
        (DESTINO / (nombre + '.shp')).write_bytes(datos)
        print(nombre, len(datos), 'bytes')
    for nombre, (_im, datos) in botones_titulo().items():
        (DESTINO / (nombre + '.shp')).write_bytes(datos)
        print(nombre, len(datos), 'bytes')
    for nombre, (_im, datos) in botones_mochila().items():
        (DESTINO / (nombre + '.shp')).write_bytes(datos)
        if nombre.startswith('btn042'):          # el de borrar del Prop es el icono 1157, en game/02
            (DESTINO_BOTONES / (nombre + '.shp')).write_bytes(datos)
        print(nombre, len(datos), 'bytes')


if __name__ == '__main__':
    main()
