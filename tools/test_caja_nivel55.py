"""Caja propia de nivel 55 (item 89055) para los monstruos de Dark Cavern: un item al azar de
nivel 55 de cualquier clase (arma, capa, collar o robot). Pedido del usuario: "genera tu el
item que de cualquier item lvl 55 ... arma, armadura, accesorio y robots"."""
import pathlib
import sqlite3
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import bolsas
import cliente_local as cl
import inventario as iv

CAJA = cl.ITEM_CAJA_55
CONTENIDO = {iid for iid, _ in cl.CAJA_55_CONTENIDO}


def test_el_contenido_es_todo_de_nivel_55():
    con = sqlite3.connect(str(RAIZ / 'corpus' / 'content.db'))
    try:
        for iid in CONTENIDO:
            fila = iv.fila_item(con, '"等級限制", "持續時間"', iid)
            assert fila and str(fila[0]) == '55', iid
            assert not fila[1], iid                      # nada de prueba ni con tiempo
    finally:
        con.close()


def test_la_fila_del_cliente_se_mete_una_sola_vez():
    base = '<root>\r\n    <道具 編號="80001" />\r\n</root>'.encode('utf-8')
    una = cl._parchear_item9_xml_bytes(base)
    assert una.count(('編號="%d"' % CAJA).encode('utf-8')) == 1
    assert '83266'.encode() in una
    assert cl._parchear_item9_xml_bytes(una) == una


def test_se_abre_y_da_algo_del_contenido():
    cl.registrar_medalla_en_servidor()      # lo mismo que hace el servidor al arrancar
    assert bolsas.es_bolsa(CAJA)
    for _ in range(40):
        item, cantidad = bolsas.abrir(CAJA)
        assert item in CONTENIDO and cantidad == 1
