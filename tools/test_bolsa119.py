"""El angel.dat recorre la bolsa hasta la ranura 119 (tools/parche_bolsa119_exe.py, 05/11/2026)."""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import parche_bolsa119_exe as pb  # noqa: E402

EXE = RAIZ / 'parches' / 'juego' / 'angel.dat'


@pytest.mark.skipif(not EXE.exists(), reason='sin parches/juego/angel.dat')
def test_el_exe_de_los_jugadores_cuenta_las_25_casillas_nuevas():
    d = EXE.read_bytes()
    assert pb.lleva_el_parche(d)
    assert pb.parchear(d) == d                      # aplicarlo otra vez no cambia nada


@pytest.mark.skipif(not EXE.exists(), reason='sin parches/juego/angel.dat')
def test_los_bucles_del_prop_viejo_siguen_por_las_casillas_nuevas():
    """"si tengo los primeros 25 puestos ocupados, no me funciona el trade por espacio" (tools/parche_prop50_huecos_exe.py)."""
    import parche_prop50_huecos_exe as ph
    d = EXE.read_bytes()
    assert ph.lleva_el_parche(d)
    from parche_canal_lua import _off
    for _inc, _r, _d, tope_va in ph.BUCLES:
        assert d[_off(d, tope_va) + 3] == ph.TOPE_NUEVO
