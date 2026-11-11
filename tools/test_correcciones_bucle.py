"""Lector unico de data/gm.txt, senuelos apagados y lo que congelaba el bucle principal."""
import asyncio
import json
import os
import pathlib
import sys
import time

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import cliente_local
import configuracion


def test_gm_txt_se_toma_una_sola_vez(tmp_path):
    ruta = tmp_path / 'gm.txt'
    ruta.write_text('\ufeffitem 10 2\nlevel 30\n', encoding='utf-8')
    assert app.tomar_comandos_gm(ruta).splitlines() == ['item 10 2', 'level 30']
    assert not ruta.exists() and not list(tmp_path.iterdir())
    assert app.tomar_comandos_gm(ruta) == ''


def test_un_solo_lector_de_gm_txt():
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    assert 'gm.cola(self)' not in fuente and 'gm.consola(self)' not in fuente
    assert fuente.count('self._cola_gm()') == 1


def test_senuelos_apagados_por_defecto():
    if os.environ.get('AO_PUERTOS_SENUELO') != '1':
        assert configuracion.PUERTOS_SENUELO is False


def test_el_sha_se_recalcula_solo_si_cambia(tmp_path):
    f = tmp_path / 'angel.dat'
    f.write_bytes(b'uno')
    n1, sha1 = cliente_local._sha_archivo(f)
    assert cliente_local._sha_archivo(f) == (n1, sha1)
    time.sleep(0.01)
    f.write_bytes(b'otro contenido')
    os.utime(f, ns=(time.time_ns(), time.time_ns()))
    n2, sha2 = cliente_local._sha_archivo(f)
    assert n2 == len(b'otro contenido') and sha2 != sha1


def test_el_manifiesto_se_sirve_desde_un_hilo():
    datos = asyncio.run(cliente_local._archivo_de_parche_async('/launcher.json'))
    assert 'version' in json.loads(datos)
