"""11/11/2026: "si muero y tengo 1 pet afuera se debe guardar"; "el enchanted de earth mage no ataca a los mob que yo
ataco, y los mob normales deberian poder atacarlo a el"."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'proto'))
import app  # noqa: E402
import combate  # noqa: E402


def _bicho(eid, x, y, npc=1):
    m = combate.Monstruo(eid, npc, 'Slarm', (x, y))
    m.vivo = True
    return m


def test_el_encantado_va_a_por_lo_que_apunto_o_lo_que_pelea_conmigo():
    enc, a, b, lejos = _bicho(1, 10, 10), _bicho(2, 12, 10), _bicho(3, 11, 11), _bicho(4, 40, 40)
    enc.encantado = True
    ses = NS(monstruos={1: enc, 2: a, 3: b, 4: lejos}, objetivo_actual=None)
    assert app._objetivo_del_encantado(ses, enc, 1001) is None            # nadie pelea conmigo
    a.en_combate_con, b.en_combate_con, lejos.en_combate_con = 1001, 1001, 1001
    assert app._objetivo_del_encantado(ses, enc, 1001) is b               # el mas cercano (el lejano no cuenta)
    ses.objetivo_actual = 2
    assert app._objetivo_del_encantado(ses, enc, 1001) is a               # el que apunto manda


def test_los_mobs_le_pegan_al_encantado_y_si_cae_muere_como_un_bicho(monkeypatch):
    enc, m = _bicho(1, 10, 10), _bicho(2, 11, 10)
    enc.hp = 50
    muertes, enviados = [], []
    monkeypatch.setattr(app, '_procesar_muerte_monstruo', lambda s, b, yo, addr, espera=0: muertes.append(b))
    ses = NS(enviar_inmediato=lambda *a: enviados.extend(a))
    app._golpe_al_encantado(ses, m, enc, 30, 656, 148, 1001)
    assert enc.hp == 20 and not muertes and enviados
    app._golpe_al_encantado(ses, m, enc, 30, 656, 148, 1001)
    assert enc.hp == 0 and muertes == [enc] and m.en_combate_con == 1001  # vuelve a por el dueno


def test_al_morir_se_guarda_la_mascota_que_esta_fuera(monkeypatch):
    guardadas = []
    monkeypatch.setattr(app, '_pet_alternar', lambda ses, addr, r: guardadas.append(r))
    p = NS(nombre='Zetha', mascotas={'7': {'fuera': True, 'ranura': 7, 'nombre': 'Dark Tutor'},
                                     '8': {'fuera': False, 'ranura': 8}})
    app._guardar_mascota_al_morir(NS(personaje=p, pet_entity_id=0x105001))
    assert guardadas == [7]
    guardadas.clear()
    app._guardar_mascota_al_morir(NS(personaje=p, pet_entity_id=None))   # sin mascota fuera, nada
    assert guardadas == []
