"""Cambio de rama en el Skill Angel (0x002F contenedor 10): gratis por debajo del nivel 20;
desde el 20 cuesta un Skill Crystal (2025/2028, "Changes the skill for Lvl 20+ characters."
en item.xml), que se gasta. Antes no habia ningun limite de nivel.
Reportado por el usuario: "El Skill angel no limita el cambio de skill a lvl 20" y "al tener
un skill cristal y ser +lvl 20 si me debe dejar cambiar"."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import login

SWORD_A_AXE = bytes([10]) + struct.pack('<II', 9, 10)


def _cambiar(nivel, inventario=None, cantidades=None):
    p = login.Personaje()
    p.nivel = nivel
    p.habilidades = [(1, 40, 0), (9, 1, 0)]   # Life + Sword
    s = NS(personaje=p, rol='mundo', entity_id=1001, inventario=dict(inventario or {}),
           cantidades=dict(cantidades or {}), instancias={}, usuario=None,
           enviar=lambda *pk: None, enviar_inmediato=lambda *pk: None)
    app.Servidor.__new__(app.Servidor).manejar(s, 0x002F, None, None, 'test', SWORD_A_AXE)
    return {h[0] for h in p.habilidades}, s


def test_por_debajo_del_20_es_gratis():
    ramas, _ = _cambiar(19)
    assert ramas == {1, 10}


def test_desde_el_20_sin_cristal_no_deja():
    ramas, _ = _cambiar(20)
    assert ramas == {1, 9}
    ramas, _ = _cambiar(150)
    assert ramas == {1, 9}


def test_desde_el_20_con_cristal_deja_y_lo_gasta():
    ramas, s = _cambiar(150, {25: 2025})
    assert ramas == {1, 10}
    assert 25 not in s.inventario


def test_el_otro_cristal_tambien_vale_y_solo_se_gasta_uno():
    ramas, s = _cambiar(60, {30: 2028}, {30: 3})
    assert ramas == {1, 10}
    assert s.inventario.get(30) == 2028 and app._cant_de(s, 30) == 2


def test_si_el_cambio_se_rechaza_el_cristal_no_se_gasta():
    p = login.Personaje()
    p.nivel = 150
    p.habilidades = [(1, 40, 0), (9, 1, 0)]   # Life + Sword
    s = NS(personaje=p, rol='mundo', entity_id=1001, inventario={25: 2025},
           cantidades={}, instancias={}, usuario=None,
           enviar=lambda *pk: None, enviar_inmediato=lambda *pk: None)
    # Sword -> Wraith: excluye con Life, se rechaza
    app.Servidor.__new__(app.Servidor).manejar(
        s, 0x002F, None, None, 'test', bytes([10]) + struct.pack('<II', 9, 2))
    assert {h[0] for h in p.habilidades} == {1, 9}
    assert s.inventario.get(25) == 2025
