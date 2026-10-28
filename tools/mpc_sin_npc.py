"""Quita de los map###.mpc del cliente los NPC que el servidor ya manda.

El cliente pinta un punto en el mapa por cada NPC que trae su .mpc, y el
servidor manda ademas la entidad del mismo NPC (la que se ve y se puede
pulsar): el mapa mostraba dos puntos. El .mpc solo aporta ese punto, no el
personaje (comprobado en Spike Farm: sin la entidad del servidor el NPC no
sale), asi que se sacan esos registros del .mpc y el servidor queda como unica
fuente.

Objeto del .mpc: 74 bytes; +0 id de sprite, +4/+8 pixel x/y, +22 u16 npc_type.
Cabecera: +24 off_objetos, +28 N_OBJETOS; con registros menos, se corren los
offsets +32, +60, +68 y +76 (los de despues de los objetos).

El resultado va a parches/extras/map/mapNNN.mpc, y parche.py lo mete en
update27.pak.

    python -I tools/mpc_sin_npc.py 6          (informa, no escribe)
    python -I tools/mpc_sin_npc.py 6 --escribir
    python -I tools/mpc_sin_npc.py todos --escribir
"""
import json
import pathlib
import re
import sqlite3
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import cliente_local as cl  # noqa: E402

BS = chr(92)
PL = RAIZ / 'server' / 'plantillas'
EXTRAS = RAIZ / 'parches' / 'extras' / 'map'
TAM = 74
DESPLAZADOS = (32, 60, 68, 76)


def plantillas():
    src = (RAIZ / 'server' / 'login.py').read_text(encoding='utf-8')
    m = re.search(r'PLANTILLAS_POR_STAGE\s*=\s*\{(.*?)\n\}', src, re.S)
    pl = {int(a): b for a, b in re.findall(r"(\d+)\s*:\s*'([^']+)'", m.group(1))}
    # Mapas que el servidor arma aparte (app.MAPAS_APARTE): Angel Lyceum y Fighting Palace
    pl.setdefault(41, 'lyceum.json')
    if (PL / 'fighting_palace.json').exists():
        pl.setdefault(57, 'fighting_palace.json')
    return pl


def npc_del_servidor(stage, archivo):
    try:
        sp = json.loads((PL / archivo).read_text(encoding='utf-8'))['spawns']
    except Exception:
        return []
    lista = [(e['npc_type'], e['tile'][0], e.get('nombre', '?')) for e in sp
             if not e.get('monstruo') and not e.get('apagado') and e.get('tile')]
    if stage == 41:                       # recent_mall.poblar() agrega los NPC de canje en el Lyceum
        try:
            for n in json.loads((PL / 'recent_mall.json').read_text(encoding='utf-8'))['npcs']:
                lista.append((n['npc_type'], n['tile'][0], n['nombre']))
        except Exception:
            pass
    return lista


def recortar(mpc, npcs):
    """(bytes nuevos, [registros quitados]). Quita el registro cuyo npc_type y x coinciden con un NPC del servidor."""
    off, n = struct.unpack_from('<II', mpc, 24)
    quitar, quitados = set(), []
    for i in range(n):
        o = off + i * TAM
        sprite, px, py = struct.unpack_from('<III', mpc, o)
        tipo = struct.unpack_from('<H', mpc, o + 22)[0]
        for t, x, nombre in npcs:
            if tipo == t and abs(px / 32 - x) <= 3:
                quitar.add(i)
                quitados.append((i, sprite, px, py, tipo, nombre))
                break
    if not quitar:
        return mpc, []
    nuevo = bytearray()
    nuevo += mpc[:off]
    for i in range(n):
        if i not in quitar:
            nuevo += mpc[off + i * TAM: off + (i + 1) * TAM]
    nuevo += mpc[off + n * TAM:]
    struct.pack_into('<I', nuevo, 28, n - len(quitar))
    for pos in DESPLAZADOS:
        v = struct.unpack_from('<I', nuevo, pos)[0]
        if v > off:
            struct.pack_into('<I', nuevo, pos, v - len(quitar) * TAM)
    return bytes(nuevo), quitados


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    escribir = '--escribir' in sys.argv
    pls = plantillas()
    stages = sorted(pls) if args == ['todos'] else [int(a) for a in args]
    ruta = cl.ruta_cliente()
    indice = cl.indice_paks(ruta)
    db = sqlite3.connect(str(RAIZ / 'corpus' / 'content.db'))
    total = 0
    import configuracion as cf
    for stage in stages:
        if cf.mapa_apagado(stage):
            continue                      # los mapas cerrados no se tocan
        fila = db.execute('select 地圖檔 from stage where id=?', (str(stage),)).fetchone()
        if not fila or not fila[0] or stage not in pls:
            continue
        nombre = fila[0].replace('/', BS)
        pak = indice.get(nombre.upper())
        mpc = cl._extraer_archivo_pak(pak, nombre) if pak else b''
        if mpc[:4] != b'MAP\x00':
            continue
        nuevo, quitados = recortar(mpc, npc_del_servidor(stage, pls[stage]))
        if not quitados:
            continue
        total += len(quitados)
        print(f'stage {stage} {nombre}: quita {len(quitados)}', quitados[:4] if len(args) == 1 else '')
        if escribir:
            EXTRAS.mkdir(parents=True, exist_ok=True)
            (EXTRAS / pathlib.PureWindowsPath(nombre).name.lower()).write_bytes(nuevo)
    print('total registros quitados:', total, '(escritos)' if escribir else '(solo informe)')


def recortar_entrada(entrada, datos):
    """Para parche.py: devuelve `datos` (un map###.mpc) sin los NPC que el servidor ya manda; si el mapa esta cerrado,
    no tiene plantilla o no es un map###.mpc, lo devuelve igual."""
    import configuracion as cf
    m = re.match(r'MAP\\MAP(\d+)\.MPC$', entrada.upper().replace('/', BS))
    if not m or datos[:4] != b'MAP\x00':
        return datos
    stage = int(m.group(1))
    pls = plantillas()
    if stage not in pls or cf.mapa_apagado(stage):
        return datos
    nuevo, _quitados = recortar(datos, npc_del_servidor(stage, pls[stage]))
    return nuevo


if __name__ == '__main__':
    main()
