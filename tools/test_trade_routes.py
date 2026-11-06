"""Trade Routes, fase 1 (05/11/2026): jobs con espera de 7 dias y PD, encargo comprado con oro, entrega en la ciudad de
destino con ganancia al azar, premio repartido entre los Hunters, un vale para cada uno, IP repetida en el grupo,
50% mas lento con carga y sin teletransportes."""
import pathlib
import random
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import cliente_local  # noqa: E402
import equipos  # noqa: E402
import trade_routes as tr  # noqa: E402

_REFRESCAR_REAL = tr.refrescar_marcas

HOMBRE, MUJER = [1, 0, 0, 0, 0], [0, 0, 0, 0, 0]


def _ses(nombre, cid, ip, stage=3, oro=10_000_000, montado=True, apariencia=HOMBRE):
    p = NS(nombre=nombre, char_id=cid, entity_id=cid, stage=stage, oro=oro, logros_cont={}, apariencia=apariencia)
    inv = {10: 3001} if montado else {}
    avisos = []
    return NS(personaje=p, addr=(ip, 5000 + cid), oro=oro, inventario=inv, cantidades={}, usuario=None,
              avisos=avisos, enviar=lambda *pk: None)


@pytest.fixture(autouse=True)
def entorno(monkeypatch, tmp_path):
    tr._ENCARGOS.clear()
    monkeypatch.setattr(tr, '_ARCHIVO', tmp_path / 'trade_routes.json')     # nunca el data/ de verdad
    grupos = {}

    def dar(ses, item_id, n=1):
        libre = next(r for r in range(20, 120) if r not in ses.inventario)
        ses.inventario[libre] = int(item_id)
        return 'dado %dx x (%d) en la casilla %d' % (n, item_id, libre)
    monkeypatch.setattr(app, '_gm_dar_item', dar)
    monkeypatch.setattr(app, '_refrescar', lambda *a, **k: [])
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *a, **k: None)
    monkeypatch.setattr(tr, 'aviso', lambda s, t: s.avisos.append(t))
    monkeypatch.setattr(equipos, 'grupo_de', lambda s: grupos.get(id(s), []))
    return grupos


def _grupo(grupos, *miembros):
    for m in miembros:
        grupos[id(m)] = list(miembros)


def test_job_y_espera_de_7_dias():
    s = _ses('Baco', 1, '1.1.1.1')
    assert tr.poner_job(s, tr.TRADER, ahora=1000)[0]
    ok, msg = tr.poner_job(s, tr.THIEF, ahora=1000 + 86400)
    assert not ok and msg.startswith('You can change your job again in 6 days')
    assert tr.poner_job(s, tr.THIEF, ahora=1000 + 7 * 86400)[0]
    assert tr.poner_job(s, tr.HUNTER, ahora=1000 + 7 * 86400, forzar=True)[0]     # /job del GM


def test_pd_por_job_y_sexo():
    s = _ses('Baco', 1, '1.1.1.1')
    assert tr.pd_de(s) == {}
    tr.poner_job(s, tr.THIEF, ahora=1)
    assert tr.pd_de(s)[168] == 70525                       # Holy Thief's Suit (M)
    s.personaje.apariencia = MUJER
    assert tr.pd_de(s)[168] == 70521                       # Holy Thief's Dress (F)
    assert tr.fashion_bloqueada(s, 168) and not tr.fashion_bloqueada(s, 30)


def _trader(**kw):
    s = _ses('Baco', 1, '1.1.1.1', **kw)
    tr.poner_job(s, tr.TRADER, ahora=1)
    return s


def test_comprar_carga_cobra_y_da_el_objeto():
    s = _trader()
    ok, msg = tr.aceptar(s, tr.SILK, ahora=100, rng=random.Random(1))
    assert ok and msg.startswith('Deliver the Silk Cargo to ') and 'within 25 minutes' in msg
    assert s.oro == 8_000_000 and tr.lleva_carga(s)
    assert tr.encargo_de(s)['destino'] != 3
    assert not tr.aceptar(s, tr.GRAIN, ahora=100)[0]        # ya tiene uno


@pytest.mark.parametrize('cambio, texto', [
    (dict(montado=False), 'You must be riding a mount'),
    (dict(oro=100), 'You need 5,000,000 gold'),
    (dict(stage=16), 'taken in the cities'),
])
def test_requisitos_del_encargo(cambio, texto):
    s = _trader(**cambio)
    ok, msg = tr.aceptar(s, tr.GEM, ahora=100)
    assert not ok and texto in msg and not tr.lleva_carga(s)


def test_misma_ip_en_el_grupo(entorno):
    s, h = _trader(), _ses('Pipe', 2, '1.1.1.1')
    tr.poner_job(h, tr.HUNTER, ahora=1)
    _grupo(entorno, s, h)
    ok, msg = tr.aceptar(s, tr.GRAIN, ahora=100)
    assert not ok and 'same IP' in msg


def test_entrega_con_ganancia_hunters_y_vales(entorno):
    s = _trader()
    h1, h2, lejos = _ses('Pipe', 2, '2.2.2.2'), _ses('Lolo', 3, '3.3.3.3'), _ses('Lejos', 4, '4.4.4.4')
    for h in (h1, h2, lejos):
        tr.poner_job(h, tr.HUNTER, ahora=1)
    _grupo(entorno, s, h1, h2, lejos)
    tr.aceptar(s, tr.GEM, ahora=100, rng=random.Random(2))
    destino = tr.encargo_de(s)['destino']
    assert not tr.entregar(s, ahora=200)[0]                  # aun en la ciudad de salida
    for x in (s, h1, h2):
        x.personaje.stage = destino
    lejos.personaje.stage = 16                               # no esta en el mapa: no cobra
    ok, msgs = tr.entregar(s, ahora=300, rng=random.Random(3))
    assert ok and not tr.lleva_carga(s) and not tr.encargo_de(s)
    ganancia = s.oro - 10_000_000                           # 10M - 5M invertidos + 5M devueltos + ganancia
    assert 600_000 <= ganancia <= 1_000_000
    assert h1.oro == h2.oro == 10_000_000 + 1_000_000 and lejos.oro == 10_000_000
    for x in (s, h1, h2):
        assert any(it in tr.VALES for it in x.inventario.values())
    assert not any(it in tr.VALES for it in lejos.inventario.values())


def test_se_acaba_el_tiempo():
    s = _trader()
    tr.aceptar(s, tr.GRAIN, ahora=100)
    tr.tick(s, ahora=100 + 20 * 60 + 1)
    assert not tr.lleva_carga(s) and not tr.encargo_de(s)
    assert 'Time is up. The cargo was lost.' in s.avisos
    assert s.oro == 9_500_000                               # la inversion se pierde


def test_con_carga_mas_lento_y_sin_teletransporte(monkeypatch):
    s = _trader()
    assert tr.factor_velocidad(s) == 1.0 and tr.bloquea_teleport(s) is None
    tr.aceptar(s, tr.GRAIN, ahora=100)
    assert tr.factor_velocidad(s) == 0.5
    assert tr.bloquea_teleport(s) == 'You cannot teleport while carrying cargo.'
    import travel_items
    with pytest.raises(travel_items.Rechazo):
        travel_items._ready(NS(personaje=NS(stage=3), muerto=False, mapa_cargando=False, inventario=s.inventario))


def test_la_carga_no_se_transfiere():
    import inventario
    assert not inventario.puede_transferir(tr.CARGAS[tr.GEM]['item'])


def test_los_textos_van_al_msg_xml():
    x = '<root>\n    <字串 編號="5001" 文字="hola" />\n</root>'.encode('utf-8')
    out = cliente_local._parchear_msg_propios_xml_bytes(x).decode('utf-8')
    assert '<字串 編號="300001" 文字="Choose your job. You can change it again in 7 days." />' in out
    assert '編號="300022"' in out and '編號="5001"' in out


def test_saludo_segun_el_job():
    import struct
    s = _ses('Baco', 1, '1.1.1.1')
    linea = tr.saludo(s)
    assert struct.unpack_from('<I', linea, 2)[0] == tr.M_SALUDO
    tr.poner_job(s, tr.TRADER, ahora=1)
    linea = tr.saludo(s)
    assert struct.unpack_from('<I', linea, 2)[0] == tr.M_JOB_ACTUAL and b'Trader' in linea


# ------------------------------------------------------------------------------------------- fase 3: robo y Fence
@pytest.fixture
def mundo(monkeypatch, entorno):
    gente = []
    monkeypatch.setattr(app, '_tw_sesiones', lambda: list(gente))
    monkeypatch.setattr(tr, '_en_mapa', lambda stage: [s for s in gente if s.personaje.stage == int(stage)])
    monkeypatch.setattr(tr, 'refrescar_marcas', lambda ses: None)
    return gente


def _con_job(nombre, cid, ip, job, **kw):
    s = _ses(nombre, cid, ip, **kw)
    s.personaje.tile_x, s.personaje.tile_y = 50, 50
    tr.poner_job(s, job, ahora=1)
    return s


def _cargado(mundo, stage=16):
    t = _con_job('Baco', 1, '1.1.1.1', tr.TRADER)
    mundo.append(t)
    tr.aceptar(t, tr.SILK, ahora=100, rng=random.Random(1))
    t.personaje.stage = stage
    return t


def test_al_morir_la_carga_cae_y_el_thief_la_roba(mundo):
    t = _cargado(mundo)
    ladron = _con_job('Zorro', 9, '9.9.9.9', tr.THIEF, stage=16)
    mundo.append(ladron)
    assert tr.puede_atacar(ladron, t) and tr.puede_atacar(t, ladron)      # el que lleva la carga se defiende
    assert tr.soltar(t, ahora=200) and not tr.lleva_carga(t)
    e = tr._ENCARGOS[1]
    assert e['suelo']['stage'] == 16 and e['suelo']['hasta'] == 200 + 300
    assert tr.contacto(ladron) and tr.lleva_carga(ladron)
    assert e['robada_en'] == 16 and e['portador'] == 9
    assert 'The cargo was stolen!' in t.avisos
    assert tr.puede_atacar(t, ladron)                       # ahora el Trader puede pegarle al Thief


def test_el_thief_de_la_misma_ip_no_la_recoge(mundo):
    t = _cargado(mundo)
    ladron = _con_job('Zorro', 9, '1.1.1.1', tr.THIEF, stage=16)
    mundo.append(ladron)
    tr.soltar(t, ahora=200)
    assert not tr.contacto(ladron) and not tr.lleva_carga(ladron)


def test_el_thief_tiene_que_ir_montado(mundo):
    t = _cargado(mundo)
    ladron = _con_job('Zorro', 9, '9.9.9.9', tr.THIEF, stage=16, montado=False)
    mundo.append(ladron)
    tr.soltar(t, ahora=200)
    assert not tr.contacto(ladron) and 'You must be riding a mount to carry cargo.' in ladron.avisos


def test_fence_no_en_el_mapa_del_robo(mundo):
    t = _cargado(mundo, stage=8)                               # robada en Crashing Hillock (tiene Fence)
    ladron = _con_job('Zorro', 9, '9.9.9.9', tr.THIEF, stage=8)
    mundo.append(ladron)
    tr.soltar(t, ahora=200)
    tr.contacto(ladron)
    ok, msgs = tr.entregar_fence(ladron, ahora=300)
    assert not ok and 'another Fence' in msgs[0]
    ladron.personaje.stage = 30                                # Cryptic Moon Swamp
    ok, msgs = tr.entregar_fence(ladron, ahora=300, rng=random.Random(4))
    assert ok and ladron.oro == 10_000_000 + 500_000 and not tr.lleva_carga(ladron)
    assert any(it in tr.VALES for it in ladron.inventario.values())
    assert not tr._ENCARGOS


def test_el_hunter_la_recupera_y_la_entrega(mundo, entorno):
    t = _cargado(mundo)
    h = _con_job('Pipe', 2, '2.2.2.2', tr.HUNTER, stage=16)
    mundo.append(h)
    _grupo(entorno, t, h)
    tr.soltar(t, ahora=200)
    assert tr.contacto(h) and 'The cargo was recovered!' in h.avisos
    destino = tr._ENCARGOS[1]['destino']
    h.personaje.stage = destino
    t.personaje.stage = 16                                     # el Trader esta lejos: cobra igual
    ok, msgs = tr.entregar(h, ahora=300, rng=random.Random(5))
    assert ok and 2_300_000 <= t.oro - 8_000_000 <= 2_600_000
    assert h.oro == 10_000_000 + 1_000_000


def test_cinco_minutos_en_el_suelo_y_se_pierde(mundo):
    t = _cargado(mundo)
    tr.soltar(t, ahora=200)
    tr.tick(t, ahora=200 + 299)
    assert tr._ENCARGOS
    tr.tick(t, ahora=200 + 301)
    assert not tr._ENCARGOS


def test_pvp_solo_fuera_de_ciudades(mundo):
    t = _cargado(mundo, stage=3)
    ladron = _con_job('Zorro', 9, '9.9.9.9', tr.THIEF, stage=3)
    assert tr.motivo_pvp(ladron, t) is None                   # en la ciudad, el evento no deja
    t.personaje.stage = ladron.personaje.stage = 16
    assert tr.motivo_pvp(ladron, t) == ''
    otro = _con_job('Nadie', 7, '7.7.7.7', tr.TRADER, stage=16)
    assert tr.motivo_pvp(ladron, otro) is None                # un Trader sin carga no


def test_la_opcion_elegida_se_traduce_con_la_linea_guardada(monkeypatch):
    """"no me asigna el job": el cliente manda el numero de opcion (10, 11...) y el servidor lo traduce con la linea
    guardada en dlg_guion; el Guild Clerk no la guardaba."""
    import dialogos
    s = _ses('Baco', 1, '1.1.1.1')
    enviados = []
    s.enviar = lambda *pk: enviados.extend(pk)
    app._trade_routes_hablar(s, 143350)
    ops = dialogos.opciones_de(s.dlg_guion[0])
    assert ops[dialogos.indice_opcion(10)] == tr.OP_TRADER
    assert ops[dialogos.indice_opcion(11)] == tr.OP_HUNTER
    monkeypatch.setattr(app, '_logros_guardar', lambda ses: None)
    monkeypatch.setattr(app, '_trade_routes_vestir', lambda ses: None)
    app._trade_routes_opcion(s, 143350, ops[dialogos.indice_opcion(11)])
    assert tr.job_de(s.personaje) == tr.HUNTER and 'You are now a Hunter.' in s.avisos


def test_dejar_el_job_siempre_pero_sin_saltarse_la_espera():
    """"no me deja quitar el job" (06/11/2026)."""
    s = _ses('Baco', 1, '1.1.1.1')
    tr.poner_job(s, tr.TRADER, ahora=1000)
    ok, msg = tr.poner_job(s, 0, ahora=1000 + 3600)
    assert ok and msg == 'You quit your job.' and not tr.job_de(s.personaje)
    ok, msg = tr.poner_job(s, tr.HUNTER, ahora=1000 + 7200)           # dejar y volver a elegir no salta la espera
    assert not ok and 'change your job again' in msg
    assert tr.poner_job(s, tr.HUNTER, ahora=1000 + 7 * 86400)[0]


def test_reloj_avisos_y_clerk_con_el_tiempo():
    """"donde veo el tiempo que tengo para entregar??" (06/11/2026)."""
    import struct
    s = _trader()
    tr.aceptar(s, tr.SILK, ahora=1000, rng=random.Random(1))
    paquete = tr.icono(s, ahora=1000 + 60)
    assert struct.unpack_from('<IBBII', paquete, 2)[2:] == (4, tr.MAGIA_CARGA, 24 * 60 * 1000)
    tr.recordatorios(s, ahora=1000 + 15 * 60 + 1)              # quedan menos de 10 min
    tr.recordatorios(s, ahora=1000 + 15 * 60 + 5)              # no se repite
    assert [a for a in s.avisos if 'minutes left' in a] == [
        'Silk Cargo: 10 minutes left to reach %s.' % tr.CIUDADES[tr.encargo_de(s)['destino']]]
    linea = tr.saludo(s)
    assert struct.unpack_from('<I', linea, 2)[0] == tr.M_EN_CAMINO and b'Silk Cargo' in linea
    tr.expirar(s)
    assert struct.unpack_from('<IBBII', tr.icono(s), 2)[4] == 0  # sin carga, el icono se quita


def test_quien_la_suelta_no_la_recoge_en_2_minutos(mundo):
    """"me sali del juego y no se cayo": al volver a entrar la recogia en el primer paso (06/11/2026)."""
    t = _cargado(mundo)
    tr.soltar(t, ahora=200)
    assert not tr.contacto(t, ahora=200 + 60)
    assert tr.contacto(t, ahora=200 + 121) and tr.lleva_carga(t)


def test_magia_del_reloj_en_el_cliente():
    import cliente_local
    out = cliente_local._parchear_magias_propias_xml_bytes('<root>\n</root>'.encode('utf-8')).decode('utf-8')
    assert '編號="23410"' in out and 'Carrying Cargo' in out


def test_el_job_se_ve_al_volver_a_entrar(monkeypatch):
    """"si me salgo debo mantener el job activo" (06/11/2026): los logros_cont se cargan tarde de la ficha."""
    s = _ses('Baco', 1, '1.1.1.1')
    s.usuario = 'baco'
    s.personaje.logros_cont = {}

    def cargar(ses):
        ses.personaje._logros_cargado = True
        ses.personaje.logros_cont = {'trade_job': tr.TRADER, 'trade_job_desde': 1}
    monkeypatch.setattr(app, '_logros_datos', cargar)
    assert tr.pd_de(s)[168] == 26701                          # Romantic Gentleman Coat
    assert tr.job_de(s.personaje) == tr.TRADER


def test_la_pd_se_viste_al_entrar_al_mapa_sin_esperar(monkeypatch):
    """"hace como 1 salto de 2 seg y luego le sale el traje" (06/11/2026)."""
    s = _ses('Baco', 1, '1.1.1.1')
    tr.poner_job(s, tr.TRADER, ahora=1)
    vestido = []
    monkeypatch.setattr(app, '_trade_routes_vestir', lambda ses: vestido.append(ses))
    monkeypatch.setattr(tr, 'refrescar_marcas', lambda ses: None)
    tr.al_entrar_mapa(s)
    assert vestido == [s]


def test_volver_al_mismo_job_sin_esperar():
    """"me quite el job y no me deja volver a serlo; no me lo cambie, solo me quite el traje" (06/11/2026)."""
    s = _ses('Baco', 1, '1.1.1.1')
    tr.poner_job(s, tr.TRADER, ahora=1000)
    tr.poner_job(s, 0, ahora=2000)
    assert tr.poner_job(s, tr.TRADER, ahora=3000)[0]                  # el mismo: sin espera
    tr.poner_job(s, 0, ahora=4000)
    ok, msg = tr.poner_job(s, tr.THIEF, ahora=5000)                   # otro distinto: 7 dias
    assert not ok and 'change your job again' in msg


def test_aviso_a_todos_al_tomar_un_job(monkeypatch):
    s, otro = _ses('Baco', 1, '1.1.1.1'), _ses('Pipe', 2, '2.2.2.2')
    monkeypatch.setattr(app, '_tw_sesiones', lambda: [s, otro])
    tr.poner_job(s, tr.THIEF, ahora=1)
    tr.anunciar_job(s)
    assert 'Baco is now a Thief!' in otro.avisos and 'Baco is now a Thief!' in s.avisos


def test_clic_en_la_carga_la_recoge_o_dice_por_que(mundo):
    """"ahora lo veo pero no lo puedo recoger" (06/11/2026)."""
    t = _cargado(mundo)
    ladron = _con_job('Zorro', 9, '9.9.9.9', tr.THIEF, stage=16)
    mundo.append(ladron)
    tr.soltar(t, ahora=200)
    entidad = tr.ENTIDAD_SUELO + 1
    assert tr.pulsar(t, entidad, ahora=210) and not tr.lleva_carga(t)
    assert any('You dropped this cargo' in a for a in t.avisos)
    ladron.personaje.tile_x = 60                                # a 10 casillas
    assert tr.pulsar(ladron, entidad) and 'Get closer to pick up the cargo.' in ladron.avisos
    ladron.personaje.tile_x = 52
    assert tr.pulsar(ladron, entidad) and tr.lleva_carga(ladron)
    assert not tr.pulsar(ladron, 12345)                        # no es una carga


def test_los_encargos_sobreviven_a_un_reinicio():
    """Cada subida reinicia el servidor: en memoria se perdia la carga y lo invertido."""
    s = _trader()
    tr.aceptar(s, tr.GEM, ahora=1000, rng=random.Random(1))
    tr.guardar(ahora=1100)
    fin = tr._ENCARGOS[1]['fin']
    tr._ENCARGOS.clear()
    assert tr.cargar(ahora=1100 + 600) == 1                  # 10 minutos apagado
    e = tr._ENCARGOS[1]
    assert e['fin'] == fin + 600 and e['portador'] == 1
    tr.tick(s, ahora=1700)
    assert tr.lleva_carga(s)                                   # sigue llevandola


def test_el_thief_ve_al_portador_atacable_y_entra_en_modo_arena(mundo, monkeypatch):
    """"siguen sin poder targetearme" (06/11/2026): con la marca 42 sola el cliente no deja apuntar a un jugador."""
    import struct
    monkeypatch.setattr(tr, 'refrescar_marcas', _REFRESCAR_REAL)      # el de verdad, no el falso del fixture
    t = _cargado(mundo)
    ladron = _con_job('Zorro', 9, '9.9.9.9', tr.THIEF, stage=16)
    recibido = []
    ladron.enviar = lambda *pk: recibido.extend(pk)
    mundo.append(ladron)
    tr.refrescar_marcas(t)
    import presencia
    eid = presencia.entidad_de(t)
    assert struct.pack('<HIBBII', 0x001D, eid, 1, 36, 1, 0) in recibido             # el objetivo, en modo arena
    assert struct.pack('<HIBBII', 0x001D, ladron.personaje.entity_id, 1, 36, 1, 0) in recibido   # y el propio
    # la 42 con la cabecera del jugador LOCAL del receptor y el objetivo aparte (presencia.para_receptor)
    assert struct.pack('<HIBBII', 0x001D, ladron.personaje.entity_id, 1, 42, eid, 1) in recibido


def test_el_que_lleva_la_carga_puede_atacar_a_sus_enemigos(mundo, entorno):
    """"si soy trader o thief y llevo la mercancia deberia poder atacar a los enemigos" (06/11/2026)."""
    t = _cargado(mundo)
    h = _con_job('Pipe', 2, '2.2.2.2', tr.HUNTER, stage=16)
    ladron = _con_job('Zorro', 9, '9.9.9.9', tr.THIEF, stage=16)
    otro_trader = _con_job('Nadie', 7, '7.7.7.7', tr.TRADER, stage=16)
    mundo.extend([h, ladron, otro_trader])
    _grupo(entorno, t, h)
    assert tr.puede_atacar(t, ladron) and tr.puede_atacar(h, ladron)      # el portador y su escolta se defienden
    assert not tr.puede_atacar(t, otro_trader)                            # a otro Trader, no
    tr.soltar(t, ahora=200)
    tr.contacto(ladron)                                                   # el Thief la roba
    assert tr.puede_atacar(ladron, t) and tr.puede_atacar(ladron, otro_trader)   # y el Thief con carga se defiende


def test_con_la_carga_en_el_suelo_sigue_la_pelea(mundo, entorno):
    """"si me bajan la mercancia, es decir muero, deberiamos igual poder targetear a los enemigos" (06/11/2026)."""
    t = _cargado(mundo)
    h = _con_job('Pipe', 2, '2.2.2.2', tr.HUNTER, stage=16)
    ladron = _con_job('Zorro', 9, '9.9.9.9', tr.THIEF, stage=16)
    mundo.extend([h, ladron])
    _grupo(entorno, t, h)
    tr.soltar(t, ahora=200)                                   # muere el Trader: la carga al suelo
    assert tr.puede_atacar(ladron, h) and tr.puede_atacar(h, ladron)
    assert tr.puede_atacar(ladron, t) and tr.puede_atacar(t, ladron)
    h.personaje.stage = 30                                    # en otro mapa no hay disputa
    assert not tr.puede_atacar(ladron, h)


def test_al_volver_al_mapa_con_la_carga_en_el_suelo_se_refrescan_las_marcas(mundo, monkeypatch):
    """"la mercancia esta abajo, yo puedo atacarlo pero el no a mi" (06/11/2026): el que murio vuelve al mapa y el
    Thief tiene que recibir otra vez el modo arena; solo se refrescaba si alguien llevaba la carga encima."""
    t = _cargado(mundo)
    t.personaje.tile_x, t.personaje.tile_y = 50, 50
    tr.soltar(t, ahora=200)
    refrescos = []
    monkeypatch.setattr(tr, 'refrescar_marcas', lambda ses: refrescos.append(ses))
    monkeypatch.setattr(app, '_trade_routes_vestir', lambda ses: None)
    tr.al_entrar_mapa(t)
    assert refrescos == [t]
