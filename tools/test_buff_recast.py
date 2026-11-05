"""Los buffs solo los frena su propio enfriamiento (05/11/2026): "porque cada 10 seg si dice 2 sec de cooldown".

Hubo un freno extra (no recastear un buff activo durante 10 s) que dejaba a la asistencia automatica reintentando
sin parar; se quito. Charming Blessing (202) tiene 2 s de enfriamiento: a los 2 s se puede volver a lanzar.
"""
import heapq
import pathlib
import struct
import sys
from types import SimpleNamespace

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import app  # noqa: E402
import combate as cb  # noqa: E402
import login  # noqa: E402


class Reloj:
    def __init__(self):
        self.now, self.pend, self.n = 1000.0, [], 0

    def call_later(self, demora, fn):
        self.n += 1
        heapq.heappush(self.pend, (self.now + demora, self.n, fn))

    def avanzar(self, s):
        fin = self.now + s
        while self.pend and self.pend[0][0] <= fin:
            self.now, _, fn = heapq.heappop(self.pend)
            fn()
        self.now = fin


def test_el_buff_se_relanza_al_acabar_su_enfriamiento(monkeypatch):
    r = Reloj()
    monkeypatch.setattr(app.asyncio, 'get_event_loop', lambda: r)
    monkeypatch.setattr(app.time, 'time', lambda: r.now)
    monkeypatch.setattr(app, '_otorgar_skill_exp', lambda *a, **kw: [])
    monkeypatch.setattr(app, '_dar_sp', lambda *a, **kw: None)
    monkeypatch.setattr(app, '_stats_ses', lambda *a: b'')
    monkeypatch.setattr(app, '_receptores_de_buff', lambda *a: ([], True))
    p = login.Personaje(hp=5000, hp_max=5000, mp=5000, mp_max=5000)
    s = SimpleNamespace(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, monstruos={},
                        usuario=None, muerto=False, enviar=lambda *a: None, enviar_inmediato=lambda *a: None)
    srv = app.Servidor.__new__(app.Servidor)
    mag = cb.datos_magia(202)
    coste, cd = mag['mp'], mag['cd_ms'] / 1000.0
    assert cd == 2.0

    def lanzar(espera):
        srv.manejar(s, 0x0006, None, None, 't', struct.pack('<HI', 202, p.entity_id))
        r.avanzar(espera)

    lanzar(0.5)
    assert p.mp == 5000 - coste
    lanzar(cd)                       # a los 0,5 s: aun en enfriamiento, no sale
    assert p.mp == 5000 - coste
    lanzar(0.5)                      # pasados los 2 s: sale aunque el buff siga activo
    assert p.mp == 5000 - 2 * coste


def test_al_rechazar_se_le_dice_al_cliente_cuanto_falta(monkeypatch):
    """Sin respuesta el cliente reintentaba cada ~50 ms y el personaje se quedaba pegado."""
    r = Reloj()
    monkeypatch.setattr(app.asyncio, 'get_event_loop', lambda: r)
    monkeypatch.setattr(app.time, 'time', lambda: r.now)
    monkeypatch.setattr(app, '_otorgar_skill_exp', lambda *a, **kw: [])
    monkeypatch.setattr(app, '_dar_sp', lambda *a, **kw: None)
    monkeypatch.setattr(app, '_stats_ses', lambda *a: b'')
    monkeypatch.setattr(app, '_receptores_de_buff', lambda *a: ([], True))
    p = login.Personaje(hp=5000, hp_max=5000, mp=5000, mp_max=5000)
    pk = []
    s = SimpleNamespace(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, monstruos={},
                        usuario=None, muerto=False, enviar=lambda *a: pk.extend(a), enviar_inmediato=lambda *a: pk.extend(a))
    srv = app.Servidor.__new__(app.Servidor)

    def pedir():
        srv.manejar(s, 0x0006, None, None, 't', struct.pack('<HI', 202, p.entity_id))

    pedir()
    r.avanzar(0.3)
    pk.clear()
    for _ in range(6):                 # la rafaga de la asistencia: 6 en 0,3 s
        pedir()
        r.avanzar(0.05)
    cd3 = [x for x in pk if isinstance(x, (bytes, bytearray)) and len(x) == 16
           and struct.unpack_from('<HIBBII', x)[:5] == (0x001D, p.entity_id, 1, 3, 202)]
    assert len(cd3) == 1                                   # uno solo, no uno por peticion
    assert 0 < struct.unpack_from('<HIBBII', cd3[0])[5] <= 2000
    assert p.mp == 5000 - cb.datos_magia(202)['mp']        # y no se lanzo de nuevo


def test_el_segundo_buff_sale_al_acabar_la_animacion_del_primero(monkeypatch):
    r = Reloj()
    monkeypatch.setattr(app.asyncio, 'get_event_loop', lambda: r)
    monkeypatch.setattr(app.time, 'time', lambda: r.now)
    monkeypatch.setattr(app, '_otorgar_skill_exp', lambda *a, **kw: [])
    monkeypatch.setattr(app, '_dar_sp', lambda *a, **kw: None)
    monkeypatch.setattr(app, '_stats_ses', lambda *a: b'')
    monkeypatch.setattr(app, '_receptores_de_buff', lambda *a: ([], True))
    p = login.Personaje(hp=5000, hp_max=5000, mp=5000, mp_max=5000)
    pk = []
    s = SimpleNamespace(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, monstruos={},
                        usuario=None, muerto=False, enviar=lambda *a: pk.extend(a), enviar_inmediato=lambda *a: pk.extend(a))
    srv = app.Servidor.__new__(app.Servidor)
    a, b = cb.datos_magia(202), cb.datos_magia(203)
    assert a['cast_time'] >= 1000 and not a.get('cost_sp') and not b.get('cost_sp')

    srv.manejar(s, 0x0006, None, None, 't', struct.pack('<HI', 202, p.entity_id))
    r.avanzar(0.2)
    srv.manejar(s, 0x0006, None, None, 't', struct.pack('<HI', 203, p.entity_id))   # en plena animacion
    r.avanzar(0.1)
    assert p.mp == 5000 - a['mp']                       # todavia no ha salido
    sin_lanzar = [x for x in pk if isinstance(x, (bytes, bytearray)) and len(x) == 16
                  and struct.unpack_from('<HIBBII', x)[:5] == (0x001D, p.entity_id, 1, 3, 203)]
    assert not sin_lanzar                               # y no se le puso enfriamiento sin lanzarlo
    r.avanzar(a['cast_time'] / 1000.0 + 1.0)
    assert p.mp == 5000 - a['mp'] - b['mp']             # salio sola al acabar la del primero
    assert 203 in p.buffs and 202 in p.buffs
