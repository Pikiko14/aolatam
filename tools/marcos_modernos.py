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


def panel() -> Image.Image:
    """El panel entero (142 x 142) del que se recortan las nueve piezas."""
    lado = 2 * L + C
    im = Image.new('RGBA', (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, lado - 1, lado - 1), radius=RADIO, fill=SOMBRA)
    d.rounded_rectangle((1, 1, lado - 2, lado - 2), radius=RADIO - 1, fill=ORO)
    d.rounded_rectangle((2, 2, lado - 3, lado - 3), radius=RADIO - 2, fill=BRILLO)
    d.rounded_rectangle((3, 3, lado - 4, lado - 4), radius=RADIO - 3, fill=FONDO)
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
        if pak.suffix.lower() != '.pak' or paks_cliente.numero(pak.name) < -1:
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


def piezas():
    """{nombre: (imagen, bytes del .shp)} de las 18 piezas nuevas."""
    res = {}
    lienzo = panel()
    for nombre, caja in PIEZAS_W006.items():
        if nombre == 'w006_09':
            im = Image.new('RGBA', (120, 120), FONDO)
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


if __name__ == '__main__':
    main()
