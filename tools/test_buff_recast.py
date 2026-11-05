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


def test_a_mano_se_refresca_pero_no_en_rafaga(monkeypatch):
    import heapq
    import struct
    import combate as cb
    import login

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
    coste = cb.datos_magia(202)['mp']

    def lanzar():
        srv.manejar(s, 0x0006, None, None, 't', struct.pack('<HI', 202, p.entity_id))
        r.avanzar(3)

    lanzar()
    assert p.mp == 5000 - coste
    lanzar()                                   # 3 s despues: rafaga, no se cobra
    assert p.mp == 5000 - coste
    r.avanzar(12)
    lanzar()                                   # 15 s despues: a mano se refresca
    assert p.mp == 5000 - 2 * coste
