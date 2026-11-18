"""Angel Arena da AG por puesto (17/11/2026): 1o 10.000, 2o 7.000, 3o 5.000, el resto 100."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import competicion_premios as cp  # noqa: E402
import competiciones  # noqa: E402

TABLA = {'1': 10000, '2': 7000, '3': 5000, 'resto': 100}


def _ronda(stage=240):
    return {'stage': stage, 'clasificacion': ['11', '12', '13', '14', '15'], 'arena_angel_gold': TABLA}


def test_ag_por_puesto():
    r = _ronda()
    assert [cp.angel_gold_arena(r, c, 'pendiente') for c in r['clasificacion']] == [10000, 7000, 5000, 100, 100]


def test_sin_ag_si_no_hay_premio_o_no_es_arena():
    r = _ronda()
    for estado in ('prueba', 'cancelado', 'observador', 'sin_competencia', 'sin_puesto'):
        assert cp.angel_gold_arena(r, '11', estado) == 0
    assert cp.angel_gold_arena(r, '99', 'pendiente') == 0              # no clasificado
    assert cp.angel_gold_arena(_ronda(112), '11', 'pendiente') == 0    # Holy tiene su propia tabla


def test_la_config_trae_la_tabla_pedida():
    t = competiciones.config_eventos()['arena_angel_gold']
    assert (t['1'], t['2'], t['3'], t['resto']) == (10000, 7000, 5000, 100)


def test_preparar_suma_el_ag_al_plan_y_lo_crea_si_no_hay_tabla(monkeypatch):
    import json
    filas = {}

    class Con:
        def execute(self, sql, args=()):
            if sql.startswith('INSERT'):
                filas[args[1]] = (args[2], json.loads(args[3]))
            return self

    monkeypatch.setattr(__import__('competicion_identidad'), 'fila',
                        lambda con, cid, m: ('u%s' % cid, cid, json.dumps({'habilidades': []})))
    r = _ronda(239)                      # sin compat: antes se quedaba 'sin_tabla' y sin nada
    r.update(id='r1', premios_config=None, arena_premio_compat=None,
             miembros={c: {'competidor': True, 'espectador': False, 'nivel': 100} for c in r['clasificacion']})
    cp.preparar(Con(), r)
    assert filas[11][0] == 'pendiente' and filas[11][1]['angel_gold'] == 10000
    assert filas[14][1]['angel_gold'] == 100 and filas[14][1]['items'] == []


def test_badge_no1_segun_el_nivel():
    assert [cp.badge_campeon(n) for n in (50, 119, 120, 200, 240, 279, 280, 434)] == \
        [8659, 8659, 66321, 66324, 66327, 66327, 66330, 66330]


def test_el_campeon_recibe_su_badge_una_vez(monkeypatch):
    import json
    filas = {}

    class Con:
        def execute(self, sql, args=()):
            if sql.startswith('INSERT'):
                filas[args[1]] = json.loads(args[3])
            return self

    monkeypatch.setattr(__import__('competicion_identidad'), 'fila',
                        lambda con, cid, m: ('u%s' % cid, cid, json.dumps({'habilidades': []})))
    r = _ronda(239)
    r.update(id='r1', fin=1000.0, premios_config=None, arena_premio_compat=None,
             miembros={c: {'competidor': True, 'espectador': False, 'nivel': 200} for c in r['clasificacion']})
    cp.preparar(Con(), r)
    assert [i['id'] for i in filas[11]['items']] == [66324]
    assert filas[11]['items'][0]['caduca_en'] == 1000.0 + 9240 * 60
    assert filas[12]['items'] == []                                  # solo el 1o
    plan = {'items': [{'id': 66330, 'cantidad': 1}]}                 # ya trae el compat Lv280
    cp._con_badge_de_campeon(r, {'nivel': 434}, plan)
    assert [i['id'] for i in plan['items']] == [66330]


def test_el_aura_del_campeon_se_manda_una_vez_por_jugador_y_mapa(monkeypatch):
    """En el cliente el aura ya no se apaga: relanzarla la hacia titilar (18/11/2026)."""
    import types
    import inventario
    import presencia
    yo_env, otro_env = [], []
    p = types.SimpleNamespace(entity_id=1001, stage=41)
    yo = types.SimpleNamespace(personaje=p, rol='mundo', inventario={inventario.RANURA_INSIGNIA: 66324},
                               mapa_cambiado_en=1.0, enviar=lambda *a: yo_env.extend(a))
    otro = types.SimpleNamespace(mapa_cambiado_en=5.0, enviar=lambda *a: otro_env.extend(a))
    monkeypatch.setattr(presencia, 'entidad_de', lambda s: 777)
    monkeypatch.setattr(presencia, 'clave_de_mapa', lambda s, st: st)
    monkeypatch.setattr(presencia, '_vivas', lambda st: [yo, otro])
    assert cp.brillo_campeon(yo) == 2                 # a el y al otro del mapa
    assert cp.brillo_campeon(yo) == 0                 # ya la tienen: no se relanza
    paquetes = yo_env + otro_env
    assert all(m[:2] == b'\x11\x00' and m[2] == cp.EFECTO_CAMPEON and m[22] == 2 for m in paquetes)
    assert int.from_bytes(yo_env[0][4:8], 'little') == 1001 and int.from_bytes(otro_env[0][4:8], 'little') == 777
    otro.mapa_cambiado_en = 9.0                       # el otro recargo el mapa: solo a el
    assert cp.brillo_campeon(yo) == 1
    yo.mapa_cambiado_en = 2.0                         # el campeon cambio de mapa: a los dos otra vez
    assert cp.brillo_campeon(yo) == 2
    yo.inventario = {inventario.RANURA_INSIGNIA: 8660}  # el No. 2 no brilla
    yo.mapa_cambiado_en = 3.0
    assert cp.brillo_campeon(yo) == 0
