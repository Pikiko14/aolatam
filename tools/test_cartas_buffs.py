"""Cartas de recoleccion, fabricacion (Facture), EXP, skill y loot de 3 dias o mas: duracion y bonos."""
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import bolsas
import configuracion
import house_services as hs

CAMPOS = {'採集速度': 'recoleccion_pct', '製作速度': 'fabricacion_pct',
          '經驗加倍': 'exp_extra_pct', '技能經驗加倍': 'skill_exp_extra_pct',
          '掉寶加倍': 'drop_extra_pct'}
TRES_DIAS = 3 * 86400


def _cartas():
    magia = hs.xml_rows('magic.xml')
    out = []
    for t in ['item.xml'] + ['item%d.xml' % i for i in range(2, 10)]:
        for iid, r in hs.xml_rows(t).items():
            m = r.get('常駐法術')
            if not (m and m.isdigit() and r.get('可使用') == '是'):
                continue
            mm = magia.get(int(m))
            if mm and int(mm.get('持續時間') or 0) >= TRES_DIAS and any(int(mm.get(c) or 0) for c in CAMPOS):
                out.append((int(iid), int(m), mm))
    return out


def test_hay_cartas_de_tres_dias_o_mas():
    assert len(_cartas()) > 20


def test_duracion_igual_a_la_del_xml_y_bonos_aplicados():
    extra = 1 + configuracion.BONO_CARTAS_VELOCIDAD_PCT / 100
    for iid, mid, mm in _cartas():
        r = bolsas.buff_de(iid, 0)
        assert r, iid
        _, entrada, dur = r
        assert dur == int(mm['持續時間']) * 1000, (iid, dur)
        for col, campo in CAMPOS.items():
            v = int(mm.get(col) or 0)
            if v:
                esperado = round(v * extra) if campo in ('recoleccion_pct', 'fabricacion_pct') else v
                assert entrada.get(campo) == esperado, (iid, campo, entrada.get(campo), esperado)
        assert entrada.get('persist_death') is True, iid


def test_cartas_con_fecha_en_el_nombre_duran_lo_que_dice():
    """'(30 days)' dura 30 dias, '(8 hours)' 8 horas. Las cartas normales llevan el plazo en la magia; las
    piedras reutilizables (使用不扣) lo llevan en el item (minutos) y la magia solo da media hora por uso."""
    magia = hs.xml_rows('magic.xml')
    mal = []
    for t in ['item.xml'] + ['item%d.xml' % i for i in range(2, 10)]:
        for iid, r in hs.xml_rows(t).items():
            m = r.get('常駐法術')
            mm = magia.get(int(m)) if m and m.isdigit() else None
            if not mm or not any(int(mm.get(c) or 0) for c in CAMPOS) or r.get('可使用') != '是':
                continue                      # solo objetos que se usan: los collares y medallas se equipan
            n = r.get('基本名稱') or ''
            f = re.search(r'\(\s*(\d+)\s*(day|days|hour|hours)\s*\)', n, re.I)
            if not f:
                continue
            segundos = int(f.group(1)) * (86400 if f.group(2).lower().startswith('day') else 3600)
            if r.get('使用不扣') == '是':
                real = int(r.get('持續時間') or 0) * 60          # plazo del item, en minutos
            else:
                real = int(mm.get('持續時間') or 0)
            if real != segundos:
                mal.append((int(iid), n, real, segundos))
    assert not mal, mal


def test_piedra_reutilizable_caduca_tras_su_plazo(monkeypatch):
    import time
    from types import SimpleNamespace as NS
    import cuentas
    avisos = []
    monkeypatch.setattr(cuentas, 'guardar_mejoras', lambda *a: None)
    import arena_premios_compat
    monkeypatch.setattr(arena_premios_compat, 'caducados', lambda ses, **kw: avisos.append(kw))
    ses = NS(usuario='u', personaje=NS(char_id=1, mejoras={}))
    piedra = 19734          # Collecting Speed Stone (30 days), 使用不扣, item 43200 min
    assert bolsas.piedra_caducada(ses, 20, piedra) is False          # primer uso: arranca el plazo
    meta = ses.personaje.mejoras[20]
    assert abs(meta['stone_fin'] - (time.time() + 43200 * 60)) < 5
    assert bolsas.piedra_caducada(ses, 20, piedra) is False          # dentro de plazo
    meta['stone_fin'] = time.time() - 1
    assert bolsas.piedra_caducada(ses, 20, piedra) is True           # vencida
    assert avisos and avisos[0]['campo_fin'] == 'stone_fin'
    assert bolsas.piedra_caducada(ses, 21, 3967) is False            # una carta normal no lleva plazo de item


def test_insignia_de_faccion_cambia_faccion_y_lleva_a_su_ciudad(monkeypatch):
    from types import SimpleNamespace as NS
    import app
    import cuentas
    enviados, viajes, guardados = [], [], []
    ses = NS(usuario='u', muerto=False, mapa_cargando=False, enviar=lambda *a: enviados.extend(a),
             personaje=NS(char_id=1, nombre='X', stage=41, faction='Heaven'))
    monkeypatch.setattr(app, '_sacar', lambda *a: 1)
    monkeypatch.setattr(app, '_refrescar', lambda *a, **k: [])
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    monkeypatch.setattr(app, '_sincronizar_cambio_mapa', lambda s, st, x, y: viajes.append((st, x, y)))
    monkeypatch.setattr(cuentas, 'guardar_faccion', lambda u, c, f: guardados.append(f))
    app._usar_insignia_faccion(ses, 'test', 20, 7030)
    assert ses.personaje.faction == 'Steel' and guardados == ['Steel']
    assert viajes == [(38, 68, 163)]
    app._usar_insignia_faccion(ses, 'test', 20, 7030)               # ya es de esa faccion: no repite
    assert len(viajes) == 1


def test_insignia_pasa_el_punto_de_revivir_de_la_ciudad_vieja_a_la_nueva(monkeypatch):
    from types import SimpleNamespace as NS
    import app
    import cuentas
    cps = []
    def sesion(cp_stage):
        return NS(usuario='u', muerto=False, mapa_cargando=False, enviar=lambda *a: None,
                  personaje=NS(char_id=1, nombre='X', stage=41, faction='Aurora', checkpoint_stage=cp_stage, checkpoint_x=5, checkpoint_y=6))
    monkeypatch.setattr(app, '_sacar', lambda *a: 1)
    monkeypatch.setattr(app, '_refrescar', lambda *a, **k: [])
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a: None)
    monkeypatch.setattr(app, '_sincronizar_cambio_mapa', lambda *a: None)
    monkeypatch.setattr(cuentas, 'guardar_faccion', lambda *a: None)
    monkeypatch.setattr(cuentas, 'guardar_checkpoint', lambda u, c, st, x, y: cps.append((st, x, y)))
    s1 = sesion(3)                                   # revivia en Aurora City: ahora es de Iron Castle
    app._usar_insignia_faccion(s1, 'test', 20, 7030)
    assert (s1.personaje.checkpoint_stage, s1.personaje.checkpoint_x, s1.personaje.checkpoint_y) == (38, 68, 163) and cps == [(38, 68, 163)]
    s2 = sesion(41)                                  # lo fijo con Cupid en el Lyceum: no se toca
    app._usar_insignia_faccion(s2, 'test', 20, 7030)
    assert s2.personaje.checkpoint_stage == 41 and len(cps) == 1


def test_las_ciudades_de_cada_faccion_son_las_suyas():
    import app
    # Aurora City 3, Dark City 26, Breeze Woods 29, Iron Castle 38 (stage.xml); antes salian cruzadas al salir de una casa
    assert app.CIUDAD_POR_FACCION == {'Aurora': (3, (191, 182)), 'Beasts': (29, (321, 97)), 'Steel': (38, (68, 163)), 'Shadow': (26, (309, 69))}
    import cuentas
    for fac, (st, tile) in app.CIUDAD_POR_FACCION.items():
        ficha = {'ranura': 0, 'char_id': 7, 'nombre': 'X', 'habilidades': [], 'barra': [], 'quests': [], 'faction': fac,
                 'stage_id': 500, 'tile_x': 1, 'tile_y': 1, 'inventario': {}}
        p = cuentas.personaje_de({'personajes': [ficha]}, 0)
        assert (p.stage, (p.tile_x, p.tile_y)) == (st, tile), fac
