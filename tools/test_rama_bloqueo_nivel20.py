"""El Skill Angel (cambio de rama, 0x002F contenedor 10) no limitaba el
cambio de rama a ningun nivel: se podia seguir cambiando de clase pasado el
nivel 20. Reportado por el usuario: "El Skill angel no limita el cambio de
skill a lvl 20 si excedo me deja cambiar"."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import login


def _sesion(nivel):
    p = login.Personaje()
    p.nivel = nivel
    p.habilidades = [(1, 40, 0), (9, 1, 0)]   # Life + Sword
    return NS(personaje=p, rol='mundo', entity_id=1001, inventario={}, usuario=None,
              enviar=lambda *pk: None, enviar_inmediato=lambda *pk: None), p


def test_pasado_el_nivel_20_no_deja_cambiar_de_rama():
    s, p = _sesion(nivel=21)
    server = app.Servidor.__new__(app.Servidor)
    cuerpo = bytes([10]) + struct.pack('<II', 9, 10)   # Sword -> Axe
    server.manejar(s, 0x002F, None, None, 'test', cuerpo)
    assert {h[0] for h in p.habilidades} == {1, 9}


def test_antes_del_nivel_20_sigue_dejando_cambiar():
    s, p = _sesion(nivel=20)
    server = app.Servidor.__new__(app.Servidor)
    cuerpo = bytes([10]) + struct.pack('<II', 9, 10)   # Sword -> Axe
    server.manejar(s, 0x002F, None, None, 'test', cuerpo)
    assert {h[0] for h in p.habilidades} == {1, 10}
