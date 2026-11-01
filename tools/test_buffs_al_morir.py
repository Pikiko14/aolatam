"""Al morir se caen los buffs sin 死亡不消失, la transformacion incluida (01/11/2026)."""
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import app
import combate


def test_la_transformacion_se_cae_y_lo_que_dura_tras_la_muerte_no(monkeypatch):
    enviados = []
    monkeypatch.setattr(app, '_stats_ses', lambda s: b'stats')
    import presencia
    monkeypatch.setattr(presencia, 'notificar_transformacion', lambda s, f: enviados.append(('forma', f)))
    p = SimpleNamespace(entity_id=7, char_id=7, nivel=60, exp=0, hp=0, mp=0,
                        buffs={21449: {'fin': 9e9}, 1897: {'fin': 9e9}, 'eilian_blessing': {}})
    s = SimpleNamespace(personaje=p, usuario=None, enviar_sin_espejo=lambda *pk: enviados.extend(pk))
    app._quitar_buffs_al_morir(s)
    assert 21449 not in p.buffs                         # el cactus: sin 死亡不消失
    assert 1897 in p.buffs and 'eilian_blessing' in p.buffs   # Recovery Notice dura tras morir
    assert combate.atributo(7, 0, combate.KIND_TRANSFORM) in enviados and ('forma', 0) in enviados
