"""El icono de angel.dat cambiado EN SU SITIO, sin mover nada del exe (12/11/2026).

tools/icono_angel_dat.py usa UpdateResource de Windows, que reescribe la seccion .rsrc entera. Si los iconos nuevos
ocupan mas, la .rsrc crece y Windows corre las secciones que van detras... y en nuestro angel.dat detras van las
propias (.aolat, .aolatp, .aolatq, .aolatk: el canal Lua y otros ganchos), a las que el codigo salta por direccion
fija. Con el emblema nuevo pasaron de 0x74e000 a 0x77d000 y el juego se cerraba al llegar a la seleccion de personaje.

Aqui no se toca la estructura: los iconos del grupo 101 que son PNG (16..256 px) se sobrescriben con el emblema del
mismo tamano en pixeles y EXACTAMENTE los mismos bytes: si el PNG sale menor se rellena con un bloque privado
("aoLp", que los lectores de PNG ignoran) antes del IEND; si sale mayor se reduce a paleta hasta que quepa. Los dos
iconos BMP viejos (32x32 de 8 y 4 bits, otro grupo de idioma) no se tocan.

    python tools/icono_angel_dat_en_sitio.py <angel.dat> [--emblema launcher/emblema.png]
"""
import argparse
import io
import pathlib
import struct
import zlib

from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def _secciones(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, pe + 6)[0]
    opt = struct.unpack_from('<H', d, pe + 20)[0]
    rsrc = struct.unpack_from('<I', d, pe + 24 + 96 + 2 * 8)[0]
    return rsrc, [struct.unpack_from('<8sIIII', d, pe + 24 + opt + 40 * i) for i in range(n)]


def iconos_png(d):
    """[(offset en el archivo, bytes)] de los RT_ICON que son PNG."""
    rsrc, secs = _secciones(d)

    def off(rva):
        for _nm, vs, va, rs, ra in secs:
            if va <= rva < va + max(vs, rs):
                return rva - va + ra
    base = off(rsrc)

    def entradas(o):
        nn, ni = struct.unpack_from('<HH', d, o + 12)
        return [struct.unpack_from('<II', d, o + 16 + 8 * i) for i in range(nn + ni)]
    salida = []
    for tid, t in entradas(base):
        if tid != 3:
            continue
        for _nid, nn in entradas(base + (t & 0x7fffffff)):
            for _lid, hoja in entradas(base + (nn & 0x7fffffff)):
                rva, tam = struct.unpack_from('<II', d, base + hoja)[:2]
                o = off(rva)
                if d[o:o + 8] == b'\x89PNG\r\n\x1a\n':
                    salida.append((o, tam))
    return salida


def _png(im, colores=None):
    if colores:
        im = im.quantize(colors=colores, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    b = io.BytesIO()
    im.save(b, format='PNG', optimize=True)
    return b.getvalue()


def _rellenar(png, tam):
    """El PNG con un bloque privado delante del IEND que lo lleva justo a `tam` bytes (12 de cabecera como poco)."""
    falta = tam - len(png)
    if falta == 0:
        return png
    if falta < 12:
        raise ValueError('sobran %d bytes: no cabe un bloque' % falta)
    datos = b'\0' * (falta - 12)
    bloque = struct.pack('>I', len(datos)) + b'aoLp' + datos
    bloque += struct.pack('>I', zlib.crc32(b'aoLp' + datos) & 0xffffffff)
    iend = png.rindex(b'IEND') - 4
    return png[:iend] + bloque + png[iend:]


def png_justo(emblema, lado, tam):
    im = emblema.resize((lado, lado), Image.LANCZOS)
    for colores in (None, 256, 128, 64, 32):
        p = _png(im, colores)
        if len(p) == tam or len(p) <= tam - 12:
            return _rellenar(p, tam)
    raise SystemExit('el icono de %d px no cabe en %d bytes' % (lado, tam))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('exe')
    ap.add_argument('--emblema', default=str(RAIZ / 'launcher' / 'emblema.png'))
    a = ap.parse_args()
    ruta = pathlib.Path(a.exe)
    d = bytearray(ruta.read_bytes())
    tam_antes = len(d)
    em = Image.open(a.emblema).convert('RGBA')
    em = em.crop(em.getbbox())
    lado = max(em.size)
    cuadro = Image.new('RGBA', (lado, lado))
    cuadro.alpha_composite(em, ((lado - em.width) // 2, (lado - em.height) // 2))
    for o, tam in iconos_png(d):
        w, h = struct.unpack_from('>II', d, o + 16)
        nuevo = png_justo(cuadro, w, tam)
        assert len(nuevo) == tam
        d[o:o + tam] = nuevo
        print('icono %dx%d: %d bytes, en su sitio' % (w, h, tam))
    assert len(d) == tam_antes
    ruta.write_bytes(bytes(d))


if __name__ == '__main__':
    main()
