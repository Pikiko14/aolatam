"""Las once reglas de exclusion entre ramas de habilidad (Life<->Wraith,
Chaos<->Earth, Meditate<->Enhance, Grapple<->Snipe, Mantle/Garment/Vestment).

El servidor nunca las comprobaba (solo se negaba el selector del cliente, y
con configuracion.RAMAS_SIN_EXCLUSION ni eso): se podia llevar Life y Wraith
a la vez. Pedido por el usuario: "me deja usar life con wraith, habilita la
validacion de restriciones que hay entre las clases".
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import clases
import login
import skills


def test_rama_en_conflicto_detecta_los_pares_y_el_trio():
    assert skills.rama_en_conflicto([1], 2) == 1          # Life <-> Wraith
    assert skills.rama_en_conflicto([2], 1) == 2
    assert skills.rama_en_conflicto([3], 4) == 3          # Chaos <-> Earth
    assert skills.rama_en_conflicto([6], 12) == 6         # Meditate <-> Enhance
    assert skills.rama_en_conflicto([13], 18) == 13       # Grapple <-> Snipe
    assert skills.rama_en_conflicto([32], 33) == 32       # Mantle/Garment/Vestment
    assert skills.rama_en_conflicto([33], 34) == 33
    # Acepta tanto ids sueltos como (sid, nivel, exp)
    assert skills.rama_en_conflicto([(1, 40, 0)], 2) == 1
    # Sin conflicto
    assert skills.rama_en_conflicto([1], 9) is None       # Life + Sword: ok
    assert skills.rama_en_conflicto([], 1) is None


def test_eleccion_de_clase_rechaza_life_y_wraith(monkeypatch):
    s = NS(personaje=login.Personaje(), rol='mundo', entity_id=1001,
           inventario={}, usuario=None,
           enviar=lambda *pk: None, enviar_inmediato=lambda *pk: None)
    server = app.Servidor.__new__(app.Servidor)
    cuerpo = bytes([1, 2, 0, 0, 0, 0])   # Life + Wraith a la vez
    server.manejar(s, 0x003A, None, None, 'test', cuerpo)
    assert s.personaje.habilidades == []


def test_eleccion_de_clase_normal_sigue_funcionando():
    """Sword + Life no es un par excluyente: tiene que pasar la validacion
    nueva y llegar al resto del handler (que aqui, sin el resto del fixture
    de una sesion real -- cuentas, inventario completo, etc. -- revienta mas
    adelante por falta de ese contexto; eso ya pasaba antes de este cambio y
    no es lo que se prueba aqui). Si la validacion rechazara el par bueno,
    volveria enseguida con las habilidades vacias y SIN excepcion -- lo que
    distingue este caso del de Life+Wraith de arriba."""
    import pytest
    s = NS(personaje=login.Personaje(), rol='mundo', entity_id=1001,
           inventario={}, usuario=None,
           enviar=lambda *pk: None, enviar_inmediato=lambda *pk: None)
    server = app.Servidor.__new__(app.Servidor)
    cuerpo = bytes([9, 1, 0, 0, 0, 0])   # Sword + Life: una de arma y una de magia
    with pytest.raises(UnboundLocalError):
        server.manejar(s, 0x003A, None, None, 'test', cuerpo)


def test_cambio_de_rama_rechaza_quedarse_con_un_par_excluyente():
    p = login.Personaje()
    p.habilidades = [(1, 40, 0), (9, 1, 0)]   # Life + Sword
    s = NS(personaje=p, rol='mundo', entity_id=1001, inventario={}, usuario=None,
           enviar=lambda *pk: None, enviar_inmediato=lambda *pk: None)
    server = app.Servidor.__new__(app.Servidor)
    # Intenta sacar Sword(9) para meter Wraith(2): se queda Life+Wraith -> rechazado
    cuerpo = bytes([10]) + struct.pack('<II', 9, 2)
    server.manejar(s, 0x002F, None, None, 'test', cuerpo)
    assert {h[0] for h in p.habilidades} == {1, 9}


def test_cambio_de_rama_normal_sigue_funcionando():
    p = login.Personaje()
    p.habilidades = [(1, 40, 0), (9, 1, 0)]   # Life + Sword
    s = NS(personaje=p, rol='mundo', entity_id=1001, inventario={}, usuario=None,
           enviar=lambda *pk: None, enviar_inmediato=lambda *pk: None)
    server = app.Servidor.__new__(app.Servidor)
    # Sacar Sword(9) y meter Axe(10): sin conflicto
    cuerpo = bytes([10]) + struct.pack('<II', 9, 10)
    server.manejar(s, 0x002F, None, None, 'test', cuerpo)
    assert {h[0] for h in p.habilidades} == {1, 10}
