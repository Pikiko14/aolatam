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
        ses.personaje.tile_x, ses.personaje.tile_y = por['llegada']
    monkeypatch.setattr(app, '_viajar_por_portal', viajar)
    w.saltos = []

    def reubicar(ses, tile, origen='spell'):
        w.saltos.append((ses.personaje.nombre, tuple(tile)))
        ses.personaje.tile_x, ses.personaje.tile_y = tile
    import desplazamientos
    monkeypatch.setattr(desplazamientos, 'reubicar', reubicar)
    monkeypatch.setattr(presencia, 'notificar_companero_accion', lambda *a, **k: None)

    def sacar(ses, stage, x=None, y=None):
        w.sacados.append(ses.personaje.nombre)
        ses.personaje.stage = stage
    monkeypatch.setattr(app, '_sincronizar_cambio_mapa', sacar)
    monkeypatch.setattr(app, '_aplicar_efectos', lambda ses, addr, ef, motivo='': w.premios.append(
        (ses.personaje.nombre, ef)))
    import clases
    _aviso = clases.aviso
    monkeypatch.setattr(clases, 'aviso', lambda t, **k: (w.carteles.append(t), _aviso(t, **k))[1])
    monkeypatch.setattr(presencia, 'clave_de_mapa', lambda ses, stage: (stage, eventos_mundo._clave_corrida(ses)))
    monkeypatch.setattr(presencia, '_vivas', lambda clave: [s for s in w.sesiones if s.personaje.stage == clave[0]
                                                            and eventos_mundo._clave_corrida(s) == clave[1]])
    monkeypatch.setattr(tb, 'PAUSA', 0)

    def nueva(cid, nombre):
        env = []
        s = SimpleNamespace(personaje=SimpleNamespace(char_id=cid, nombre=nombre, stage=41, entity_id=cid, tile_x=0,
                                                      tile_y=0), monstruos={},
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
    assert (jefe.npc_type, jefe.hp_max, jefe.atk) == (p1['npc_type'], int(p1['hp'] * 2), int(p1['atk'] * 2))   # solo x2
    tb.al_morir(a, jefe)
    assert c['piso'] == 2 and c['jefe'] in a.monstruos and a.monstruos[c['jefe']].npc_type == tb.pisos()[1]['npc_type']
    assert any('Floor 1 cleared' in t for t in mundo.carteles)


def test_en_party_empieza_el_lider_invita_y_el_jefe_sale_x3(mundo):
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
    assert (jefe.hp_max, jefe.atk, jefe.defensa) == (int(p1['hp'] * 3), int(p1['atk'] * 3), int(p1['def'] * 3))  # party x3
    assert tb.iniciar(b, '?', tb.PARTY) is None                              # acepta: se une a la misma corrida
    assert tb.corrida(b) is c and c['nombres'] == {'Impacty', 'Baco'}
    assert mundo.viajes[-1] == ('Baco', tb.STAGE)
    tb.al_entrar(b)                                                          # no saca otro jefe
    assert len(a.monstruos) == 1


def test_en_party_con_bichos_separados_hay_un_solo_jefe_y_todos_lo_ven(mundo, monkeypatch):
    """"A veces salen 2 mobs" / "si estoy en pt no veo el jefe" (03/11/2026): en el VPS cada uno de la party tiene sus
    propios bichos. El segundo que entra no saca otro jefe: recibe el mismo, dibujado, y al morir se le quita."""
    def poner(ses, eid, npc_type, tile, zona):
        m = Bicho(eid, npc_type)
        m.nombre, m.tile_x, m.tile_y, m.vivo = 'Jefe', tile[0], tile[1], True
        m.porcentaje = 100
        ses.monstruos[eid] = m                    # solo en los de quien lo saca
        return m
    monkeypatch.setattr(app, '_poner_generado', poner)
    a, b = mundo.nueva(1, 'Impacty'), mundo.nueva(2, 'Baco')
    b.canal_lua = 1
    equipos._DE_QUIEN.update({1: 1, 2: 1})
    equipos._GRUPOS.update({1: [a, b]})
    assert tb.iniciar(a, '?', tb.PARTY) is None
    tb.al_entrar(a)
    assert tb.iniciar(b, '?', tb.PARTY) is None
    tb.al_entrar(b)
    c = tb.corrida(a)
    assert list(a.monstruos) == list(b.monstruos) == [c['jefe']]
    assert a.monstruos[c['jefe']] is b.monstruos[c['jefe']]
    assert any(p[:2] == struct.pack('<H', 0x0008) for p in b.enviados)                   # a Baco se le dibuja
    jefe = a.monstruos[c['jefe']]
    jefe.hp, jefe.vivo = 0, False
    tb.al_morir(a, jefe)
    assert jefe.entity_id not in b.monstruos                                 # y se le quita al morir


def test_al_subir_de_piso_la_mascota_va_con_su_dueno_y_los_demas_la_ven(mundo, monkeypatch):
    """"No se ven los summon ni los pet" (03/11/2026): en cada salto la mascota se lleva al piso nuevo y se presenta
    otra vez a los companeros."""
    a, b = mundo.nueva(1, 'Impacty'), mundo.nueva(2, 'Baco')
    b.personaje.mascota = {'fuera': True, 'x': 0, 'y': 0}
    b.invocacion = {'entity_id': 77, 'tile_x': 0, 'tile_y': 0}
    recibidos = []
    monkeypatch.setattr(presencia, 'paquetes_mascota',
                        lambda s: [('pet', s.personaje.nombre, s.personaje.mascota['x'])] if getattr(s.personaje, 'mascota', None) else [])
    monkeypatch.setattr(presencia, 'paquetes_invocaciones',
                        lambda s: [('inv', s.personaje.nombre)] if getattr(s, 'invocacion', None) else [])
    monkeypatch.setattr(presencia, '_mandar', lambda o, *pk: recibidos.append((o.personaje.nombre,) + tuple(pk)))
    equipos._DE_QUIEN.update({1: 1, 2: 1})
    equipos._GRUPOS.update({1: [a, b]})
    assert tb.iniciar(a, '?', tb.PARTY) is None and tb.iniciar(b, '?', tb.PARTY) is None
    c = tb.corrida(a)
    c['piso'] = 2
    tb.subir(a, c)
    x, y = tb.llegada(2)
    assert b.personaje.mascota['x'] == x + 1 and (b.invocacion['tile_x'], b.invocacion['tile_y']) == (x - 1, y)
    assert ('Impacty', ('inv', 'Baco'), ('pet', 'Baco', x + 1)) in recibidos


def test_quien_ya_estuvo_en_la_torre_comparte_la_sala_de_su_party(mundo, monkeypatch):
    """"No se ve ninguna animacion de ataque de los companeros" (03/11/2026): cada uno reutilizaba la sala de su
    ultima entrada al 133 (ses.estado_mapa) y la party no compartia bichos ni golpes."""
    monkeypatch.setattr(eventos_mundo, '_CORRIDAS', {})
    a, b = mundo.nueva(1, 'Impacty'), mundo.nueva(2, 'Baco')
    for s in (a, b):
        s.personaje.stage = tb.STAGE
        s.usuario = s.personaje.nombre
    vieja_b = eventos_mundo.estado_de(b)                      # Baco estuvo antes solo en la torre
    equipos._DE_QUIEN.update({1: 1, 2: 1})
    equipos._GRUPOS.update({1: [a, b]})
    sala = eventos_mundo.estado_de(a)
    assert eventos_mundo.estado_de(b) is sala and sala is not vieja_b


def test_el_lider_invita_tambien_si_la_subida_ya_estaba_empezada(mundo):
    a, b = mundo.nueva(1, 'Impacty'), mundo.nueva(2, 'Baco')
    b.canal_lua = 1
    equipos._DE_QUIEN.update({1: 1, 2: 1})
    equipos._GRUPOS.update({1: [a, b]})
    assert tb.iniciar(a, '?', tb.PARTY) is None
    b.enviados.clear()
    assert tb.iniciar(a, '?', tb.PARTY) is None                             # vuelve a entrar: misma corrida
    assert any(p[2:].startswith(b'TorreInvitacion(') for p in b.enviados)
    assert any('invitation sent to 1' in t for t in mundo.carteles)


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
    dado = dict(mundo.premios[0][1][0][1])
    assert len(mundo.premios) == 1 and dado.pop(tb.MOUNT_COIN) == 5
    assert sum(dado.values()) == 5 and set(dado) <= set(tb.TICKETS)


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


def test_el_mapa_es_la_limitless_tower_y_cada_piso_una_sala():
    import json as _json
    import transitable
    lay = tb.mapa()
    import sys as _s
    _s.path.insert(0, str(RAIZ / 'tools' / 'editor_mapas'))
    import mpcio
    import oscurecer_torre
    torre = mpcio.leer((RAIZ / 'parches' / 'extras' / 'map' / 'map133.mpc').read_bytes())
    limitless = mpcio.leer((RAIZ / 'tools' / 'originales' / 'map110.mpc').read_bytes())
    # La misma Limitless Tower ("hazlo mas dark"): el suelo igual y cada objeto en su sitio, el decorado con su copia
    # oscura.
    assert torre['celdas'] == limitless['celdas']
    n = len(limitless['objetos'])
    assert [o[1:] for o in torre['objetos'][:n]] == [o[1:] for o in limitless['objetos']]
    # "Agrega mas objetos para que no parezca la Limitless Tower": decorado oscuro del juego en cada sala.
    assert len(torre['objetos']) - n >= 12 * 20
    assert sum(o[0] >= oscurecer_torre.ID_BASE for o in torre['objetos']) > 1000
    # "Aparezco donde no es": el suelo es el que valida el servidor, y con margen alrededor (nada de bordes).
    pisa = lambda x, y: all(transitable.se_pisa(133, x + dx, y + dy) for dx in (-2, 0, 2) for dy in (-2, 0, 2))
    assert len(lay['pisos']) == 60 and lay['salas'] == 12
    assert all(pisa(*d['centro']) and pisa(*d['llegada']) and d['centro'] != d['llegada'] for d in lay['pisos'])
    assert [d['sala'] for d in lay['pisos'][:13]] == list(range(12)) + [0]      # una sala por piso, y vuelta a empezar
    assert tb.entrada() == tb.llegada(1)
    # "Y los mob que salgan donde es": cada jefe sale en la sala donde la Limitless Tower tiene sus monstruos.
    nativos = _json.loads((RAIZ / 'server' / 'plantillas' / 'limitless_tower.json').read_text(encoding='utf-8'))
    bichos = [tuple(m['tile']) for m in nativos['spawns'] if m.get('monstruo') and m.get('zona')]
    for d in lay['pisos'][:12]:
        cx, cy = d['centro']
        assert min((x - cx) ** 2 + (y - cy) ** 2 for x, y in bichos) <= 15 ** 2


def test_al_matar_al_jefe_todos_suben_a_la_sala_siguiente(mundo):
    a, b = mundo.nueva(1, 'Impacty'), mundo.nueva(2, 'Baco')
    b.canal_lua = 1
    equipos._DE_QUIEN.update({1: 1, 2: 1})
    equipos._GRUPOS.update({1: [a, b]})
    tb.iniciar(a, '?', tb.PARTY)
    tb.al_entrar(a)
    tb.iniciar(b, '?', tb.PARTY)
    tb.al_entrar(b)
    assert (a.personaje.tile_x, a.personaje.tile_y) == tb.llegada(1) == (b.personaje.tile_x, b.personaje.tile_y)
    c = tb.corrida(a)
    tb.al_morir(a, a.monstruos[c['jefe']])
    assert sorted(mundo.saltos) == [('Baco', tb.llegada(2)), ('Impacty', tb.llegada(2))]
    assert a.monstruos[c['jefe']].npc_type == tb.pisos()[1]['npc_type'] and len(
        [m for m in a.monstruos.values() if m.hp > 0]) == 2       # el jefe nuevo (el viejo no se quita en el test)
    assert any('Going up to floor 2' in t for t in mundo.carteles)


def test_la_torre_va_sin_mapa_ni_minimapa():
    """"Sigue saliendo el mapa / el minimapa igual" (02/11/2026): el 0x0014 de la torre lleva el bit 0x20, que el
    servidor saca del stage.xml del parche (content.db es de antes y no lo tiene)."""
    import struct as _st
    import login
    assert _st.unpack_from('<I', login.flags_de_mapa(133), 2)[0] & login.SIN_MAPA


def test_los_jefes_no_se_repiten():
    """"Que los jefes no se repitan" (02/11/2026): 60 pisos, 60 jefes distintos (ni el mismo nombre con otro id)."""
    pisos = tb.pisos()
    assert len(pisos) == 60
    assert len({p['nombre'] for p in pisos}) == 60 and len({p['npc_type'] for p in pisos}) == 60
