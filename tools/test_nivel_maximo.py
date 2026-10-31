"""El tope de nivel del personaje sale de configuracion.NIVEL_MAXIMO_PERSONAJE ("limita el lvl del juego a
lvl 60 que sea una variable en config")."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate
import configuracion


def test_el_tope_es_el_de_configuracion(monkeypatch):
    monkeypatch.setattr(configuracion, 'NIVEL_MAXIMO_PERSONAJE', 60)
    assert combate.nivel_maximo() == 60
    monkeypatch.setattr(configuracion, 'NIVEL_MAXIMO_PERSONAJE', 80)
    assert combate.nivel_maximo() == 80


def test_no_pasa_del_fin_de_level_xml(monkeypatch):
    monkeypatch.setattr(configuracion, 'NIVEL_MAXIMO_PERSONAJE', 9999)
    assert combate.nivel_maximo() == 471
