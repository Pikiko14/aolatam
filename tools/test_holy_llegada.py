"""Holy: al cruzar una puerta propia se aparece DELANTE de las estatuas, no encima ni dentro del disparador.

La llegada original de la puerta 6 del equipo 2 es (126,74), la casilla de su guardian: el primer paso devolvia al
jugador al otro lado (captura del usuario, 31/10/2026)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import holy_battlefield as hb
import transitable


def _puertas():
    d = hb.datos()
    for team in (1, 2):
        for n in range(1, 11):
            guardias = [tuple(g['tile']) for g in d['structures']
                        if g['kind'] == 'guard' and g['team'] == team and g['number'] == n]
            tags = (50 + n, 60 + n) if team == 1 else (70 + n, 80 + n)
            marcas = [tuple(d['tags'][str(t)][0]) for t in tags]
            yield team, n, guardias, marcas


def test_las_llegadas_quedan_lejos_de_guardianes_y_disparadores():
    cheb = lambda a, b: max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    vistas = 0
    for team, n, guardias, marcas in _puertas():
        if len(guardias) != 2:
            continue
        for m in marcas:
            t = hb.llegada_segura(m, team, n)
            assert transitable.se_pisa(112, *t), (team, n, t)
            assert all(cheb(t, g) >= hb.DISTANCIA_LLEGADA for g in guardias), (team, n, m, t)
            assert all(cheb(t, x) >= 3 for x in marcas), (team, n, m, t)
            vistas += 1
    assert vistas == 40


def test_la_puerta_6_del_equipo_2_ya_no_deja_encima_del_guardian():
    t = hb.llegada_segura((126, 74), 2, 6)
    assert t != (126, 74) and max(abs(t[0] - 126), abs(t[1] - 74)) >= hb.DISTANCIA_LLEGADA
