"""El estallido de las habilidades 射出型 espera a que llegue el proyectil (13/11/2026, "el pk5 no esta centrado")."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import combate  # noqa: E402


def test_panther_killing_espera_segun_la_distancia():
    cerca = combate.viaje_proyectil(754, (10, 10), (11, 10))
    lejos = combate.viaje_proyectil(754, (10, 10), (20, 14))
    assert 0 < cerca < lejos <= combate.VIAJE_PROYECTIL_MAXIMO
    assert abs(lejos - 10 * combate.VIAJE_PROYECTIL_POR_CASILLA) < 1e-9


def test_un_golpe_cuerpo_a_cuerpo_no_espera():
    assert combate.viaje_proyectil(750, (10, 10), (11, 10)) == 0          # Strong Beat V
