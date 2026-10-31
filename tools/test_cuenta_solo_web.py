"""Las cuentas se crean en la web (server/web_registro.py): el juego ya no crea una cuenta al entrar con un nombre nuevo."""
import pathlib
import sqlite3
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import cuentas

AUTH = b'nuevo'.ljust(21, b'\0') + bytes(range(32)) + bytes(20)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(cuentas, 'DB_PATH', tmp_path / 'cuentas.db')
    monkeypatch.setattr(cuentas, '_notificar_cambio', lambda **kw: None)
    with sqlite3.connect(cuentas.DB_PATH) as c:
        c.execute('CREATE TABLE cuentas(usuario TEXT PRIMARY KEY COLLATE NOCASE, password TEXT)')
        c.execute('CREATE TABLE personajes(usuario TEXT COLLATE NOCASE,char_id INTEGER,ranura INTEGER,nombre TEXT,'
                  'datos TEXT,PRIMARY KEY(usuario,ranura))')
        c.execute('CREATE TABLE configuracion(clave TEXT PRIMARY KEY, valor TEXT, nota TEXT)')


def _poner(clave, valor):
    with sqlite3.connect(cuentas.DB_PATH) as c:
        c.execute('INSERT OR REPLACE INTO configuracion VALUES (?, ?, "")', (clave, valor))


def test_un_usuario_que_no_existe_no_entra_ni_se_crea(db):
    cuenta, motivo = cuentas.validar('nuevo', AUTH)
    assert cuenta is None and 'web' in motivo
    assert cuentas.usuario_disponible('nuevo')


def test_reservado_en_la_web_entra_y_se_queda_con_su_contrasena(db):
    assert cuentas.reservar_usuario('nuevo')
    cuenta, motivo = cuentas.validar('nuevo', AUTH)
    assert cuenta is not None and motivo == 'contrasena registrada'
    otra = AUTH[:21] + bytes(32) + AUTH[53:]
    assert cuentas.validar('nuevo', otra)[0] is None          # despues, la contrasena manda


def test_el_interruptor_vuelve_a_crearla_al_entrar(db):
    _poner('crear_cuenta_al_entrar', '1')
    cuenta, motivo = cuentas.validar('nuevo', AUTH)
    assert cuenta is not None and 'creada' in motivo
