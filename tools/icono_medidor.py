"""El icono del contador de dano para la barra de abajo (02/11/2026): una espada sobre unas barras de grafica.

Mismo formato que el de la subasta (tools/icono_subasta.a_shp): parches/extras/shape/wnd01/aolat_dm_n.shp y _f.shp.
El boton lo anade tools/parche_subasta_ventana.py a wnd01.xml (BOTONES_BARRA).

    python tools/icono_medidor.py
"""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageEnhance

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from icono_subasta import ANCHO, ALTO, SALIDA, a_shp, al_estilo_nativo

NOMBRE = 'aolat_dm'


def dibujar() -> Image.Image:
    k = 4
    im = Image.new('RGBA', (ANCHO * k, ALTO * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    borde = (40, 16, 8, 255)

    def r(*xy):
        return [v * k for v in xy]
    # Tres barras de grafica, de menos a mas, en rojo y naranja.
    for x, alto, color in ((5, 12, (230, 120, 40, 255)), (15, 20, (232, 72, 40, 255)), (25, 30, (210, 30, 30, 255))):
        d.rectangle(r(x, 54 - alto, x + 8, 54), fill=color, outline=borde, width=k)
        d.line(r(x + 2, 55 - alto, x + 2, 52), fill=(255, 200, 150, 255), width=k)
    # La espada, en diagonal por encima.
    d.line(r(8, 30, 33, 5), fill=borde, width=7 * k)
    d.line(r(8, 30, 33, 5), fill=(220, 228, 240, 255), width=4 * k)
    d.line(r(14, 25, 32, 7), fill=(255, 255, 255, 255), width=k)
    d.line(r(6, 24, 14, 32), fill=borde, width=6 * k)            # la guarda
    d.line(r(6, 24, 14, 32), fill=(236, 190, 70, 255), width=3 * k)
    d.line(r(4, 34, 9, 29), fill=borde, width=6 * k)             # el puno
    d.line(r(4, 34, 9, 29), fill=(150, 88, 40, 255), width=3 * k)
    return im.resize((ANCHO, ALTO), Image.LANCZOS)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    normal = al_estilo_nativo(dibujar())
    foco = ImageEnhance.Brightness(normal).enhance(1.25)
    for sufijo, im in (('_n', normal), ('_f', foco)):
        ruta = SALIDA / (NOMBRE + sufijo + '.shp')
        ruta.write_bytes(a_shp(im))
        print('escrito', ruta)


if __name__ == '__main__':
    main()
