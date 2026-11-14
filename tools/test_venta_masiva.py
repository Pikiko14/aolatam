"""Bulk Sell de la tienda NPC (13/11/2026): el gear y las armas de la mochila salen marcados, una fila se desmarca
pulsandola y el check vende lo marcado (comando 172 del 0x002F)."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import inventario  # noqa: E402

ESPADA, ESCUDO, POCION, CASCO_EQUIPADO = 1001, 1002, 3001, 1003


def _sesion(monkeypatch):
    enviados = []
    monkeypatch.setattr(inventario, 'es_equipable', lambda it: it in (ESPADA, ESCUDO, CASCO_EQUIPADO))
    monkeypatch.setattr(inventario, 'es_mascota', lambda it: False)
    monkeypatch.setattr(inventario, 'es_item_fashion', lambda it: False)
    monkeypatch.setattr(app, '_precio_venta', lambda it: {ESPADA: 100, ESCUDO: 50, POCION: 5}.get(it, 0))
    monkeypatch.setattr(app, '_nombre_item', lambda it: 'Item %d' % it)
    monkeypatch.setattr(app, '_refrescar', lambda ses, r, **k: [])
    monkeypatch.setattr(app, '_guardar_bolsa', lambda ses, cid: None)
    for m in ('arena_premios_compat', 'item_mall'):
        mod = __import__(m)
        monkeypatch.setattr(mod, 'es_premio' if m == 'arena_premios_compat' else 'es_temporal', lambda s, r: False)
    monkeypatch.setattr(__import__('furniture_items'), 'protegido', lambda s, r: False)
    p = NS(char_id=7, oro=0, mejoras={}, nombre='x')
    ses = NS(personaje=p, oro=0, usuario=None, inventario={3: CASCO_EQUIPADO, 20: ESPADA, 21: POCION, 22: ESCUDO},
             cantidades={}, enviar=lambda *a: enviados.extend(a))
    monkeypatch.setattr(app, '_cant_de', lambda s, r: 1)

    def sacar(s, r, n=1):
        return 1 if s.inventario.pop(r, None) else 0
    monkeypatch.setattr(app, '_sacar', sacar)
    return ses, enviados


def _cmd(sub, i=0):
    return struct.pack('<BII', app.CMD_VENTA_MASIVA, sub, i)


def test_salen_marcados_solo_el_gear_y_las_armas_de_la_mochila(monkeypatch):
    ses, enviados = _sesion(monkeypatch)
    assert app._venta_masiva(ses, 'a', _cmd(app.VM_VER))
    assert ses._venta_masiva['filas'] == [(20, ESPADA), (22, ESCUDO)] and not ses._venta_masiva['fuera']
    lua = enviados[-1][2:].decode('latin1')
    assert lua.startswith('VentaMasivaLista(') and '"Item 1001"' in lua and ',150,' in lua
    assert ',5616}' in lua.replace(' ', '')                         # el icono del objeto (原型介面) en su casilla


def test_desmarcar_y_vender_solo_lo_marcado(monkeypatch):
    ses, _env = _sesion(monkeypatch)
    app._venta_masiva(ses, 'a', _cmd(app.VM_VER))
    app._venta_masiva(ses, 'a', _cmd(app.VM_MARCAR, 1))           # fuera el escudo
    app._venta_masiva(ses, 'a', _cmd(app.VM_VENDER))
    assert ses.oro == 100 and 20 not in ses.inventario and ses.inventario[22] == ESCUDO
    assert ses.inventario[3] == CASCO_EQUIPADO and ses.inventario[21] == POCION
    assert ses._venta_masiva['filas'] == [(22, ESCUDO)]             # la lista nueva: lo que queda


def test_otro_comando_no_es_suyo(monkeypatch):
    ses, _env = _sesion(monkeypatch)
    assert not app._venta_masiva(ses, 'a', struct.pack('<BII', 11, 0, 0))


def test_las_monturas_y_los_robots_no_entran(monkeypatch):
    ses, _env = _sesion(monkeypatch)
    LEON, ROBOT = 83305, 3795                                      # Celestial Lion (座騎), Penguin Robot (機甲)
    monkeypatch.setattr(inventario, 'es_equipable', lambda it: it in (ESPADA, ESCUDO, CASCO_EQUIPADO, LEON, ROBOT))
    monkeypatch.setattr(app, '_precio_venta', lambda it: 1500000 if it in (LEON, ROBOT) else 100)
    ses.inventario.update({23: LEON, 24: ROBOT})
    assert [it for _r, it in app.vm_candidatos(ses)] == [ESPADA, ESCUDO]
