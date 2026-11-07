"""Totem War: el cartel y la vida siguen al nivel, y la mascota no ataca al totem propio (07/11/2026)."""
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import app  # noqa: E402
import totem_war as tw  # noqa: E402


def _campo():
    return next(iter(tw.TOTEM_CAMPO))


def test_cartel_con_el_tipo_del_nivel_actual(monkeypatch):
    st = _campo()
    monkeypatch.setattr(tw, 'nivel_totem', lambda s: (8, 0))
    m = NS(entity_id=5, tile_x=1, tile_y=2, stage=st, npc_type=tw.TOTEM_TIPO_CAMPO, porcentaje=100)
    pk = tw.spawn_totem_campo(m)
    assert struct.unpack_from('<H', pk, 2 + 45)[0] == tw.TOTEM_TIPO_CAMPO + 7
    assert struct.unpack_from('<I', pk, 2 + 40)[0] == 7


def test_mascota_no_ataca_al_totem_que_su_dueno_no_puede_romper(monkeypatch):
    monkeypatch.setattr(__import__('holy_battlefield'), 'puede_atacar', lambda s, m: True)
    totem = NS(es_totem_tw=True, stage=_campo())
    monkeypatch.setattr(tw, 'puede_pegar', lambda s, m: False)
    assert not app._pet_puede_atacar(NS(), totem)
    monkeypatch.setattr(tw, 'puede_pegar', lambda s, m: True)
    assert app._pet_puede_atacar(NS(), totem)
    assert app._pet_puede_atacar(NS(), NS())                     # un bicho normal, si


def test_repintar_sube_la_vida_con_el_nivel(monkeypatch):
    st = _campo()
    monkeypatch.setattr(tw, 'nivel_totem', lambda s: (1, 0))
    m = tw.crear_totem(st)
    m.__dict__['_hp'] = m.hp_max // 2                          # a la mitad
    sala = NS(monstruos={m.entity_id: m}, sesiones=[])
    monkeypatch.setitem(app._SALAS_DEL_MUNDO, st, sala)
    monkeypatch.setattr(tw, 'nivel_totem', lambda s: (4, 0))
    app._tw_repintar_totem(st)
    assert m.hp_max == tw.VIDA_POR_NIVEL * 4 and m.hp == m.hp_max // 2


def test_efecto_level_up_al_subir(monkeypatch):
    st = _campo()
    monkeypatch.setattr(tw, 'nivel_totem', lambda s: (3, 0))
    enviados = []
    ses = NS(personaje=NS(stage=st), enviar=lambda *p: enviados.extend(p))
    monkeypatch.setitem(app._SALAS_DEL_MUNDO, st, NS(sesiones=[ses], monstruos={}))
    app._tw_efecto_nivel(st)
    assert enviados and enviados[0][:2] == b'\x20\x00'


def test_sentado_a_los_demas_es_el_8_no_el_7():
    import presencia
    assert presencia.ACCION_SENTADO_AJENO == 8        # en el 0x000A el 7 es la muerte


def test_matar_un_totem_de_nivel_alto_lo_baja_uno_sin_dar_el_territorio(monkeypatch):
    st = _campo()
    niveles = {'n': 3}
    monkeypatch.setattr(tw, 'activa', lambda: True)
    monkeypatch.setattr(tw, 'nivel_totem', lambda s: (niveles['n'], 0))

    def bajar(s):
        niveles['n'] -= 1
        return niveles['n']
    monkeypatch.setattr(tw, 'bajar_nivel', bajar)
    capturas, relevantados = [], []
    monkeypatch.setattr(tw, 'capturado', lambda ses, m: capturas.append(1) or 'x')
    monkeypatch.setattr(app, '_tw_relevantar', lambda s: relevantados.append(s))
    monkeypatch.setattr(app, '_tw_efecto_nivel', lambda s, baja=False: None)
    ses = NS(personaje=NS(nombre='Zetha'))
    m = NS(stage=st)
    app._tw_totem_roto(ses, m, 'test')
    assert niveles['n'] == 2 and relevantados == [st] and not capturas
    niveles['n'] = 1
    monkeypatch.setattr(app, '_logros_contar', lambda *a, **k: None)
    monkeypatch.setattr(app, '_tw_difundir', lambda *a: None)
    monkeypatch.setattr(app, '_tw_echar_del_campo', lambda s: None)
    app._tw_totem_roto(ses, m, 'test')
    assert capturas == [1]                                   # en nivel 1 si se pierde


def test_efecto_por_nivel_y_tope_5():
    assert [tw.efecto_de_nivel(n) for n in range(1, 7)] == [None, 7, 8, 9, 10, None]    # probados en el juego
    assert tw.NIVEL_MAX_TOTEM == 5


def test_al_bajar_no_usa_los_de_subir():
    assert [tw.efecto_de_nivel(n, baja=True) for n in (1, 2, 3, 4, 5)] == [11, 12, 13, 14, None]
    assert tw.efecto_de_nivel(3) == 8
