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


def test_el_numero_amarillo_del_ko_son_los_creditos_de_la_guerra(monkeypatch):
    import struct
    import pvp_liga
    monkeypatch.setattr(tw, '_MUERTOS', set())
    monkeypatch.setattr(tw, '_RONDA', {})
    monkeypatch.setattr(tw, '_CREDITOS_GUERRA', {})
    enviados = []
    p = NS(char_id=1, entity_id=1, nombre='Baco', creditos=0, rango=1, pvp_kills=0)
    ses = NS(personaje=p, usuario=None, enviar=lambda *x: enviados.extend(x))
    pvp_liga._contar_baja(ses, p, NS(nivel=60, char_id=2))
    pvp_liga._contar_baja(ses, p, NS(nivel=60, char_id=2))
    ko = [x for x in enviados if x[:2] == b'\x1d\x00' and x[7] == 25][-1]
    ronda, amarillo = struct.unpack_from('<II', ko, 8)
    assert (ronda, amarillo) == (2, 300 + 120)
