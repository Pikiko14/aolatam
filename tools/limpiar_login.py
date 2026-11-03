"""Quita las nubes y los angeles que el cliente dibuja sobre el fondo del login (03/11/2026): "puedes quitar esos
angeles y nubes?". Con el fondo nuevo (tools/fondo_login.py) tapaban la imagen.

Cada pieza se reemplaza por una del mismo tamano y el mismo anclaje, toda transparente, en
parches/extras/shape/log/. Los marcos, botones y caras del login no se tocan.

    python tools/limpiar_login.py
    python tools/generar_parche.py
"""
import pathlib
import struct
import sys

from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
sys.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))
from icono_subasta import a_shp

SALIDA = RAIZ / 'parches' / 'extras' / 'shape' / 'log'
PIEZAS = ('w038_04', 'w038_05',      # nubes con angel, izquierda y derecha
          'w038_14', 'w038_15',      # nubes de arriba
          'w038_29', 'w038_31')      # los angelitos


def main():
    cliente = sys.argv[1] if len(sys.argv) > 1 else r'C:\AO\Angels Online'
    sys.argv = [sys.argv[0], cliente]
    import editor_mapas as em
    em.cargar()
    SALIDA.mkdir(parents=True, exist_ok=True)
    for nombre in PIEZAS:
        orig = em.datos('shape/log/%s.shp' % nombre)
        w, h = struct.unpack_from('<II', orig, 20)
        ancla = struct.unpack_from('<ii', orig, 28)
        datos = bytearray(a_shp(Image.new('RGBA', (w, h), (0, 0, 0, 0))))
        struct.pack_into('<ii', datos, 28, *ancla)
        (SALIDA / (nombre + '.shp')).write_bytes(bytes(datos))
        print('vacia', nombre, (w, h), 'ancla', ancla)


if __name__ == '__main__':
    main()
