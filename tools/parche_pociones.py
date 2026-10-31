"""Cooldown de las pociones: 1 s para todo consumible que cura HP o MP.

El cooldown de una pocion no lo pone el servidor: lo lee el cliente de su magic.xml
(columna 後置時間, 500 ms de origen). Este script toma el magic.xml vigente del
cliente, sube a COOLDOWN_MS esa columna en las filas de magia que usan los
consumibles de HP/MP, y deja el resultado en parches/extras/ para que
server/parche.py lo meta en update27.pak.

El servidor valida lo mismo al usar el objeto (app.py, COOLDOWN_POCION_S), por si
alguien edita sus archivos.

Uso:
    python tools/parche_pociones.py [ruta del cliente]
    python tools/generar_parche.py
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.stdout.reconfigure(encoding='utf-8')

import cliente_local
import inventario
import parche
import house_services as hs

COOLDOWN_MS = 1000
NOMBRE = 'SETTING\\ENG\\MAGIC.XML'
SALIDA = RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'magic.xml'


def magias_de_pociones() -> set:
    """Ids de magic.xml de los consumibles que curan HP o MP (los de app.py, Caso 5)."""
    magia = hs.xml_rows('magic.xml')
    ids = set()
    for k, fila in hs.xml_rows('item.xml').items():
        mid = fila.get('常駐法術')
        if fila.get('可使用') != '是' or not (mid and mid.isdigit()):
            continue
        m = magia.get(int(mid))
        if not m or m.get('對象') != '自己' or not (m.get('HP') or m.get('MP')):
            continue
        ef = inventario.efecto_consumible(int(k))
        if ef and ('hp' in ef or 'mp' in ef):
            ids.add(int(mid))
    return ids


def magic_xml_vigente(ruta_cli: pathlib.Path) -> bytes:
    """El magic.xml que el cliente lee de verdad (el del pak de numero mas alto)."""
    pak = cliente_local.indice_paks(ruta_cli)[NOMBRE]
    crudo = pak.read_bytes()
    return parche._leer(crudo, parche._directorio(crudo)[NOMBRE])


def main():
    ruta = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else r'C:\AO\Angels Online')
    ids = magias_de_pociones()
    texto = magic_xml_vigente(ruta).decode('utf-8')
    cambiadas = 0

    def cambiar(m):
        nonlocal cambiadas
        if int(m.group(1)) not in ids:
            return m.group(0)
        if '後置時間=' in m.group(0):
            nuevo = re.sub(r'後置時間="\d+"', '後置時間="%d"' % COOLDOWN_MS, m.group(0), count=1)
        else:                       # sin la columna: el cliente usa su valor por defecto, se la ponemos
            nuevo = re.sub(r'\s*/?>$', ' 後置時間="%d" />' % COOLDOWN_MS, m.group(0))
        if nuevo != m.group(0):
            cambiadas += 1
        return nuevo

    texto = re.sub(r'<法術 編號="(\d+)"[^>]*>', cambiar, texto)
    texto = cliente_local._parchear_magias_propias_xml_bytes(texto.encode('utf-8')).decode('utf-8')   # auras Low
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_bytes(texto.encode('utf-8'))
    print('magias de pociones:', len(ids), 'filas cambiadas:', cambiadas, '->', SALIDA)


if __name__ == '__main__':
    main()
