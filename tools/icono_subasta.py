"""El icono de la casa de subastas para la barra de abajo (02/11/2026): un mazo de subasta sobre monedas.

Se dibuja con PIL y se guarda como .shp del juego (parches/extras/shape/wnd01/aolat_ah_n.shp y _f.shp, el normal y
el de pasar el raton), que van al parche como cualquier otro extra. El boton lo anade tools/parche_subasta_ventana.py
a wnd01.xml.

El .shp de los iconos de la interfaz (medido sobre btn017_n, btn024_n y actboard/btn_icon_1) es paletizado:
    cabecera de 20 u32: 'TLHS', 1, 2 (paleta), 0x300, 0x7e0, ancho, alto, ox, oy, n_tramos, bytes_pixeles,
                        inicio_pixeles, inicio_pixeles, 0, 0, 0, inicio_paleta, 0, 0, 0
    una u32 por fila: donde empiezan sus tramos
    tramos de 8 bytes [u16 cuantos][u16 x][u32 donde estan sus pixeles]; cada fila acaba en [0][0xffff][pixeles fila]
    la paleta: 256 colores RGB565
    los pixeles: un byte (indice de paleta) cada uno
Lo transparente es lo que no cae en ningun tramo. tools/editor_mapas/editor_mapas.decode_shp lo lee.

    python tools/icono_subasta.py
"""
import pathlib
import struct

from PIL import Image, ImageDraw, ImageEnhance

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = RAIZ / 'parches' / 'extras' / 'shape' / 'wnd01'
NOMBRE = 'aolat_ah'
ANCHO, ALTO = 40, 56
MARGEN = 5        # px libres a cada lado: "dale un poco de padding a los iconos" (02/11/2026), que iban pegados


def con_margen(im: Image.Image) -> Image.Image:
    """El dibujo reducido para que deje MARGEN libre a los lados, centrado y apoyado abajo como antes."""
    caja = im.getbbox()
    if not caja:
        return im
    dibujo = im.crop(caja)
    f = min(1.0, (ANCHO - 2 * MARGEN) / dibujo.width, (ALTO - 2 * MARGEN) / dibujo.height)
    dibujo = dibujo.resize((max(1, round(dibujo.width * f)), max(1, round(dibujo.height * f))), Image.LANCZOS)
    out = Image.new('RGBA', (ANCHO, ALTO), (0, 0, 0, 0))
    out.alpha_composite(dibujo, ((ANCHO - dibujo.width) // 2, min(caja[3], ALTO - 2) - dibujo.height))
    return out


def _rgb565(r, g, b):
    return (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)


def a_shp(im: Image.Image) -> bytes:
    """Un RGBA como .shp paletizado de icono. Lo que tiene alfa < 128 queda transparente."""
    im = im.convert('RGBA')
    w, h = im.size
    alfa = im.getchannel('A')
    pal_im = im.convert('RGB').quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    paleta = pal_im.getpalette()[:255 * 3]
    idx = pal_im.load()
    a = alfa.load()
    filas = []                      # por fila: [(x, [indices])]
    for y in range(h):
        tramos, x = [], 0
        while x < w:
            if a[x, y] < 128:
                x += 1
                continue
            ini = x
            while x < w and a[x, y] >= 128:
                x += 1
            tramos.append((ini, [idx[i, y] for i in range(ini, x)]))
        filas.append(tramos)
    n_tramos = sum(len(t) + 1 for t in filas)
    tabla = 80
    ini_tramos = tabla + 4 * h
    ini_paleta = ini_tramos + 8 * n_tramos
    ini_pixeles = ini_paleta + 512
    tramos_b, pixeles, offs_fila = bytearray(), bytearray(), []
    for tramos in filas:
        offs_fila.append(ini_tramos + len(tramos_b))
        en_fila = 0
        for x, px in tramos:
            tramos_b += struct.pack('<HHI', len(px), x, ini_pixeles + len(pixeles))
            pixeles += bytes(px)
            en_fila += len(px)
        tramos_b += struct.pack('<HHI', 0, 0xFFFF, en_fila)
    pal_b = bytearray()
    for i in range(256):
        r, g, b = paleta[3 * i:3 * i + 3] if i < len(paleta) // 3 else (0, 0, 0)
        pal_b += struct.pack('<H', _rgb565(r, g, b))
    cab = struct.pack('<4s19I', b'TLHS', 1, 2, 0x300, 0x7E0, w, h, 0, 0, n_tramos, len(pixeles),
                      ini_pixeles, ini_pixeles, 0, 0, 0, ini_paleta, 0, 0, 0)
    return cab + b''.join(struct.pack('<I', o) for o in offs_fila) + bytes(tramos_b) + bytes(pal_b) + bytes(pixeles)


def dibujar() -> Image.Image:
    """El mazo dorado sobre un monton de monedas, con contorno oscuro como los demas iconos de la barra."""
    k = 4                                            # se dibuja a 4x y se reduce, para suavizar
    im = Image.new('RGBA', (ANCHO * k, ALTO * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    borde = (40, 24, 8, 255)

    def r(*xy):
        return [v * k for v in xy]
    # Monedas: tres pilas.
    for cx, base, n in ((10, 52, 3), (22, 53, 5), (32, 51, 2)):
        for i in range(n):
            y = base - i * 4
            d.ellipse(r(cx - 8, y - 3, cx + 8, y + 3), fill=(232, 178, 40, 255), outline=borde, width=k)
            d.ellipse(r(cx - 5, y - 2, cx + 5, y + 1), fill=(255, 222, 96, 255))
    # Mango del mazo, en diagonal.
    d.line(r(10, 38, 30, 14), fill=borde, width=7 * k)
    d.line(r(10, 38, 30, 14), fill=(150, 88, 40, 255), width=4 * k)
    # Cabeza del mazo: un barril girado.
    cabeza = Image.new('RGBA', (26 * k, 14 * k), (0, 0, 0, 0))
    dc = ImageDraw.Draw(cabeza)
    dc.rounded_rectangle(r(1, 1, 25, 13), radius=3 * k, fill=(196, 120, 52, 255), outline=borde, width=k)
    dc.rectangle(r(4, 1, 7, 13), fill=(236, 196, 80, 255), outline=borde, width=k)
    dc.rectangle(r(19, 1, 22, 13), fill=(236, 196, 80, 255), outline=borde, width=k)
    dc.line(r(5, 4, 21, 4), fill=(236, 170, 110, 255), width=k)
    cabeza = cabeza.rotate(40, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(cabeza, (int(13 * k), int(0 * k)))
    # Un brillo.
    d.ellipse(r(31, 3, 35, 7), fill=(255, 255, 220, 255))
    return im.resize((ANCHO, ALTO), Image.LANCZOS)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    normal = con_margen(dibujar())
    foco = ImageEnhance.Brightness(normal).enhance(1.25)
    for sufijo, im in (('_n', normal), ('_f', foco)):
        ruta = SALIDA / (NOMBRE + sufijo + '.shp')
        ruta.write_bytes(a_shp(im))
        print('escrito', ruta.relative_to(RAIZ))


if __name__ == '__main__':
    main()
