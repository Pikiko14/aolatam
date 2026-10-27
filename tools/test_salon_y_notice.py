"""Peluqueria (C2S 0x002F subtipo 0x25) y Recovery Notice (C2S 0x004D)."""
import pathlib
import struct
import sys
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate
import cuentas
import presencia
import recent_mall
import recovery_notice
import salon


def _sesion(nombre='Yo', char_id=1, bolsa=None):
    s = types.SimpleNamespace(
        usuario='u', addr='test', paquetes=[], conectado=True,
        inventario=dict(bolsa or {}),
        personaje=types.SimpleNamespace(nombre=nombre, char_id=char_id, entity_id=500 + char_id,
                                        apariencia=[1, 1, 1, 0, 8], buffs={}))
    s.enviar = lambda *pk: s.paquetes.extend(pk)
    return s


@pytest.fixture
def entorno(monkeypatch):
    gastado = []

    def cambiar(ses, consumo, premios, transaccion=None):
        for casilla, n in consumo.items():
            gastado.append((casilla, ses.inventario[casilla]))
            ses.inventario.pop(casilla)
    monkeypatch.setattr(recent_mall, 'cambiar', cambiar)
    monkeypatch.setattr(app, '_tope_bolsa', lambda bolsa: 99)
    monkeypatch.setattr(cuentas, 'guardar_apariencia', lambda *a: None)
    monkeypatch.setattr(presencia, 'notificar_equipo', lambda ses: None)
    return gastado


def peluqueria(ses, item, opcion):
    return salon.procesar(ses, struct.pack('<BII', 0x25, item, opcion))


def test_la_complexion_cambia_la_piel(entorno):
    ses = _sesion(bolsa={40: 7036})
    assert peluqueria(ses, 7036, 19)
    assert ses.personaje.apariencia == [1, 1, 1, 0, 19]
    assert entorno == [(40, 7036)]
    assert combate.atributo(501, 19, 38) in ses.paquetes


def test_peine_altura_y_color(entorno):
    ses = _sesion(bolsa={40: 7034, 41: 8895, 42: 7035})
    peluqueria(ses, 7034, 9)
    peluqueria(ses, 8895, 2)
    peluqueria(ses, 7035, 30)
    assert ses.personaje.apariencia == [1, 9, 2, 30, 8]


def test_opcion_fuera_de_rango_o_igual_no_gasta(entorno):
    ses = _sesion(bolsa={40: 7036})
    assert peluqueria(ses, 7036, 26)
    assert peluqueria(ses, 7036, 8)
    assert peluqueria(ses, 7034, 3)
    assert not entorno and ses.personaje.apariencia == [1, 1, 1, 0, 8]


def test_otros_0x002f_no_son_de_la_peluqueria():
    ses = _sesion()
    assert not salon.procesar(ses, struct.pack('<BII', 0x16, 39, 0xFFFFFFFF))


def notice(ses, casilla, nombre):
    return recovery_notice.procesar(ses, bytes([casilla]) + nombre.encode().ljust(17, b'\0'))


@pytest.fixture
def jugadores(entorno, monkeypatch):
    yo = _sesion('Yo', 1, {37: 4297, 38: 20139, 39: 4458})
    otro = _sesion('Impacty', 2)
    monkeypatch.setattr(app, '_tw_sesiones', lambda: [yo, otro])
    buffs = []
    monkeypatch.setattr(app, '_buff_a_otro',
                        lambda s, tipo, entrada, dur_ms, mag, lanzador=None, ef=0: buffs.append((s, tipo, entrada['hp_bonus'], dur_ms)))
    recovery_notice._ESPERA_HASTA.clear()
    return yo, otro, buffs


def test_el_notice_da_hp_maximo_al_nombrado(jugadores, entorno):
    yo, otro, buffs = jugadores
    assert notice(yo, 37, 'impacty')
    assert buffs == [(otro, 1897, 500, 10800000)]
    assert entorno == [(37, 4297)]
    bc = [pk for pk in otro.paquetes if pk[:2] == struct.pack('<H', 0x0128)]
    assert bc and bc[0][6] == 11 and b'used a Recovery Notice on Impacty' in bc[0]


def test_la_descripcion_del_buff_va_al_cliente(monkeypatch):
    import cliente_local
    import configuracion
    monkeypatch.setattr(configuracion, 'DESCRIPCIONES_MAGIAS', {1897: 'Increase Maximum HP by 500.'})
    xml = ('<法術 編號="1897" 名稱="Recovery Notice" HP="500" />\n'
           '<法術 編號="6758" 名稱="Super" 說明="Increase Maximum HP by 2000. " />').encode('utf-8')
    out = cliente_local._parchear_descripciones_xml_bytes(xml, '法術', '說明', 'DESCRIPCIONES_MAGIAS').decode('utf-8')
    assert '編號="1897" 名稱="Recovery Notice" HP="500" 說明="Increase Maximum HP by 500." />' in out
    assert 'Increase Maximum HP by 2000. ' in out


def test_una_vez_cada_24_horas_por_objetivo(jugadores, entorno):
    yo, otro, buffs = jugadores
    notice(yo, 37, 'Impacty')
    yo.inventario[37] = 4297
    notice(yo, 37, 'Impacty')
    assert len(buffs) == 1 and len(entorno) == 1
    notice(yo, 38, 'Impacty')
    assert buffs[-1][1:3] == (6758, 2000)


def test_sin_conectar_no_se_gasta(jugadores, entorno):
    yo, otro, buffs = jugadores
    assert notice(yo, 37, 'Nadie')
    assert not buffs and not entorno


def test_las_de_amor_siguen_su_camino(jugadores):
    yo, otro, buffs = jugadores
    assert not notice(yo, 39, 'Impacty')
