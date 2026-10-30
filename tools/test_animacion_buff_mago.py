"""La animacion de lanzar un buff (byte 20 del 0x0011 fase 0x00: 1=mago,
2=guerrero) no se mandaba segun el hechizo: efecto_magia_self_inicio() se
llamaba sin `es_magia`, que por defecto es False, asi que SIEMPRE salia la
animacion de guerrero (2) -- incluso para buffs de mago (施法 en magic.xml,
mag['es_magia_visual']). Reportado por el usuario: "la animacion de buff de
mago se hace como warrior".
"""
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


def _lanzar(monkeypatch, magic_id):
    clock = Clock()
    monkeypatch.setattr(app.asyncio, 'get_event_loop', lambda: clock)
    monkeypatch.setattr(app.time, 'time', lambda: clock.now)
    p = login.Personaje(hp=20000, hp_max=100000, mp=50000, mp_max=150000)
    packets = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id,
           inventario={}, monstruos={}, usuario=None, muerto=False,
           enviar=lambda *pk: packets.extend(pk),
           enviar_inmediato=lambda *pk: packets.extend(pk))
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s, 0x0006, None, None, 'test', struct.pack('<HI', magic_id, p.entity_id))
    return packets


def _byte_animacion(packets, magic_id):
    """El byte 20 del cuerpo (offset 22 del paquete entero) del 0x0011 fase
    0x00 (inicio) que lleva ese magic_id en los dos ultimos bytes."""
    for pk in packets:
        if pk[:2] == struct.pack('<H', 0x0011) and len(pk) == 25 and pk[3] & 0x80 == 0:
            if struct.unpack_from('<H', pk, 23)[0] == magic_id:
                return pk[22]
    return None


def test_buff_de_mago_usa_la_animacion_de_mago(monkeypatch):
    magic_id = 15105   # Third Spirit V: es_magia_visual=True
    assert cb.datos_magia(magic_id)['es_magia_visual']
    anim = _byte_animacion(_lanzar(monkeypatch, magic_id), magic_id)
    assert anim == 1, f"esperaba animacion de mago (1), salio {anim}"


def test_buff_que_no_es_de_mago_sigue_con_su_animacion(monkeypatch):
    magic_id = 5424   # Amazing Avatar IV: es_buff=True, es_magia_visual=False
    d = cb.datos_magia(magic_id)
    assert d['es_buff'] and not d['es_cura'] and not d['es_magia_visual']
    anim = _byte_animacion(_lanzar(monkeypatch, magic_id), magic_id)
    assert anim == 2, f"esperaba animacion de guerrero (2), salio {anim}"
