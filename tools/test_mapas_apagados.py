"""Expansiones apagadas: solo Mainland abierto (configuracion.MAPAS_APAGADOS)."""
import pathlib
import sys
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import clases
import configuracion
import travel_items


@pytest.fixture(autouse=True)
def _lista_real(mapas_apagados_configurados):
    pass


class Ses:
    def __init__(self, stage, tile=(100, 100)):
        self.personaje = types.SimpleNamespace(stage=stage, tile_x=tile[0], tile_y=tile[1],
                                               nombre='Prueba', char_id=1, entity_id=1001)
        self.packets = []
        self.puesto = None
        self.portal_pisado = None

    def enviar(self, *paquetes):
        self.packets.extend(paquetes)


@pytest.mark.parametrize('stage', [41, 3, 26, 29, 38, 21, 69, 128, 132, 57, 500, 501, 112])
def test_mainland_y_mapas_de_sistema_siguen_abiertos(stage):
    assert not configuracion.mapa_apagado(stage)


@pytest.mark.parametrize('stage', [88, 97, 120, 148, 157, 175, 198, 296, 308, 413, 422])
def test_expansiones_e_instancias_suyas_apagadas(stage):
    assert configuracion.mapa_apagado(stage)


def test_viajar_a_una_expansion_avisa_y_no_cambia_de_mapa():
    s = Ses(3)
    app._sincronizar_cambio_mapa(s, 88, 150, 100)
    assert s.personaje.stage == 3 and (s.personaje.tile_x, s.personaje.tile_y) == (100, 100)
    assert len(s.packets) == 1 and s.packets[0][:2] != b'\x0c\x00'


def test_el_tornado_cerrado_no_repite_el_aviso_mientras_se_esta_encima():
    s = Ses(27)
    por = {'tile': [10, 10], 'destino': 120, 'llegada': [5, 5]}
    app._viajar_por_portal(s, 'test', por)
    assert s.personaje.stage == 27 and s.portal_pisado == (10, 10)


def test_revivir_en_un_checkpoint_apagado_lleva_al_lyceum(monkeypatch):
    s = Ses(88)
    destinos = []
    monkeypatch.setattr(app, '_monstruos_de', lambda stage: {})
    monkeypatch.setattr(clases, 'cambiar_mapa', lambda stage: destinos.append(stage) or b'\x0c\x00')
    app._sincronizar_cambio_mapa(s, 88, 150, 100)
    assert destinos == [clases.STAGE_LYCEUM]
    assert (s.personaje.stage, s.personaje.tile_x, s.personaje.tile_y) == (
        clases.STAGE_LYCEUM, *clases.TILE_LYCEUM)


def test_pergaminos_y_marcas_no_llevan_a_una_expansion():
    with pytest.raises(travel_items.Rechazo, match='closed'):
        travel_items._point(88, 150, 100)
