"""Genera la instancia oscura de Lv55-60: un mapa .mpc NUEVO (stage 46) y su plantilla de monstruos.

El mapa es una cueva hecha de cero (salas unidas por pasillos, tierra oscura del Training Cave y setas/estalactitas como
decoracion); no es una copia de ningun mapa del juego. Se escribe en `tools/mapas_propios/map046.mpc` y `instalar` lo reparte:
parches/extras/map (jugadores), update28.pak del cliente local y transitable.bin del servidor.

Los monstruos usan sprites que SI estan en el cliente (shape/mon/*/<sprite>_wait.spr). Con los de la serie 5254-5258
(Cursed Barft, Cursed Larry...) no se veia nada: esos sprites no vienen en ningun .pak.

    python tools/generar_instancia_oscura.py            # mapa + plantilla
    python tools/generar_instancia_oscura.py --instalar # ademas: parche, pack del cliente local y transitable.bin
"""
import collections
import json
import pathlib
import random
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
sys.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))
sys.stdout.reconfigure(encoding='utf-8')

STAGE = 900                    # numero propio: el mapa 46 (Training Cave) lo sirve data1.pak y gana al del parche
BASE = 46                      # del que se toman cabecera y pinceles (el original, de data1.pak)
ANCHO, ALTO = 200, 125
SEMILLA = 460055
ENTIDAD_BASE = 7550000
MAPA_PROPIO = RAIZ / 'tools' / 'mapas_propios' / 'map900.mpc'
NOMBRE_STAGE = 'Dark Cavern'

SUELO, ROCA, BORDE = 46, 65, 64        # pinceles de map046: tierra, roca y la franja que las une
DECORADO_BLOQUEA = (5539, 5540, 5541, 5542, 9211, 9214, 9215, 9216, 9217, 9218, 9219, 9220, 9221, 9222)   # setas grandes, estalactitas
DECORADO_LIBRE = (5505, 5514, 5530, 5531, 5543, 5546)                                                      # setas pequenas, helechos

# (npc_type, nombre, sprite, nivel)
NORMALES = [(204, 'Evil Wind Elf', 42059, 55), (205, 'Mirror Elf', 42061, 55), (206, 'Evil Earth Elf', 42062, 56),
            (843, 'Gold Fly', 42276, 60), (847, 'Flame Fly', 42277, 60), (953, 'Terra Miner', 42283, 60)]
ELITES = [(195, 'Savage Chief Apu', 42203, 60), (810, 'Soul Slalin', 42280, 60), (208, 'Fane Protector', 42093, 60)]
JEFE = (209, 'Dragonkin Moowad', 42091, 65)
VIDA = 0.7                              # todos los bichos con un 30% menos de vida
ELITE_HP, ELITE_ATK = 1.0 * VIDA, 1.15
JEFE_HP, JEFE_ATK = 40.0 * VIDA, 1.3


def _vecinos8(x, y):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                yield x + dx, y + dy


def hacer_cueva(azar):
    """(libre[ALTO][ANCHO] de bool, salas [(cx, cy, rx, ry)]) con la entrada a la izquierda y el jefe a la derecha."""
    libre = [[False] * ANCHO for _ in range(ALTO)]

    def elipse(cx, cy, rx, ry):
        for y in range(max(2, cy - ry), min(ALTO - 2, cy + ry + 1)):
            for x in range(max(2, cx - rx), min(ANCHO - 2, cx + rx + 1)):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    libre[y][x] = True

    def pasillo(a, b, r=2):
        n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        for i in range(n + 1):
            x = round(a[0] + (b[0] - a[0]) * i / n)
            y = round(a[1] + (b[1] - a[1]) * i / n)
            elipse(x, y, r, r)

    salas = [(20, 62, 11, 9)]
    for i in range(1, 12):
        x = 20 + i * 12 + azar.randint(-1, 1)
        y = azar.randint(24, 100)
        while abs(y - salas[-1][1]) < 18:
            y = azar.randint(24, 100)
        salas.append((x, y, azar.randint(8, 12), azar.randint(6, 9)))
    salas.append((183, 62, 13, 12))                      # sala del jefe
    for s in salas:
        elipse(*s)
    for a, b in zip(salas, salas[1:]):
        pasillo(a[:2], b[:2])
    for a, b in ((salas[2], salas[4]), (salas[5], salas[7]), (salas[8], salas[10])):    # atajos
        pasillo(a[:2], b[:2], 1)
    # bordes irregulares: se rompe la elipse y se alisa
    for y in range(3, ALTO - 3):
        for x in range(3, ANCHO - 3):
            borde = any(libre[v][u] != libre[y][x] for u, v in _vecinos8(x, y))
            if borde and azar.random() < 0.28:
                libre[y][x] = not libre[y][x]
    for _ in range(2):
        nuevo = [fila[:] for fila in libre]
        for y in range(3, ALTO - 3):
            for x in range(3, ANCHO - 3):
                n = sum(libre[v][u] for u, v in _vecinos8(x, y))
                nuevo[y][x] = n >= 5 if not libre[y][x] else n >= 3
        libre = nuevo
    # solo la zona que se camina desde la entrada
    origen = (salas[0][0], salas[0][1])
    vistos = {origen}
    cola = collections.deque([origen])
    while cola:
        x, y = cola.popleft()
        for u, v in _vecinos8(x, y):
            if 0 <= u < ANCHO and 0 <= v < ALTO and libre[v][u] and (u, v) not in vistos:
                vistos.add((u, v))
                cola.append((u, v))
    if any((s[0], s[1]) not in vistos for s in salas):
        raise ValueError('la cueva quedo partida')
    return [[(x, y) in vistos for x in range(ANCHO)] for y in range(ALTO)], salas


def hacer_mpc(libre, azar):
    """Los bytes del .mpc: se parte de la cabecera/tilesets de map046 y se cambian casillas y objetos."""
    import os
    argv, sys.argv = sys.argv, ['x', os.environ.get('AO_CLIENTE', r'C:\AO\Angels Online'), '0']
    import editor_mapas as E
    import mpcio
    E.cargar()
    sys.argv = argv
    import cliente_local
    original = cliente_local._extraer_archivo_pak(pathlib.Path(cliente_local.ruta_cliente()) / 'data1.pak', 'MAP' + chr(92) + 'MAP%03d.MPC' % BASE)
    base = mpcio.leer(original)
    plantillas = {}
    for o in base['objetos']:
        plantillas.setdefault(o[0], o)
    cel = bytearray(ANCHO * ALTO * 6)
    cerca = lambda x, y: any(0 <= u < ANCHO and 0 <= v < ALTO and libre[v][u] for u, v in _vecinos8(x, y))
    for y in range(ALTO):
        for x in range(ANCHO):
            i = (y * ANCHO + x) * 6
            if libre[y][x]:
                cel[i] = SUELO
            else:
                cel[i] = BORDE if cerca(x, y) else ROCA
                cel[i + 1] = 2
    objetos = []

    def poner(oid, x, y):
        t = plantillas[oid]
        objetos.append([oid, x * 32 + 16, y * 32 + 24, t[3], t[4], t[5], t[6]])

    for y in range(ALTO):
        for x in range(ANCHO):
            if not libre[y][x] and cerca(x, y) and azar.random() < 0.16:
                poner(azar.choice(DECORADO_BLOQUEA), x, y)
            elif libre[y][x] and azar.random() < 0.012:
                poner(azar.choice(DECORADO_LIBRE), x, y)
    m = dict(base)
    m.update(w=ANCHO, h=ALTO, celdas=bytes(cel), objetos=objetos, extra=b'', rutas=[], puntos=[], resto='')
    datos = mpcio.escribir(m)
    assert mpcio.leer(datos)['celdas'] == bytes(cel)
    return datos, len(objetos)


SELLO = (208, 'Seal Guardian', 42093, 60)       # (npc_type, nombre base, sprite, nivel); el nombre lleva I, II, III
RADIO_PUERTA = 5
OBJETO_BARRERA = 60402                         # '光柵', la cortina de luz que el Holy Battlefield dibuja desde el servidor


def puerta_en(libre, a, b):
    """(x, y) de la casilla del pasillo entre las salas a y b que queda mas lejos de las dos."""
    f = lambda s, x, y: ((x - s[0]) / s[2]) ** 2 + ((y - s[1]) / s[3]) ** 2
    n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    mejor = None
    for i in range(n + 1):
        x = round(a[0] + (b[0] - a[0]) * i / n)
        y = round(a[1] + (b[1] - a[1]) * i / n)
        v = min(f(a, x, y), f(b, x, y))
        if libre[y][x] and (mejor is None or v > mejor[0]):
            mejor = (v, x, y)
    return mejor[1], mejor[2]


def zona_de(libre, a, b, centro):
    """Franja de 3 casillas de grosor que cruza el pasillo entre las salas a y b por `centro` (casillas del mapa).

    Devuelve (zona, barrera): zona = todas las casillas caminables de la franja (por ahi no se pasa mientras la puerta
    este cerrada); barrera = las del centro, donde se dibuja la cortina de luz.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    largo = (dx * dx + dy * dy) ** 0.5
    zona, barrera = set(), []
    for y in range(centro[1] - RADIO_PUERTA - 2, centro[1] + RADIO_PUERTA + 3):
        for x in range(centro[0] - RADIO_PUERTA - 2, centro[0] + RADIO_PUERTA + 3):
            if 0 <= x < ANCHO and 0 <= y < ALTO and libre[y][x]:
                proy = ((x - centro[0]) * dx + (y - centro[1]) * dy) / largo
                if abs(proy) <= 1.5:
                    zona.add((x, y))
                    if abs(proy) <= 0.6:
                        barrera.append((x, y))
    return zona, barrera


def alcanzable(libre, origen, cerradas):
    """Casillas a las que se llega desde `origen` sin pisar ninguna de las zonas (sets) cerradas."""
    bloqueadas = set().union(*cerradas) if cerradas else set()
    vistos = {origen}
    cola = collections.deque([origen])
    while cola:
        x, y = cola.popleft()
        for u, v in _vecinos8(x, y):
            if 0 <= u < ANCHO and 0 <= v < ALTO and libre[v][u] and (u, v) not in vistos and (u, v) not in bloqueadas:
                vistos.add((u, v))
                cola.append((u, v))
    return vistos


def hacer_plantilla(libre, salas, azar):
    # y del servidor = ALTO - 1 - y del mapa
    tile = lambda x, y: (x, ALTO - 1 - y)
    cheb = lambda a, b: max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    llegada = tile(salas[0][0] + 4, salas[0][1])
    jefe_tile = tile(salas[-1][0] + 4, salas[-1][1])
    usados, spawns, eid = [llegada, jefe_tile], [], [ENTIDAD_BASE]
    # puertas de los puzzles: en pasillos que ningun atajo salta (las salas 4->5 y 11->12)
    pa = puerta_en(libre, salas[4], salas[5])
    pb = puerta_en(libre, salas[11], salas[12])
    za, ba = zona_de(libre, salas[4], salas[5], pa)
    zb, bb = zona_de(libre, salas[11], salas[12], pb)
    puertas_mapa = [za, zb]
    cerca_de_puerta = {(x + dx, y + dy) for x, y in za | zb for dx in range(-2, 3) for dy in range(-2, 3)}

    def piso(x, y):
        return 0 <= x < ANCHO and 0 <= y < ALTO and libre[y][x]

    def poner(tipo, centro, radio, elite=False, extra=None):
        for _ in range(300):
            x, y = centro[0] + azar.randint(-radio, radio), centro[1] + azar.randint(-radio, radio)
            if not all(piso(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                continue
            t = tile(x, y)
            if (x, y) in cerca_de_puerta:
                continue
            if all(cheb(t, u) >= (4 if elite else 3) for u in usados) and cheb(t, llegada) >= 16:
                eid[0] += 1
                npc, nombre, sprite, nivel = tipo
                e = {'entity_id': eid[0], 'nombre': nombre, 'npc_type': npc, 'sprite': sprite, 'klass': 1, 'monstruo': True,
                     'tile': list(t), 'direccion': azar.randint(0, 7), 'visible': 0, 'nivel': nivel}
                if elite:
                    e.update(hp_mult=ELITE_HP, atk_mult=ELITE_ATK, elite=True)
                else:
                    e['hp_mult'] = VIDA
                if extra:
                    e.update(extra)
                spawns.append(e)
                usados.append(t)
                return

    # Guardianes del Sello: dos antes de la primera puerta (salas 2 y 4) y uno entre las dos puertas (sala 10)
    for n, sala in ((1, 2), (2, 4), (3, 10)):
        tipo = (SELLO[0], 'Seal Guardian ' + 'I' * n, SELLO[2], SELLO[3])
        poner(tipo, salas[sala][:2], 3, elite=True, extra={'sello': n, 'hp_mult': 2.0 * VIDA})
    for s in salas[1:-1]:
        for _ in range(5):
            poner(azar.choice(NORMALES), s[:2], min(s[2], s[3]) - 2)
        poner(azar.choice(ELITES), s[:2], min(s[2], s[3]) - 2, elite=True)
    # sala del jefe: guardia de elites y el jefe en el fondo
    cx, cy = salas[-1][:2]
    for _ in range(4):
        poner(random.Random(azar.random()).choice(ELITES), (cx - 3, cy), 8, elite=True)
    for _ in range(6):
        poner(azar.choice(NORMALES), (cx - 3, cy), 10)
    eid[0] += 1
    npc, nombre, sprite, nivel = JEFE
    spawns.append({'entity_id': eid[0], 'nombre': nombre, 'npc_type': npc, 'sprite': sprite, 'klass': 1, 'monstruo': True,
                   'tile': list(jefe_tile), 'direccion': 3, 'visible': 0, 'nivel': nivel,
                   'hp_mult': JEFE_HP, 'atk_mult': JEFE_ATK, 'jefe': True})
    sellos = [e['entity_id'] for e in spawns if e.get('sello')]
    assert len(sellos) == 3, 'faltan Guardianes del Sello'
    # el diseno se comprueba: cerradas las puertas no se llega al jefe; abierta la primera, tampoco; abiertas las dos, si
    origen = (salas[0][0], salas[0][1])
    en_mapa = lambda t: (t[0], ALTO - 1 - t[1])
    jefe_m = en_mapa(jefe_tile)
    sello_m = {e['sello']: en_mapa(e['tile']) for e in spawns if e.get('sello')}
    r_ambas = alcanzable(libre, origen, puertas_mapa)
    assert sello_m[1] in r_ambas and sello_m[2] in r_ambas and sello_m[3] not in r_ambas and jefe_m not in r_ambas
    r_a = alcanzable(libre, origen, puertas_mapa[1:])
    assert sello_m[3] in r_a and jefe_m not in r_a
    assert jefe_m in alcanzable(libre, origen, [])
    casillas = lambda zs: sorted([list(tile(x, y)) for x, y in zs])
    puzzles = {'sellos': sellos, 'objeto_barrera': OBJETO_BARRERA,
               'puertas': [{'id': 'A', 'nombre': 'to the deep cave', 'zona': casillas(za), 'barrera': casillas(ba), 'requiere': [1, 2]},
                           {'id': 'B', 'nombre': 'to the boss chamber', 'zona': casillas(zb), 'barrera': casillas(bb), 'requiere': [1, 2, 3]}]}
    datos = {'_nota': 'Instancia oscura Lv55-60 en el mapa propio map900 (Dark Cavern, cueva nueva): grupos de bichos normales y elites por las salas y, '
                      'al fondo, el jefe Dragonkin Moowad (suelta piedras de Holy Battlefield). Generado con tools/generar_instancia_oscura.py.',
             'stage': STAGE, 'spawns': spawns, 'recursos': [], 'puzzles': puzzles}
    return datos, llegada, jefe_tile, tile(salas[0][0] - 7, salas[0][1])


def registrar_stage(extras):
    """setting/eng/stage.xml con la fila del stage 900 (copia de la del 46: oscuro, sin flags) en parches/extras."""
    import parche
    bs = chr(92)
    raw = (RAIZ / 'parches' / 'update27.pak').read_bytes()
    base = {n: parche._leer(raw, e) for n, e in parche._directorio(raw).items()}['SETTING' + bs + 'ENG' + bs + 'STAGE.XML'].decode('utf-8')
    if '編號="%d"' % STAGE not in base:
        # la minimapa (雷達圖) se queda con la del Training Cave: no hay imagen smap para el mapa nuevo
        fila = ('    <場景 編號="%d" 名稱="%s" 地圖檔="map' + bs + 'map%03d.mpc" 筆刷檔="brush' + bs + 'brush.gic" '
                '雷達圖="smap' + bs + '046" 配樂檔1="music' + bs + '11.ogg" 亮度="160" 天氣="0" 不懲罰="是" />\r\n'
                ) % (STAGE, NOMBRE_STAGE, STAGE)
        fin = base.rindex('<DEFINE')
        base = base[:fin].rstrip(' ') + fila + '    ' + base[fin:]
    destino = extras / 'setting' / 'eng'
    destino.mkdir(parents=True, exist_ok=True)
    (destino / 'stage.xml').write_bytes(base.encode('utf-8'))


def instalar(datos):
    import instalar_mapa
    import cliente_local
    extras = RAIZ / 'parches' / 'extras'
    (extras / 'map').mkdir(parents=True, exist_ok=True)
    (extras / 'map' / ('map%03d.mpc' % STAGE)).write_bytes(datos)
    viejo = extras / 'map' / ('map%03d.mpc' % BASE)         # el 46 vuelve a ser el original: no se reparte el nuestro
    if viejo.exists():
        viejo.unlink()
    registrar_stage(extras)
    original = cliente_local._extraer_archivo_pak(pathlib.Path(cliente_local.ruta_cliente()) / 'data1.pak', 'MAP' + chr(92) + 'MAP%03d.MPC' % BASE)
    instalar_mapa.actualizar_transitable(BASE, original)
    instalar_mapa.actualizar_transitable(STAGE, datos)
    print('instalado: parches/extras (map%03d.mpc + stage.xml), transitable.bin (46 original, %d nuevo)' % (STAGE, STAGE))


def main():
    # una semilla puede dar una cueva partida o puertas que no cortan el pasillo: se prueba la siguiente
    for intento in range(60):
        semilla = SEMILLA + intento * 7
        try:
            azar = random.Random(semilla)
            libre, salas = hacer_cueva(azar)
            plantilla, llegada, jefe, vuelta = hacer_plantilla(libre, salas, random.Random(semilla + 1))
            break
        except (ValueError, AssertionError, TypeError):
            continue
    else:
        raise SystemExit('ninguna semilla dio una cueva valida')
    datos, nobj = hacer_mpc(libre, azar)
    if MAPA_PROPIO.exists() and MAPA_PROPIO.read_bytes() != datos and '--forzar' not in sys.argv:
        raise SystemExit('%s ya existe y es distinto del generado (¿lo editaste en el editor de mapas?). Con --forzar se pisa; '
                         'tambien se pisan la plantilla de monstruos y los puzzles.' % MAPA_PROPIO)
    MAPA_PROPIO.parent.mkdir(parents=True, exist_ok=True)
    MAPA_PROPIO.write_bytes(datos)
    destino = RAIZ / 'server' / 'plantillas' / 'dark_cavern.json'
    destino.write_text(json.dumps(plantilla, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    n = collections.Counter('jefe' if s.get('jefe') else 'elite' if s.get('elite') else 'normal' for s in plantilla['spawns'])
    print('semilla', semilla, '| mapa', MAPA_PROPIO, len(datos), 'bytes,', nobj, 'objetos; casillas libres', sum(map(sum, libre)))
    print('monstruos', dict(n), '| llegada', llegada, '| jefe', jefe, '| portal de vuelta', vuelta)
    if '--instalar' in sys.argv:
        instalar(datos)


if __name__ == '__main__':
    main()
