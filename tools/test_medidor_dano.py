"""El contador de dano en vivo (server/medidor_dano.py)."""
import pathlib
import struct
import sys
from types import SimpleNamespace

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import contador_dano
import equipos
import medidor_dano as md


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    monkeypatch.setattr(md, '_NOMBRES', {})
    monkeypatch.setattr(md, '_PELEAS', {})
    monkeypatch.setattr(md, '_OBJETIVO', {})
    monkeypatch.setattr(equipos, '_DE_QUIEN', {})


def _ses(cid, nombre):
    enviados = []
    s = SimpleNamespace(personaje=SimpleNamespace(char_id=cid, nombre=nombre), enviados=enviados)
    s.enviar = lambda *pk: enviados.extend(pk)
    s.volcar = lambda: None
    return s


class Bicho:
    def __init__(self, nombre='Slime', hp=100):
        self.nombre, self.hp, self.dano_por, self.muerto_en, self.npc_type = nombre, hp, {}, 0, 1


def test_solo_cuenta_tu_dano_y_el_dps():
    s = _ses(1, 'Impacty')
    md.anotar(s, Bicho(), 300, ahora=100.0)
    md.anotar(s, Bicho(), 200, ahora=110.0)
    titulo, filas = md.vista(s, ahora=110.0)
    assert titulo == 'You  10s  DPS 50' and filas == [['Impacty', '500', 100]]


def test_la_party_suma_a_todos_con_su_porcentaje():
    a, b = _ses(1, 'Impacty'), _ses(2, 'Baco')
    equipos._DE_QUIEN.update({1: 1, 2: 1})
    md.anotar(a, Bicho(), 300, ahora=100.0)
    md.anotar(b, Bicho(), 100, ahora=104.0)
    titulo, filas = md.vista(b, ahora=104.0)
    assert titulo.startswith('Party') and filas == [['Impacty', '300', 75], ['Baco', '100', 25]]


def test_tras_la_pausa_la_pelea_empieza_de_cero():
    s = _ses(1, 'Impacty')
    md.anotar(s, Bicho(), 300, ahora=100.0)
    md.anotar(s, Bicho(), 50, ahora=100.0 + md.PAUSA_PELEA + 1)
    assert md.vista(s)[1] == [['Impacty', '50', 100]]


def test_con_un_jefe_sale_su_ranking(monkeypatch):
    monkeypatch.setattr(contador_dano, 'es_jefe', lambda m: m.nombre == 'Moowad')
    a, b = _ses(1, 'Impacty'), _ses(2, 'Baco')
    jefe = Bicho('Moowad', hp=5000)
    jefe.dano_por = {1: 900, 2: 2700}
    md._NOMBRES.update({1: 'Impacty', 2: 'Baco'})
    md.anotar(a, jefe, 900, ahora=100.0)
    titulo, filas = md.vista(a, ahora=101.0)
    assert titulo == 'Moowad' and filas == [['Baco', '2,700', 75], ['Impacty', '900', 25]]
    jefe.hp, jefe.muerto_en = 0, 102.0
    assert md.vista(a, ahora=110.0)[0] == 'Moowad (defeated)'
    assert md.vista(a, ahora=102.0 + md.JEFE_TRAS_MORIR + 1)[0].startswith('You')


def test_sin_dano_lo_dice():
    assert md.vista(_ses(1, 'Impacty')) == ('Hit something to start.', [])


def test_el_boton_abre_y_cierra_y_la_x_solo_para_el_envio():
    s = _ses(1, 'Impacty')
    assert md.procesar(s, struct.pack('<BII', md.CMD_MEDIDOR, 1, 0)) and md.abierto(s)
    assert b'function MedidorDatos' in s.enviados[0] and s.enviados[1][2:-1] == b'MedidorAbrir()'
    md.procesar(s, struct.pack('<BII', md.CMD_MEDIDOR, 1, 0))
    assert not md.abierto(s) and s.enviados[-1][2:-1] == b'MedidorCerrar()'
    md.procesar(s, struct.pack('<BII', md.CMD_MEDIDOR, 1, 0))
    n = len(s.enviados)
    md.procesar(s, struct.pack('<BII', md.CMD_MEDIDOR, 0, 0))      # cerrada con la X
    assert not md.abierto(s) and len(s.enviados) == n
    assert not md.procesar(s, struct.pack('<BII', 161, 0, 1))
