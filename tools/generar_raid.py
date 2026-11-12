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
import random
import re
import sqlite3
import statistics

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
# 11/11/2026, "vida normales 5k, elites 10k jefes 1.000.000, 1.500.000 y 2.000.000": solo cambia la vida.
STATS = {
    'trash': dict(nivel=80, hp=5000, atk=745, var=5, df=1100, matk=640, mdef=340, acc=435, agi=265, exp=3400),
    'elite': dict(nivel=80, hp=10000, atk=820, var=5, df=1180, matk=700, mdef=370, acc=455, agi=275, exp=10000),
    'add': dict(nivel=80, hp=12000, atk=720, var=5, df=1050, matk=620, mdef=330, acc=430, agi=260, exp=900),
    'jefe1': dict(nivel=100, hp=1000000, atk=1400, var=5, df=2400, matk=870, mdef=890, acc=590, agi=360, exp=120000),
    'jefe2': dict(nivel=100, hp=1500000, atk=1450, var=5, df=2450, matk=890, mdef=900, acc=595, agi=362, exp=160000),
    'jefe3': dict(nivel=100, hp=2000000, atk=1500, var=5, df=2500, matk=910, mdef=920, acc=600, agi=365, exp=240000),
    # Los de los puzles (11/11/2026): los pilares de los totems (no pegan) y los guardianes de los sellos (minijefes).
    'pilar': dict(nivel=80, hp=15000, atk=1, var=5, df=1100, matk=1, mdef=340, acc=435, agi=265, exp=500),
    'guardian': dict(nivel=90, hp=60000, atk=880, var=5, df=1300, matk=760, mdef=420, acc=480, agi=290, exp=30000),
}
# TODOS los hechizos de los clones son de nivel 60: los originales son de nivel 300 (Oath Wrap V 2930, Explosive Shell
# V 4542, y las elites traian 10840 / 10843 que pegaban 607 y 813) o buffs V (Spike Armor, Armor Break, Deadly
# Sweep...). Fuego: Phoenix Fire I (212, 132 de dano), Fireball Hit IV (258) y III (241).
HECHIZOS_POR_PAPEL = {'trash': (212, 258), 'elite': (212, 241), 'add': (241, 258),
                      'jefe1': (212, 258), 'jefe2': (258, 241), 'jefe3': (212, 241),
                      'pilar': (0, 0), 'guardian': (258, 241)}
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

# LOS PUZLES (11/11/2026: "que tengas uno que otro puzzle"; server/raid_puzles.py). Uno antes de cada jefe, rotando los
# cuatro tipos para que cada raid tenga tres distintos:
#   placas    casillas marcadas (altares de luz) con un jugador encima de cada una a la vez;
#   totems    cuatro pilares de colores que hay que matar en el orden que dan las pistas (si se falla, reviven);
#   sellos    tres sellos (altares del infierno), cada uno con un guardian: los minijefes del mapa;
#   antorcha  llevar la llama del altar de salida al de llegada antes de que se apague, mientras salen bichos.
PUZLES = {'flamefang': ('placas', 'antorcha', 'sellos'), 'warring': ('sellos', 'totems', 'placas'),
          'wintry': ('antorcha', 'placas', 'totems'), 'dragon': ('totems', 'sellos', 'antorcha')}
PUZLE_BASE = {'flamefang': 23870, 'warring': 23877, 'wintry': 23884, 'dragon': 23891}   # +0..3 pilares, +4..6 guardianes
PILARES = ((855, 'Crimson Pillar'), (946, 'Golden Pillar'), (18699, 'Jade Pillar'), (20701, 'Azure Pillar'))
GUARDIANES = {'flamefang': (17656, 17658, 17657), 'warring': (23433, 23434, 23435),
              'wintry': (23350, 23351, 23352), 'dragon': (23517, 23518, 23519)}


def clones_puzle(clave):
    b = PUZLE_BASE[clave]
    return ([(b + k, o, 'pilar') for k, (o, _n) in enumerate(PILARES)]
            + [(b + 4 + k, o, 'guardian') for k, o in enumerate(GUARDIANES[clave])])


def nombres_puzle(clave):
    return {b: n for b, (_o, n) in zip(range(PUZLE_BASE[clave], PUZLE_BASE[clave] + 4), PILARES)}


CLONES += clones_puzle('flamefang')
NOMBRES = nombres_puzle('flamefang')          # los pilares llevan nombre propio (su color: las pistas lo usan)
DE_ORIGINAL = {o: n for n, o, p in CLONES if p not in ('pilar', 'guardian')}

# LA AMBIENTACION: lo que sale al entrar en cada zona y al acercarse a su jefe por primera vez.
AMBIENTE = {
    'flamefang': (("Heat rises from the cracked stone. The Ember Gate burns ahead.",
                   "The ground trembles: something huge stirs in the lava."),
                  ("Ash falls like snow over The Burning Hall.", "A roar shakes the hall. Razorex smells you."),
                  ("Satrixia's Throne glows red. Her servants watch from the flames.",
                   "Satrixia laughs: \"Come closer, little ones.\"")),
    'warring': (("Chains rattle at Cerberus' Gate. Three heads are waiting.",
                 "You hear three growls at once. Cerberus is near."),
                ("Banners of a forgotten war cover Ares' Battlefield.", "Steel clashes in the distance. Ares is ready."),
                ("Souls drift towards the Throne of Hades.", "A cold voice whispers your names.")),
    'wintry': (("A freezing wind blows through The Frozen Pass.", "The ice cracks under the steps of a giant."),
               ("Paw prints the size of a shield lead into Leon's Den.", "A deep growl echoes in the den."),
               ("Snowflakes dance around Seasonia's Throne.", "The air freezes: Seasonia turns towards you.")),
    'dragon': (("Cherry petals fall over the Blossom Garden.", "The petals swirl. Blossom Hail is near."),
               ("War drums beat in the General's Camp.", "General Rizaburo draws his blade."),
               ("Waves crash against Watatsumi's Shrine.", "The sea rises. Watatsumi has awakened.")),
}

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


def todos_los_clones(carpeta=None):
    """[(numero, original, papel, stats de su papel, hechizos)] de todas las raids: la Flamefang y las de NUEVAS (estas,
    de su plantilla, para poder rehacer los monstruos en el VPS sin content.db local: --db RUTA --plantillas DIR)."""
    salida = [(n, o, p, STATS[p], HECHIZOS_POR_PAPEL[p], NOMBRES.get(n)) for n, o, p in CLONES]
    carpeta = pathlib.Path(carpeta) if carpeta else RAIZ / 'server' / 'plantillas'
    for cfg in NUEVAS:
        d = json.loads((carpeta / cfg['plantilla']).read_text(encoding='utf-8'))
        nombres = {int(k): v for k, v in (d.get('nombres') or {}).items()}
        salida += [(n, o, p, d['stats'][p], HECHIZOS_POR_PAPEL[p], nombres.get(n)) for n, o, p in d['clones']]
    return salida


def content_db(ruta, carpeta=None):
    """Los clones en la tabla monster de esa content.db (quita los de antes)."""
    con = sqlite3.connect(ruta)
    clones = todos_los_clones(carpeta)
    for nuevo, original, papel, s, (h1, h2), nombre in clones:
        cols, f = _fila_db(con, original)
        if nombre:
            f['name'] = nombre
        f.update({'id': str(nuevo), 'level': str(s['nivel']), 'hp': str(s['hp']), 'atk_avg': str(s['atk']),
                  'atk_var': str(s['var']), 'def': str(s['df']), 'matk': str(s['matk']), 'mdef': str(s['mdef']),
                  'accuracy': str(s['acc']), 'agility': str(s['agi']), 'exp_value': str(s['exp']), 'crit_rate': '5',
                  'res_lightning': '20', 'res_fire': '40', 'res_ice': '20', 'res_corrosion': '20', 'res_body': '20',
                  'res_mind': '40', 'drop_id': '0'})
        for k, h in (('攻擊法術1', h1), ('攻擊法術2', h2), ('攻擊法術3', h1), ('攻擊法術4', h2)):
            if k in f:
                f[k] = str(h)
        f.update({'atk_speed': str(VELOCIDAD_ATAQUE), 'move_speed': str(0 if papel == 'pilar' else VELOCIDAD)})
        for k in ('腐蝕攻擊', '火焰攻擊', '雷電攻擊', '寒冰攻擊', '特殊怪傷害調整', '召喚怪物', '常駐法術1', '常駐法術2',
                  '補血法術1', '補血法術2', '施展機率'):
            if k in f:
                f[k] = None
        con.execute('delete from monster where id=?', (str(nuevo),))
        con.execute('insert into monster (%s) values (%s)' % (','.join('"%s"' % c for c in cols), ','.join('?' * len(cols))),
                    [f[c] for c in cols])
    con.commit()
    con.close()
    print('content.db: %d monstruos de las raids en %s' % (len(clones), ruta))


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
    for nuevo, original, papel, s, (h1, h2), nombre in todos_los_clones():
        f = _fila_xml(texto, original)
        if nombre:
            f = re.sub(r'(?<= )名稱="[^"]*"', lambda _m: '名稱="%s"' % nombre, f, count=1)
        cambios = {'編號': nuevo, '等級': s['nivel'], 'HP': s['hp'], '平均攻擊': s['atk'], '攻擊變數': s['var'],
                   '防禦': s['df'], '魔攻': s['matk'], '魔防': s['mdef'], '精準': s['acc'], '靈敏': s['agi'],
                   '經驗價值': s['exp'], '掉寶編號': 0}
        for k, v in cambios.items():
            f = re.sub(r'(?<= )%s="[^"]*"' % k, lambda _m, k=k, v=v: '%s="%s"' % (k, v), f, count=1)
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
        zona = {'nombre': z['nombre'], 'inicio': z['inicio'], 'jefe': z['jefe'], 'casilla_jefe': z['casilla_jefe'],
                'adds': z['adds'], 'casillas_adds': adds, 'grupos': grupos}
        tipos = sorted({b[2] for g in grupos for b in g if 23910 <= b[2] < 23930})
        zona.update(extras_zona(STAGE, 'flamefang', len(zonas), zona, tipos, random.Random(STAGE + len(zonas))))
        zonas.append(zona)
    datos = {'_nota': 'Generado por tools/generar_raid.py; no editar a mano.', 'clave': 'flamefang',
             'nombre': 'Flamefang Raid', 'nivel': 60, 'stage': STAGE, 'entrada': ENTRADA,
             'zonas': zonas, 'mecanicas': MECANICAS, 'stats': STATS, 'lockout_dia': LOCKOUT_DIA}
    PLANTILLA.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('plantilla: %s' % ', '.join('%s %d grupos / %d bichos' % (z['nombre'], len(z['grupos']),
                                                                     sum(len(g) for g in z['grupos'])) for z in zonas))


# ================================================================================ LAS RAIDS DE NIVEL 50, 40 Y 30
# 11/11/2026: "necesito crees 3 raid mas una lvl 50, una lvl 40 y una lvl 30 elige mapas de lvl altos y nerfea sus mob
# para los lvl que te digo, los premios los mismos porfa armas ride y pimp del lvl correspondiente". Mapas de nivel
# 400+ con tres jefes cada uno, copiados como instancia (tools/subir_mapa.py 914..916 --instancia). Se montan como la
# Flamefang, con sus stats escalados a su nivel N (stats_de) y las mismas mecanicas por orden (charcos y division, garra y aliento, nova, escudo y condena), con sus textos ('t').
# Las zonas salen solas: alrededor de cada jefe, los grupos en casillas a las que se llega andando desde el.
NUEVAS = [
    dict(clave='warring', nombre='Warring Realm Raid', stage=914, nivel=50, base=23950,
         poblacion='warring_realm.json', plantilla='raid_warring.json',
         jefes=[(23437, "Cerberus' Gate"), (23436, "Ares' Battlefield"), (23438, 'Throne of Hades')],
         adds=(23427, 23362),
         textos=[{'lava': 'hellfire', 'adds': 'Infernal Guards', 'parte': 'howls and calls its pack'},
                 {'garra': 'War Strike', 'aliento': 'raises his blade'},
                 {'nova': 'Soul Reaping', 'escudo': 'a shield of souls', 'adds': 'Undead Knights',
                  'condena': 'DEATH', 'grito': 'Your souls are mine!', 'su': 'his'}]),
    dict(clave='wintry', nombre='Wintry Realm Raid', stage=915, nivel=40, base=23966,
         poblacion='wintry_realm.json', plantilla='raid_wintry.json',
         jefes=[(23354, 'The Frozen Pass'), (23353, "Leon's Den"), (23355, "Seasonia's Throne")],
         adds=(23346, 23345),
         textos=[{'lava': 'frost', 'adds': 'Yetis', 'parte': 'shatters into Yetis'},
                 {'garra': 'Frost Claw', 'aliento': 'inhales freezing air'},
                 {'nova': 'Blizzard', 'escudo': 'a shield of ice', 'adds': 'Snow Girls',
                  'condena': 'FROSTBITE', 'grito': 'Freeze, all of you!', 'su': 'her'}]),
    dict(clave='dragon', nombre="Dragon's Lair Raid", stage=916, nivel=30, base=23982,
         poblacion='dragons_lair.json', plantilla='raid_dragon.json',
         jefes=[(23520, 'Blossom Garden'), (23521, "General's Camp"), (23522, "Watatsumi's Shrine")],
         adds=(23512, 23513),
         textos=[{'lava': 'cherry blossoms', 'adds': 'Pastel Snips', 'parte': 'scatters into Pastel Snips'},
                 {'garra': 'Iaido Cut', 'aliento': 'draws his sword'},
                 {'nova': 'Tidal Wave', 'escudo': 'a shield of water', 'adds': 'Kitsumengami',
                  'condena': 'the TIDE MARK', 'grito': 'The sea will take you!', 'su': 'his'}]),
]
MAX_TRASH, MAX_ELITES = 8, 3          # ids por raid: base+0..7 normales, +8..10 elites, +11..13 jefes, +14..15 adds


def _r(x, paso=1):
    return max(paso, int(round(x / paso) * paso))


def stats_de(nivel):
    """Los STATS de una raid de nivel `nivel`: los de la Flamefang (nivel 60, ajustados a mano el 11/11/2026) con el
    ataque, la defensa, la precision y la agilidad en proporcion al nivel, y la vida y la experiencia al cuadrado (la
    vida de los jugadores tambien crece con el nivel). Las medianas de content.db por nivel no sirven: van a saltos
    (los de nivel 60 tienen mas vida que los de 80). Los niveles que se ven, como en la Flamefang: +20 y +40."""
    f = nivel / 60.0
    st = {}
    for papel, s in STATS.items():
        st[papel] = dict(nivel=s['nivel'] - 60 + nivel, var=s['var'],
                         hp=_r(s['hp'] * f * f, 10000 if papel.startswith('jefe') else 100),
                         atk=_r(s['atk'] * f), df=_r(s['df'] * f), matk=_r(s['matk'] * f), mdef=_r(s['mdef'] * f),
                         acc=_r(s['acc'] * f), agi=_r(s['agi'] * f), exp=_r(s['exp'] * f * f, 10))
    return st


def _spawns(cfg):
    ruta = RAIZ / 'server' / 'plantillas' / cfg['poblacion']
    return [s for s in json.loads(ruta.read_text(encoding='utf-8'))['spawns'] if s.get('monstruo')]


def clones_de(cfg):
    """[(numero propio, original, papel)] de la raid: los tipos normales y elites del mapa, sus tres jefes y dos adds."""
    import collections
    con = sqlite3.connect(RAIZ / 'corpus' / 'content.db')
    try:
        info = {int(r[0]): (r[1] or '', int(r[2] or 0)) for r in con.execute('select id, name, hp from monster')}
    finally:
        con.close()
    cuenta = collections.Counter(int(s['npc_type']) for s in _spawns(cfg))
    jefes = [j for j, _n in cfg['jefes']]
    tipos = [t for t, n in cuenta.items() if t in info and t not in jefes and n >= 3 and info[t][1] > 1000]
    hp_normal = statistics.median(info[t][1] for t in tipos if not info[t][0].startswith('E-'))
    normales = sorted((t for t in tipos if not info[t][0].startswith('E-') and info[t][1] <= 2 * hp_normal
                       and cuenta[t] >= 10), key=lambda t: (-cuenta[t], t))[:MAX_TRASH]
    elites = sorted((t for t in tipos if info[t][0].startswith('E-')), key=lambda t: (-cuenta[t], t))[:MAX_ELITES]
    b = cfg['base']
    salida = [(b + k, t, 'trash') for k, t in enumerate(normales)]
    salida += [(b + 8 + k, t, 'elite') for k, t in enumerate(elites)]
    salida += [(b + 11 + k, t, 'jefe%d' % (k + 1)) for k, t in enumerate(jefes)]
    salida += [(b + 14 + k, t, 'add') for k, t in enumerate(cfg['adds'])]
    return salida


def _transitable():
    import sys
    if str(RAIZ / 'server') not in sys.path:
        sys.path.insert(0, str(RAIZ / 'server'))
    import transitable
    return transitable


def _alcanzables(stage, desde, hasta=48):
    """{casilla: pasos} de las casillas a las que se llega andando desde `desde` (como mucho `hasta` pasos)."""
    from collections import deque
    tr = _transitable()
    dist = {tuple(desde): 0}
    cola = deque([tuple(desde)])
    while cola:
        x, y = cola.popleft()
        if dist[(x, y)] >= hasta:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            p = (x + dx, y + dy)
            if p not in dist and tr.se_pisa(stage, *p):
                dist[p] = dist[(x, y)] + 1
                cola.append(p)
    return dist


def _pisable_en(stage, x, y, radio=6):
    tr = _transitable()
    cerca = [(math.dist((x, y), (x + dx, y + dy)), x + dx, y + dy)
             for dx in range(-radio, radio + 1) for dy in range(-radio, radio + 1)
             if tr.se_pisa(stage, x + dx, y + dy)]
    return list(min(cerca)[1:]) if cerca else None


RECORRIDO = 62          # pasos de la llegada al jefe, como mucho
GRUPOS_ZONA = 8
PATRULLAS, POR_PATRULLA = 2, 3


def _camino(dist, desde):
    """Las casillas de `desde` al jefe (dist: pasos hasta el), bajando siempre."""
    p, salida = tuple(desde), [tuple(desde)]
    while dist.get(p, 0) > 0:
        p = min(((p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)
                 and (p[0] + dx, p[1] + dy) in dist), key=lambda q: (dist[q], q))
        salida.append(p)
    return salida


def _repartidas(casillas, cuantas, separacion, rng):
    libres = sorted(casillas)
    rng.shuffle(libres)
    elegidas = []
    for q in libres:
        if all(math.dist(q, e) >= separacion for e in elegidas):
            elegidas.append(q)
        if len(elegidas) == cuantas:
            break
    return [list(q) for q in elegidas]


def extras_zona(stage, clave, k, zona, tipos, rng, dist=None):
    """Lo que se anadio el 11/11/2026 a cada zona: patrullas que van y vuelven por el camino, el puzle de antes del
    jefe (con sus casillas) y los textos de ambientacion."""
    dist = dist or _alcanzables(stage, zona['casilla_jefe'], hasta=130)
    inicio = tuple(zona['inicio']) if tuple(zona['inicio']) in dist else min(
        dist, key=lambda q: math.dist(q, zona['inicio']))
    camino = _camino(dist, inicio)
    n = len(camino)
    patrullas = []
    for j in range(PATRULLAS):
        tramo = camino[int(n * (0.15 + 0.35 * j)): int(n * (0.45 + 0.35 * j))] or camino
        ruta = [list(tramo[0]), list(tramo[len(tramo) // 2]), list(tramo[-1]), list(tramo[len(tramo) // 2])]
        sitio = [q for q in dist if math.dist(q, tramo[0]) <= 2]
        rng.shuffle(sitio)
        patrullas.append({'bichos': [[x, y, tipos[(i + j) % len(tipos)]] for i, (x, y) in enumerate(sitio[:POR_PATRULLA])],
                          'ruta': ruta})
    tipo = PUZLES[clave][k]
    b = PUZLE_BASE[clave]
    entre = lambda lo, hi: [q for q, d in dist.items() if lo <= d <= hi]      # noqa: E731
    if tipo == 'placas':
        puzle = {'tipo': tipo, 'casillas': _repartidas(entre(6, 10), 4, 5, rng), 'segundos': 3}
    elif tipo == 'totems':
        puzle = {'tipo': tipo, 'casillas': _repartidas(entre(5, 9), 4, 4, rng), 'pilares': [b + i for i in range(4)]}
    elif tipo == 'sellos':
        puzle = {'tipo': tipo, 'casillas': _repartidas(entre(10, 24), 3, 8, rng),
                 'guardianes': [b + 4 + i for i in range(3)]}
    else:
        origen = camino[max(0, n - 32)] if n > 32 else camino[0]
        puzle = {'tipo': tipo, 'origen': list(origen), 'destino': _repartidas(entre(6, 8), 1, 1, rng)[0],
                 'entregas': 2, 'segundos': 45, 'acosadores': tipos[:2]}
    intro, cerca = AMBIENTE[clave][k]
    return {'patrullas': patrullas, 'puzle': puzle, 'ambiente': {'entrar': intro, 'cerca': cerca}}


def plantilla_auto(cfg):
    rng = random.Random(cfg['stage'])
    clones = clones_de(cfg) + clones_puzle(cfg['clave'])
    stage = cfg['stage']
    normales = [n for n, _o, p in clones if p == 'trash']
    elites = [n for n, _o, p in clones if p == 'elite']
    jefes = {o: n for n, o, p in clones if p.startswith('jefe')}
    adds = [n for n, _o, p in clones if p == 'add']
    posicion = {int(s['npc_type']): s['tile'] for s in _spawns(cfg)}
    zonas = []
    for k, (original, nombre) in enumerate(cfg['jefes']):
        casilla = _pisable_en(stage, *posicion[original])
        if casilla is None:
            raise SystemExit('%s: el jefe %d no tiene casilla pisable cerca' % (cfg['clave'], original))
        dist = _alcanzables(stage, casilla, hasta=RECORRIDO + 5)
        lejos = max(dist.values())
        if lejos < 20:
            raise SystemExit('%s: alrededor de %s solo se anda %d casillas' % (cfg['clave'], nombre, lejos))
        # "Recorrido mas largo" (11/11/2026): la llegada, la casilla mas lejana del jefe (hasta RECORRIDO pasos); los
        # grupos, repartidos a lo largo del camino de ella al jefe, un poco a los lados.
        inicio = max((d, p) for p, d in dist.items() if d <= RECORRIDO)[1]
        camino = _camino(dist, inicio)
        centros = []
        for g in range(GRUPOS_ZONA):
            base = camino[int(6 + (len(camino) - 16) * g / max(1, GRUPOS_ZONA - 1))]
            cerca = [q for q in dist if math.dist(q, base) <= 3 and dist[q] >= 9]
            centros.append(rng.choice(sorted(cerca)) if cerca else base)
        tipos = normales[k::3] or normales
        grupos = []
        for g, (cx, cy) in enumerate(centros):
            libres = sorted(p for p in dist if math.dist(p, (cx, cy)) <= 2.5)
            rng.shuffle(libres)
            bichos = [[x, y, tipos[(g + i) % len(tipos)]] for i, (x, y) in enumerate(libres[:POR_GRUPO])]
            if elites and g % ELITE_CADA == 0 and len(libres) > POR_GRUPO:
                x, y = libres[POR_GRUPO]
                bichos.append([x, y, elites[(k + g // ELITE_CADA) % len(elites)]])
            grupos.append(bichos)
        casillas_adds = sorted((p for p, d in dist.items() if 3 <= d <= 6), key=lambda p: (dist[p], p))[::3][:12]
        zona = {'nombre': nombre, 'inicio': list(inicio), 'jefe': jefes[original], 'casilla_jefe': casilla,
                'adds': adds[0] if k == 0 else (adds[1] if k == 2 else None),
                'casillas_adds': [list(p) for p in casillas_adds] or [casilla], 'grupos': grupos}
        zona.update(extras_zona(stage, cfg['clave'], k, zona, tipos, rng, dist))
        zonas.append(zona)
    mecanicas = {}
    for k, z in enumerate(zonas):
        m = json.loads(json.dumps(MECANICAS[str(23940 + k)]))
        m['t'] = cfg['textos'][k]
        mecanicas[str(z['jefe'])] = m
    datos = {'_nota': 'Generado por tools/generar_raid.py; no editar a mano.', 'clave': cfg['clave'],
             'nombre': cfg['nombre'], 'nivel': cfg['nivel'], 'stage': stage, 'entrada': zonas[0]['inicio'],
             'zonas': zonas, 'mecanicas': mecanicas, 'stats': stats_de(cfg['nivel']), 'lockout_dia': LOCKOUT_DIA,
             'clones': [list(c) for c in clones], 'nombres': {str(k): v for k, v in nombres_puzle(cfg['clave']).items()}}
    ruta = RAIZ / 'server' / 'plantillas' / cfg['plantilla']
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('plantilla %s: %s' % (cfg['plantilla'], ', '.join(
        '%s %d grupos / %d bichos' % (z['nombre'], len(z['grupos']), sum(len(g) for g in z['grupos'])) for z in zonas)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', help='solo los monstruos en esa content.db')
    ap.add_argument('--plantillas', help='con --db: la carpeta de las plantillas raid_*.json (por defecto la del repo)')
    a = ap.parse_args()
    if a.db:
        content_db(a.db, a.plantillas)
        return
    for cfg in NUEVAS:
        plantilla_auto(cfg)
    content_db(RAIZ / 'corpus' / 'content.db')
    monster_xml()
    plantilla()


if __name__ == '__main__':
    main()
