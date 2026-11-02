"""La ventana propia de la subasta (server/subasta_ventana.py) sobre los datos de subastas.py."""
import pathlib
import re
import struct
import sys
from types import SimpleNamespace

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import subasta_ventana as sv
import subastas

ITEM = 3093            # Ruby (gema apilable)
ARMA = 1513


@pytest.fixture(autouse=True)
def base_propia(tmp_path, monkeypatch):
    monkeypatch.setattr(subastas, 'DB_PATH', tmp_path / 'subastas.db')
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)


def _ses(char_id, nombre, inventario, oro=0, canal=True):
    enviados = []
    p = SimpleNamespace(char_id=char_id, nombre=nombre, entity_id=char_id, stage=subastas.STAGE, tile_x=10,
                        tile_y=10, mejoras={}, mascotas={}, mascota=None, oro=oro, buffs={})
    s = SimpleNamespace(personaje=p, inventario=dict(inventario), cantidades={}, usuario=None, oro=oro,
                        enviados=enviados, canal_lua=1 if canal else 0)
    s.enviar = lambda *pk: enviados.extend(pk)
    s.volcar = lambda: None
    return s


def _cmd(cmd, a, b=0):
    return struct.pack('<BII', cmd, a, b)


def _lua(pk):
    assert pk[:2] == b'\xa0\x01' and pk.endswith(b'\0')
    return pk[2:-1].decode('latin1')


def _ultima_lista(ses):
    return next(_lua(p) for p in reversed(ses.enviados) if p[:2] == b'\xa0\x01' and b'SubastaLista(' in p)


def _publicar(ses, ranura, item, cant, precio):
    ses.cantidades[ranura] = cant
    subastas.publicar(ses, [{'ranura': ranura, 'item_id': item, 'cantidad': cant, 'precio': precio}])


def test_el_saludo_marca_al_cliente_con_el_canal():
    s = _ses(1, 'A', {}, canal=False)
    assert _lua(sv.saludo()) == 'game.netcommand2(160, 1, 0)'
    assert not sv.tiene_ventana(s)
    assert sv.procesar(s, _cmd(sv.CMD_SALUDO, 1))
    assert sv.tiene_ventana(s)


def test_sin_saludo_la_ventana_no_contesta():
    s = _ses(1, 'A', {}, canal=False)
    assert sv.procesar(s, _cmd(sv.CMD_BUSCAR, 0, 1)) and s.enviados == []


def test_los_otros_usos_del_002f_no_son_suyos():
    assert not sv.procesar(_ses(1, 'A', {}), struct.pack('<BII', 11, 20, 1))


def test_abrir_manda_su_lua_y_los_filtros_hasta_el_nivel_60():
    s = _ses(1, 'A', {})
    lua, llamada = (_lua(p) for p in sv.abrir(s))
    assert 'function SubastaLista' in lua and 'function OnSubastaAceptar' in lua
    assert llamada.startswith('SubastaAbrir({"All","Headwear"')
    assert '"Lv 51-60"}' in llamada and 'Lv 61' not in llamada


def test_buscar_pagina_de_diez_en_diez():
    v = _ses(10, 'Vende', {20 + i: ITEM for i in range(12)})
    for i in range(12):
        _publicar(v, 20 + i, ITEM, 1, 100 + i)
    c = _ses(11, 'Compra', {})
    sv.procesar(c, _cmd(sv.CMD_BUSCAR, 0, 2))
    lista = _ultima_lista(c)
    assert lista.startswith('SubastaLista(0,2,2,{{')
    assert len(re.findall(r'\{\d+,"Ruby"', lista)) == 2           # 12 = 10 + 2


def test_mine_solo_ensena_lo_propio():
    v = _ses(10, 'Vende', {20: ITEM})
    _publicar(v, 20, ITEM, 3, 500)
    otro = _ses(12, 'Otro', {20: ARMA})
    _publicar(otro, 20, ARMA, 1, 9000)
    sv.procesar(v, _cmd(sv.CMD_BUSCAR, sv.MODO_MIO << 16, 1))
    lista = _ultima_lista(v)
    assert '"Vende"' in lista and '"Otro"' not in lista


def test_los_filtros_de_categoria_y_nivel():
    import inventario as iv
    cat = next(i for i, (_, c) in enumerate(sv.CATEGORIAS) if c and c != 'resto' and iv.categoria_item(ARMA) in c)
    assert sv.pasa_filtro(ARMA, cat, 0)
    assert not sv.pasa_filtro(ITEM, cat, 0)
    assert sv.pasa_filtro(ITEM, len(sv.CATEGORIAS) - 1, 0) or iv.categoria_item(ITEM) in sv._CON_CATEGORIA
    nivel = max(1, sv._nivel_de(ARMA))
    dentro = next(i for i, (_, lo, hi) in enumerate(sv.NIVELES) if lo and lo <= nivel <= hi) if nivel <= 60 else None
    if dentro:
        assert sv.pasa_filtro(ARMA, 0, dentro)
        assert not sv.pasa_filtro(ARMA, 0, dentro % (len(sv.NIVELES) - 1) + 1)


def test_comprar_desde_la_ventana_cobra_entrega_y_refresca():
    v = _ses(10, 'Vende', {20: ITEM})
    _publicar(v, 20, ITEM, 5, 1000)
    fid = subastas.listado()[0]['id']
    c = _ses(11, 'Compra', {}, oro=10_000)
    sv.procesar(c, _cmd(sv.CMD_COMPRAR, fid, 3))
    assert c.oro == 7000 and app._cant_de(c, next(r for r, it in c.inventario.items() if it == ITEM)) == 3
    assert subastas.listado()[0]['cantidad'] == 2
    assert 'SubastaAviso("Done' in _lua(c.enviados[-1])


def test_retirar_no_toca_lo_ajeno():
    v = _ses(10, 'Vende', {20: ARMA})
    _publicar(v, 20, ARMA, 1, 1000)
    fid = subastas.listado()[0]['id']
    c = _ses(11, 'Compra', {}, oro=10_000)
    sv.procesar(c, _cmd(sv.CMD_RETIRAR, fid))
    assert c.oro == 10_000 and ARMA not in c.inventario.values() and len(subastas.listado()) == 1
    sv.procesar(v, _cmd(sv.CMD_RETIRAR, fid))
    assert ARMA in v.inventario.values() and subastas.listado() == []


def test_soltar_un_objeto_prepara_la_venta_con_su_nombre_y_cantidad():
    v = _ses(10, 'Vende', {23: ITEM})
    v.cantidades[23] = 5
    sv.procesar(v, _cmd(sv.CMD_PREPARAR, 23, ITEM))
    assert _lua(v.enviados[-1]) == 'SubastaPreparada(23,%d,"Ruby",5)' % ITEM


def test_si_la_ranura_no_cuadra_busca_el_objeto_en_la_mochila():
    v = _ses(10, 'Vende', {25: ITEM})
    v.cantidades[25] = 2
    sv.procesar(v, _cmd(sv.CMD_PREPARAR, 23, ITEM))
    assert _lua(v.enviados[-1]).startswith('SubastaPreparada(25,')


def test_no_se_vende_lo_intransferible_ni_lo_equipado(monkeypatch):
    import house_services
    import inventario as iv
    v = _ses(10, 'Vende', {23: ITEM, 3: ARMA})
    monkeypatch.setattr(house_services, 'xml_rows', lambda n: {ITEM: {'不可交易': '是'}})
    sv.procesar(v, _cmd(sv.CMD_PREPARAR, 23, ITEM))
    assert 'cannot be traded' in _lua(v.enviados[-1])
    if iv.es_equipo(3):
        sv.procesar(v, _cmd(sv.CMD_PREPARAR, 3, ARMA))
        assert 'Take it off' in _lua(v.enviados[-1])


def test_publicar_desde_la_ventana_saca_de_la_mochila_y_sale_en_mine():
    v = _ses(10, 'Vende', {23: ITEM})
    v.cantidades[23] = 5
    sv.procesar(v, _cmd(sv.CMD_PUBLICAR, (23 << 16) | 3, 1500))
    fila = subastas.listado()[0]
    assert (fila['item_id'], fila['cantidad'], fila['precio'], fila['vendedor']) == (ITEM, 3, 1500, 'Vende')
    assert app._cant_de(v, 23) == 2
    textos = [_lua(p) for p in v.enviados if p[:2] == b'\xa0\x01']
    assert textos[-2].startswith('SubastaLista(1,1,1,{{') and textos[-1].startswith('SubastaPublicada(')


def test_sin_precio_no_se_publica():
    v = _ses(10, 'Vende', {23: ITEM})
    v.cantidades[23] = 5
    sv.procesar(v, _cmd(sv.CMD_PUBLICAR, (23 << 16) | 3, 0))
    assert subastas.listado() == [] and 'price' in _lua(v.enviados[-1])


def test_cheap_ordena_por_precio_y_cada_fila_lleva_su_item_y_el_total():
    v = _ses(10, 'Vende', {20: ITEM, 21: ITEM, 22: ITEM})
    for r, precio in ((20, 900), (21, 100), (22, 500)):
        _publicar(v, r, ITEM, 1, precio)
    c = _ses(11, 'Compra', {})
    sv.procesar(c, _cmd(sv.CMD_BUSCAR, sv.ORDEN_BARATO << 24, 1))
    lista = _ultima_lista(c)
    assert re.findall(r'"(\d+)","Vende",%d' % ITEM, lista) == ['100', '500', '900']
    assert lista.endswith(',3)')
    sv.procesar(c, _cmd(sv.CMD_BUSCAR, 0, 1))
    assert re.findall(r'"(\d+)","Vende"', _ultima_lista(c)) == ['500', '100', '900']


def test_el_saludo_define_el_boton_de_la_barra_y_el_boton_abre_la_ventana():
    s = _ses(1, 'A', {}, canal=False)
    sv.procesar(s, _cmd(sv.CMD_SALUDO, 1))
    assert _lua(s.enviados[-1]).startswith('function OnCommandSubasta(')
    assert 'game.netcommand2(%d, 0, 0)' % sv.CMD_ABRIR in _lua(s.enviados[-1])
    sv.procesar(s, _cmd(sv.CMD_ABRIR, 0))
    assert _lua(s.enviados[-1]).startswith('SubastaAbrir(')


def test_el_diagnostico_de_soltar_solo_se_anota():
    s = _ses(1, 'A', {})
    assert sv.procesar(s, _cmd(sv.CMD_DIAG, 1, 0)) and s.enviados == []
