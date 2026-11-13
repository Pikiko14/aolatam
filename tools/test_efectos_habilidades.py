"""Los poderes hacen lo que dicen (13/11/2026, "todos los poderes, de cualquier clase, deben dar el efecto que dicen
sin excepcion"): debuffs encadenados, ralentizacion y silencio en monstruos, probabilidad de los procs."""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import combate  # noqa: E402
import hechizos_mob  # noqa: E402


def _bicho():
    m = combate.Monstruo(1, 1, 'Dummy', (10, 10))
    m.res_mind = m.res_body = 0                              # sin resistencias: el efecto siempre entra
    return m


def test_tendon_chop_frena_al_monstruo():
    m = _bicho()
    ef = combate.efecto_secundario(604)                      # Tendon Chop I
    assert m.aplicar_efecto(dict(ef, prob=100)) == 'lento'
    assert any(d.get('vel_mov_mod', 0) < 0 and d['fin'] > time.time() for d in m.debuffs.values())


def test_shatter_armor_le_baja_la_mitigacion():
    m = _bicho()
    ef = combate.efecto_secundario(5631)                     # Shatter Armor I
    m.aplicar_efecto(ef)
    assert any(d.get('phys_mit_pct', 0) < 0 for d in m.debuffs.values())


def test_un_monstruo_silenciado_no_lanza_hechizos(monkeypatch):
    m = _bicho()
    monkeypatch.setattr(hechizos_mob, 'hechizos', lambda t: (1.0, [(1, 10, 0)]))
    assert hechizos_mob.elegir(m) == (1, 10, 0)
    m.res_mind = 0
    m.aplicar_efecto({'magia': 914, 'dur_ms': 5000, 'estado': 'silenciado'})
    assert hechizos_mob.elegir(m) is None


def test_la_maldicion_magica_baja_el_dano_del_hechizo_del_monstruo():
    m = _bicho()
    m.matk = 100
    sin = hechizos_mob.dano((1, 100, 0), m, 0, 0)
    m.debuffs = {207: {'fin': time.time() + 10, 'mag_dmg_pct': -50}}
    assert hechizos_mob.dano((1, 100, 0), m, 0, 0) < sin


def test_el_proc_usa_su_probabilidad_y_su_lado():
    assert combate.lado_del_proc('When attacking, 10% chance to deal') == (True, False)
    assert combate.lado_del_proc('When attacked, there is a 20% chance') == (False, True)


def test_las_curas_que_no_curaban_ahora_curan():
    for mid in (5096, 12006, 13310, 15051, 5046):           # Sacred, Celestial, Healing Cross, Holy Stanza, Divine Prayer
        d = combate.datos_magia(mid)
        assert d['es_cura'] and not d['es_ataque'] and d['hp'] > 0, mid
    assert combate.datos_magia(13310)['cura_58'] == (5000, 50, 80)
    assert not combate.datos_magia(301)['es_cura']           # Flying Dart sigue siendo ataque


def test_los_drenajes_de_las_formulas_3_4_y_56():
    assert combate.datos_magia(110)['drain_hp_pct'] == 10                       # Blood Absorbing Spell
    assert combate.datos_magia(113)['drain_mp_pct'] == 5                        # Demon-Sucking
    assert combate.datos_magia(13260)['drain_hp_tope_pct'] == 10                # Drain Strike
    assert combate.datos_magia(5401)['drain_mp_pct'] > 0                        # Stab


def test_el_reflejo_sale_de_los_datos():
    assert combate.datos_magia(308)['refl_fis_pct'] == 3                        # Rebound Spell I
    assert combate.datos_magia(5021)['refl_mag_pct'] == 9                       # Refusal Wall I


def test_en_pvp_el_debuff_baja_las_stats_del_rival(monkeypatch):
    from types import SimpleNamespace as NS
    import app
    import presencia
    import pvp_liga
    monkeypatch.setattr(presencia, '_vivas', lambda clave: [])
    monkeypatch.setattr(presencia, 'clave_de_mapa', lambda s, st: 0)
    monkeypatch.setattr(presencia, 'entidad_de', lambda s: 1)
    monkeypatch.setattr(app, '_stats_ses', lambda s: b'')
    env = []
    yo = NS(personaje=NS(nombre='a', entity_id=1, stage=1), enviar=lambda *x: None)
    otro = NS(personaje=NS(nombre='b', entity_id=2, stage=1, buffs={}), enviar=lambda *x: env.extend(x))
    assert pvp_liga.aplicar_debuff(yo, otro, 5631, {'phys_mit_pct': -15, 'def_mod': -40}, 5000, 'Shatter Armor')
    b = otro.personaje.buffs[5631]
    assert b['mit'] == -15 and b['def'] == -40 and pvp_liga.mitigacion(otro, False) > 1.0
    assert not pvp_liga.aplicar_debuff(yo, otro, 1, {}, 5000)
