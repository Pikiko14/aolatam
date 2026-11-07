"""Al cambiar de rama de armadura (Mantle -> Vestment) se quita a la mochila lo que la rama vieja permitia llevar; si
no cabe, el cambio no se hace (07/11/2026): "Cuando me cambio de Mantle a Vestment o Garment sigo manteniendo el set
puesto y la defensa ... si no tiene el espacio falla el cambio de skill de la armadura"."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import inventario  # noqa: E402
import login  # noqa: E402

ARMADURA_MANTLE = 144      # 衣服, 技能限制1 = 32 (Mantle), 技能等限 4: va en la casilla 2
MANTLE, VESTMENT, SWORD = 32, 34, 9


def _ses(bolsa):
    p = login.Personaje(hp=500, hp_max=500, mp=300, mp_max=300)
    p.nivel = 10
    p.habilidades = [(SWORD, 10, 0), (MANTLE, 10, 0)]
    recibido = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario=dict(bolsa), cantidades={},
           usuario=None, muerto=False, monstruos={},
           enviar=lambda *pk: recibido.extend(pk), enviar_inmediato=lambda *pk: recibido.extend(pk))
    return s, recibido


def _cambiar(s, fuera, dentro):
    srv = app.Servidor.__new__(app.Servidor)
    srv.manejar(s, 0x002F, None, None, 't', struct.pack('<BII', 10, fuera, dentro))


def test_la_armadura_de_mantle_va_a_la_mochila_al_pasar_a_vestment():
    assert inventario.falta_requisito(ARMADURA_MANTLE, 10, [(MANTLE, 10, 0)]) is None
    s, _ = _ses({2: ARMADURA_MANTLE})
    _cambiar(s, MANTLE, VESTMENT)
    assert [h[0] for h in s.personaje.habilidades] == [SWORD, VESTMENT]
    assert 2 not in s.inventario
    assert ARMADURA_MANTLE in [it for r, it in s.inventario.items() if not inventario.es_equipo(r)]


def test_sin_hueco_en_la_mochila_el_cambio_falla_y_no_se_toca_nada():
    s, _ = _ses({2: ARMADURA_MANTLE})
    for r in app._ranuras_bolsa(s.inventario):
        if not inventario.es_equipo(r):
            s.inventario.setdefault(r, 20141)        # mochila llena
    antes = dict(s.inventario)
    _cambiar(s, MANTLE, VESTMENT)
    assert [h[0] for h in s.personaje.habilidades] == [SWORD, MANTLE]
    assert s.inventario == antes
