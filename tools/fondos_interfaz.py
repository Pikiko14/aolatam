"""Fondos de la interfaz rehechos a partir de los del cliente (04/11/2026).

1. aolat_prop50.shp: el fondo del Prop (Alt+B) con 10 filas de casillas en vez de 5, para la mochila de 50
   ("el bag sigue pequeno debe tener 50 espacios"). El original (shape/wnd01/w011_1) trae la cuadricula pintada,
   asi que las casillas 3151-3175 existian pero no se veian. Se repiten las 190 filas de pixeles de la cuadricula
   (5 casillas de 38) y debajo va la franja del oro y los botones.
2. aolat_barra.shp: la barra de abajo (shape/wnd01/w007_01) sin los dos ovalos que quedaron vacios al quitar el
   Star Blessing y el Pet Amplify ("salen los 2 circulos vacios"). Ver BORRAR_BARRA.

Se trabaja sobre los bytes del .shp (tramos de pixeles por fila), sin pasar por PIL: la paleta y los pixeles
quedan iguales que los nativos. Formato: ver tools/icono_subasta.py; con la marca 4 (w011_1) cada pixel son
2 bytes y el cierre de fila lleva 0.

    python tools/fondos_interfaz.py
"""
import pathlib
import struct
import sys
import zlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import paks_cliente  # noqa: E402

SALIDA = RAIZ / 'parches' / 'extras' / 'shape' / 'wnd01'
CLIENTE = pathlib.Path(r'C:\AO\Angels Online')

ALTO_CUADRICULA = 190          # 5 casillas de 38 px
FILAS_EXTRA = 5                # de 5 a 10 filas
# Lo que se borra de la barra, en pixeles de la imagen (x0, x1, y0, y1). Arriba, el ovalo de la izquierda (el
# Event Overview pasa al de la derecha, el que cuelga de la parra); abajo, el primero de la izquierda, y los botones
# de abajo se corren un ovalo a la derecha hasta la parra ("mueve un poco los iconos de abajo a la derecha").
BORRAR_BARRA = ((355, 399, 40, 90), (0, 42, 86, 152))


def del_cliente(nombre):
    """El .shp vigente (el del pak de numero mas alto, contando los .bak sin parches nuestros)."""
    nombre = nombre.lower()
    mejor = None
    for pak in CLIENTE.glob('*'):
        if pak.suffix.lower() not in ('.pak',) or paks_cliente.numero(pak.name) < -1:
            continue
        fuente = pak.with_name(pak.name + '.bak')
        fuente = fuente if fuente.exists() else pak
        datos = fuente.read_bytes()
        for n, _crc, cs, _us, off in paks_cliente._directorio(datos):
            if n.lower() == nombre and (mejor is None or paks_cliente.numero(pak.name) > mejor[0]):
                mejor = (paks_cliente.numero(pak.name), zlib.decompress(datos[off:off + cs], -15))
    if not mejor:
        raise SystemExit('no esta %s en %s' % (nombre, CLIENTE))
    return mejor[1]


def leer(d):
    cab = list(struct.unpack_from('<4s19I', d))
    alto = cab[6]
    bpp = 2 if cab[2] == 4 else 1
    offs = struct.unpack_from('<%dI' % alto, d, 80)
    filas = []
    for y in range(alto):
        p, tramos = offs[y], []
        while True:
            n, x, src = struct.unpack_from('<HHI', d, p)
            p += 8
            if x == 0xFFFF:
                break
            tramos.append((x, d[src:src + n * bpp]))
        filas.append(tramos)
    paleta = d[cab[16]:cab[16] + 512]
    return cab, bpp, filas, paleta


def escribir(cab, bpp, filas, paleta):
    alto = len(filas)
    n_tramos = sum(len(t) + 1 for t in filas)
    ini_tramos = 80 + 4 * alto
    ini_paleta = ini_tramos + 8 * n_tramos
    ini_pix = ini_paleta + len(paleta)
    tabla, tramos_b, pix = bytearray(), bytearray(), bytearray()
    for tramos in filas:
        tabla += struct.pack('<I', ini_tramos + len(tramos_b))
        en_fila = 0
        for x, px in tramos:
            tramos_b += struct.pack('<HHI', len(px) // bpp, x, ini_pix + len(pix))
            pix += px
            en_fila += len(px) // bpp
        tramos_b += struct.pack('<HHI', 0, 0xFFFF, en_fila if bpp == 1 else 0)
    cab = list(cab)
    cab[6], cab[9], cab[10], cab[11], cab[16] = alto, n_tramos, len(pix) // bpp, ini_pix, ini_paleta
    if cab[12]:
        cab[12] = ini_pix
    return struct.pack('<4s19I', *cab) + bytes(tabla) + bytes(tramos_b) + bytes(paleta) + bytes(pix)


def prop50():
    cab, bpp, filas, paleta = leer(del_cliente(r'shape\wnd01\w011_1.shp'))
    cuadricula = filas[:ALTO_CUADRICULA]
    nuevas = cuadricula + cuadricula[:FILAS_EXTRA * 38] + filas[ALTO_CUADRICULA:]
    if cab[8]:                          # el origen va abajo: crece lo mismo que la imagen
        cab[8] += len(nuevas) - len(filas)
    return escribir(cab, bpp, nuevas, paleta)


def barra():
    cab, bpp, filas, paleta = leer(del_cliente(r'shape\wnd01\w007_01.shp'))
    nuevas = []
    for y, tramos in enumerate(filas):
        for x0, x1, y0, y1 in BORRAR_BARRA:
            if not y0 <= y <= y1:
                continue
            fila = []
            for x, px in tramos:
                n = len(px) // bpp
                # se parte el tramo en lo que queda a la izquierda y a la derecha de [x0, x1]
                izq = max(0, min(n, x0 - x))
                der = max(0, min(n, x + n - 1 - x1))
                if izq:
                    fila.append((x, px[:izq * bpp]))
                if der:
                    fila.append((x + n - der, px[(n - der) * bpp:]))
            tramos = fila
        nuevas.append(tramos)
    return escribir(cab, bpp, nuevas, paleta)


# 3. aolat_sys_aof.shp: el fondo de la pestana AOF de la ventana System (tools/parche_aof_ventana.py). Es el de la
#    pagina Sound (shape/wnd01/w050_01, 249x343, con el atributo del tema: sigue el color de ventana elegido) sin sus
#    tres railes de deslizador (y 13..64) ni sus tres casillas (y 84..133): esas filas se tapan con una fila limpia del
#    cuerpo ("se ve mal", 08/11/2026: con el fondo de Sound salian los railes y las casillas detras del texto).
FILAS_SUCIAS_AOF = range(0, 161)
FILA_LIMPIA_AOF = 200


def sys_aof():
    cab, bpp, filas, paleta = leer(del_cliente(r'shape\wnd01\w050_01.shp'))
    limpia = filas[FILA_LIMPIA_AOF]
    nuevas = [limpia if y in FILAS_SUCIAS_AOF else tramos for y, tramos in enumerate(filas)]
    return escribir(cab, bpp, nuevas, paleta)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre, datos in (('aolat_prop50.shp', prop50()), ('aolat_barra.shp', barra()),
                          ('aolat_sys_aof.shp', sys_aof())):
        (SALIDA / nombre).write_bytes(datos)
        print(nombre, len(datos), 'bytes')


if __name__ == '__main__':
    main()
