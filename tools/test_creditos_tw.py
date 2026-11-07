"""Totem War: creditos por baja segun el nivel de la victima, x5 la primera vez y x2 despues (07/11/2026)."""
import pathlib
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import totem_war as tw  # noqa: E402


def test_primera_muerte_x5_y_despues_x2(monkeypatch):
    monkeypatch.setattr(tw, '_MUERTOS', set())
    v = NS(nivel=60, char_id=7)
    assert tw.creditos_por_baja(v) == 300
    assert tw.creditos_por_baja(v) == 120
    assert tw.creditos_por_baja(NS(nivel=10, char_id=8)) == 50
    assert tw.creditos_por_baja(None) == tw.CREDITOS_POR_BAJA
