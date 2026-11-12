"""El logo de la pantalla de login (03/11/2026): "Angels Online Forever" en vez del "Angels Online" del cliente.

El login dibuja dos logos de shape/log/: w038_02 (435x212, el grande, anclado en su centro: x 217) y w038_13
(225x108, el pequeno, anclado en la esquina). Este script toma el PNG del usuario (tools/originales/logo_forever.png),
le quita el fondo cuadriculado que trae pintado (no tiene canal alfa: se borra desde los bordes todo lo gris claro
que este conectado con el borde, y los huecos de las letras que tengan ese mismo cuadriculado), lo encaja en cada
tamano conservando la proporcion y escribe:

    parches/extras/shape/log/w038_02.shp
    parches/extras/shape/log/w038_13.shp

    python tools/logo_login.py
    python tools/generar_parche.py
"""
import pathlib
import struct
import sys
from collections import deque

from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
from icono_subasta import a_shp

# 12/11/2026: el emblema redondo del launcher (launcher/emblema.png, ya con su canal alfa).
ORIGEN = RAIZ / 'launcher' / 'emblema.png'
SALIDA = RAIZ / 'parches' / 'extras' / 'shape' / 'log'
LOGOS = {'w038_02': ((435, 212), True), 'w038_13': ((225, 108), False)}   # tamano y si va anclado en su centro

GRIS_MAX = 18        # max - min de un pixel del cuadriculado (gris, sin color)
CLARO_MIN = 150      # y como poco asi de claro
HUECO_MAX = 80000    # un hueco de letra con cuadriculado es pequeno; un trozo de letra blanca no lo borramos si es mayor
VARIACION_HUECO = 14  # el cuadriculado alterna dos grises: su desviacion es alta; la cara blanca de una letra, no


def _es_fondo(p):
    r, g, b = p[:3]
    return max(r, g, b) - min(r, g, b) <= GRIS_MAX and min(r, g, b) >= CLARO_MIN


def quitar_fondo(im: Image.Image) -> Image.Image:
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    visto = set()

    def region(x0, y0):
        cola, out = deque([(x0, y0)]), []
        visto.add((x0, y0))
        while cola:
            x, y = cola.popleft()
            out.append((x, y))
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= n[0] < w and 0 <= n[1] < h and n not in visto and _es_fondo(px[n]):
                    visto.add(n)
                    cola.append(n)
        return out

    borrar = []
    for x in range(w):
        for y in (0, h - 1):
            if (x, y) not in visto and _es_fondo(px[x, y]):
                borrar += region(x, y)
    for y in range(h):
        for x in (0, w - 1):
            if (x, y) not in visto and _es_fondo(px[x, y]):
                borrar += region(x, y)
    # Los huecos de las letras (la "e", la "O"...) no tocan el borde: se borran si son pequenos y cuadriculados.
    for y in range(h):
        for x in range(w):
            if (x, y) in visto or not _es_fondo(px[x, y]):
                continue
            r = region(x, y)
            if len(r) <= HUECO_MAX:
                luz = [sum(px[c][:3]) / 3.0 for c in r]
                media = sum(luz) / len(luz)
                if (sum((v - media) ** 2 for v in luz) / len(luz)) ** 0.5 >= VARIACION_HUECO:
                    borrar += r
    for c in borrar:
        px[c] = (0, 0, 0, 0)
    return im.crop(im.getbbox())


def encajar(im: Image.Image, tam) -> Image.Image:
    w, h = tam
    copia = im.copy()
    copia.thumbnail((w, h), Image.LANCZOS)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    out.alpha_composite(copia, ((w - copia.width) // 2, (h - copia.height) // 2))
    return out


def main():
    im = Image.open(ORIGEN)
    if im.mode == 'RGBA' and im.getchannel('A').getextrema()[0] < 255:
        limpio = im.crop(im.getbbox())            # ya trae transparencia: no hay cuadriculado que quitar
    else:
        limpio = quitar_fondo(im)
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, (tam, centrado) in LOGOS.items():
        datos = bytearray(a_shp(encajar(limpio, tam)))
        if centrado:
            struct.pack_into('<ii', datos, 28, tam[0] // 2, 0)     # el ancla del original (217, 0)
        (SALIDA / (nombre + '.shp')).write_bytes(bytes(datos))
        print('escrito', (SALIDA / (nombre + '.shp')).relative_to(RAIZ), tam)


if __name__ == '__main__':
    main()
