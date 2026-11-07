"""Cupid: "Set the place for your revival" fija donde se revive (07/11/2026: "cuando muera debo aparecer en el cupido que guarde")."""
import pathlib
import struct
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import app
import dialogos
import login


@pytest.fixture
def world(monkeypatch):
    p = login.Personaje(nivel=60, hp=100, hp_max=1000, mp=100, mp_max=1000, stage=41, faction='Aurora')
    p.tile_x, p.tile_y = 150, 70
    packets = []
    s = SimpleNamespace(personaje=p, inventario=p.inventario, rol='mundo', entity_id=p.entity_id, monstruos={},
                        usuario=None, muerto=False, enviar=lambda *pk: packets.extend(pk),
                        enviar_inmediato=lambda *pk: packets.extend(pk))
    monkeypatch.setattr(app, '_stats_ses', lambda *a: b'')
    monkeypatch.setattr(app, '_refrescar', lambda *a, **kw: [])
    return SimpleNamespace(p=p, s=s, packets=packets, server=app.Servidor.__new__(app.Servidor))


def test_cupid_del_lyceum_guarda_el_punto(world):
    world.server.manejar(world.s, 0x0005, None, None, 'test', struct.pack('<IH', 33, 0))
    print('dlg_ent', getattr(world.s, 'dlg_ent', None), 'mapa', getattr(world.s, 'dlg_mapa', None) and world.s.dlg_mapa.get('opciones'))
    # Segunda opcion: "Set the place for your revival." (5747)
    world.server.manejar(world.s, 0x000B, None, {'valor': dialogos.PRIMERA_OPCION + 1}, 'test')
    for _ in range(3):
        world.server.manejar(world.s, 0x000B, None, {'valor': 1}, 'test')
    assert (world.p.checkpoint_stage, world.p.checkpoint_x, world.p.checkpoint_y) == (41, 150, 70)


def test_cupid_tambien_si_el_cliente_manda_la_accion(world):
    world.server.manejar(world.s, 0x0005, None, None, 'test', struct.pack('<IH', 33, 0))
    world.server.manejar(world.s, 0x000B, None, {'valor': 1000030}, 'test')      # accion de "Set the place..."
    for _ in range(3):
        world.server.manejar(world.s, 0x000B, None, {'valor': 1}, 'test')
    assert (world.p.checkpoint_stage, world.p.checkpoint_x, world.p.checkpoint_y) == (41, 150, 70)


def test_acciones_de_la_linea():
    linea = dialogos.armar_linea(5745, 6, [5746, 5747, 5748], acciones=[1000029, 1000030, 0])[2:]
    assert dialogos.acciones_de(linea) == [1000029, 1000030, 0]
    assert dialogos.opcion_de_valor(linea, 1000030) == 5747 and dialogos.opcion_de_valor(linea, 5) is None
