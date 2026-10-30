"""El equipo con duracion (持續時間 en minutos: los "(3 days)", "(60 days)"...) solo traia
fecha si salia del mall, la Arena, Holy o un cofre. El resto ni ensenaba la cuenta atras ni
caducaba. Reportado: "Hay items que duran x dias armas, pd, etc pero no dicen la cuenta
atras de cuanto les queda"."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import arena_premios_compat
import inventario as iv
import login

YUKATA = 30691      # Blue Stripe Yukata (3 days): 4320 min, cuenta desde que se tiene
ANTILOPE = 61823    # Abysston Antelope (60 days): 86400 min, 使用計時 = cuenta al equiparlo
AHORA = 1_000_000.0


def _ses(inventario, mejoras=None):
    p = login.Personaje()
    p.mejoras = dict(mejoras or {})
    enviados = []
    return NS(personaje=p, inventario=dict(inventario), cantidades={}, instancias={},
              usuario=None, enviar=lambda *pk: enviados.extend(pk), enviados=enviados)


def test_los_datos_del_cliente():
    assert iv._col_item(YUKATA, '持續時間') == 4320
    assert iv._col_item(ANTILOPE, '持續時間') == 86400
    assert not app._cuenta_al_equipar(YUKATA) and app._cuenta_al_equipar(ANTILOPE)


def test_el_de_3_dias_cuenta_desde_que_se_tiene():
    s = _ses({25: YUKATA})
    assert app._items_con_tiempo(s, now=AHORA) == [25]
    meta = s.personaje.mejoras[25]
    assert meta == {'item_fin': AHORA + 4320 * 60, 'item_fin_id': YUKATA}
    assert s.enviados                                     # se refresca para ver la cuenta atras
    assert app._items_con_tiempo(s, now=AHORA + 5) == []  # no se le vuelve a poner


def test_el_de_usar_cuenta_solo_al_equiparlo():
    s = _ses({26: ANTILOPE})
    assert app._items_con_tiempo(s, now=AHORA) == []
    s.inventario = {app.RANURA_MONTURA: ANTILOPE}
    assert app._items_con_tiempo(s, now=AHORA) == [app.RANURA_MONTURA]


def test_no_pisa_la_fecha_del_mall():
    s = _ses({25: YUKATA}, {25: {'mall_fin': AHORA + 60, 'mall_item': YUKATA}})
    assert app._items_con_tiempo(s, now=AHORA) == []


def test_la_ficha_lleva_la_fecha_para_la_cuenta_atras():
    entrada = bytearray(120)
    struct.pack_into('<I', entrada, 9, YUKATA)
    marcada = iv.marcar_caducidad_holy(bytes(entrada), {'item_fin': AHORA + 3600, 'item_fin_id': YUKATA})
    assert struct.unpack_from('<I', marcada, 47)[0] == int(AHORA + 3600)


def test_al_pasar_el_plazo_se_retira(monkeypatch):
    s = _ses({25: YUKATA}, {25: {'item_fin': AHORA - 1, 'item_fin_id': YUKATA}})
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    arena_premios_compat.caducados(s, AHORA, campo_fin='item_fin', campo_item='item_fin_id')
    assert 25 not in s.inventario and 25 not in s.personaje.mejoras
