"""Pet Defense, fase 1 (21/11/2026): torres-mascota fijas que pegan a los monstruos en su alcance (server/pet_defense.py)."""
import pathlib

import pytest
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import combate  # noqa: E402
import gm  # noqa: E402
import pet_defense as pd  # noqa: E402


class Ses:
    def __init__(self, monstruos=None):
        self.personaje = NS(entity_id=500001, nombre='Tester', stage=2, tile_x=10, tile_y=10)
        self.monstruos = monstruos or {}
        self.enviados = []
        self.cerrada = False

    def enviar(self, *pk):
        self.enviados.extend(pk)

    enviar_inmediato = enviar


def _bicho(eid, x, y, hp=10_000):
    m = combate.Monstruo(eid, 1, 'Slime', (x, y), 0, stage=2)
    m.hp_max = max(m.hp_max, hp)
    m.hp = hp
    return m


def _preparar(monkeypatch, ses):
    monkeypatch.setattr(pd, '_sesiones_del_mapa', lambda stage: [ses])
    monkeypatch.setattr(pd, '_arrancar', lambda: None)
    monkeypatch.setattr(app, '_pet_puede_atacar', lambda s, m: True)
    pd._TORRES.clear()


def test_poner_manda_la_mascota_sin_enlace(monkeypatch):
    ses = Ses()
    _preparar(monkeypatch, ses)
    msg = pd.poner(ses, 'guardian')
    assert 'placed at (10,10)' in msg
    ops = [struct.unpack_from('<H', p)[0] for p in ses.enviados]
    assert 0x0050 in ops and 0x001D not in ops          # sin el enlace jugador -> mascota
    t = next(iter(pd._TORRES.values()))
    spawn = ses.enviados[ops.index(0x0050)]
    assert struct.unpack_from('<I', spawn, 2 + 71)[0] == t.entidad
    assert struct.unpack_from('<I', spawn, 2 + 75)[0] == 0          # sin dueno: si no, el cliente abre el panel de SU mascota
    pd._TORRES.clear()


def test_pega_al_mas_cercano_dentro_del_alcance(monkeypatch):
    lejos, cerca = _bicho(9001, 10, 30), _bicho(9002, 12, 11)
    ses = Ses({9001: lejos, 9002: cerca})
    _preparar(monkeypatch, ses)
    pd.poner(ses, 'guardian')
    ses.enviados.clear()
    pd.tick(ahora=1000.0)
    assert cerca.hp < 10_000 and lejos.hp == 10_000
    assert any(struct.unpack_from('<H', p)[0] == 0x000A for p in ses.enviados) or ses.enviados
    hp = cerca.hp
    pd.tick(ahora=1000.1)                               # antes de la cadencia: no vuelve a pegar
    assert cerca.hp == hp
    pd.tick(ahora=1000.0 + pd.config()['torres']['guardian']['cadencia'])
    assert cerca.hp < hp
    pd._TORRES.clear()


def test_al_matar_reparte_como_la_mascota(monkeypatch):
    m = _bicho(9003, 11, 10, hp=1)
    ses = Ses({9003: m})
    _preparar(monkeypatch, ses)
    muertes = []
    monkeypatch.setattr(app, '_procesar_muerte_monstruo', lambda s, mm, yo, addr, espera=0.0: muertes.append((mm, yo)))
    pd.poner(ses, 'guardian')
    pd.tick(ahora=2000.0)
    assert m.hp == 0 and muertes == [(m, ses.personaje.entity_id)]
    pd._TORRES.clear()


def test_se_quita_si_el_dueno_cambia_de_mapa(monkeypatch):
    ses = Ses({9004: _bicho(9004, 11, 10)})
    _preparar(monkeypatch, ses)
    pd.poner(ses, 'guardian')
    ses.personaje.stage = 3
    pd.tick(ahora=3000.0)
    assert not pd._TORRES


def test_tope_y_tipo_desconocido(monkeypatch):
    ses = Ses()
    _preparar(monkeypatch, ses)
    assert 'unknown tower' in pd.poner(ses, 'dragonzote')
    for _ in range(pd.config()['max_torres_por_jugador']):
        pd.poner(ses, 'arquero')
    assert 'already have' in pd.poner(ses, 'arquero')
    assert pd.quitar(ses) == pd.config()['max_torres_por_jugador'] and not pd._TORRES


def test_comando_gm():
    assert 'torre' in gm.PALABRAS_DELEGADAS and 'torre' in gm.RESULTADOS_DELEGADOS
    assert gm.parsear('/torre fuego') == ('torre', 'fuego') and gm.parsear('/tower quitar') == ('torre', 'quitar')


@pytest.fixture(autouse=True)
def rk_tmp(tmp_path, monkeypatch):
    """Las partidas que acaban no van a la base de datos de verdad (data/pet_defense.db)."""
    import pet_defense_ranking
    monkeypatch.setattr(pet_defense_ranking, 'DB_PATH', tmp_path / 'pet_defense.db')

