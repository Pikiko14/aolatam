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


def test_el_golpe_basico_no_sale_justo_despues_de_una_habilidad(monkeypatch):
    """"si soy bow y uso 1 turno de ataque ejemplo lanzo poder, no debe lanzar la flecha basica"."""
    s, packets = _sesion_con_arco(monkeypatch, con_municion=True)
    s.personaje.habilidades = [(17, 10, 0)]
    s.volcar = lambda *a, **k: None
    server = app.Servidor.__new__(app.Servidor)
    try:
        _magia(server, s, 901)                               # Basic Shot I
    except AttributeError:
        pass                                                 # el resto del lanzamiento pide una sesion entera
    assert getattr(s, 'ultimo_golpe', 0) > 0
    packets.clear()
    server.manejar(s, 0x0006, None, None, 'test', struct.pack('<HI', cb.ATAQUE_NORMAL, 9999))
    assert not packets


def test_el_monstruo_contesta_ya_y_otro_golpe_no_le_reinicia_el_reloj(monkeypatch):
    """"los mob cuando los comienzo atacar demoran en darme target"."""
    s, _ = _sesion_con_arco(monkeypatch, con_municion=True)
    m = s.monstruos[9999]
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s, 0x0006, None, None, 'test', struct.pack('<HI', cb.ATAQUE_NORMAL, 9999))
    assert m.en_combate_con == s.entity_id and m.ultimo_ataque == 0
    m.ultimo_ataque = 123.0                                   # la IA ya le hizo pegar
    s.ultimo_golpe = 0
    server.manejar(s, 0x0006, None, None, 'test', struct.pack('<HI', cb.ATAQUE_NORMAL, 9999))
    assert m.ultimo_ataque == 123.0


def test_al_primer_golpe_el_monstruo_no_espera_la_pausa_del_paseo(monkeypatch):
    """Paseando, le quedaba la pausa aleatoria (hasta 0,9 s) antes de salir a por el jugador."""
    import time
    s, _ = _sesion_con_arco(monkeypatch, con_municion=True)
    m = s.monstruos[9999]
    ahora = time.time()
    m.proximo_paso, m.llega_paseo = ahora + 5.0, ahora + 0.2     # andando 0,2 s mas y luego 4,8 s de pausa
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s, 0x0006, None, None, 'test', struct.pack('<HI', cb.ATAQUE_NORMAL, 9999))
    assert m.proximo_paso <= ahora + 0.3


def test_el_tramo_del_monstruo_dura_lo_que_dibuja_el_cliente():
    # 3 casillas a velocidad 75: 96 px a 187,5 px/s = 0,51 s (antes se contaban 1,28 s).
    assert abs(cb.segundos_de_tramo(3, 75) - 0.512) < 0.01
