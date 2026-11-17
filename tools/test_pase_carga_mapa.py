"""El estado del Angel Pass no se pierde si llega mientras el cliente carga un mapa (17/11/2026: al entrar muerto la
ventana se quedaba en "Lv. 1" y sin misiones): session._filtrar_carga_mapa lo aplaza en vez de tirarlo."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import pase  # noqa: E402
from session import Session  # noqa: E402


class _Ses:
    rol = 'mundo'
    _filtrar_carga_mapa = Session._filtrar_carga_mapa

    def __init__(self):
        self.mapa_cargando = False
        self._mapa_ui_diferida = []


def test_el_estado_del_pase_se_aplaza_durante_la_carga_del_mapa():
    est = pase.Estado(1, {'nivel': 2, 'exp': 50})
    estado = pase.paquete_estado(est)
    cambio = (0x000C).to_bytes(2, 'little') + bytes(8)
    ses = _Ses()
    salen = ses._filtrar_carga_mapa((cambio, estado, pase.paquete_nivel(est)))
    assert salen == (cambio,)
    assert ses._mapa_ui_diferida == [estado, pase.paquete_nivel(est)]
