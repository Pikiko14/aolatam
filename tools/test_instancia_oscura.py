"""Instancia oscura Lv55-60 (Shadow Area, stage 55): plantilla, portales y jefe con piedras de Holy."""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate
import eventos
import transitable

PLANT = RAIZ / 'server' / 'plantillas'
STAGE = 55
JEFE = 5258
PIEDRAS_HOLY = {8537, 8770, 24882, 28866, 40921}


def _spawns():
    return json.loads((PLANT / 'shadow_area.json').read_text(encoding='utf-8'))['spawns']


def test_es_instancia_y_tiene_plantilla():
    assert app.es_instancia(STAGE)
    assert app.mapas_poblados()[STAGE] == 'shadow_area.json'


def test_niveles_mezcla_de_normales_y_elites_y_un_jefe():
    sp = _spawns()
    normales = [s for s in sp if not s.get('elite') and not s.get('jefe')]
    elites = [s for s in sp if s.get('elite')]
    jefes = [s for s in sp if s.get('jefe')]
    assert len(normales) >= 40 and len(elites) >= 8 and len(jefes) == 1
    assert all(55 <= s['nivel'] <= 60 for s in normales + elites)
    assert jefes[0]['npc_type'] == JEFE
    assert all(s['hp_mult'] > 1 for s in elites)
    assert len({s['entity_id'] for s in sp}) == len(sp)


def test_todos_pisan_suelo_y_se_llega_a_ellos_desde_la_entrada():
    llegada = tuple(eventos.casillas_de_tag(STAGE, 1)[0])
    visto, cola = {llegada}, [llegada]
    while cola:
        x, y = cola.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if n not in visto and transitable.se_pisa(STAGE, *n):
                    visto.add(n)
                    cola.append(n)
    for s in _spawns():
        assert tuple(s['tile']) in visto, s


def test_los_monstruos_se_arman_con_vida_extra_para_elites_y_jefe():
    bichos = app._monstruos_de(STAGE)
    por_tipo = {}
    for m in bichos.values():
        por_tipo.setdefault(m.npc_type, m)
    assert len(bichos) == len(_spawns())
    assert bichos[next(e['entity_id'] for e in _spawns() if e.get('jefe'))].hp_max > 500000
    assert por_tipo[5254].hp_max < por_tipo[5255].hp_max


def test_portales_de_ida_y_vuelta_validos():
    portales = json.loads((PLANT / 'portales.json').read_text(encoding='utf-8'))['mapas']
    ida = next(p for p in portales['41'] if p.get('destino') == STAGE)
    vuelta = next(p for p in portales[str(STAGE)] if p.get('destino') == 41)
    assert transitable.se_pisa(41, *ida['tile']) and transitable.se_pisa(STAGE, *ida['llegada'])
    assert transitable.se_pisa(STAGE, *vuelta['tile']) and transitable.se_pisa(41, *vuelta['llegada'])
    cheb = lambda a, b: max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    assert cheb(ida['llegada'], vuelta['tile']) > 1 and cheb(vuelta['llegada'], ida['tile']) > 1
    assert ida['entity'] != vuelta['entity']


def test_el_jefe_solo_suelta_piedras_de_holy():
    for _ in range(50):
        botin = combate.botin_items(JEFE, 'Cursed Larry', 63)
        assert botin and all(item in PIEDRAS_HOLY for item, _n in botin)
