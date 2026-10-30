"""El golpe basico con arco (o honda, la misma rama 17) no tenia entrada en
GOLPE_POR_SKILL y caia en el de espada, (3, 1480): el arquero pegaba con el
tajo de espadachin. Reportado por el usuario: "La animacion del ataque basico
bow esta mala"."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate as cb

BOW, CATAPULTA, ESPADA, LANZA = 6, 19844, 10, 19838


def test_arco_y_honda_dejan_la_animacion_al_cliente():
    assert cb.golpe_de_arma(BOW) == (0, 0)
    assert cb.golpe_de_arma(CATAPULTA) == (0, 0)


def test_espada_y_lanza_siguen_con_lo_medido():
    assert cb.golpe_de_arma(ESPADA) == (3, 1480)
    assert cb.golpe_de_arma(LANZA) == (2, 827)
