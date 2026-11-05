"""El conversor de .spr de monstruos (tools/spr_ewsp.py): ida y vuelta sin perder nada (05/11/2026)."""
import pathlib
import sys
import zlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))

import spr_ewsp as sp  # noqa: E402

CLIENTE = pathlib.Path(r'C:\AO\Angels Online')


def _spr_del_cliente(nombre):
    import paks_cliente as pc
    for p in sorted(CLIENTE.glob('*'), key=lambda p: pc.numero(p.name)):
        if p.suffix.lower() != '.pak':
            continue
        d = p.read_bytes()
        for n, _crc, cs, _us, off in pc._directorio(d):
            if n.lower().endswith(nombre):
                return zlib.decompress(d[off:off + cs], -15)
    return None


@pytest.mark.skipif(not CLIENTE.is_dir(), reason='sin cliente local')
def test_ida_y_vuelta_identica():
    d = _spr_del_cliente('42107_hurt.spr')         # Slarm, recibe golpe
    if d is None:
        pytest.skip('sin el sprite en el cliente')
    frames, k = sp.leer(d)
    assert len(frames) == 10 and frames[0][2] == 'h013.SHP'
    nuevo = sp.escribir([(im, o) for im, o, _ in frames], 'hurt', k)
    otra, _ = sp.leer(nuevo)
    for (a, oa, na), (b, ob, nb) in zip(frames, otra):
        assert a.size == b.size and oa == ob and na == nb
        assert a.tobytes() == b.tobytes()
