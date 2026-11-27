"""La mascota tranquila se recupera ("si el pet esta calmado no se recupera", 27/11/2026)."""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402


def _ses():
    f = {'fuera': True, 'entidad': 900, 'nivel': 29, 'hp': 50, 'hp_max': 1000, 'mp': 10, 'mp_max': 500,
         'saciedad': 50}
    enviados = []
    return NS(personaje=NS(mascota=f, mascotas={}, char_id=1), pet_entity_id=900, pet_objetivo=None, muerto=False,
              usuario=None, enviar_inmediato=lambda *pk: enviados.extend(pk), enviados=enviados), f


def test_tranquila_se_recupera_cada_tic():
    ses, f = _ses()
    assert app._regen_mascota(ses, 100.0)
    assert 50 < f['hp'] <= 1000 and 10 < f['mp'] <= 500 and ses.enviados
    hp = f['hp']
    assert not app._regen_mascota(ses, 100.5)                     # aun no toca
    assert app._regen_mascota(ses, 102.5) and f['hp'] > hp


def test_peleando_o_golpeada_no():
    ses, f = _ses()
    ses.pet_objetivo = object()
    assert not app._regen_mascota(ses, 100.0)
    ses.pet_objetivo = None
    f['_golpe_en'] = 98.0
    assert not app._regen_mascota(ses, 100.0)
    assert app._regen_mascota(ses, 103.0)


def test_muerta_o_guardada_no():
    ses, f = _ses()
    f['hp'] = 0
    assert not app._regen_mascota(ses, 100.0)
    f['hp'], f['fuera'] = 50, False
    assert not app._regen_mascota(ses, 100.0)
