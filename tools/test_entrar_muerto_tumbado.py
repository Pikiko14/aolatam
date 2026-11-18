"""Quien entra muerto (reconexion, cambio de mapa) sale ya tumbado y no "vivo y luego cae" (17/11/2026)."""
import pathlib
import sys
import types

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import login  # noqa: E402


def _ficha(p):
    return next(m for m in login.secuencia(p) if m[:2] == b'\x02\x00')


def test_la_ficha_del_muerto_lleva_el_7_en_el_byte_61():
    p = login.Personaje()
    assert _ficha(p)[2 + 61] == 0
    p._ficha_muerto = True
    assert _ficha(p)[2 + 61] == login.FICHA_MUERTO


def test_solo_el_muerto_que_no_es_alma_entra_tumbado():
    for muerto, alma, esperado in ((True, False, True), (True, True, False), (False, False, False)):
        ses = types.SimpleNamespace(personaje=login.Personaje(), muerto=muerto, fantasma=alma)
        app._marcar_ficha_muerto(ses)
        assert ses.personaje._ficha_muerto is esperado


def test_con_la_ficha_tumbada_no_se_le_repite_la_caida(monkeypatch):
    enviados = []
    p = login.Personaje()
    p._ficha_muerto = True
    ses = types.SimpleNamespace(personaje=p, muerto=True, fantasma=False, monstruos={},
                                enviar=lambda *a: enviados.extend(a))
    monkeypatch.setattr(app, '_avisar_muerte_a_los_demas', lambda *a: None)
    monkeypatch.setattr(app, '_quitar_buffs_al_morir', lambda *a: None)
    app._reaplicar_muerte(ses)
    assert enviados and not any(m[:2] == b'\x0a\x00' for m in enviados)
