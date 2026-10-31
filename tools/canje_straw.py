"""El canje de Straws del Green Angel (Angel Lyceum): pestles, ride feed y hammers por 100 Straws cada uno.

Reescribe las recetas del grupo lyceum_services.GRUPO_GREEN (401) de extracted_paks/update26/setting/eng/exchange.xml
(el que lee el servidor) con PREMIOS, reusando los numeros de receta que ya tenia el grupo; las que sobran se quitan.
El cliente pinta la ventana con el mismo exchange.xml, asi que despues hay que publicarlo:

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
STRAWS = 100
# (objeto, nombre): niveles 3, 4 y 5 de cada cosa (pedido del usuario el 31/10/2026).
PREMIOS = (
    (6897, '3-star Lucky Enhanced Pestle'), (6898, '4-star Lucky Enhanced Pestle'), (6899, '5-star Lucky Enhanced Pestle'),
    (7039, 'Lvl 3 Lucky Ride Feed'), (7040, 'Lvl 4 Lucky Ride Feed'), (7041, 'Lvl 5 Lucky Ride Feed'),
    (6907, '3-star Lucky Piercing Hammer'), (6908, '4-star Lucky Piercing Hammer'), (6909, '5-star Lucky Piercing Hammer'),
    (7085, '3-star Lucky Hammer'), (7086, '4-star Lucky Hammer'), (7087, '5-star Lucky Hammer'),
)


def reescribir(texto):
    """El exchange.xml con el grupo del Green Angel cambiado; (texto, numeros de receta usados)."""
    filas = list(re.finditer(r'[ \t]*<exchange 編號="(\d+)" 群組="%d"[^>]*/>\r?\n' % ly.GRUPO_GREEN, texto))
    if len(filas) < len(PREMIOS):
        raise SystemExit('el grupo %d tiene %d recetas y hacen falta %d' % (ly.GRUPO_GREEN, len(filas), len(PREMIOS)))
    salto = '\r\n' if '\r\n' in filas[0].group(0) else '\n'
    numeros = [int(f.group(1)) for f in filas][:len(PREMIOS)]
    nuevas = ''.join('\t<exchange 編號="%d" 群組="%d" 獎賞說明="%s" 獎賞1="%d" 獎賞1數量="1" 材料1="%d" 材料1數量="%d"/>%s'
                     % (n, ly.GRUPO_GREEN, nombre, item, ly.STRAW, STRAWS, salto)
                     for n, (item, nombre) in zip(numeros, PREMIOS))
    # Las filas del grupo van seguidas: se cambia el bloque entero.
    return texto[:filas[0].start()] + nuevas + texto[filas[-1].end():], numeros


def main():
    texto, numeros = reescribir(ARCHIVO.read_bytes().decode('utf-8'))
    ARCHIVO.write_bytes(texto.encode('utf-8'))
    print('grupo %d: %d recetas (%d-%d), %d Straws cada una' % (ly.GRUPO_GREEN, len(numeros), numeros[0], numeros[-1], STRAWS))


if __name__ == '__main__':
    main()
