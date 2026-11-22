"""Las ventanas de Pet Defense (21/11/2026), como las de la Torre de Babel y las raids (tools/ventana_torre.py): cada
ventana es un DLG_1 con su barra de titulo y el contenido es un fondo propio en una hija BASE con icono, la ULTIMA de la
lista (el juego pinta las hijas de la ultima a la primera); los textos que cambian son STATIC que llena el Lua
(server/lua/pet_defense.lua) y los que no, van dibujados. Los .shp solo tienen transparencia de todo o nada.

"Utiliza mas pet, hay muchos en su fase a b c; que no se seleccione al iniciar, que tengamos posiciones para ello, se
clickeen y se pueda seleccionar cual quiero poner ahi" (21/11/2026):

  * MENU (59280): el banner, la galeria de las torres (hasta 12: retrato de la fase b, nombre y coste; el clic ensena
    su papel y numeros) y Start. Ya no se elige nada al empezar.
  * ELEGIR (59350): al pulsar una piedra libre, las mismas mascotas como botones con su coste; la que se pulsa se pone.
  * TORRE (59380): al pulsar la piedra de una torre, su ficha: el retrato de su fase (a, b o c segun el nivel), nivel,
    numeros, lo que da el siguiente nivel y su coste, Upgrade y Sell.
  * HUD (59330): vida del cristal, oleada, Essence, aviso, Next wave now (en la pausa) y Leave.
  * FIN (59340): VICTORY o DEFEAT, cuatro lineas, Play again y Leave.

Los retratos salen de las propias mascotas de plantillas/pet_defense.json ('sprites': fase a, b, c): su grafico (圖號1
de pet.xml) es el shape\\mon\\...\\<grafico>_Wait.spr del cliente. Los de tipo ARGB4444 que el cliente tine (los elfos
de fase a) se cambian por la fase siguiente.

Ids: ventanas y textos en 59280..59390, iconos y colores en 59701..59783 (huecos libres entre los que el cliente ya
carga). El boton de la barra es el 59005, a la izquierda del de AOF Raid (59004).

    python tools/ventana_pet_defense.py [--vista CARPETA]
"""
import json
import pathlib
import re
import struct
import sys
import zlib

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
sys.path.insert(0, str(RAIZ / 'server'))
from icono_subasta import ALTO, ANCHO, SALIDA, a_shp, al_estilo_nativo  # noqa: E402

ENG = RAIZ / 'parches' / 'extras' / 'setting' / 'eng'
CONFIG = RAIZ / 'server' / 'plantillas' / 'pet_defense.json'
MARCA = 'aolat pet defense'
MARCO_X, MARCO_Y, MARCO_ABAJO = 4, 20, 4
N_MAX = 12                     # torres que caben en la galeria y en la ventana de elegir (6 x 2)

# ---------------------------------------------------------------------------------------------- ids
V_MENU, M_SUB, M_INFO, M_ESTADO, M_EMPEZAR, M_FONDO = 59280, 59281, 59282, 59283, 59284, 59285
M_ARTE, M_NOMBRE, M_COSTE = 59286, 59298, 59310                              # + 0..11
V_HUD, H_CRISTAL, H_OLEADA, H_ESSENCE, H_AVISO, H_SIGUIENTE, H_SALIR, H_FONDO = range(59330, 59338)
V_FIN, F_TITULO, F_LINEA, F_OTRA, F_SALIR, F_FONDO = 59340, 59341, 59342, 59346, 59347, 59348
V_ELEGIR, E_TITULO, E_ESTADO, E_FONDO, E_OPCION, E_COSTE = 59350, 59351, 59352, 59353, 59354, 59366   # + 0..11
V_TORRE, T_RETRATO, T_NOMBRE, T_NIVEL, T_STATS, T_SIGUIENTE, T_MEJORAR, T_VENDER, T_ESTADO, T_FONDO = range(59380, 59390)
I_M_FONDO, I_H_FONDO, I_F_FONDO, I_VICTORIA, I_DERROTA, I_E_FONDO, I_T_FONDO = range(59701, 59708)
I_EMPEZAR, I_SIGUIENTE, I_SALIR, I_OTRA, I_F_SALIR, I_MEJORAR, I_VENDER = range(59708, 59715)
I_CARTA, I_OPCION, I_RETRATO = 59716, 59728, 59740          # + i (0..11); retrato + 3*i + fase (0..2)
C_ACENTO, C_TENUE, C_ORO, C_ROJO = 59780, 59781, 59782, 59783
COLORES = {C_ACENTO: (110, 231, 183), C_TENUE: (148, 163, 184), C_ORO: (251, 211, 104), C_ROJO: (248, 113, 113)}
C_BLANCO = 103
BOTON_BARRA, X_BARRA, Y_BARRA, NOMBRE_BOTON = 59005, 167, -127, 'aolat_pd'

# ---------------------------------------------------------------------------------------------- medidas
CW, CH, CPASO = 66, 96, 70                       # tarjeta de la galeria
RET_H = 62                                       # alto del retrato en tarjetas y opciones
MW, MH = 432, 340
BANNER = (4, 4, MW - 4, 70)
FILAS_MENU = (76, 176)
BOTON_W, BOTON_H = 110, 26
EMPEZAR_XY = (MW - 8 - BOTON_W, MH - 8 - BOTON_H)

EW, EH = 432, 262
OW, OH = 66, 84                                  # opcion de la ventana de elegir (retrato + nombre dibujado)
FILAS_ELEGIR = (26, 132)

TW, TH = 280, 150
T_CAJA = (8, 8, 88, 88)
T_BOTON_W = 128
MEJORAR_XY, VENDER_XY = (8, TH - 8 - BOTON_H), (TW - 8 - T_BOTON_W, TH - 8 - BOTON_H)

HW, HH = 400, 52
PILDORAS = ((4, 4, 128, 24), (132, 4, 236, 24), (240, 4, 336, 24))
SALIR_XY, SALIR_WH = (340, 4), (56, 20)
SIGUIENTE_XY, SIGUIENTE_WH = (240, 28), (156, 20)

FW, FH = 300, 196
CARTEL = (4, 4, FW - 4, 64)
F_BOTON_W = 110
OTRA_XY, F_SALIR_XY = (30, FH - 8 - BOTON_H), (FW - 30 - F_BOTON_W, FH - 8 - BOTON_H)

# ---------------------------------------------------------------------------------------------- paleta
FONDO_ARRIBA, FONDO_ABAJO = (22, 30, 46), (9, 13, 22)
SUPERFICIE, SUPERFICIE_2, LINEA = (30, 41, 60), (22, 31, 48), (52, 66, 92)
ACENTO, ACENTO_OSCURO, ACENTO_HUNDIDO = (52, 211, 153), (4, 120, 87), (6, 95, 70)
ORO, TENUE, BLANCO = (251, 211, 104), (120, 136, 162), (240, 246, 252)
ROJO, ROJO_CLARO, ROJO_HUNDIDO = (159, 42, 58), (204, 64, 82), (120, 30, 44)
ESQUINA = (14, 19, 31)
ELEMENTO = {'lobo': (148, 163, 184), 'guardian': (180, 136, 78), 'bebe': (250, 204, 21), 'arquero': (56, 189, 248),
            'oso': (161, 98, 7), 'escarcha': (147, 197, 253), 'flor': (244, 114, 182), 'elfo': (167, 139, 250),
            'fuego': (249, 115, 22), 'espada': (226, 232, 240), 'dragon': (45, 212, 191)}
OTROS_COLORES = ((52, 211, 153), (251, 146, 60), (96, 165, 250), (232, 121, 249), (250, 204, 21), (248, 113, 113))


def color_de(clave, i=0):
    return ELEMENTO.get(clave, OTROS_COLORES[i % len(OTROS_COLORES)])


def _rgba(c, a=255):
    return tuple(c) + (a,)


def _fuente(nombre, tam):
    try:
        return ImageFont.truetype('C:/Windows/Fonts/' + nombre, tam)
    except OSError:
        return ImageFont.load_default()


def _degradado(w, h, arriba, abajo):
    im = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        v = y / max(1, h - 1)
        d.line((0, y, w, y), fill=tuple(int(arriba[k] + (abajo[k] - arriba[k]) * v) for k in range(3)) + (255,))
    return im


def _texto_centrado(d, caja, texto, fuente, color):
    x0, y0, x1, y1 = caja
    bx0, by0, bx1, by1 = d.textbbox((0, 0), texto, font=fuente)
    d.text((x0 + (x1 - x0 - (bx1 - bx0)) // 2 - bx0, y0 + (y1 - y0 - (by1 - by0)) // 2 - by0), texto, font=fuente,
           fill=_rgba(color))


def _titulo(im, xy, texto, tam, color=BLANCO):
    f = _fuente('segoeuib.ttf', tam)
    sombra = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).text((xy[0], xy[1] + 1), texto, font=f, fill=(0, 0, 0, 255))
    im.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(2)))
    ImageDraw.Draw(im).text(xy, texto, font=f, fill=_rgba(color))


def _redondear(im, r=8, fondo=ESQUINA):
    """Opaca entera, con las esquinas de fuera del color de lo que hay detras."""
    base = Image.new('RGBA', im.size, _rgba(fondo))
    mascara = Image.new('L', im.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=r, fill=255)
    base.paste(im, (0, 0), mascara)
    return base


def _resplandor(w, h, color, centro, radio, alfa=150):
    capa = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    cx, cy = centro
    ImageDraw.Draw(capa).ellipse((cx - radio, cy - radio, cx + radio, cy + radio), fill=_rgba(color, alfa))
    return capa.filter(ImageFilter.GaussianBlur(max(1, radio // 2)))


def config():
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def torres():
    """[(clave, datos)] de las torres, en el orden de plantillas/pet_defense.json (las N_MAX primeras)."""
    return list((config().get('torres') or {}).items())[:N_MAX]


# ---------------------------------------------------------------------------------------------- retratos
_INDICE = {}


def _indice():
    """{grafico: (datos del pak, tamano comprimido, offset)} de todos los _Wait.spr de shape\\mon del cliente."""
    if _INDICE:
        return _INDICE
    import fondos_interfaz as fi
    import paks_cliente
    pre = 'shape' + chr(92) + 'mon' + chr(92)
    for pak in sorted(fi.CLIENTE.glob('*.pak'), key=lambda x: paks_cliente.numero(x.name)):
        if paks_cliente.numero(pak.name) < -1:
            continue
        fuente = pak.with_name(pak.name + '.bak')
        fuente = fuente if fuente.exists() else pak
        datos = fuente.read_bytes()
        for n, _c, cs, _u, off in paks_cliente._directorio(datos):
            nl = n.lower()
            if nl.startswith(pre) and nl.endswith('_wait.spr'):
                nombre = nl.rsplit(chr(92), 1)[1].split('_')[0]
                if nombre.isdigit():
                    _INDICE[int(nombre)] = (datos, cs, off)
    return _INDICE


FRAME_DE_FRENTE = 4            # de los 8 del _Wait.spr, el que mira hacia delante (el 0 es de espaldas en lobos y osos)


def _frame(grafico):
    """El frame de frente del _Wait.spr como RGBA (el primero si no tiene tantos: las espadas traen 3), o None si es de
    los ARGB4444 que el cliente tine. "Que salgan de frente los pet" (21/11/2026)."""
    import spr_ewsp
    datos, cs, off = _indice()[int(grafico)]
    d = zlib.decompress(datos[off:off + cs], -15)
    n = struct.unpack_from('<4s7I', d, 0)[2]
    f = FRAME_DE_FRENTE if n > FRAME_DE_FRENTE else 0
    _o, o_t, _tam = struct.unpack_from('<3I', d, 80 + 12 * f)
    if struct.unpack_from('<4s19I', d[o_t:o_t + 80], 0)[2] == 4:
        return None
    return spr_ewsp.leer(d)[0][f][0].copy()


def retrato(sprites, fase, lado):
    """El retrato de la mascota de esa fase (0, 1, 2) dentro de un cuadrado de `lado`; si esa fase no se puede leer,
    la siguiente (y si no, la anterior)."""
    import mascotas
    orden = [fase] + [f for f in range(fase + 1, len(sprites))] + [f for f in range(fase - 1, -1, -1)]
    for f in orden:
        try:
            im = _frame(int(mascotas.ficha_de_sprite(int(sprites[f]))['tipo']))
        except Exception:
            im = None
        if im is None:
            continue
        caja = im.getbbox()
        if caja:
            im = im.crop(caja)
        im.thumbnail((lado, lado), Image.LANCZOS)
        return im
    return None


def _con_retrato(im, sprites, fase, lado, caja, color):
    r = retrato(sprites, fase, lado)
    x0, y0, x1, y1 = caja
    if r is None:
        ImageDraw.Draw(im).ellipse((x0 + (x1 - x0) // 2 - 16, y0 + 10, x0 + (x1 - x0) // 2 + 16, y0 + 42),
                                   fill=_rgba(color), outline=_rgba(BLANCO))
        return
    im.alpha_composite(r, (x0 + (x1 - x0 - r.width) // 2, y1 - 2 - r.height))


# ---------------------------------------------------------------------------------------------- dibujos
def banner_menu():
    bw, bh = BANNER[2] - BANNER[0], BANNER[3] - BANNER[1]
    im = _degradado(bw, bh, (8, 26, 30), (16, 52, 54))
    im.alpha_composite(_resplandor(bw, bh, ACENTO, (bw - 70, bh // 2), 46))
    d = ImageDraw.Draw(im)
    cx, cy = bw - 70, bh // 2
    d.polygon(((cx, cy - 26), (cx + 16, cy), (cx, cy + 26), (cx - 16, cy)), fill=(80, 220, 200, 255),
              outline=(200, 255, 245, 255))
    d.polygon(((cx, cy - 26), (cx + 16, cy), (cx, cy)), fill=(150, 245, 230, 255))
    d.line((cx - 16, cy, cx + 16, cy), fill=(30, 140, 130, 255))
    for i, x in enumerate(range(150, cx - 24, 9)):
        y = cy + int(10 * (1 if (i // 3) % 2 else -1) * ((i % 3) / 2))
        d.ellipse((x, y - 1, x + 3, y + 2), fill=_rgba(ACENTO))
    _titulo(im, (12, 6), 'PET DEFENSE', 22)
    ImageDraw.Draw(im).rounded_rectangle((13, 36, 60, 38), radius=1, fill=_rgba(ACENTO))
    return im


def fondo_menu():
    im = _degradado(MW, MH, FONDO_ARRIBA, FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, MW - 1, MH - 1), outline=_rgba(LINEA))
    ban = banner_menu()
    mascara = Image.new('L', ban.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, ban.width - 1, ban.height - 1), radius=8, fill=255)
    im.paste(ban, BANNER[:2], mascara)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(BANNER, radius=8, outline=_rgba(LINEA))
    d.line((8, EMPEZAR_XY[1] - 6, MW - 9, EMPEZAR_XY[1] - 6), fill=_rgba(LINEA))
    return im


def tarjeta(clave, datos, i, w, h, nombre_dibujado=False, foco=False):
    """Tarjeta con el retrato de la fase b sobre el resplandor de su color; abajo el sitio de los textos."""
    color = color_de(clave, i)
    im = Image.new('RGBA', (w, h), _rgba(SUPERFICIE if foco else SUPERFICIE_2))
    im.alpha_composite(_degradado(w, RET_H, tuple(int(c * (0.45 if foco else 0.32)) for c in color), SUPERFICIE_2))
    im.alpha_composite(_resplandor(w, RET_H, color, (w // 2, RET_H // 2 + 6), 22, 170 if foco else 140))
    _con_retrato(im, datos.get('sprites') or [datos.get('sprite', 3049)], 1, 56, (0, 0, w, RET_H), color)
    d = ImageDraw.Draw(im)
    d.line((5, RET_H, w - 6, RET_H), fill=_rgba(color))
    if nombre_dibujado:
        _texto_centrado(d, (2, RET_H + 2, w - 2, h - 2), datos.get('nombre', clave), _fuente('segoeuib.ttf', 9), BLANCO)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=7, outline=_rgba(ACENTO if foco else LINEA))
    return _redondear(im, 7)


def fondo_elegir():
    im = _degradado(EW, EH, FONDO_ARRIBA, FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, EW - 1, EH - 1), outline=_rgba(LINEA))
    d.line((8, 22, EW - 9, 22), fill=_rgba(LINEA))
    d.line((8, EH - 24, EW - 9, EH - 24), fill=_rgba(LINEA))
    return im


def fondo_torre():
    im = _degradado(TW, TH, FONDO_ARRIBA, FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, TW - 1, TH - 1), outline=_rgba(LINEA))
    d.rounded_rectangle(T_CAJA, radius=8, fill=_rgba(SUPERFICIE_2), outline=_rgba(LINEA))
    d.line((8, MEJORAR_XY[1] - 6, TW - 9, MEJORAR_XY[1] - 6), fill=_rgba(LINEA))
    return im


def retrato_torre(clave, datos, i, fase):
    """El retrato de la ficha (80x80) de esa fase, sobre su resplandor; las estrellas de la fase abajo."""
    w = h = T_CAJA[2] - T_CAJA[0]
    color = color_de(clave, i)
    im = Image.new('RGBA', (w, h), _rgba(SUPERFICIE_2))
    im.alpha_composite(_resplandor(w, h, color, (w // 2, h // 2), 26, 170))
    _con_retrato(im, datos.get('sprites') or [datos.get('sprite', 3049)], fase, 70, (0, 0, w, h - 6), color)
    d = ImageDraw.Draw(im)
    for k in range(3):
        x = w // 2 - 15 + k * 11
        d.ellipse((x, h - 9, x + 7, h - 2), fill=_rgba(ORO if k <= fase else LINEA))
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=8, outline=_rgba(color))
    return _redondear(im, 8)


def boton(texto, estado, w=BOTON_W, h=BOTON_H, rojo=False, fondo=(12, 17, 28), tam=13):
    if rojo:
        relleno, borde = {'n': (ROJO, ROJO_CLARO), 'f': (ROJO_CLARO, (240, 120, 134)), 's': (ROJO_HUNDIDO, ROJO)}[estado]
    else:
        relleno, borde = {'n': (ACENTO_OSCURO, ACENTO), 'f': ((16, 150, 110), (170, 245, 215)),
                          's': (ACENTO_HUNDIDO, ACENTO)}[estado]
    im = Image.new('RGBA', (w, h), _rgba(fondo))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=_rgba(relleno), outline=_rgba(borde))
    o = 1 if estado == 's' else 0
    _texto_centrado(d, (0, o, w, h + o), texto, _fuente('segoeuib.ttf', tam), BLANCO)
    return im


def fondo_hud():
    im = _degradado(HW, HH, FONDO_ARRIBA, FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, HW - 1, HH - 1), outline=_rgba(LINEA))
    for caja in PILDORAS:
        d.rounded_rectangle(caja, radius=10, fill=_rgba(SUPERFICIE), outline=_rgba(LINEA))
    x, y = PILDORAS[0][0] + 6, PILDORAS[0][1] + 3
    d.polygon(((x + 7, y), (x + 13, y + 7), (x + 7, y + 14), (x + 1, y + 7)), fill=(80, 220, 200, 255),
              outline=(200, 255, 245, 255))
    x, y = PILDORAS[1][0] + 6, PILDORAS[1][1] + 3
    d.line((x + 1, y + 13, x + 13, y + 1), fill=_rgba(BLANCO), width=2)
    d.line((x + 1, y + 1, x + 13, y + 13), fill=_rgba(BLANCO), width=2)
    x, y = PILDORAS[2][0] + 6, PILDORAS[2][1] + 3
    d.polygon(((x + 3, y + 1), (x + 11, y + 1), (x + 14, y + 5), (x + 7, y + 14), (x, y + 5)), fill=_rgba(ORO),
              outline=(255, 245, 200, 255))
    return im


def fondo_fin():
    im = _degradado(FW, FH, FONDO_ARRIBA, FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, FW - 1, FH - 1), outline=_rgba(LINEA))
    d.rounded_rectangle((8, 70, FW - 9, OTRA_XY[1] - 8), radius=8, fill=_rgba(SUPERFICIE_2), outline=_rgba(LINEA))
    return im


def cartel(texto, color, arriba, abajo):
    w, h = CARTEL[2] - CARTEL[0], CARTEL[3] - CARTEL[1]
    im = _degradado(w, h, arriba, abajo)
    im.alpha_composite(_resplandor(w, h, color, (w // 2, h // 2), 40))
    f = _fuente('segoeuib.ttf', 28)
    bx0, by0, bx1, by1 = ImageDraw.Draw(im).textbbox((0, 0), texto, font=f)
    _titulo(im, ((w - (bx1 - bx0)) // 2 - bx0, (h - (by1 - by0)) // 2 - by0 - 1), texto, 28, BLANCO)
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=8, outline=_rgba(color))
    return _redondear(im, 8, FONDO_ARRIBA)


def icono_barra():
    """El icono de la barra (40x56): el cristal con un escudo delante."""
    k = 4
    im = Image.new('RGBA', (ANCHO * k, ALTO * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    borde = (20, 40, 40, 255)

    def r(*xy):
        return [v * k for v in xy]
    d.polygon(r(20, 4, 33, 24, 20, 44, 7, 24), fill=(80, 220, 200, 255), outline=borde, width=k)
    d.polygon(r(20, 4, 33, 24, 20, 24), fill=(170, 248, 236, 255))
    d.line(r(7, 24, 33, 24), fill=(30, 140, 130, 255), width=k)
    d.polygon(r(12, 34, 28, 34, 28, 44, 20, 52, 12, 44), fill=(214, 160, 70, 255), outline=borde, width=k)
    d.ellipse(r(16, 38, 24, 46), fill=(255, 236, 170, 255), outline=borde, width=k)
    return im.resize((ANCHO, ALTO), Image.LANCZOS)


def piezas() -> dict:
    p = {'aolat_pd_menu': fondo_menu(), 'aolat_pd_hud': fondo_hud(), 'aolat_pd_fin': fondo_fin(),
         'aolat_pd_elegir': fondo_elegir(), 'aolat_pd_torre': fondo_torre(),
         'aolat_pd_victoria': cartel('VICTORY!', ORO, (60, 44, 10), (24, 18, 6)),
         'aolat_pd_derrota': cartel('DEFEAT', ROJO_CLARO, (60, 14, 20), (24, 6, 10))}
    for i, (clave, datos) in enumerate(torres()):
        p['aolat_pd_carta%d' % i] = tarjeta(clave, datos, i, CW, CH)
        p['aolat_pd_op%d_n' % i] = tarjeta(clave, datos, i, OW, OH, nombre_dibujado=True)
        p['aolat_pd_op%d_f' % i] = tarjeta(clave, datos, i, OW, OH, nombre_dibujado=True, foco=True)
        for fase in range(3):
            p['aolat_pd_ret%d_%d' % (i, fase)] = retrato_torre(clave, datos, i, fase)
    for e in 'nfs':
        p['aolat_pd_empezar_%s' % e] = boton('Start', e)
        p['aolat_pd_siguiente_%s' % e] = boton('Next wave now', e, *SIGUIENTE_WH, tam=11)
        p['aolat_pd_salir_%s' % e] = boton('Leave', e, *SALIR_WH, rojo=True, tam=10)
        p['aolat_pd_otra_%s' % e] = boton('Play again', e, F_BOTON_W)
        p['aolat_pd_fsalir_%s' % e] = boton('Leave', e, F_BOTON_W, rojo=True)
        p['aolat_pd_mejorar_%s' % e] = boton('Upgrade', e, T_BOTON_W)
        p['aolat_pd_vender_%s' % e] = boton('Sell', e, T_BOTON_W, rojo=True)
    normal = al_estilo_nativo(icono_barra())
    p[NOMBRE_BOTON + '_n'] = normal
    p[NOMBRE_BOTON + '_f'] = ImageEnhance.Brightness(normal).enhance(1.25)
    return p


# ---------------------------------------------------------------------------------------------- el XML
def _w(clase, wid, x, y, w, h, extra='', estilo='wsVisible=""', cuerpo=''):
    return ('    <window class="%s" id="%d" range="%d,%d,%d,%d"%s>\n        <style %s />\n%s    </window>\n'
            % (clase, wid, x, y, w, h, extra, estilo, cuerpo))


def _texto(wid, x, y, w, color, titulo='', estilo=''):
    return _w('WND_CLASS_STATIC', wid, x, y, w, 14, ' title="%s" fcolor="%d" font="1"' % (titulo, color),
              'wsVisible="" ssVCenter=""' + estilo)


def _boton(wid, x, y, w, h, icono, funcion, ayuda=''):
    extra = ' title="" icon="%d"' % icono + (' tooltip="10040" tooltext="%s"' % ayuda if ayuda else '')
    return _w('WND_CLASS_BUTTON', wid, x, y, w, h, extra, 'wsVisible="" wsTab=""',
              '        <OnCommand>%s</OnCommand>\n' % funcion if funcion else '')


def _icono(iid, base, focus=None, down=None):
    return ('    <icon id="%d" dir="\\wnd01\\" normal="%s" focus="%s" down="%s" disable="normal" />\n'
            % (iid, base, focus or 'normal', down or 'normal'))


def _dlg(wid, titulo, w, h, hijos):
    return ('    <window class="WND_CLASS_DLG_1" range="0,0,%d,%d" id="%d" title="%s" fcolor="104" font="1">\n'
            '        <style wsVisible="" wsMoveable="" />\n%s    </window>\n'
            % (w + 2 * MARCO_X, h + MARCO_Y + MARCO_ABAJO, wid, titulo,
               ''.join('        <child>%d</child>\n' % c for c in hijos)))


def _rejilla(i, filas):
    return 8 + (i % 6) * CPASO, filas[i // 6]


def bloque() -> str:
    xml = []

    def ventana(wid, titulo, w, h, hijos_xml):
        xml.append(_dlg(wid, titulo, w, h, [c for c, _ in hijos_xml]))
        xml.extend(x for _, x in hijos_xml)

    n = N_MAX
    # MENU: textos encima, luego las tarjetas (botones con su clic) y el fondo.
    m = [(M_EMPEZAR, _boton(M_EMPEZAR, EMPEZAR_XY[0], EMPEZAR_XY[1], BOTON_W, BOTON_H, I_EMPEZAR, 'OnPDEmpezar',
                            'Start a Pet Defense game')),
         (M_SUB, _texto(M_SUB, 14, 44, 260, C_ACENTO))]
    for i in range(n):
        x, y = _rejilla(i, FILAS_MENU)
        m.append((M_NOMBRE + i, _texto(M_NOMBRE + i, x + 2, y + RET_H + 2, CW - 4, C_BLANCO, '', ' ssHCenter=""')))
        m.append((M_COSTE + i, _texto(M_COSTE + i, x + 2, y + RET_H + 17, CW - 4, C_ORO, '', ' ssHCenter=""')))
    m.append((M_INFO, _texto(M_INFO, 10, FILAS_MENU[1] + CH + 6, MW - 20, C_TENUE)))
    m.append((M_ESTADO, _texto(M_ESTADO, 10, EMPEZAR_XY[1] + 6, EMPEZAR_XY[0] - 18, C_ORO)))
    for i in range(n):
        x, y = _rejilla(i, FILAS_MENU)
        m.append((M_ARTE + i, _boton(M_ARTE + i, x, y, CW, CH, I_CARTA + i, 'OnPDCarta%d' % (i + 1))))
    m.append((M_FONDO, _w('WND_CLASS_BASE', M_FONDO, 0, 0, MW, MH, ' icon="%d"' % I_M_FONDO)))
    ventana(V_MENU, 'Pet Defense', MW, MH, m)

    # ELEGIR
    e = [(E_TITULO, _texto(E_TITULO, 10, 4, EW - 20, C_BLANCO))]
    for i in range(n):
        x, y = _rejilla(i, FILAS_ELEGIR)
        e.append((E_COSTE + i, _texto(E_COSTE + i, x + 2, y + OH + 3, OW - 4, C_ORO, '', ' ssHCenter=""')))
    e.append((E_ESTADO, _texto(E_ESTADO, 10, EH - 20, EW - 20, C_ORO)))
    for i in range(n):
        x, y = _rejilla(i, FILAS_ELEGIR)
        e.append((E_OPCION + i, _boton(E_OPCION + i, x, y, OW, OH, I_OPCION + i, 'OnPDOpcion%d' % (i + 1))))
    e.append((E_FONDO, _w('WND_CLASS_BASE', E_FONDO, 0, 0, EW, EH, ' icon="%d"' % I_E_FONDO)))
    ventana(V_ELEGIR, 'Choose a pet', EW, EH, e)

    # TORRE
    tx = T_CAJA[2] + 8
    t = [(T_MEJORAR, _boton(T_MEJORAR, MEJORAR_XY[0], MEJORAR_XY[1], T_BOTON_W, BOTON_H, I_MEJORAR, 'OnPDMejorar')),
         (T_VENDER, _boton(T_VENDER, VENDER_XY[0], VENDER_XY[1], T_BOTON_W, BOTON_H, I_VENDER, 'OnPDVender')),
         (T_NOMBRE, _texto(T_NOMBRE, tx, 10, TW - tx - 8, C_BLANCO)),
         (T_NIVEL, _texto(T_NIVEL, tx, 28, TW - tx - 8, C_ACENTO)),
         (T_STATS, _texto(T_STATS, tx, 46, TW - tx - 8, C_BLANCO)),
         (T_SIGUIENTE, _texto(T_SIGUIENTE, tx, 64, TW - tx - 8, C_TENUE)),
         (T_ESTADO, _texto(T_ESTADO, 8, T_CAJA[3] + 8, TW - 16, C_ORO)),
         (T_RETRATO, _w('WND_CLASS_BUTTON', T_RETRATO, T_CAJA[0], T_CAJA[1], T_CAJA[2] - T_CAJA[0],
                        T_CAJA[3] - T_CAJA[1], ' title="" icon="%d"' % I_RETRATO)),
         (T_FONDO, _w('WND_CLASS_BASE', T_FONDO, 0, 0, TW, TH, ' icon="%d"' % I_T_FONDO))]
    ventana(V_TORRE, 'Tower', TW, TH, t)

    # HUD
    h = [(H_SIGUIENTE, _boton(H_SIGUIENTE, SIGUIENTE_XY[0], SIGUIENTE_XY[1], SIGUIENTE_WH[0], SIGUIENTE_WH[1],
                              I_SIGUIENTE, 'OnPDSiguiente', 'Skip the pause and send the next wave')),
         (H_SALIR, _boton(H_SALIR, SALIR_XY[0], SALIR_XY[1], SALIR_WH[0], SALIR_WH[1], I_SALIR, 'OnPDSalir',
                          'Give up and leave'))]
    for wid, caja in ((H_CRISTAL, PILDORAS[0]), (H_OLEADA, PILDORAS[1]), (H_ESSENCE, PILDORAS[2])):
        h.append((wid, _texto(wid, caja[0] + 24, caja[1] + 3, caja[2] - caja[0] - 28, C_BLANCO)))
    h.append((H_AVISO, _texto(H_AVISO, 8, 31, SIGUIENTE_XY[0] - 14, C_ORO)))
    h.append((H_FONDO, _w('WND_CLASS_BASE', H_FONDO, 0, 0, HW, HH, ' icon="%d"' % I_H_FONDO)))
    ventana(V_HUD, 'Pet Defense', HW, HH, h)

    # FIN
    f = [(F_OTRA, _boton(F_OTRA, OTRA_XY[0], OTRA_XY[1], F_BOTON_W, BOTON_H, I_OTRA, 'OnPDOtra', 'Play again')),
         (F_SALIR, _boton(F_SALIR, F_SALIR_XY[0], F_SALIR_XY[1], F_BOTON_W, BOTON_H, I_F_SALIR, 'OnPDSalirFin',
                          'Back to town'))]
    for k in range(4):
        f.append((F_LINEA + k, _texto(F_LINEA + k, 16, 78 + 18 * k, FW - 32, C_BLANCO if k < 3 else C_ORO, '',
                                      ' ssHCenter=""')))
    f.append((F_TITULO, _w('WND_CLASS_BUTTON', F_TITULO, CARTEL[0], CARTEL[1], CARTEL[2] - CARTEL[0],
                           CARTEL[3] - CARTEL[1], ' title="" icon="%d"' % I_VICTORIA)))
    f.append((F_FONDO, _w('WND_CLASS_BASE', F_FONDO, 0, 0, FW, FH, ' icon="%d"' % I_F_FONDO)))
    ventana(V_FIN, 'Pet Defense', FW, FH, f)

    iconos = [_icono(I_M_FONDO, 'aolat_pd_menu'), _icono(I_H_FONDO, 'aolat_pd_hud'), _icono(I_F_FONDO, 'aolat_pd_fin'),
              _icono(I_E_FONDO, 'aolat_pd_elegir'), _icono(I_T_FONDO, 'aolat_pd_torre'),
              _icono(I_VICTORIA, 'aolat_pd_victoria'), _icono(I_DERROTA, 'aolat_pd_derrota')]
    for i in range(len(torres())):
        iconos.append(_icono(I_CARTA + i, 'aolat_pd_carta%d' % i))
        iconos.append(_icono(I_OPCION + i, 'aolat_pd_op%d_n' % i, 'aolat_pd_op%d_f' % i, 'aolat_pd_op%d_f' % i))
        for fase in range(3):
            iconos.append(_icono(I_RETRATO + 3 * i + fase, 'aolat_pd_ret%d_%d' % (i, fase)))
    for iid, nombre in ((I_EMPEZAR, 'empezar'), (I_SIGUIENTE, 'siguiente'), (I_SALIR, 'salir'), (I_OTRA, 'otra'),
                        (I_F_SALIR, 'fsalir'), (I_MEJORAR, 'mejorar'), (I_VENDER, 'vender')):
        iconos.append(_icono(iid, 'aolat_pd_%s_n' % nombre, 'aolat_pd_%s_f' % nombre, 'aolat_pd_%s_s' % nombre))
    colores = ''.join('    <color id="%d" normal="%s" focus="%s" down="%s" disable="%s"/>\n'
                      % ((cid,) + (','.join(map(str, c)),) * 4) for cid, c in COLORES.items())
    return '    <!-- %s -->\n%s%s%s    <!-- /%s -->\n' % (MARCA, colores, ''.join(xml), ''.join(iconos), MARCA)


def _quitar_marca(texto):
    return re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\n' % (MARCA, MARCA), '', texto, flags=re.S)


def wnd03(texto: str) -> str:
    """wnd03.xml con las ventanas (idempotente)."""
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = _quitar_marca(texto.replace('\r\n', '\n'))
    fin = texto.rindex('</root>')
    return (texto[:fin] + bloque() + texto[fin:]).replace('\n', nl)


def wnd01(texto: str) -> str:
    """wnd01.xml con el boton en la barra, a la izquierda del de AOF Raid (idempotente)."""
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = _quitar_marca(texto.replace('\r\n', '\n'))
    texto = re.sub(r'\n[ \t]*<child>%d</child>' % BOTON_BARRA, '', texto)
    m = re.search(r'([ \t]*)<child>59004</child>', texto)
    if not m:
        raise SystemExit('no esta el boton de AOF Raid (59004) en wnd01.xml')
    texto = texto[:m.end()] + '\n' + m.group(1) + '<child>%d</child>' % BOTON_BARRA + texto[m.end():]
    boton_xml = ('    <!-- %s -->\n' % MARCA
                 + '    <window class="WND_CLASS_BUTTON" range="%d,%d,40,56" id="%d" icon="%d" tooltip="10043" '
                   'tooltext="Pet Defense">\n        <style wsVisible="" wsTab="" />\n'
                   '        <OnCommand>OnCommandPetDefense</OnCommand>\n    </window>\n'
                   % (X_BARRA, Y_BARRA, BOTON_BARRA, BOTON_BARRA)
                 + '    <icon id="%d" dir="\\wnd01\\" normal="%s_n" focus="%s_f" down="%s_n" disable="normal" />\n'
                   % (BOTON_BARRA, NOMBRE_BOTON, NOMBRE_BOTON, NOMBRE_BOTON)
                 + '    <!-- /%s -->\n' % MARCA)
    fin = texto.rindex('</root>')
    return (texto[:fin] + boton_xml + texto[fin:]).replace('\n', nl)


def _reescribir(ruta, cambio):
    crudo = ruta.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    ruta.write_bytes((b'\xef\xbb\xbf' if bom else b'') + cambio(crudo.decode('utf-8-sig')).encode('utf-8'))


def _piezas_viejas():
    """Los .shp de la version anterior (cartas de 4, botones de tipo) que ya no se usan."""
    return [f for f in SALIDA.glob('aolat_pd_*.shp')
            if re.match(r'aolat_pd_(carta\d_[ns]|tipo\d_[nfs])\.shp$', f.name)]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--vista', help='carpeta donde dejar las piezas en .png para mirarlas')
    a = ap.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)
    for f in _piezas_viejas():
        f.unlink()
    p = piezas()
    for nombre, im in p.items():
        (SALIDA / (nombre + '.shp')).write_bytes(a_shp(im))
        if a.vista:
            pathlib.Path(a.vista).mkdir(parents=True, exist_ok=True)
            im.save(pathlib.Path(a.vista) / (nombre + '.png'))
    _reescribir(ENG / 'wnd03.xml', wnd03)
    _reescribir(ENG / 'wnd01.xml', wnd01)
    print('Pet Defense: %d piezas, %d torres' % (len(p), len(torres())))


if __name__ == '__main__':
    main()
