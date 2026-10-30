"""Deja consistente server/plantillas/dark_cavern.json despues de editar el mapa 900 en el editor de mapas.

El editor exporta los monstruos que pones, pero no sabe de los puzzles ni de que el cliente solo dibuja los sprites que
trae. Esta herramienta (idempotente) hace tres cosas:

  1. Los 3 Guardianes del Sello (puzzles.sellos) existen: si los borraste, vuelven a su sitio (o a la casilla libre mas
     cercana). Sin ellos las puertas no se abren nunca.
  2. Cada monstruo se dibuja: los tipos cuyo sprite NO esta en el cliente (el monstruo existe pero no se ve) pasan a un
     sprite parecido que si esta. Se guarda el original en `sprite_original`; su npc_type, nombre y nivel no cambian.
  3. Los monstruos sin hp_mult llevan el de la instancia (VIDA = 0,7: un 30% menos de vida). El jefe (Dragonkin Moowad,
     npc_type 209) recupera su vida y ataque aunque lo hayas vuelto a poner desde el editor.

    python tools/reparar_instancia_oscura.py          # repara y dice que cambio
    python tools/reparar_instancia_oscura.py --ver    # solo informa
"""
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.stdout.reconfigure(encoding='utf-8')

PLANTILLA = RAIZ / 'server' / 'plantillas' / 'dark_cavern.json'
VIDA = 0.7
SELLO = (208, 'Seal Guardian', 42093, 60)
JEFE_TIPO, JEFE_HP, JEFE_ATK = 209, 40.0 * VIDA, 1.3     # Dragonkin Moowad: el jefe suelta las piedras de Holy (combate._DROPS_PONDERADOS_JEFES)
# sprite que falta -> sprite parecido que si esta en el cliente (los npc_type no cambian)
SUSTITUTOS = {
    42495: 42063,   # Howling Wolf -> lobo
    42322: 42093,   # Cursed General / Evil Warden -> Fane Protector
    42421: 42283,   # Puqi Local -> Terra Miner
    42425: 42076,   # Puqi Pirate -> Piratekin
    42144: 42030,   # Death Leech -> Leech
    42208: 42088,   # Fane Priest -> Savage Priest
}


def sprites_del_cliente():
    import cliente_local
    ruta = pathlib.Path(cliente_local.ruta_cliente())
    por = {}
    for nombre in cliente_local.indice_paks(ruta):
        m = re.fullmatch(r'SHAPE[\\/]MON[\\/][^\\/]+[\\/](\d+)_(WAIT|RUN|ATT|HURT|DEAD)\.SPR', nombre.upper())
        if m:
            por.setdefault(int(m.group(1)), set()).add(m.group(2))
    return {s for s, v in por.items() if {'WAIT', 'RUN', 'ATT', 'HURT', 'DEAD'} <= v}


def libre(stage, tile):
    import transitable
    return transitable.se_pisa(stage, *tile)


def main():
    solo_ver = '--ver' in sys.argv
    d = json.loads(PLANTILLA.read_text(encoding='utf-8'))
    stage = d['stage']
    sp = d['spawns']
    cambios = []
    visibles = sprites_del_cliente()

    # 2. sprites que si se ven
    for e in sp:
        s = int(e.get('sprite') or 0)
        if s and s not in visibles:
            if s in SUSTITUTOS and SUSTITUTOS[s] in visibles:
                e.setdefault('sprite_original', s)
                e['sprite'] = SUSTITUTOS[s]
                cambios.append('sprite %d -> %d (%s)' % (s, e['sprite'], e['nombre']))
            else:
                cambios.append('SIN SPRITE y sin sustituto: %s (%d)' % (e['nombre'], s))

    # 3. vida
    for e in sp:
        if e['npc_type'] == JEFE_TIPO and (e.get('hp_mult') != JEFE_HP or not e.get('jefe')):
            e.update(hp_mult=JEFE_HP, atk_mult=JEFE_ATK, jefe=True)
            cambios.append('jefe: vida x%.1f, ataque x%.1f' % (JEFE_HP, JEFE_ATK))
    for e in sp:
        if 'hp_mult' not in e:
            e['hp_mult'] = VIDA
            cambios.append('vida x%.1f (%s)' % (VIDA, e['nombre']))

    # 1. sellos
    pz = d.get('puzzles') or {}
    ids_sello = set(pz.get('sellos') or [])
    existentes = {e['sello'] for e in sp if e.get('sello')}
    por_defecto = {1: (47, 76), 2: (66, 43), 3: (141, 91)}
    zona = {tuple(t) for p in pz.get('puertas', []) for t in p['zona']}
    usados = [tuple(e['tile']) for e in sp]
    mayor = max([e['entity_id'] for e in sp] + [7550000])
    for n in (1, 2, 3):
        if n in existentes:
            continue
        x0, y0 = por_defecto[n]
        cand = sorted(((x0 + dx, y0 + dy) for dx in range(-6, 7) for dy in range(-6, 7)),
                      key=lambda t: max(abs(t[0] - x0), abs(t[1] - y0)))
        t = next(t for t in cand if all(libre(stage, (t[0] + a, t[1] + b)) for a in (-1, 0, 1) for b in (-1, 0, 1))
                 and all(max(abs(t[0] - z[0]), abs(t[1] - z[1])) > 2 for z in zona)
                 and all(max(abs(t[0] - u[0]), abs(t[1] - u[1])) >= 3 for u in usados))
        mayor += 1
        sp.append({'entity_id': mayor, 'nombre': 'Seal Guardian ' + 'I' * n, 'npc_type': SELLO[0], 'sprite': SELLO[2],
                   'klass': 1, 'monstruo': True, 'tile': list(t), 'direccion': 4, 'visible': 0, 'nivel': SELLO[3],
                   'hp_mult': 2.0 * VIDA, 'atk_mult': 1.15, 'elite': True, 'sello': n})
        usados.append(t)
        cambios.append('vuelve el Guardian del Sello %d en %s' % (n, t))
    pz['sellos'] = [e['entity_id'] for e in sorted((e for e in sp if e.get('sello')), key=lambda e: e['sello'])]
    d['puzzles'] = pz

    print('\n'.join(cambios) if cambios else 'nada que reparar')
    if cambios and not solo_ver:
        PLANTILLA.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print('escrito', PLANTILLA)


if __name__ == '__main__':
    main()
