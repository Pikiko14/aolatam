"""Holy: EXP ademas del AG segun resultado y puntos, y el salto de las puertas a tiempo."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import combate
import competicion_premios as cp

CFG = {'puntos_umbral': 500, 'ganador': [500000, 350000], 'perdedor': [250000, 200000],
       'empate': [250000, 200000]}
TABLA = [dict(nivel_min=1, nivel_max=10000, resultado=res, angel_gold=ag)
         for res, ag in (('ganador', 5000), ('perdedor', 2000), ('empate', 1000))]


def _ronda(ganador=1):
    miembros = {'1': dict(equipo=1, nivel=50, score=500, espectador=False),
                '2': dict(equipo=1, nivel=50, score=499, espectador=False),
                '3': dict(equipo=2, nivel=50, score=800, espectador=False),
                '4': dict(equipo=2, nivel=50, score=10, espectador=False)}
    return dict(stage=112, ganador=ganador, miembros=miembros, premios_config=TABLA,
                holy_exp_resultado=CFG)


def test_exp_segun_resultado_y_puntos():
    r = _ronda()
    gap = combate.exp_para_nivel(51) - combate.exp_para_nivel(50)
    esperado = {'1': (5000, gap * 50 // 100), '2': (5000, gap * 35 // 100),
                '3': (2000, gap * 25 // 100), '4': (2000, gap * 20 // 100)}
    for cid, (ag, exp) in esperado.items():
        plan, estado = cp.seleccionar(r, cid, r['miembros'][cid])
        assert estado == 'pendiente'
        assert (plan['angel_gold'], plan['exp']) == (ag, exp), cid


def test_sin_config_solo_da_el_ag():
    r = _ronda()
    r['holy_exp_resultado'] = None
    plan, _ = cp.seleccionar(r, '1', r['miembros']['1'])
    assert (plan['angel_gold'], plan['exp']) == (5000, 0)


def test_la_config_real_trae_los_porcentajes():
    import json
    cfg = json.loads((RAIZ / 'server' / 'plantillas' / 'competiciones_config.json').read_text('utf-8'))
    h = cfg['holy_exp_por_resultado']
    assert (h['puntos_umbral'], h['ganador'], h['perdedor']) == (500, [500000, 350000], [250000, 200000])
