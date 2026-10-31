"""El puesto de venta se abre donde ESTA el personaje, no en el destino de su ultimo paso."""
import pathlib
import sys
from types import SimpleNamespace

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app


def _ses(tramo, destino):
    p = SimpleNamespace(tile_x=destino[0], tile_y=destino[1], buffs={})
    return SimpleNamespace(personaje=p, _ultimo_tramo=tramo, inventario={})


def test_a_mitad_de_camino_cuenta_por_donde_va():
    # De (100,40) a (110,40) a speed 110 = 275 px/s: en 0,58 s lleva 160 px = 5 casillas.
    ses = _ses((1000.0, 100 * 32, 40 * 32, 110 * 32, 40 * 32, 110), (110, 40))
    assert app.posicion_actual(ses, ahora=1000.0) == (100, 40)
    assert app.posicion_actual(ses, ahora=1000.0 + 160 / 275) == (105, 40)
    assert app.posicion_actual(ses, ahora=1010.0) == (110, 40)


def test_sin_tramo_o_con_tramo_viejo_vale_la_casilla_del_personaje():
    assert app.posicion_actual(_ses(None, (7, 8))) == (7, 8)
    # El destino cambio por otro camino (un salto, un portal): el tramo guardado ya no sirve.
    viejo = (1000.0, 0, 0, 320, 0, 110)
    assert app.posicion_actual(_ses(viejo, (50, 50)), ahora=1000.1) == (50, 50)
