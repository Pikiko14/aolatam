"""El album del mapa del tesoro cuenta fragmentos de CUALQUIER nivel (06/11/2026: "los mapas se pueden usar de
cualquier nivel, no pide la secuencia, puede usar 10 lvl 1")."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402


def test_diez_del_mismo_nivel_completan_el_album():
    p = NS(logros_cont={})
    for i in range(1, 11):
        assert app.anotar_fragmento(p) == (True, i)
    assert app.anotar_fragmento(p) == (False, 10)
    assert app.tesoro_hallados(p) == 10


def test_lo_anotado_antes_con_la_mascara_se_conserva():
    p = NS(logros_cont={app.CLAVE_TESORO: 0b101})          # dos fragmentos de la version anterior
    assert app.tesoro_hallados(p) == 2
    assert app.anotar_fragmento(p) == (True, 3)


def test_el_paquete_lleva_los_hallados(monkeypatch):
    monkeypatch.setattr(app, '_logros_datos', lambda ses: None)
    ses = NS(personaje=NS(logros_cont={app.CLAVE_TESORO_N: 7}))
    assert app._tesoro_paquete(ses)[2 + 12:2 + 16] == (7).to_bytes(4, 'little')
