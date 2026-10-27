"""Los tests de viajes, portales, instancias y Totem War recorren todo el
juego: corren con todos los mapas abiertos y los ocho campos en guerra.
test_mapas_apagados pide la lista configurada con su fixture."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import configuracion

_CONFIGURADOS = configuracion.MAPAS_APAGADOS
configuracion.MAPAS_APAGADOS = frozenset()
configuracion.CAMPOS_TOTEM_WAR = frozenset({8, 9, 11, 12, 15, 16, 17, 21})


@pytest.fixture
def mapas_apagados_configurados(monkeypatch):
    monkeypatch.setattr(configuracion, 'MAPAS_APAGADOS', _CONFIGURADOS)
    return _CONFIGURADOS
