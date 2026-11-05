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
