"""El album del mapa del tesoro cuenta fragmentos de CUALQUIER nivel (06/11/2026: "los mapas se pueden usar de
cualquier nivel, no pide la secuencia, puede usar 10 lvl 1")."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402


def test_diez_del_mismo_nivel_completan_el_album():
    p = NS(logros_cont={})
    for i in range(1, 11):
        assert app.anotar_fragmento(p) == (True, i)
    assert app.anotar_fragmento(p) == (False, 10)
    assert app.tesoro_hallados(p) == 10


def test_lo_anotado_antes_con_la_mascara_se_conserva():
    p = NS(logros_cont={app.CLAVE_TESORO: 0b101})          # dos fragmentos de la version anterior
    assert app.tesoro_hallados(p) == 2
    assert app.anotar_fragmento(p) == (True, 3)


def test_el_paquete_lleva_los_hallados(monkeypatch):
    monkeypatch.setattr(app, '_logros_datos', lambda ses: None)
    ses = NS(personaje=NS(logros_cont={app.CLAVE_TESORO_N: 7}))
    assert app._tesoro_paquete(ses)[2 + 12:2 + 16] == (7).to_bytes(4, 'little')


# 09/11/2026: "al llenar el mapa no me dice donde esta el tesoro". El album lleno lleva mapa, escena y punto en el
# 0x012A (el cliente los marca en la pestana TreMap) y al pasar por el punto sale el premio.
import struct  # noqa: E402

import tesoros  # noqa: E402


def _lleno(nivel=1):
    p = NS(logros_cont={}, stage=0, char_id=1)
    for _ in range(10):
        app.anotar_fragmento(p, nivel)
    return p


def test_el_album_lleno_manda_donde_esta_el_tesoro(monkeypatch):
    monkeypatch.setattr(app, '_logros_datos', lambda ses: None)
    p = _lleno()
    _op, tipo, mapa, escena, hallados, punto, _semilla = struct.unpack('<HIIIIIB', app._tesoro_paquete(NS(personaje=p)))
    assert (tipo, hallados) == (0, 10)
    assert 1 <= mapa <= 10 and escena == 41 and tesoros.casilla(escena, punto)
    assert app.tesoro_destino(p) == (mapa, escena, punto)          # se queda el mismo


def test_sin_llenar_no_hay_tesoro(monkeypatch):
    monkeypatch.setattr(app, '_logros_datos', lambda ses: None)
    p = NS(logros_cont={app.CLAVE_TESORO_N: 9})
    assert struct.unpack('<HIIIIIB', app._tesoro_paquete(NS(personaje=p)))[2] == 0


def test_los_niveles_de_las_piezas_eligen_la_franja():
    assert tesoros.franja_de_nivel(1) == 1 and tesoros.franja_de_nivel(10) == tesoros.FRANJAS
    mapa = app.tesoro_destino(_lleno(10))[0]
    assert 60 < mapa <= tesoros.MAPA_MAXIMO
    p = NS(logros_cont={app.CLAVE_TESORO_N: 10})                   # album lleno de antes, sin niveles
    assert app.tesoro_destino(p)[0] <= 10


def _sesion(p, monkeypatch, cabe=True):
    enviados = []
    monkeypatch.setattr(app, '_logros_datos', lambda ses: None)
    monkeypatch.setattr(app, '_logros_guardar', lambda ses: None)
    monkeypatch.setattr(app, '_guardar_bolsa', lambda ses, cid: None)
    monkeypatch.setattr(app, '_refrescar', lambda ses, r, **k: [])
    monkeypatch.setattr(app, '_meter', lambda ses, it, n=1: 5 if cabe else None)
    return NS(personaje=p, enviar=lambda *a: enviados.extend(a)), enviados


def test_al_pasar_por_el_punto_sale_el_cofre_y_al_pulsarlo_el_premio(monkeypatch):
    # 13/11/2026, "el treasure map me da el item directamente y no me muestra el cofre en tierra": al pasar sale el
    # cofre (0x000E con su sprite de server.obd) y el premio solo al pulsarlo, de cerca.
    p = _lleno()
    mapa, escena, punto = app.tesoro_destino(p)
    p.stage = escena
    x, y = tesoros.casilla(escena, punto)
    ses, enviados = _sesion(p, monkeypatch)
    app._tesoro_al_pisar(ses, 'a', [(x + 20, y + 20)])               # lejos: nada
    assert not getattr(ses, '_tesoro_cofre', None) and app.tesoro_hallados(p) == 10
    app._tesoro_al_pisar(ses, 'a', [(x + 2, y - 1)])
    cofre = ses._tesoro_cofre
    assert cofre and cofre['tile'] == (x, y) and app.tesoro_hallados(p) == 10          # aun sin premio
    sprite = tesoros.de_id(mapa)['sprite_cofre']
    assert any(pk[:2] == b'\x0e\x00' and struct.unpack_from('<I', pk, 2 + 34)[0] == sprite for pk in enviados)
    p.tile_x, p.tile_y = x + 10, y                                    # lejos: no se abre
    assert app._tesoro_pulsar(ses, 'a', cofre['eid']) and app.tesoro_hallados(p) == 10
    p.tile_x, p.tile_y = x + 1, y
    assert not app._tesoro_pulsar(ses, 'a', cofre['eid'] + 1)         # otra entidad
    assert app._tesoro_pulsar(ses, 'a', cofre['eid'])
    assert app.tesoro_hallados(p) == 0 and app.tesoro_destino(p) is None and ses._tesoro_cofre is None


def test_con_la_bolsa_llena_el_cofre_espera(monkeypatch):
    p = _lleno()
    mapa, escena, punto = app.tesoro_destino(p)
    p.stage = escena
    ses, _env = _sesion(p, monkeypatch, cabe=False)
    x, y = tesoros.casilla(escena, punto)
    app._tesoro_al_pisar(ses, 'a', [(x, y)])
    p.tile_x, p.tile_y = x, y
    assert app._tesoro_pulsar(ses, 'a', ses._tesoro_cofre['eid'])
    assert app.tesoro_destino(p) == (mapa, escena, punto) and ses._tesoro_cofre


def test_delete_vacia_el_album(monkeypatch):
    p = _lleno()
    ses, _env = _sesion(p, monkeypatch)
    app._tesoro_borrar(ses, 'a')
    assert app.tesoro_hallados(p) == 0 and app.tesoro_destino(p) is None
