"""El portal que se arma al terminar el paso salta cuando el cliente LLEGA, no el doble de tarde (17/11/2026: "demora
para entrar a la dungeon": se quedaba parado encima del tornado de Thorn Wasteland antes de cargar)."""
import pathlib
import sys
import types

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402


class _Bucle:
    def __init__(self):
        self.esperas = []

    def call_later(self, t, fn):
        self.esperas.append(t)
        return types.SimpleNamespace(cancel=lambda: None)


def test_la_espera_del_portal_es_lo_que_tarda_el_cliente_en_andar(monkeypatch):
    bucle = _Bucle()
    monkeypatch.setattr(app.asyncio, 'get_event_loop', lambda: bucle)
    monkeypatch.setattr(app, '_portal_en', lambda st, x, y: {'tile': [x, y], 'destino': 900, 'llegada': [14, 43]})
    monkeypatch.setattr(app, '_velocidad_de', lambda ses: 110)
    ses = types.SimpleNamespace(personaje=types.SimpleNamespace(stage=16), portal_armado=None, portal_pisado=None)
    app._armar_portal_al_llegar(ses, None, (130, 70), 10)
    # 10 casillas = 320 px a 110 * 2,5 = 275 px/s: 1,16 s (antes 10 * 25 / 110 = 2,27 s)
    assert abs(bucle.esperas[0] - 320 / 275) < 0.01
