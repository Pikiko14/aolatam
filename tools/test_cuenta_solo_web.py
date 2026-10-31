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


def _auth_real(usuario, pw, basura=b'\x5a'):
    """Un AUTH como el del cliente de Windows: la contrasena, un 0 y basura, cifrado con Blowfish (clave_cliente)."""
    import clave_cliente
    bufer = (pw.encode() + b'\0' + basura * 32)[:32]
    return usuario.encode().ljust(21, b'\0') + clave_cliente.cifrar(bufer) + bytes(20)


def test_la_contrasena_de_la_web_es_la_del_juego(db):
    assert cuentas.reservar_usuario('webheroe', 'secreto1')
    # entra con la contrasena de la web, aunque la basura de detras cambie entre ingresos
    assert cuentas.validar('webheroe', _auth_real('webheroe', 'secreto1'))[0] is not None
    assert cuentas.validar('webheroe', _auth_real('webheroe', 'secreto1', b'\x13'))[0] is not None
    cuenta, motivo = cuentas.validar('webheroe', _auth_real('webheroe', 'otraclave'))
    assert cuenta is None and motivo == 'contrasena incorrecta'


def test_una_cuenta_vieja_se_pasa_sola_al_formato_nuevo(db):
    import clave_cliente
    auth = _auth_real('vieja', 'clave123')
    h = cuentas.hash_de_auth(auth)
    with sqlite3.connect(cuentas.DB_PATH) as c:
        c.execute("INSERT INTO cuentas VALUES ('vieja', ?)", ('ab$' + cuentas._firmar(h, 'ab'),))
    cuenta, motivo = cuentas.validar('vieja', auth)
    assert cuenta is not None and 'formato nuevo' in motivo
    with sqlite3.connect(cuentas.DB_PATH) as c:
        guardado = c.execute("SELECT password FROM cuentas WHERE usuario='vieja'").fetchone()[0]
    assert guardado.startswith(cuentas.PREFIJO_PW) and cuentas.contrasena_ok(guardado, 'clave123')
    # y desde entonces la basura de detras ya no importa
    assert cuentas.validar('vieja', _auth_real('vieja', 'clave123', b'\x77'))[0] is not None


def test_el_interruptor_vuelve_a_crearla_al_entrar(db):
    _poner('crear_cuenta_al_entrar', '1')
    cuenta, motivo = cuentas.validar('nuevo', AUTH)
    assert cuenta is not None and 'creada' in motivo
