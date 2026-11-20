"""El fondo propio de la casa de subastas (20/11/2026): "puedes crear una propia pestana para la subasta que se vea
armoniosa".

El de antes era el del tablon de IGG (shape/wnd01/w030_01, icono 3511 de wnd03.xml): una rejilla de 4 x 10 casillas
de objeto que no casa con la lista de 4 columnas (Item, Qty., Price each, Seller), y un dibujo "de tema" (sus
pixeles son indices que el cliente tine con el color del tema), que con el gris salia translucido y apagado.

Este se dibuja a medida de los controles de la ventana 3501 (parche_subasta_ventana.py), con los colores de las
ventanas del juego como la del Angel Pass (marino, azul petroleo y un filete dorado):

    y   0..39   barra de arriba: a la izquierda lo de vender (casilla 3590, nombre, precio 3593 y cantidad 3576),
                a la derecha los filtros (los desplegables 3524 y 3527 sobre su caja oscura)
    y  41..78   la cabecera de la lista 3530, con las columnas cada ~197 px
    y  79..420  las 9 filas de 38 px, en bandas alternas, cada una con la casilla de su icono (3595...) en x=5
    y 425..443  la pagina (3531..3533)
    y 444..467  la barra de abajo: pestanas, el aviso, el oro (3534), lo publicado (3535), la cantidad (3537..3539)
                y el boton de aceptar (3540)

Se guarda como .shp de paleta (icono_subasta.a_shp) en parches/extras/shape/wnd01/aolat_subasta.shp; el icono 3511
pasa a usarlo, sin ICON_ATTRIB_THEME (parche_subasta_ventana.py). Con --vista RUTA.png deja una vista previa.

    python tools/fondo_subasta.py [--vista RUTA.png]
"""
import argparse
import pathlib
import sys

from PIL import Image, ImageDraw

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import icono_subasta  # noqa: E402

SALIDA = RAIZ / 'parches' / 'extras' / 'shape' / 'wnd01' / 'aolat_subasta.shp'
ANCHO, ALTO = 790, 468

MARINO_ARRIBA = (20, 36, 58)
MARINO_ABAJO = (11, 21, 37)
BARRA = (19, 52, 72)
BORDE = (64, 132, 152)
BORDE_SUAVE = (38, 74, 96)
CAJA = (8, 16, 28)
CABECERA_ARRIBA = (0, 104, 118)
CABECERA_ABAJO = (0, 74, 90)
ORO = (214, 174, 84)
FILA_A = (21, 41, 62)
FILA_B = (26, 50, 74)
SEPARADOR = (44, 82, 106)
CASILLA = (10, 20, 33)
# Las cajas de los textos OSCUROS del cliente (los desplegables 3524 y 3527, la pagina 3532 y la cantidad 3538): en el
# fondo original eran claras, y sobre caja oscura no se leian (captura del 20/11/2026).
CLARA = (226, 218, 192)
CLARA_BORDE = (150, 140, 110)

LISTA_X0, LISTA_X1 = 6, 783
CABECERA_Y0, FILAS_Y0, FILA_ALTO, N_FILAS = 41, 79, 38, 9
COLUMNAS = (199, 396, 594)            # donde empieza cada columna de la lista (tras Item)


def _degradado(dib, caja, arriba, abajo):
    x0, y0, x1, y1 = caja
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, y1 - y0)
        c = tuple(int(arriba[i] + (abajo[i] - arriba[i]) * t) for i in range(3))
        dib.line((x0, y, x1, y), fill=c)


def _caja(dib, caja, relleno=CAJA, borde=BORDE_SUAVE, r=3):
    dib.rounded_rectangle(caja, radius=r, fill=relleno, outline=borde)


def _casilla(dib, x, y, lado=34):
    """Casilla de objeto: hundida, con luz arriba a la izquierda y sombra abajo a la derecha."""
    dib.rounded_rectangle((x, y, x + lado, y + lado), radius=3, fill=CASILLA, outline=BORDE)
    dib.line((x + 2, y + lado - 2, x + lado - 2, y + lado - 2), fill=(30, 58, 78))
    dib.line((x + lado - 2, y + 2, x + lado - 2, y + lado - 2), fill=(30, 58, 78))


def dibujar() -> Image.Image:
    im = Image.new('RGBA', (ANCHO, ALTO), (0, 0, 0, 255))
    dib = ImageDraw.Draw(im)
    _degradado(dib, (0, 0, ANCHO - 1, ALTO - 1), MARINO_ARRIBA, MARINO_ABAJO)
    dib.rectangle((0, 0, ANCHO - 1, ALTO - 1), outline=BORDE)

    # Barra de arriba.
    dib.rounded_rectangle((2, 1, ANCHO - 3, 38), radius=4, fill=BARRA, outline=BORDE)
    # Lo de vender (solo se ve en Sell, pero sus cajas quedan como marco): casilla, nombre, precio y cantidad.
    _casilla(dib, 4, 2, 35)
    dib.line((44, 20, 234, 20), fill=BORDE_SUAVE)
    _caja(dib, (44, 22, 114, 36))
    _caja(dib, (184, 22, 234, 36))
    dib.line((242, 6, 242, 33), fill=BORDE_SUAVE)
    # Filtros: los dos desplegables sobre caja oscura, y un separador antes de la lupa.
    _caja(dib, (552, 13, 604, 31), relleno=CLARA, borde=CLARA_BORDE)
    _caja(dib, (676, 13, 728, 31), relleno=CLARA, borde=CLARA_BORDE)
    dib.line((748, 6, 748, 33), fill=BORDE_SUAVE)

    # Cabecera de la lista, con filete dorado debajo.
    _degradado(dib, (LISTA_X0, CABECERA_Y0, LISTA_X1, FILAS_Y0 - 2), CABECERA_ARRIBA, CABECERA_ABAJO)
    dib.rectangle((LISTA_X0, CABECERA_Y0, LISTA_X1, FILAS_Y0 - 2), outline=BORDE)
    dib.line((LISTA_X0, FILAS_Y0 - 1, LISTA_X1, FILAS_Y0 - 1), fill=ORO)
    for x in COLUMNAS:
        dib.line((x, CABECERA_Y0 + 6, x, FILAS_Y0 - 7), fill=(90, 170, 180))

    # Las filas.
    for i in range(N_FILAS):
        y0 = FILAS_Y0 + i * FILA_ALTO
        y1 = y0 + FILA_ALTO - 1
        dib.rectangle((LISTA_X0, y0, LISTA_X1, y1), fill=FILA_A if i % 2 == 0 else FILA_B)
        for x in COLUMNAS:
            dib.line((x, y0 + 5, x, y1 - 5), fill=SEPARADOR)
        _casilla(dib, 4, y0 + 2)
    dib.rectangle((LISTA_X0, FILAS_Y0, LISTA_X1, FILAS_Y0 + N_FILAS * FILA_ALTO - 1), outline=BORDE)

    # Pagina.
    _caja(dib, (716, 425, 768, 442), relleno=CLARA, borde=CLARA_BORDE)

    # Barra de abajo.
    dib.rectangle((1, 444, ANCHO - 2, ALTO - 2), fill=BARRA)
    dib.line((1, 444, ANCHO - 2, 444), fill=BORDE)
    _caja(dib, (86, 447, 460, 464), relleno=(14, 34, 50))          # el aviso
    _caja(dib, (466, 447, 548, 464))                              # el oro
    dib.ellipse((469, 450, 479, 460), fill=ORO, outline=(150, 110, 40))
    _caja(dib, (552, 447, 620, 464))                              # lo publicado
    _caja(dib, (665, 448, 717, 464), relleno=CLARA, borde=CLARA_BORDE)   # la cantidad
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--vista')
    a = ap.parse_args()
    im = dibujar()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes(icono_subasta.a_shp(im))
    print('fondo', SALIDA, SALIDA.stat().st_size)
    if a.vista:
        im.convert('RGB').save(a.vista)
        print('vista en', a.vista)


if __name__ == '__main__':
    main()
