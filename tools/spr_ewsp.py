"""Leer y escribir los .spr de los monstruos (contenedor EWSP de frames TLHS), 05/11/2026.

Medido sobre shape/mon/*/110668_*.spr (Wham Ogre) y 42107 (Slarm):

  EWSP  cabecera '<4s7I': 'EWSP', 768, n_frames, 80 (tabla), off_paleta, off_nombres, 9*n, 0; ceros hasta 80
        tabla en 80: n x '<3I' (off_nombre, off_tlhs, tam_tlhs)
        paleta: 256 colores RGB565 (el 0 es transparente), compartida por todos los frames
        nombres: n x 9 bytes ASCIIZ, "w013.SHP" = animacion (w a r h d) + '0' + pose (1..) + direccion (3..7)
        frames TLHS seguidos
  TLHS  cabecera '<4s19I': 'TLHS', 1, 2, 768, k, ancho, alto, ox, oy (el punto de los pies, desde arriba a la
        izquierda), n_tramos, n_pixeles, ini_pixeles, ini_pixeles + 512, 0, 0, 0, 0, 64, 0, 0
        una u32 por fila: donde empiezan sus tramos
        tramos de 8 bytes [u16 cuantos][u16 x][u32 donde estan sus pixeles]; la fila acaba en
        [0][0xFFFF][pixeles acumulados hasta esta fila]
        pixeles: un byte (indice de la paleta del EWSP) cada uno
Cada animacion son N poses x 5 direcciones, la pose por fuera: frame = pose*5 + direccion.
"""
import struct

from PIL import Image

LETRAS = {'wait': 'w', 'run': 'r', 'att': 'a', 'hurt': 'h', 'dead': 'd'}


def _de565(c):
    return ((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31


def _a565(r, g, b):
    return (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)


def leer(datos: bytes):
    """[(imagen RGBA, (ox, oy), nombre)] y la cabecera k de los TLHS."""
    mag, _f, n, tabla, off_pal, _off_nom, _t, _z = struct.unpack_from('<4s7I', datos, 0)
    if mag != b'EWSP':
        raise ValueError('no es un EWSP')
    pal = [_de565(struct.unpack_from('<H', datos, off_pal + 2 * i)[0]) for i in range(256)]
    out = []
    k = None
    for i in range(n):
        o_nom, o_t, tam = struct.unpack_from('<3I', datos, tabla + 12 * i)
        nombre = datos[o_nom:o_nom + 9].split(b'\0')[0].decode('latin-1')
        b = datos[o_t:o_t + tam]
        c = struct.unpack_from('<4s19I', b, 0)
        k = c[4] if k is None else k
        w, h, ox, oy = c[5], c[6], c[7], c[8]
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        px = im.load()
        for y in range(h):
            p = struct.unpack_from('<I', b, 80 + 4 * y)[0]
            while True:
                cnt, x, src = struct.unpack_from('<HHI', b, p)
                p += 8
                if x == 0xFFFF:
                    break
                for j in range(cnt):
                    idx = b[src + j]
                    if idx and 0 <= x + j < w:
                        px[x + j, y] = pal[idx] + (255,)
        out.append((im, (ox, oy), nombre))
    return out, k


def paleta_de(frames, colores=255):
    """Una paleta de hasta 255 colores (mas el 0 transparente) comun a todos los frames."""
    opacos = []
    for im, _o, _n in frames:
        a = im.getchannel('A')
        rgb = im.convert('RGB')
        for (r, g, b), al in zip(rgb.getdata(), a.getdata()):
            if al >= 128:
                opacos.append((r, g, b))
    muestra = Image.new('RGB', (len(opacos), 1))
    muestra.putdata(opacos)
    q = muestra.quantize(colors=colores, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:3 * colores]
    return [tuple(pal[3 * i:3 * i + 3]) for i in range(len(pal) // 3)], q


def _tlhs(im, ox, oy, q, k):
    """Un frame RGBA como TLHS con indices de la paleta cuantizada q (indice paleta+1; 0 transparente)."""
    w, h = im.size
    alfa = im.getchannel('A').load()
    idx = im.convert('RGB').quantize(palette=q, dither=Image.Dither.NONE).load()
    filas = []
    for y in range(h):
        tramos, x = [], 0
        while x < w:
            if alfa[x, y] < 128:
                x += 1
                continue
            ini = x
            while x < w and alfa[x, y] >= 128:
                x += 1
            tramos.append((ini, bytes(idx[i, y] + 1 for i in range(ini, x))))
        filas.append(tramos)
    n_tramos = sum(len(t) + 1 for t in filas)
    ini_tramos = 80 + 4 * h
    ini_pix = ini_tramos + 8 * n_tramos
    tabla, tb, pix = bytearray(), bytearray(), bytearray()
    for tramos in filas:
        tabla += struct.pack('<I', ini_tramos + len(tb))
        for x, px in tramos:
            tb += struct.pack('<HHI', len(px), x, ini_pix + len(pix))
            pix += px
        tb += struct.pack('<HHI', 0, 0xFFFF, len(pix))
    cab = struct.pack('<4s19I', b'TLHS', 1, 2, 768, k, w, h, ox, oy, n_tramos, len(pix), ini_pix, ini_pix + 512,
                      0, 0, 0, 0, 64, 0, 0)
    return cab + bytes(tabla) + bytes(tb) + bytes(pix)


def escribir(frames, anim: str, k: int = 10466, prefijo: str = '') -> bytes:
    """frames: [(imagen RGBA, (ox, oy))] en el orden del juego (pose*5 + direccion)."""
    n = len(frames)
    pal, q = paleta_de([(im, o, None) for im, o in frames])
    letra = prefijo + LETRAS[anim]          # 'h' en las monturas: hw013.SHP, hr013.SHP (char.obd)
    tlhs = [_tlhs(im, ox, oy, q, k) for im, (ox, oy) in frames]
    off_pal = 80 + 12 * n
    off_nom = off_pal + 512
    # Cada nombre con su cero al final: 9 bytes en los monstruos (w013.SHP) y 10 en las monturas (hw013.SHP, como el
    # 1201_Wait.spr del caballo). Con 9 los de montura iban pegados sin el cero y el cliente se cerraba (11/11/2026).
    hueco = len(letra) + 8
    off_t = off_nom + hueco * n
    cab = struct.pack('<4s7I', b'EWSP', 768, n, 80, off_pal, off_nom, hueco * n, 0).ljust(80, b'\0')
    tabla = bytearray()
    pos = off_t
    for i, t in enumerate(tlhs):
        tabla += struct.pack('<3I', off_nom + hueco * i, pos, len(t))
        pos += len(t)
    paleta = bytearray(struct.pack('<H', 0))
    for r, g, b in pal:
        paleta += struct.pack('<H', _a565(r, g, b))
    paleta = bytes(paleta.ljust(512, b'\0'))
    nombres = bytearray()
    for i in range(n):
        pose, dirn = divmod(i, 5)
        nombres += ('%s0%d%d.SHP' % (letra, pose + 1, dirn + 3)).encode('latin-1').ljust(hueco, b'\0')
    return bytes(cab) + bytes(tabla) + paleta + bytes(nombres) + b''.join(tlhs)
