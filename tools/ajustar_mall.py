"""Precios y packs del Item Mall como en las capturas del usuario (03/11/2026).

  Special > General (13)   "solo esto en general, ajusta los precios a como estan aca": las pociones de aspecto
                           (estaban en Function > General), Angel Amulet Scroll, Skill Crystal, las cartas de 30
                           minutos y Recovery Notice (tambien estaba en Function > General). Nada mas.
  Special > Teleport (27)  Witch Summon Book y Witch Fly Book a 50 y 500 el pack de 10; lo demas de la pestana queda.
  Pet (19)                 "en pet solo esto sin los high lvl y common exp": certificados, Low-level Exp Stone, Pet
                           Feed, Master's Love y Pet's Double EXP Card.
  Function > General (11)  "en common solo esto": Broadcasting, Super Broadcasting, Spacious Iron Room y Bank, Safe
                           Key (Permanence), boda, divorcio y las nueve Stall Card.
  Furniture (32-35)        "en furniture quita todo".

Cada objeto: [(cuantos, precio)]. Las pestanas marcadas SOLO se quedan con esto y nada mas; en las otras solo se
cambian estos objetos. Los objetos que se mueven a una pestana SOLO se quitan de las demas. Las filas nuevas toman
ids libres por debajo de 32768 (el cliente no pinta las de mas).

    python tools/ajustar_mall.py
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MALL = RAIZ / 'server' / 'plantillas' / 'item_mall.json'
sys.stdout.reconfigure(encoding='utf-8')

PESTANAS = {
    13: (True, (            # Special > General
        (7032, ((1, 500),)), (7033, ((1, 500),)), (7034, ((1, 500),)),      # Gender Bolus, Height Potion, Magic Comb
        (7035, ((1, 500),)), (7036, ((1, 500),)),                           # Hair Color Potion, Complexion Potion
        (3692, ((1, 1000),)),                                               # Angel Amulet Scroll
        (2025, ((1, 200), (6, 1200))),                                      # Skill Crystal
        (2017, ((1, 35), (10, 350))),                                       # Double Exp Card (30 Minutes)
        (2018, ((1, 35), (10, 350))),                                       # Double Skill Exp Card (30 M.)
        (498, ((1, 35), (10, 350))),                                        # Collecting Speedup Card (30 M.)
        (499, ((1, 35), (10, 350))),                                        # Facture Speedup Card (30 M.)
        (4297, ((1, 300), (10, 3000))),                                     # Recovery Notice
    )),
    27: (False, (           # Special > Teleport
        (1333, ((1, 50), (10, 500))),                                       # Witch Summon Book
        (2987, ((1, 50), (10, 500))),                                       # Witch Fly Book
    )),
    19: (True, (            # Pet
        (3378, ((1, 1400), (5, 7000))),                                     # AdvancedBlood Certificate
        (3377, ((1, 700), (5, 3500))),                                      # MediumBlood Certificate
        (3383, ((1, 175), (10, 1750))),                                     # Low-levelExp Stone
        (3376, ((1, 35), (10, 350))),                                       # Pet Feed
        (3382, ((1, 100), (10, 1000))),                                     # Master's Love
        (3460, ((1, 50), (10, 500))),                                       # Pet's Double EXP Card (30 M.)
    )),
    11: (True, (            # Function > General
        (2002, ((1, 20), (10, 200))), (2003, ((1, 100), (10, 1000))),       # Broadcasting, Super Broadcasting
        (6853, ((1, 35), (10, 350))), (6854, ((1, 50), (10, 500))),         # Spacious Iron Room, Spacious Bank
        (2734, ((1, 2500),)), (4023, ((1, 875),)), (4024, ((1, 1575),)),    # Safe Key (Permanence), boda, divorcio
        (2701, ((1, 35),)), (2702, ((1, 350),)), (2703, ((1, 1050),)),      # Stall Common Card 1-3
        (2704, ((1, 50),)), (2705, ((1, 500),)), (2706, ((1, 780),)),       # Stall Silver Card 1-3
        (2707, ((1, 70),)), (2708, ((1, 350),)), (2709, ((1, 1050),)),      # Stall Gold Card 1-3
    )),
}
FUERA = (32, 33, 34, 35)    # Furniture: vacia
# "Saca todos los lvl 60 del mall" (03/11/2026): los robots de nivel 60 y 70 de Fashion > Robots (con el tope en 60
# los de 70 tampoco se pueden usar). La Lv60 Mount Lucky Bag la quita tools/generar_lucky_bags.py.
QUITAR = {9301, 9302, 9303, 9304}   # Weighty cat Boots, Black Dog Rot, Repair Duck Robot, Pink crocodile Robot
ID_MAX = 32767


def main():
    mall = json.loads(MALL.read_text(encoding='utf-8'))
    filas = mall['rows']
    base = dict(next(r for r in filas if r['category'] == 13))
    for k in ('price_source', 'publication'):
        base.pop(k, None)
    movidos = {iid for pestana, (solo, objetos) in PESTANAS.items() if solo for iid, _ in objetos}
    tocados = {(pestana, iid) for pestana, (_, objetos) in PESTANAS.items() for iid, _ in objetos}
    antes = len(filas)
    # El mismo objeto y la misma cantidad conservan su id de fila (las compras y los tests lo usan: 30590 es la
    # Double Exp Card de 1).
    id_viejo = {}
    for r in filas:
        id_viejo.setdefault((r['item'], r['quantity']), int(r['id']))
    filas = [r for r in filas
             if r['category'] not in FUERA and r['item'] not in QUITAR
             and not (r['category'] in PESTANAS and PESTANAS[r['category']][0])      # pestana SOLO: se rehace entera
             and (r['category'], r['item']) not in tocados
             and not (r['item'] in movidos and r['category'] in (11, 13, 19, 27))]
    usados = {int(r['id']) for r in filas}
    reservados = set(id_viejo.values())
    libres = (i for i in range(ID_MAX, 0, -1) if i not in usados and i not in reservados)
    nuevas = []
    for pestana, (_, objetos) in PESTANAS.items():
        orden = max([r['sort'] for r in filas if r['category'] == pestana] or [0])
        for iid, packs in objetos:
            for cuantos, precio in packs:
                orden += 1
                viejo = id_viejo.get((iid, cuantos))
                if viejo is None or viejo in usados:
                    viejo = next(libres)
                usados.add(viejo)
                nuevas.append(dict(base, id=viejo, item=iid, category=pestana, sort=orden, quantity=cuantos,
                                   price=precio, special_price=0, flags=base.get('flags', 1),
                                   price_source='captura del usuario (tools/ajustar_mall.py)',
                                   publication='pedido del usuario 03/11/2026'))
    mall['rows'] = filas + nuevas
    MALL.write_bytes((json.dumps(mall, ensure_ascii=False, indent=4) + '\n').replace('\n', '\r\n').encode('utf-8'))
    print('filas: %d antes, %d quitadas, %d nuevas, %d ahora' % (antes, antes - len(filas), len(nuevas),
                                                                 len(mall['rows'])))


if __name__ == '__main__':
    main()
