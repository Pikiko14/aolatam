"""La Torre de Babel (server/torre_babel.py): pisos, corridas solo y party, premios, final y ranking."""
import pathlib
import struct
import sys
from types import SimpleNamespace

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import equipos
import eventos_mundo
import presencia
import torre_babel as tb
import totem_war


class Bicho:
    def __init__(self, eid, npc_type):
        self.entity_id, self.npc_type, self.hp, self.hp_max = eid, npc_type, 100, 100
        self.atk = self.defensa = self.matk = self.mdef = 1


@pytest.fixture()
def mundo(tmp_path, monkeypatch):
    """Sesiones de mentira y las funciones del servidor que usa la torre, apuntadas."""
    monkeypatch.setattr(tb, 'DB_PATH', tmp_path / 'torre.db')
    monkeypatch.setattr(tb, '_CORRIDAS', {})
    monkeypatch.setattr(equipos, '_DE_QUIEN', {})
    monkeypatch.setattr(equipos, '_GRUPOS', {})
    w = SimpleNamespace(viajes=[], sacados=[], premios=[], carteles=[], sesiones=[])
    monkeypatch.setattr(app, '_SIG_GENERADO', [96_000_000])

    def poner(ses, eid, npc_type, tile, zona):
        m = Bicho(eid, npc_type)
        ses.monstruos[eid] = m
        for s in w.sesiones:                      # la copia comparte los bichos
            s.monstruos[eid] = m
        return m
    monkeypatch.setattr(app, '_poner_generado', poner)

    def viajar(ses, addr, por, motivo=''):
        w.viajes.append((ses.personaje.nombre, por['destino']))
        ses.personaje.stage = por['destino']
    monkeypatch.setattr(app, '_viajar_por_portal', viajar)

    def sacar(ses, stage, x=None, y=None):
        w.sacados.append(ses.personaje.nombre)
        ses.personaje.stage = stage
    monkeypatch.setattr(app, '_sincronizar_cambio_mapa', sacar)
    monkeypatch.setattr(app, '_aplicar_efectos', lambda ses, addr, ef, motivo='': w.premios.append(
        (ses.personaje.nombre, ef)))
    monkeypatch.setattr(totem_war, 'cartel_deslizante', lambda t: (w.carteles.append(t), b'\x28\x01')[1])
    monkeypatch.setattr(presencia, 'clave_de_mapa', lambda ses, stage: (stage, eventos_mundo._clave_corrida(ses)))
    monkeypatch.setattr(presencia, '_vivas', lambda clave: [s for s in w.sesiones if s.personaje.stage == clave[0]
                                                            and eventos_mundo._clave_corrida(s) == clave[1]])
    monkeypatch.setattr(tb, 'PAUSA', 0)

    def nueva(cid, nombre):
        env = []
        s = SimpleNamespace(personaje=SimpleNamespace(char_id=cid, nombre=nombre, stage=41), monstruos={},
                            enviados=env, muerto=False)
        s.enviar = lambda *pk: env.extend(pk)
        s.volcar = lambda: None
        w.sesiones.append(s)
        return s
    w.nueva = nueva
    return w


def test_hay_60_pisos_del_nivel_1_al_60_con_sus_stats():
    pisos = tb.pisos()
    assert [p['piso'] for p in pisos] == list(range(1, 61)) and [p['nivel'] for p in pisos] == list(range(1, 61))
    assert all(p['hp'] > 0 and p['atk'] > 0 and p['def'] > 0 and p['npc_type'] for p in pisos)
    assert pisos[0]['hp'] < pisos[29]['hp'] < pisos[59]['hp']          # cuesta mas arriba


def test_solo_no_se_entra_en_party_ni_party_sin_ella(mundo):
    a = mundo.nueva(1, 'Impacty')
    equipos._DE_QUIEN.update({1: 1})
    equipos._GRUPOS.update({1: [a]})
    assert 'leave your party' in tb.iniciar(a, '?', tb.SOLO)
    equipos._DE_QUIEN.clear()
    equipos._GRUPOS.clear()
    assert 'need to be in a party' in tb.iniciar(a, '?', tb.PARTY)
    assert mundo.viajes == []


def test_una_corrida_solo_del_piso_1_al_siguiente(mundo):
    a = mundo.nueva(1, 'Impacty')
    assert tb.iniciar(a, '?', tb.SOLO) is None and mundo.viajes == [('Impacty', tb.STAGE)]
    tb.al_entrar(a)
    c = tb.corrida(a)
    jefe = a.monstruos[c['jefe']]
    p1 = tb.pisos()[0]
    assert (jefe.npc_type, jefe.hp_max, jefe.atk) == (p1['npc_type'], p1['hp'], p1['atk'])
    tb.al_morir(a, jefe)
    assert c['piso'] == 2 and c['jefe'] in a.monstruos and a.monstruos[c['jefe']].npc_type == tb.pisos()[1]['npc_type']
    assert any('Floor 1 cleared' in t for t in mundo.carteles)


def test_en_party_empieza_el_lider_invita_y_el_jefe_sale_x2(mundo):
    a, b = mundo.nueva(1, 'Impacty'), mundo.nueva(2, 'Baco')
    b.canal_lua = 1
    equipos._DE_QUIEN.update({1: 1, 2: 1})
    equipos._GRUPOS.update({1: [a, b]})
    assert 'Only the party leader' in tb.iniciar(b, '?', tb.PARTY)          # el que no es lider no empieza
    assert tb.iniciar(a, '?', tb.PARTY) is None
    invitacion = [p[2:-1].decode('latin1') for p in b.enviados if p[2:].startswith(b'TorreInvitacion(')]
    assert invitacion == ['TorreInvitacion("Impacty",{"Solo","Party"},60)']
    assert mundo.viajes == [('Impacty', tb.STAGE)]                           # Baco no se mueve hasta aceptar
    tb.al_entrar(a)
    c = tb.corrida(a)
    p1 = tb.pisos()[0]
    jefe = a.monstruos[c['jefe']]
    assert (jefe.hp_max, jefe.atk, jefe.defensa) == (int(p1['hp'] * 2), int(p1['atk'] * 2), int(p1['def'] * 2))
    assert tb.iniciar(b, '?', tb.PARTY) is None                              # acepta: se une a la misma corrida
    assert tb.corrida(b) is c and c['nombres'] == {'Impacty', 'Baco'}
    assert mundo.viajes[-1] == ('Baco', tb.STAGE)
    tb.al_entrar(b)                                                          # no saca otro jefe
    assert len(a.monstruos) == 1


def test_sin_launcher_nuevo_la_invitacion_llega_por_el_chat(mundo):
    a, b = mundo.nueva(1, 'Impacty'), mundo.nueva(2, 'Baco')
    equipos._DE_QUIEN.update({1: 1, 2: 1})
    equipos._GRUPOS.update({1: [a, b]})
    tb.iniciar(a, '?', tb.PARTY)
    assert any(b'update your launcher' in p for p in b.enviados)


def test_cada_diez_pisos_hay_premio_para_todos(mundo):
    a = mundo.nueva(1, 'Impacty')
    tb.iniciar(a, '?', tb.SOLO)
    tb.al_entrar(a)
    c = tb.corrida(a)
    c['piso'] = 10
    tb.poner_jefe(a, c)
    tb.al_morir(a, a.monstruos[c['jefe']])
    assert len(mundo.premios) == 1 and sum(n for _, n in mundo.premios[0][1][0][1]) == 1
    assert all(t in tb.TICKETS for t, _ in mundo.premios[0][1][0][1])


def test_morir_y_salir_acaba_la_corrida_y_va_al_ranking(mundo):
    a = mundo.nueva(1, 'Impacty')
    tb.iniciar(a, '?', tb.SOLO)
    tb.al_entrar(a)
    c = tb.corrida(a)
    for _ in range(3):
        tb.al_morir(a, a.monstruos[c['jefe']])
    tb.antes_de_viajar(a, 41)                     # revive fuera
    assert tb.corrida(a) is None
    assert tb.ranking(tb.SOLO)[0][:2] == ['Impacty', 3]
    a.personaje.stage = tb.STAGE                  # vuelve a entrar sin corrida: fuera
    tb.al_entrar(a)
    assert mundo.sacados == ['Impacty']


def test_conquistar_el_60_saca_a_todos_y_guarda_los_60(mundo):
    a = mundo.nueva(1, 'Impacty')
    tb.iniciar(a, '?', tb.SOLO)
    tb.al_entrar(a)
    c = tb.corrida(a)
    c['piso'] = tb.total_pisos()
    tb.poner_jefe(a, c)
    tb.al_morir(a, a.monstruos[c['jefe']])
    assert tb.corrida(a) is None and mundo.sacados == ['Impacty']
    assert tb.ranking(tb.SOLO)[0][1] == 60 and any('conquered' in t for t in mundo.carteles)


def test_el_ranking_va_por_modo_y_por_pisos(mundo):
    tb.guardar(tb.SOLO, {'A'}, 5, 100)
    tb.guardar(tb.SOLO, {'B'}, 9, 300)
    tb.guardar(tb.SOLO, {'C'}, 9, 200)
    tb.guardar(tb.PARTY, {'X', 'Y'}, 20, 50)
    assert [f[0] for f in tb.ranking(tb.SOLO)] == ['C', 'B', 'A']
    assert tb.ranking(tb.PARTY) == [['X, Y', 20, '0:50']]


def test_la_ventana_se_abre_cambia_de_modo_y_entra(mundo):
    a = mundo.nueva(1, 'Impacty')
    assert tb.procesar(a, struct.pack('<BII', tb.CMD_TORRE, 1, 0))
    textos = [p[2:-1].decode('latin1') for p in a.enviados]
    assert 'function TorreAbrir' in textos[0] and textos[1].startswith('TorreAbrir({"Solo","Party"},60)')
    tb.procesar(a, struct.pack('<BII', tb.CMD_TORRE, 2, 1))
    assert a.enviados[-1][2:-1].startswith(b'TorreRanking(1,')
    tb.procesar(a, struct.pack('<BII', tb.CMD_TORRE, 3, 1))                 # party sin party
    assert b'TorreAviso(' in a.enviados[-1]
    tb.procesar(a, struct.pack('<BII', tb.CMD_TORRE, 3, 0))
    assert a.enviados[-1][2:-1] == b'TorreCerrar()' and mundo.viajes == [('Impacty', tb.STAGE)]
    assert not tb.procesar(a, struct.pack('<BII', 168, 1, 0))


def test_el_mapa_tiene_60_arenas_y_cada_puente_su_cortina():
    import json
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))
    import mpcio
    lay = tb.mapa()
    assert len(lay['pisos']) == 60 and all('cortina' in d and 'puente' in d for d in lay['pisos'][:59])
    m = mpcio.leer((RAIZ / 'parches' / 'extras' / 'map' / 'map133.mpc').read_bytes())
    pisa = lambda x, y: m['celdas'][(y * m['w'] + x) * 6 + 1] == 0
    assert pisa(*tb.entrada()) and all(pisa(*d['centro']) for d in lay['pisos'])
    assert all(pisa(*t) for d in lay['pisos'][:59] for t in d['puente'])
    # Entre dos arenas solo se pasa por el puente: lo de alrededor es cielo.
    x, y = lay['pisos'][0]['cortina'][0]
    assert not pisa(x, y - 2) and not pisa(x, y + 4)


def test_las_cortinas_cierran_el_puente_hasta_matar_al_jefe(mundo):
    a = mundo.nueva(1, 'Impacty')
    tb.iniciar(a, '?', tb.SOLO)
    a.personaje.tile_x, a.personaje.tile_y = tb.casilla_jefe(1)
    tb.al_entrar(a)
    assert sum(1 for p in a.enviados if p[:2] == b'\x0e\x00') == 59 * 3      # todas las cortinas, del 1 al 59
    puente = tb.mapa()['pisos'][0]['puente']
    lejos = puente[-1]
    assert tb.bloquear_paso(a, tb.casilla_jefe(1), lejos)
    c = tb.corrida(a)
    n = len(a.enviados)
    tb.al_morir(a, a.monstruos[c['jefe']])
    quitadas = [p for p in a.enviados[n:] if p[:2] == b'\x07\x00']
    assert len(quitadas) == 3
    assert not tb.bloquear_paso(a, tb.casilla_jefe(1), lejos)                 # el puente 1 ya esta abierto
    assert tb.bloquear_paso(a, tb.casilla_jefe(2), tb.mapa()['pisos'][1]['puente'][-1])   # el 2 aun no
