"""La asistencia automatica no recastea un buff que el objetivo aun lleva (04/11/2026)."""
import pathlib
import sys
import time
from types import SimpleNamespace

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import app  # noqa: E402

YO = 1001


def _ses(buffs=None, mascota=None, pet=None):
    p = SimpleNamespace(buffs=buffs or {}, mascota=mascota)
    return SimpleNamespace(personaje=p, pet_entity_id=pet)


def test_buff_propio_vigente():
    s = _ses({202: {'fin': time.time() + 200}})
    ent, queda = app._buff_vigente(s, 202, YO, YO)
    assert ent == YO and queda > app.BUFF_RECAST_MARGEN_S
    assert app._buff_vigente(s, 203, YO, YO) is None
    assert app._buff_vigente(s, 202, 0, YO)[0] == YO


def test_buff_a_punto_de_acabar_o_acabado():
    s = _ses({'702': {'fin': time.time() + 10}, 703: {'fin': time.time() - 5}})
    assert app._buff_vigente(s, 702, YO, YO)[1] < app.BUFF_RECAST_MARGEN_S
    assert app._buff_vigente(s, 703, YO, YO) is None


def test_buff_de_la_mascota():
    fp = {'fuera': True, 'entidad': 5000, 'buffs': {703: {'fin': time.time() + 300}}}
    s = _ses({}, mascota=fp, pet=5000)
    assert app._buff_vigente(s, 703, 5000, YO)[0] == 5000
    assert app._buff_vigente(s, 703, YO, YO) is None
