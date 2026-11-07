"""Reglas "matar X monstruos" del editor (server/eventos_propios.py)."""
import json
import pathlib
import random
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import eventos_propios as evp


def _reglas(tmp_path, monkeypatch, *reglas):
    f = tmp_path / 'eventos_propios.json'
    f.write_text(json.dumps({'reglas': list(reglas)}), encoding='utf-8')
    monkeypatch.setattr(evp, 'ARCHIVO', f)
    monkeypatch.setattr(evp, '_cache', {'mtime': None, 'reglas': []})
    monkeypatch.setattr(evp, '_cuentas', {})
    monkeypatch.setattr(evp, '_hechas', set())
    monkeypatch.setattr(evp, '_portales', {})


def _ses(cid, stage=900):
    return NS(personaje=NS(char_id=cid, stage=stage, nombre='pj%d' % cid, tile_x=10, tile_y=10))


def _mob(npc=8138, propio=None):
    return NS(npc_type=npc, propio=propio, tile_x=5, tile_y=6)


REGLA = dict(id='r', stage=900, matar=dict(mobs=[8138, 'dc50'], cantidad=3, alcance='jugador', repetir=True),
             premios=[dict(tipo='dar', item=89055, cantidad=1)])


def test_cuenta_por_jugador_y_se_repite(tmp_path, monkeypatch):
    _reglas(tmp_path, monkeypatch, REGLA)
    a, b = _ses(1), _ses(2)
    assert not evp.al_morir(a, _mob()) and not evp.al_morir(a, _mob(1, 'dc50'))
    assert not evp.al_morir(b, _mob())                       # b lleva su propia cuenta
    assert evp.al_morir(a, _mob())[0][0]['id'] == 'r'
    assert evp.progreso(a, 'r') == (0, 3) and evp.progreso(b, 'r') == (1, 3)


def test_otros_mobs_u_otro_mapa_no_cuentan(tmp_path, monkeypatch):
    _reglas(tmp_path, monkeypatch, dict(REGLA, matar=dict(REGLA['matar'], cantidad=1)))
    assert not evp.al_morir(_ses(1), _mob(9999))
    assert not evp.al_morir(_ses(1, stage=41), _mob())
    assert evp.al_morir(_ses(1), _mob())


def test_alcance_mapa_y_una_sola_vez(tmp_path, monkeypatch):
    # En un mapa normal (el 41) todos suman a la misma cuenta.
    _reglas(tmp_path, monkeypatch, dict(REGLA, stage=41, matar=dict(mobs=[], cantidad=2, alcance='mapa', repetir=False)))
    assert not evp.al_morir(_ses(1, 41), _mob(1))
    assert evp.al_morir(_ses(2, 41), _mob(2))                # la segunda baja del mapa, de otro jugador
    assert not evp.al_morir(_ses(1, 41), _mob(1)) and not evp.al_morir(_ses(1, 41), _mob(1))


def test_en_una_instancia_cada_copia_cuenta_y_ve_lo_suyo(tmp_path, monkeypatch):
    # El 900 es instancia: dos jugadores que van solos estan en copias distintas.
    _reglas(tmp_path, monkeypatch, dict(REGLA, matar=dict(mobs=[], cantidad=2, alcance='mapa', repetir=True)))
    a, b = _ses(1), _ses(2)
    assert evp.sala_de(a) != evp.sala_de(b) and evp.sala_de(_ses(1, 41)) is None
    assert not evp.al_morir(a, _mob(1)) and not evp.al_morir(b, _mob(2))   # una baja en cada copia
    assert evp.al_morir(a, _mob(1))                                        # la segunda de la copia de a
    eid = evp.abrir_portal(900, (5, 6), 16, (134, 70), 60, sala=evp.sala_de(a))
    assert evp.poblar(900) == []                                            # no va al reparto general
    assert len(evp.de_sala(900, evp.sala_de(a))) == 1 and evp.de_sala(900, evp.sala_de(b)) == []
    assert evp.pulsar(b, eid) is False                                      # b no puede usarlo


def test_el_portal_de_una_instancia_llega_a_los_de_su_copia(monkeypatch):
    # presencia guarda a los de una instancia bajo (stage, copia): con _vivas(900) no salia nadie.
    import eventos_mundo
    import presencia
    a, b = _ses(1), _ses(2)
    for s in (a, b):
        s.cerrada = False
    sa, sb = evp.sala_de(a), evp.sala_de(b)
    clave = (lambda s, st: (900, s)) if eventos_mundo.grupo_de_instancia(900) else (lambda s, st: 900)
    monkeypatch.setattr(presencia, '_POR_MAPA', {clave(sa, 900): [a], **({clave(sb, 900): [b]} if clave(sb, 900) != clave(sa, 900) else {})})
    if clave(sa, 900) == 900:
        presencia._POR_MAPA[900] = [a, b]
    assert evp.destinatarios(900, sa) == [a]
    assert evp.destinatarios(900, sb) == [b]


def test_reglas_invalidas_se_ignoran(tmp_path, monkeypatch):
    _reglas(tmp_path, monkeypatch, dict(REGLA, premios=[]), dict(REGLA, id='', ))
    assert evp.reglas() == []
    assert evp.validar(dict(REGLA, premios=[dict(tipo='portal', destino=41)])) == [
        '"portal" sin mapa o casilla de llegada']


def test_premios_a_efectos():
    efectos, ag, portales = evp.efectos_de([
        dict(tipo='dar', item=5, cantidad=2), dict(tipo='soltar', items=[[7, 1]], prob=100),
        dict(tipo='soltar', items=[[8, 1]], prob=0), dict(tipo='oro', cantidad=500),
        dict(tipo='ag', cantidad=50), dict(tipo='portal', destino=41, llegada=[1, 2])], rnd=random.Random(1))
    assert efectos == [('dar', [(5, 2)]), ('dar', [(7, 1)]), ('oro', 500)]
    assert ag == 50 and portales[0]['destino'] == 41


def test_portal_temporal_se_ve_al_entrar_y_caduca(tmp_path, monkeypatch):
    _reglas(tmp_path, monkeypatch)
    ahora = [1000.0]
    monkeypatch.setattr(evp.time, 'time', lambda: ahora[0])
    eid = evp.abrir_portal(900, (5, 6), 41, (160, 36), 60)
    assert evp.portal(eid)['destino'] == 41
    assert len(evp.poblar(900)) == 1 and evp.poblar(41) == []
    ahora[0] += 61
    assert evp.portal(eid) is None and evp.poblar(900) == []


def test_un_solo_portal_por_copia_y_otra_baja_lo_alarga(monkeypatch):
    """El jefe de Dark Cavern reaparece cada minuto y medio: cada baja abria otro portal y se apilaban (02/11/2026)."""
    import time
    eid = evp.abrir_portal(900, (5, 6), 16, (134, 70), 60, sala='A')
    assert evp.portal_abierto(900, 16, sala='A') == eid
    assert evp.portal_abierto(900, 16, sala='B') is None          # otra copia abre el suyo
    assert evp.portal_abierto(900, 41, sala='A') is None          # otro destino tambien
    antes = evp._portales[eid]['hasta']
    monkeypatch.setattr(time, 'time', lambda: antes - 10)
    evp.alargar(eid, 300)
    assert evp._portales[eid]['hasta'] == antes + 290


# ------------------------------------------------------------------ disparadores nuevos (07/11/2026)
def _limpio(monkeypatch):
    monkeypatch.setattr(evp, '_ultima', {})


def test_al_entrar_una_vez_por_jugador(tmp_path, monkeypatch):
    _limpio(monkeypatch)
    _reglas(tmp_path, monkeypatch, dict(id='bienv', cuando='entrar', stage=900, entrar=dict(repetir=False),
                                        premios=[dict(tipo='exp', cantidad=500)]))
    a = _ses(1)
    a.personaje.nivel = 10
    assert evp.al_entrar(a)[0][0]['id'] == 'bienv'
    assert evp.al_entrar(a) == []                       # solo la primera vez
    assert evp.al_entrar(_ses(2, stage=3)) == []        # otro mapa
    assert evp.extras_de(evp.al_entrar(_ses(3))[0][1])['exp'] == 500


def test_al_entrar_con_enfriamiento(tmp_path, monkeypatch):
    _limpio(monkeypatch)
    _reglas(tmp_path, monkeypatch, dict(id='e', cuando='entrar', stage=900, entrar=dict(repetir=True, enfriamiento_min=10),
                                        premios=[dict(tipo='oro', cantidad=5)]))
    a = _ses(1)
    assert evp.al_entrar(a, ahora=1000) and not evp.al_entrar(a, ahora=1300) and evp.al_entrar(a, ahora=1700)


def test_condiciones_de_nivel_y_franja(tmp_path, monkeypatch):
    r = dict(si=dict(nivel_min=20, nivel_max=40))
    assert not evp.cumple_si(r, NS(nivel=10)) and evp.cumple_si(r, NS(nivel=30)) and not evp.cumple_si(r, NS(nivel=50))
    import time
    t = time.mktime((2026, 11, 7, 22, 30, 0, 0, 0, -1))
    assert evp.cumple_si(dict(si=dict(desde='20:00', hasta='23:00')), None, t)
    assert not evp.cumple_si(dict(si=dict(desde='08:00', hasta='12:00')), None, t)
    assert evp.cumple_si(dict(si=dict(desde='22:00', hasta='02:00')), None, t)       # cruza la medianoche
    assert not evp.cumple_si(dict(si=dict(prob=0)), None, t)


def test_horario_a_la_hora_y_cada_n(tmp_path, monkeypatch):
    _limpio(monkeypatch)
    import time
    _reglas(tmp_path, monkeypatch,
            dict(id='h', cuando='horario', stage=900, horario=dict(horas=['20:00']),
                 premios=[dict(tipo='aviso_global', texto='hola')]),
            dict(id='c', cuando='horario', stage=0, horario=dict(cada_min=30), premios=[dict(tipo='aviso_global', texto='x')]))
    t20 = time.mktime((2026, 11, 7, 20, 0, 5, 0, 0, -1))
    assert [r['id'] for r, _ in evp.horario_pendientes(t20)] == ['h']               # 'c' arranca su reloj
    assert evp.horario_pendientes(t20 + 20) == []                                   # una vez por hora marcada
    assert [r['id'] for r, _ in evp.horario_pendientes(t20 + 31 * 60)] == ['c']


def test_validar_escenarios_nuevos():
    assert evp.validar(dict(id='a', cuando='horario', stage=900, horario=dict(horas=['25:00']),
                            premios=[dict(tipo='oro', cantidad=1)]))
    assert evp.validar(dict(id='a', cuando='horario', stage=900, horario=dict(cada_min=5),
                            premios=[dict(tipo='monstruo', npc_type=209, donde='monstruo')]))       # sin casilla fija
    assert evp.validar(dict(id='a', cuando='entrar', stage=0, premios=[dict(tipo='oro', cantidad=1)]))
    assert evp.validar(dict(id='a', cuando='horario', stage=900, horario=dict(horas=['20:00']),
                            premios=[dict(tipo='monstruo', npc_type=209, cantidad=3, donde=[10, 10], segundos=600),
                                     dict(tipo='aviso_global', texto='Boss!')])) == []
    assert evp.validar(dict(REGLA, si=dict(nivel_min=50, nivel_max=10)))


def test_sitio():
    assert evp.sitio([3, 4]) == (3, 4)
    assert evp.sitio('jugador', _mob(), NS(tile_x=1, tile_y=2)) == (1, 2)
    assert evp.sitio('monstruo', _mob(), NS(tile_x=1, tile_y=2)) == (5, 6)
