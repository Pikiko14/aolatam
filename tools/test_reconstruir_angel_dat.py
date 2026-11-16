"""Reconstruccion de angel.dat: transplant de .rsrc y orden de parches (14/11/2026)."""
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import reconstruir_angel_dat as R  # noqa: E402
from parche_canal_lua import _secciones  # noqa: E402

REF = pathlib.Path(__file__).resolve().parent.parent / 'parches' / 'juego' / 'angel.dat'


def test_transplantar_rsrc_deja_image_en_aolat():
    """Tras el transplant, SizeOfImage apunta al inicio de donde ira .aolat (0x74e000)."""
    if not REF.is_file():
        return
    # Cabecera minima: un PE falso no sirve; se parte de la referencia recortada a .rsrc.
    ref = REF.read_bytes()
    pe, _tab, secs = _secciones(ref)
    rsrc = next(s for s in secs if s['nombre'].startswith(b'.rsrc'))
    base = bytearray(ref[:rsrc['rptr'] + 0x1000])  # .rsrc "chico" como el UPX
    # Simula virgin: .rsrc pequeno en cabecera
    struct.pack_into('<IIII', base, rsrc['cab'] + 8, 0xfa8, rsrc['va'], 0x1000, rsrc['rptr'])
    dd = pe + 24 + 96 + 2 * 8
    struct.pack_into('<II', base, dd, rsrc['va'], 0xfa8)
    struct.pack_into('<I', base, pe + 24 + 8, 0x1000)
    del base[rsrc['rptr'] + 0x1000:]
    out = R.transplantar_rsrc(base, ref)
    pe2, _t2, secs2 = _secciones(out)
    r2 = next(s for s in secs2 if s['nombre'].startswith(b'.rsrc'))
    assert r2['rsz'] == rsrc['rsz']
    assert r2['vsz'] == rsrc['vsz']
    assert struct.unpack_from('<I', out, pe2 + 24 + 56)[0] == 0x74e000
    assert out[r2['rptr']:r2['rptr'] + r2['rsz']] == ref[rsrc['rptr']:rsrc['rptr'] + rsrc['rsz']]


def test_reconstruir_coincide_con_referencia():
    if not REF.is_file() or not R.IGG_DEF.is_file() or not R.UPX_DEF.is_file():
        return
    import tempfile
    with tempfile.TemporaryDirectory(prefix='test_recon_angel_') as tmp:
        out = pathlib.Path(tmp) / 'angel.dat'
        R.reconstruir(
            R.IGG_DEF, out,
            upx=R.UPX_DEF,
            referencia=REF,
            icono_update=False,
            ico=R.ICO_DEF,
            emblema=None,
        )
        assert out.read_bytes() == REF.read_bytes()
        assert R.sha256(out) == R.sha256(REF)


if __name__ == '__main__':
    test_transplantar_rsrc_deja_image_en_aolat()
    test_reconstruir_coincide_con_referencia()
    print('ok')
