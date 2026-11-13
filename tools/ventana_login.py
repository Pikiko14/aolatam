"""La ventana de servidor e inicio de sesion, mas bonita (12/11/2026: "podemos cambiar y hacer mas gustoso el cliente de
acceso?? o sea el selector de server e inicio de sesion").

Es la 2529 de wnd02.xml (WND_CLASS_DLG_1, 189x299 con el marco): la lista de servidores 2706 (2,2,177,207), "ID" y
"PW" (2701/2703) con sus casillas 2702/2704, la de recordar la cuenta 2528 y los botones 2705 (entrar) y 2523 (salir).
Su interior es el icono 2529, shape/log/w038_03.shp (181x275, 16 bits), con ICON_ATTRIB_THEME: el cliente lo tine
con el color del tema y por eso salia verde azulado.

Aqui, a juego con el launcher y su emblema (azul noche, oro y gemas):
  * w038_03.shp nuevo: panel azul noche con estrellas, marco de oro, el recuadro de la lista con su cabecera
    ("SERVER / STATUS") y franjas por fila, y los de ID y PW como casillas hundidas con borde de oro;
  * el icono 2529 sin ICON_ATTRIB_THEME (sus colores tal cual) y la lista 2706 sin bcolor (transparente: se ve el panel);
  * los botones 2705 y 2523 con texto ("Login" / "Exit") y un icono propio de cristal azul con marco de oro
    (aolat_login_btn_n/f/s, iconos 60460/60461), mas anchos y centrados;
  * el titulo, "Angels Online Forever".

    python tools/ventana_login.py
    python tools/generar_parche.py
"""
import pathlib
import random
import re
import sys

from PIL import Image, ImageDraw, ImageFilter

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import fondos_interfaz as fi  # noqa: E402
from icono_subasta import a_shp  # noqa: E402

EXTRAS = RAIZ / 'parches' / 'extras'
LOG = EXTRAS / 'shape' / 'log'
WND01 = EXTRAS / 'shape' / 'wnd01'
W, H = 181, 275
# 12/11/2026, "deja un poco de margin-top entre los botones y el password y que se vea el checkbox de guardar
# usuario": la lista 8 px mas corta y la cuenta 8 px mas arriba, para que entre PW y los botones quede aire; y la
# casilla de recordar la cuenta (2528) con su recuadro y el rotulo "Save" debajo.
SUBE = 8
LISTA = (2, 2, 179, 209 - SUBE)          # la 2706 (2,2,177,207 - SUBE)
ID, PW = (37, 217 - SUBE, 150, 231 - SUBE), (37, 235 - SUBE, 150, 249 - SUBE)
CASILLA = (153, 216 - SUBE, 14)          # la 2528: x, y, lado
CUENTA = (3, 212 - SUBE, W - 3, 252 - SUBE)
# Las ventanas que se mueven (id: x, y, ancho, alto)
MOVER = {2706: (2, 2, 177, 207 - SUBE), 2701: (9, 219 - SUBE, 1, 1), 2702: (37, 217 - SUBE, 113, 14),
         2703: (9, 237 - SUBE, 1, 1), 2704: (37, 235 - SUBE, 113, 14), 2528: (CASILLA[0], CASILLA[1], 14, 14)}
BOTON_W, BOTON_H = 66, 18
# El juego no pinta el titulo de estos dos botones: el texto va dibujado en su icono (uno por boton).
BOTONES = {2705: (14, 254, 'Login', 60460), 2523: (101, 254, 'Exit', 60461)}
TITULO = 'Angels Online Forever'
# La textura de las celdas de las listas (bcolor): transparente, del tamano de la del cliente (wnd01/w012_1, 265x235).
ICONO_CELDAS, ARCHIVO_CELDAS = 60464, 'aolat_login_celdas'
MARCA = 'aolat login'

ORO = (238, 196, 92)
ORO_OSCURO = (150, 100, 34)
NOCHE = (10, 22, 64)
NOCHE_HONDA = (6, 12, 38)


def _degradado(w, h, arriba, abajo):
    im = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line((0, y, w, y), fill=tuple(int(arriba[i] + (abajo[i] - arriba[i]) * t) for i in range(3)) + (255,))
    return im


def fondo() -> Image.Image:
    im = _degradado(W, H, (26, 52, 128), NOCHE_HONDA)
    # un resplandor azul arriba y estrellas
    brillo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse((-40, -60, W + 40, 90), fill=(90, 170, 255, 70))
    im.alpha_composite(brillo.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(im)
    rnd = random.Random(2529)
    for _ in range(55):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        c = rnd.choice(((255, 236, 180), (210, 230, 255), (255, 255, 255)))
        d.point((x, y), fill=c + (rnd.randint(120, 255),))
    # el recuadro de la lista, hundido y limpio (la lista no tiene cabecera y no se sabe a que alto pinta cada fila:
    # unas franjas pintadas no casarian con sus filas)
    x0, y0, x1, y1 = LISTA
    d.rounded_rectangle((x0, y0, x1, y1), radius=5, fill=NOCHE_HONDA + (235,), outline=ORO_OSCURO, width=1)
    d.line((x0 + 4, y0 + 1, x1 - 4, y0 + 1), fill=(60, 110, 200, 255))
    # el emblema del launcher de marca de agua, tenue, en la parte baja de la lista (con un servidor queda vacia)
    emblema = Image.open(RAIZ / 'launcher' / 'emblema.png').convert('RGBA')
    lado = 120
    emblema = emblema.resize((lado, round(emblema.height * lado / emblema.width)), Image.LANCZOS)
    emblema.putalpha(emblema.getchannel('A').point(lambda a: a * 30 // 100))
    im.alpha_composite(emblema, ((x0 + x1 - lado) // 2, y1 - emblema.height - 18))
    d = ImageDraw.Draw(im)
    # la zona de la cuenta: una franja con borde de oro, y ID / PW como casillas hundidas
    d.rounded_rectangle(CUENTA, radius=5, fill=(14, 28, 74, 255), outline=ORO_OSCURO)
    for (a, b, c, e) in (ID, PW):
        d.rectangle((a - 1, b - 1, c + 1, e + 1), fill=(4, 8, 26, 255), outline=ORO)
        d.line((a, b, c, b), fill=(0, 0, 10, 255))
    # la casilla de recordar la cuenta: hundida con borde de oro (el tic lo pinta el juego) y "Save" debajo
    cx, cy, lado = CASILLA
    d.rectangle((cx - 1, cy - 1, cx + lado, cy + lado), fill=(4, 8, 26, 255), outline=ORO)
    _rotulo(d, 'Save', cx + lado // 2, PW[1] + 1)
    # la franja de los botones
    d.line((8, 252 - 1, W - 9, 252 - 1), fill=ORO_OSCURO)
    # el marco de oro de todo el panel, doble
    d.rectangle((0, 0, W - 1, H - 1), outline=ORO)
    d.rectangle((1, 1, W - 2, H - 2), outline=ORO_OSCURO)
    return im


def celdas() -> Image.Image:
    """La textura de las celdas de las listas (su bcolor): azul noche con un brillo suave arriba. Transparente no
    sirve: el juego marca la fila elegida tinendo esta textura, y sin textura no se distinguia ("no se distingue el
    canal seleccionado", 12/11/2026)."""
    im = _degradado(265, 235, (24, 46, 112), (12, 24, 66))
    d = ImageDraw.Draw(im)
    rnd = random.Random(60464)
    for _ in range(90):
        x, y = rnd.uniform(0, 265), rnd.uniform(0, 235)
        d.point((x, y), fill=(120, 150, 220, 255))
    return im


def _letra(tam=9):
    from PIL import ImageFont
    try:
        return ImageFont.truetype('tahomabd.ttf', tam)
    except OSError:
        return ImageFont.load_default()


def _rotulo(d, texto, cx, y, color=(238, 210, 140, 255), tam=9):
    """Texto nitido (sin suavizado) centrado en cx, con contorno oscuro."""
    d.fontmode = '1'
    f = _letra(tam)
    caja = d.textbbox((0, 0), texto, font=f)
    x = cx - (caja[2] - caja[0]) // 2 - caja[0]
    y -= caja[1]
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        d.text((x + dx, y + dy), texto, font=f, fill=(4, 8, 26, 255))
    d.text((x, y), texto, font=f, fill=color)


def boton(estado, texto='') -> Image.Image:
    """66x18: cristal azul (mas claro con el raton encima, hundido al pulsar) con marco de oro, una gema a cada lado
    y el texto en blanco con sombra."""
    arriba, abajo = {'n': ((70, 150, 245), (18, 50, 150)), 'f': ((120, 195, 255), (36, 86, 200)),
                     's': ((18, 50, 150), (60, 130, 230))}[estado]
    im = Image.new('RGBA', (BOTON_W, BOTON_H), (0, 0, 0, 0))
    cuerpo = _degradado(BOTON_W, BOTON_H, arriba, abajo)
    mascara = Image.new('L', (BOTON_W, BOTON_H), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, BOTON_W - 1, BOTON_H - 1), radius=5, fill=255)
    im.paste(cuerpo, (0, 0), mascara)
    reflejo = Image.new('RGBA', im.size, (0, 0, 0, 0))     # mezclado: pintado encima dejaba esos pixeles casi transparentes
    ImageDraw.Draw(reflejo).rounded_rectangle((2, 2, BOTON_W - 3, BOTON_H // 2), radius=3,
                                              fill=(255, 255, 255, 50 if estado != 's' else 15))
    im = Image.alpha_composite(im, reflejo)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, BOTON_W - 1, BOTON_H - 1), radius=5, outline=ORO, width=1)
    for cx in (4, BOTON_W - 5):
        cy = BOTON_H // 2
        d.polygon(((cx, cy - 4), (cx + 3, cy), (cx, cy + 4), (cx - 3, cy)), fill=(150, 230, 255, 255), outline=ORO)
    if texto:
        # Nitido (12/11/2026, "que se vean mas nitidos los botones"): letra recta sin suavizado (pixel exacto, sin
        # medios tonos que la paleta del juego emborrona) con un contorno oscuro de 1 px.
        from PIL import ImageFont
        try:
            f = ImageFont.truetype('tahomabd.ttf', 11)
        except OSError:
            f = ImageFont.load_default()
        d.fontmode = '1'
        caja = d.textbbox((0, 0), texto, font=f)
        x = (BOTON_W - (caja[2] - caja[0])) // 2 - caja[0]
        y = (BOTON_H - (caja[3] - caja[1])) // 2 - caja[1] + (1 if estado == 's' else 0)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
            d.text((x + dx, y + dy), texto, font=f, fill=(6, 16, 60, 255))
        d.text((x, y), texto, font=f, fill=(255, 250, 230, 255))
    return im


# EL SELECTOR DE CANAL (12/11/2026, "rehaz el selector de canal siguiendo la linea grafica nueva" y luego "plantea otro
# diseno y distribucion"): la 2530 de wnd02.xml, "Choose game branch". Era una columna alta (181x275) con la lista y la
# leyenda apiladas; ahora es una tarjeta apaisada de CW x CH:
#   arriba, una cabecera con el emblema pequeno y "Select your channel";
#   en medio, los canales en filas anchas: la columna de estado 2699 y la lista 2531, de FILAS_CANAL filas;
#   abajo, la leyenda de capacidad en una linea (cuadros 2695..2698 y textos 2691..2694, "Normal"...) y los botones
#   2532 (Enter) y 2533 (Back) a la derecha.
# Su interior es el icono 2530 (log/w038_22), sin el tinte del tema.
CW, CH = 300, 204                       # 8 px mas: margen sobre los botones ("los botones tengan algo de margin top")
FILA_CANAL, FILAS_CANAL = 19, 5
CABECERA_CANAL = (0, 0, CW, 38)
CANAL_MARCO = (6, 42, CW - 6, 42 + 8 + FILA_CANAL * FILAS_CANAL)            # 6,42 .. 294,145
CANAL_ESTADO = (12, 46, 18, FILA_CANAL * FILAS_CANAL)
CANAL_LISTA = (34, 46, CW - 46, FILA_CANAL * FILAS_CANAL)
LEYENDA_Y = 152
LEYENDA = ((2695, 2691, 'Normal'), (2696, 2692, 'Moderate'), (2697, 2693, 'Crowded'), (2698, 2694, 'Full'))
LEYENDA_X = (10, 80, 158, 236)                                              # donde va cada cuadro
BOTONES_CANAL = {2532: (CW - 164, 180, 'Enter', 60462), 2533: (CW - 78, 180, 'Back', 60463)}
TITULO_CANAL = 'Angels Online Forever'
# El rango de la ventana: el interior mas lo que pone el marco de WND_CLASS_DLG_1 (como 181x275 -> 189x299).
RANGO_CANAL = (CW + 8, CH + 24)


def fondo_canal() -> Image.Image:
    im = _degradado(CW, CH, (26, 52, 128), NOCHE_HONDA)
    brillo = Image.new('RGBA', (CW, CH), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).ellipse((-60, -70, CW + 60, 70), fill=(110, 180, 255, 90))
    im.alpha_composite(brillo.filter(ImageFilter.GaussianBlur(16)))
    d = ImageDraw.Draw(im)
    rnd = random.Random(2530)
    for _ in range(60):
        x, y = rnd.uniform(0, CW), rnd.uniform(0, 38)
        d.point((x, y), fill=rnd.choice(((255, 236, 180), (210, 230, 255))) + (rnd.randint(120, 255),))
    # la cabecera: emblema pequeno a la izquierda y el titulo en oro, con una linea de oro debajo
    emblema = Image.open(RAIZ / 'launcher' / 'emblema.png').convert('RGBA')
    emblema = emblema.resize((32, round(emblema.height * 32 / emblema.width)), Image.LANCZOS)
    im.alpha_composite(emblema, (8, 3))
    d = ImageDraw.Draw(im)
    _rotulo(d, 'Select your channel', 170, 9, color=(255, 226, 140, 255), tam=13)
    _rotulo(d, 'Pick a channel to enter the world', 170, 25, color=(190, 210, 255, 255), tam=9)
    d.line((48, 37, CW - 8, 37), fill=ORO_OSCURO)
    # los canales: un recuadro hundido con una franja por fila y la columna de estado separada
    x0, y0, x1, y1 = CANAL_MARCO
    d.rounded_rectangle((x0, y0, x1, y1), radius=6, fill=NOCHE_HONDA + (245,), outline=ORO_OSCURO)
    ex, ey, ew, _eh = CANAL_ESTADO
    for k in range(FILAS_CANAL):
        y = ey + k * FILA_CANAL
        color = (16, 32, 80, 255) if k % 2 == 0 else (10, 22, 60, 255)
        d.rounded_rectangle((ex - 2, y, x1 - 6, y + FILA_CANAL - 2), radius=3, fill=color)
    d.line((ex + ew + 2, y0 + 5, ex + ew + 2, y1 - 5), fill=(50, 84, 160, 255))
    # la leyenda: cuatro casillas con el cuadro de color (lo pinta el juego) en su hueco con borde de oro
    d.rounded_rectangle((6, LEYENDA_Y - 4, CW - 6, LEYENDA_Y + 18 + 2), radius=5, fill=(14, 28, 74, 255),
                        outline=ORO_OSCURO)
    for x in LEYENDA_X:
        d.rectangle((x - 1, LEYENDA_Y - 1, x + 18, LEYENDA_Y + 18), outline=ORO)
    # la franja de los botones
    d.rectangle((0, 0, CW - 1, CH - 1), outline=ORO)
    d.rectangle((1, 1, CW - 2, CH - 2), outline=ORO_OSCURO)
    return im


def _base(relativa):
    """El original del cliente (extracted_paks, sin nada nuestro): el script se puede correr las veces que haga falta."""
    original = RAIZ / 'extracted_paks' / 'update26' / relativa.replace('\\', '/')
    crudo = original.read_bytes() if original.is_file() else fi.del_cliente(relativa)
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    return texto, bom, '\r\n' if '\r\n' in texto else '\n'


def _guardar(relativa, texto, bom):
    destino = EXTRAS / relativa.replace('\\', '/')
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes((b'\xef\xbb\xbf' if bom else b'') + texto.encode('utf-8'))


def _ventana(texto, wid):
    m = re.search(r'<window [^>]*\bid="%d"[^>]*>' % wid, texto)
    if not m:
        raise SystemExit('no esta la ventana %d' % wid)
    return m


def wnd02():
    texto, bom, nl = _base(r'setting\eng\wnd02.xml')
    texto = re.sub(r'[ \t]*<!-- %s -->.*?<!-- /%s -->\r?\n' % (MARCA, MARCA), '', texto, flags=re.S)
    # el interior de la 2529 sin tinte del tema
    m = re.search(r'(<icon id="2529" [^>]*>)\s*<attrib [^>]*/>\s*(</icon>)', texto)
    if m:
        texto = texto[:m.start()] + m.group(1).rstrip('>') + ' />' + texto[m.end():]
    # la lista sin su fondo
    m = _ventana(texto, 2706)
    texto = texto[:m.start()] + re.sub(r' bcolor="\d+"', ' bcolor="%d"' % ICONO_CELDAS, m.group(0)) + texto[m.end():]
    # los botones: solo otro sitio, otro tamano y su icono (lo demas, tooltips incluidos, como en el original)
    for wid, (x, y, _titulo, icono) in BOTONES.items():
        m = _ventana(texto, wid)
        tag = re.sub(r'range="[^"]*"', 'range="%d,%d,%d,%d"' % (x, y, BOTON_W, BOTON_H), m.group(0), count=1)
        tag = re.sub(r'icon="\d+"', 'icon="%d"' % icono, tag, count=1)
        texto = texto[:m.start()] + tag + texto[m.end():]
    # lo que sube para dejar aire sobre los botones
    for wid, caja in MOVER.items():
        m = _ventana(texto, wid)
        tag = re.sub(r'range="[^"]*"', 'range="%d,%d,%d,%d"' % caja, m.group(0), count=1)
        texto = texto[:m.start()] + tag + texto[m.end():]
    # EL SELECTOR DE CANAL: interior sin tinte, lista sin fondo, botones con su icono y su titulo
    m = re.search(r'(<icon id="2530" [^>]*>)\s*<attrib [^>]*/>\s*(</icon>)', texto)
    if m:
        texto = texto[:m.start()] + m.group(1).rstrip('>') + ' />' + texto[m.end():]
    m = _ventana(texto, 2531)
    texto = texto[:m.start()] + re.sub(r' bcolor="\d+"', ' bcolor="%d"' % ICONO_CELDAS, m.group(0)) + texto[m.end():]
    for wid, (x, y, _titulo, icono) in BOTONES_CANAL.items():
        m = _ventana(texto, wid)
        tag = re.sub(r'range="[^"]*"', 'range="%d,%d,%d,%d"' % (x, y, BOTON_W, BOTON_H), m.group(0), count=1)
        tag = re.sub(r'icon="\d+"', 'icon="%d"' % icono, tag, count=1)
        texto = texto[:m.start()] + tag + texto[m.end():]
    m = _ventana(texto, 2530)
    tag = re.sub(r'title="[^"]*"', 'title="%s"' % TITULO_CANAL, m.group(0))
    # "sigue sin estar centrado contra el logo": el juego la pone por su esquina, como la de 189 de ancho; el x
    # negativo la centra (lo mismo hace el acuerdo original: 328 de ancho y range="-69,0,...").
    tag = re.sub(r'range="[^"]*"', 'range="%d,0,%d,%d"' % (((189 - RANGO_CANAL[0]) // 2,) + RANGO_CANAL), tag, count=1)
    texto = texto[:m.start()] + tag + texto[m.end():]
    # la distribucion nueva: estado y lista de FILAS_CANAL filas, y la leyenda en una linea
    for wid, caja in ((2699, CANAL_ESTADO), (2531, CANAL_LISTA)):
        m = _ventana(texto, wid)
        tag = re.sub(r'range="[^"]*"', 'range="%d,%d,%d,%d"' % caja, m.group(0), count=1)
        tag = re.sub(r'rows="\d+"', 'rows="%d"' % FILAS_CANAL, tag, count=1)
        texto = texto[:m.start()] + tag + texto[m.end():]
    for (cuadro, rotulo, nombre), x in zip(LEYENDA, LEYENDA_X):
        m = _ventana(texto, cuadro)
        texto = texto[:m.start()] + re.sub(r'range="[^"]*"', 'range="%d,%d,18,18"' % (x, LEYENDA_Y), m.group(0),
                                           count=1) + texto[m.end():]
        m = _ventana(texto, rotulo)
        tag = re.sub(r'range="[^"]*"', 'range="%d,%d,%d,18"' % (x + 20, LEYENDA_Y, 52), m.group(0), count=1)
        tag = re.sub(r'title="[^"]*"', 'title="%s"' % nombre, tag, count=1)
        tag = tag.replace(' ssHCenter=""', '')
        texto = texto[:m.start()] + tag + texto[m.end():]
    # las casillas de ID y PW con texto claro (el 105 es oscuro: estaba pensado para la casilla clara de antes)
    for wid in (2702, 2704):
        m = _ventana(texto, wid)
        texto = texto[:m.start()] + re.sub(r'fcolor="\d+"', 'fcolor="103"', m.group(0), count=1) + texto[m.end():]
    m = _ventana(texto, 2529)
    texto = texto[:m.start()] + re.sub(r'title="[^"]*"', 'title="%s"' % TITULO, m.group(0)) + texto[m.end():]
    iconos = '    <!-- %s -->%s' % (MARCA, nl)
    for _x, _y, titulo, icono in list(BOTONES.values()) + list(BOTONES_CANAL.values()):
        a = 'aolat_login_%s_' % titulo.lower()
        iconos += ('    <icon id="%d" dir="\\wnd01\\" normal="%sn" focus="%sf" down="%ss" disable="%sn" />%s'
                   % (icono, a, a, a, a, nl))
    iconos += ('    <icon id="%d" dir="\\wnd01\\" normal="%s" focus="normal" down="normal" disable="normal" />%s'
               % (ICONO_CELDAS, ARCHIVO_CELDAS, nl))
    iconos += '    <!-- /%s -->%s' % (MARCA, nl)
    fin = texto.rindex('</')
    texto = texto[:fin] + iconos + texto[fin:]
    import seleccion_personaje  # la pantalla de seleccion de personaje (12/11/2026)
    texto = seleccion_personaje.wnd02(texto, nl)
    _guardar(r'setting\eng\wnd02.xml', texto, bom)


def wndtext02():
    texto, bom, _nl = _base(r'setting\eng\wndtext02.xml')
    texto = re.sub(r'<window id="2529" title="[^"]*"/>', '<window id="2529" title="%s"/>' % TITULO, texto)
    texto = re.sub(r'<window id="2530" title="[^"]*"/>', '<window id="2530" title="%s"/>' % TITULO_CANAL, texto)
    for _cuadro, rotulo, nombre in LEYENDA:
        texto = re.sub(r'<window id="%d" title="[^"]*"/>' % rotulo, '<window id="%d" title="%s"/>' % (rotulo, nombre),
                       texto)
    import seleccion_personaje
    texto = seleccion_personaje.wndtext02(texto)
    _guardar(r'setting\eng\wndtext02.xml', texto, bom)


def main():
    LOG.mkdir(parents=True, exist_ok=True)
    WND01.mkdir(parents=True, exist_ok=True)
    (LOG / 'w038_03.shp').write_bytes(a_shp(fondo()))
    (LOG / 'w038_22.shp').write_bytes(a_shp(fondo_canal()))
    (WND01 / (ARCHIVO_CELDAS + '.shp')).write_bytes(a_shp(celdas()))
    for _x, _y, titulo, _icono in list(BOTONES.values()) + list(BOTONES_CANAL.values()):
        for e in 'nfs':
            (WND01 / ('aolat_login_%s_%s.shp' % (titulo.lower(), e))).write_bytes(a_shp(boton(e, titulo)))
    for viejo in WND01.glob('aolat_login_btn_*.shp'):
        viejo.unlink()
    import seleccion_personaje
    seleccion_personaje.dibujar()
    wnd02()
    wndtext02()
    print('ventana de login y seleccion de personaje listas')


if __name__ == '__main__':
    main()
