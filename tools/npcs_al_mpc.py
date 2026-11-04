"""Pone los NPC de las plantillas en la casilla donde los dibuja el .mpc del cliente.

POR QUE. El .mpc trae cada NPC como objeto (id = su sprite, 40033 Herbalist Hebu) y el cliente pinta un punto azul
en el minimapa en esa casilla. Si nuestra plantilla lo pone una casilla al lado, salen DOS puntos azules: el del mapa
y el del NPC que mandamos ("Error visuales de los puntos azules de los NPC's", 03/11/2026: Breeze City, Dense Forest,
Cryptic Moon Swamp, Mushroom Forest, Mysterious Garden). Merchant Wushor, en la misma casilla en los dos, sale con uno.

Solo se mueve un NPC si en su mapa hay UN objeto con su sprite a MAXIMO `--radio` casillas (por defecto 3): mas lejos
es otro NPC con el mismo dibujo, y con dos candidatos no se adivina.

Uso:
    python tools/npcs_al_mpc.py                 # lista lo que cambiaria
    python tools/npcs_al_mpc.py --poner         # lo escribe en las plantillas
    python tools/npcs_al_mpc.py --stage 23 29   # solo esos mapas
"""
import argparse
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PLANTILLAS = RAIZ / 'server' / 'plantillas'
sys.path.insert(0, str(RAIZ / 'tools'))
import mapa_del_cliente as mc


def cambios(stages=None, radio=3):
    out = []
    for f in sorted(PLANTILLAS.glob('*.json')):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(d, dict) or not isinstance(d.get('spawns'), list) or not d.get('stage'):
            continue
        st = int(d['stage'])
        if stages and st not in stages:
            continue
        m = mc.mapa(st)
        if m is None:
            continue
        por_sprite = {}
        for o in m.objetos:
            if 40000 <= o['id'] < 50000:
                por_sprite.setdefault(o['id'], []).append(tuple(o['tile']))
        for i, s in enumerate(d['spawns']):
            if s.get('monstruo') or not s.get('tile') or 'hex' in s:
                continue
            spr = int(s.get('sprite') or 0)
            tile = tuple(s['tile'])
            cerca = [t for t in por_sprite.get(spr, ())
                     if max(abs(t[0] - tile[0]), abs(t[1] - tile[1])) <= radio]
            if len(cerca) == 1 and cerca[0] != tile:
                out.append((f, i, st, s.get('nombre'), tile, cerca[0]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--poner', action='store_true')
    ap.add_argument('--stage', type=int, nargs='*')
    ap.add_argument('--radio', type=int, default=3)
    a = ap.parse_args()
    lista = cambios(set(a.stage or ()), a.radio)
    for f, i, st, nombre, viejo, nuevo in lista:
        print('%-28s %4d  %-24s %s -> %s' % (f.name, st, nombre, viejo, nuevo))
    print(len(lista), 'NPC fuera de su casilla del .mpc')
    if a.poner:
        por_archivo = {}
        for f, i, st, nombre, viejo, nuevo in lista:
            por_archivo.setdefault(f, []).append((i, nuevo))
        for f, cambios_f in por_archivo.items():
            texto = f.read_text(encoding='utf-8')
            d = json.loads(texto)
            for i, nuevo in cambios_f:
                d['spawns'][i]['tile'] = list(nuevo)
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1 if '\n "' in texto[:200] else 2) + '\n',
                         encoding='utf-8')
        print('escritas', len(por_archivo), 'plantillas')


if __name__ == '__main__':
    main()
