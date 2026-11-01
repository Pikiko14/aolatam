"""La casa de subastas con las ventanas del puesto de venta (subastas.py)."""
import pathlib
import struct
import sys
from types import SimpleNamespace

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import subastas

ITEM = 3093            # Ruby (gema apilable)
ARMA = 1513            # un arma: lleva sus mejoras


@pytest.fixture(autouse=True)
def base_propia(tmp_path, monkeypatch):
    monkeypatch.setattr(subastas, 'DB_PATH', tmp_path / 'subastas.db')


def _ses(char_id, nombre, inventario, oro=0, cerca=True):
    enviados = []
    x, y = subastas.CASILLA if cerca else (10, 10)
    p = SimpleNamespace(char_id=char_id, nombre=nombre, entity_id=char_id, stage=subastas.STAGE, tile_x=x,
                        tile_y=y, mejoras={}, mascotas={}, mascota=None, oro=oro, buffs={})
    s = SimpleNamespace(personaje=p, inventario=dict(inventario), cantidades={}, usuario=None, oro=oro,
                        enviados=enviados)
    s.enviar = lambda *pk: enviados.extend(pk)
    s.volcar = lambda: None
    return s


def _compra(eid, inst8, cant=1):
    return struct.pack('<II', eid, 1) + struct.pack('<8sI', inst8, cant)


def test_el_subastador_solo_sale_en_el_lyceum_con_su_cartel():
    pk = subastas.presentacion(subastas.STAGE)
    assert pk[0][:2] == b'\x01\x00' and b'Auction House' in pk[0]
    assert pk[1] == struct.pack('<HIIBBH', 0x000A, subastas.ENTIDAD, 0, 10, subastas.ESTILO, 0)
    assert subastas.presentacion(1) == []


def test_publicar_saca_de_la_bolsa_y_sale_en_la_ventana(monkeypatch):
    v = _ses(10, 'Vende', {20: ITEM})
    v.cantidades[20] = 5
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    assert subastas.publicar(v, [{'ranura': 20, 'item_id': ITEM, 'cantidad': 3, 'precio': 1000}]) == 1
    assert app._cant_de(v, 20) == 2
    fila = subastas.listado()[0]
    assert (fila['item_id'], fila['cantidad'], fila['precio'], fila['vendedor']) == (ITEM, 3, 1000, 'Vende')
    pkt = subastas.vista()
    assert pkt[:2] == b'\x32\x00' and struct.unpack_from('<II', pkt, 19) == (1, 0)
    assert struct.unpack_from('<8sIII', pkt, 27) == (subastas.instancia(fila['id']), 3, 1000, ITEM)


def test_comprar_cobra_y_paga_al_vendedor_conectado_menos_la_comision(monkeypatch):
    v = _ses(10, 'Vende', {20: ARMA})
    v.personaje.mejoras[20] = {'veces': 4, 'gemas': [], 'extra': {}, 'huecos': 0}
    c = _ses(11, 'Compra', {}, oro=5000)
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    monkeypatch.setattr(app, '_tw_sesiones', lambda: [v, c])
    subastas.publicar(v, [{'ranura': 20, 'item_id': ARMA, 'cantidad': 1, 'precio': 2000}])
    assert 20 not in v.inventario and 20 not in v.personaje.mejoras
    fid = subastas.listado()[0]['id']
    subastas.comprar(c, _compra(subastas.ENTIDAD, subastas.instancia(fid)))
    r = next(k for k, it in c.inventario.items() if it == ARMA)
    assert c.oro == 3000 and c.personaje.mejoras[r]['veces'] == 4
    assert v.oro == 1900                                      # 2000 menos el 5 %
    assert subastas.listado() == []


def test_sin_oro_no_se_compra(monkeypatch):
    v = _ses(10, 'Vende', {20: ARMA})
    c = _ses(11, 'Compra', {}, oro=10)
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    subastas.publicar(v, [{'ranura': 20, 'item_id': ARMA, 'cantidad': 1, 'precio': 2000}])
    fid = subastas.listado()[0]['id']
    subastas.comprar(c, _compra(subastas.ENTIDAD, subastas.instancia(fid)))
    assert ARMA not in c.inventario.values() and len(subastas.listado()) == 1


def test_comprar_lo_propio_lo_retira_gratis(monkeypatch):
    v = _ses(10, 'Vende', {20: ARMA}, oro=0)
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    subastas.publicar(v, [{'ranura': 20, 'item_id': ARMA, 'cantidad': 1, 'precio': 2000}])
    fid = subastas.listado()[0]['id']
    subastas.comprar(v, _compra(subastas.ENTIDAD, subastas.instancia(fid)))
    assert ARMA in v.inventario.values() and v.oro == 0 and subastas.listado() == []


def test_solo_se_publica_cerca_del_subastador():
    assert subastas.cerca(_ses(1, 'A', {}, cerca=True))
    assert not subastas.cerca(_ses(1, 'A', {}, cerca=False))
