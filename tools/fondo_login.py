"""El fondo de la pantalla de login (03/11/2026): la imagen del usuario en vez de la ciudad del cielo del cliente.

El fondo es shape/log/w038_01.shp: 1573x768, 16 bits (RGB565), opaco, una tirada entera por fila y anclado en
x 1573. Se deja el archivo del cliente tal cual (cabecera, filas, anclaje) y solo se cambian sus pixeles por los de
tools/originales/fondo_login.png, escalada para cubrir 1573x768 y recortada por arriba y por abajo (se quita mas de
abajo, que en la imagen es suelo liso, para no cortar el logo de arriba).

    python tools/fondo_login.py
    python tools/generar_parche.py
"""
import pathlib
import struct
import sys

from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))

# 12/11/2026, "aca igual cambia el logo y la imagen de fondo": la misma imagen que el launcher (launcher/arte).
ORIGEN = RAIZ / 'launcher' / 'arte' / 'cielo.webp'
SALIDA = RAIZ / 'parches' / 'extras' / 'shape' / 'log' / 'w038_01.shp'
ANCHO, ALTO = 1573, 768
ARRIBA = 0.25           # de lo que sobra en alto, esta parte se quita de arriba y el resto de abajo


def _a565(r, g, b):
    return (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)


def _a_la_derecha(im: Image.Image) -> Image.Image:
    """12/11/2026: la imagen del cielo es menos ancha que el fondo (1573) y el juego en 1024 solo ensena el centro
    (x 274..1298): escalada para cubrir, las chicas de la izquierda quedaban fuera. Va a toda la altura, pegada a la
    derecha, y el hueco de la izquierda se rellena con su borde en espejo y difuminado."""
    from PIL import ImageFilter
    im = im.resize((round(im.width * ALTO / im.height), ALTO), Image.LANCZOS)
    x = ANCHO - im.width
    lienzo = Image.new('RGB', (ANCHO, ALTO))
    espejo = im.crop((0, 0, x, ALTO)).transpose(Image.FLIP_LEFT_RIGHT).filter(ImageFilter.GaussianBlur(6))
    lienzo.paste(espejo, (0, 0))
    lienzo.paste(im, (x, 0))
    return lienzo


def cubrir(im: Image.Image) -> Image.Image:
    im = im.convert('RGB')
    if im.width * ALTO / im.height < ANCHO:
        return _a_la_derecha(im)
    k = max(ANCHO / im.width, ALTO / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    x = (im.width - ANCHO) // 2
    y = int((im.height - ALTO) * ARRIBA)
    return im.crop((x, y, x + ANCHO, y + ALTO))


def main():
    cliente = sys.argv[1] if len(sys.argv) > 1 else r'C:\AO\Angels Online'
    sys.argv = [sys.argv[0], cliente]
    import editor_mapas as em
    em.cargar()
    b = bytearray(em.datos('shape/log/w038_01.shp'))
    h = struct.unpack_from('<20I', b, 0)
    assert (h[2], h[3], h[5], h[6]) == (2, 512, ANCHO, ALTO), 'el fondo del cliente no es el que se espera'
    px = cubrir(Image.open(ORIGEN)).load()
    for y in range(ALTO):
        o = struct.unpack_from('<I', b, 80 + 4 * y)[0]
        while True:
            cnt, x0, off = struct.unpack_from('<HHI', b, o)
            o += 8
            if x0 == 0xFFFF or (cnt == 0 and off == 0):
                break
            for i in range(cnt):
                if x0 + i < ANCHO:
                    struct.pack_into('<H', b, off + 2 * i, _a565(*px[x0 + i, y]))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes(bytes(b))
    print('escrito', SALIDA.relative_to(RAIZ))


if __name__ == '__main__':
    main()
