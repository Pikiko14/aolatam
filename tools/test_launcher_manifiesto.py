"""El /launcher.json que pide el launcher propio (launcher/, tools/compilar_launcher.py)."""
import hashlib
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import cliente_local as cl
import parche


def test_el_manifiesto_describe_el_parche_y_sus_archivos(tmp_path, monkeypatch):
    pak = parche.armar_pak({'MAP\\MAP900.MPC': b'mapa'})
    (tmp_path / 'update27.pak').write_bytes(pak)
    (tmp_path / 'version.json').write_text(json.dumps({
        'version': '8.5.1.50', 'pak': 'update27.pak', 'bytes': len(pak),
        'sha256': hashlib.sha256(pak).hexdigest(), 'archivos': ['MAP\\MAP900.MPC']}), encoding='utf-8')
    monkeypatch.setattr(parche, 'DESTINO', tmp_path)
    m = json.loads(cl._archivo_de_parche('/launcher.json'))
    assert (m['version'], m['pak'], m['bytes']) == ('8.5.1.50', 'update27.pak', len(pak))
    assert m['sha256'] == hashlib.sha256(pak).hexdigest()
    # el relleno de los mini-paks del START.EXE cuenta como del parche (para retirar los update28..31 viejos)
    assert set(m['archivos']) == {'MAP\\MAP900.MPC', cl.RELLENO[0]}
    assert isinstance(m['noticias'], list) and 'launcher' not in m
    # y el pak se sirve entero por la misma via
    assert cl._archivo_de_parche('/update27.pak') == pak


def test_anuncia_y_sirve_el_propio_launcher(tmp_path, monkeypatch):
    (tmp_path / 'version.json').write_text('{}', encoding='utf-8')
    (tmp_path / 'launcher_propio').mkdir()
    (tmp_path / 'launcher_propio' / cl.LAUNCHER_EXE).write_bytes(b'MZ launcher')
    monkeypatch.setattr(parche, 'DESTINO', tmp_path)
    m = json.loads(cl._archivo_de_parche('/launcher.json'))
    assert m['launcher'] == {'archivo': cl.LAUNCHER_EXE, 'bytes': 11, 'sha256': hashlib.sha256(b'MZ launcher').hexdigest()}
    assert cl._archivo_de_parche('/' + cl.LAUNCHER_EXE) == b'MZ launcher'
