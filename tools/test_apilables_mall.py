"""Las Lucky Bags del Item Mall se venden de 11 y de 110: el cliente tiene que
apilarlas o la Store Cabinet pide una casilla por bolsa."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import cliente_local


def test_las_bolsas_del_mall_se_apilan():
    ids = cliente_local.apilables_del_mall()
    assert {11767, 11963, 4978, 4979}.issubset(ids)   # 8531 Lucky Bag (Boys) la quito el usuario


def test_el_parche_pone_y_corrige_el_campo():
    xml = ('<道具 編號="11767" 基本名稱="Lucky Bag" />\n'
           '<道具 編號="11963" 可堆疊="否" 基本名稱="Bag" />\n'
           '<道具 編號="1" 基本名稱="Otro" />').encode('utf-8')
    out = cliente_local._parchear_apilables_xml_bytes(xml, {11767, 11963}).decode('utf-8')
    assert '<道具 編號="11767" 基本名稱="Lucky Bag" 可堆疊="是" />' in out
    assert '編號="11963" 可堆疊="是"' in out
    assert '<道具 編號="1" 基本名稱="Otro" />' in out
