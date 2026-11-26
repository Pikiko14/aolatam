"""El calendario semanal de eventos (25/11/2026, server/calendario.py y plantillas/calendario.json)."""
import datetime as dt
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import calendario  # noqa: E402

LUNES = dt.datetime(2026, 11, 23)          # un lunes


def test_la_semana_no_tiene_eventos_que_se_pisen():
    ev = calendario.config()['eventos']
    por_dia = {}
    for d, h, c in calendario.semana():
        assert c in ev, c
        hh, mm = (int(x) for x in h.split(':'))
        ini = hh * 60 + mm
        por_dia.setdefault(d, []).append((ini, ini + int(ev[c]['duracion']), c))
    assert sorted(por_dia) == list(range(7))                     # algo todos los dias
    for d, lista in por_dia.items():
        lista.sort()
        for (a, fa, ca), (b, _fb, cb) in zip(lista, lista[1:]):
            assert fa <= b, (calendario.DIAS[d], ca, cb)


def test_cada_evento_toma_sus_horas_del_calendario():
    import daily_events
    import league_war
    import moba_lobby
    import totem_war
    assert totem_war._horario() == ((2, 21, 0), (5, 14, 0))
    assert league_war._schedules() == [{'weekday': 1, 'start': '21:00'}, {'weekday': 6, 'start': '18:00'},
                                       {'weekday': 6, 'start': '22:30'}]
    quick = [(s['day'], s['start']) for s in daily_events.slots() if s['alias'] == 'quick']
    assert quick == [(1, '18:00'), (4, '21:00')]                 # 0=domingo en daily_events
    # martes 19:00: el siguiente MOBA es el miercoles a las 14:00 (el martes a las 21 es la League War)
    martes = (LUNES + dt.timedelta(days=1)).replace(hour=19).astimezone()
    assert moba_lobby.proxima(martes) == (LUNES + dt.timedelta(days=2)).replace(hour=14).astimezone()


def test_el_holy_battlefield_abre_a_las_horas_del_calendario(monkeypatch):
    import competiciones
    abiertos = []
    monkeypatch.setattr(competiciones, '_modo_pruebas', lambda: False)
    monkeypatch.setattr(competiciones, 'iniciar', lambda stage, *a, **k: abiertos.append((stage, k.get('inicio'))))
    monkeypatch.setattr(competiciones, 'fase', lambda r, t: 'cerrada')
    monkeypatch.setattr(competiciones, '_RONDAS', {})
    viernes = (LUNES + dt.timedelta(days=4)).replace(hour=9, minute=50).astimezone()
    competiciones.cron(viernes)
    assert [s for s, _ in abiertos] == [112]
    abiertos.clear()
    competiciones.cron(viernes.replace(day=viernes.day - 1))     # el jueves no hay
    assert abiertos == []


def test_el_angel_arena_solo_abre_el_tramo_lv50_89(monkeypatch):
    import competiciones
    abiertos = []
    monkeypatch.setattr(competiciones, '_modo_pruebas', lambda: False)
    monkeypatch.setattr(competiciones, 'iniciar', lambda stage, *a, **k: abiertos.append((stage, a)))
    monkeypatch.setattr(competiciones, 'fase', lambda r, t: 'cerrada')
    monkeypatch.setattr(competiciones, '_RONDAS', {})
    martes = (LUNES + dt.timedelta(days=1)).replace(hour=15, minute=50).astimezone()
    competiciones.cron(martes)
    assert len(abiertos) == 1 and abiertos[0][0] == 159 and competiciones.tramo(abiertos[0][1][2])[0] == 50
    abiertos.clear()
    competiciones.cron(LUNES.replace(hour=19, minute=20).astimezone())      # el horario viejo por tramos ya no
    assert abiertos == []


def test_aviso_30_minutos_antes_y_una_sola_vez(monkeypatch):
    import competiciones
    carteles = []
    monkeypatch.setattr(competiciones, 'anunciar', carteles.append)
    monkeypatch.setattr(calendario, '_AVISADOS', set())
    lunes = LUNES.replace(hour=13, minute=30).astimezone()
    calendario.cron(lunes)
    calendario.cron(lunes + dt.timedelta(seconds=40))
    assert carteles == ['Angel MOBA starts in 30 minutes (14:00)! Talk to Angel MOBA in the Sign Up Office.']
    calendario.cron(lunes.replace(hour=12))                       # 12:30: el del tesoro de las 13:00, no otro del MOBA
    assert len(carteles) == 2 and carteles[1].startswith('Treasure Hunt starts in 30 minutes (13:00)')


def test_al_conectar_y_el_comando(monkeypatch):
    lunes = LUNES.replace(hour=15).astimezone()
    assert calendario.texto_hoy(lunes) == ("Today's events: 17:00 Santa Clausula, 18:00 Quick Reflexes, 18:40 Pet Tournament, "
                                          "19:30 World Boss, 20:15 Treasure Hunt, "
                                          "21:00 Angel MOBA, 22:00 Hunted Hunter, 23:00 World Boss. "
                                          "Type /events for the week.")
    assert calendario.texto_hoy(lunes.replace(hour=23, minute=50)).startswith('No more events today')
    assert calendario.lineas_semana()[0] == ('Monday: 12:00 World Boss, 13:00 Treasure Hunt, 14:00 Angel MOBA, '
                                             '17:00 Santa Clausula, 18:00 Quick Reflexes, 18:40 Pet Tournament, '
                                             '19:30 World Boss, '
                                             '20:15 Treasure Hunt, '
                                             '21:00 Angel MOBA, 22:00 Hunted Hunter, 23:00 World Boss')
    assert app._gm_parsear('/events') == ('calendario',) and 'calendario' in app.COMANDOS_DE_JUGADOR
