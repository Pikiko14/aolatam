"""Muerto (como alma) se puede sentar y comerciar (05/11/2026: "cuando estoy muerto no me deja sentar ni aceptar trade")."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import login  # noqa: E402
import presencia  # noqa: E402


def _ses(nombre):
    p = login.Personaje(hp=0, hp_max=1000)
    p.nombre, p.stage, p.tile_x, p.tile_y = nombre, 41, 100, 100
    r = []
    return NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, cantidades={}, usuario=None,
              muerto=True, fantasma=True, recibido=r, enviar=lambda *pk: r.extend(pk),
              enviar_inmediato=lambda *pk: r.extend(pk), volcar=lambda: None)


def test_el_alma_se_sienta():
    s = _ses('Baco')
    app.Servidor.__new__(app.Servidor).manejar(s, 0x0016, None, None, 't', struct.pack('<BI', 4, 0))
    assert s.sentado


def test_muerto_sin_ser_alma_sigue_sin_sentarse():
    s = _ses('Baco')
    s.fantasma = False
    app.Servidor.__new__(app.Servidor).manejar(s, 0x0016, None, None, 't', struct.pack('<BI', 4, 0))
    assert not getattr(s, 'sentado', False)


def test_muerto_acepta_el_intercambio():
    a, b = _ses('Pipe'), _ses('Baco')
    a.muerto = a.fantasma = False
    b.trade_invita = a
    app._intercambio(b, 't', 0x002C, b'')
    assert getattr(b, 'trade', None) and b.trade['socio'] is a
