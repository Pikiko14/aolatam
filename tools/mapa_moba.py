"""El mapa del evento MOBA (23/11/2026): "podemos crear un evento de moba?".

Es el Holy Battlefield del cliente (map112.mpc: un campo continuo de 320x300 con la base de Jiabli arriba a la
derecha y la de Raphael abajo a la izquierda) con numero propio, el 918 "Angel MOBA", para que cada partida tenga su
copia sin cruzarse con el Holy de verdad. Primero se probo el Outpost Battlefield (47), pero sus islas no se pisan entre
si: se cruzan con teletransportes. Los tres carriles y las torres salen de server/plantillas/moba.json.

Escribe tools/editor_mapas/salida/MAP918.mpc y la fila de stage.xml (con el minimapa del 112); con --instalar corre
tools/subir_mapa.py 918 --solo-local (copia, colision del servidor y parche).

    python tools/mapa_moba.py [--instalar]
"""
import argparse
import pathlib
import re
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
sys.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))
sys.path.insert(0, str(RAIZ / 'server'))
import mpcio  # noqa: E402

STAGE, STAGE_ORIGEN, NOMBRE = 918, 112, 'Angel MOBA'
SALIDA = RAIZ / 'tools' / 'editor_mapas' / 'salida' / ('MAP%d.mpc' % STAGE)
STAGE_XML = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'stage.xml'


def original():
    import fondos_interfaz as fi
    return fi.del_cliente('map\\map%03d.mpc' % STAGE_ORIGEN)


def fila_stage(texto):
    """stage.xml con la fila del 918: la del mapa de origen con su nombre y su mapa (rehace la que hubiera)."""
    texto = re.sub(r'[ \t]*<場景 編號="%d" [^\n]*?/>\r?\n' % STAGE, '', texto)
    m = re.search(r'([ \t]*)<場景 編號="%d" [^\n]*?/>(\r?\n)' % STAGE_ORIGEN, texto)
    if not m:
        raise SystemExit('no esta el mapa %d en stage.xml' % STAGE_ORIGEN)
    fila = m.group(0).replace('編號="%d"' % STAGE_ORIGEN, '編號="%d"' % STAGE)
    fila = re.sub(r'名稱="[^"]*"', '名稱="%s"' % NOMBRE, fila, count=1)
    fila = re.sub(r'(地圖檔="map\\)map\d+\.mpc"', r'\g<1>map%d.mpc"' % STAGE, fila, count=1)
    fila = re.sub(r'雷達圖="smap\\\d+"', r'雷達圖="smap\\%d"' % STAGE, fila, count=1)      # su minimapa (mapa_moba_tema)
    return texto[:m.end()] + fila + texto[m.end():]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--instalar', action='store_true')
    a = ap.parse_args()
    d = original()
    m = mpcio.leer(d)
    # Sin los eventos del Outpost: sus disparadores llevan al mapa 47 (accion 3 [47, tag]) y no pintan nada aqui. Fuera
    # tambien el enlace objeto -> evento (los 4 primeros bytes del registro extra de cada objeto).
    m['eventos'] = '<?xml version="1.0" encoding="UTF-8" ?>\n<root>\n\t<head version="1.0"/>\n</root>\n'
    for o in m['objetos']:
        if len(o) > 6 and o[6]:
            o[6] = '00000000' + o[6][8:]
    # Su aspecto propio, el del Crystal Grounds ("que no parezca el de hbf", 24/11/2026): tools/mapa_moba_tema.py.
    import mapa_moba_tema as mt
    em = mt._editor()
    print('bioma:', mt.tematizar(m, em))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes(mpcio.escribir(m))
    print('mapa %d (%dx%d, %d objetos) -> %s' % (STAGE, m['w'], m['h'], len(m['objetos']), SALIDA))
    mt.minimapa(m, em)
    print('minimapa ->', mt.SMAP)
    crudo = STAGE_XML.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    nuevo = fila_stage(texto)
    if nuevo != texto:
        STAGE_XML.write_bytes((b'\xef\xbb\xbf' if bom else b'') + nuevo.encode('utf-8'))
        print('fila del %d en stage.xml' % STAGE)
    if a.instalar:
        sys.exit(subprocess.call([sys.executable, str(RAIZ / 'tools' / 'subir_mapa.py'), str(STAGE), '--solo-local',
                                  '--sin-pruebas']))


if __name__ == '__main__':
    main()
