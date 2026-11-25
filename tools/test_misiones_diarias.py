"""Misiones diarias y semanales con racha (25/11/2026, server/misiones_diarias.py)."""
import datetime as dt
import pathlib
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import misiones_diarias as md  # noqa: E402

DIA = dt.datetime(2026, 11, 25, 15, 0)


@pytest.fixture
def jug(tmp_path, monkeypatch):
    monkeypatch.setattr(md, 'DB_PATH', tmp_path / 'misiones.db')
    avisos, exp, oro, items = [], [], [], []
    monkeypatch.setattr(md, '_aviso', lambda s, t: avisos.append(t))
    monkeypatch.setattr(app, '_dar_exp_y_creditos', lambda s, exp=0, creditos=0: exp_.append(exp))
    exp_ = exp
    import trade_routes
    monkeypatch.setattr(trade_routes, '_cambiar_oro', lambda s, d: oro.append(d))
    monkeypatch.setattr(app, '_gm_dar_item', lambda s, it, n=1: items.append(it))
    ses = NS(personaje=NS(char_id=7, nombre='Tester', nivel=50))
    return NS(ses=ses, avisos=avisos, exp=exp, oro=oro, items=items)


def _cumplir_diarias(ses, ahora):
    for per, m in md.de_hoy(ahora):
        if per.startswith('d:'):
            md.sumar(ses, m['tipo'], m['n'], ahora)


def test_cada_dia_tres_iguales_para_todos_y_como_mucho_una_del_moba():
    for k in range(30):
        dia = DIA + dt.timedelta(days=k)
        hoy = [m for per, m in md.de_hoy(dia) if per.startswith('d:')]
        assert len(hoy) == 3 and len({m['id'] for m in hoy}) == 3
        assert sum(m['tipo'].startswith('moba') for m in hoy) <= 1
        assert hoy == [m for per, m in md.de_hoy(dia.replace(hour=1)) if per.startswith('d:')]
    semana = [m['id'] for per, m in md.de_hoy(DIA) if per.startswith('w:')]
    assert len(semana) == 3 and semana == [m['id'] for per, m in md.de_hoy(DIA + dt.timedelta(days=1))
                                           if per.startswith('w:')]


def test_progreso_y_cobro_una_sola_vez(jug):
    per, m = next((p, m) for p, m in md.de_hoy(DIA) if p.startswith('d:'))
    assert md.sumar(jug.ses, m['tipo'], m['n'] - 1, DIA) == []
    assert md.sumar(jug.ses, m['tipo'], 5, DIA) == [(per, m)]
    assert len(jug.exp) == 1 and jug.exp[0] > 0 and jug.oro == [300 * 50]
    assert 'done!' in jug.avisos[-1]
    assert md.sumar(jug.ses, m['tipo'], 5, DIA) == []            # ya cobrada
    assert any(l.endswith('(done)') for l in md.lineas(jug.ses, DIA))


def test_la_racha_sube_dia_a_dia_y_se_corta(jug):
    assert md.racha(7, DIA) == 0
    _cumplir_diarias(jug.ses, DIA)
    assert md.racha(7, DIA) == 1 and 'Streak: 1 day' in jug.avisos[-1]
    oro_dia1 = jug.oro[0]
    for k in (1, 2):
        _cumplir_diarias(jug.ses, DIA + dt.timedelta(days=k))
    assert md.racha(7, DIA + dt.timedelta(days=2)) == 3
    assert 'Streak bonus' in jug.avisos[-1] and jug.items        # el dia 3, su gacha
    assert max(jug.oro) > oro_dia1                               # mas premio con la racha
    assert md.racha(7, DIA + dt.timedelta(days=4)) == 0          # un dia sin hacerlas: se corta
    _cumplir_diarias(jug.ses, DIA + dt.timedelta(days=4))
    assert md.racha(7, DIA + dt.timedelta(days=4)) == 1


def test_el_multiplicador_tiene_tope():
    assert md.multiplicador(1) == 1.0 and md.multiplicador(4) == pytest.approx(1.3) and md.multiplicador(50) == 2.0


def test_un_jefe_cuenta_para_todos_los_que_le_pegaron(jug, monkeypatch):
    otro = NS(personaje=NS(char_id=8, nombre='Otro', nivel=50))
    monkeypatch.setattr(app, '_tw_sesiones', lambda: [jug.ses, otro])
    vistos = []
    monkeypatch.setattr(md, 'sumar', lambda s, tipo, cuanto=1, ahora=None: vistos.append((s.personaje.char_id, tipo)))
    md.al_matar(jug.ses, NS(npc_type=707, dano_por={7: 100, 8: 50}))
    assert vistos == [(7, 'matar'), (7, 'jefe'), (8, 'jefe')]
    vistos.clear()
    md.al_matar(jug.ses, NS(npc_type=1, dano_por={7: 100}))
    assert vistos == [(7, 'matar')]


def test_el_comando():
    assert app._gm_parsear('/missions') == ('misiones_diarias',) and 'misiones_diarias' in app.COMANDOS_DE_JUGADOR


def test_el_panel(jug, monkeypatch):
    """"Que tengamos algun panel para las diarias" (25/11/2026): la ventana 58800 y su boton 59007."""
    import struct
    import canal_lua
    enviados = []
    jug.ses.enviar = lambda *p: enviados.extend(p)
    jug.ses.personaje.nombre = 'Tester'
    titulo, racha, racha2, pie, filas = md.vista(jug.ses, DIA)
    assert titulo.startswith('Daily reset in 9h 00m') and 'Weekly reset in 4d 9h' in titulo
    assert racha.startswith('No streak yet') and 'day 3 Gear Gacha, day 7 Lv60 Box' in racha2
    assert len(filas) == 6 and all(f[1].startswith('0 / ') and f[2] == 0 for f in filas)
    assert md.procesar(jug.ses, struct.pack('<BII', md.CMD_MD, 1, 0))      # el boton de la barra
    assert jug.ses._md_abierto and any(b'MDAbrir' in p for p in enviados)
    # mientras esta abierto se refresca solo
    enviados.clear()
    per, m = next((p, m) for p, m in md.de_hoy() if p.startswith('d:'))
    md.sumar(jug.ses, m['tipo'], 1)
    assert any(b'MDDatos' in p for p in enviados)
    # cerrado con la X: ya no
    md.procesar(jug.ses, struct.pack('<BII', md.CMD_MD, 0, 0))
    enviados.clear()
    md.sumar(jug.ses, m['tipo'], 1)
    assert not any(b'MDDatos' in p for p in enviados)
    # cliente sin el parche: por el chat
    md.procesar(jug.ses, struct.pack('<BII', md.CMD_MD, 9, 0))
    assert any(a.startswith('[Daily]') for a in jug.avisos)
    assert not md.procesar(jug.ses, struct.pack('<BII', 175, 1, 0))
    assert 'OnCommandMisiones' in md.SALUDO_LUA and canal_lua.CARPETA.joinpath('misiones.lua').exists()


def test_la_racha_en_el_panel(jug):
    _cumplir_diarias(jug.ses, DIA)
    _t, racha, racha2, _p, filas = md.vista(jug.ses, DIA)
    assert racha.startswith('Streak: 1 day') and 'Next in 2 days' in racha2       # dia 3: pasado manana
    assert [f[1] for f in filas[:3]] == ['Done!'] * 3 and all(f[2] == 100 for f in filas[:3])
    _t, racha, racha2, _p, _f = md.vista(jug.ses, DIA + dt.timedelta(days=1))
    assert 'finish today to keep it' in racha and 'Next in 1 day' in racha2
    _t, _r, racha2, _p, _f = md.vista(jug.ses, DIA + dt.timedelta(days=1, hours=1))
    _cumplir_diarias(jug.ses, DIA + dt.timedelta(days=1))
    _t, _r, racha2, _p, _f = md.vista(jug.ses, DIA + dt.timedelta(days=2))
    assert 'Next: today!' in racha2


def test_la_ventana_del_cliente():
    sys.path.insert(0, str(RAIZ / 'tools'))
    import ventana_misiones as vm
    x = vm.bloque()
    assert 'id="58800"' in x and x.count('WND_CLASS_PROGRESS') == 6
    w1 = vm.wnd01('<root>\n\t\t<child>59005</child>\n</root>\n')
    assert '<child>59007</child>' in w1 and 'OnCommandMisiones' in w1 and vm.wnd01(w1) == w1
