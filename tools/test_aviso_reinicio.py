"""Aviso de reinicio a todos los jugadores (05/11/2026)."""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import app  # noqa: E402
import aviso_reinicio as ar  # noqa: E402


class Loop:
    def __init__(self):
        self.prog = []

    def call_later(self, demora, fn):
        h = type('H', (), {'cancel': lambda s: self.prog.remove(e)})()
        e = (demora, fn, h)
        self.prog.append(e)
        return h


def test_cuenta_atras_de_5_minutos(monkeypatch):
    enviados = []
    monkeypatch.setattr(ar, 'difundir', lambda t: enviados.append(t) or 3)
    loop = Loop()
    assert ar.programar(5, loop=loop) == [300, 180, 120, 60, 30]
    assert len(enviados) == 1 and '5 minutes' in enviados[0] and 'desconectate' in enviados[0]
    assert sorted(d for d, _, _ in loop.prog) == [120, 180, 240, 270]
    for _, fn, _ in sorted(loop.prog, key=lambda e: e[0]):
        fn()
    assert '30 seconds' in enviados[-1] and 'in 1 minute.' in enviados[-2]
    assert all(t.encode('latin-1') for t in enviados)


def test_cancelar(monkeypatch):
    enviados = []
    monkeypatch.setattr(ar, 'difundir', lambda t: enviados.append(t) or 0)
    loop = Loop()
    ar.programar(2, loop=loop)
    assert loop.prog
    assert ar.comando(['reinicio', 'cancelar']) == 'cuenta atras cancelada'
    assert not loop.prog and enviados[-1] == ar.CANCELADO


def test_el_comando_gm_se_reconoce_sin_jugador():
    assert app._gm_parsear('reinicio 5') == ('aviso_reinicio', ['reinicio', '5'])
    assert app._gm_parsear('/aviso Hola a todos')[0] == 'notice'      # el de siempre, no se pisa
    assert ar.comando(['reinicio', '999']).startswith('los minutos')


def test_la_otra_cola_de_gm_txt_tambien_lo_entiende(monkeypatch):
    import gm
    monkeypatch.setattr(ar, 'difundir', lambda t: 0)
    assert gm.ejecutar_linea(None, 'reinicio cancelar') in ('GM no habia cuenta atras', 'GM cuenta atras cancelada')
    assert gm.ejecutar_linea(None, '/reinicio 999').startswith('GM los minutos')
