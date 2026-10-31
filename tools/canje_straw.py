"""Los canjes propios de exchange.xml (pedido del usuario el 31/10/2026):

* Green Angel (Angel Lyceum, grupo lyceum_services.GRUPO_GREEN = 401): pestles, ride feed y hammers de nivel 3, 4 y 5,
  uno por 100 Straws.
* Event Overview > Exchange > Enhanced Pestle and Ride Feed (grupo 595): lo mismo, uno por 20 tickets de su tipo
  (los suelta el jefe de Dark Cavern, instancia_oscura.tickets_del_jefe), y las gemas Clean por 20 Lucky Piercing
  Hammer Ticket (no hay runas de nivel bajo).

Reescribe las recetas de esos grupos en extracted_paks/update26/setting/eng/exchange.xml (el que lee el servidor),
reusando los numeros de receta que ya tenia cada grupo; las que sobran se quitan. El cliente pinta la ventana con el
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
GEMAS = ((3094, 'Clean Ruby'), (3099, 'Clean Orange Gem'), (3104, 'Clean Yellow Gem'), (3109, 'Clean Emerald'),
         (3114, 'Clean Sapphire'), (3119, 'Clean Purple Gem'))
PREMIOS = PESTLES + RIDE_FEED + PIERCING + HAMMERS          # los del Green Angel (el orden de la ventana)

TICKET_PESTLE, TICKET_RIDE, TICKET_PIERCING, TICKET_HAMMER = 20228, 20229, 20230, 20231
GRUPO_TICKETS = 595
GRUPO_VACIO = 0        # donde van las recetas que sobran (ver reescribir)

# {grupo: [(objeto, nombre, material, cuantos)]}
CANJES = {
    ly.GRUPO_GREEN: [(item, nombre, ly.STRAW, 100) for item, nombre in PREMIOS],
    GRUPO_TICKETS: ([(i, n, TICKET_PESTLE, 20) for i, n in PESTLES] + [(i, n, TICKET_RIDE, 20) for i, n in RIDE_FEED]
                    + [(i, n, TICKET_PIERCING, 20) for i, n in PIERCING]
                    + [(i, n, TICKET_HAMMER, 20) for i, n in HAMMERS]
                    + [(i, n, TICKET_PIERCING, 20) for i, n in GEMAS]),
}


def reescribir(texto, grupo=ly.GRUPO_GREEN):
    """El exchange.xml con las recetas de `grupo` cambiadas por CANJES[grupo]; (texto, numeros de receta usados)."""
    recetas = CANJES[grupo]
    filas = list(re.finditer(r'[ \t]*<exchange 編號="(\d+)" 群組="%d"[^>]*/>\r?\n' % grupo, texto))
    if len(filas) < len(recetas):
        raise SystemExit('el grupo %d tiene %d recetas y hacen falta %d' % (grupo, len(filas), len(recetas)))
    if any(texto[a.end():b.start()].strip() for a, b in zip(filas, filas[1:])):
        raise SystemExit('las recetas del grupo %d no van seguidas en exchange.xml' % grupo)
    salto = '\r\n' if '\r\n' in filas[0].group(0) else '\n'
    numeros = [int(f.group(1)) for f in filas][:len(recetas)]
    nuevas = ''.join('\t<exchange 編號="%d" 群組="%d" 獎賞說明="%s" 獎賞1="%d" 獎賞1數量="1" 材料1="%d" 材料1數量="%d"/>%s'
                     % (n, grupo, nombre, item, material, cuantos, salto)
                     for n, (item, nombre, material, cuantos) in zip(numeros, recetas))
    # LAS QUE SOBRAN NO SE BORRAN: el cliente usa el 編號 como posicion en la lista (van 1, 2, 3... sin huecos) y
    # quitando filas se descuadraba todo lo que venia detras: las ventanas de canje salian vacias (31/10/2026).
    # Se quedan con su numero, en el grupo GRUPO_VACIO, que no abre nadie.
    sobrantes = ''.join(re.sub(r'群組="\d+"', '群組="%d"' % GRUPO_VACIO, f.group(0), count=1)
                        for f in filas[len(recetas):])
    return texto[:filas[0].start()] + nuevas + sobrantes + texto[filas[-1].end():], numeros


def main():
    texto = ARCHIVO.read_bytes().decode('utf-8')
    for grupo, recetas in CANJES.items():
        texto, numeros = reescribir(texto, grupo)
        print('grupo %d: %d recetas (%d-%d)' % (grupo, len(numeros), numeros[0], numeros[-1]))
    ARCHIVO.write_bytes(texto.encode('utf-8'))


if __name__ == '__main__':
    main()
