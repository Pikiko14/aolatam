"""Instala en el cliente un mapa .mpc exportado por el editor de mapas.

El cliente lee cada mapa del .pak de numero mas alto que lo trae (map120 esta
en UPDATE14.PAK, map041 en update26.pak). Se reemplaza ahi, con
cliente_local.actualizar_pak_cliente, que antes guarda el pak original como
.pak.bak. Despues se actualiza la fila del mapa en
server/plantillas/transitable.bin, que es por donde el servidor deja caminar
a jugadores y monstruos.

Lo que el servidor NO toma del .mpc: los monstruos (plantillas/*.json) y los
portales (plantillas/portales.json). Un generador o un tornado nuevo se ven
en el cliente, pero el servidor no los conoce.

Solo reemplaza mapas que ya existen: un stage nuevo necesita tambien su fila
en stage.xml y una entrada nueva en el pak, que actualizar_pak_cliente no sabe
anadir.

Con el cliente, el editor y el servidor cerrados (tienen los .pak abiertos):
    py -3 tools/instalar_mapa.py "C:\\AO\\Angels Online\\editor-mapas\\salida\\map120.mpc"
    py -3 tools/instalar_mapa.py salida\\mi_mapa.mpc --stage 120
    py -3 tools/instalar_mapa.py --restaurar 120
"""
import argparse
import pathlib
import re
import struct
import sys
import types
import zlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))

import cliente_local
import configuracion
import paks_cliente
import transitable as tr

TRANSITABLE = RAIZ / 'server' / 'plantillas' / 'transitable.bin'


def nombre_en_pak(stage):
    return 'MAP\\MAP%03d.MPC' % int(stage)


def _entradas(pak):
    """Nombres (en mayusculas, con \\) que trae el pak; solo lee el directorio."""
    with open(pak, 'rb') as f:
        f.seek(-22, 2)
        eocd = bytearray(f.read(22))
        if eocd[:4] != b'OD\x05\x06':
            return set()
        for i in range(4, 22):
            eocd[i] ^= (3 * i - 91) & 0xFF
        comp, _, _, _, cd_off, _ = struct.unpack('<IHHIIH', eocd[4:22])
        f.seek(cd_off + 4)
        raw = bytearray(f.read(comp))
    raw[0] ^= 0x7A
    cd, off, salida = zlib.decompress(bytes(raw)), 0, set()
    while off + 46 <= len(cd):
        fn, ex, cm = struct.unpack_from('<HHH', cd, off + 28)
        salida.add(cd[off + 46:off + 46 + fn].decode('ascii', 'ignore').upper().replace('/', '\\'))
        off += 46 + fn + ex + cm
    return salida


def pak_del_mapa(cliente, stage):
    """El pak que manda para ese mapa: el de numero mas alto que lo trae."""
    paks = sorted((p for p in pathlib.Path(cliente).iterdir()
                   if p.suffix.lower() == '.pak' and paks_cliente.numero(p.name) >= -1),
                  key=lambda p: paks_cliente.numero(p.name), reverse=True)
    for pak in paks:
        if nombre_en_pak(stage) in _entradas(pak):
            return pak
    return None


def comprobar_mpc(data):
    """(ancho, alto) si es un .mpc que se puede leer entero; si no, ValueError."""
    import mapa_del_cliente
    if data[:4] != b'MAP\0':
        raise ValueError('no empieza por MAP\\0: no es un .mpc')
    tmp = pathlib.Path(cliente_local.RAIZ_PROYECTO / 'data' / '_mapa_a_instalar.mpc')
    tmp.write_bytes(data)
    try:
        m = mapa_del_cliente.Mapa(0, tmp)
        if m.fin_tags != len(data):
            raise ValueError('sobran o faltan bytes al final (%d de %d)' % (m.fin_tags, len(data)))
        if tr.capa(tmp) is None:
            raise ValueError('la capa de casillas no tiene el tamano esperado')
        return m.ancho, m.alto
    finally:
        tmp.unlink()


def actualizar_transitable(stage, data, ruta=TRANSITABLE):
    """Reemplaza (o anade) la fila del stage en transitable.bin."""
    w, h, bits = tr.capa(types.SimpleNamespace(read_bytes=lambda: data))
    b = ruta.read_bytes()
    n, p, filas = struct.unpack_from('<I', b, 0)[0], 4, {}
    for _ in range(n):
        st, fw, fh = struct.unpack_from('<HHH', b, p)
        largo = (fw * fh + 7) // 8
        filas[st] = b[p:p + 6 + largo]
        p += 6 + largo
    filas[int(stage)] = struct.pack('<HHH', int(stage), w, h) + bytes(bits)
    ruta.write_bytes(struct.pack('<I', len(filas)) + b''.join(filas.values()))


def escribir(pak, stage, data):
    try:
        return cliente_local.actualizar_pak_cliente(pak, {nombre_en_pak(stage): data})
    except PermissionError:
        raise SystemExit('%s esta en uso: cierra el cliente, el editor de mapas y el servidor.' % pak.name)


def instalar(ruta, stage=None, cliente=None):
    ruta = pathlib.Path(ruta)
    if stage is None:
        m = re.fullmatch(r'map(\d+)\.mpc', ruta.name.lower())
        if not m:
            raise SystemExit('el archivo no se llama mapNNN.mpc: indica el mapa con --stage N')
        stage = int(m.group(1))
    data = ruta.read_bytes()
    w, h = comprobar_mpc(data)
    cliente = pathlib.Path(cliente or cliente_local.ruta_cliente())
    pak = pak_del_mapa(cliente, stage)
    if pak is None:
        raise SystemExit('el cliente no trae map%03d.mpc: solo se pueden reemplazar mapas existentes' % stage)
    original = cliente_local._extraer_archivo_pak(pak, nombre_en_pak(stage))
    ow, oh = struct.unpack_from('<II', original, 4)
    escribir(pak, stage, data)
    if cliente_local._extraer_archivo_pak(pak, nombre_en_pak(stage)) != data:
        raise SystemExit('al releer %s el mapa no coincide con el instalado' % pak.name)
    actualizar_transitable(stage, data)
    print('map%03d.mpc instalado en %s (%dx%d); original guardado en %s.bak'
          % (stage, pak.name, w, h, pak.name))
    print('transitable.bin actualizado: reinicia el servidor para que lo use.')
    if (w, h) != (ow, oh):
        print('OJO: el original media %dx%d. Las casillas de monstruos, NPC y portales del '
              'servidor siguen siendo las del mapa viejo.' % (ow, oh))
    if configuracion.mapa_apagado(stage):
        print('OJO: el stage %d esta en configuracion.MAPAS_APAGADOS: nadie puede entrar.' % stage)


def restaurar(stage, cliente=None):
    cliente = pathlib.Path(cliente or cliente_local.ruta_cliente())
    pak = pak_del_mapa(cliente, stage)
    bak = pak.with_name(pak.name + '.bak') if pak else None
    if not bak or not bak.exists():
        raise SystemExit('no hay copia original de map%03d.mpc (falta el .pak.bak)' % stage)
    data = cliente_local._extraer_archivo_pak(bak, nombre_en_pak(stage))
    escribir(pak, stage, data)
    actualizar_transitable(stage, data)
    print('map%03d.mpc restaurado al original en %s; transitable.bin actualizado.' % (stage, pak.name))


def main():
    ap = argparse.ArgumentParser(description='Instala un .mpc del editor de mapas en el cliente.')
    ap.add_argument('mpc', nargs='?', help='el .mpc exportado (salida\\mapNNN.mpc)')
    ap.add_argument('--stage', type=int, help='numero del mapa, si el archivo no se llama mapNNN.mpc')
    ap.add_argument('--restaurar', type=int, metavar='STAGE', help='vuelve a poner el mapa original')
    ap.add_argument('--cliente', help='carpeta del cliente (por defecto la que usa el servidor)')
    a = ap.parse_args()
    if a.restaurar is not None:
        restaurar(a.restaurar, a.cliente)
    elif a.mpc:
        instalar(a.mpc, a.stage, a.cliente)
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
