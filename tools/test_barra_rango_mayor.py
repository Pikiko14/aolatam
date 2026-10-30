"""Aprendido Basic Attack II (812), la barra F1..F12 seguia mostrando el I (801): el servidor
la guarda y la devuelve tal cual al entrar (0x005B). Ahora cada hechizo de la barra sube al
rango mas alto aprendido de su linea. Reportado: "el rango 2 no tapa al 1" (caso real del log
del VPS: pergamino 2542 -> 812, y despues reconecto)."""
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import login
import skills

BASIC_ATTACK_I, BASIC_ATTACK_II, BLOODY_SONG_I, MORTERO = 801, 812, 802, 47382


def test_rango_mayor_de():
    assert skills.rango_mayor_de(BASIC_ATTACK_I, {BASIC_ATTACK_II}) == BASIC_ATTACK_II
    assert skills.rango_mayor_de(BLOODY_SONG_I, {BASIC_ATTACK_II}) == BLOODY_SONG_I
    assert skills.rango_mayor_de(BASIC_ATTACK_II, {BASIC_ATTACK_I}) == BASIC_ATTACK_II


def test_al_entrar_la_barra_lleva_el_rango_aprendido():
    p = login.Personaje()
    p.barra = [[1, BASIC_ATTACK_I], [1, BLOODY_SONG_I], [2, MORTERO]]
    p.hechizos_aprendidos = {BASIC_ATTACK_II}
    pk = login._barra(p, b'')
    assert pk.find(struct.pack('<I', BASIC_ATTACK_II)) >= 0
    assert pk.find(struct.pack('<I', BASIC_ATTACK_I)) < 0
    assert pk.find(struct.pack('<I', BLOODY_SONG_I)) >= 0
    assert pk.find(struct.pack('<I', MORTERO)) >= 0          # los objetos no se tocan


def test_al_aprender_con_pergamino_la_barra_cambia_ya():
    from types import SimpleNamespace as NS
    import app
    p = login.Personaje()
    p.nivel = 50
    p.habilidades = [(11, 50, 0)]             # Spear
    p.barra = [[1, BASIC_ATTACK_I], [1, BLOODY_SONG_I]]
    packets = []
    s = NS(personaje=p, rol='mundo', entity_id=p.entity_id, inventario={20: 2542},
           cantidades={}, instancias={}, usuario=None,
           enviar=lambda *pk: packets.extend(pk), enviar_inmediato=lambda *pk: packets.extend(pk))
    app.Servidor.__new__(app.Servidor).manejar(s, 0x002E, None, None, 'test', struct.pack('<I', 20))
    assert BASIC_ATTACK_II in p.hechizos_aprendidos
    assert p.barra == [[1, BASIC_ATTACK_II], [1, BLOODY_SONG_I]]
    assert any(pk[:2] == struct.pack('<H', 0x005B) for pk in packets)


def test_sin_rango_nuevo_la_barra_queda_igual():
    p = login.Personaje()
    p.barra = [[1, BASIC_ATTACK_I]]
    assert login._barra(p, b'').find(struct.pack('<I', BASIC_ATTACK_I)) >= 0
