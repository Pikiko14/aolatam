"""PvP: los efectos secundarios de las habilidades tambien a jugadores (07/11/2026)."""
import pathlib
import sys
import time
from types import SimpleNamespace as NS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import combate  # noqa: E402
import pvp_liga as pl  # noqa: E402


def _par():
    env = []
    p = NS(nombre='A', entity_id=1, stage=16, buffs={})
    q = NS(nombre='B', entity_id=2, stage=16, buffs={}, hp=1000, char_id=2)
    a = NS(personaje=p, enviar=lambda *x: None)
    b = NS(personaje=q, enviar=lambda *x: env.extend(x), muerto=False)
    return a, b, env


def test_estados_que_paran(monkeypatch):
    a, b, _ = _par()
    llamadas = []
    monkeypatch.setattr(pl, '_aplicar_control', lambda s, o, t, m, est: llamadas.append(est))
    monkeypatch.setattr(pl, 'aplicar_dot', lambda *x, **k: llamadas.append('dot'))
    monkeypatch.setattr(combate, 'efecto_secundario', lambda t: {'magia': 9, 'prob': 100, 'estado': 'aturdido', 'dur_ms': 2000})
    pl.aplicar_secundario(a, b, 701, {'nombre': 'x'})
    monkeypatch.setattr(combate, 'efecto_secundario', lambda t: {'magia': 9, 'prob': 100, 'estado': '閃紅色', 'dur_ms': 10000,
                                                                  'hp_tick': -23, 'intervalo': 2})
    pl.aplicar_secundario(a, b, 217, {'nombre': 'x'})
    monkeypatch.setattr(combate, 'efecto_secundario', lambda t: {'magia': 9, 'prob': 0, 'estado': 'aturdido', 'dur_ms': 2000})
    pl.aplicar_secundario(a, b, 701, {'nombre': 'x'})
    assert llamadas == ['aturdido', 'dot']


def test_quieto():
    _, b, _ = _par()
    b.personaje.buffs[5] = {'fin': time.time() + 5, 'estado': 'inmovil'}
    assert pl.esta_quieto(b) and not pl.esta_quieto(b, ataque=True)
    b.personaje.buffs[6] = {'fin': time.time() + 5, 'estado': 'aturdido'}
    assert pl.esta_quieto(b, ataque=True)


def test_fire_trap_trae_su_quemadura():
    sec = combate.efecto_secundario(217)
    assert sec['hp_tick'] == -23 and sec['intervalo'] == 2 and sec['dur_ms'] == 10000 and sec['prob'] == 90
