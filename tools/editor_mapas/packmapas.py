"""Pack nuevo para los mapas del editor: update28.pak en la carpeta del cliente.

El cliente carga update.pak .. update31.pak en orden y, si un archivo esta en varios, gana el de numero mas alto. Por eso cada mapa que se guarda o se
exporta desde el editor se mete aqui como MAP\\NOMBRE.MPC: el juego lo usa en lugar del original sin tocar ningun .pak del cliente (borrar update28.pak
lo deshace todo). Los mapas que ya estaban en el pack se conservan; el que se guarda de nuevo reemplaza al suyo.

Formato = el de los paks de FAO: datos deflate (sin cabecera) uno tras otro, directorio comprimido con zlib y cifrado con el XOR del cliente, y al final
la firma 'OD\\x05\\x06' con la cola cifrada.
"""
import os
import struct
import time
import zlib

PACK = 'update28.pak'

_FIRMA_ENTRADA = 0x0201444F      # 'OD\x01\x02'
_VERSION_ZIP = 0x14
_ATRIBUTOS = 0x81B60020


def _directorio(data):
    """{NOMBRE: (offset, tam_comprimido, metodo)} de un pak OD."""
    eocd = bytearray(data[-22:])
    if eocd[:4] != b'OD\x05\x06':
        return {}
    for i in range(4, 22):
        eocd[i] ^= (3 * i - 91) & 0xFF
    comp, _, _, _, cd_off, _ = struct.unpack('<IHHIIH', eocd[4:22])
    raw = bytearray(data[cd_off + 4: cd_off + 4 + comp])
    raw[0] ^= 0x7A
    cd = zlib.decompress(bytes(raw))
    out, off = {}, 0
    while off + 46 <= len(cd):
        metodo = struct.unpack_from('<H', cd, off + 10)[0]
        csize, fn_len, ex_len, cm_len = struct.unpack_from('<IxxxxHHH', cd, off + 20)
        lhoff = struct.unpack_from('<I', cd, off + 42)[0]
        nombre = cd[off + 46: off + 46 + fn_len].decode('latin1').upper().replace('/', '\\')
        out[nombre] = (lhoff, csize, metodo)
        off += 46 + fn_len + ex_len + cm_len
    return out


def leer(ruta):
    """{NOMBRE: bytes sin comprimir} del pack, o {} si todavia no existe."""
    if not os.path.exists(ruta):
        return {}
    data = open(ruta, 'rb').read()
    res = {}
    for nombre, (off, cs, metodo) in _directorio(data).items():
        crudo = data[off: off + cs]
        res[nombre] = zlib.decompress(crudo, -15) if metodo == 8 else crudo
    return res


def armar(archivos):
    """Los bytes de un pak con esos archivos {NOMBRE: bytes}."""
    datos, cd = bytearray(), bytearray()
    t = time.localtime()
    mtime = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
    mdate = ((t.tm_year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
    for nombre in sorted(archivos):
        crudo = archivos[nombre]
        c = zlib.compressobj(9, zlib.DEFLATED, -15)
        comp = c.compress(crudo) + c.flush()
        fn = nombre.upper().replace('/', '\\').encode('ascii')
        cd += struct.pack('<IHHHHHHIIIHHHHHII', _FIRMA_ENTRADA, _VERSION_ZIP, _VERSION_ZIP, 0, 8, mtime, mdate,
                          zlib.crc32(crudo) & 0xFFFFFFFF, len(comp), len(crudo), len(fn), 0, 0, 0, 0, _ATRIBUTOS, len(datos))
        cd += fn
        datos += comp
    cd_comp = bytearray(zlib.compress(bytes(cd)))
    cd_comp[0] ^= 0x7A
    eocd = bytearray(b'OD\x05\x06' + struct.pack('<IHHIIH', len(cd_comp), len(archivos), len(archivos), len(cd), len(datos), 0))
    for i in range(4, 22):
        eocd[i] ^= (3 * i - 91) & 0xFF
    return bytes(datos) + b'OD\x05\x06' + bytes(cd_comp) + bytes(eocd)


def guardar_mapa(ruta_pack, nombre, mpc):
    """Mete (o reemplaza) el mapa `nombre` en el pack y lo deja escrito. Devuelve un resumen.

    Falla con PermissionError si el cliente (o el servidor) tiene el pack abierto: hay que cerrarlo y volver a guardar.
    """
    entrada = 'MAP\\' + nombre.upper() + '.MPC'
    archivos = leer(ruta_pack)
    nuevo = entrada not in archivos
    archivos[entrada] = mpc
    pak = armar(archivos)
    # comprobacion: lo escrito se vuelve a leer y trae el mapa tal cual
    tmp = ruta_pack + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(pak)
    try:
        os.replace(tmp, ruta_pack)
    except OSError:
        os.remove(tmp)
        raise
    ver = leer(ruta_pack)
    if ver.get(entrada) != mpc:
        raise RuntimeError('el pack se escribio pero el mapa no coincide al releerlo')
    return dict(pack=os.path.basename(ruta_pack), ruta=ruta_pack, entrada=entrada, nuevo=nuevo, mapas=len(ver), bytes=len(pak))
