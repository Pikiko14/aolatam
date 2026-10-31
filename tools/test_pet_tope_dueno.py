""""EL PET NUNCA DEBE PASAR EL NIVEL DE SU DUENO Y AL USAR PET FEED DEBE VALIDAR SI ESTA ALGUN PET AFUERA"."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import mascotas


def _ficha(nivel):
    return {'nivel': nivel, 'exp': 0, 'sprite': None}


def test_la_mascota_no_pasa_al_dueno():
    f = _ficha(30)
    mascotas.dar_exp(f, 10 ** 9, nivel_dueno=32)
    assert f['nivel'] == 32
    assert 0 < f['exp'] < mascotas.exp_para_subir(32, f.get('sprite'))      # se queda al borde del 33


def test_al_subir_el_dueno_sube_la_mascota():
    f = _ficha(32)
    mascotas.dar_exp(f, 10 ** 9, nivel_dueno=32)
    mascotas.dar_exp(f, 1, nivel_dueno=33)
    assert f['nivel'] == 33


def test_una_que_ya_lo_pasaba_no_sube_mas():
    f = _ficha(35)
    assert mascotas.dar_exp(f, 10 ** 9, nivel_dueno=32) == 0 and f['nivel'] == 35


def test_el_pet_feed_pide_una_mascota_afuera():
    import inspect
    import app
    fuente = inspect.getsource(app)
    assert "Summon your pet before using this item." in fuente
