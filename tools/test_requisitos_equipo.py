"""Requisitos de item.xml al equipar (04/11/2026): el escudo se ponia sin la rama Shield y sin su nivel."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import inventario as inv  # noqa: E402

ESCUDO_NEWBIE = 9          # Round Shield: Shield (14) a nivel 5
ESCUDO_FRESHMAN = 23       # sin requisitos
ESPADA_NEWBIE = 4          # 等級限制 5


def test_escudo_sin_rama_o_con_poco_nivel_no():
    assert inv.falta_requisito(ESCUDO_NEWBIE, 30, [])
    assert inv.falta_requisito(ESCUDO_NEWBIE, 30, [(9, 50, 0)])
    assert inv.falta_requisito(ESCUDO_NEWBIE, 30, [(14, 4, 0)])


def test_escudo_con_su_rama_si():
    assert inv.falta_requisito(ESCUDO_NEWBIE, 30, [(14, 5, 0)]) is None
    assert inv.falta_requisito(ESCUDO_FRESHMAN, 1, []) is None


def test_nivel_del_personaje():
    assert inv.falta_requisito(ESPADA_NEWBIE, 4, [(9, 10, 0)])
    assert inv.falta_requisito(ESPADA_NEWBIE, 5, [(9, 10, 0)]) is None
