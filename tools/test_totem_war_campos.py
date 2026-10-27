"""Totem War solo en configuracion.CAMPOS_TOTEM_WAR; el resto, totem decorativo."""
import importlib
import pathlib
import struct
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import configuracion
import totem_war


@pytest.fixture
def tw(monkeypatch):
    monkeypatch.setattr(configuracion, 'CAMPOS_TOTEM_WAR', frozenset({11, 16, 21}))
    yield importlib.reload(totem_war)
    monkeypatch.undo()
    importlib.reload(totem_war)


def test_solo_los_campos_elegidos_tienen_guerra(tw):
    assert set(tw.TOTEM_CAMPO) == {11, 16, 21}
    assert set(tw.TW_A_CAMPO) == {202, 205, 207}
    assert all(tw.es_mapa_tw(c) for c in (11, 16, 21))
    assert not any(tw.es_mapa_tw(c) for c in (8, 9, 12, 15, 17))


@pytest.mark.parametrize('campo,tile', [(8, (92, 174)), (9, (147, 100)), (12, (288, 11)),
                                        (15, (151, 156)), (17, (48, 95))])
def test_los_sacados_conservan_un_totem_decorativo_que_no_se_rompe(tw, campo, tile):
    m = tw.crear_totem(campo)
    assert tw.es_totem_decorativo(campo) and getattr(m, 'decorativo', False)
    assert (m.tile_x, m.tile_y) == tile


def test_los_campos_de_entrenamiento_siguen_igual(tw):
    assert all(tw.es_totem_decorativo(c) for c in (7, 20, 22, 28))


def test_los_sacados_no_llevan_dueno_en_el_paquete_de_territorios(tw):
    pkt = tw.paquete_territorios()
    n = struct.unpack_from('<H', pkt, 2)[0]
    filas = [struct.unpack_from('<III', pkt, 4 + 29 * i) for i in range(n)]
    for campo in (8, 9, 12, 15, 17, 200, 201, 203, 204, 206):
        assert (campo, 0, 0) in filas
