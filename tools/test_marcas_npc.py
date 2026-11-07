"""[!] en el nombre de los NPC con mision para el jugador (06/11/2026)."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import login  # noqa: E402
import marcas_npc as mn  # noqa: E402
import misiones  # noqa: E402


def _ses(quests=None):
    p = NS(char_id=1, nombre='T', nivel=25, rango=2, stage=3, faction='Aurora', quests=quests or [],
           entity_id=1001, exp=0, oro=0)
    env = []
    return NS(personaje=p, rol='mundo', enviar=lambda *s: env.extend(s), usuario=None), env


def _nombre(pkt):
    return pkt[2 + 16:2 + 33].split(b'\0', 1)[0].decode()


def test_npc_con_mision_lleva_marca():
    ses, _ = _ses()
    pk = login._npc_spawn(950, 1234, 'Aurora Angel', (10, 10), sprite=40001, klass=199)
    (out,) = mn.marcar(ses, (pk,))
    assert _nombre(out).startswith('[!]Aurora Angel'[:16])
    assert len(out) == len(pk) and out[2 + 32] == 0


def test_npc_sin_mision_y_monstruos_quedan_igual():
    ses, _ = _ses()
    npc = login._npc_spawn(951, 1234, 'Nadie Raro', (10, 10), sprite=40001, klass=199)
    mob = login._npc_spawn(952, 19, 'Aurora Angel', (10, 10), klass=1)
    assert mn.marcar(ses, (npc, mob)) == (npc, mob)


def test_al_hacerla_se_quita_la_marca():
    ses, env = _ses()
    pk = login._npc_spawn(950, 1234, 'Aurora Angel', (10, 10), sprite=40001, klass=199)
    mn.marcar(ses, (pk,))
    ses.personaje.quests = [(q, 99) for q in misiones.misiones_disponibles_npc(ses.personaje, 'Aurora Angel', 3)]
    import unittest.mock as um
    with um.patch.object(misiones, 'mision_completada', lambda p, q: True):
        mn.refrescar(ses)
    assert env and env[0][:2] == b'\x07\x00' and _nombre(env[1]) == 'Aurora Angel'
    mn.olvidar(ses)
