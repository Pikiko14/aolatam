"""Sneak vuelve transparente al asesino: 0x0185 con el bit 潛行 (0x40 de la palabra alta), a el y a los demas del mapa;
romperlo o caducar lo quita, y quien llega despues tambien lo recibe (07/11/2026: "el sneak no me vuelve invisible")."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import login  # noqa: E402
import presencia  # noqa: E402

SNEAK = 5426


def _ses(nombre, recibido):
    p = login.Personaje(hp=5000, hp_max=5000, mp=5000, mp_max=5000)
    p.nombre, p.stage, p.tile_x, p.tile_y = nombre, 41, 100, 100
    p.habilidades = [(30, 10, 0)]                       # ShadowBlade
    return NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, cantidades={}, monstruos={},
              usuario=None, muerto=False, sp=5000,
              enviar=lambda *pk: recibido.extend(pk), enviar_inmediato=lambda *pk: recibido.extend(pk))


def _sigilos(paquetes):
    return [struct.unpack_from('<III', x, 2) for x in paquetes if len(x) == 14 and x[:2] == b'\x85\x01']


def test_sneak_manda_el_bit_y_romperlo_lo_quita(monkeypatch):
    pend = []
    monkeypatch.setattr(app.asyncio, 'get_event_loop', lambda: NS(call_later=lambda t, f: pend.append(f),
                                                              call_soon=lambda f: pend.append(f)))
    monkeypatch.setattr(app, '_otorgar_skill_exp', lambda *a, **kw: [])
    monkeypatch.setattr(app, '_stats_ses', lambda *a: b'')
    monkeypatch.setattr(app, '_receptores_de_buff', lambda *a: ([], True))
    presencia._POR_MAPA.clear()
    a_ve, b_ve = [], []
    a, b = _ses('Aegon', a_ve), _ses('Zetha', b_ve)
    presencia._POR_MAPA[41] = [a, b]
    a._mapa_presencia = b._mapa_presencia = 41
    srv = app.Servidor.__new__(app.Servidor)
    srv.manejar(a, 0x0006, None, None, 't', struct.pack('<HI', SNEAK, a.personaje.entity_id))
    assert app._sigilo_activo(a)
    assert (a.personaje.entity_id, 0, 0x40) in _sigilos(a_ve)                  # el, con su id
    assert (presencia.entidad_de(a), 0, 0x40) in _sigilos(b_ve)               # los demas, con el publico
    nuevo = []
    presencia._presentar(a, NS(personaje=b.personaje, enviar=nuevo.extend, enviar_inmediato=lambda *pk: nuevo.extend(pk)))
    assert (presencia.entidad_de(a), 0, 0x40) in _sigilos(nuevo)              # el que llega despues
    a_ve.clear(); b_ve.clear()
    app._romper_sigilo(a, 't', 'por atacar')
    assert (a.personaje.entity_id, 0, 0) in _sigilos(a_ve)
    assert (presencia.entidad_de(a), 0, 0) in _sigilos(b_ve)


def test_conserva_los_demas_bits():
    s = NS(flags_magicos=(0x04000000, 0x1))
    assert struct.unpack_from('<III', app._paquete_sigilo(s, 7, True), 2) == (7, 0x04000000, 0x41)
    assert struct.unpack_from('<III', app._paquete_sigilo(s, 7, False), 2) == (7, 0x04000000, 0x1)
