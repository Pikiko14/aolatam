"""La ventana de entrada a la Torre de Babel rehecha (13/11/2026, "rehaz la interfaz de entrada a la torre de babel que
sea moderna parecida a la de raids").

Antes era un DLG_1 con la textura del tema, una lista nativa y el boton de check con su rotulo al lado
(tools/parche_subasta_ventana.TORRE). Ahora va como las ventanas de las raids (tools/parche_raid.py): el DLG_1 se
queda con su barra de titulo y el contenido es un fondo propio en una hija BASE con icono, la ULTIMA de la lista (el
juego pinta las hijas de la ultima a la primera). El dibujo sigue la linea de la seleccion de personaje
(tools/seleccion_personaje.py): pizarra oscura, acento celeste, pastillas y esquinas redondeadas.

  * arriba, el banner de la torre (cielo de noche, la torre con sus ventanas encendidas y el titulo) y debajo del
    titulo el texto de los pisos (59021, lo pone el Lua con el numero del servidor);
  * las pestanas Solo / Party (59022, 59023) como control segmentado: el texto va DIBUJADO en el icono (el juego no
    pinta el de todos los botones) y la elegida lleva su icono encendido (seticon desde server/lua/torre.lua);
  * una linea que explica el modo (59028);
  * el ranking: cabecera (59024), columnas dibujadas y diez filas de textos sueltos (puesto, nombres, pisos, tiempo:
    59210.., 59220.., 59230.., 59240..), con el primero en oro, plata y bronce para los tres primeros; encima de cada
    fila un boton transparente (59250..) cuyo tooltip lleva todos los nombres; y el aviso de vacio (59027);
  * abajo el estado (59026) y el boton grande (59025), con Enter / Join / Leave dibujados (tres iconos).

Los .shp solo tienen transparencia de todo o nada: todo lo que lleva texto dibujado es opaco.

    python tools/ventana_torre.py          (dibuja los .shp y pone la ventana en parches/extras/setting/eng/wnd03.xml)
    tools/parche_subasta_ventana.py la vuelve a poner cuando rehace wnd03.xml.
"""
import pathlib
import re
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
from icono_subasta import SALIDA, a_shp  # noqa: E402

WND03 = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'wnd03.xml'
MARCA = 'aolat torre ventana'

# El contenido (sin el marco del DLG_1: parche_raid.MARCO_X/Y/ABAJO = 4, 20, 4).
W, H = 340, 346
MARCO_X, MARCO_Y, MARCO_ABAJO = 4, 20, 4

VENTANA = 59020
PISOS, SOLO, PARTY, CABECERA, ENTRAR, ESTADO, VACIO, MODO = 59021, 59022, 59023, 59024, 59025, 59026, 59027, 59028
FONDO = 59203
PUESTO, NOMBRES, NPISOS, TIEMPO, CLIC = 59210, 59220, 59230, 59240, 59250
N_FILAS = 10
# Todos los ids entre los que el cliente ya carga (13/11/2026): con 61001..61072, por encima de los mas altos de
# wnd*.xml (ventana 60472, icono 60466, color 59099), el juego se cerraba al entrar al mundo.
# Iconos
I_FONDO, I_SOLO, I_SOLO_ON, I_PARTY, I_PARTY_ON, I_ENTRAR, I_UNIRSE, I_SALIR = (59260, 59262, 59263, 59264, 59265,
                                                                              59266, 59267, 59268)
# Colores de texto propios (los 510..514 son los de wnd01.xml: gris, verde, blanco, amarillo, oro)
C_CELESTE, C_TENUE, C_BRONCE = 59270, 59271, 59272
COLORES = {C_CELESTE: (125, 211, 252), C_TENUE: (148, 163, 184), C_BRONCE: (214, 140, 72)}
C_ORO, C_PLATA, C_BLANCO, C_AMARILLO = 514, 510, 103, 513

# Las cajas del dibujo (x0, y0, x1, y1), desde la esquina del contenido.
BANNER = (4, 4, W - 4, 68)
PESTANAS = (6, 74, 204, 100)            # la pista del control segmentado
PESTANA_W, PESTANA_H = 96, 22
SOLO_XY, PARTY_XY = (8, 76), (106, 76)
MODO_Y = 105
TABLA = (4, 124, W - 4, 306)
CAB_Y = TABLA[1] + 4                    # la cabecera (59024)
COLS_Y = TABLA[1] + 22                  # los rotulos de las columnas (dibujados)
FILA0, PASO = TABLA[1] + 40, 14         # la primera fila y la distancia entre filas
COL_PUESTO, COL_NOMBRES, COL_PISOS, COL_TIEMPO = (12, 22), (36, 176), (218, 48), (274, 56)   # (x, ancho)
BOTON_W, BOTON_H = 96, 26
BOTON_XY = (W - 8 - BOTON_W, H - 8 - BOTON_H)

# La paleta de tools/seleccion_personaje.py
FONDO_ARRIBA, FONDO_ABAJO = (24, 32, 54), (10, 14, 26)
SUPERFICIE = (30, 41, 64)
SUPERFICIE_2 = (24, 33, 54)
LINEA = (52, 66, 94)
ACENTO = (56, 189, 248)
ACENTO_OSCURO = (3, 105, 161)
ACENTO_HUNDIDO = (2, 80, 124)
TENUE = (120, 136, 162)
BLANCO = (240, 246, 252)
ROJO, ROJO_CLARO, ROJO_HUNDIDO = (159, 42, 58), (204, 64, 82), (120, 30, 44)


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


# ---------------------------------------------------------------------------------------------- el dibujo

def banner() -> Image.Image:
    """El banner (332x64): cielo de noche, estrellas, un resplandor celeste y la torre a la derecha."""
    import random
    bw, bh = BANNER[2] - BANNER[0], BANNER[3] - BANNER[1]
    im = _degradado(bw, bh, (6, 10, 24), (20, 40, 76))
    rnd = random.Random(133)
    d = ImageDraw.Draw(im)
    for _ in range(46):                                         # estrellas
        x, y = rnd.uniform(0, bw), rnd.uniform(0, bh * 0.8)
        c = rnd.choice(((200, 225, 255), (150, 190, 240), (255, 255, 255)))
        d.point((x, y), fill=_rgba(c))
    brillo = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse((bw - 150, 6, bw + 20, bh + 60), fill=_rgba(ACENTO, 120))
    im.alpha_composite(brillo.filter(ImageFilter.GaussianBlur(16)))
    # La torre: pisos escalonados, cada uno mas estrecho, con ventanas encendidas; un haz de luz en la punta.
    d = ImageDraw.Draw(im)
    cx, base = bw - 62, bh
    pisos = 6
    for i in range(pisos):
        ancho = 64 - 9 * i
        y1 = base - 9 * i
        y0 = y1 - 9
        tono = 34 + 6 * i
        d.rectangle((cx - ancho // 2, y0, cx + ancho // 2, y1), fill=(tono, tono + 12, tono + 34, 255),
                    outline=_rgba(LINEA))
        d.line((cx - ancho // 2 + 1, y0 + 1, cx + ancho // 2 - 1, y0 + 1), fill=_rgba((70, 96, 140)))
        for vx in range(cx - ancho // 2 + 4, cx + ancho // 2 - 2, 6):
            d.rectangle((vx, y0 + 4, vx + 1, y0 + 6), fill=_rgba(ACENTO if (vx + i) % 3 else (180, 230, 255)))
    punta = base - 9 * pisos
    d.polygon(((cx - 5, punta), (cx + 5, punta), (cx, punta - 9)), fill=_rgba(ACENTO_OSCURO), outline=_rgba(ACENTO))
    haz = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    ImageDraw.Draw(haz).polygon(((cx - 2, punta - 8), (cx + 2, punta - 8), (cx + 14, 0), (cx - 14, 0)),
                                fill=_rgba(ACENTO, 110))
    im.alpha_composite(haz.filter(ImageFilter.GaussianBlur(3)))
    # El titulo con sombra y una barra de acento debajo; el texto de los pisos (59021) va debajo, lo pone el juego.
    f = _fuente('segoeuib.ttf', 21)
    sombra = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).text((12, 6), 'TOWER OF BABEL', font=f, fill=(0, 0, 0, 255))
    im.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(2)))
    d = ImageDraw.Draw(im)
    d.text((12, 6), 'TOWER OF BABEL', font=f, fill=_rgba(BLANCO))
    d.rounded_rectangle((13, 35, 53, 37), radius=1, fill=_rgba(ACENTO))
    return im


def fondo() -> Image.Image:
    """Todo el contenido (340x346), opaco."""
    im = _degradado(W, H, FONDO_ARRIBA, FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W - 1, H - 1), outline=_rgba(LINEA))
    # El banner con su borde redondeado (las esquinas de fuera, del color del fondo).
    ban = banner()
    mascara = Image.new('L', ban.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, ban.width - 1, ban.height - 1), radius=8, fill=255)
    im.paste(ban, BANNER[:2], mascara)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(BANNER, radius=8, outline=_rgba(LINEA))
    # La pista de las pestanas.
    d.rounded_rectangle(PESTANAS, radius=(PESTANAS[3] - PESTANAS[1]) // 2, fill=_rgba(SUPERFICIE_2),
                        outline=_rgba(LINEA))
    # La tabla: caja, barra de acento, la cabecera, los rotulos de las columnas y las franjas alternas.
    x0, y0, x1, y1 = TABLA
    d.rounded_rectangle(TABLA, radius=8, fill=_rgba(SUPERFICIE_2), outline=_rgba(LINEA))
    d.rounded_rectangle((x0 + 24, y0, x0 + 90, y0 + 2), radius=1, fill=_rgba(ACENTO))
    f = _fuente('segoeuib.ttf', 9)
    for (x, _w), rotulo in zip((COL_PUESTO, COL_NOMBRES, COL_PISOS, COL_TIEMPO), ('#', 'CLIMBERS', 'FLOORS', 'TIME')):
        d.text((x + 1, COLS_Y + 1), rotulo, font=f, fill=_rgba(TENUE))
    d.line((x0 + 6, FILA0 - 4, x1 - 6, FILA0 - 4), fill=_rgba(LINEA))
    for i in range(N_FILAS):
        if i % 2 == 0:
            y = FILA0 + PASO * i
            d.rounded_rectangle((x0 + 5, y - 1, x1 - 5, y + PASO - 2), radius=3, fill=_rgba(SUPERFICIE))
    # El pie: una linea fina.
    d.line((8, BOTON_XY[1] - 6, W - 9, BOTON_XY[1] - 6), fill=_rgba(LINEA))
    return im


def pestana(texto, estado) -> Image.Image:
    """Una pestana de 96x22 con su texto: 'n' apagada (del color de la pista), 'f' con el raton, 's' la elegida."""
    relleno, borde, color = {'n': (SUPERFICIE_2, SUPERFICIE_2, TENUE), 'f': (SUPERFICIE, LINEA, BLANCO),
                             's': (ACENTO_OSCURO, ACENTO, BLANCO)}[estado]
    # Opaca entera (con el color de la pista en las esquinas): el texto dibujado no pierde su suavizado.
    im = Image.new('RGBA', (PESTANA_W, PESTANA_H), _rgba(SUPERFICIE_2))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, PESTANA_W - 1, PESTANA_H - 1), radius=PESTANA_H // 2, fill=_rgba(relleno),
                        outline=_rgba(borde))
    _texto_centrado(d, (0, 0, PESTANA_W, PESTANA_H), texto, _fuente('segoeuib.ttf', 12), color)
    return im


def boton(texto, estado, rojo=False) -> Image.Image:
    """El boton grande (96x26): pastilla llena de acento (o roja para salir) con su texto."""
    if rojo:
        relleno, borde = {'n': (ROJO, ROJO_CLARO), 'f': (ROJO_CLARO, (240, 120, 134)), 's': (ROJO_HUNDIDO, ROJO)}[estado]
    else:
        relleno, borde = {'n': (ACENTO_OSCURO, ACENTO), 'f': ((14, 136, 200), (150, 220, 252)),
                          's': (ACENTO_HUNDIDO, ACENTO)}[estado]
    # Las esquinas con el color del fondo de abajo (el boton se pinta sobre el degradado, casi en su color final).
    im = Image.new('RGBA', (BOTON_W, BOTON_H), _rgba((12, 17, 31)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, BOTON_W - 1, BOTON_H - 1), radius=BOTON_H // 2, fill=_rgba(relleno),
                        outline=_rgba(borde))
    o = 1 if estado == 's' else 0
    _texto_centrado(d, (0, o, BOTON_W, BOTON_H + o), texto, _fuente('segoeuib.ttf', 13), BLANCO)
    return im


def piezas() -> dict:
    """{nombre del .shp: imagen}."""
    p = {'aolat_torre_fondo': fondo()}
    for nombre, texto in (('solo', 'Solo'), ('party', 'Party')):
        for e in 'nfs':
            p['aolat_torre_%s_%s' % (nombre, e)] = pestana(texto, e)
    for nombre, texto, rojo in (('entrar', 'Enter', False), ('unirse', 'Join', False), ('salir', 'Leave', True)):
        for e in 'nfs':
            p['aolat_torre_%s_%s' % (nombre, e)] = boton(texto, e, rojo)
    return p


# ---------------------------------------------------------------------------------------------- el XML

def _w(clase, wid, x, y, w, h, extra='', estilo='wsVisible=""', cuerpo=''):
    return ('    <window class="%s" id="%d" range="%d,%d,%d,%d"%s>\n        <style %s />\n%s    </window>\n'
            % (clase, wid, x, y, w, h, extra, estilo, cuerpo))


def _texto(wid, x, y, w, color, titulo='', estilo=''):
    return _w('WND_CLASS_STATIC', wid, x, y, w, 14, ' title="%s" fcolor="%d" font="1"' % (titulo, color),
              'wsVisible="" ssVCenter=""' + estilo)


def _icono(iid, base, focus=None, down=None):
    return ('    <icon id="%d" dir="\\wnd01\\" normal="%s" focus="%s" down="%s" disable="normal" />\n'
            % (iid, base, focus or 'normal', down or 'normal'))


def bloque() -> str:
    hijos, ventanas = [], []

    def poner(wid, xml):
        hijos.append(wid)
        ventanas.append(xml)
    # Primero lo que va encima (el juego pinta las hijas de la ultima a la primera): los botones de las filas.
    for i in range(N_FILAS):
        poner(CLIC + i, _w('WND_CLASS_BUTTON', CLIC + i, TABLA[0] + 5, FILA0 + PASO * i - 1, TABLA[2] - TABLA[0] - 10,
                           PASO, ' appdata="%d"' % i, 'wsTab=""'))
    poner(SOLO, _w('WND_CLASS_BUTTON', SOLO, SOLO_XY[0], SOLO_XY[1], PESTANA_W, PESTANA_H,
                   ' title="" fcolor="103" font="1" icon="%d"' % I_SOLO_ON, 'wsVisible="" wsTab=""',
                   '        <OnCommand>OnTorreSolo</OnCommand>\n'))
    poner(PARTY, _w('WND_CLASS_BUTTON', PARTY, PARTY_XY[0], PARTY_XY[1], PESTANA_W, PESTANA_H,
                    ' title="" fcolor="103" font="1" icon="%d"' % I_PARTY, 'wsVisible="" wsTab=""',
                    '        <OnCommand>OnTorreParty</OnCommand>\n'))
    poner(ENTRAR, _w('WND_CLASS_BUTTON', ENTRAR, BOTON_XY[0], BOTON_XY[1], BOTON_W, BOTON_H,
                     ' title="" icon="%d" tooltip="10040" tooltext="Enter the Tower of Babel"' % I_ENTRAR,
                     'wsVisible="" wsTab=""', '        <OnCommand>OnTorreEntrar</OnCommand>\n'))
    poner(PISOS, _texto(PISOS, 14, 42, 200, C_CELESTE))
    poner(MODO, _texto(MODO, 10, MODO_Y, W - 20, C_TENUE))
    poner(CABECERA, _texto(CABECERA, TABLA[0] + 8, CAB_Y + 2, 220, C_BLANCO))
    poner(VACIO, _texto(VACIO, TABLA[0] + 8, FILA0 + PASO * 3, TABLA[2] - TABLA[0] - 16, C_TENUE,
                        'No climbs yet. Be the first!', ' ssHCenter=""'))
    poner(ESTADO, _texto(ESTADO, 10, BOTON_XY[1] + 6, BOTON_XY[0] - 18, C_AMARILLO))
    for i in range(N_FILAS):
        y = FILA0 + PASO * i
        puesto = (C_ORO, C_PLATA, C_BRONCE)[i] if i < 3 else C_TENUE
        poner(PUESTO + i, _texto(PUESTO + i, COL_PUESTO[0], y, COL_PUESTO[1], puesto))
        poner(NOMBRES + i, _texto(NOMBRES + i, COL_NOMBRES[0], y, COL_NOMBRES[1], C_ORO if i == 0 else C_BLANCO))
        poner(NPISOS + i, _texto(NPISOS + i, COL_PISOS[0], y, COL_PISOS[1], C_CELESTE))
        poner(TIEMPO + i, _texto(TIEMPO + i, COL_TIEMPO[0], y, COL_TIEMPO[1], C_BLANCO))
    poner(FONDO, _w('WND_CLASS_BASE', FONDO, 0, 0, W, H, ' icon="%d"' % I_FONDO))
    iconos = [_icono(I_FONDO, 'aolat_torre_fondo')]
    for iid, iid_on, nombre in ((I_SOLO, I_SOLO_ON, 'solo'), (I_PARTY, I_PARTY_ON, 'party')):
        iconos.append(_icono(iid, 'aolat_torre_%s_n' % nombre, 'aolat_torre_%s_f' % nombre,
                             'aolat_torre_%s_s' % nombre))
        iconos.append(_icono(iid_on, 'aolat_torre_%s_s' % nombre, 'aolat_torre_%s_s' % nombre,
                             'aolat_torre_%s_s' % nombre))
    for iid, nombre in ((I_ENTRAR, 'entrar'), (I_UNIRSE, 'unirse'), (I_SALIR, 'salir')):
        iconos.append(_icono(iid, 'aolat_torre_%s_n' % nombre, 'aolat_torre_%s_f' % nombre,
                             'aolat_torre_%s_s' % nombre))
    colores = ''.join('    <color id="%d" normal="%s" focus="%s" down="%s" disable="%s"/>\n'
                      % ((cid,) + (','.join(map(str, c)),) * 4) for cid, c in COLORES.items())
    cab = ('    <window class="WND_CLASS_DLG_1" range="0,0,%d,%d" id="%d" title="Tower of Babel" fcolor="104" '
           'font="1">\n        <style wsVisible="" wsMoveable="" />\n%s    </window>\n'
           % (W + 2 * MARCO_X, H + MARCO_Y + MARCO_ABAJO, VENTANA,
              ''.join('        <child>%d</child>\n' % c for c in hijos)))
    return '    <!-- %s -->\n%s%s%s%s    <!-- /%s -->\n' % (MARCA, colores, cab, ''.join(ventanas), ''.join(iconos),
                                                         MARCA)


# Las ventanas de la version de antes (tools/parche_subasta_ventana.TORRE), que se quitan.
VIEJAS = tuple(range(59020, 59028))


def wnd03(texto: str) -> str:
    """wnd03.xml con la ventana nueva (idempotente: quita la vieja y la suya antes de ponerla)."""
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = texto.replace('\r\n', '\n')
    texto = re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\n' % (MARCA, MARCA), '', texto, flags=re.S)
    for wid in VIEJAS:
        texto = re.sub(r'[ \t]*<window [^>]*\bid="%d"[^>]*>(?:(?!<window )[\s\S])*?</window>\n' % wid, '', texto)
    fin = texto.rindex('</root>')
    texto = texto[:fin] + bloque() + texto[fin:]
    return texto.replace('\n', nl)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, im in piezas().items():
        (SALIDA / (nombre + '.shp')).write_bytes(a_shp(im))
    crudo = WND03.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    WND03.write_bytes((b'\xef\xbb\xbf' if bom else b'') + wnd03(crudo.decode('utf-8-sig')).encode('utf-8'))
    print('ventana %d (%dx%d) y %d piezas listas' % (VENTANA, W, H, len(piezas())))


if __name__ == '__main__':
    main()
