"""Al reconectar en una sala compartida, la sesion vieja del mismo personaje no cuenta como companero: si no, la IA de
la nueva se saltaba los bichos que peleaban con su entidad ("no me atacan cuando los ataco", 16/11/2026)."""
import pathlib
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import app


def _sala(*sesiones):
    e = NS(monstruos={}, sesiones=list(sesiones), stage=16)
    for s in sesiones:
        s._sala = e
        s.monstruos = e.monstruos
    return e


def _ses(eid, **kw):
    return NS(personaje=NS(entity_id=eid, stage=16), **kw)


def test_la_sesion_vieja_del_mismo_personaje_no_es_companera(monkeypatch):
    vieja, nueva, otro = _ses(1017), _ses(1017), _ses(2000)
    e = _sala(vieja, nueva, otro)
    monkeypatch.setattr(app, '_sala_de', lambda ses: e)
    assert app._companeros(nueva) == [otro]


def test_las_desconectadas_no_son_companeras(monkeypatch):
    yo, ido = _ses(1), _ses(2, desconectado=True)
    e = _sala(yo, ido)
    monkeypatch.setattr(app, '_sala_de', lambda ses: e)
    assert app._companeros(yo) == []
