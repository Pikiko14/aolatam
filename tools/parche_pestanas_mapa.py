"""Quita de la ventana del mapa (M) las pestanas de las expansiones cerradas (configuracion.MAPAS_APAGADOS).

Las pestanas (Scene, World, Dungeon, Atlantis, Forest... y "Switch Maps", que pasa a la segunda tanda) son
botones de la ventana 556 de setting/eng/wnd01.xml. El script del cliente (main.lua, CreateStageMapWnd) oculta
las que el ejecutable no tiene definidas y a las demas solo les ajusta la altura, conservando su X. Asi que
basta con mandar la X de las que sobran fuera de la pantalla: el cliente las deja ahi y no se ven, sin tocar el
ejecutable ni los scripts compilados.

Una region se oculta si TODOS sus mapas (jumpmap.xml, por su 類別1) estan en MAPAS_APAGADOS: al abrir una expansion
(borrando su bloque de configuracion.py) y volver a correr esto, su pestana vuelve. "Switch Maps" se oculta si
todas las pestanas de la segunda tanda lo estan.

    python tools/parche_pestanas_mapa.py
    python tools/publicar_setting.py wnd01.xml --sin-copiar      # parche + VPS
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.stdout.reconfigure(encoding='utf-8')

import configuracion
from house_services import xml_rows

ORIGEN = RAIZ / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'wnd01.xml'
SALIDA = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'wnd01.xml'
VENTANA_MAPA = '556'
PRIMERA_TANDA = {'12245', '12246', '12899', '12898', '12897', '12896', '12895', '12894'}
SWITCH_MAPS = '24750'
FUERA = 5000          # X fuera de cualquier pantalla


def regiones_cerradas():
    """Nombres (en minusculas) de las regiones de jumpmapclass.xml con todos sus mapas apagados."""
    # Por la categoria PRINCIPAL (類別1): los mapas 129-131 son de Heart of Eden (abiertos) y salen tambien en
    # Desert como 類別2; con ellos Desert nunca quedaba cerrada.
    mapas = {}
    for fila in xml_rows('jumpmap.xml').values():
        v = fila.get('類別1')
        if str(v).isdigit():
            mapas.setdefault(int(v), set()).add(int(fila.get('場景編號') or 0))
    out = set()
    for cid, fila in xml_rows('jumpmapclass.xml').items():
        stages = mapas.get(int(cid))
        if stages and stages <= set(configuracion.MAPAS_APAGADOS):
            out.add(fila.get('類別名稱', '').strip().lower())
    return out


def pestanas(texto):
    """{id: titulo} de los botones hijos de la ventana del mapa."""
    m = re.search(r'<window[^>]*\bid="%s"[^>]*>(.*?)</window>' % VENTANA_MAPA, texto, re.S)
    hijos = set(re.findall(r'<child>(\d+)</child>', m.group(1))) if m else set()
    out = {}
    for b in re.finditer(r'<window class="WND_CLASS_BUTTON" id="(\d+)"[^>]*title="([^"]*)"', texto):
        if b.group(1) in hijos:
            out[b.group(1)] = b.group(2).strip()
    return out


def main():
    texto = ORIGEN.read_bytes().decode('utf-8')
    cerradas = regiones_cerradas()
    botones = pestanas(texto)
    ocultar = {i for i, t in botones.items() if t.lower() in cerradas}
    segunda = {i for i, t in botones.items() if i not in PRIMERA_TANDA and i != SWITCH_MAPS and t.lower() != 'show all'}
    if segunda and segunda <= ocultar:
        ocultar.add(SWITCH_MAPS)

    def mover(m):
        if m.group(1) not in ocultar:
            return m.group(0)
        return re.sub(r'range="-?\d+,', 'range="%d,' % FUERA, m.group(0), count=1)

    texto = re.sub(r'<window class="WND_CLASS_BUTTON" id="(\d+)"[^>]*>', mover, texto)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes(texto.encode('utf-8'))
    print('pestanas ocultas: %s' % ', '.join(sorted(botones.get(i, i) for i in ocultar)))
    print('quedan: %s' % ', '.join(t for i, t in botones.items() if i not in ocultar))


if __name__ == '__main__':
    main()
