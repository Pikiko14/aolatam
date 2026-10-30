"""Cuando no hay MP para una habilidad, el servidor la rechazaba (log.info y
return) sin avisarle nada al cliente: el hechizo simplemente no pasaba nada,
sin explicacion. Reportado por el usuario: "no sale [aviso] cuando no hay
mana"."""
import heapq
import itertools
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate as cb
import login


class Clock:
    def __init__(self):
        self.now = 1000000.0
        self.pending = []
        self.ids = itertools.count()

    def call_later(self, delay, callback):
        heapq.heappush(self.pending, (self.now + delay, next(self.ids), callback))

    def advance(self, seconds):
        end = self.now + seconds
        while self.pending and self.pending[0][0] <= end:
            self.now, _, callback = heapq.heappop(self.pending)
            callback()
        self.now = end


def _battle(monkeypatch, mp):
    clock = Clock()
    monkeypatch.setattr(app.asyncio, 'get_event_loop', lambda: clock)
    monkeypatch.setattr(app.time, 'time', lambda: clock.now)
    p = login.Personaje(hp=20000, hp_max=100000, mp=mp, mp_max=150000)
    packets = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id,
           inventario={}, monstruos={}, usuario=None, muerto=False,
           enviar=lambda *pk: packets.extend(pk),
           enviar_inmediato=lambda *pk: packets.extend(pk))
    server = app.Servidor.__new__(app.Servidor)
    return s, p, packets, server


SKILL = 15105   # Third Spirit V, mp real (cb.datos_magia(SKILL)['mp']) > 0


def test_sin_mana_avisa_y_no_descuenta(monkeypatch):
    s, p, packets, server = _battle(monkeypatch, mp=0)
    server.manejar(s, 0x0006, None, None, 'test', struct.pack('<HI', SKILL, p.entity_id))
    assert p.mp == 0
    assert any(b'Not enough Mana' in pk for pk in packets)


def test_con_mana_suficiente_no_avisa_y_descuenta(monkeypatch):
    costo = cb.datos_magia(SKILL)['mp']
    s, p, packets, server = _battle(monkeypatch, mp=costo + 1000)
    server.manejar(s, 0x0006, None, None, 'test', struct.pack('<HI', SKILL, p.entity_id))
    assert p.mp == 1000
    assert not any(b'Not enough Mana' in pk for pk in packets)
