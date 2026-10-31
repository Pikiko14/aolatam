"""La mascota sigue al dueño a su paso, tambien montado."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app


def test_va_al_paso_del_dueno(monkeypatch):
    monkeypatch.setattr(app, '_velocidad_de', lambda ses: 110)
    assert app._velocidad_seguir_pet(None, 105, 2) == 110
    assert app._velocidad_seguir_pet(None, 140, 2) == 140


def test_montado_no_se_queda_atras(monkeypatch):
    monkeypatch.setattr(app, '_velocidad_de', lambda ses: 275)
    assert app._velocidad_seguir_pet(None, 105, 3) == 275
    assert app._velocidad_seguir_pet(None, 105, 10) == int(275 * 1.2)   # alcanza sin correr de mas
