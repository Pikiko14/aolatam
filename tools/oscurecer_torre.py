"""La Torre de Babel a oscuras (02/11/2026): "cambia los objetos del mapa, hazlo mas dark".

El mapa 133 es la Limitless Tower (tools/generar_mapa_torre.py), de marmol blanco, turquesa, nubes y hojas. En el
cliente no hay una version oscura de esas piezas del mismo tamano, asi que se hace una: cada objeto de decorado que usa
la torre se copia como objeto NUEVO (id desde ID_BASE, nombre "暗-...", carpeta \\stage\\aolat_tb\\) con sus sprites
pasados a piedra oscura violacea, y solo el map133.mpc apunta a las copias. Los demas mapas que usan esas piezas no
cambian.

Escribe:
    parches/extras/setting/mapobj.obd            el del cliente + las definiciones nuevas
    parches/extras/shape/stage/aolat_tb/*        los sprites oscurecidos
    parches/extras/map/map133.mpc                la torre con los objetos cambiados

    python tools/oscurecer_torre.py [carpeta del cliente]
    python tools/generar_parche.py
"""
import pathlib
import re
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))
import mpcio

ORIGEN = RAIZ / 'tools' / 'originales' / 'map110.mpc'
EXTRAS = RAIZ / 'parches' / 'extras'
SALIDA_MPC = EXTRAS / 'map' / 'map133.mpc'
SALIDA_OBD = EXTRAS / 'setting' / 'mapobj.obd'
CARPETA = 'aolat_tb'
SALIDA_SHAPES = EXTRAS / 'shape' / 'stage' / CARPETA

ID_BASE = 45000            # libres: los de mapobj.obd llegan a 44779 y los de servidor van desde 60000
MARCA = '// ---- Torre de Babel oscura (tools/oscurecer_torre.py) ----'

# Piedra oscura con un poco de violeta: la luz de cada pixel, muy rebajada, y el color que tenia apenas se nota.
LUZ = 0.42
TINTE = (0.95, 0.80, 1.15)
COLOR = 0.18
FICHA = re.compile(r'[0-9A-Za-z]+-[0-9A-Za-z]+-[0-9A-Za-z]+')


def oscuro(r, g, b):
    lum = 0.30 * r + 0.59 * g + 0.11 * b
    out = []
    for c, t in zip((r, g, b), TINTE):
        v = (lum * (1 - COLOR) + c * COLOR) * LUZ * t
        out.append(max(0, min(255, int(round(v)))))
    return tuple(out)


def _de565(v, bgr=False):
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    r, g, b = r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2
    return (b, g, r) if bgr else (r, g, b)


def _a565(r, g, b, bgr=False):
    if bgr:
        r, b = b, r
    return (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)


def _color(v, bgr=False):
    return _a565(*oscuro(*_de565(v, bgr)), bgr=bgr)


def _paleta(b: bytearray, ini: int, n: int):
    for i in range(n):
        p = ini + 2 * i
        if p + 2 <= len(b):
            struct.pack_into('<H', b, p, _color(struct.unpack_from('<H', b, p)[0]))


def oscurecer_shp(datos: bytes) -> bytes:
    """Un .shp con sus colores oscurecidos: la paleta si es paletizado, cada pixel si es de 16 bits."""
    b = bytearray(datos)
    if b[:4] != b'TLHS' or len(b) < 96:
        return datos
    h = struct.unpack_from('<20I', b, 0)
    typ, fl, alto = h[2], h[3], h[6]
    if fl == 768 and typ == 2:
        if h[16] and h[16] + 512 <= len(b):
            _paleta(b, h[16], 256)
        return bytes(b)
    bgr = typ == 4
    hechos = set()
    for y in range(alto):
        o = struct.unpack_from('<I', b, 80 + 4 * y)[0]
        while o + 8 <= len(b):
            cnt, x, off = struct.unpack_from('<HHI', b, o)
            o += 8
            if x == 0xFFFF or (cnt == 0 and off == 0):
                break
            for i in range(cnt):
                p = off + 2 * i
                if p + 2 <= len(b) and p not in hechos:
                    hechos.add(p)
                    struct.pack_into('<H', b, p, _color(struct.unpack_from('<H', b, p)[0], bgr))
    return bytes(b)


def oscurecer_spr(datos: bytes) -> bytes:
    """Un .spr (varios cuadros): su paleta comun y, por si alguno es de 16 bits, cada cuadro."""
    b = bytearray(datos)
    if b[:4] != b'EWSP':
        return datos
    cnt = struct.unpack_from('<I', b, 8)[0]
    pal = 80 + 12 * cnt
    fin_pal = struct.unpack_from('<I', b, 80)[0]
    _paleta(b, pal, max(0, (fin_pal - pal) // 2))
    for i in range(cnt):
        off, size, _ = struct.unpack_from('<III', b, 84 + 12 * i)
        cuadro = bytes(b[off:off + size])
        if cuadro[:4] == b'TLHS':
            h = struct.unpack_from('<20I', cuadro, 0)
            if not (h[3] == 768 and h[2] == 2):
                b[off:off + size] = oscurecer_shp(cuadro)
    return bytes(b)


def _bloques(texto):
    """{Sequence: texto del bloque [OBJECT]} de un .obd."""
    out = {}
    for bloque in re.split(r'\r?\n\[OBJECT\]\r?\n', texto)[1:]:
        m = re.search(r'^\s*Sequence\s*=\s*(0x[0-9a-fA-F]+|\d+)', bloque, re.M)
        if m:
            out.setdefault(int(m.group(1), 0), bloque.rstrip('\r\n'))
    return out


def main():
    cliente = sys.argv[1] if len(sys.argv) > 1 else r'C:\AO\Angels Online'
    sys.argv = [sys.argv[0], cliente]
    import editor_mapas as em
    em.cargar()

    obd = em.datos('setting/mapobj.obd').decode('cp950')
    if MARCA in obd:                      # el del parche ya las trae: se parte del original
        obd = obd[:obd.index(MARCA)].rstrip('\r\n') + '\r\n'
    bloques = _bloques(obd)

    m = mpcio.leer(ORIGEN.read_bytes())
    usados = sorted({o[0] for o in m['objetos']})
    nuevos, nuevo_de, archivos = [], {}, set()
    for sid in usados:
        bloque = bloques.get(sid)
        if not bloque or 'SP_CLASS_MAPOBJ' not in bloque:
            continue                      # generadores, marcas y objetos del servidor: tal cual
        dirm = re.search(r'^\s*Directory\s*=\s*(.+?)\s*$', bloque, re.M)
        if not dirm or not dirm.group(1).strip('\\').lower().startswith('stage'):
            continue
        carpeta = dirm.group(1).replace('\\', '/').strip('/').lower()
        nid = ID_BASE + len(nuevos)
        b = re.sub(r'^(\s*Sequence\s*=\s*)\S+', lambda x: x.group(1) + str(nid), bloque, count=1, flags=re.M)
        b = re.sub(r'^(\s*Name\s*=\s*)', lambda x: x.group(1) + '暗-', b, count=1, flags=re.M)
        b = re.sub(r'^(\s*Directory\s*=\s*).+$', lambda x: x.group(1) + '\\stage\\%s\\' % CARPETA, b, count=1,
                   flags=re.M)
        linea = re.search(r'^\s*Sprite\s*=.*$', b, re.M)
        for ficha in FICHA.findall(linea.group(0) if linea else ''):
            for ext in ('shp', 'spr'):
                k = 'shape/%s/%s.%s' % (carpeta, ficha.lower(), ext)
                if k in em.INDEX:
                    archivos.add((k, '%s.%s' % (ficha.lower(), ext)))
        nuevos.append(b)
        nuevo_de[sid] = nid

    SALIDA_SHAPES.mkdir(parents=True, exist_ok=True)
    for viejo in SALIDA_SHAPES.iterdir():
        viejo.unlink()
    for k, nombre in sorted(archivos):
        crudo = em.datos(k)
        hecho = oscurecer_spr(crudo) if nombre.endswith('.spr') else oscurecer_shp(crudo)
        (SALIDA_SHAPES / nombre).write_bytes(hecho)

    texto = obd.rstrip('\r\n') + '\r\n\r\n' + MARCA + '\r\n' + ''.join(
        '\r\n[OBJECT]\r\n' + b.replace('\r\n', '\n').replace('\n', '\r\n') + '\r\n\r\n' for b in nuevos)
    SALIDA_OBD.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_OBD.write_bytes(texto.encode('cp950'))

    for o in m['objetos']:
        o[0] = nuevo_de.get(o[0], o[0])
    SALIDA_MPC.write_bytes(mpcio.escribir(m))
    print('%d objetos oscurecidos (ids %d-%d), %d sprites, %d piezas del mapa cambiadas'
          % (len(nuevos), ID_BASE, ID_BASE + len(nuevos) - 1, len(archivos),
             sum(1 for o in m['objetos'] if o[0] >= ID_BASE and o[0] < ID_BASE + len(nuevos))))


if __name__ == '__main__':
    main()
