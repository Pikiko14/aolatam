"""Los demas jugadores no veian los buffs ni los hechizos que lanzaba uno: _espejar solo
reenviaba lo que tocaba a un BICHO, y un buff (0x0011 de uno sobre si mismo) no lo toca.
Reportado por el usuario: "no puedo ver cuando otra persona usa 1 spell o buff"."""
import pathlib
import struct
import sys
from unittest import mock

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate
import presencia

YO, PUBLICO = 100, 500100


class _Ses:
    def __init__(self, eid, shared):
        self.personaje = type('P', (), {'entity_id': eid, 'stage': 1})()
        self.monstruos = shared
        self.pet_entity_id = None
        self.invocacion = self.invocacion2 = None
        self.cerrada = False
        self.received = []

    def enviar_sin_espejo(self, *packets):
        self.received.extend(packets)

    def volcar(self):
        pass


def _sala():
    shared = {9001: combate.Monstruo(9001, 1, 'Lily', (10, 10))}
    owner, viewer = _Ses(YO, shared), _Ses(200, shared)
    room = type('Room', (), {'stage': 1, 'monstruos': shared, 'sesiones': [owner, viewer]})()
    owner._sala = viewer._sala = room
    return owner, viewer


def test_el_buff_propio_le_llega_a_los_demas_con_el_id_publico():
    owner, viewer = _sala()
    buff = (combate.efecto_magia_self_inicio(YO, 251, 15105, es_magia=True),
            combate.efecto_magia_self_fin(YO, 251, 15105, es_magia=True))
    with mock.patch.object(presencia, 'entidad_de', return_value=PUBLICO):
        app._espejar(owner, buff)
    assert len(viewer.received) == 2
    for pk in viewer.received:
        assert struct.unpack_from('<II', pk, 4) == (PUBLICO, PUBLICO)


def test_los_iconos_y_cooldowns_propios_no_se_reenvian():
    owner, viewer = _sala()
    cooldown = struct.pack('<HIBBII', 0x001D, YO, 1, 3, 15105, 5000)
    with mock.patch.object(presencia, 'entidad_de', return_value=PUBLICO):
        app._espejar(owner, (cooldown,))
    assert viewer.received == []
