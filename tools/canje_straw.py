"""Los canjes propios de exchange.xml (pedido del usuario el 31/10/2026):

* Green Angel (Angel Lyceum, grupo lyceum_services.GRUPO_GREEN = 401): pestles, ride feed y hammers de nivel 3, 4 y 5,
  uno por 100 Straws.
* Event Overview > Exchange > Enhanced Pestle and Ride Feed (grupo 595): lo mismo y ademas el nivel 6, por tickets de
  su tipo (los suelta el jefe de Dark Cavern, instancia_oscura.tickets_del_jefe): 20 el nivel 3, 30 el 4, 40 el 5 y 50
  el 6. Y las gemas de nivel 40 (Ruby, Orange Gem...) por 20 Lucky Piercing Hammer Ticket (no hay runas de nivel bajo).

Reescribe las recetas de esos grupos en extracted_paks/update26/setting/eng/exchange.xml (el que lee el servidor),
reusando los numeros de receta que ya tenia cada grupo (si faltan, toma filas del GRUPO_VACIO). El cliente pinta la ventana con el
mismo exchange.xml, asi que despues hay que publicarlo:

    python tools/canje_straw.py
    python tools/publicar_setting.py exchange.xml        # parche + VPS
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.stdout.reconfigure(encoding='utf-8')

import lyceum_services as ly

ARCHIVO = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'exchange.xml'

PESTLES = ((6897, '3-star Lucky Enhanced Pestle'), (6898, '4-star Lucky Enhanced Pestle'),
           (6899, '5-star Lucky Enhanced Pestle'))
RIDE_FEED = ((7039, 'Lvl 3 Lucky Ride Feed'), (7040, 'Lvl 4 Lucky Ride Feed'), (7041, 'Lvl 5 Lucky Ride Feed'))
PIERCING = ((6907, '3-star Lucky Piercing Hammer'), (6908, '4-star Lucky Piercing Hammer'),
            (6909, '5-star Lucky Piercing Hammer'))
HAMMERS = ((7085, '3-star Lucky Hammer'), (7086, '4-star Lucky Hammer'), (7087, '5-star Lucky Hammer'))
# Nivel 6: solo en el canje por tickets (31/10/2026).
NIVEL_6 = {'pestle': (6900, '6-star Lucky Enhanced Pestle'), 'ride': (7042, 'Lvl 6 Lucky Ride Feed'),
           'piercing': (6910, '6-star Lucky Piercing Hammer'), 'hammer': (7088, '6-star Lucky Hammer')}
# Las de nivel 40 (las Clean son de nivel 60).
GEMAS = ((3093, 'Ruby'), (3098, 'Orange Gem'), (3103, 'Yellow Gem'), (3108, 'Emerald'), (3113, 'Sapphire'),
         (3118, 'Purple Gem'))
PREMIOS = PESTLES + RIDE_FEED + PIERCING + HAMMERS          # los del Green Angel (el orden de la ventana)
TICKETS_POR_NIVEL = (20, 30, 40, 50)                        # niveles 3, 4, 5 y 6

TICKET_PESTLE, TICKET_RIDE, TICKET_PIERCING, TICKET_HAMMER = 20228, 20229, 20230, 20231
GRUPO_TICKETS = 595
GRUPO_VACIO = 0        # donde van las recetas que sobran (ver reescribir)


def _por_tickets(premios, ticket):
    return [(i, n, ticket, cuantos) for (i, n), cuantos in zip(premios, TICKETS_POR_NIVEL)]

# Event Overview > Exchange > Ride and Robots (grupo 538): monturas raras de nivel 50-60 que no vende ningun NPC, por
# Mount Coins (cliente_local.ITEM_MONEDA_MONTURA, de Dark Cavern). Las 92 recetas que tenia (monturas y robots de
# nivel 170-370 por vouchers de eventos) estan en tools/respaldos/exchange_538_ride_and_robots.xml.
GRUPO_MONTURAS = 538
MOUNT_COIN = 89073
MONTURAS = ((3722, 'Flame Warrior', 50), (3725, 'Blue Cyclone', 50), (507, 'Hell Wolf', 50),
            (504, 'Ice Magic Cat', 50), (3854, 'Gold Lizard', 50), (3855, 'Evil Star Cat', 50),
            (505, 'Beast God of Forest', 50), (3723, 'Evil Lizard', 50), (3724, 'Handsome Burro', 50),
            (3800, 'Icy Lizard', 50), (506, 'Marmot', 50), (3799, 'Night Cat', 50), (3853, 'Silver Lizard', 50),
            (5128, 'Flame Eagle', 60), (5129, 'Thunder Bird', 60), (4911, 'Iron Land Bird', 60),
            (4912, 'Blue Sea Soldier', 60), (4523, 'Red Circus Elephant', 60), (4522, 'Red Stiff Beetle', 60),
            (6473, 'Anniversary Elephant', 60), (6472, 'Anniversary Turtle', 60), (7212, 'Bright Gold Turtle', 60),
            (5684, 'Cherry Kiss Turtle', 60), (4913, 'Shake Turtle', 60), (4909, 'Swift Turtle', 60))
COINS_POR_NIVEL = {50: 30, 60: 50}

# {grupo: [(objeto, nombre, material, cuantos)]}
CANJES = {
    ly.GRUPO_GREEN: [(item, nombre, ly.STRAW, 100) for item, nombre in PREMIOS],
    GRUPO_TICKETS: (_por_tickets(PESTLES + (NIVEL_6['pestle'],), TICKET_PESTLE)
                    + _por_tickets(RIDE_FEED + (NIVEL_6['ride'],), TICKET_RIDE)
                    + _por_tickets(PIERCING + (NIVEL_6['piercing'],), TICKET_PIERCING)
                    + _por_tickets(HAMMERS + (NIVEL_6['hammer'],), TICKET_HAMMER)
                    + [(i, n, TICKET_PIERCING, 20) for i, n in GEMAS]),
    GRUPO_MONTURAS: [(i, n, MOUNT_COIN, COINS_POR_NIVEL[nv]) for i, n, nv in MONTURAS],
}


def reescribir(texto, grupo=ly.GRUPO_GREEN):
    """El exchange.xml con las recetas de `grupo` cambiadas por CANJES[grupo]; (texto, numeros de receta usados)."""
    recetas = CANJES[grupo]
    filas = list(re.finditer(r'<exchange 編號="(\d+)" 群組="%d"[^>]*/>' % grupo, texto))
    if len(filas) < len(recetas) and grupo != GRUPO_VACIO:
        libres = list(re.finditer(r'<exchange 編號="(\d+)" 群組="%d"[^>]*/>' % GRUPO_VACIO, texto))
        filas = sorted(filas + libres[:len(recetas) - len(filas)], key=lambda f: int(f.group(1)))
    if len(filas) < len(recetas):
        raise SystemExit('el grupo %d tiene %d recetas y hacen falta %d' % (grupo, len(filas), len(recetas)))
    numeros = [int(f.group(1)) for f in filas][:len(recetas)]
    # Cada fila se cambia EN SU SITIO (las de un grupo pueden estar repartidas por el archivo). LAS QUE SOBRAN NO SE
    # BORRAN: el cliente usa el 編號 como posicion en la lista (van 1, 2, 3... sin huecos) y quitando filas se
    # descuadraba todo lo que venia detras: las ventanas de canje salian vacias (31/10/2026). Se quedan con su
    # numero, en el grupo GRUPO_VACIO, que no abre nadie.
    cambios = {}
    for f, (item, nombre, material, cuantos) in zip(filas, recetas):
        cambios[f.start()] = (f.end(), '<exchange 編號="%s" 群組="%d" 獎賞說明="%s" 獎賞1="%d" 獎賞1數量="1" 材料1="%d" '
                                        '材料1數量="%d"/>' % (f.group(1), grupo, nombre, item, material, cuantos))
    for f in filas[len(recetas):]:
        cambios[f.start()] = (f.end(), re.sub(r'群組="\d+"', '群組="%d"' % GRUPO_VACIO, f.group(0), count=1))
    for inicio in sorted(cambios, reverse=True):
        fin, nuevo = cambios[inicio]
        texto = texto[:inicio] + nuevo + texto[fin:]
    return texto, numeros


def main():
    texto = ARCHIVO.read_bytes().decode('utf-8')
    for grupo, recetas in CANJES.items():
        texto, numeros = reescribir(texto, grupo)
        print('grupo %d: %d recetas (%d-%d)' % (grupo, len(numeros), numeros[0], numeros[-1]))
    ARCHIVO.write_bytes(texto.encode('utf-8'))


if __name__ == '__main__':
    main()
