"""Con configuracion.FLECHAS_INFINITAS = False, atacar con un arco/honda sin
flechas/bolitas en la mano izquierda solo dejaba de DESCONTAR la municion: el
golpe se procesaba igual, sin arma de verdad. El cliente avisa "sin
municiones" por su cuenta, pero el servidor igual mandaba el dano.
Reportado por el usuario: "Sigue dejando atacar sin bullet o arrow me dice
que no tengo municiones pero igual lanza el ataque"."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate as cb
import configuracion
import login


def _sesion_con_arco(monkeypatch, con_municion):
    monkeypatch.setattr(configuracion, 'FLECHAS_INFINITAS', False)
    p = login.Personaje(hp=20000, hp_max=100000, mp=50000, mp_max=150000)
    p.tile_x, p.tile_y = 100, 100
    m = cb.Monstruo(9999, 999999, 'Dummy', (100, 100))
    inventario = {3: 6}   # Bow (arco, 弓箭) en la mano derecha
    if con_municion:
        inventario[4] = 138   # Arrow
    packets = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario=inventario,
           monstruos={9999: m}, usuario=None, muerto=False, objetivo_actual=None,
           enviar=lambda *pk: packets.extend(pk), enviar_inmediato=lambda *pk: packets.extend(pk))
    return s, packets


def test_sin_municion_no_ataca(monkeypatch):
    s, packets = _sesion_con_arco(monkeypatch, con_municion=False)
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s, 0x0006, None, None, 'test',
                   struct.pack('<HI', cb.ATAQUE_NORMAL, 9999))
    assert not packets


def test_con_municion_ataca_normal(monkeypatch):
    s, packets = _sesion_con_arco(monkeypatch, con_municion=True)
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s, 0x0006, None, None, 'test',
                   struct.pack('<HI', cb.ATAQUE_NORMAL, 9999))
    assert packets


def test_con_flechas_infinitas_no_hace_falta_municion(monkeypatch):
    monkeypatch.setattr(configuracion, 'FLECHAS_INFINITAS', True)
    p = login.Personaje(hp=20000, hp_max=100000, mp=50000, mp_max=150000)
    p.tile_x, p.tile_y = 100, 100
    m = cb.Monstruo(9999, 999999, 'Dummy', (100, 100))
    packets = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={3: 6},
           monstruos={9999: m}, usuario=None, muerto=False, objetivo_actual=None,
           enviar=lambda *pk: packets.extend(pk), enviar_inmediato=lambda *pk: packets.extend(pk))
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s, 0x0006, None, None, 'test',
                   struct.pack('<HI', cb.ATAQUE_NORMAL, 9999))
    assert packets


def _magia(server, s, magia):
    server.manejar(s, 0x0006, None, None, 'test', struct.pack('<HI', magia, 9999))


def test_habilidad_de_disparo_sin_municion_no_sale(monkeypatch):
    """"que no me deje usar ninguna instance de bow o spell de bow si no tengo arrows"."""
    s, packets = _sesion_con_arco(monkeypatch, con_municion=False)
    _magia(app.Servidor.__new__(app.Servidor), s, 901)   # Basic Shot I
    assert len(packets) == 1 and b'arrows or bullets' in packets[0]


def test_buff_de_arco_sin_municion_si_sale(monkeypatch):
    """"solo los buff de bow": Accurate Song no pide flechas."""
    s, packets = _sesion_con_arco(monkeypatch, con_municion=False)
    _magia(app.Servidor.__new__(app.Servidor), s, 902)   # Accurate Song I
    assert not any(b'arrows or bullets' in pk for pk in packets)


def test_habilidad_de_disparo_con_municion_no_avisa(monkeypatch):
    s, packets = _sesion_con_arco(monkeypatch, con_municion=True)
    _magia(app.Servidor.__new__(app.Servidor), s, 901)
    assert not any(b'arrows or bullets' in pk for pk in packets)
