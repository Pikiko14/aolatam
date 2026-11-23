"""La ventana del Angel MOBA (23/11/2026): elegir la clase del evento y apuntarse ("que se deba elegir que clase se
quiere jugar en ese evento"). Como las de Pet Defense (tools/ventana_pet_defense.py, de donde salen las piezas comunes):
un DLG_1 con su barra de titulo y el contenido es un fondo propio en una hija BASE, la ULTIMA de la lista.

  * 58300: el banner, la linea de la inscripcion, las 9 clases como tarjetas (su retrato del juego, nombre y papel; el
    clic la elige y ensena su ficha), la ficha (titulo, numeros, 4 poderes), lo elegido, el aviso, Join y Leave.
  * El boton de la barra es el 59006, a la izquierda del de Pet Defense (59005).

Ids: ventana y textos 58300..58339, iconos 58400..58429 (libres en wnd01/wnd03).

    python tools/ventana_moba.py [--vista CARPETA]
"""
import json
import pathlib
import re
import sys

from PIL import Image, ImageDraw, ImageEnhance

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import ventana_pet_defense as vp  # noqa: E402
from icono_subasta import ALTO, ANCHO, SALIDA, a_shp, al_estilo_nativo  # noqa: E402

CONFIG = RAIZ / 'server' / 'plantillas' / 'moba.json'
MARCA = 'aolat angel moba'

V_MOBA, L_ESTADO, L_TITULO, L_NUMEROS, L_PODER, L_AVISO, L_ELEGIDA = 58300, 58301, 58302, 58303, 58304, 58308, 58309
L_UNIRSE, L_DEJAR, L_FONDO, L_CLASE = 58310, 58311, 58312, 58320               # L_CLASE + 0..8
I_FONDO, I_UNIRSE, I_DEJAR, I_CLASE = 58400, 58401, 58402, 58410                # I_CLASE + 0..8
BOTON_BARRA, X_BARRA, Y_BARRA, NOMBRE_BOTON = 59006, 121, -127, 'aolat_mb'
N_CLASES = 9
# Fase 3: el marcador (58350) y el final (58360)
V_HUD, H_ARRIBA, H_ABAJO, H_FONDO = 58350, 58351, 58352, 58353
V_FIN, F_CARTEL, F_LINEA, F_CERRAR, F_FONDO = 58360, 58361, 58362, 58374, 58375          # F_LINEA + 0..11
I_HUD, I_FIN, I_VICTORIA, I_DERROTA, I_CERRAR = 58430, 58431, 58432, 58433, 58434
HW, HH = 420, 40
# Fase 4: el boton Ranking (en el banner) y la ventana del ranking (58380, filas en 58450..58499)
L_RANKING, I_RANKING, I_R_FONDO = 58313, 58435, 58436
V_RANKING, R_TITULO, R_MARCA, R_RANGOS, R_PREMIOS, R_VACIO, R_FONDO = range(58380, 58387)
R_PUESTO, R_NOMBRE, R_RANGO, R_PUNTOS, R_RECORD = 58450, 58460, 58470, 58480, 58490      # + 0..9
N_RANKING = 10
RW, RH = 420, 292
R_FILA0, R_PASO = 46, 18
R_COLS = ((12, 22), (36, 130), (170, 70), (244, 60), (306, 104))
RANKING_W, RANKING_H = 90, 22
# Los puntos de poder en la partida (58520): "debo irlos desbloqueando, que me de la opcion de cual" (23/11/2026)
V_PUNTOS, P_TITULO, P_ESTADO, P_NOMBRE, P_DETALLE, P_BOTON, P_FONDO = 58520, 58521, 58522, 58523, 58527, 58531, 58535
I_P_FONDO, I_ELEGIR = 58437, 58438
PW, PH = 380, 226
P_FILA0, P_PASO = 26, 44
P_ICONO = 58540                                       # P_ICONO + 0..3: el icono del poder de cada fila
I_PODER0 = 58600                                      # + clase x 4 + poder: el icono del juego de cada poder
P_BOTON_W, P_BOTON_H = 90, 24
# La tienda (58560): "que se puedan comprar items para mejorar los stats" (23/11/2026). Los iconos son los de los
# objetos del juego (el Lua los pone con game.getitemicon); aqui solo el marco de cada casilla.
V_TIENDA, T_TITULO, T_ESTADO, T_ITEM, T_NOMBRE, T_PRECIO, T_TEXTO = 58560, 58561, 58562, 58563, 58571, 58579, 58587
T_PROPIO, T_FONDO = 58595, 58601                      # T_PROPIO + 0..5
I_T_FONDO, I_T_CASILLA = 58439, 58440
TW, TH = 400, 284
T_CW, T_CH, T_PASO_X, T_PASO_Y, T_Y0 = 94, 88, 98, 94, 26
T_ICONO = 36
T_PROPIOS_Y = T_Y0 + 2 * T_PASO_Y + 4
FW, FH = 340, 280
CARTEL = (4, 4, FW - 4, 56)
CERRAR_XY = ((FW - 110) // 2, FH - 8 - 26)

MW, MH = 470, 386
BANNER = (4, 4, MW - 4, 60)
CW, CH, CPASO = 84, 74, 92
FILAS = (86, 166)
PANEL = (8, 248, MW - 8, 344)
BOTON_W, BOTON_H = 110, 26
DEJAR_XY = (MW - 8 - BOTON_W, MH - 8 - BOTON_H)
UNIRSE_XY = (DEJAR_XY[0] - 8 - BOTON_W, DEJAR_XY[1])
RANKING_XY = (MW - 4 - 10 - RANKING_W, 4 + 10)

ROL = {'Fighter': (249, 115, 22), 'Tank': (180, 136, 78), 'Marksman': (56, 189, 248), 'Assassin': (192, 132, 252),
       'Support': (251, 211, 104), 'Mage': (232, 121, 249), 'Controller': (74, 222, 128)}


def clases():
    return list(json.loads(CONFIG.read_text(encoding='utf-8'))['clases'].items())[:N_CLASES]


def posicion(i):
    if i < 5:
        return 8 + i * CPASO, FILAS[0]
    return 8 + CPASO // 2 + (i - 5) * CPASO, FILAS[1]


# ---------------------------------------------------------------------------------------------- dibujos
RETRATO = 42


def retrato(datos):
    """El retrato de la clase del propio juego: shape/skill/jobNN.shp del cliente (moba.json "icono"), con las
    esquinas redondeadas y su borde. "Usa los iconos de las clases del juego, no inventes" (23/11/2026)."""
    import fondos_interfaz as fi
    import shp_icon
    nombre = 'shape' + chr(92) + 'skill' + chr(92) + 'job%02d.shp' % int(datos['icono'])
    im = shp_icon.decode_shp_bytes(fi.del_cliente(nombre), front=False).convert('RGBA')
    im = im.resize((RETRATO, RETRATO), Image.LANCZOS)
    mascara = Image.new('L', im.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, RETRATO - 1, RETRATO - 1), radius=6, fill=255)
    im.putalpha(mascara)
    ImageDraw.Draw(im).rounded_rectangle((0, 0, RETRATO - 1, RETRATO - 1), radius=6, outline=(12, 16, 26, 255))
    return im


def tarjeta(clave, datos, foco=False):
    color = ROL.get(datos.get('rol'), vp.ACENTO)
    im = vp._degradado(CW, CH, tuple(int(v * 0.35) for v in color), vp.SUPERFICIE_2)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, CW - 1, CH - 1), radius=8, outline=vp._rgba(color if foco else vp.LINEA),
                        width=2 if foco else 1)
    if foco:
        im.alpha_composite(vp._resplandor(CW, CH, color, (CW // 2, 22), 30, 90))
    im.alpha_composite(retrato(datos), ((CW - RETRATO) // 2, 2))
    vp._texto_centrado(d, (0, 44, CW, 58), datos['nombre'], vp._fuente('segoeuib.ttf', 11), vp.BLANCO)
    vp._texto_centrado(d, (0, 58, CW, 71), datos.get('rol', ''), vp._fuente('segoeui.ttf', 10), color)
    return vp._redondear(im, 8, vp.FONDO_ABAJO)


def fondo():
    im = vp._degradado(MW, MH, vp.FONDO_ARRIBA, vp.FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, MW - 1, MH - 1), outline=vp._rgba(vp.LINEA))
    w, h = BANNER[2] - BANNER[0], BANNER[3] - BANNER[1]
    b = vp._degradado(w, h, (70, 24, 34), (22, 26, 60))
    b.alpha_composite(vp._resplandor(w, h, (248, 113, 113), (70, h // 2), 60, 120))
    b.alpha_composite(vp._resplandor(w, h, (96, 165, 250), (w - 70, h // 2), 60, 120))
    vp._titulo(b, (16, 4), 'ANGEL MOBA', 26, vp.BLANCO)
    ImageDraw.Draw(b).text((18, 36), '5 vs 5  -  three lanes  -  destroy the enemy statue', font=vp._fuente('segoeui.ttf', 12),
                          fill=(226, 232, 240, 255))
    ImageDraw.Draw(b).rounded_rectangle((0, 0, w - 1, h - 1), radius=8, outline=vp._rgba(vp.LINEA))
    im.alpha_composite(vp._redondear(b, 8, vp.FONDO_ARRIBA), BANNER[:2])
    d.rounded_rectangle(PANEL, radius=8, fill=vp._rgba(vp.SUPERFICIE_2), outline=vp._rgba(vp.LINEA))
    return im


def fondo_ranking():
    im = vp._degradado(RW, RH, vp.FONDO_ARRIBA, vp.FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, RW - 1, RH - 1), outline=vp._rgba(vp.LINEA))
    d.rounded_rectangle((6, 22, RW - 7, R_FILA0 - 4), radius=6, fill=vp._rgba(vp.SUPERFICIE))
    f = vp._fuente('segoeuib.ttf', 11)
    for (x, _w), texto in zip(R_COLS, ('#', 'Hero', 'Rank', 'Points', 'Record')):
        d.text((x, 25), texto, font=f, fill=vp.TENUE)
    for i in range(N_RANKING):
        if i % 2:
            y = R_FILA0 + R_PASO * i
            d.rectangle((6, y, RW - 7, y + R_PASO - 1), fill=vp._rgba(vp.SUPERFICIE_2))
    return im


def boton_ranking(fondo_ventana, estado):
    """El boton Ranking dibujado sobre el trozo del banner que tiene detras (con un fondo liso se veia un rectangulo
    encima del banner, 23/11/2026)."""
    x, y = RANKING_XY
    im = fondo_ventana.crop((x, y, x + RANKING_W, y + RANKING_H)).convert('RGBA')
    relleno, borde = {'n': (vp.ACENTO_OSCURO, vp.ACENTO), 'f': ((16, 150, 110), (170, 245, 215)),
                      's': (vp.ACENTO_HUNDIDO, vp.ACENTO)}[estado]
    k = 4                                            # a 4 aumentos, para que el borde redondo quede suave
    capa = Image.new('RGBA', (RANKING_W * k, RANKING_H * k), (0, 0, 0, 0))
    ImageDraw.Draw(capa).rounded_rectangle((0, 0, RANKING_W * k - 1, RANKING_H * k - 1), radius=RANKING_H * k // 2,
                                           fill=vp._rgba(relleno), outline=vp._rgba(borde), width=k)
    im.alpha_composite(capa.resize((RANKING_W, RANKING_H), Image.LANCZOS))
    o = 1 if estado == 's' else 0
    vp._texto_centrado(ImageDraw.Draw(im), (0, o, RANKING_W, RANKING_H + o), 'Ranking', vp._fuente('segoeuib.ttf', 11),
                       vp.BLANCO)
    return im


def iconos_poder():
    """{nombre de la pieza: bytes del .shp}: el icono de cada poder TAL CUAL lo trae el cliente (介面圖號 de magic ->
    skillicon.xml -> shape/skill/*.shp). "Que se vea el icono del poder al aprenderlo" (23/11/2026)."""
    import sqlite3
    import fondos_interfaz as fi
    xml = fi.del_cliente('setting' + chr(92) + 'skillicon.xml').decode('utf-8', 'replace')
    mapa = {int(m.group(1)): (m.group(2), m.group(3))
            for m in re.finditer(r'<icon id="(\d+)" dir="([^"]*)" normal="([^"]*)"', xml)}
    con = sqlite3.connect(RAIZ / 'corpus' / 'content.db')
    out = {}
    try:
        for _clave, datos in clases():
            for p in datos['poderes']:
                ic = int(con.execute('SELECT "介面圖號" FROM magic WHERE id=?', (str(p['id']),)).fetchone()[0])
                carpeta, nombre = mapa[ic]
                out['aolat_mb_sk%d' % int(p['id'])] = fi.del_cliente('shape' + carpeta.rstrip(chr(92)) + chr(92) + nombre + '.shp')
    finally:
        con.close()
    return out


def fondo_puntos():
    im = vp._degradado(PW, PH, vp.FONDO_ARRIBA, vp.FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, PW - 1, PH - 1), outline=vp._rgba(vp.LINEA))
    for k in range(4):
        y = P_FILA0 + P_PASO * k
        d.rounded_rectangle((6, y, PW - 7, y + P_PASO - 5), radius=6,
                            fill=vp._rgba(vp.SUPERFICIE if k < 3 else (52, 40, 20)), outline=vp._rgba(vp.LINEA))
        d.rectangle((10, y + 2, 10 + 37, y + 2 + 37), fill=(10, 14, 24, 255), outline=vp._rgba(vp.LINEA))
    return im


def fondo_tienda():
    im = vp._degradado(TW, TH, vp.FONDO_ARRIBA, vp.FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, TW - 1, TH - 1), outline=vp._rgba(vp.LINEA))
    for i in range(8):
        x, y = 6 + (i % 4) * T_PASO_X, T_Y0 + (i // 4) * T_PASO_Y
        d.rounded_rectangle((x, y, x + T_CW - 1, y + T_CH - 1), radius=8, fill=vp._rgba(vp.SUPERFICIE),
                            outline=vp._rgba(vp.LINEA))
        cx = x + (T_CW - T_ICONO) // 2
        d.rounded_rectangle((cx - 2, y + 3, cx + T_ICONO + 1, y + T_ICONO + 6), radius=4, fill=(10, 14, 24, 255),
                            outline=vp._rgba(vp.LINEA))
    d.text((10, T_PROPIOS_Y + 12), 'Your items', font=vp._fuente('segoeuib.ttf', 12), fill=vp.TENUE)
    for k in range(6):
        x = 96 + k * 46
        d.rounded_rectangle((x - 2, T_PROPIOS_Y - 2 + 2, x + T_ICONO + 1, T_PROPIOS_Y + T_ICONO + 3), radius=4,
                            fill=(10, 14, 24, 255), outline=vp._rgba(vp.LINEA))
    return im


def fondo_hud():
    im = vp._degradado(HW, HH, vp.FONDO_ARRIBA, vp.FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, HW - 1, HH - 1), outline=vp._rgba(vp.LINEA))
    d.rectangle((1, 1, 5, HH - 2), fill=(204, 64, 82, 255))
    d.rectangle((HW - 6, 1, HW - 2, HH - 2), fill=(59, 130, 246, 255))
    return im


def fondo_fin():
    im = vp._degradado(FW, FH, vp.FONDO_ARRIBA, vp.FONDO_ABAJO)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, FW - 1, FH - 1), outline=vp._rgba(vp.LINEA))
    d.rounded_rectangle((8, CARTEL[3] + 6, FW - 9, CERRAR_XY[1] - 6), radius=8, fill=vp._rgba(vp.SUPERFICIE_2),
                        outline=vp._rgba(vp.LINEA))
    return im


def cartel(texto, color, arriba, abajo):
    w, h = CARTEL[2] - CARTEL[0], CARTEL[3] - CARTEL[1]
    im = vp._degradado(w, h, arriba, abajo)
    im.alpha_composite(vp._resplandor(w, h, color, (w // 2, h // 2), 40))
    f = vp._fuente('segoeuib.ttf', 26)
    bx0, by0, bx1, by1 = ImageDraw.Draw(im).textbbox((0, 0), texto, font=f)
    vp._titulo(im, ((w - (bx1 - bx0)) // 2 - bx0, (h - (by1 - by0)) // 2 - by0 - 1), texto, 26, vp.BLANCO)
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=8, outline=vp._rgba(color))
    return vp._redondear(im, 8, vp.FONDO_ARRIBA)


def icono_barra():
    """El icono de la barra (40x56): dos espadas cruzadas sobre un escudo rojo y azul."""
    k = 4
    im = Image.new('RGBA', (ANCHO * k, ALTO * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    borde = (20, 24, 40, 255)

    def r(*xy):
        return [v * k for v in xy]
    d.polygon(r(6, 10, 20, 6, 20, 48, 6, 34), fill=(204, 64, 82, 255), outline=borde, width=k)
    d.polygon(r(20, 6, 34, 10, 34, 34, 20, 48), fill=(59, 130, 246, 255), outline=borde, width=k)
    for a, b in (((8, 40), (32, 14)), ((32, 40), (8, 14))):
        d.line(r(*a, *b), fill=(240, 246, 252, 255), width=3 * k)
    d.ellipse(r(16, 23, 24, 31), fill=(251, 211, 104, 255), outline=borde, width=k)
    return im.resize((ANCHO, ALTO), Image.LANCZOS)


def piezas() -> dict:
    p = {'aolat_mb_fondo': fondo()}
    for i, (clave, datos) in enumerate(clases()):
        p['aolat_mb_c%d_n' % i] = tarjeta(clave, datos)
        p['aolat_mb_c%d_f' % i] = tarjeta(clave, datos, foco=True)
    for e in 'nfs':
        p['aolat_mb_unirse_%s' % e] = vp.boton('Join', e)
        p['aolat_mb_dejar_%s' % e] = vp.boton('Leave queue', e, rojo=True)
    p['aolat_mb_rfondo'] = fondo_ranking()
    for e in 'nfs':
        p['aolat_mb_ranking_%s' % e] = boton_ranking(p['aolat_mb_fondo'], e)
    p['aolat_mb_pfondo'] = fondo_puntos()
    for e in 'nfs':
        p['aolat_mb_elegir_%s' % e] = vp.boton('Choose', e, P_BOTON_W, P_BOTON_H, fondo=vp.SUPERFICIE, tam=11)
    p['aolat_mb_tfondo'] = fondo_tienda()
    p['aolat_mb_casilla'] = Image.new('RGBA', (T_ICONO, T_ICONO), (10, 14, 24, 255))
    p['aolat_mb_hud'] = fondo_hud()
    p['aolat_mb_fin'] = fondo_fin()
    p['aolat_mb_victoria'] = cartel('VICTORY!', vp.ORO, (60, 44, 10), (24, 18, 6))
    p['aolat_mb_derrota'] = cartel('DEFEAT', vp.ROJO_CLARO, (60, 14, 20), (24, 6, 10))
    for e in 'nfs':
        p['aolat_mb_cerrar_%s' % e] = vp.boton('Close', e)
    normal = al_estilo_nativo(icono_barra())
    p[NOMBRE_BOTON + '_n'] = normal
    p[NOMBRE_BOTON + '_f'] = ImageEnhance.Brightness(normal).enhance(1.25)
    return p


# ---------------------------------------------------------------------------------------------- el XML
def bloque() -> str:
    hijos = [(L_RANKING, vp._boton(L_RANKING, RANKING_XY[0], RANKING_XY[1], RANKING_W, RANKING_H, I_RANKING,
                                   'OnMBRanking', 'Season ranking and rewards')),
             (L_UNIRSE, vp._boton(L_UNIRSE, UNIRSE_XY[0], UNIRSE_XY[1], BOTON_W, BOTON_H, I_UNIRSE, 'OnMBUnirse',
                                  'Sign up with the selected class')),
             (L_DEJAR, vp._boton(L_DEJAR, DEJAR_XY[0], DEJAR_XY[1], BOTON_W, BOTON_H, I_DEJAR, 'OnMBDejar',
                                 'Leave the sign-up queue')),
             (L_ESTADO, vp._texto(L_ESTADO, 10, 66, MW - 20, vp.C_ORO)),
             (L_TITULO, vp._texto(L_TITULO, PANEL[0] + 8, PANEL[1] + 4, PANEL[2] - PANEL[0] - 16, vp.C_BLANCO)),
             (L_NUMEROS, vp._texto(L_NUMEROS, PANEL[0] + 8, PANEL[1] + 20, PANEL[2] - PANEL[0] - 16, vp.C_ACENTO))]
    for k in range(4):
        hijos.append((L_PODER + k, vp._texto(L_PODER + k, PANEL[0] + 8, PANEL[1] + 38 + 14 * k, PANEL[2] - PANEL[0] - 16,
                                             vp.C_ORO if k == 3 else vp.C_BLANCO)))
    hijos += [(L_ELEGIDA, vp._texto(L_ELEGIDA, 10, UNIRSE_XY[1] - 2, UNIRSE_XY[0] - 18, vp.C_ACENTO)),
              (L_AVISO, vp._texto(L_AVISO, 10, UNIRSE_XY[1] + 13, UNIRSE_XY[0] - 18, vp.C_ORO))]
    for i in range(len(clases())):
        x, y = posicion(i)
        hijos.append((L_CLASE + i, vp._boton(L_CLASE + i, x, y, CW, CH, I_CLASE + i, 'OnMBClase%d' % (i + 1))))
    hijos.append((L_FONDO, vp._w('WND_CLASS_BASE', L_FONDO, 0, 0, MW, MH, ' icon="%d"' % I_FONDO)))
    xml = [vp._dlg(V_MOBA, 'Angel MOBA', MW, MH, [c for c, _ in hijos])] + [x for _, x in hijos]
    iconos = [vp._icono(I_FONDO, 'aolat_mb_fondo'),
              vp._icono(I_UNIRSE, 'aolat_mb_unirse_n', 'aolat_mb_unirse_f', 'aolat_mb_unirse_s'),
              vp._icono(I_DEJAR, 'aolat_mb_dejar_n', 'aolat_mb_dejar_f', 'aolat_mb_dejar_s')]
    # el marcador y el final
    hud = [(H_ARRIBA, vp._texto(H_ARRIBA, 12, 4, HW - 24, vp.C_BLANCO, '', ' ssHCenter=""')),
           (H_ABAJO, vp._texto(H_ABAJO, 12, 21, HW - 24, vp.C_ORO, '', ' ssHCenter=""')),
           (H_FONDO, vp._w('WND_CLASS_BASE', H_FONDO, 0, 0, HW, HH, ' icon="%d"' % I_HUD))]
    xml += [vp._dlg(V_HUD, 'Angel MOBA', HW, HH, [c for c, _ in hud])] + [x for _, x in hud]
    fin = [(F_CERRAR, vp._boton(F_CERRAR, CERRAR_XY[0], CERRAR_XY[1], BOTON_W, BOTON_H, I_CERRAR, 'OnMBFinCerrar'))]
    for k in range(12):
        fin.append((F_LINEA + k, vp._texto(F_LINEA + k, 16, CARTEL[3] + 10 + 14 * k, FW - 32,
                                           vp.C_ACENTO if k in (0, 6) else vp.C_BLANCO)))
    fin += [(F_CARTEL, vp._w('WND_CLASS_BUTTON', F_CARTEL, CARTEL[0], CARTEL[1], CARTEL[2] - CARTEL[0],
                             CARTEL[3] - CARTEL[1], ' title="" icon="%d"' % I_VICTORIA)),
            (F_FONDO, vp._w('WND_CLASS_BASE', F_FONDO, 0, 0, FW, FH, ' icon="%d"' % I_FIN))]
    xml += [vp._dlg(V_FIN, 'Angel MOBA', FW, FH, [c for c, _ in fin])] + [x for _, x in fin]
    rk = [(R_TITULO, vp._texto(R_TITULO, 10, 4, RW - 20, vp.C_BLANCO)),
          (R_VACIO, vp._texto(R_VACIO, 14, R_FILA0 + R_PASO * 3, RW - 28, vp.C_TENUE,
                              'No games yet this season. Be the first!', ' ssHCenter=""'))]
    for i in range(N_RANKING):
        y = R_FILA0 + R_PASO * i + 1
        puesto = (vp.C_ORO, vp.C_BLANCO, vp.C_ORO)[i] if i < 3 else vp.C_TENUE
        for base, (x, w), color in ((R_PUESTO, R_COLS[0], puesto), (R_NOMBRE, R_COLS[1], vp.C_ORO if i == 0 else vp.C_BLANCO),
                                    (R_RANGO, R_COLS[2], vp.C_ACENTO), (R_PUNTOS, R_COLS[3], vp.C_BLANCO),
                                    (R_RECORD, R_COLS[4], vp.C_TENUE)):
            rk.append((base + i, vp._texto(base + i, x, y, w, color)))
    yb = R_FILA0 + R_PASO * N_RANKING + 12
    rk += [(R_MARCA, vp._texto(R_MARCA, 10, yb, RW - 20, vp.C_ORO)),
           (R_RANGOS, vp._texto(R_RANGOS, 10, yb + 16, RW - 20, vp.C_TENUE)),
           (R_PREMIOS, vp._texto(R_PREMIOS, 10, yb + 32, RW - 20, vp.C_ACENTO)),
           (R_FONDO, vp._w('WND_CLASS_BASE', R_FONDO, 0, 0, RW, RH, ' icon="%d"' % I_R_FONDO))]
    xml += [vp._dlg(V_RANKING, 'Angel MOBA ranking', RW, RH, [c for c, _ in rk])] + [x for _, x in rk]
    pu = [(P_TITULO, vp._texto(P_TITULO, 10, 5, PW - 20, vp.C_ORO))]
    for k in range(4):
        y = P_FILA0 + P_PASO * k
        pu += [(P_BOTON + k, vp._boton(P_BOTON + k, PW - 12 - P_BOTON_W, y + 7, P_BOTON_W, P_BOTON_H, I_ELEGIR,
                                       'OnMBPunto%d' % (k + 1), 'Spend a skill point here')),
               (P_ICONO + k, vp._w('WND_CLASS_BUTTON', P_ICONO + k, 11, y + 3, 36, 36, ' title="" icon="%d"' % I_PODER0)),
               (P_NOMBRE + k, vp._texto(P_NOMBRE + k, 54, y + 5, PW - P_BOTON_W - 74, vp.C_BLANCO if k < 3 else vp.C_ORO)),
               (P_DETALLE + k, vp._texto(P_DETALLE + k, 54, y + 21, PW - P_BOTON_W - 74, vp.C_ACENTO))]
    pu += [(P_ESTADO, vp._texto(P_ESTADO, 10, PH - 18, PW - 20, vp.C_ROJO)),
           (P_FONDO, vp._w('WND_CLASS_BASE', P_FONDO, 0, 0, PW, PH, ' icon="%d"' % I_P_FONDO))]
    xml += [vp._dlg(V_PUNTOS, 'Skill points', PW, PH, [c for c, _ in pu])] + [x for _, x in pu]
    k = 0
    for _clave, datos in clases():
        for p in datos['poderes']:
            iconos.append(vp._icono(I_PODER0 + k, 'aolat_mb_sk%d' % int(p['id'])))
            k += 1
    iconos += [vp._icono(I_P_FONDO, 'aolat_mb_pfondo'),
               vp._icono(I_ELEGIR, 'aolat_mb_elegir_n', 'aolat_mb_elegir_f', 'aolat_mb_elegir_s')]
    ti = [(T_TITULO, vp._texto(T_TITULO, 10, 5, TW - 20, vp.C_ORO))]
    for i in range(8):
        x, y = 6 + (i % 4) * T_PASO_X, T_Y0 + (i // 4) * T_PASO_Y
        ti += [(T_ITEM + i, vp._boton(T_ITEM + i, x + (T_CW - T_ICONO) // 2, y + 5, T_ICONO, T_ICONO, I_T_CASILLA,
                                      'OnMBComprar%d' % (i + 1), 'Buy')),
               (T_NOMBRE + i, vp._texto(T_NOMBRE + i, x + 3, y + 44, T_CW - 6, vp.C_BLANCO, '', ' ssHCenter=""')),
               (T_TEXTO + i, vp._texto(T_TEXTO + i, x + 3, y + 58, T_CW - 6, vp.C_ACENTO, '', ' ssHCenter=""')),
               (T_PRECIO + i, vp._texto(T_PRECIO + i, x + 3, y + 72, T_CW - 6, vp.C_ORO, '', ' ssHCenter=""'))]
    for k in range(6):
        ti.append((T_PROPIO + k, vp._w('WND_CLASS_BUTTON', T_PROPIO + k, 96 + k * 46, T_PROPIOS_Y + 2, T_ICONO, T_ICONO,
                                        ' title="" icon="%d"' % I_T_CASILLA)))
    ti += [(T_ESTADO, vp._texto(T_ESTADO, 10, TH - 20, TW - 20, vp.C_ORO)),
           (T_FONDO, vp._w('WND_CLASS_BASE', T_FONDO, 0, 0, TW, TH, ' icon="%d"' % I_T_FONDO))]
    xml += [vp._dlg(V_TIENDA, 'Angel MOBA shop', TW, TH, [c for c, _ in ti])] + [x for _, x in ti]
    iconos += [vp._icono(I_T_FONDO, 'aolat_mb_tfondo'), vp._icono(I_T_CASILLA, 'aolat_mb_casilla')]
    iconos += [vp._icono(I_R_FONDO, 'aolat_mb_rfondo'),
               vp._icono(I_RANKING, 'aolat_mb_ranking_n', 'aolat_mb_ranking_f', 'aolat_mb_ranking_s')]
    iconos += [vp._icono(I_HUD, 'aolat_mb_hud'), vp._icono(I_FIN, 'aolat_mb_fin'),
               vp._icono(I_VICTORIA, 'aolat_mb_victoria'), vp._icono(I_DERROTA, 'aolat_mb_derrota'),
               vp._icono(I_CERRAR, 'aolat_mb_cerrar_n', 'aolat_mb_cerrar_f', 'aolat_mb_cerrar_s')]
    for i in range(len(clases())):
        iconos.append(vp._icono(I_CLASE + i, 'aolat_mb_c%d_n' % i, 'aolat_mb_c%d_f' % i, 'aolat_mb_c%d_f' % i))
    return '    <!-- %s -->\n%s%s    <!-- /%s -->\n' % (MARCA, ''.join(xml), ''.join(iconos), MARCA)


def _quitar_marca(texto):
    return re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\n' % (MARCA, MARCA), '', texto, flags=re.S)


def wnd03(texto: str) -> str:
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = _quitar_marca(texto.replace('\r\n', '\n'))
    fin = texto.rindex('</root>')
    return (texto[:fin] + bloque() + texto[fin:]).replace('\n', nl)


def wnd01(texto: str) -> str:
    """El boton en la barra, a la izquierda del de Pet Defense (idempotente)."""
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = _quitar_marca(texto.replace('\r\n', '\n'))
    texto = re.sub(r'\n[ \t]*<child>%d</child>' % BOTON_BARRA, '', texto)
    m = re.search(r'([ \t]*)<child>%d</child>' % vp.BOTON_BARRA, texto)
    if not m:
        raise SystemExit('no esta el boton de Pet Defense (%d) en wnd01.xml' % vp.BOTON_BARRA)
    texto = texto[:m.end()] + '\n' + m.group(1) + '<child>%d</child>' % BOTON_BARRA + texto[m.end():]
    boton_xml = ('    <!-- %s -->\n' % MARCA
                 + '    <window class="WND_CLASS_BUTTON" range="%d,%d,40,56" id="%d" icon="%d" tooltip="10043" '
                   'tooltext="Angel MOBA">\n        <style wsVisible="" wsTab="" />\n'
                   '        <OnCommand>OnCommandMoba</OnCommand>\n    </window>\n'
                   % (X_BARRA, Y_BARRA, BOTON_BARRA, BOTON_BARRA)
                 + '    <icon id="%d" dir="\\wnd01\\" normal="%s_n" focus="%s_f" down="%s_n" disable="normal" />\n'
                   % (BOTON_BARRA, NOMBRE_BOTON, NOMBRE_BOTON, NOMBRE_BOTON)
                 + '    <!-- /%s -->\n' % MARCA)
    fin = texto.rindex('</root>')
    return (texto[:fin] + boton_xml + texto[fin:]).replace('\n', nl)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--vista', help='carpeta donde dejar las piezas en .png para mirarlas')
    a = ap.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)
    p = piezas()
    for nombre, im in p.items():
        (SALIDA / (nombre + '.shp')).write_bytes(a_shp(im))
    crudos = iconos_poder()
    for nombre, datos in crudos.items():               # los del juego, sin tocar
        (SALIDA / (nombre + '.shp')).write_bytes(datos)
        if a.vista:
            pathlib.Path(a.vista).mkdir(parents=True, exist_ok=True)
            im.save(pathlib.Path(a.vista) / (nombre + '.png'))
    vp._reescribir(vp.ENG / 'wnd03.xml', wnd03)
    vp._reescribir(vp.ENG / 'wnd01.xml', wnd01)
    print('Angel MOBA: %d piezas, %d iconos de poder, %d clases' % (len(p), len(crudos), len(clases())))


if __name__ == '__main__':
    main()
