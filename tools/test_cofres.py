"""Cofres del banco alquilados con Safe Key (C2S 0x002F subtipo 0x17)."""
import pathlib
import struct
import sys
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import cofres
import cuentas
import inventario as inv

AHORA = 1_800_000_000.0
DIA = 86400


@pytest.fixture
def ses(monkeypatch):
    monkeypatch.setattr(app, '_tope_bolsa', lambda bolsa: 99)
    monkeypatch.setattr(app, '_refrescar', lambda s, ranuras, con_oro=False: [])
    monkeypatch.setattr(app, '_guardar_bolsa', lambda s, cid: None)
    monkeypatch.setattr(cuentas, 'guardar_banco', lambda *a: None)

    def sacar(s, ranura, n):
        s.inventario.pop(ranura)
    monkeypatch.setattr(app, '_sacar', sacar)
    s = types.SimpleNamespace(usuario='u', addr='test', paquetes=[], inventario={30: 2001, 31: 2734},
                              personaje=types.SimpleNamespace(char_id=1, entity_id=9, banco={}, mejoras={}))
    s.enviar = lambda *pk: s.paquetes.extend(pk)
    return s


def rentar(s, indice, tipo, ahora=AHORA):
    cofres.alquilar(s, struct.pack('<BII', 0x17, indice, tipo), ahora=ahora)


def test_las_casillas_salen_del_cliente():
    assert list(cofres.casillas_de(1)) == list(range(26, 41))
    assert list(cofres.casillas_de(6)) == list(range(101, 116))
    assert cofres.casilla_llave(1) == 116 and cofres.casilla_llave(6) == 121


def test_alquilar_30_dias_deja_la_llave_en_el_banco(ses):
    rentar(ses, 0, 2)
    p = ses.personaje
    assert 30 not in ses.inventario
    assert p.banco[116] == (2001, 1)
    assert p.mejoras[-10116] == {'cofre_fin': AHORA + 30 * DIA, 'cofre_item': 2001}
    assert cofres.vigente(p, 1, AHORA) and not cofres.vigente(p, 1, AHORA + 31 * DIA)


def test_la_caducidad_va_en_la_entrada_de_la_llave(ses):
    rentar(ses, 0, 2)
    pk = [x for x in ses.paquetes if x[:2] == struct.pack('<H', 0x001B)][0]
    assert struct.unpack_from('<I', pk, 6 + 47)[0] == int(AHORA + 30 * DIA)


def test_volver_a_alquilar_suma_dias(ses):
    rentar(ses, 0, 2)
    ses.inventario[30] = 2001
    rentar(ses, 0, 2, ahora=AHORA + DIA)
    assert ses.personaje.mejoras[-10116]['cofre_fin'] == AHORA + 60 * DIA


def test_para_siempre(ses):
    rentar(ses, 1, 3)
    assert ses.personaje.mejoras[-10117]['cofre_fin'] == 0
    assert cofres.vigente(ses.personaje, 2, AHORA + 3650 * DIA)


def test_sin_la_llave_de_ese_tipo_no_se_alquila(ses):
    rentar(ses, 0, 1)
    assert not ses.personaje.banco and 30 in ses.inventario


def test_solo_se_guarda_en_cofres_vigentes(ses):
    p = ses.personaje
    assert cofres.guardables(p, AHORA) == list(range(1, 26))
    rentar(ses, 0, 2)
    assert cofres.guardables(p, AHORA) == list(range(1, 41))
    assert cofres.se_puede_guardar(p, 30, AHORA)
    assert not cofres.se_puede_guardar(p, 30, AHORA + 31 * DIA)
    assert not cofres.se_puede_guardar(p, 45, AHORA)


def test_el_guardado_conserva_la_llave(monkeypatch):
    guardado = {}
    monkeypatch.setattr(cuentas, '_actualizar_personaje', lambda u, c, mut: mut(guardado))
    cuentas.guardar_mejoras('u', 1, {-10117: {'cofre_fin': 0, 'cofre_item': 2734}})
    assert '-10117' in guardado['mejoras']
