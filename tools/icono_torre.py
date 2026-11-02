"""El icono de la Torre de Babel para la barra de abajo (02/11/2026): una torre de piedra en pisos, con la punta dorada.

Mismo formato que el de la subasta (tools/icono_subasta.a_shp): parches/extras/shape/wnd01/aolat_tb_n.shp y _f.shp.
El boton lo anade tools/parche_subasta_ventana.py a wnd01.xml (BOTONES_BARRA).

    python tools/icono_torre.py
"""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageEnhance

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from icono_subasta import ANCHO, ALTO, SALIDA, a_shp

NOMBRE = 'aolat_tb'


def dibujar() -> Image.Image:
    k = 4
    im = Image.new('RGBA', (ANCHO * k, ALTO * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    borde = (40, 28, 16, 255)

    def r(*xy):
        return [v * k for v in xy]
    # Cinco pisos, cada uno mas estrecho, de abajo arriba.
    pisos = [(4, 46, 36, 54), (7, 38, 33, 46), (10, 30, 30, 38), (13, 22, 27, 30), (16, 14, 24, 22)]
    for i, (x0, y0, x1, y1) in enumerate(pisos):
        tono = 178 + i * 12
        d.rectangle(r(x0, y0, x1, y1), fill=(tono, tono - 22, tono - 70, 255), outline=borde, width=k)
        d.line(r(x0 + 1, y0 + 1, x1 - 1, y0 + 1), fill=(240, 226, 180, 255), width=k)
        for vx in range(x0 + 3, x1 - 2, 5):                  # ventanas iluminadas
            d.rectangle(r(vx, y0 + 3, vx + 1, y1 - 2), fill=(255, 210, 80, 255))
    # La punta dorada.
    d.polygon(r(20, 3, 16, 14, 24, 14), fill=(240, 190, 60, 255), outline=borde)
    d.ellipse(r(18, 1, 22, 5), fill=(255, 245, 190, 255), outline=borde)
    return im.resize((ANCHO, ALTO), Image.LANCZOS)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    normal = dibujar()
    foco = ImageEnhance.Brightness(normal).enhance(1.25)
    for sufijo, im in (('_n', normal), ('_f', foco)):
        ruta = SALIDA / (NOMBRE + sufijo + '.shp')
        ruta.write_bytes(a_shp(im))
        print('escrito', ruta)


if __name__ == '__main__':
    main()
