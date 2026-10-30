"""La ropa de arranque (Students' Uniform/Gloves/Shoes) es de mujer en
item.xml (dolls 129/131/133): puesta a un personaje hombre no se dibuja y
queda con el cuerpo descubierto, aunque el servidor la de por puesta.

personaje_nuevo() nunca miraba el genero y entregaba siempre la ropa de
mujer. Reportado por el usuario: "empiezas el juego con ropa puesta y no te
da los items clasicos de student de AL" (un personaje hombre).
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import personajes


def test_personaje_mujer_recibe_la_ropa_de_mujer():
    p = personajes.personaje_nuevo('Karma', 0, 1001, elegidos=[0, 0, 1, 0, 0])
    assert p['inventario']['2'] == personajes.ROPA_INICIAL['cuerpo']
    assert p['inventario']['5'] == personajes.ROPA_INICIAL['guantes']
    assert p['inventario']['6'] == personajes.ROPA_INICIAL['zapatos']


def test_personaje_hombre_recibe_la_ropa_de_hombre():
    p = personajes.personaje_nuevo('Karmo', 0, 1002, elegidos=[1, 0, 1, 0, 0])
    assert p['inventario']['2'] == personajes.ROPA_INICIAL_HOMBRE['cuerpo']
    assert p['inventario']['5'] == personajes.ROPA_INICIAL_HOMBRE['guantes']
    assert p['inventario']['6'] == personajes.ROPA_INICIAL_HOMBRE['zapatos']


def test_sin_eleccion_se_usa_la_apariencia_por_defecto_mujer():
    p = personajes.personaje_nuevo('SinElegir', 0, 1003, elegidos=None)
    assert p['inventario']['2'] == personajes.ROPA_INICIAL['cuerpo']
