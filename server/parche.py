"""El parche para los jugadores: update27.pak con todo lo que el servidor
cambia en el cliente local, y la version que lo identifica.

El servidor parchea el cliente de ESTA maquina dentro de sus propios paks
(cliente_local.aplicar_modo_estacion, tools/instalar_mapa.py...), guardando
el original como <pak>.bak. Lo que hay que repartir es justo la diferencia:
cada archivo cuyo pak vigente ya no es igual a su .bak. Va a un pak NUEVO,
porque angel.dat carga update.pak..update31.pak en orden y, si un archivo
esta en varios, gana el del numero mas alto: update27 pisa a los originales
del jugador sin tocarlos, y basta con borrarlo para deshacerlo.

Uso:
    import parche; parche.generar()          (lo hace el servidor al arrancar)
    python tools/generar_parche.py
"""
import hashlib
import json
import logging
import pathlib
import struct
import time
import zlib

log = logging.getLogger('parche')

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DESTINO = RAIZ / 'parches'
NOMBRE_PAK = 'update27.pak'
ESTADO = 'version.json'
# La version del cliente de IGG (reg.ini Version). El parche sube el ultimo numero.
VERSION_BASE = '8.5.1'
VERSION_INICIAL = 0

# Campos fijos de cada entrada del directorio, copiados de update26.pak.
_FIRMA_ENTRADA = 0x0201444F      # 'OD\x01\x02'
_VERSION_ZIP = 0x14
_METODO_DEFLATE = 8
_ATRIBUTOS = 0x81B60020


def _directorio(data: bytes) -> dict:
    """{NOMBRE: (crc, csize, usize, offset)} de un pak OD\\x05\\x06."""
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
        crc, csize, usize, fn_len, ex_len, cm_len = struct.unpack_from('<IIIHHH', cd, off + 16)
        lhoff = struct.unpack_from('<I', cd, off + 42)[0]
        nombre = cd[off + 46: off + 46 + fn_len].decode('ascii', 'ignore').upper().replace('/', '\\')
        out[nombre] = (crc, csize, usize, lhoff)
        off += 46 + fn_len + ex_len + cm_len
    return out


def _leer(data: bytes, entrada) -> bytes:
    _, csize, _, lhoff = entrada
    return zlib.decompress(data[lhoff: lhoff + csize], -15)


def cambios_del_cliente(ruta_cli: pathlib.Path) -> dict:
    """{NOMBRE: bytes} de lo que el cliente local lee distinto de sus originales."""
    import cliente_local
    indice = cliente_local.indice_paks(ruta_cli)
    out = {}
    for pak in sorted({p for p in indice.values()}, key=lambda p: p.name):
        bak = pak.with_name(pak.name + '.bak')
        if not bak.exists():
            continue
        actual_raw = pak.read_bytes()
        actual = _directorio(actual_raw)
        original = _directorio(bak.read_bytes())
        for nombre, entrada in actual.items():
            if indice.get(nombre) != pak:
                continue
            previo = original.get(nombre)
            if previo and previo[0] == entrada[0] and previo[2] == entrada[2]:
                continue
            out[nombre] = _leer(actual_raw, entrada)
    out.update(_extras())
    return out


def _extras() -> dict:
    """Archivos hechos aparte (tools/mpc_sin_npc.py) que van en el parche tal cual:
    parches/extras/map/map006.mpc -> MAP\\MAP006.MPC."""
    base = DESTINO / 'extras'
    out = {}
    if base.is_dir():
        for f in base.rglob('*'):
            if f.is_file():
                out[str(f.relative_to(base)).upper().replace('/', '\\')] = f.read_bytes()
    return out


def armar_pak(archivos: dict) -> bytes:
    """Los bytes de un pak con esos archivos, en el formato que lee angel.dat."""
    datos = bytearray()
    cd = bytearray()
    t = time.localtime()
    mtime = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
    mdate = ((t.tm_year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
    for nombre in sorted(archivos):
        crudo = archivos[nombre]
        c = zlib.compressobj(9, zlib.DEFLATED, -15)
        comp = c.compress(crudo) + c.flush()
        fn = nombre.upper().replace('/', '\\').encode('ascii')
        cd += struct.pack('<IHHHHHHIIIHHHHHII', _FIRMA_ENTRADA, _VERSION_ZIP, _VERSION_ZIP, 0,
                          _METODO_DEFLATE, mtime, mdate, zlib.crc32(crudo) & 0xFFFFFFFF,
                          len(comp), len(crudo), len(fn), 0, 0, 0, 0, _ATRIBUTOS, len(datos))
        cd += fn
        datos += comp
    cd_comp = bytearray(zlib.compress(bytes(cd)))
    cd_comp[0] ^= 0x7A
    eocd = bytearray(b'OD\x05\x06' + struct.pack('<IHHIIH', len(cd_comp), len(archivos),
                                                 len(archivos), len(cd), len(datos), 0))
    for i in range(4, 22):
        eocd[i] ^= (3 * i - 91) & 0xFF
    return bytes(datos) + b'OD\x05\x06' + bytes(cd_comp) + bytes(eocd)


def escribir_pak(ruta: pathlib.Path, archivos: dict):
    """Un pak nuevo con esos archivos, en el formato que lee angel.dat."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + '.tmp')
    tmp.write_bytes(armar_pak(archivos))
    tmp.replace(ruta)


_CACHE_ENTRADAS = {}


def entradas(destino: pathlib.Path = DESTINO) -> dict:
    """{NOMBRE: bytes} de lo que lleva parches/update27.pak (con cache por fecha)."""
    pak = destino / NOMBRE_PAK
    try:
        marca = (pak.stat().st_mtime_ns, pak.stat().st_size)
    except OSError:
        return {}
    previo = _CACHE_ENTRADAS.get(str(pak))
    if previo and previo[0] == marca:
        return previo[1]
    crudo = pak.read_bytes()
    dic = {n: _leer(crudo, e) for n, e in _directorio(crudo).items()}
    _CACHE_ENTRADAS[str(pak)] = (marca, dic)
    return dic


def _huella(archivos: dict) -> str:
    h = hashlib.sha256()
    for nombre in sorted(archivos):
        h.update(nombre.encode('ascii'))
        h.update(hashlib.sha256(archivos[nombre]).digest())
    return h.hexdigest()


def estado(destino: pathlib.Path = DESTINO) -> dict:
    try:
        return json.loads((destino / ESTADO).read_text(encoding='utf-8'))
    except Exception:
        return {}


def version(destino: pathlib.Path = DESTINO) -> str:
    return estado(destino).get('version') or '%s.%d' % (VERSION_BASE, VERSION_INICIAL)


def generar(ruta_cli: pathlib.Path = None, destino: pathlib.Path = DESTINO) -> dict:
    """Rehace parches/update27.pak si lo que hay que repartir cambio y sube la version."""
    import os
    # Servidor sin cliente (el VPS): el parche se genera en la maquina que tiene el cliente y se sube hecho; AO_PARCHE_FIJO=1 impide que el arranque
    # lo rehaga (sin cliente saldria vacio y pisaria el bueno).
    if os.environ.get('AO_PARCHE_FIJO') == '1' and (destino / NOMBRE_PAK).exists() and estado(destino).get('version'):
        return estado(destino)
    import cliente_local
    ruta_cli = ruta_cli or cliente_local.ruta_cliente()
    archivos = cambios_del_cliente(ruta_cli)
    huella = _huella(archivos)
    previo = estado(destino)
    pak = destino / NOMBRE_PAK
    if previo.get('huella') == huella and pak.exists():
        _copiar_al_cliente(pak, ruta_cli)
        return previo
    numero = int(previo.get('numero', VERSION_INICIAL)) + 1
    escribir_pak(pak, archivos)
    nuevo = {
        'version': '%s.%d' % (VERSION_BASE, numero),
        'numero': numero,
        'huella': huella,
        'pak': NOMBRE_PAK,
        'bytes': pak.stat().st_size,
        'sha256': hashlib.sha256(pak.read_bytes()).hexdigest(),
        'archivos': sorted(archivos),
        'generado': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    (destino / ESTADO).write_text(json.dumps(nuevo, indent=1, ensure_ascii=False), encoding='utf-8')
    log.info('parche %s: %s con %d archivos (%d B)', nuevo['version'], NOMBRE_PAK,
             len(archivos), nuevo['bytes'])
    _copiar_al_cliente(pak, ruta_cli)
    return nuevo


def _copiar_al_cliente(pak: pathlib.Path, ruta_cli):
    """El cliente local lleva el mismo update27.pak que los jugadores. Con el
    juego abierto el archivo esta bloqueado y se queda para el proximo arranque."""
    if not ruta_cli or not pathlib.Path(ruta_cli).is_dir():
        return
    local = pathlib.Path(ruta_cli) / NOMBRE_PAK
    try:
        if local.exists() and local.read_bytes() == pak.read_bytes():
            return
        local.write_bytes(pak.read_bytes())
        log.info('parche copiado al cliente local: %s', local)
    except OSError as e:
        log.warning('no se pudo copiar %s al cliente (quiza el juego esta abierto): %s', NOMBRE_PAK, e)
