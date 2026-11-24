"""Angel MOBA, fase 1 (23/11/2026): mapa 918, carriles, oleadas, torres, nucleos y quien pega a quien (server/moba.py)."""
import time
import pathlib
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import combate  # noqa: E402
import moba  # noqa: E402
import transitable  # noqa: E402

CFG = moba.config()


@pytest.fixture(autouse=True)
def rk_tmp(tmp_path, monkeypatch):
    """Las partidas del ranking, a una base de datos de usar y tirar (no a data/moba.db)."""
    import moba_ranking
    monkeypatch.setattr(moba_ranking, 'DB_PATH', tmp_path / 'moba.db')
    encolados = []
    monkeypatch.setattr(moba_ranking, '_encolar', lambda ronda, cid, plan: encolados.append((ronda, cid, plan)))
    moba_ranking._ULTIMO[:] = [0, 0.0]
    return encolados


class Ses:
    def __init__(self, eid=500001):
        self.personaje = NS(entity_id=eid, nombre='Tester', stage=CFG['mapa']['stage'], tile_x=44, tile_y=22, hp=1000,
                            char_id=1)
        self.monstruos = {}
        self.enviados = []
        self.cerrada = False

    def enviar(self, *pk):
        self.enviados.extend(pk)


@pytest.fixture
def partida():
    ses = Ses()
    pa = moba.Partida('t', 1000.0)
    pa.jugadores[ses] = 1
    moba._DE_SESION[ses] = pa
    moba._PARTIDAS['t'] = pa
    moba.montar(pa)
    yield ses, pa
    moba._PARTIDAS.clear()
    moba._DE_SESION.clear()


def test_el_mapa_y_los_tres_carriles():
    st = CFG['mapa']['stage']
    assert transitable.conocido(st)
    for carril in CFG['carriles']:
        for eq in (1, 2):
            r = moba.ruta(carril, eq)
            assert len(r) > 100 and all(transitable.se_pisa(st, *c) for c in r)
            base = tuple(CFG['equipos'][str(eq)]['nucleo'])
            enemiga = tuple(CFG['equipos'][str(3 - eq)]['nucleo'])
            assert r[0] == base and r[-1] == enemiga
    for eq in ('1', '2'):
        assert transitable.se_pisa(st, *CFG['equipos'][eq]['llegada'])


def test_montar_pone_nucleos_y_torres(partida):
    ses, pa = partida
    tipos = [(m.moba_tipo, m.moba_equipo) for m in pa.unidades.values()]
    assert tipos.count(('nucleo', 1)) == tipos.count(('nucleo', 2)) == 1
    assert tipos.count(('torre', 1)) == tipos.count(('torre', 2)) == 6
    assert all(e in ses.monstruos for e in pa.unidades)
    assert pa.montada


def test_el_reloj_saca_los_subditos(partida):
    """Por moba.tick (el reloj de verdad), no llamando a _oleadas a mano: "no salen los minions" (23/11/2026)."""
    ses, pa = partida
    moba.tick(pa.proxima_oleada + 0.1)
    assert any(m.moba_tipo == 'subdito' for m in pa.unidades.values())


def test_salen_oleadas_por_los_tres_carriles(partida):
    ses, pa = partida
    moba._oleadas(pa, pa.proxima_oleada + 30)
    subditos = [m for m in pa.unidades.values() if m.moba_tipo == 'subdito']
    assert len(subditos) == 2 * 3                                   # el primero de cada carril y equipo
    assert {(m.moba_equipo, m.moba_carril) for m in subditos} == {(e, c) for e in (1, 2) for c in CFG['carriles']}


def test_el_subdito_anda_por_su_carril(partida):
    ses, pa = partida
    m = moba._nueva_unidad(pa, 'subdito', 1, moba.ruta('bot', 1)[0], 'bot')
    t = 2000.0
    for _ in range(200):
        moba._tick_unidad(pa, m, t)
        t += 0.5
    assert m.moba_i > 20 and (m.tile_x, m.tile_y) == moba.ruta('bot', 1)[m.moba_i]


def test_subditos_enemigos_pelean_y_mueren(partida):
    ses, pa = partida
    a = moba._nueva_unidad(pa, 'subdito', 1, (199, 100), 'mid')
    b = moba._nueva_unidad(pa, 'subdito', 2, (200, 100), 'mid')
    b.hp = 1
    moba._tick_unidad(pa, a, 3000.0)
    assert b.entity_id not in pa.unidades and a.entity_id in pa.unidades


def test_la_torre_pega_al_subdito_enemigo(partida):
    ses, pa = partida
    torre = next(m for m in pa.unidades.values() if m.moba_tipo == 'torre' and m.moba_equipo == 1)
    s = moba._nueva_unidad(pa, 'subdito', 2, (int(torre.tile_x) + 2, int(torre.tile_y)), 'bot')
    hp = s.hp
    moba._tick_unidad(pa, torre, 4000.0)
    assert s.hp < hp


def test_cae_el_nucleo_y_gana_el_otro(partida):
    ses, pa = partida
    nucleo = next(m for m in pa.unidades.values() if m.moba_tipo == 'nucleo' and m.moba_equipo == 2)
    moba.muere(pa, nucleo, ses)
    assert pa.resultado == 1 and not pa.unidades and 't' not in moba._PARTIDAS


def test_no_se_pega_a_los_de_tu_equipo(partida):
    ses, pa = partida
    propia = next(m for m in pa.unidades.values() if m.moba_equipo == 1)
    ajena = next(m for m in pa.unidades.values() if m.moba_equipo == 2)
    import holy_battlefield
    assert not holy_battlefield.puede_atacar(ses, propia) and moba.puede_atacar(ses, ajena)
    otro = Ses(500002)
    assert not moba.puede_atacar(otro, ajena)                      # sin partida no se pega a unidades del MOBA
    normal = combate.Monstruo(9000, 6, 'Fire Goblin', (1, 1), 0, stage=41)
    assert moba.puede_atacar(otro, normal)


def test_comando_moba():
    import gm
    assert gm.parsear('/moba start 2 arco') == ('moba', 'start', '2', 'arco') and gm.parsear('/moba stop')[:2] == ('moba', 'stop')
    assert 'moba' in gm.PALABRAS_DELEGADAS and 'moba' in gm.RESULTADOS_DELEGADOS


# ---------------------------------------------------------------------------------------------- fase 2a: el heroe
import moba_heroe  # noqa: E402
import moba_lobby  # noqa: E402


class SesHeroe(Ses):
    def __init__(self, eid=500001, x=44, y=22):
        super().__init__(eid)
        self.personaje.tile_x, self.personaje.tile_y = x, y
        self.personaje.nivel, self.personaje.exp, self.personaje.mp = 200, 0, 500
        self.personaje.hp_max, self.personaje.mp_max = 20000, 9000
        self.personaje.habilidades, self.personaje.barra = [], []
        self.inventario = {}
        self.muerto = False


@pytest.fixture
def heroe(monkeypatch):
    import desplazamientos
    import presencia
    monkeypatch.setattr(desplazamientos, 'reubicar', lambda ses, tile, origen='': None)
    monkeypatch.setattr(presencia, 'entrar', lambda ses, st: None)
    ses = SesHeroe()
    pa = moba.Partida('h', 1000.0)
    pa.jugadores[ses] = 1
    moba._DE_SESION[ses] = pa
    moba._PARTIDAS['h'] = pa
    h = moba_heroe.entrar(ses, pa, 'espada')
    yield ses, pa, h
    moba._PARTIDAS.clear()
    moba._DE_SESION.clear()


def test_hay_nueve_clases_con_3_poderes_y_ultimate():
    clases = CFG['clases']
    assert len(clases) >= 9
    for k, c in clases.items():
        ps = c['poderes']
        assert len(ps) == 4 and sum(1 for p in ps if p.get('ultimate')) == 1, k
        assert all(combate.datos_magia(p['id']).get('efecto') for p in ps), k


def test_empieza_a_nivel_1_y_sube_hasta_18(heroe):
    ses, pa, h = heroe
    assert h.nivel == 1 and h.hp == h.hp_max == CFG['clases']['espada']['base']['hp']
    moba_heroe.dar_exp(pa, h, 10 ** 7)
    assert h.nivel == 18 == len(CFG['niveles'])
    assert ses.personaje.nivel == 200                     # el personaje de verdad no cambia


def test_la_ultimate_desde_nivel_6(heroe):
    ses, pa, h = heroe
    i_ult = next(i for i, p in enumerate(h.datos['poderes']) if p.get('ultimate'))
    ult = h.datos['poderes'][i_ult]
    enemigo = moba._nueva_unidad(pa, 'subdito', 2, (ses.personaje.tile_x + 1, ses.personaje.tile_y), 'mid')
    assert moba_heroe._no_puede(h, ult, enemigo, 2000.0).startswith(ult['nombre'])
    assert not moba_heroe.subir(h, i_ult)[0]                       # nivel 1: no
    moba_heroe.dar_exp(pa, h, CFG['niveles'][5])
    assert h.nivel >= 6 and moba_heroe.subir(h, i_ult)[0]
    assert moba_heroe._no_puede(h, ult, enemigo, 2000.0) is None


def test_un_punto_por_nivel_y_se_elige_que_poder(heroe):
    ses, pa, h = heroe
    assert h.puntos == 1 and h.aprendidos() == []
    assert any(b'MBPuntos' in p for p in ses.enviados)              # al entrar ya se le ofrece elegir
    ok, _ = moba_heroe.subir(h, 1)
    assert ok and h.aprendidos() == [h.datos['poderes'][1]['id']] and h.puntos == 0
    assert not moba_heroe.subir(h, 0)[0]                           # sin puntos
    moba_heroe.dar_exp(pa, h, CFG['niveles'][1])                   # nivel 2: un punto
    assert h.puntos == 1 and not moba_heroe.subir(h, 1)[0]         # rango 2 pide nivel 3
    assert moba_heroe.subir(h, 0)[0]
    moba_heroe.dar_exp(pa, h, CFG['niveles'][2])                   # nivel 3
    p1 = h.datos['poderes'][1]
    antes = moba_heroe.mult_de(h, p1)
    assert moba_heroe.subir(h, 1)[0] and moba_heroe.mult_de(h, p1) > antes


def test_no_se_lanza_un_poder_sin_desbloquear(heroe):
    ses, pa, h = heroe
    s = moba._nueva_unidad(pa, 'subdito', 2, (ses.personaje.tile_x + 1, ses.personaje.tile_y), 'mid')
    hp = s.hp
    moba_heroe.accion(ses, h.datos['poderes'][0]['id'], s.entity_id, ahora=3000.0)
    assert s.hp == hp


def test_los_poderes_se_conceden_al_entrar_con_su_nivel():
    """"Cuando aprendo 1 poder no sale el icono": el cliente los tiene desde el principio, con su nivel de verdad."""
    import struct
    import skills
    ses = SesHeroe()
    pa = moba.Partida('c', 1000.0)
    pa.jugadores[ses] = 1
    h = moba_heroe.entrar(ses, pa, 'espada')
    concedidos = {}
    for p in ses.enviados:
        if len(p) >= 7 and struct.unpack_from('<H', p)[0] == 0x001D and p[7:8] == b'\x09':
            for k in range(p[6]):
                kind, mid, mlv = struct.unpack_from('<BII', p, 7 + 9 * k)
                concedidos[mid] = mlv
    assert concedidos == {int(x['id']): skills.nivel_de_magia(int(x['id'])) for x in h.datos['poderes']}


def test_la_ventana_de_puntos_por_el_lobby(heroe):
    import struct
    ses, pa, h = heroe
    assert moba_lobby.procesar(ses, struct.pack('<BII', 175, 6, 2))
    assert h.rangos[h.datos['poderes'][2]['id']] == 1


def test_ataque_basico_y_poder_contra_un_subdito(heroe):
    ses, pa, h = heroe
    s = moba._nueva_unidad(pa, 'subdito', 2, (ses.personaje.tile_x + 1, ses.personaje.tile_y), 'mid')
    hp = s.hp
    assert moba_heroe.accion(ses, combate.ATAQUE_NORMAL, s.entity_id, ahora=3000.0)
    assert s.hp < hp
    poder = h.datos['poderes'][0]
    moba_heroe.subir(h, 0)
    mp = h.mp
    hp = s.hp
    moba_heroe.accion(ses, poder['id'], s.entity_id, ahora=3001.0)
    assert s.hp < hp and h.mp == mp - poder['mana'] and h.cds[poder['id']] > 3001.0
    hp = s.hp
    moba_heroe.accion(ses, poder['id'], s.entity_id, ahora=3001.5)  # en recarga: nada
    assert s.hp == hp


def test_no_pega_a_los_suyos_ni_usa_otros_poderes(heroe):
    ses, pa, h = heroe
    propio = moba._nueva_unidad(pa, 'subdito', 1, (ses.personaje.tile_x + 1, ses.personaje.tile_y), 'mid')
    hp = propio.hp
    moba_heroe.accion(ses, combate.ATAQUE_NORMAL, propio.entity_id, ahora=4000.0)
    assert propio.hp == hp
    assert moba_heroe.accion(ses, 9999, propio.entity_id, ahora=4000.0)    # otro poder: lo para el MOBA


def test_las_unidades_le_pegan_muere_y_reaparece(heroe):
    ses, pa, h = heroe
    torre = moba._nueva_unidad(pa, 'torre', 2, (ses.personaje.tile_x + 2, ses.personaje.tile_y))
    h.hp = 1
    moba._tick_unidad(pa, torre, 5000.0)
    assert h.muerto and ses.muerto
    moba_heroe.tick(pa, h.muerto_hasta + 0.1)
    assert not h.muerto and not ses.muerto and h.hp == h.hp_max


def test_doble_triple_cuadruple_y_pentakill(heroe):
    """"Sonidos de doble kill... pentakill": bajas seguidas (< 10 s), el anuncio y el efecto con su voz."""
    import struct
    ses, pa, h = heroe
    efectos = []
    for k in range(5):
        ses.enviados.clear()
        assert moba_heroe.racha(pa, h, 100.0 + k * 5) == k + 1
        efectos.append([p[2] | (p[3] & 0x0F) << 8 for p in ses.enviados       # el efecto va en 12 bits
                        if struct.unpack_from('<H', p)[0] == 0x0011 and not p[3] & 0xF0])
    assert [e[:1] for e in efectos] == [[], [53], [55], [72], [301]]
    assert moba_heroe.racha(pa, h, 200.0) == 1                      # paso mucho: vuelve a empezar
    import pathlib
    raiz = pathlib.Path(moba.__file__).resolve().parent.parent
    for _, ef in moba_heroe.RACHAS.values():
        assert (raiz / 'parches' / 'extras' / 'sound' / ('magic%03d.wav' % ef)).exists()


def test_la_estatua_grande_tambien_ataca(heroe):
    """"Las estatuas deben atacar": el nucleo enemigo pega al heroe y a los subditos."""
    ses, pa, h = heroe
    nucleo = moba._nueva_unidad(pa, 'nucleo', 2, (ses.personaje.tile_x + 3, ses.personaje.tile_y))
    antes = h.hp
    moba._tick_unidad(pa, nucleo, 5000.0)
    assert h.hp < antes
    sub = moba._nueva_unidad(pa, 'subdito', 1, (nucleo.tile_x + 1, nucleo.tile_y),
                              next(iter(moba.config()['carriles'])))
    vida = sub.hp
    moba._tick_unidad(pa, nucleo, 5010.0)
    assert sub.hp < vida


def test_la_cura_y_el_escudo():
    import copy
    assert any(p['tipo'] == 'cura' for p in CFG['clases']['vida']['poderes'])
    assert any(p['tipo'] == 'escudo' for p in CFG['clases']['hacha']['poderes'])


def test_un_jugador_sin_moba_va_por_el_combate_normal():
    assert moba_heroe.accion(SesHeroe(eid=777), combate.ATAQUE_NORMAL, 1) is False


def test_la_vida_maxima_es_la_del_heroe(heroe, monkeypatch):
    """"La vida maxima debe ir acorde": ni la ropa ni las habilidades del personaje, ni por app._stats_ses."""
    import struct
    import app as _app
    import inventario as inv
    ses, pa, h = heroe
    monkeypatch.setattr(inv, 'bonos_de_equipo', lambda *a, **k: dict.fromkeys(
        ('def', 'atk_r', 'atk_l', 'accuracy', 'agility', 'matk', 'mdef', 'hp', 'mp'), 5000))
    for paquete in (moba_heroe._paquete_stats(h), _app._stats_ses(ses)):
        assert struct.unpack_from('<IIII', paquete, 2) == (h.hp, h.hp_max, h.mp, h.mp_max)
        assert struct.unpack_from('<I', paquete, 2 + 24)[0] == h.atk


def test_al_salir_vuelve_lo_suyo(heroe):
    ses, pa, h = heroe
    ses.enviados.clear()
    moba_heroe.salir(ses, pa)
    import struct
    nivel = [p for p in ses.enviados if struct.unpack_from('<H', p)[0] == 0x001D and p[6] == 4]
    assert nivel and struct.unpack_from('<I', nivel[0], 8)[0] == 200 and ses not in pa.heroes


# ---------------------------------------------------------------------------------------------- fase 2b: 5 contra 5


@pytest.fixture
def lobby(monkeypatch):
    import app as _app
    import competiciones
    viajes = []
    monkeypatch.setattr(_app, '_viajar_por_portal', lambda ses, addr, d, motivo='': viajes.append((ses, d)))
    monkeypatch.setattr(competiciones, 'anunciar', lambda texto: None)
    moba_lobby._COLA.clear()
    yield viajes
    moba_lobby._COLA.clear()
    moba_lobby._ESTADO.update(empieza=None, abierta_desde=None)
    moba._PARTIDAS.clear()
    moba._DE_SESION.clear()


def test_repartir_en_equipos_de_cinco():
    grupos, fuera = moba_lobby.repartir(list(range(23)), 5, 2)
    assert [len(g) for g in grupos] == [10, 10, 3] and fuera == []
    grupos, fuera = moba_lobby.repartir(list(range(21)), 5, 2)
    assert [len(g) for g in grupos] == [10, 10] and fuera == [20]
    assert [e for _, e in grupos[0]].count(1) == [e for _, e in grupos[0]].count(2) == 5


def test_apuntarse_solo_con_la_inscripcion_abierta_y_clase(lobby):
    s = SesHeroe(eid=1101)
    assert not moba_lobby.apuntar(s, 'arco')[0]                    # cerrada
    moba_lobby.abrir_inscripcion(time_now() + 300)
    assert not moba_lobby.apuntar(s, None)[0]                      # sin clase
    assert moba_lobby.apuntar(s, 'arco')[0] and moba_lobby._COLA[s] == 'arco'
    assert moba_lobby.quitar(s) and s not in moba_lobby._COLA


def test_la_ventana_elige_clase_y_apunta(lobby):
    import struct
    s = SesHeroe(eid=1102)
    moba_lobby.abrir_inscripcion(time_now() + 300)
    assert moba_lobby.procesar(s, struct.pack('<BII', 175, 2, 3))     # la 4a clase
    assert s._mb_clase == list(CFG['clases'])[3]
    moba_lobby.procesar(s, struct.pack('<BII', 175, 3, 0))
    assert moba_lobby._COLA[s] == list(CFG['clases'])[3]
    assert not moba_lobby.procesar(s, struct.pack('<BII', 174, 1, 0))


def test_a_la_hora_se_arma_la_partida_compartida(lobby):
    gente = [SesHeroe(eid=1200 + i) for i in range(4)]
    moba_lobby.abrir_inscripcion(time_now() + 60)
    for i, s in enumerate(gente):
        assert moba_lobby.apuntar(s, list(CFG['clases'])[i])[0]
    moba_lobby.cron(time_now() + 61)
    pa = moba.partida_de(gente[0])
    assert pa is not None and all(moba.partida_de(s) is pa for s in gente)
    assert sorted(pa.jugadores.values()) == [1, 1, 2, 2] and len(lobby) == 4
    assert pa.clases[gente[2]] == list(CFG['clases'])[2]
    import presencia
    claves = {presencia.clave_de_mapa(s, pa.stage) for s in gente}
    assert len(claves) == 1                                        # se ven entre ellos
    assert presencia.clave_de_mapa(SesHeroe(eid=1300), pa.stage) not in claves


def test_heroe_contra_heroe(monkeypatch, lobby):
    import desplazamientos
    import presencia
    monkeypatch.setattr(desplazamientos, 'reubicar', lambda ses, tile, origen='': None)
    monkeypatch.setattr(presencia, 'entrar', lambda ses, st: None)
    a, b = SesHeroe(eid=1401, x=50, y=50), SesHeroe(eid=1402, x=51, y=50)
    pa = moba.empezar_partida([(a, 1, 'espada'), (b, 2, 'arco')], 1000.0)
    ha, hb_ = moba_heroe.entrar(a, pa, 'espada'), moba_heroe.entrar(b, pa, 'arco')
    pub_b = presencia.entidad_de(b)
    a.enviados.clear()
    b.enviados.clear()
    hp = hb_.hp
    assert moba_heroe.accion(a, combate.ATAQUE_NORMAL, pub_b, ahora=2000.0)     # pulsa el id publico del rival
    assert hb_.hp < hp
    import struct
    # cada uno ve la vida del golpeado con su id: b la suya tal cual, a la de b en porcentaje con el publico
    vida_b = [p for p in b.enviados if struct.unpack_from('<H', p)[0] == 0x0013 and struct.unpack_from('<I', p, 2)[0] == 1402]
    vida_en_a = [p for p in a.enviados if struct.unpack_from('<H', p)[0] == 0x0013 and struct.unpack_from('<I', p, 2)[0] == pub_b]
    assert vida_b and vida_en_a
    hb_.hp = 1
    moba_heroe.accion(a, combate.ATAQUE_NORMAL, pub_b, ahora=2010.0)
    assert hb_.muerto and pa.bajas[1] == 1 and ha.exp > 0


def test_las_marcas_de_enemigo(lobby):
    import presencia
    a, b, c = SesHeroe(eid=1501), SesHeroe(eid=1502), SesHeroe(eid=1503)
    pa = moba.empezar_partida([(a, 1, 'espada'), (b, 2, 'arco'), (c, 1, 'vida')], 1000.0)
    import struct
    hostil = {struct.unpack_from('<I', p, 8)[0]: p[-4] for p in moba.marcas(pa, a)
              if len(p) == 16 and p[6:8] == bytes((1, 42))}
    assert hostil == {presencia.entidad_de(b): 1, presencia.entidad_de(c): 0}


def time_now():
    import time
    return time.time()


# ---------------------------------------------------------------------------------------------- fase 3: jungla, jefe, marcador
def test_los_campamentos_y_el_jefe_estan_en_suelo_alcanzable():
    import pet_defense_partida as pp
    st = CFG['mapa']['stage']
    base = tuple(CFG['equipos']['1']['llegada'])
    for sitio in CFG['jungla']['campamentos'] + [CFG['jefe']['sitio']]:
        assert transitable.se_pisa(st, *sitio) and pp.camino(st, base, tuple(sitio))


def test_sale_la_jungla_y_no_pelea_con_los_carriles(partida):
    ses, pa = partida
    moba._jungla(pa, pa.inicio + 10 ** 6)
    neutrales = [m for m in pa.unidades.values() if m.moba_tipo in moba.NEUTRALES]
    assert len(neutrales) == len(CFG['jungla']['campamentos']) * 3 + 1
    sub = moba._nueva_unidad(pa, 'subdito', 1, tuple(CFG['jungla']['campamentos'][0]), 'mid')
    assert not any(u.moba_equipo == 0 for u in moba._enemigos(pa, sub)) and moba._enemigos(pa, neutrales[0]) == []


def test_la_jungla_se_defiende_y_da_exp(heroe):
    ses, pa, h = heroe
    x, y = ses.personaje.tile_x, ses.personaje.tile_y
    m = moba._nueva_unidad(pa, 'pequeno', 0, (x + 1, y), npc=CFG['jungla']['pequeno']['npc_types'][0])
    m.moba_campamento = 0
    hp = h.hp
    moba_heroe.accion(ses, combate.ATAQUE_NORMAL, m.entity_id, ahora=6000.0)
    assert m.moba_blanco is ses
    moba._tick_unidad(pa, m, 6000.5)
    assert h.hp < hp
    m.hp = 1
    moba_heroe.accion(ses, combate.ATAQUE_NORMAL, m.entity_id, ahora=6010.0)
    assert m.entity_id not in pa.unidades and h.exp >= CFG['exp']['pequeno']
    assert pa.jungla_proxima[0] is not None                       # el campamento reaparecera


def test_si_se_aleja_vuelve_a_vida_completa(heroe):
    ses, pa, h = heroe
    m = moba._nueva_unidad(pa, 'grande', 0, (ses.personaje.tile_x + 1, ses.personaje.tile_y),
                           npc=CFG['jungla']['grande']['npc_types'][0])
    moba.provocar(pa, m, h)
    m.hp = 10
    ses.personaje.tile_x += 40
    moba._tick_unidad(pa, m, 7000.0)
    assert m.moba_blanco is None and m.hp == m.hp_max


def test_el_jefe_da_buff_al_equipo(heroe):
    ses, pa, h = heroe
    atk, df = h.atk, h.defensa()
    j = moba._nueva_unidad(pa, 'jefe', 0, (ses.personaje.tile_x + 1, ses.personaje.tile_y), npc=CFG['jefe']['npc_types'][0])
    moba.muere(pa, j, ses)
    assert h.atk > atk and h.defensa() > df and pa.jefe_proximo is not None


def test_el_marcador_y_el_final(heroe):
    import moba_marcador
    ses, pa, h = heroe
    h.bajas, pa.bajas[1] = 2, 2
    arriba, abajo = moba_marcador.lineas_hud(pa, ses, pa.inicio + 75)
    assert '1:15' in arriba and 'K 2' in abajo and 'Lv 1' in abajo
    lineas = moba_marcador.lineas_fin(pa, ses)
    assert len(lineas) == 12 and lineas[0].startswith(CFG['equipos']['1']['nombre']) and lineas[6].startswith(CFG['equipos']['2']['nombre'])


# ---------------------------------------------------------------------------------------------- fase 4: premios y ranking
import moba_ranking  # noqa: E402


def test_los_retratos_de_clase_son_del_juego():
    assert all(1 <= int(c['icono']) <= 15 for c in CFG['clases'].values())
    assert CFG['clases']['sombra']['icono'] == 15 and CFG['clases']['vida']['icono'] == 1


def test_al_acabar_se_guarda_y_se_premia(rk_tmp, monkeypatch):
    import desplazamientos
    import presencia
    monkeypatch.setattr(desplazamientos, 'reubicar', lambda ses, tile, origen='': None)
    monkeypatch.setattr(presencia, 'entrar', lambda ses, st: None)
    a, b = SesHeroe(eid=1601), SesHeroe(eid=1602)
    a.usuario, b.usuario = 'ana', 'beto'
    a.personaje.char_id, b.personaje.char_id = 61, 62
    pa = moba.Partida('r', 1000.0)
    for s_, eq in ((a, 1), (b, 2)):
        pa.jugadores[s_] = eq
        moba._DE_SESION[s_] = pa
    moba._PARTIDAS['r'] = pa
    moba_heroe.entrar(a, pa, 'arco').bajas = 4
    moba_heroe.entrar(b, pa, 'vida')
    moba.terminar(pa, 1)
    assert [f[0] for f in moba_ranking.ranking(top=5)] == [61, 62]
    p = CFG['ranking']['puntos']
    assert moba_ranking.ranking()[0][3] == p['victoria'] + 4 * p['por_baja'] and moba_ranking.ranking()[1][3] == p['derrota']
    ags = {cid: plan['angel_gold'] for _r, cid, plan in rk_tmp}
    assert ags == {61: CFG['ranking']['premio_partida']['victoria'], 62: CFG['ranking']['premio_partida']['derrota']}


def test_rangos_y_cierre_de_temporada_una_vez(rk_tmp):
    r = CFG['ranking']['rangos']
    assert moba_ranking.rango(r['Gold'], 1) == 'Champion' and moba_ranking.rango(r['Silver'], 50) == 'Silver'
    assert moba_ranking.rango(r['Bronze'] - 1, 1) is None
    con = moba_ranking._con()
    con.execute("INSERT INTO partidas (partida, temporada, char_id, usuario, nombre, clase, equipo, gano, bajas, "
                "muertes, nivel, puntos, fecha) VALUES ('x', 1, 7, 'u', 'Top', 'arco', 1, 1, 9, 0, 18, ?, 0)",
                (r['Gold'],))
    con.commit()
    con.close()
    hechos = moba_ranking.cerrar(1)
    assert [(n, rg) for n, rg, _p in hechos] == [('Top', 'Champion')] and moba_ranking.cerrar(1) == []
    assert rk_tmp[-1][2]['angel_gold'] == CFG['ranking']['premios']['Champion']['angel_gold']


def test_la_ventana_del_ranking(rk_tmp):
    import struct
    s = SesHeroe(eid=1701)
    s.enviados.clear()
    assert moba_lobby.procesar(s, struct.pack('<BII', 175, 5, 0))
    assert any(b'MBRanking' in p for p in s.enviados)


# ---------------------------------------------------------------------------------------------- MP, recarga y tienda
import struct  # noqa: E402

import moba_tienda  # noqa: E402


def _recargas(ses):
    return [struct.unpack_from('<II', p, 8) for p in ses.enviados
            if struct.unpack_from('<H', p)[0] == 0x001D and len(p) == 16 and p[6:8] == bytes((1, 3))]


def test_el_area_sobre_uno_mismo_sale_gasta_mp_y_ensena_la_recarga(heroe):
    """Spliting Attack: el cliente la pide con el propio heroe de objetivo (680 sobre 1004, 23/11/2026)."""
    ses, pa, h = heroe
    i = next(k for k, p in enumerate(h.datos['poderes']) if p['tipo'] == 'area' and not p.get('ultimate'))
    poder = h.datos['poderes'][i]
    h.puntos = 1
    moba_heroe.subir(h, i)
    s = moba._nueva_unidad(pa, 'subdito', 2, (ses.personaje.tile_x + 1, ses.personaje.tile_y), 'mid')
    hp, mp = s.hp, h.mp
    ses.enviados.clear()
    moba_heroe.accion(ses, poder['id'], ses.personaje.entity_id, ahora=8000.0)
    assert s.hp < hp and h.mp == mp - poder['mana']
    assert (poder['id'], int(poder['cd'] * 1000)) in _recargas(ses)
    ses.enviados.clear()
    moba_heroe.accion(ses, poder['id'], ses.personaje.entity_id, ahora=8001.0)     # en recarga: se la recuerda
    assert _recargas(ses) and _recargas(ses)[0][0] == poder['id']


def test_al_salir_la_experiencia_de_64_bits(heroe):
    ses, pa, h = heroe
    ses.personaje.exp = 25478672000
    moba_heroe.salir(ses, pa)                                     # no revienta (struct.error)


def test_los_objetos_de_la_tienda_son_del_juego():
    import app
    for o in CFG['tienda']['objetos']:
        assert app._icono_item(o['id']) > 0, o['nombre']


def test_cada_clase_ve_sus_armas_y_las_comunes(heroe):
    """"Que la tienda tenga mas objetos para todas las clases": 3 armas de su clase y las de todos, 12 casillas."""
    import inventario as inv
    ses, pa, h = heroe
    for clave in CFG['clases']:
        h.clave = clave
        vistos = [CFG['tienda']['objetos'][i] for i in moba_tienda.indices_de(h)]
        armas = [o for o in vistos if o.get('clases')]
        assert len(vistos) == moba_tienda.CASILLAS and len(armas) == 3, clave
        assert all(clave in o['clases'] and inv.ranura_equipo_de(o['id']) == 3 for o in armas)
    h.clave = 'espada'
    ses.personaje.tile_x, ses.personaje.tile_y = CFG['equipos']['1']['nucleo']
    h.oro = 10 ** 6
    moba_tienda.procesar(ses, 2)                                  # la casilla 3: su arma mejor
    assert CFG['tienda']['objetos'][h.objetos[-1]]['nombre'] == 'Arclight Sword'


def test_lo_comprado_se_ve_puesto_y_al_salir_no(heroe):
    """"Compro 1 espada, se me ve esa espada": a la vista, sin tocar el inventario; al salir, lo suyo."""
    import struct
    import presencia
    ses, pa, h = heroe
    base = CFG['equipos']['1']['nucleo']
    ses.personaje.tile_x, ses.personaje.tile_y = base
    i = next(k for k, o in enumerate(CFG['tienda']['objetos']) if o['nombre'] == 'Arclight Sword')
    espada = CFG['tienda']['objetos'][i]['id']
    h.oro = 10 ** 6
    ses.enviados.clear()
    assert moba_tienda.comprar(pa, h, i)[0]
    assert ses.inventario == {}
    casillas = [p for p in ses.enviados if struct.unpack_from('<H', p)[0] == 0x001B]
    assert any(struct.pack('<I', espada) in p for p in casillas)    # su cliente la dibuja desde la casilla

    def puesto():
        return {struct.unpack_from('<II', p, 8) for p in app._apariencia(ses)}
    assert (3, espada) in puesto() and (169, 0) in puesto()            # su fashion vacia, como al equiparse
    assert struct.unpack_from('<I', presencia._spawn(ses), 2 + 96)[0] == espada
    ses.enviados.clear()
    moba_heroe.salir(ses, pa)
    assert (3, espada) not in puesto()
    assert any(struct.unpack_from('<H', p)[0] == 0x001B for p in ses.enviados)   # las casillas de verdad


def test_al_entrar_lleva_el_arma_de_su_clase_de_heroe(heroe):
    """"Lo aprendi y no esta": un mago jugando de Swordsman, sin espada en la casilla 3 el cliente no deja usar sus
    poderes ("It needs equipment Sword Blade"). Al entrar lleva el arma inicial de su clase; lo comprado la sustituye."""
    import struct
    ses, pa, h = heroe
    ses.inventario = {3: 19850}                                      # el baston de verdad del mago
    moba_heroe.salir(ses, pa)
    ses.enviados.clear()
    moba_heroe.entrar(ses, pa, 'espada')
    puesto = {struct.unpack_from('<II', p, 8) for p in app._apariencia(ses)}
    assert (3, moba_tienda.ARMA_INICIAL['espada']) in puesto
    assert any(struct.unpack_from('<H', p)[0] == 0x001B and struct.pack('<I', 10) in p for p in ses.enviados)
    h = pa.heroes[ses]
    ses.personaje.tile_x, ses.personaje.tile_y = CFG['equipos']['1']['nucleo']
    i = next(k for k, o in enumerate(CFG['tienda']['objetos']) if o['nombre'] == 'Steel Trace Blade')
    h.oro = 10 ** 6
    assert moba_tienda.comprar(pa, h, i)[0]
    assert (3, 18994) in {struct.unpack_from('<II', p, 8) for p in app._apariencia(ses)}


def test_comprar_en_la_base_sube_las_estadisticas(heroe):
    ses, pa, h = heroe
    base = CFG['equipos']['1']['nucleo']
    ses.personaje.tile_x, ses.personaje.tile_y = base[0] + 2, base[1]
    i = next(k for k, o in enumerate(CFG['tienda']['objetos']) if (o.get('stats') or {}).get('atk'))
    o = CFG['tienda']['objetos'][i]
    h.oro = o['precio'] - 1
    assert not moba_tienda.comprar(pa, h, i)[0]                   # sin oro
    h.oro = o['precio'] + 5
    atk = h.atk
    assert moba_tienda.comprar(pa, h, i)[0] and h.atk == atk + o['stats']['atk'] and h.oro == 5
    ses.personaje.tile_x += 40
    h.oro = 10 ** 6
    ses.ultimo_combate = time.time()
    assert moba_tienda.comprar(pa, h, i)[1].startswith('In combat')  # lejos y peleando no
    ses.ultimo_combate = time.time() - 10
    assert moba_tienda.comprar(pa, h, i)[0]                          # lejos y sin pelear, si ("no me deja comprar nada")


def test_las_botas_bajan_la_recarga_y_la_bolsa_tiene_tope(heroe):
    ses, pa, h = heroe
    base = CFG['equipos']['1']['nucleo']
    ses.personaje.tile_x, ses.personaje.tile_y = base
    h.oro = 10 ** 6
    botas = next(k for k, o in enumerate(CFG['tienda']['objetos']) if o.get('cdr'))
    for _ in range(CFG['tienda']['max_objetos']):
        assert moba_tienda.comprar(pa, h, botas)[0]
    assert moba_tienda.cdr(h) == CFG['tienda']['cdr_max']
    assert not moba_tienda.comprar(pa, h, botas)[0]


def test_oro_por_bajas_y_goteo(heroe):
    ses, pa, h = heroe
    oro = h.oro
    s = moba._nueva_unidad(pa, 'subdito', 2, (ses.personaje.tile_x + 1, ses.personaje.tile_y), 'mid')
    s.hp = 1
    moba_heroe.accion(ses, combate.ATAQUE_NORMAL, s.entity_id, ahora=9000.0)
    assert h.oro == oro + CFG['tienda']['oro']['subdito']
    moba_tienda.goteo(pa, 9000.0)
    moba_tienda.goteo(pa, 9000.0 + CFG['tienda']['oro']['cada'])
    assert h.oro == oro + CFG['tienda']['oro']['subdito'] + CFG['tienda']['oro']['goteo']


def test_el_boton_en_partida_abre_la_tienda(heroe):
    ses, pa, h = heroe
    ses.enviados.clear()
    moba_lobby.procesar(ses, struct.pack('<BII', 175, 1, 0))
    assert any(b'MBTienda' in p for p in ses.enviados)


def test_la_ventana_de_puntos_lleva_el_icono_del_poder(heroe):
    ses, pa, h = heroe
    import ventana_moba as vm
    ids = [moba_heroe.icono_poder(h.clave, p['id']) for p in h.datos['poderes']]
    k0 = list(CFG['clases']).index(h.clave) * 4
    assert ids == [vm.I_PODER0 + k0 + i for i in range(4)]


def test_al_aprender_se_vuelve_a_mandar_la_barra(heroe):
    ses, pa, h = heroe
    ses.enviados.clear()
    moba_heroe.subir(h, 0)                                        # sin bucle, _despues lo hace ya
    barras = [p for p in ses.enviados if struct.unpack_from('<H', p)[0] == 0x005B]
    assert len(barras) == 2


def test_la_inscripcion_es_un_npc_en_la_sign_up_office_y_la_tienda_un_boton_del_marcador():
    """"El npc del MOBA donde esta el de HBF, en el 66 30; quita el icono, que solo salga dentro del evento"."""
    import json
    import pathlib
    import sys
    import moba_lobby
    raiz = pathlib.Path(moba.__file__).resolve().parent.parent
    spawns = json.loads((raiz / 'server' / 'plantillas' / 'sign_up_office.json').read_text(encoding='utf-8'))['spawns']
    npc = next(s for s in spawns if s['nombre'] == moba_lobby.NPC_NOMBRE)
    assert npc['tile'] == [66, 30] and moba_lobby.NPC_STAGE == 114
    sys.path.insert(0, str(raiz / 'tools'))
    import ventana_moba as vm
    barra = '<root>\n    <child>59005</child>\n    <child>59006</child>\n</root>'
    assert '59006' not in vm.wnd01(barra) and vm.wnd01(vm.wnd01(barra)) == vm.wnd01(barra)
    assert 'OnMBHudTienda' in vm.bloque()
    lua = (raiz / 'server' / 'lua' / 'moba.lua').read_text(encoding='utf-8')
    assert 'function OnMBHudTienda' in lua
