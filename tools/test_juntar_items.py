"""Soltar un monton sobre otro del mismo objeto los junta (05/11/2026: "los items deja separarlos pero no juntarlos").

El 0x0012 con el destino ocupado siempre intercambiaba las casillas, aunque fuera el mismo objeto apilable.
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import login  # noqa: E402

POCION = 2003


def _ses(bolsa, cantidades):
    p = login.Personaje()
    return NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario=dict(bolsa), cantidades=dict(cantidades),
              usuario=None, muerto=False, enviar=lambda *a: None, enviar_inmediato=lambda *a: None)


def test_juntar_dos_montones(monkeypatch):
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    s = _ses({26: POCION, 100: POCION}, {26: 5, 100: 7})
    app.Servidor.__new__(app.Servidor).manejar(s, 0x0012, None, None, 't', struct.pack('<HH', 100, 26))
    assert 100 not in s.inventario and s.inventario[26] == POCION and app._cant_de(s, 26) == 12


def test_objetos_distintos_se_intercambian(monkeypatch):
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    s = _ses({26: POCION, 27: 2002}, {26: 5, 27: 3})
    app.Servidor.__new__(app.Servidor).manejar(s, 0x0012, None, None, 't', struct.pack('<HH', 27, 26))
    assert s.inventario[26] == 2002 and s.inventario[27] == POCION
