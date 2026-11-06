"""Las ramas elementales del mago solo suben con un hechizo suyo (05/11/2026: "los poderes de mago solo suben de nivel
si se usa un spell de su tipo; ahorita Life esta subiendo usando poderes Chaos")."""
import pathlib
import sqlite3
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import clases  # noqa: E402
import login  # noqa: E402


def _hechizo(rama_txt):
    c = sqlite3.connect(str(RAIZ / 'corpus' / 'content.db'))
    return int(c.execute('select id from magic where "技能限制1"=? limit 1', (rama_txt,)).fetchone()[0])


def _subidas(monkeypatch, magic_id):
    monkeypatch.setattr(app.cuentas, 'guardar_progreso', lambda *a, **k: None)
    p = login.Personaje(hp=100, hp_max=100, mp=100, mp_max=100)
    p.nivel, p.buffs = 50, {}
    p.habilidades = [(1, 10, 0), (2, 10, 0), (3, 10, 0), (4, 10, 0), (6, 10, 0)]
    s = NS(personaje=p, inventario={}, usuario=None, enviar=lambda *a: None)
    app._otorgar_skill_exp(s, p, p.entity_id, magic_id=magic_id, prob_override=1.0)
    return {sid for sid, nv, pts in p.habilidades if pts > 0 or nv > 10}


def test_chaos_no_sube_life(monkeypatch):
    chaos = _hechizo('混亂技能')
    assert clases.skill_de_magia(chaos) == 3
    sube = _subidas(monkeypatch, chaos)
    assert 3 in sube and not ({1, 2, 4} & sube)
    assert 6 in sube                               # Meditate sigue subiendo con cualquier magia


def test_life_solo_sube_life(monkeypatch):
    sube = _subidas(monkeypatch, _hechizo('生命技能'))
    assert 1 in sube and not ({2, 3, 4} & sube)
