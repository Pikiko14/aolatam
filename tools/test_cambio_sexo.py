"""Gender Bolus (0x0016 accion 0x24) y Master's Love (04/11/2026)."""
import pathlib
import struct
import sys
from types import SimpleNamespace

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import app  # noqa: E402
import cambio_sexo  # noqa: E402
import login  # noqa: E402


def _ses(apariencia, bolsa):
    paquetes = []
    p = login.Personaje(nombre='Prueba')
    p.apariencia = apariencia
    s = SimpleNamespace(personaje=p, inventario=dict(bolsa), cantidades={}, usuario=None, addr='t',
                        enviar=lambda *pk: paquetes.extend(pk), enviar_inmediato=lambda *pk: paquetes.extend(pk))
    return s, paquetes


def _atributos(paquetes):
    return [struct.unpack_from('<HIIB', pk)[1:] for pk in paquetes
            if isinstance(pk, (bytes, bytearray)) and pk[:2] == b'\x13\x00' and len(pk) >= 11]


def test_cambia_de_hombre_a_mujer_y_gasta_el_bolus(monkeypatch):
    monkeypatch.setattr(app, '_refrescar', lambda ses, r, **k: [])
    monkeypatch.setattr(cambio_sexo, 'log', SimpleNamespace(info=lambda *a: None))
    import presencia
    monkeypatch.setattr(presencia, 'notificar_equipo', lambda ses: None)
    s, pk = _ses([1, 5, 1, 8, 8], {30: 7032})
    assert cambio_sexo.procesar(s, 30)
    assert s.personaje.apariencia[:2] == [0, 0]
    assert 30 not in s.inventario


def test_sin_el_objeto_no_cambia(monkeypatch):
    s, pk = _ses([1, 5, 1, 8, 8], {30: 3376})
    assert not cambio_sexo.procesar(s, 30)
    assert s.personaje.apariencia[0] == 1


def test_con_ropa_del_sexo_contrario_puesta_no_cambia(monkeypatch):
    # 5657 Spy Business Suit (F) puesta en una mujer que pasaria a hombre
    s, pk = _ses([0, 5, 1, 8, 8], {30: 7032, 168: 5657})
    assert cambio_sexo.equipo_que_no_vale(s.inventario, True) == [168]
    assert not cambio_sexo.procesar(s, 30)
    assert s.personaje.apariencia[0] == 0 and 30 in s.inventario


def test_masters_love_no_es_pocion():
    assert app.ITEM_MASTERS_LOVE == 3382
