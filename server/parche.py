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
import re
import struct
import time
import zlib

log = logging.getLogger('parche')

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DESTINO = RAIZ / 'parches'
NOMBRE_PAK = 'update27.pak'
ESTADO = 'version.json'
# La version del parche: 0.0.0.1, 0.0.0.2... (el launcher propio la escribe en reg.ini Version; decide si
# actualizar por el sha256 del pak, no por el numero). Hasta el 31/10/2026 era la de IGG, 8.5.1.N: al
# encontrar una de otra base se vuelve a empezar por 1.
VERSION_BASE = '0.0.0'
VERSION_INICIAL = 0
# Archivos que se quitan A PROPOSITO del parche (si no, generar() los arrastra del parche anterior): 'SETTING\ENG\X.XML'.
# 13/11/2026: los sprites e icono del Celestial Draco que al final no fue (el leon celestial es el ciervo, 83305).
QUITAR_DEL_PARCHE = frozenset({r'SHAPE\CHR\H720\1920_RUN.SPR', r'SHAPE\CHR\H720\1920_WAIT.SPR',
                               r'SHAPE\ITEM\I9307.SHP'})

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
        bak_raw = bak.read_bytes()
        original = _directorio(bak_raw)
        for nombre, entrada in actual.items():
            if indice.get(nombre) != pak:
                continue
            previo = original.get(nombre)
            # Mismo CRC y tamano NO basta: cliente_local reescribe el pak sin recalcular el CRC, y un cambio del mismo
            # largo (前置時間 2000 -> 1000, 收購價格 1238 -> 3000) no salia en el parche (05/11/2026). Se comparan
            # tambien los bytes comprimidos.
            if (previo and previo[0] == entrada[0] and previo[2] == entrada[2]
                    and bak_raw[previo[3]: previo[3] + previo[1]] == actual_raw[entrada[3]: entrada[3] + entrada[1]]):
                continue
            out[nombre] = _leer(actual_raw, entrada)
    # El pack del editor y parches/extras pueden traer el MISMO mapa. Gana el mas reciente: antes el del editor
    # pisaba siempre, y cuando su pack se quedaba atras se repartia un mapa viejo aunque tools/subir_mapa.py hubiera
    # puesto el nuevo en extras (el 900 salio con el terreno de una version anterior, 30/10/2026).
    extras, editor = _extras(), _pack_del_editor(ruta_cli)
    pack = pathlib.Path(ruta_cli) / PACK_EDITOR if ruta_cli else None
    t_pack = pack.stat().st_mtime if pack and pack.is_file() else 0
    t_extras = _fechas_extras()
    out.update(editor)
    for nombre, datos in extras.items():
        if nombre not in editor or t_extras.get(nombre, 0) >= t_pack:
            out[nombre] = datos
    return out


# El editor de mapas (C:\AO\Angels Online\editor-mapas) deja los mapas que se guardan o exportan en este pack del cliente.
PACK_EDITOR = 'update28.pak'


def _pack_del_editor(ruta_cli) -> dict:
    """{NOMBRE: bytes} de los mapas del pack del editor, listos para repartir: a cada map###.mpc se le quitan los NPC que
    el servidor ya manda (tools/mpc_sin_npc.py), para que el mapa muestre un solo punto por NPC. Si el mismo mapa esta
    tambien en parches/extras, gana el mas reciente (ver cambios_del_cliente)."""
    f = pathlib.Path(ruta_cli) / PACK_EDITOR
    if not f.is_file():
        return {}
    crudo = f.read_bytes()
    try:
        entradas = {n: _leer(crudo, e) for n, e in _directorio(crudo).items()}
    except Exception as e:
        log.warning('parche: no se pudo leer %s: %s', PACK_EDITOR, e)
        return {}
    try:
        import sys
        tools = str(RAIZ / 'tools')
        if tools not in sys.path:
            sys.path.append(tools)
        import mpc_sin_npc
        for n, d in list(entradas.items()):
            entradas[n] = mpc_sin_npc.recortar_entrada(n, d)
    except Exception as e:
        log.warning('parche: los mapas del editor van sin quitar NPC duplicados (%s)', e)
    log.info('parche: %d mapa(s) del editor en %s', len(entradas), PACK_EDITOR)
    return entradas


def _extras() -> dict:
    """Archivos hechos aparte (tools/mpc_sin_npc.py) que van en el parche tal cual:
    parches/extras/map/map006.mpc -> MAP\\MAP006.MPC."""
    base = DESTINO / 'extras'
    out = {}
    if base.is_dir():
        for f in base.rglob('*'):
            if f.is_file():
                nombre = str(f.relative_to(base)).upper().replace('/', '\\')
                datos = f.read_bytes()
                # Las copias de item*.xml de extras (tools/parche_materiales.py) pisan a las del cliente local, que
                # llevan los packs del Item Mall como apilables: sin esto la Store Cabinet decia "There is not
                # enough space in the bag" al sacar 110 bolsas aunque hubiera sitio (31/10/2026).
                if re.fullmatch(r'SETTING\\ENG\\ITEM\d*\.XML', nombre):
                    import cliente_local
                    datos = cliente_local._parchear_apilables_xml_bytes(datos)
                out[nombre] = datos
    return out


def _fechas_extras() -> dict:
    """{NOMBRE: mtime} de los archivos de parches/extras (mismas claves que _extras)."""
    base = DESTINO / 'extras'
    if not base.is_dir():
        return {}
    return {str(f.relative_to(base)).upper().replace('/', '\\'): f.stat().st_mtime
            for f in base.rglob('*') if f.is_file()}


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


def _de_esta_base(est: dict) -> bool:
    return str(est.get('version') or '').startswith(VERSION_BASE + '.')


def renumerar(destino: pathlib.Path = DESTINO) -> dict:
    """Pone el parche actual, sin tocarlo, como el primero de la base nueva (VERSION_BASE.1). El pak y su sha256
    no cambian, asi que nadie vuelve a bajar nada."""
    est = estado(destino)
    if not est or _de_esta_base(est):
        return est
    est.update(version='%s.%d' % (VERSION_BASE, VERSION_INICIAL + 1), numero=VERSION_INICIAL + 1)
    (destino / ESTADO).write_text(json.dumps(est, indent=1, ensure_ascii=False), encoding='utf-8')
    return est


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
    previo = estado(destino)
    pak = destino / NOMBRE_PAK
    # LO QUE YA SE REPARTIO NO SE PIERDE (04/11/2026). Con el cliente de desarrollo vacio o reinstalado (sin sus .bak),
    # la 0.0.0.47 salio sin ITEM3-9.XML, las tiendas SP_*, BATTLEPASS, dos mapas y el logo: varios de esos archivos los
    # pusieron herramientas a mano y solo viven en el parche publicado. Ahora el parche nuevo parte del anterior y encima
    # van los cambios del cliente y parches/extras. Para quitar un archivo a proposito: QUITAR_DEL_PARCHE, o
    # AO_PARCHE_SIN_ARRASTRE=1 para rehacerlo solo desde el cliente.
    if pak.exists() and _de_esta_base(previo) and os.environ.get('AO_PARCHE_SIN_ARRASTRE') != '1':
        try:
            crudo = pak.read_bytes()
            for nombre, entrada in _directorio(crudo).items():
                if nombre not in archivos and nombre not in QUITAR_DEL_PARCHE:
                    archivos[nombre] = _leer(crudo, entrada)
        except Exception:
            log.exception('no se pudo leer el parche anterior para arrastrar sus archivos')
    huella = _huella(archivos)
    if previo.get('huella') == huella and pak.exists():
        _copiar_al_cliente(pak, ruta_cli)
        return previo
    numero = (int(previo.get('numero', VERSION_INICIAL)) if _de_esta_base(previo) else VERSION_INICIAL) + 1
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
