"""Mejoras de rendimiento: checksum plegado, volcar() agrupado y progreso diferido."""
import asyncio
import json
import os
import random
import sqlite3
import struct
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'proto'))
sys.path.insert(0, str(RAIZ / 'server'))
import framing
import cuentas
from session import Session


def _checksum_palabra_a_palabra(payload, length):
    v = 0xD31F
    for i in range(0, min(length & ~1, len(payload)), 2):
        v ^= struct.unpack_from('<H', payload, i)[0]
    v &= 0xFFFF
    s = v & 0xF
    if s:
        v = ((v << s) | (v >> (16 - s))) & 0xFFFF
    return (v & 0xFF) ^ ((v >> 8) & 0xFF)


def test_checksum_plegado_da_lo_mismo_que_palabra_a_palabra():
    r = random.Random(7)
    for _ in range(3000):
        n = r.randrange(0, 2000)
        b = r.randbytes(n)
        largo = r.choice([n, max(0, n - r.randrange(4))])
        assert framing.checksum(b, largo) == _checksum_palabra_a_palabra(b, largo)


class _Writer:
    def __init__(self):
        self.escrituras = []

    def write(self, b):
        self.escrituras.append(bytes(b))

    def is_closing(self):
        return False


def _sesion():
    ses = Session.__new__(Session)
    ses.salida = []
    ses.rol = 'login'
    ses.mapa_cargando = False
    ses._mapa_ui_diferida = []
    ses.writer = _Writer()
    return ses


def test_varios_envios_inmediatos_salen_en_una_escritura_y_en_orden():
    ses = _sesion()

    async def turno():
        for i in range(5):
            ses.enviar_inmediato(struct.pack('<HI', 0x0099, i))
        assert ses.writer.escrituras == []          # todavia en la misma vuelta
        await asyncio.sleep(0)
    asyncio.run(turno())
    assert len(ses.writer.escrituras) == 1
    esperado = b''.join(framing.build_frame(framing.pack_submessages([struct.pack('<HI', 0x0099, i)]), 1)
                        for i in range(5))
    assert ses.writer.escrituras[0] == esperado


def test_sin_bucle_volcar_escribe_en_el_acto():
    ses = _sesion()
    ses.enviar_inmediato(struct.pack('<H', 0x0099))
    assert len(ses.writer.escrituras) == 1


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(cuentas, 'DB_PATH', tmp_path / 'accounts.db')
    monkeypatch.setattr(cuentas, '_notificar_cambio', lambda **kw: None)
    monkeypatch.setattr(cuentas, 'ESPERA_PROGRESO', 3600)       # que no lo vacie el hilo
    with sqlite3.connect(cuentas.DB_PATH) as c:
        c.execute('CREATE TABLE cuentas(usuario TEXT PRIMARY KEY COLLATE NOCASE, password TEXT)')
        c.execute('CREATE TABLE personajes(usuario TEXT COLLATE NOCASE,char_id INTEGER,ranura INTEGER,'
                  'nombre TEXT,datos TEXT,actualizado_en TIMESTAMP,PRIMARY KEY(usuario,ranura))')
    p = {'nombre': 'Rapido', 'ranura': 0, 'nivel': 1, 'exp': 0}
    cuentas.guardar_personaje_nuevo('a', p)
    yield p['char_id']
    cuentas._PROGRESO_PENDIENTE.clear()


def _en_disco(char_id):
    with sqlite3.connect(cuentas.DB_PATH) as c:
        return json.loads(c.execute('SELECT datos FROM personajes WHERE char_id=?', (char_id,)).fetchone()[0])


def test_el_progreso_se_junta_y_no_toca_la_base_en_el_acto(db):
    for exp in range(1, 50):
        cuentas.guardar_progreso('a', db, 3, exp, hp=100 + exp, mp=20)
    cuentas.guardar_progreso('a', db, 3, 60)                  # sin hp: se queda el ultimo
    assert _en_disco(db)['exp'] == 0
    cuentas.vaciar_progreso()
    d = _en_disco(db)
    assert (d['nivel'], d['exp'], d['hp'], d['mp']) == (3, 60, 149, 20)


def test_cualquier_otra_operacion_ve_el_progreso_pendiente(db):
    cuentas.guardar_progreso('a', db, 7, 1234, habilidades=[[5, 2, 10]])
    p = cuentas.lista_de_personajes('a')[0]
    assert (p['nivel'], p['exp']) == (7, 1234)
    assert p['banco_habilidades'] == {'5': [2, 10]}


def test_una_escritura_posterior_no_la_pisa_el_progreso_viejo(db):
    cuentas.guardar_progreso('a', db, 2, 10)
    cuentas._actualizar_personaje('a', db, lambda p: p.update(exp=999))
    cuentas.vaciar_progreso()
    assert _en_disco(db)['exp'] == 999
