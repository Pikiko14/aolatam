"""Tras una habilidad de ataque, un solo golpe basico (05/11/2026).

"analiza porque despues de usar un ataque se queda lanzando basicos??, los basicos solo se deben lanzar si le doy
click al mob eso si sin tener una habilidad marcada, o si uso 1 skill solo debe pegar 1 basico".
El cliente sigue mandando el 0x0016 accion 0x0C cada ~1,5 s despues de la habilidad (hasta 10 seguidos en las
grabaciones, sin clic de por medio). El clic al mob (0x0005) deja los basicos libres otra vez.
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import combate as cb  # noqa: E402
import login  # noqa: E402

BASIC_BEATING = 701   # Basic Beating I (Axe), habilidad de ataque


class Servidor(app.Servidor):
    """Cuenta los golpes basicos que llegan a ejecutarse (el 0x0C los pasa como 0x0006 ATAQUE_NORMAL)."""
    basicos = 0

    def manejar(self, ses, op, m, d, addr, cuerpo):
        if op == 0x0006 and struct.unpack_from('<H', cuerpo)[0] == cb.ATAQUE_NORMAL:
            Servidor.basicos += 1
        return super().manejar(ses, op, m, d, addr, cuerpo)


def _montar(monkeypatch):
    reloj = [1000.0]
    monkeypatch.setattr(app.time, 'time', lambda: reloj[0])
    p = login.Personaje(hp=20000, hp_max=100000, mp=50000, mp_max=150000)
    p.tile_x, p.tile_y = 100, 100
    p.habilidades = [(10, 30, 0), (12, 1, 0)]       # Axe + Enhance
    mob = cb.Monstruo(9999, 999999, 'Dummy', (100, 100))
    mob.hp = mob.hp_max = 10 ** 9
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={3: 19832}, cantidades={},
           monstruos={9999: mob}, usuario=None, muerto=False, objetivo_actual=None, sp=5000,
           enviar=lambda *pk: None, enviar_inmediato=lambda *pk: None)
    srv = Servidor.__new__(Servidor)
    Servidor.basicos = 0

    def basico():
        reloj[0] += 3.0                                 # siempre fuera de la cadencia
        srv.manejar(s, 0x0016, None, None, 't', struct.pack('<BI', 0x0C, 9999))

    def clic():
        srv.manejar(s, 0x0005, None, None, 't', struct.pack('<IH', 9999, 0))

    def skill():
        reloj[0] += 5.0
        srv.manejar(s, 0x0006, None, None, 't', struct.pack('<HI', BASIC_BEATING, 9999))

    return basico, clic, skill


def test_con_clic_los_basicos_siguen(monkeypatch):
    basico, clic, _ = _montar(monkeypatch)
    clic()
    for _ in range(5):
        basico()
    assert Servidor.basicos == 5


def test_tras_una_habilidad_ningun_basico_hasta_el_clic(monkeypatch):
    # "el golpe basico solo sale al dar clic" (07/11/2026): antes se dejaba pasar uno.
    basico, clic, skill = _montar(monkeypatch)
    clic()
    skill()
    for _ in range(6):                                  # el cliente sigue pidiendolos
        basico()
    assert Servidor.basicos == 0
    clic()                                              # clic al mob sin habilidad: vuelven
    basico()
    basico()
    assert Servidor.basicos == 2
