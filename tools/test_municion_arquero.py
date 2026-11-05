"""El arquero recibe 1000 Feshman Bullet al elegir clase (05/11/2026); antes un 15000 que no existe."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import clases  # noqa: E402
import house_services  # noqa: E402
import inventario  # noqa: E402


def test_longbow_recibe_la_honda_y_balas_de_verdad():
    regalo = dict(clases.regalo([17, 18, 19, 15, 16, 13]))
    assert inventario.es_honda(regalo[3])
    assert regalo[4] == clases.MUNICION_HONDA == 145
    fila = house_services.xml_rows('item.xml').get(regalo[4])
    assert fila and fila.get('物品類別') == '彈藥' and not fila.get('等級限制')
    assert inventario.compatibles_manos(regalo[3], regalo[4])


def test_la_vieja_no_existe():
    assert house_services.xml_rows('item.xml').get(clases.MUNICION_VIEJA) is None
