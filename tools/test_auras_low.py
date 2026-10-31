"""Auras "Low" propias: "creemos un Low Attack Angel Aura ... 70 de attack, 50 mattack y 15 rigor, lo mismo una
low def aura de 90 def 60 sdef 15 agy" y la de "200 hp 150 mp, 5% ms y 2000 de weight"."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import bolsas
import cliente_local


def _buff(item):
    mid, entrada, dur = bolsas.buff_de(item, 0)
    return mid, entrada, dur


def test_low_attack():
    mid, e, dur = _buff(89058)
    assert (mid, dur) == (23401, 10800 * 1000)
    assert (e['atk'], e['matk'], e['hit']) == (70, 50, 15)


def test_low_defense():
    _, e, _ = _buff(89059)
    assert (e['def'], e['mdef'], e['eva']) == (90, 60, 15)


def test_low_exu():
    _, e, _ = _buff(89060)
    assert (e['hp_bonus'], e['mp_bonus'], e['carga'], e['mag']['move_speed_bonus']) == (200, 150, 2000, 5)
    assert 'carta' not in e


def test_la_exu_original_no_es_una_carta_y_suma_su_carga():
    _, e, _ = _buff(66376)
    assert 'carta' not in e and e['carga'] == 3000
    assert bolsas.cartas_pisadas({1937: {'de_item': 4526, 'fabricacion_pct': 65, 'carta': 'fabricacion_pct'}},
                                 21089, e) == []


def test_los_xml_del_cliente_llevan_items_y_hechizos():
    item9 = cliente_local._parchear_item9_xml_bytes(b'<root>\r\n</root>').decode('utf-8')
    magia = cliente_local._parchear_magias_propias_xml_bytes(b'<root>\r\n</root>').decode('utf-8')
    for iid, icono, nombre, mid, *_ in cliente_local.AURAS_LOW:
        assert '編號="%d" 原型介面="%d" 基本名稱="%s"' % (iid, icono, nombre) in item9
        assert '常駐法術="%d"' % mid in item9
        assert '編號="%d"' % mid in magia
    assert cliente_local._parchear_magias_propias_xml_bytes(magia.encode('utf-8')) == magia.encode('utf-8')
