"""El peso de la mochila se actualiza al cambiar una casilla (17/11/2026: "si dropeo algun item, uso algun lucky bag y
obtengo 1 item no se actualiza el weight"): session.Session.enviar anade el 0x0042 si va un 0x001B y el peso cambio."""
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402,F401  (engancha Session.paquete_peso)
import inventario as inv  # noqa: E402
from session import Session  # noqa: E402


class _Ses:
    rol = 'mundo'
    enviar = Session.enviar
    paquete_peso = staticmethod(app._paquete_peso)

    def __init__(self, bolsa):
        self.personaje = type('P', (), {'char_id': 1, 'habilidades': None, 'hp': 1, 'hp_max': 1, 'mp': 1, 'mp_max': 1,
                                        'buffs': None, 'mejoras': {}, 'mascotas': {}, 'sp': 0})()
        self.inventario = bolsa
        self.oro = 0
        self.mandado = []

    def _filtrar_carga_mapa(self, s):
        self.mandado.append(tuple(s))
        return ()


def _opcodes(ses):
    return [struct.unpack_from('<H', m)[0] for m in ses.mandado[-1]]


def test_al_tirar_algo_se_manda_el_peso_nuevo_y_solo_si_cambio():
    pocion = next(i for i in range(2, 200) if inv.peso_de(i) > 0)
    ses = _Ses({41: pocion, 42: pocion})
    ses.enviar(inv.vaciar_ranura(1, 99))
    assert 0x0042 in _opcodes(ses)                 # la primera vez no se habia mandado nunca
    ses.enviar(inv.vaciar_ranura(1, 99))
    assert 0x0042 not in _opcodes(ses)             # el peso no cambio
    ses.inventario.pop(42)
    ses.enviar(inv.vaciar_ranura(1, 42))
    assert 0x0042 in _opcodes(ses)                 # se tiro algo: va el peso nuevo


def test_al_cargar_un_mapa_el_peso_espera():
    pocion = next(i for i in range(2, 200) if inv.peso_de(i) > 0)
    ses = _Ses({41: pocion})
    ses.mapa_cargando = True
    assert app._paquete_peso(ses) is None and getattr(ses, 'peso_enviado', None) is None
