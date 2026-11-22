"""Cuatro pedidos del 05/11/2026:
- "vender gear de lvl 1 a 60 en 100 a 6k gold" (venta_nivel.py y el 收購價格 del parche); desde el 21/11/2026,
  todo lo que no se compra vale 100 por casilla
- "los aoe lvl 32 y 60 de las 4 clases de mago baja el cast time a 1 seg" (combate.CAST_RAPIDO)
- "que el dark cavern el minimapa salga negro y aumenta un 30% el ataque de los mob y jefe"
- "que los mob te persigan por todo el mapa" (en el Dark Cavern)
"""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import cliente_local  # noqa: E402
import combate  # noqa: E402
import instancia_oscura  # noqa: E402
import venta_nivel  # noqa: E402

IRON_SWORD_LV30, COPPER_SWORD_LV10 = 163, 148


RED_POTION = 2                 # se compra en las tiendas NPC: conserva su precio (si no, oro infinito)


def test_lo_que_no_se_compra_vale_100_por_casilla():
    """21/11/2026: "que todo lo que los npc compren valga 100 gold" (antes el gear 1..60 iba de 100 a 6.000)."""
    assert venta_nivel.PRECIO_FIJO == 100
    for it in (IRON_SWORD_LV30, COPPER_SWORD_LV10):
        assert venta_nivel.fijo(it)
        assert app._precio_venta(it) == 100
        assert app._ganancia_venta(it, 1) == app._ganancia_venta(it, 20) == 100


def test_lo_de_tienda_conserva_su_precio():
    assert RED_POTION in venta_nivel.items_comprables() and not venta_nivel.fijo(RED_POTION)
    p = app._precio_venta(RED_POTION)
    assert 0 < p < app._precio_compra(RED_POTION)
    assert app._ganancia_venta(RED_POTION, 11) == p * 11


def test_el_cliente_ensena_100():
    x = ('<root>\n  <道具 編號="%d" 價格="500" />\n  <道具 編號="%d" 收購價格="50" />\n'
         '  <道具 編號="%d" 收購價格="12" />\n</root>' % (IRON_SWORD_LV30, COPPER_SWORD_LV10, RED_POTION)).encode('utf-8')
    out = cliente_local._parchear_venta_por_nivel_xml_bytes(x).decode('utf-8')
    assert out.count('收購價格="100"') == 2 and '收購價格="12"' in out


def test_aoe_de_mago_en_1_segundo():
    for mid in (14, 17, 116, 118, 214, 217, 314, 317, 84, 390):
        assert combate.datos_magia(mid)['cast_time'] == 1000, mid
    x = '<root>\n\t<法術 編號="217" 前置時間="2000" 後置時間="2000" />\n</root>'.encode('utf-8')
    assert '前置時間="1000"' in cliente_local._parchear_cast_rapido_xml_bytes(x).decode('utf-8')


def test_dark_cavern_doble_de_ataque():
    b = NS(atk=100, matk=50)
    instancia_oscura.subir_ataque({1: b})
    assert (b.atk, b.matk) == (200, 100)


def test_dark_cavern_minimapa_negro():
    stage = (RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'stage.xml').read_text(encoding='utf-8')
    assert '雷達圖="smap\\900"' in stage
    assert (RAIZ / 'parches' / 'extras' / 'shape' / 'smap' / '900.shp').exists()
