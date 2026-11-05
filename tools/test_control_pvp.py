"""Binding y Silence en PvP (05/11/2026: "Binding y silence no funciona").

Las dos son solo de jugadores y no hacen dano: Binding (捆綁) ralentiza y Silence (沉默) no deja usar habilidades.
pvp_liga solo hacia dano y no aplicaba nada.
"""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import combate as cb  # noqa: E402
import login  # noqa: E402
import pvp_liga  # noqa: E402
import presencia  # noqa: E402

BINDING_V, SILENCE_I = 80, 914


def _par(monkeypatch, reloj):
    monkeypatch.setattr(app.time, 'time', lambda: reloj[0])
    monkeypatch.setattr(pvp_liga, 'permitido', lambda a, b: True)
    monkeypatch.setattr(pvp_liga.cuentas, 'guardar_progreso', lambda *a, **k: None)
    presencia._POR_MAPA.clear()
    lados = []
    for nombre, x in (('Baco', 100), ('Pipe', 101)):
        p = login.Personaje(hp=5000, hp_max=5000, mp=5000, mp_max=5000)
        p.nombre, p.stage, p.tile_x, p.tile_y, p.buffs = nombre, 47, x, 100, {}
        recibido = []
        s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={}, cantidades={}, usuario=None,
               muerto=False, sp=5000, monstruos={}, recibido=recibido,
               enviar=lambda *pk, r=recibido: r.extend(pk), enviar_inmediato=lambda *pk, r=recibido: r.extend(pk))
        lados.append(s)
    presencia._POR_MAPA[47] = list(lados)
    return lados


def test_estados_de_control():
    assert pvp_liga.estado_de_control(BINDING_V) == 'atado'
    assert pvp_liga.estado_de_control(SILENCE_I) == 'silenciado'
    assert pvp_liga.estado_de_control(601) is None                 # Slicing Hit: dano normal


def test_binding_ralentiza_al_rival(monkeypatch):
    reloj = [1000.0]
    a, b = _par(monkeypatch, reloj)
    antes = app._velocidad_de(b)
    assert pvp_liga.atacar(a, b, BINDING_V, cb.datos_magia(BINDING_V), 0)
    assert b.personaje.hp == 5000                                   # sin dano
    assert app._velocidad_de(b) < antes
    assert [x for x in b.recibido if x[:2] == struct.pack('<H', 0x001D) and x[7] == 4]      # icono en el rival
    reloj[0] += 13                                                  # Binding V dura 12 s
    assert app._velocidad_de(b) == antes


def test_silence_no_deja_lanzar_habilidades(monkeypatch):
    reloj = [1000.0]
    a, b = _par(monkeypatch, reloj)
    assert pvp_liga.atacar(a, b, SILENCE_I, cb.datos_magia(SILENCE_I), 0)
    assert pvp_liga.tiene_estado(b, 'silenciado')
    mp = b.personaje.mp
    app.Servidor.__new__(app.Servidor).manejar(b, 0x0006, None, None, 't', struct.pack('<HI', 202, b.entity_id))
    assert b.personaje.mp == mp                                     # Charming Blessing no salio
    reloj[0] += 5                                                   # Silence I dura 4 s
    assert not pvp_liga.tiene_estado(b, 'silenciado')
