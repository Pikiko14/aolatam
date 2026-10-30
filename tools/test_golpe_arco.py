"""El golpe basico con arco (o honda, la misma rama 17) no tenia entrada en
GOLPE_POR_SKILL y caia en el de espada, (3, 1480): el arquero pegaba con el
tajo de espadachin, y con (0, 0) no se dibujaba nada. (4, 1282) es el que eligio
el usuario probando en el juego con /anim. Reportado: "La animacion del ataque
basico bow esta mala"."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate as cb

BOW, CATAPULTA, ESPADA, LANZA = 6, 19844, 10, 19838


def test_arco_y_honda_usan_el_golpe_de_arquero():
    assert cb.golpe_de_arma(BOW) == (4, 1282)
    assert cb.golpe_de_arma(CATAPULTA) == (4, 1282)


def test_lanza_usa_el_golpe_probado_en_el_juego():
    assert cb.golpe_de_arma(LANZA) == (2, 181)


def test_espada_sigue_con_lo_medido():
    assert cb.golpe_de_arma(ESPADA) == (3, 1480)
