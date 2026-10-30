"""El regalo de clase de Longbow (17) daba municion incompatible con su propia
arma.

FreshmanCatapult (19844) es una HONDA (彈弓), no un arco: solo admite bolitas
(小鋼珠/彈藥) en la mano izquierda, nunca flechas (箭矢). El regalo le daba
Wooden Arrow (458, categoria de arco y ademas nivel 10, contra un personaje
recien hecho de nivel 1), asi que el personaje arrancaba con las dos manos
YA incompatibles entre si (visible en cuanto algo tocara esas ranuras:
equipar cualquier cosa en la 3 o la 4 expulsaba una de las dos a la mochila).
Reportado por el usuario como "atacar sin flechas", "equipar flechas lvl 10
sin ser del nivel" y "al equipar el bow o las flechas se quita uno u otro",
los tres solo al crear la clase Bow.
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import clases
import inventario as inv


def test_el_regalo_de_longbow_es_compatible_entre_manos():
    regalo = clases.regalo([17, 12, 13, 15, 16, 33])
    rhand = dict(regalo)[3]
    lhand = dict(regalo)[4]
    assert inv.es_honda(rhand)
    assert inv.es_bala(lhand)
    assert inv.compatibles_manos(rhand, lhand)


def test_la_municion_de_arranque_no_pide_nivel():
    import sqlite3
    regalo = clases.regalo([17, 12, 13, 15, 16, 33])
    lhand = dict(regalo)[4]
    con = sqlite3.connect(str(RAIZ / 'corpus' / 'content.db'))
    try:
        row = con.execute('select "等級限制" from item where id = ?', (str(lhand),)).fetchone()
    finally:
        con.close()
    assert not row or not row[0] or int(row[0]) <= 1
