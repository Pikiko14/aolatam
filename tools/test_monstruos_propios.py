"""Los 15 monstruos propios de Dark Cavern (Lv45-60): un npc_type real de nivel alto (habilidades,
IA y dibujo) con stats, exp y oro de su nivel; sueltan la caja de nivel 55 y, mas raro, piedras de
Holy, y dan 50 de Angel Gold. Ver tools/generar_monstruos_propios.py."""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import cliente_local
import combate
import cuentas
import item_mall

PROPIOS = combate.monstruos_propios()


def test_son_15_de_nivel_45_a_60_con_curva_creciente():
    mobs = sorted(PROPIOS['mobs'].values(), key=lambda m: m['nivel'])
    assert len(mobs) == 15
    assert mobs[0]['nivel'] == 45 and mobs[-1]['nivel'] == 60
    for a, b in zip(mobs, mobs[1:]):
        assert b['hp'] >= a['hp'] and b['exp'] >= a['exp']


def test_su_base_es_de_nivel_alto_con_habilidades():
    import sqlite3
    con = sqlite3.connect(str(RAIZ / 'corpus' / 'content.db'))
    try:
        for m in PROPIOS['mobs'].values():
            lv, hab = con.execute('select level, "攻擊法術1" from monster where id=?', (str(m['base']),)).fetchone()
            assert int(lv) >= 150 and hab, m['nombre']
    finally:
        con.close()


def test_aplicar_propio_cambia_stats_nombre_nivel_y_exp():
    mob = PROPIOS['mobs']['dc50']
    m = combate.Monstruo(1, mob['base'], 'x', (10, 10), sprite=mob['sprite'])
    assert m.hp_max > mob['hp'] * 5                # el de nivel 150+ tal cual
    assert combate.aplicar_propio(m, 'dc50')
    assert (m.hp_max, m.atk, m.defensa, m.nivel, m.nombre) == (mob['hp'], mob['atk'], mob['def'], 50, mob['nombre'])
    assert combate.calcular_exp(m.npc_type, {}, base=m.exp_propia) == combate.calcular_exp(0, {}, base=mob['exp'])
    m.hp = 1
    m.revivir()
    assert m.hp == mob['hp']                       # al reaparecer conserva su vida propia
    assert not combate.aplicar_propio(m, 'no-existe')


def test_la_plantilla_crea_el_propio_con_su_vida_y_el_hp_mult(tmp_path, monkeypatch):
    mob = PROPIOS['mobs']['dc55']
    pl = tmp_path / 'propios.json'
    pl.write_text(json.dumps({'stage': 999, 'spawns': [
        {'entity_id': 5, 'nombre': 'x', 'npc_type': mob['base'], 'sprite': mob['sprite'], 'monstruo': True,
         'tile': [3, 3], 'propio': 'dc55', 'hp_mult': 0.7}]}), encoding='utf-8')
    monkeypatch.setattr(app, 'mapas_poblados', lambda: {999: str(pl)})
    b = app._monstruos_de(999)[5]
    assert b.propio == 'dc55' and b.nombre == mob['nombre']
    assert b.hp_max == int(mob['hp'] * 0.7)


def test_botin_caja_y_piedra(monkeypatch):
    monkeypatch.setattr(combate.random, 'random', lambda: 0.0)
    assert combate.botin_propio() == [(cliente_local.ITEM_CAJA_55, 1), (8537, 1)]
    monkeypatch.setattr(combate.random, 'random', lambda: 0.999)
    assert combate.botin_propio() == []


def test_sumar_ag(tmp_path, monkeypatch):
    monkeypatch.setattr(cuentas, 'DB_PATH', tmp_path / 'cuentas.db')
    monkeypatch.setattr(cuentas, 'ARCHIVO', tmp_path / 'cuentas.json')
    cuentas._init_db()
    antes = item_mall.saldo('u1')
    assert item_mall.sumar_ag('u1', 50) == antes + 50
    assert item_mall.saldo('u1') == antes + 50
