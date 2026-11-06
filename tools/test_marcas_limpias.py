"""Fuera de Totem War / Holy / Arena, al presentar a un jugador se le apagan el aura de Arena, la marca hostil y el equipo
de Holy (05/11/2026: "a veces cuando salgo un mapa a otro me sale ese aro ... como si estuviera activa la totem war o
si estuviera dentro de la hb"). entidad_de reutiliza ids y el cliente guarda esas marcas pegadas al id."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import login  # noqa: E402
import presencia  # noqa: E402


def _ses(nombre, stage, x):
    p = login.Personaje(hp=100, hp_max=100, mp=10, mp_max=10)
    p.nombre, p.stage, p.tile_x, p.tile_y, p.buffs = nombre, stage, x, 100, {}
    rec = []
    return NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, cantidades={}, usuario=None,
              muerto=False, recibido=rec, enviar=lambda *pk, r=rec: r.extend(pk),
              enviar_inmediato=lambda *pk, r=rec: r.extend(pk))


def _apagadas(eid):
    return {struct.pack('<HIBBII', 0x001D, eid, 1, 36, 0, 0), struct.pack('<HIBBII', 0x001D, eid, 1, 38, 1, 0)}


def _hostil_apagada(eid, recibido):
    # la cabecera de la 42 la reescribe para_receptor; lo que cuenta es el actor y el 0
    return any(len(x) == 16 and x[:2] == struct.pack('<H', 0x001D) and x[7] == 42
               and struct.unpack_from('<II', x, 8) == (eid, 0) for x in recibido)


def test_al_cambiar_de_mapa_los_demas_salen_sin_aro():
    presencia._POR_MAPA.clear()
    a, b = _ses('Impacty', 41, 100), _ses('Zetha', 41, 101)
    presencia.entrar(a, 41)
    presencia.entrar(b, 41)
    ea, eb = presencia.entidad_de(a), presencia.entidad_de(b)
    assert _apagadas(ea) <= set(b.recibido) and _hostil_apagada(ea, b.recibido)   # el que llega ve al otro sin aro
    assert _apagadas(eb) <= set(a.recibido) and _hostil_apagada(eb, a.recibido)   # y al reves


def test_en_holy_no_se_apagan():
    a = _ses('Impacty', 112, 100)
    assert presencia.marcas_limpias(a) == ()
