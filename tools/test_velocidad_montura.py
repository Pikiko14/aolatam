"""La velocidad al montar respeta el move_speed del item: BONO_MONTURA ya no lo pisa.

Antes BONO_MONTURA valia 150 fijo (a peticion del usuario), asi que CUALQUIER montura
corria igual de rapido sin importar lo que dijera item.xml. El usuario pidio que cada
montura de el % que declara, asi que el bono por defecto pasa a 0.
"""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app


def _sesion():
    return NS(personaje=NS(buffs={}), inventario={app.RANURA_MONTURA: 90001})


def test_bono_montura_es_cero_por_defecto():
    assert app.BONO_MONTURA == 0, 'BONO_MONTURA deberia respetar item.xml por defecto'


def test_la_velocidad_usa_el_porcentaje_de_la_montura_sin_pisarlo(monkeypatch):
    import inventario as inv
    monkeypatch.setattr(app, 'BONO_MONTURA', 0)
    for pct in (50, 60, 120):
        monkeypatch.setattr(inv, 'velocidad_de_montura',
                            lambda item_id, pct=pct: pct if item_id == 90001 else 0)
        ses = _sesion()
        esperado = max(1, min(1000, int(round(app.VELOCIDAD_JUGADOR * (100 + pct) / 100.0))))
        assert app._velocidad_de(ses) == esperado, pct


def test_un_bono_distinto_de_cero_sigue_pisando_la_montura_de_verdad(monkeypatch):
    """BONO_MONTURA no desaparece: solo su valor por defecto cambio. Quien lo quiera
    encender (AO_MONTURA_BONO) sigue pudiendo pisar move_speed, igual que antes."""
    import inventario as inv
    monkeypatch.setattr(app, 'BONO_MONTURA', 150)
    monkeypatch.setattr(inv, 'velocidad_de_montura', lambda item_id: 50 if item_id == 90001 else 0)
    ses = _sesion()
    esperado = max(1, min(1000, int(round(app.VELOCIDAD_JUGADOR * (100 + 150) / 100.0))))
    assert app._velocidad_de(ses) == esperado
