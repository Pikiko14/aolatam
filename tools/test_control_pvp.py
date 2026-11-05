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


def test_la_mascota_va_a_por_el_jugador_que_ataca_el_dueno(monkeypatch):
    """"los pets no reaccionan al atacar a los jugadores, solo a los mobs"."""
    reloj = [1000.0]
    a, b = _par(monkeypatch, reloj)
    a.pet_entity_id = 1069500
    f_pet = {'fuera': True, 'x': 100, 'y': 101, 'atk': 800, 'agilidad': 15, 'saciedad': 50, 'nombre': 'Ape'}
    a.personaje.mascota = f_pet
    assert not app._pet_contra_rival(a, f_pet, a.pet_entity_id, reloj[0])      # aun no hay rival
    pvp_liga.atacar(a, b, cb.ATAQUE_NORMAL, {}, 0)
    vida = b.personaje.hp
    reloj[0] += 2
    assert app._pet_contra_rival(a, f_pet, a.pet_entity_id, reloj[0])
    assert b.personaje.hp < vida                                                 # le pego la mascota
    # lejos: primero se acerca
    f_pet.update({'x': 106, 'y': 106, 'proximo_paso': 0})
    reloj[0] += 2
    vida = b.personaje.hp
    assert app._pet_contra_rival(a, f_pet, a.pet_entity_id, reloj[0])
    assert b.personaje.hp == vida and (f_pet['x'], f_pet['y']) != (106, 106)


def _con_mascota(s, eid, x, skills):
    f = {'fuera': True, 'x': x, 'y': 101, 'atk': 800, 'matk': 800, 'dfs': 50, 'mdef': 50, 'agilidad': 15,
         'saciedad': 50, 'nombre': 'Ape', 'hp': 3000, 'hp_max': 3000, 'skills': skills, 'ranura': 30}
    s.pet_entity_id = eid
    s.personaje.mascota = f
    s.personaje.mascotas = {'30': f}
    return f


def test_la_mascota_usa_sus_poderes_contra_jugadores(monkeypatch):
    """"los pet no lanzan poderes"."""
    reloj = [1000.0]
    a, b = _par(monkeypatch, reloj)
    f = _con_mascota(a, 1069500, 100, [601])                    # Slicing Hit I
    monkeypatch.setattr(app.random, 'random', lambda: 0.0)
    pvp_liga.atacar(a, b, cb.ATAQUE_NORMAL, {}, 0)
    a.recibido.clear()
    reloj[0] += 2
    app._pet_contra_rival(a, f, 1069500, reloj[0])
    golpes = [x for x in a.recibido if x[:2] == struct.pack('<H', 0x000B)]
    assert any(struct.unpack_from('<H', x, 10)[0] == 601 for x in golpes) or 601 in f['cd_skills']


def test_las_mascotas_se_pegan_entre_si(monkeypatch):
    """"no atacan entre si en pvp si hay 2 pet"."""
    reloj = [1000.0]
    a, b = _par(monkeypatch, reloj)
    monkeypatch.setattr(app, '_refrescar', lambda *x: [])
    monkeypatch.setattr(app.random, 'random', lambda: 0.99)    # golpe basico
    fa = _con_mascota(a, 1069500, 100, [])
    fb = _con_mascota(b, 1069501, 101, [])
    pvp_liga.atacar(a, b, cb.ATAQUE_NORMAL, {}, 0)
    vida_b = b.personaje.hp
    reloj[0] += 2
    app._pet_contra_rival(a, fa, 1069500, reloj[0])
    assert fb['hp'] < 3000 and b.personaje.hp == vida_b       # le pego a la mascota, no al dueno
    fb['hp'] = 1
    reloj[0] += 2
    app._pet_contra_rival(a, fa, 1069500, reloj[0])
    assert not fb['fuera'] and b.pet_entity_id is None          # cae y se guarda
