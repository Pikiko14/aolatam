"""Los poderes hacen lo que dicen (13/11/2026, "todos los poderes, de cualquier clase, deben dar el efecto que dicen
sin excepcion"): debuffs encadenados, ralentizacion y silencio en monstruos, probabilidad de los procs."""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import combate  # noqa: E402
import hechizos_mob  # noqa: E402


def _bicho():
    return combate.Monstruo(1, 1, 'Dummy', (10, 10))


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
