"""Census Angel del Lyceum: cambio de faccion del personaje (server/cambio_faccion.py)."""
import pathlib
import struct
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import app
import cambio_faccion
import dialogos
import login


@pytest.fixture
def world(monkeypatch):
    p = login.Personaje(nivel=410, hp=100, hp_max=1000, mp=100, mp_max=1000,
                        stage=41, faction='Beasts')
    p.oro = 5_000_000
    p.checkpoint_stage, p.checkpoint_x, p.checkpoint_y = 29, 321, 97
    p.cambio_faccion_ts = 0
    packets, viajes = [], []
    s = SimpleNamespace(personaje=p, inventario=p.inventario, rol='mundo',
                        entity_id=p.entity_id, monstruos={}, usuario=None, muerto=False,
                        enviar=lambda *pk: packets.extend(pk),
                        enviar_inmediato=lambda *pk: packets.extend(pk))
    monkeypatch.setattr(app, '_stats_ses', lambda *a: b'')
    monkeypatch.setattr(app, '_refrescar', lambda *a, **kw: [])
    monkeypatch.setattr(app, '_cerrar_viaje', lambda *a: viajes.append(a))
    return SimpleNamespace(p=p, s=s, packets=packets, viajes=viajes,
                           server=app.Servidor.__new__(app.Servidor))


def _msg(world):
    return struct.unpack_from('<I', world.packets[-1], 2)[0]


def _elegir(world, mensaje):
    i = [o[0] for o in world.s.dlg_mapa['opciones']].index(mensaje)
    world.server.manejar(world.s, 0x000B, None, {'valor': dialogos.PRIMERA_OPCION + i}, 'test')


def test_beasts_se_pasa_a_aurora_pagando_y_viaja_al_cerrar(world):
    world.server.manejar(world.s, 0x0005, None, None, 'test', struct.pack('<IH', 49, 0))
    _elegir(world, 5831)                      # I wish to change faction.
    _elegir(world, 6218)
    assert _msg(world) == 5836                # Which faction do you want to join?
    assert 5839 not in [o[0] for o in world.s.dlg_mapa['opciones']]   # la suya (Beasts) no sale
    _elegir(world, 5837)                      # Aurora
    assert _msg(world) == 5844
    _elegir(world, 5865)                      # nivel 71+: 3.200.000
    assert _msg(world) == 5857                # "You are one of members of Aurora faction"
    assert world.p.oro == 5_000_000 - 3_200_000
    assert world.s.faccion_al_llegar == 'Aurora'
    assert world.s.viaje_pendiente == (3, (191, 182), 'Aurora')
    assert (world.p.checkpoint_stage, world.p.checkpoint_x) == (3, 191)
    assert 3541 not in world.p.inventario.values()
    world.server.manejar(world.s, 0x000B, None, {'valor': 1}, 'test')   # cerrar el cuadro
    assert world.viajes and world.viajes[0][2:] == (3, (191, 182), 'Aurora')


def _nodo_final(alineacion):
    import dialogos_mapa
    arbol = dialogos_mapa._arbol(41)
    return next(k for k, n in arbol.items()
                if any(a[0] == 20 and list(a[1]) == [3200000] for a in n.get('a', []))
                and any(a[0] == 29 and a[1][0] == alineacion for a in n.get('a', [])))


def test_una_vez_al_dia(world):
    world.p.cambio_faccion_ts = time.time() - 3600
    assert app._recorrer_dialogo_mapa(world.s, 'test', 41, _nodo_final(4))
    assert _msg(world) == cambio_faccion.MSG_ESPERA
    assert world.p.oro == 5_000_000 and world.p.faction == 'Beasts'
    assert not getattr(world.s, 'viaje_pendiente', None)


def test_pasadas_24_h_si(world):
    world.p.cambio_faccion_ts = time.time() - 25 * 3600
    assert app._recorrer_dialogo_mapa(world.s, 'test', 41, _nodo_final(4))
    assert world.s.faccion_al_llegar == 'Shadow'
    assert world.s.viaje_pendiente[0] == 26


def test_sin_oro_no_cambia(world):
    world.p.oro = 1000
    assert app._recorrer_dialogo_mapa(world.s, 'test', 41, _nodo_final(3))
    assert _msg(world) == cambio_faccion.MSG_SIN_ORO
    assert world.p.oro == 1000 and not getattr(world.s, 'faccion_al_llegar', None)


def test_en_liga_no_puede(world, monkeypatch):
    import eventos_mundo
    monkeypatch.setattr(eventos_mundo.ContextoSesion, 'tiene_guild', lambda self: True)
    world.server.manejar(world.s, 0x0005, None, None, 'test', struct.pack('<IH', 49, 0))
    _elegir(world, 5831)
    _elegir(world, 6218)
    _elegir(world, 5837)
    assert _msg(world) == 5856                # sal de tu liga primero
    assert not getattr(world.s, 'faccion_al_llegar', None)
