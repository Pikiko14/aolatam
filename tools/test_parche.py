"""El parche para los jugadores: update27.pak y su servicio por FTP/HTTP."""
import asyncio
import ftplib
import pathlib
import sys
import threading
import urllib.request

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import cliente_local
import configuracion
import parche

ARCHIVOS = {'SETTING\\ENG\\ITEM.XML': b'<root>uno</root>' * 50, 'MAP\\MAP041.MPC': bytes(range(256)) * 9}


def test_el_pak_se_lee_con_los_lectores_del_servidor(tmp_path):
    pak = tmp_path / 'update27.pak'
    parche.escribir_pak(pak, ARCHIVOS)
    assert cliente_local._entradas_pak(pak) == set(ARCHIVOS)
    assert cliente_local._extraer_varios_pak(pak, list(ARCHIVOS)) == ARCHIVOS
    assert cliente_local._extraer_archivo_pak(pak, 'map\\map041.mpc') == ARCHIVOS['MAP\\MAP041.MPC']


def test_se_reparte_lo_que_difiere_del_bak(tmp_path, monkeypatch):
    original = {'SETTING\\ENG\\ITEM.XML': b'original', 'SETTING\\ENG\\STAGE.XML': b'igual'}
    cambiado = dict(original, **{'SETTING\\ENG\\ITEM.XML': b'cambiado'})
    pak = tmp_path / 'update26.pak'
    parche.escribir_pak(pak.with_name('update26.pak.bak'), original)
    parche.escribir_pak(pak, cambiado)
    monkeypatch.setattr(cliente_local, 'indice_paks', lambda ruta: {n: pak for n in cambiado})
    assert parche.cambios_del_cliente(tmp_path) == {'SETTING\\ENG\\ITEM.XML': b'cambiado'}


def test_la_version_sube_solo_si_cambia_el_contenido(tmp_path, monkeypatch):
    contenido = dict(ARCHIVOS)
    monkeypatch.setattr(parche, 'cambios_del_cliente', lambda ruta: dict(contenido))
    a = parche.generar(tmp_path, tmp_path / 'parches')
    b = parche.generar(tmp_path, tmp_path / 'parches')
    contenido['SETTING\\ENG\\ITEM.XML'] = b'otro'
    c = parche.generar(tmp_path, tmp_path / 'parches')
    assert a['version'] == b['version'] == '8.5.1.1' and c['version'] == '8.5.1.2'


@pytest.fixture
def servidor(tmp_path, monkeypatch):
    destino = tmp_path / 'parches'
    monkeypatch.setattr(parche, 'DESTINO', destino)
    monkeypatch.setattr(parche, 'cambios_del_cliente', lambda ruta: dict(ARCHIVOS))
    monkeypatch.setattr(configuracion, 'PARCHE_EN_LAUNCHER', True)
    parche.generar(tmp_path, destino)
    bucle = asyncio.new_event_loop()
    srv = bucle.run_until_complete(asyncio.start_server(cliente_local._manejar_actualizacion, '127.0.0.1', 0))
    hilo = threading.Thread(target=bucle.run_forever, daemon=True)
    hilo.start()
    yield srv.sockets[0].getsockname()[1], destino
    bucle.call_soon_threadsafe(bucle.stop)


def test_el_ftp_anuncia_y_entrega_el_parche(servidor):
    puerto, destino = servidor
    ftp = ftplib.FTP()
    ftp.connect('127.0.0.1', puerto, timeout=10)
    ftp.login('u', 'p')
    ini = []
    ftp.retrbinary('RETR update3.ini', ini.append)
    texto = b''.join(ini).decode('ascii')
    assert 'GameVer = 8.5.1.1' in texto and 'GameURL = update27.pak' in texto
    pak = []
    ftp.retrbinary('RETR update27.pak', pak.append)
    assert b''.join(pak) == (destino / 'update27.pak').read_bytes()
    with pytest.raises(ftplib.error_perm):
        ftp.retrbinary('RETR ../version.json', lambda b: None)
    ftp.quit()


def test_el_http_tambien(servidor):
    puerto, destino = servidor
    with urllib.request.urlopen('http://127.0.0.1:%d/alog-patch/update27.pak' % puerto, timeout=10) as r:
        assert r.read() == (destino / 'update27.pak').read_bytes()
