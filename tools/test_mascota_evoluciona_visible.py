"""Al evolucionar una mascota que esta fuera, el dueno la veia cambiar pero los demas del mapa
la seguian viendo con el aspecto viejo hasta reloguear. Reportado por el usuario: "si
evolucionan los pet no lo veo inmediato deben iniciar sesion nuevamente para verlo"."""
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import login
import mascotas
import presencia

STAGE = 41


class _Ses:
    def __init__(self, eid, nombre):
        self.personaje = login.Personaje(entity_id=eid, nombre=nombre, stage=STAGE)
        self._mapa_presencia = STAGE
        self.writer = object()
        self.sent = []

    def enviar(self, *packets):
        self.sent.extend(packets)


def _opcodes(pkts):
    return [struct.unpack_from('<H', p)[0] for p in pkts]


def test_los_demas_ven_la_mascota_nueva_al_recrearla():
    owner, viewer = _Ses(1001, 'Dueno'), _Ses(1002, 'Otro')
    f = mascotas.recien_nacida('Pet', 13001)
    f.update(fuera=True, x=10, y=10)
    owner.personaje.mascota = f
    owner.pet_entity_id = 5555
    old = list(presencia._POR_MAPA.get(STAGE, []))
    try:
        presencia._POR_MAPA[STAGE] = [owner, viewer]
        salida = app._pet_recrear(owner)
    finally:
        presencia._POR_MAPA[STAGE] = old
    assert owner.pet_entity_id != 5555
    assert mascotas.quitar(5555) in salida                     # el dueno: fuera la vieja
    assert mascotas.quitar(5555) in viewer.sent                # el otro: fuera la vieja...
    assert 0x0050 in _opcodes(viewer.sent)                     # ...y aparece la nueva
    assert owner.sent == []


def test_sin_mascota_fuera_no_hace_nada():
    owner = _Ses(1001, 'Dueno')
    owner.personaje.mascota = {'fuera': False}
    assert app._pet_recrear(owner) == []
