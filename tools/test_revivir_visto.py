"""Al revivir, los demas del mapa lo ven de pie (05/11/2026).

"sale disque muerto pero sale vivo": Impacty murio, siguio como alma y revivio en el mismo mapa; los demas le veian
tirado en el suelo con la vida llena. Al presentarlo de nuevo hace falta el 0x000A "de pie" ademas del spawn.
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import login  # noqa: E402
import presencia  # noqa: E402


def _ses(nombre, recibido):
    p = login.Personaje(hp=0, hp_max=1000, mp=0, mp_max=500)
    p.nombre, p.stage, p.tile_x, p.tile_y = nombre, 41, 100, 100
    return NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={20: 1234}, cantidades={20: 1},
              usuario=None, muerto=False, fantasma=False,
              enviar=lambda *pk: recibido.extend(pk), enviar_inmediato=lambda *pk: recibido.extend(pk))


def _de_pie(paquetes, eid):
    return [x for x in paquetes if x[:2] == struct.pack('<H', 0x000A) and struct.unpack_from('<III', x, 2) == (eid, 0, 0)]


def test_el_pergamino_de_revivir_lo_levanta_para_los_demas(monkeypatch):
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    monkeypatch.setattr(app, '_refrescar', lambda *a: [])
    presencia._POR_MAPA.clear()
    a_ve, b_ve = [], []
    a, b = _ses('Impacty', a_ve), _ses('Lovebb', b_ve)
    a.muerto = a.fantasma = True
    presencia._POR_MAPA[41] = [a, b]
    app._usar_pergamino_revivir(a, 't', 20, 100)
    assert not a.muerto and a.personaje.hp == 1000
    assert _de_pie(b_ve, presencia.entidad_de(a))           # Lovebb lo ve levantarse
    b_ve.clear()
    presencia.entrar(a, 41)                                 # y solo una vez: un cambio de mapa normal no lo repite
    assert not _de_pie(b_ve, presencia.entidad_de(a))
