"""El tooltip del amigo: nivel, faccion, oficio, rango y liga (01/11/2026)."""
import pathlib
import struct
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import amigos
import login


def _ses(cid, nombre):
    p = login.Personaje(char_id=cid, entity_id=cid, nombre=nombre, stage=41, nivel=60)
    p.faction, p.class_id, p.rango, p.apariencia = 'Beasts', 12, 3, [1, 0, 0, 0, 0]
    return SimpleNamespace(personaje=p, desconectado=False, conectado=True, rol='mundo')


def test_el_0028_lleva_el_perfil_en_el_41_y_nada_en_el_cumpleanos():
    b = amigos._status(_ses(1, 'Impacty'), 5, 'Baco', _ses(5, 'Baco'))[2:]
    assert len(b) == 83 and b[30:41] == bytes(11)
    assert (b[41], struct.unpack_from('<I', b, 42)[0], b[46], b[47], b[48]) == (1, 60, 2, 12, 3)
    assert b[66:70] == b'Baco'


def test_el_002a_lleva_el_perfil_en_el_59():
    b = amigos._added(_ses(1, 'Impacty'), _ses(5, 'Baco'))[2:]
    assert len(b) == 84 and b[48:59] == bytes(11)
    assert (b[59], struct.unpack_from('<I', b, 60)[0], b[64], b[65], b[66]) == (1, 60, 2, 12, 3)
