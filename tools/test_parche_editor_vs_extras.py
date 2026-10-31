"""Si un mapa esta en el pack del editor y en parches/extras, el parche reparte el mas reciente."""
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import cliente_local
import parche

NOMBRE = 'MAP\\MAP900.MPC'


def _preparar(tmp_path, monkeypatch, extras_mas_nuevo):
    destino, cliente = tmp_path / 'parches', tmp_path / 'cliente'
    (destino / 'extras' / 'map').mkdir(parents=True)
    cliente.mkdir()
    extra = destino / 'extras' / 'map' / 'map900.mpc'
    extra.write_bytes(b'MAPA DE SUBIR_MAPA')
    pack = cliente / parche.PACK_EDITOR
    pack.write_bytes(parche.armar_pak({NOMBRE: b'MAPA DEL EDITOR'}))
    viejo, nuevo = 1_700_000_000, 1_700_000_500
    os.utime(extra, (nuevo, nuevo) if extras_mas_nuevo else (viejo, viejo))
    os.utime(pack, (viejo, viejo) if extras_mas_nuevo else (nuevo, nuevo))
    monkeypatch.setattr(parche, 'DESTINO', destino)
    monkeypatch.setattr(cliente_local, 'indice_paks', lambda ruta: {})
    import mpc_sin_npc
    monkeypatch.setattr(mpc_sin_npc, 'recortar_entrada', lambda n, d: d)
    return cliente


def test_gana_extras_si_es_mas_nuevo(tmp_path, monkeypatch):
    sys.path.insert(0, str(RAIZ / 'tools'))
    cliente = _preparar(tmp_path, monkeypatch, extras_mas_nuevo=True)
    assert parche.cambios_del_cliente(cliente)[NOMBRE] == b'MAPA DE SUBIR_MAPA'


def test_gana_el_editor_si_es_mas_nuevo(tmp_path, monkeypatch):
    sys.path.insert(0, str(RAIZ / 'tools'))
    cliente = _preparar(tmp_path, monkeypatch, extras_mas_nuevo=False)
    assert parche.cambios_del_cliente(cliente)[NOMBRE] == b'MAPA DEL EDITOR'
