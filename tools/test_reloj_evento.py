"""El reloj grande de evento (0x016A) se quita al estar fuera del evento (02/11/2026)."""
import pathlib
import struct
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import daily_events


def test_fuera_del_evento_se_quita_el_reloj_una_vez():
    enviados = []
    s = SimpleNamespace(_reloj_evento=True, enviar=lambda *p: enviados.extend(p))
    daily_events.quitar_reloj(s)
    daily_events.quitar_reloj(s)
    assert enviados == [struct.pack('<H', 0x16b)] and not s._reloj_evento


def test_sin_reloj_no_se_manda_nada():
    enviados = []
    daily_events.quitar_reloj(SimpleNamespace(enviar=lambda *p: enviados.extend(p)))
    assert enviados == []
