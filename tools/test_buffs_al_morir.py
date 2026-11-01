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


def _ses_muerta(fantasma, monkeypatch, enviados):
    monkeypatch.setattr(app, '_stats_ses', lambda s: b'stats')
    monkeypatch.setattr(app, '_avisar_muerte_a_los_demas', lambda s, a: enviados.append(('demas', a)))
    monkeypatch.setattr(app, '_alma_a_los_demas', lambda s: enviados.append(('alma_demas',)))
    p = SimpleNamespace(entity_id=7, char_id=7, nivel=60, exp=0, hp=500, mp=0, buffs={}, nombre='X',
                        logros_cont={})
    return SimpleNamespace(personaje=p, usuario=None, muerto=True, fantasma=fantasma, monstruos={555: object()},
                           enviar_sin_espejo=lambda *pk: enviados.extend(pk), volcar=lambda: None)


def test_al_cargar_un_mapa_el_muerto_sigue_muerto(monkeypatch):
    """"me doy tp por algun portal o dc y aparezco de pie": el mapa nuevo lo presentaba vivo."""
    enviados = []
    s = _ses_muerta(False, monkeypatch, enviados)
    app._reaplicar_muerte(s)
    assert s.personaje.hp == 0
    assert combate.ataque(7, 555, 0, combate.TIPO_MUERTE) in enviados and ('demas', 555) in enviados


def test_al_cargar_un_mapa_el_alma_sigue_alma(monkeypatch):
    import supremo
    enviados = []
    s = _ses_muerta(True, monkeypatch, enviados)
    app._reaplicar_muerte(s)
    assert supremo.paquete_estado(s.personaje, supremo.ESTADO_PROPIO | combate.ESTADO_FANTASMA) in enviados
    assert ('alma_demas',) in enviados


def test_vivo_no_se_toca(monkeypatch):
    enviados = []
    s = _ses_muerta(False, monkeypatch, enviados)
    s.muerto = False
    app._reaplicar_muerte(s)
    assert enviados == [] and s.personaje.hp == 500
