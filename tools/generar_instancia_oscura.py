"""Genera server/plantillas/training_cave_big.json: la instancia oscura de Lv55-60 (stage 46, Training Cave (big)).

Mezcla bichos normales (Lv55-60) con elites (Lv60, mas vida y ataque) en grupos repartidos por el mapa, y al fondo
un jefe (Cursed Larry, npc_type 5258) con cuatro elites de guardia. El jefe suelta piedras de Holy Battlefield
(combate._DROPS_PONDERADOS_JEFES). Es determinista: la misma semilla da siempre el mismo mapa.

    python tools/generar_instancia_oscura.py
"""
import collections
import json
import pathlib
import random
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.stdout.reconfigure(encoding='utf-8')

import transitable

STAGE = 46            # Training Cave (big): cueva oscura (brillo 160), sin faccion ni teletransporte forzoso.
                      # Shadow Area (55) NO sirve: su stage.xml lleva 強制傳送 y el cliente se cerraba al entrar.
ENTIDAD_BASE = 7550000
SEMILLA = 55060

# (npc_type, nombre, sprite, nivel)
NORMALES = [(5254, 'Cursed Barft', 42204, 55), (912, 'Rotten Seeker', 42346, 55), (814, 'Soul-eating Worm', 42300, 55),
            (902, 'Fossa Rat', 42338, 58), (894, 'Imp Elf', 42331, 58), (903, 'Tail Rotten Rat', 42339, 60)]
ELITES = [(5255, 'Cursed General', 42322, 60), (5256, 'Cursed Fasit', 42327, 60), (5257, 'Cursed Priest', 42438, 60),
          (4629, 'Evil Warden', 42322, 60)]
JEFE = (5258, 'Cursed Larry', 42207, 63)
ELITE_HP, ELITE_ATK = 3.0, 1.25
JEFE_HP, JEFE_ATK = 45.0, 1.5
GRUPOS = 12
POR_GRUPO = 5


def alcanzables(origen):
    vistos = {origen: 0}
    cola = collections.deque([origen])
    while cola:
        x, y = cola.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if n not in vistos and transitable.se_pisa(STAGE, *n):
                    vistos[n] = vistos[(x, y)] + 1
                    cola.append(n)
    return vistos


def main():
    azar = random.Random(SEMILLA)
    # Este mapa no trae tags de llegada: la entrada es el extremo de la zona caminable mas grande (arriba a la derecha)
    # y el jefe queda en lo mas lejano que se camina desde ella.
    todos = [(x, y) for x in range(200) for y in range(125) if transitable.se_pisa(STAGE, x, y)]
    zona = alcanzables(todos[0])
    abiertas = [t for t in zona if all((t[0] + dx, t[1] + dy) in zona for dx in range(-3, 4) for dy in range(-3, 4))]
    llegada = max(abiertas, key=lambda t: t[0] - t[1])      # con espacio libre alrededor, no en el borde del mapa
    dist = alcanzables(llegada)
    libres = list(dist)
    cheb = lambda a, b: max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    # el jefe, en lo mas lejano que se camina
    jefe_tile = max(libres, key=lambda t: dist[t])
    centros = []
    candidatos = [t for t in libres if cheb(t, llegada) >= 28 and cheb(t, jefe_tile) >= 18]
    azar.shuffle(candidatos)
    for t in candidatos:
        if all(cheb(t, c) >= 22 for c in centros):
            centros.append(t)
        if len(centros) == GRUPOS:
            break
    usados = []
    spawns = []
    eid = [ENTIDAD_BASE]

    def libre_cerca(centro, radio, minimo=3):
        for _ in range(200):
            t = (centro[0] + azar.randint(-radio, radio), centro[1] + azar.randint(-radio, radio))
            if t in dist and all(cheb(t, u) >= minimo for u in usados) and cheb(t, llegada) >= 14:
                return t
        return None

    def poner(tipo, centro, radio, elite=False, jefe=False):
        t = libre_cerca(centro, radio, 4 if (elite or jefe) else 3)
        if t is None:
            return
        eid[0] += 1
        npc, nombre, sprite, nivel = tipo
        e = {'entity_id': eid[0], 'nombre': nombre, 'npc_type': npc, 'sprite': sprite, 'klass': 1, 'monstruo': True,
             'tile': list(t), 'direccion': azar.randint(0, 7), 'visible': 0, 'nivel': nivel}
        if jefe:
            e.update(hp_mult=JEFE_HP, atk_mult=JEFE_ATK, jefe=True)
        elif elite:
            e.update(hp_mult=ELITE_HP, atk_mult=ELITE_ATK, elite=True)
        spawns.append(e)
        usados.append(t)

    for c in centros:
        for _ in range(POR_GRUPO):
            poner(azar.choice(NORMALES), c, 6)
        poner(azar.choice(ELITES), c, 6, elite=True)
    usados.append(jefe_tile)
    eid[0] += 1
    npc, nombre, sprite, nivel = JEFE
    spawns.append({'entity_id': eid[0], 'nombre': nombre, 'npc_type': npc, 'sprite': sprite, 'klass': 1, 'monstruo': True,
                   'tile': list(jefe_tile), 'direccion': 3, 'visible': 0, 'nivel': nivel,
                   'hp_mult': JEFE_HP, 'atk_mult': JEFE_ATK, 'jefe': True})
    for _ in range(4):
        poner(random.Random(azar.random()).choice(ELITES), jefe_tile, 7, elite=True)
    datos = {'_nota': 'Training Cave (big), stage 46, como instancia oscura Lv55-60: bichos normales y elites en %d grupos y, al fondo, '
                      'el jefe Cursed Larry (suelta piedras de Holy Battlefield). Generado con tools/generar_instancia_oscura.py.' % len(centros),
             'stage': STAGE, 'spawns': spawns, 'recursos': []}
    destino = RAIZ / 'server' / 'plantillas' / 'training_cave_big.json'
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    n = collections.Counter('jefe' if s.get('jefe') else 'elite' if s.get('elite') else 'normal' for s in spawns)
    print('escrito', destino, dict(n), 'jefe en', jefe_tile, 'llegada', llegada, 'zona', len(dist))
    # el portal de vuelta, a 3-4 casillas de la llegada
    vuelta = next(t for t in sorted(abiertas, key=lambda t: dist[t]) if 3 <= cheb(t, llegada) <= 4)
    print('portal de vuelta en', vuelta)


if __name__ == '__main__':
    main()
