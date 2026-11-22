"""El mapa propio de Pet Defense (21/11/2026): "que el mapa sea totalmente nuevo o edita ese mapa usado".

Es la Training Cave(small) del cliente (map045.mpc, el 45 que nadie usaba) retocada y con numero propio, el 917
"Pet Defense", para que se vea como el camino de un tower defense:

  * EL CAMINO de los enemigos (el mismo que calcula server/pet_defense_partida.camino, del portal al cristal) pintado
    con losas de piedra oscura (brush 183), tres casillas de ancho donde se pisa;
  * EL PORTAL de los enemigos: el circulo magico verde (objeto 5780) sobre piedra agrietada (brush 190), con calaveras;
  * LA PLAZA DEL CRISTAL: baldosa con circulo grabado (brush 126) alrededor del cristal, con pilares azules (6941) y
    racimos de cristal (6648, 6660);
  * LUCES a lo largo del camino: farolas (5790) y baculos de luz azul (7157), alternando lado, sin tapar las piedras de
    las torres.

La colision no cambia (es la de la cueva), asi que el camino y las piedras de las torres caen donde caian. Los objetos
de la cueva que estaban encima del camino se quitan para que se vea limpio.

Escribe tools/editor_mapas/salida/MAP917.mpc (abrible con el editor) y, con --instalar, corre tools/subir_mapa.py 917
--solo-local (copia, colision del servidor, parche). La fila de stage.xml la pone esto (con el minimapa de la cueva,
smap/045), no subir_mapa (que pondria el del 46).

    python tools/mapa_pet_defense.py [--instalar]
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

STAGE, STAGE_ORIGEN, NOMBRE = 917, 45, 'Pet Defense'
SALIDA = RAIZ / 'tools' / 'editor_mapas' / 'salida' / ('MAP%d.mpc' % STAGE)
STAGE_XML = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'stage.xml'

BRUSH_CAMINO, BRUSH_PLAZA, BRUSH_PORTAL = 183, 126, 190
# "Que el piso se vea armonioso, se ve raro" (21/11/2026): las texturas de fuera de la cueva no se funden con las suyas
# (bordes cuadrados y trozos mas grises con un corte recto), asi que el suelo se queda el de la cueva y el camino lo
# marcan las luces. Con True se vuelve a pintar como antes.
PINTAR_SUELO = False
OBJ_PORTAL, OBJ_CALAVERAS = 5780, 6051
OBJ_LUCES = (5790, 7157)
OBJ_PILAR, OBJ_CRISTALES = 6941, (6648, 6660)
CAPA_OBJ = 192                       # el 'c' de los objetos de la cueva
RADIO_PLAZA, RADIO_PORTAL, RADIO_LIMPIO = 4, 2, 7
PILARES = 5                          # los pilares (grandes: tapan ~4 casillas hacia arriba), en las esquinas a esta distancia
CRISTALES_A = 7                      # y los racimos de cristal, en cruz a esta
CADA_LUZ, LADO_LUZ = 8, 2


def original():
    import fondos_interfaz as fi
    return fi.del_cliente('map\\map%03d.mpc' % STAGE_ORIGEN)


def _celda(m, x, y):
    """Indice de la celda de la casilla del SERVIDOR (x, y): la y del servidor cuenta desde abajo."""
    return ((m['h'] - 1 - y) * m['w'] + x) * 6


def _se_pisa(m, x, y):
    return 0 <= x < m['w'] and 0 <= y < m['h'] and m['celdas'][_celda(m, x, y) + 1] == 0


def _pintar(m, cel, casillas, brush):
    for x, y in casillas:
        if _se_pisa(m, x, y):
            cel[_celda(m, x, y)] = brush


def _objeto(m, sid, x, y):
    return [int(sid), x * 32 + 16, (m['h'] - 1 - y) * 32 + 16, 0, 0, CAPA_OBJ, '00' * 50]


def _casilla_obj(m, o):
    return (o[1] // 32, m['h'] - 1 - o[2] // 32)


def generar(d=None):
    """El mapa retocado, como dict de mpcio."""
    import pet_defense as pd
    import pet_defense_partida as pp
    m = mpcio.leer(d or original())
    mp = pd.config()['mapa']
    portal, cristal = tuple(mp['portal']), tuple(mp['cristal'])
    ruta = pp.camino(STAGE_ORIGEN, portal, cristal)
    if not ruta:
        raise SystemExit('no hay camino del portal %s al cristal %s' % (portal, cristal))
    espacios = set(pp.espacios(STAGE_ORIGEN, ruta, int(mp['separacion_espacios']), int(mp['distancia_espacio'])))
    cel = bytearray(m['celdas'])

    camino = {(x + dx, y + dy) for x, y in ruta for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    plaza = {(cristal[0] + dx, cristal[1] + dy) for dx in range(-RADIO_PLAZA, RADIO_PLAZA + 1)
             for dy in range(-RADIO_PLAZA, RADIO_PLAZA + 1)}
    zona_portal = {(portal[0] + dx, portal[1] + dy) for dx in range(-RADIO_PORTAL, RADIO_PORTAL + 1)
                   for dy in range(-RADIO_PORTAL, RADIO_PORTAL + 1)}
    if PINTAR_SUELO:
        _pintar(m, cel, camino, BRUSH_CAMINO)
        _pintar(m, cel, zona_portal, BRUSH_PORTAL)
        _pintar(m, cel, plaza, BRUSH_PLAZA)
        m['tilesets'] = sorted(set(m['tilesets']) | {BRUSH_CAMINO, BRUSH_PLAZA, BRUSH_PORTAL})
    m['celdas'] = bytes(cel)

    # Fuera los objetos de la cueva que tapan el camino, la plaza o el portal
    limpio = set(ruta) | zona_portal | {(cristal[0] + dx, cristal[1] + dy) for dx in range(-RADIO_LIMPIO, RADIO_LIMPIO + 1)
                                        for dy in range(-RADIO_LIMPIO, RADIO_LIMPIO + 1)}
    antes = len(m['objetos'])
    m['objetos'] = [o for o in m['objetos'] if _casilla_obj(m, o) not in limpio]
    quitados = antes - len(m['objetos'])

    ocupado = set(camino) | plaza | zona_portal | {(x + dx, y + dy) for x, y in espacios
                                                   for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    nuevos = [_objeto(m, OBJ_PORTAL, *portal)]
    for dx, dy in ((-2, 3), (3, -2), (-3, -2)):
        t = (portal[0] + dx, portal[1] + dy)
        if _se_pisa(m, *t):
            nuevos.append(_objeto(m, OBJ_CALAVERAS, *t))
    for k, (dx, dy) in enumerate(((-PILARES, -PILARES), (PILARES, -PILARES), (-PILARES, PILARES), (PILARES, PILARES))):
        t = (cristal[0] + dx, cristal[1] + dy)
        if _se_pisa(m, *t) and t not in camino:
            nuevos.append(_objeto(m, OBJ_PILAR, *t))
    for k, (dx, dy) in enumerate(((CRISTALES_A, 0), (0, CRISTALES_A), (0, -CRISTALES_A), (-CRISTALES_A, 0))):
        t = (cristal[0] + dx, cristal[1] + dy)
        if _se_pisa(m, *t) and t not in camino:
            nuevos.append(_objeto(m, OBJ_CRISTALES[k % 2], *t))
    # Luces: cada CADA_LUZ casillas del camino, a LADO_LUZ de el, alternando lado
    lado, luces = 1, 0
    for i in range(CADA_LUZ // 2, len(ruta) - 4, CADA_LUZ):
        x, y = ruta[i]
        ax, ay = ruta[max(0, i - 2)]
        bx, by = ruta[min(len(ruta) - 1, i + 2)]
        px, py = (-(by - ay) > 0) - (-(by - ay) < 0), ((bx - ax) > 0) - ((bx - ax) < 0)
        for s in (lado, -lado):
            t = (x + px * s * LADO_LUZ, y + py * s * LADO_LUZ)
            if _se_pisa(m, *t) and t not in ocupado:
                nuevos.append(_objeto(m, OBJ_LUCES[luces % 2], *t))
                luces += 1
                break
        lado = -lado
    m['objetos'] += nuevos
    m['_resumen'] = dict(camino=len(ruta), pintadas=len(camino), quitados=quitados, puestos=len(nuevos), luces=luces)
    return m


def fila_stage(texto):
    """stage.xml con la fila del 917: la de la cueva (45) con su nombre y su mapa (idempotente)."""
    if ('編號="%d"' % STAGE) in texto:
        return texto
    m = re.search(r'([ \t]*)<場景 編號="%d" [^\n]*?/>(\r?\n)' % STAGE_ORIGEN, texto)
    if not m:
        raise SystemExit('no esta el mapa %d en stage.xml' % STAGE_ORIGEN)
    fila = m.group(0)
    fila = fila.replace('編號="%d"' % STAGE_ORIGEN, '編號="%d"' % STAGE)
    fila = re.sub(r'名稱="[^"]*"', '名稱="%s"' % NOMBRE, fila, count=1)
    fila = re.sub(r'(地圖檔="map\\)map\d+\.mpc"', r'\g<1>map%d.mpc"' % STAGE, fila, count=1)
    return texto[:m.end()] + fila + texto[m.end():]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--instalar', action='store_true', help='y corre tools/subir_mapa.py %d --solo-local' % STAGE)
    a = ap.parse_args()
    m = generar()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    datos = mpcio.escribir(m)
    mpcio.leer(datos)                                       # que se relee bien
    SALIDA.write_bytes(datos)
    print('mapa %d: %s -> %s' % (STAGE, m['_resumen'], SALIDA))
    crudo = STAGE_XML.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    nuevo = fila_stage(texto)
    if nuevo != texto:
        STAGE_XML.write_bytes((b'\xef\xbb\xbf' if bom else b'') + nuevo.encode('utf-8'))
        print('fila del %d en stage.xml' % STAGE)
    if a.instalar:
        sys.exit(subprocess.call([sys.executable, str(RAIZ / 'tools' / 'subir_mapa.py'), str(STAGE), '--solo-local']))


if __name__ == '__main__':
    main()
