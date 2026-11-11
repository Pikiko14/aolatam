"""La raid Flamefang (11/11/2026): "20 jugadores max, toma un mapa de las expansiones nuevas ... nivel 60, que de items
lvl 60 clase S, rides, items para intensificar ride y gear, con datos tipo wow, usa mob de las nuevas expansiones ...
con stats lvl 60 pero un poco mas fuerte".

El mapa es la escena 902 ("Flamefang Raid"), copia del Flamefang Sanctum (292) instalada con
`tools/subir_mapa.py 902 --instancia`. Aqui se hace lo demas:

  * LOS MONSTRUOS: clones de los del Flamefang (sus dibujos, nombres, IA e inmunidades) con numero propio (239xx),
    nivel 60-65 y stats de nivel 60 algo mas fuertes (STATS). Sus hechizos de nivel 300 (hasta 4542 de dano) se cambian
    por los de fuego de nivel 60 (HECHIZOS). Van a corpus/content.db (de donde el servidor saca nombre, sprite y stats:
    combate._datos) y a parches/extras/setting/eng/monster.xml (nombre y nivel que ve el cliente).
  * LA PLANTILLA server/plantillas/raid_flamefang.json: la entrada, las tres zonas con sus grupos de bichos (de las
    casillas reales del 292, plantillas/flamefang_sanctum.json) y su jefe, donde salen los adds y los numeros de las
    mecanicas. La lee server/raid.py.

    python tools/generar_raid.py                 # monstruos (content.db local + monster.xml) y plantilla
    python3 tools/generar_raid.py --db RUTA      # solo los monstruos en esa content.db (la del VPS)
"""
import argparse
import json
import math
import pathlib
import re
import sqlite3

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / 'server' / 'plantillas' / 'raid_flamefang.json'
POBLACION_292 = RAIZ / 'server' / 'plantillas' / 'flamefang_sanctum.json'
MONSTER_XML = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'monster.xml'
STAGE = 902

# Por papel: los stats de la raid. Salen de la mediana de los monstruos reales de nivel 56-64 (vida 10.000, ataque 492,
# defensa 680, m.atk 443, m.def 258, precision 337, agilidad 207, exp 849) "un poco mas fuertes".
# "Que los mob tengan stat de lvl 60 plss, estan muy rotos" (11/11/2026): los de nivel 60 de verdad (la mediana de
# arriba) sin el "un poco mas fuertes" de la primera version (trash 12.000 de vida y 560 de ataque, jefes con 900-1100).
# Las elites y los jefes solo llevan mas vida; el ataque es el de un nivel 60, poco mas.
# 11/11/2026, "que los mob y elites tengan hp y stat de mob lvl 80 y los jefes de mob lvl 100 ... los elites sean mas
# fuertes que los normales lvl 80". Medianas de content.db (monster, id < 23900, nivel +-3):
#   80 normal: hp 4827, atk 677, def 985, matk 582, mdef 325, acc 422, agi 258
#  100 jefe:   hp 98860, atk 1349, def 2404, matk 846, mdef 885, acc 587, agi 357
# Como con los de nivel 60: stats x1,1 y la vida de raid (unas 4 veces la normal). Los jefes conservan la vida de antes
# (2,5 / 3,5 / 5 M): con 2400 de defensa los jugadores de nivel 60 les hacen ~2,4 veces menos dano, y por eso el enrage
# de MECANICAS se doblo.
STATS = {
    'trash': dict(nivel=80, hp=20000, atk=745, var=5, df=1100, matk=640, mdef=340, acc=435, agi=265, exp=3400),
    'elite': dict(nivel=80, hp=50000, atk=820, var=5, df=1180, matk=700, mdef=370, acc=455, agi=275, exp=10000),
    'add': dict(nivel=80, hp=12000, atk=720, var=5, df=1050, matk=620, mdef=330, acc=430, agi=260, exp=900),
    'jefe1': dict(nivel=100, hp=2500000, atk=1400, var=5, df=2400, matk=870, mdef=890, acc=590, agi=360, exp=120000),
    'jefe2': dict(nivel=100, hp=3500000, atk=1450, var=5, df=2450, matk=890, mdef=900, acc=595, agi=362, exp=160000),
    'jefe3': dict(nivel=100, hp=5000000, atk=1500, var=5, df=2500, matk=910, mdef=920, acc=600, agi=365, exp=240000),
}
# TODOS los hechizos de los clones son de nivel 60: los originales son de nivel 300 (Oath Wrap V 2930, Explosive Shell
# V 4542, y las elites traian 10840 / 10843 que pegaban 607 y 813) o buffs V (Spike Armor, Armor Break, Deadly
# Sweep...). Fuego: Phoenix Fire I (212, 132 de dano), Fireball Hit IV (258) y III (241).
HECHIZOS_POR_PAPEL = {'trash': (212, 258), 'elite': (212, 241), 'add': (241, 258),
                      'jefe1': (212, 258), 'jefe2': (258, 241), 'jefe3': (212, 241)}
VELOCIDAD_ATAQUE, VELOCIDAD = 70, 90        # los de nivel 60 (los jefes del 292 iban a 120 y 150)

# (numero propio, original del 292, papel)
CLONES = [
    (23910, 17641, 'trash'), (23911, 17642, 'trash'), (23912, 17644, 'trash'), (23913, 17643, 'trash'),
    (23914, 17645, 'trash'), (23915, 17646, 'trash'), (23916, 17648, 'trash'), (23917, 17650, 'trash'),
    (23918, 17649, 'trash'), (23919, 17647, 'trash'),
    (23930, 17651, 'elite'), (23931, 17652, 'elite'), (23932, 17653, 'elite'), (23933, 17654, 'elite'),
    (23934, 17655, 'elite'),
    (23940, 17660, 'jefe1'), (23941, 17659, 'jefe2'), (23942, 17661, 'jefe3'),
    (23943, 17662, 'add'), (23944, 17663, 'add'),
]
DE_ORIGINAL = {o: n for n, o, _p in CLONES}

# Las zonas, por donde caen las casillas del 292: la entrada arriba a la derecha, el Infernal Lavamon abajo a la
# derecha, el Hellfire Razorex en el centro y Satrixia abajo a la izquierda.
ZONAS = [
    dict(nombre='The Ember Gate', jefe=23940, casilla_jefe=[244, 154], inicio=[270, 40],
         dentro=lambda x, y: x >= 215 and y < 125, adds=23943, grupos=6),
    dict(nombre='The Burning Hall', jefe=23941, casilla_jefe=[196, 134], inicio=[205, 72],
         dentro=lambda x, y: 115 <= x < 215, adds=None, grupos=6),
    dict(nombre="Satrixia's Throne", jefe=23942, casilla_jefe=[63, 162], inicio=[100, 72],
         dentro=lambda x, y: x < 115, adds=23944, grupos=6),
]
ENTRADA = [278, 9]
POR_GRUPO = 4          # bichos normales por grupo
ELITE_CADA = 2         # una elite cada tantos grupos
RADIO_GRUPO = 7

# Las mecanicas tipo WoW (server/raid.py). Tiempos en segundos; dano en % de la vida maxima del jugador.
MECANICAS = {
    '23940': {   # Infernal Lavamon
        'enrage': 720,
        'lava': {'cada': 18, 'marcados': 3, 'aviso': 3.0, 'radio': 2, 'dano': 45},
        'adds_al': [50], 'adds': 6,
    },
    '23941': {   # Hellfire Razorex
        'enrage': 840,
        'garra': {'cada': 10, 'mas_por_pila': 25, 'dura': 20},
        'aliento': {'cada': 22, 'aviso': 2.5, 'largo': 6, 'dano': 60},
        'furia_al': 30, 'furia_velocidad': 1.3,
    },
    '23942': {   # Satrixia
        'enrage': 1080,
        'nova': {'cada': 30, 'aviso': 3.0, 'dano': 35},
        'fase2_al': 66, 'adds': 8,
        'fase3_al': 33,
        'condena': {'cada': 25, 'aviso': 5.0, 'radio': 4, 'dano': 70},
    },
}
# El botin (por jugador, una vez por semana y jefe). Los ids de las cajas y objetos los pone raid.py en BOTIN.
LOCKOUT_DIA = 0        # lunes: el lockout semanal se reinicia el lunes a las 00:00 (hora del servidor)


# ---------------------------------------------------------------------------------------------- monstruos
def _fila_db(con, original):
    cols = [c[1] for c in con.execute('pragma table_info(monster)')]
    fila = con.execute('select * from monster where id=?', (str(original),)).fetchone()
    return cols, dict(zip(cols, fila))


def content_db(ruta):
    """Los clones en la tabla monster de esa content.db (quita los de antes)."""
    con = sqlite3.connect(ruta)
    for nuevo, original, papel in CLONES:
        cols, f = _fila_db(con, original)
        s = STATS[papel]
        f.update({'id': str(nuevo), 'level': str(s['nivel']), 'hp': str(s['hp']), 'atk_avg': str(s['atk']),
                  'atk_var': str(s['var']), 'def': str(s['df']), 'matk': str(s['matk']), 'mdef': str(s['mdef']),
                  'accuracy': str(s['acc']), 'agility': str(s['agi']), 'exp_value': str(s['exp']), 'crit_rate': '5',
                  'res_lightning': '20', 'res_fire': '40', 'res_ice': '20', 'res_corrosion': '20', 'res_body': '20',
                  'res_mind': '40', 'drop_id': '0'})
        h1, h2 = HECHIZOS_POR_PAPEL[papel]
        for k, h in (('攻擊法術1', h1), ('攻擊法術2', h2), ('攻擊法術3', h1), ('攻擊法術4', h2)):
            if k in f:
                f[k] = str(h)
        f.update({'atk_speed': str(VELOCIDAD_ATAQUE), 'move_speed': str(VELOCIDAD)})
        for k in ('腐蝕攻擊', '火焰攻擊', '雷電攻擊', '寒冰攻擊', '特殊怪傷害調整', '召喚怪物', '常駐法術1', '常駐法術2',
                  '補血法術1', '補血法術2', '施展機率'):
            if k in f:
                f[k] = None
        con.execute('delete from monster where id=?', (str(nuevo),))
        con.execute('insert into monster (%s) values (%s)' % (','.join('"%s"' % c for c in cols), ','.join('?' * len(cols))),
                    [f[c] for c in cols])
    con.commit()
    con.close()
    print('content.db: %d monstruos de la raid en %s' % (len(CLONES), ruta))


def _fila_xml(texto, original):
    m = re.search(r'<npc 編號="%d"[^>]*/>' % original, texto)
    if not m:
        raise SystemExit('monster.xml no tiene el %d' % original)
    return m.group(0)


def monster_xml():
    crudo = MONSTER_XML.read_bytes()
    texto = crudo.decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in texto else '\n'
    texto = re.sub(r'[ \t]*<!-- aolat raid -->.*?<!-- /aolat raid -->\r?\n', '', texto, flags=re.S)
    filas = []
    for nuevo, original, papel in CLONES:
        s = STATS[papel]
        f = _fila_xml(texto, original)
        cambios = {'編號': nuevo, '等級': s['nivel'], 'HP': s['hp'], '平均攻擊': s['atk'], '攻擊變數': s['var'],
                   '防禦': s['df'], '魔攻': s['matk'], '魔防': s['mdef'], '精準': s['acc'], '靈敏': s['agi'],
                   '經驗價值': s['exp'], '掉寶編號': 0}
        for k, v in cambios.items():
            f = re.sub(r'(?<= )%s="[^"]*"' % k, lambda _m, k=k, v=v: '%s="%s"' % (k, v), f, count=1)
        h1, h2 = HECHIZOS_POR_PAPEL[papel]
        f = re.sub(r' (攻擊法術[1-4]|常駐法術[12]|補血法術[12]|施展機率|腐蝕攻擊|火焰攻擊|雷電攻擊|寒冰攻擊)="[^"]*"', '', f)
        f = f.replace(' 平時音效=', ' 攻擊法術1="%d" 攻擊法術2="%d" 攻擊法術3="%d" 攻擊法術4="%d" 平時音效='
                      % (h1, h2, h1, h2), 1)
        f = re.sub(r'(?<= )攻擊速度="[^"]*"', '攻擊速度="%d"' % VELOCIDAD_ATAQUE, f, count=1)
        f = re.sub(r'(?<= )移動速度="[^"]*"', '移動速度="%d"' % VELOCIDAD, f, count=1)
        filas.append('    ' + f)
    bloque = nl.join(['    <!-- aolat raid -->'] + filas + ['    <!-- /aolat raid -->']) + nl
    fin = texto.rindex('</')
    texto = texto[:fin] + bloque + texto[fin:]
    MONSTER_XML.write_bytes((b'\xef\xbb\xbf' if crudo.startswith(b'\xef\xbb\xbf') else b'') + texto.encode('utf-8'))
    print('monster.xml: %d filas de la raid' % len(filas))


# ---------------------------------------------------------------------------------------------- plantilla
def _grupos(puntos, cuantos):
    """Agrupa casillas cercanas (voraz, RADIO_GRUPO) y devuelve los `cuantos` grupos mas grandes."""
    libres = list(puntos)
    grupos = []
    while libres:
        semilla = libres.pop(0)
        g = [semilla] + [p for p in libres if math.dist(p[:2], semilla[:2]) <= RADIO_GRUPO]
        libres = [p for p in libres if p not in g]
        grupos.append(g)
    grupos.sort(key=len, reverse=True)
    return grupos[:cuantos]


def _pisable(x, y, radio=5):
    """La casilla pisable mas cercana a (x, y), o None. Hay bichos del 292 en casillas a las que no se llega (la
    colision del servidor dice que no se pisan, en el 292 igual que en la copia)."""
    import sys
    sys.path.insert(0, str(RAIZ / 'server'))
    import transitable
    if transitable.se_pisa(STAGE, x, y):
        return [x, y]
    cerca = [(math.dist((x, y), (x + dx, y + dy)), x + dx, y + dy)
             for dx in range(-radio, radio + 1) for dy in range(-radio, radio + 1)
             if transitable.se_pisa(STAGE, x + dx, y + dy)]
    return list(min(cerca)[1:]) if cerca else None


def plantilla():
    spawns = [s for s in json.loads(POBLACION_292.read_text(encoding='utf-8'))['spawns'] if s.get('monstruo')]
    for s in spawns:
        s['tile'] = _pisable(*s['tile'])
    spawns = [s for s in spawns if s['tile']]
    zonas = []
    for z in ZONAS:
        normales = [(s['tile'][0], s['tile'][1], DE_ORIGINAL[s['npc_type']]) for s in spawns
                    if s['npc_type'] in DE_ORIGINAL and 23910 <= DE_ORIGINAL[s['npc_type']] < 23930
                    and z['dentro'](*s['tile'])]
        elites = [(s['tile'][0], s['tile'][1], DE_ORIGINAL[s['npc_type']]) for s in spawns
                  if s['npc_type'] in DE_ORIGINAL and 23930 <= DE_ORIGINAL[s['npc_type']] < 23940
                  and z['dentro'](*s['tile'])]
        grupos = []
        for k, g in enumerate(_grupos(normales, z['grupos'])):
            bichos = [[x, y, t] for x, y, t in g[:POR_GRUPO]]
            if elites and k % ELITE_CADA == 0:
                cx = sum(b[0] for b in bichos) / len(bichos)
                cy = sum(b[1] for b in bichos) / len(bichos)
                ex, ey, et = min(elites, key=lambda e: math.dist(e[:2], (cx, cy)))
                bichos.append([ex, ey, et])
            grupos.append(bichos)
        adds = []
        if z['adds']:
            adds = [list(s['tile']) for s in spawns if math.dist(s['tile'], z['casilla_jefe']) <= 10][:12] \
                or [z['casilla_jefe']]
        zonas.append({'nombre': z['nombre'], 'inicio': z['inicio'], 'jefe': z['jefe'], 'casilla_jefe': z['casilla_jefe'],
                      'adds': z['adds'], 'casillas_adds': adds, 'grupos': grupos})
    datos = {'_nota': 'Generado por tools/generar_raid.py; no editar a mano.', 'stage': STAGE, 'entrada': ENTRADA,
             'zonas': zonas, 'mecanicas': MECANICAS, 'stats': STATS, 'lockout_dia': LOCKOUT_DIA}
    PLANTILLA.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('plantilla: %s' % ', '.join('%s %d grupos / %d bichos' % (z['nombre'], len(z['grupos']),
                                                                     sum(len(g) for g in z['grupos'])) for z in zonas))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', help='solo los monstruos en esa content.db')
    a = ap.parse_args()
    if a.db:
        content_db(a.db)
        return
    content_db(RAIZ / 'corpus' / 'content.db')
    monster_xml()
    plantilla()


if __name__ == '__main__':
    main()
