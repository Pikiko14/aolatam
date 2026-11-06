"""Cuatro pedidos del 05/11/2026:
- "vender gear de lvl 1 a 60 en 100 a 6k gold" (venta_nivel.py y el 收購價格 del parche)
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


def test_venta_por_nivel_de_100_a_6000():
    assert venta_nivel.VENTA_POR_NIVEL == ((1, 100), (60, 6000))
    assert venta_nivel.precio(IRON_SWORD_LV30) == 3000
    assert venta_nivel.precio(COPPER_SWORD_LV10) == 1000
    assert app._precio_venta(IRON_SWORD_LV30) == 3000


def test_el_cliente_ensena_el_precio_nuevo():
    x = ('<root>\n  <道具 編號="%d" 價格="500" />\n  <道具 編號="%d" 收購價格="50" />\n</root>'
         % (IRON_SWORD_LV30, COPPER_SWORD_LV10)).encode('utf-8')
    out = cliente_local._parchear_venta_por_nivel_xml_bytes(x).decode('utf-8')
    assert '收購價格="3000"' in out and '收購價格="1000"' in out


def test_aoe_de_mago_en_1_segundo():
    for mid in (14, 17, 116, 118, 214, 217, 314, 317, 84, 390):
        assert combate.datos_magia(mid)['cast_time'] == 1000, mid
    x = '<root>\n\t<法術 編號="217" 前置時間="2000" 後置時間="2000" />\n</root>'.encode('utf-8')
    assert '前置時間="1000"' in cliente_local._parchear_cast_rapido_xml_bytes(x).decode('utf-8')


def test_dark_cavern_30_por_ciento_mas_de_ataque():
    b = NS(atk=100, matk=50)
    instancia_oscura.subir_ataque({1: b})
    assert (b.atk, b.matk) == (130, 65)


def test_dark_cavern_minimapa_negro():
    stage = (RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'stage.xml').read_text(encoding='utf-8')
    assert '雷達圖="smap\\900"' in stage
    assert (RAIZ / 'parches' / 'extras' / 'shape' / 'smap' / '900.shp').exists()
