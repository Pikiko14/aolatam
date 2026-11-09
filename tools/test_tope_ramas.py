"""El nivel de una rama de combate no pasa del nivel del personaje; las de recoleccion y produccion, hasta +11.

08/11/2026: "porque shadow blade sube mas que el nivel del personaje??" (ShadowBlade 22 con el personaje en 20): la
rama 30 estaba en SKILLS_PRODUCTOR por ser Alchemy en otro cliente; en este es ShadowBlade.
"""
import pathlib
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import login  # noqa: E402



def _subir(monkeypatch, habilidades, veces=400, **kw):
    monkeypatch.setattr(app.cuentas, 'guardar_progreso', lambda *a, **k: None)
    p = login.Personaje(hp=100, hp_max=100, mp=100, mp_max=100)
    p.nivel, p.buffs = 20, {}
    p.habilidades = list(habilidades)
    s = NS(personaje=p, inventario={}, usuario=None, enviar=lambda *a: None)
    for _ in range(veces):
        app._otorgar_skill_exp(s, p, p.entity_id, prob_override=1.0, **kw)
    return {sid: nv for sid, nv, _pts in p.habilidades}


def test_shadowblade_no_pasa_del_nivel_del_personaje(monkeypatch):
    niveles = _subir(monkeypatch, [(30, 19, 0)], veces=4000, skills_forzadas={30})
    assert niveles[30] == 20


def test_cook_si_puede_pasar_del_nivel_del_personaje(monkeypatch):
    niveles = _subir(monkeypatch, [(31, 20, 0)], veces=4000, skills_forzadas={31})
    assert niveles[31] > 20
