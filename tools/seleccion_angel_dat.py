"""La distribucion nueva de la seleccion de personaje en angel.dat (12/11/2026, "cambia la distribucion de las cartas y
opciones"). La parte de dibujo y XML esta en tools/seleccion_personaje.py.

El juego coloca la seleccion por codigo, en coordenadas de 800x600 centradas en la ventana:
    x = (ancho - 800) / 2 + c        y = (alto - 600) / 2 + c
(medido con capstone sobre el angel.dat descomprimido, base 0x400000):

  0x4bf968  la barra "(1)" de encima del menu (se crea por codigo): y +0x190, x +0x290
  0x4bf9ca  el menu 2565: y +0x1a7, x +0x28c
  0x4bfc02  las fichas 2713+i:              y +0x8c, x +0x19 + 209*i
  0x4bfd1a  la marca de borrado 2545+i:     y +0xf5, x +0x69 + 209*i
  0x4c0a5c  el personaje (objeto 0xfab6):  y +0x101, x +5 + 209*i
  0x4c5c6d  el objeto 0x3e7 de cada ficha:  y +0x42, x +0x74 + 209*i

Las cuatro cosas de cada ficha se mueven juntas cambiando el 800 y el 600 de su centrado (asi no hay que tocar cada
suma, y algunas son de un byte y no caben): con 800 - 2*DX y 600 - 2*DY todo se corre DX, DY.

Lo nuevo (en 800x600):
  * las fichas centradas (DX = +71: de x 25 a 96, las tres juntas ocupan 607 de 800) y 30 px mas arriba (DY = -30);
  * el menu, una barra de MENU_W x MENU_H centrada debajo de las fichas, en MENU_X, MENU_Y;
  * la barra "(1)" fuera de la pantalla (y -3000).

    python tools/seleccion_angel_dat.py <angel.dat> [...]          # los cambia en su sitio
    python tools/seleccion_angel_dat.py <angel.dat> --ver          # solo dice como estan
"""
import argparse
import pathlib
import struct

DX, DY = 71, -30
MENU_W, MENU_H = 580, 30
MENU_X, MENU_Y = (800 - MENU_W) // 2, 110 + 426 + 4      # bajo las fichas (que ahora empiezan en y 110)
FUERA = -3000


def _sub(v):
    return b'\x2d' + struct.pack('<I', v)


def _add(v):
    return b'\x05' + struct.pack('<i', v)


# (offset en el archivo, original, nuevo, que es)
PARCHES = (
    (0xbed72, _add(0x190), _add(FUERA), 'barra (1): y fuera de la pantalla'),
    (0xbedd4, _add(0x1a7), _add(MENU_Y), 'menu: y'),
    (0xbede9, _add(0x28c), _add(MENU_X), 'menu: x'),
) + tuple(   # el centrado en x de las cuatro piezas de cada ficha (el de y lo busca _con_y)
    (off, _sub(800), _sub(800 - 2 * DX), nombre + ': x')
    for off, nombre in ((0xbf023, 'fichas'), (0xbf13b, 'marca de borrado'), (0xbfe7c, 'personaje'),
                        (0xc508c, 'objeto 0x3e7'))
)


def _con_y(d):
    """Las sumas de y de las cuatro piezas de las fichas: el sub 600 que va antes de cada sub 800 de PARCHES."""
    extra = []
    for off, antes, _despues, que in PARCHES:
        if que.endswith(': x') and antes == _sub(800):
            y = d.rfind(_sub(600), off - 0x40, off)
            if y < 0:
                y = d.rfind(_sub(600 - 2 * DY), off - 0x40, off)
            if y < 0:
                raise SystemExit('no encuentro el centrado en y de %s' % que)
            extra.append((y, _sub(600), _sub(600 - 2 * DY), que[:-3] + ': y'))
    return PARCHES + tuple(extra)


def estado(d, offset, antes, despues):
    trozo = bytes(d[offset:offset + len(antes)])
    return 'original' if trozo == antes else 'parcheado' if trozo == despues else 'desconocido (%s)' % trozo.hex()


def parchear(ruta: pathlib.Path, ver=False):
    d = bytearray(ruta.read_bytes())
    parches = _con_y(d)
    estados = [estado(d, o, x, y) for o, x, y, _q in parches]
    for (o, _x, _y, que), e in zip(parches, estados):
        print('  %-28s 0x%x  %s' % (que, o, e))
    if ver:
        return
    if any(e.startswith('desconocido') for e in estados):
        raise SystemExit('%s no es el angel.dat esperado: no se toca' % ruta)
    for (o, _x, despues, _q), e in zip(parches, estados):
        if e == 'original':
            d[o:o + len(despues)] = despues
    ruta.write_bytes(bytes(d))
    print('listo:', ruta)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('exe', nargs='+')
    ap.add_argument('--ver', action='store_true')
    a = ap.parse_args()
    for exe in a.exe:
        print(exe)
        parchear(pathlib.Path(exe), a.ver)


if __name__ == '__main__':
    main()
