"""Pet Defense: las ventanas (server/pet_defense_ui.py, server/lua/pet_defense.lua, tools/ventana_pet_defense.py), la
evolucion de las torres al mejorarlas y los tipos de torre (21/11/2026: "utiliza mas pet ... que no se seleccione al
iniciar, que tengamos posiciones para ello, se clickeen y se pueda seleccionar cual quiero poner ahi")."""
import copy
import pathlib
import re
import struct
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
import app  # noqa: E402
import canal_lua  # noqa: E402
import combate  # noqa: E402
import pet_defense as pd  # noqa: E402
import pet_defense_partida as pp  # noqa: E402
import pet_defense_ui as ui  # noqa: E402
import ventana_pet_defense as v  # noqa: E402

LUA = (RAIZ / 'server' / 'lua' / 'pet_defense.lua').read_text(encoding='utf-8')
CFG = copy.deepcopy(pd.config())


class Ses:
    def __init__(self, stage=41):
        self.personaje = NS(entity_id=500001, nombre='Tester', stage=stage, tile_x=9, tile_y=35)
        self.enviados = []
        self.monstruos = {}
        self.cerrada = False

    def enviar(self, *pk):
        self.enviados.extend(pk)

    enviar_inmediato = enviar


def _lua_de(pk):
    return [p[2:-1].decode('latin1') for p in pk if struct.unpack_from('<H', p)[0] == canal_lua.OPCODE]


def _cuerpo(a, b=0):
    return struct.pack('<BII', ui.CMD_PD, a, b)


@pytest.fixture
def partida(monkeypatch):
    """Una partida de verdad en el mapa de Pet Defense, con el jugador de mentira."""
    s = Ses(CFG['mapa']['stage'])
    s._pd_pendiente = True
    monkeypatch.setattr(pd, '_sesiones_del_mapa', lambda stage: [s])
    monkeypatch.setattr(pd, '_arrancar', lambda: None)
    monkeypatch.setattr(app, '_poner_generado', lambda ss, eid, npc_type, tile, zona: None)
    pd._TORRES.clear()
    pp._PARTIDAS.clear()
    pp.al_entrar(s)
    yield s, pp.partida(s)
    pp._PARTIDAS.clear()
    pd._TORRES.clear()


def test_hay_muchas_mascotas_con_sus_tres_fases():
    torres = CFG['torres']
    assert len(torres) >= 10
    import mascotas
    for clave, d in torres.items():
        assert len(d['sprites']) == 3, clave
        etapas = [mascotas.ficha_de_sprite(sp).get('etapa') for sp in d['sprites']]
        assert etapas[0] == '初階' and etapas[2] == '高階', (clave, etapas)


def test_abrir_manda_el_script_y_la_galeria():
    ses = Ses()
    assert ui.procesar(ses, _cuerpo(1))
    textos = _lua_de(ses.enviados)
    assert any('function PDAbrir' in t for t in textos)
    llamada = [t for t in textos if t.startswith('PDAbrir(')][0]
    assert all(d['nombre'] in llamada for d in CFG['torres'].values())
    ses.enviados.clear()
    ui.procesar(ses, _cuerpo(1))                    # el script va una vez por conexion
    assert not any('function PDAbrir' in t for t in _lua_de(ses.enviados))


def test_otro_comando_no_es_suyo():
    assert not ui.procesar(Ses(), struct.pack('<BII', 169, 1, 0))


def test_empezar_no_elige_nada(monkeypatch):
    ses = Ses()
    llamadas = []
    monkeypatch.setattr(pp, 'empezar', lambda s, addr='?': llamadas.append(s) or 'ok')
    ui.procesar(ses, _cuerpo(3, 0))
    assert llamadas == [ses] and getattr(ses, '_pd_tipo', None) is None
    assert any(t.startswith('PDCerrar(') for t in _lua_de(ses.enviados))


def test_elegir_la_mascota_de_la_piedra(partida):
    ses, pa = partida
    eid = next(e for e, i in pa.npc_espacio.items() if i == 2)
    pp.pulsar(ses, eid)
    assert ses._pd_espacio == 2
    claves = list(CFG['torres'])
    ses.enviados.clear()
    ui.procesar(ses, _cuerpo(7, claves.index('arquero')))
    assert pa.torres[2].tipo == 'arquero'
    assert pa.essence == CFG['partida']['essence_inicial'] - CFG['torres']['arquero']['coste']
    assert any(t == 'PDElegirCerrar()' for t in _lua_de(ses.enviados))
    # sin Essence: aviso en la ventana y nada construido
    pa.essence = 0
    otra = next(e for e, i in pa.npc_espacio.items() if i == 3)
    pp.pulsar(ses, otra)
    ses.enviados.clear()
    ui.procesar(ses, _cuerpo(7, claves.index('dragon')))
    assert 3 not in pa.torres and any(t.startswith('PDElegirAviso(') for t in _lua_de(ses.enviados))


def test_la_ficha_mejora_y_vende(partida):
    ses, pa = partida
    pa.essence = 10_000
    pp.construir(pa, 0, 'fuego')
    eid = next(e for e, i in pa.npc_espacio.items() if i == 0)
    ses.enviados.clear()
    pp.pulsar(ses, eid)
    ficha = [t for t in _lua_de(ses.enviados) if t.startswith('PDTorre(')][0]
    assert ficha.startswith('PDTorre(%d,1,' % (list(CFG['torres']).index('fuego') + 1))
    ui.procesar(ses, _cuerpo(8))
    assert pa.torres[0].nivel == 2
    assert any(t.startswith('PDTorre(') and ',2,' in t for t in _lua_de(ses.enviados))
    ui.procesar(ses, _cuerpo(9))
    assert 0 not in pa.torres


def test_la_barra_solo_se_manda_si_cambia():
    ses = Ses()
    pa = NS(ses=ses, vida=20, vida_max=20, oleada=1, total_oleadas=10, essence=150, cola=[], enemigos={},
            proxima_oleada=1010.0, resultado=None)
    assert ui.refrescar(pa, 1000.0)
    assert any(t.startswith('PDHud(') and 'Next wave in 10 s' in t for t in _lua_de(ses.enviados))
    assert not ui.refrescar(pa, 1000.2)
    pa.essence = 90
    assert ui.refrescar(pa, 1000.3)


def test_el_final_ensena_victoria_o_quita_la_barra():
    ses = Ses()
    pa = NS(ses=ses, vida=12, vida_max=20, total_oleadas=10, resultado='victoria',
            resultado_datos={'puntos': 21300, 'oleadas': 10, 'segundos': 754, 'muertos': 140})
    ui.fin(pa)
    fin = [t for t in _lua_de(ses.enviados) if t.startswith('PDFin(')][0]
    assert fin.startswith('PDFin(true') and '21,300' in fin and '12:34' in fin
    ses.enviados.clear()
    pa.resultado = 'abandono'
    ui.fin(pa)
    assert _lua_de(ses.enviados) == ['PDHudCerrar()']


def test_saltar_la_pausa():
    pa = NS(resultado=None, cola=[], enemigos={}, proxima_oleada=1010.0)
    assert pp.saltar_pausa(pa, 1000.0) and pa.proxima_oleada == 1000.0
    pa.enemigos = {1: object()}
    pa.proxima_oleada = 1010.0
    assert not pp.saltar_pausa(pa, 1000.0)


def test_la_torre_evoluciona_al_mejorar(monkeypatch):
    ses = Ses(45)
    monkeypatch.setattr(pd, '_sesiones_del_mapa', lambda stage: [ses])
    monkeypatch.setattr(pd, '_arrancar', lambda: None)
    pd._TORRES.clear()
    datos = dict(CFG['torres']['fuego'])
    t = pd.crear(ses, 'fuego', datos, (10, 10))
    assert t.sprite() == datos['sprites'][0] and t.ficha['sprite'] == datos['sprites'][0]
    vieja = t.entidad
    ses.enviados.clear()
    pd.evolucionar(t, 2)
    assert t.ficha['sprite'] == datos['sprites'][1] and t.nivel == 2
    ops = [struct.unpack_from('<H', p)[0] for p in ses.enviados]
    assert ops[:2] == [0x0007, 0x0050]               # se quita la vieja y sale la evolucion con una entidad NUEVA
    assert struct.unpack_from('<I', ses.enviados[0], 2)[0] == vieja
    assert struct.unpack_from('<I', ses.enviados[1], 2 + 71)[0] == t.entidad != vieja
    assert t.entidad in pd._TORRES and vieja not in pd._TORRES
    pd._TORRES.clear()


def test_jefe_al_final_de_cada_oleada_y_aspectos_variados(partida):
    ses, pa = partida
    import random
    random.seed(3)
    jefes = CFG['enemigos']['jefe']['npc_types']
    for n in (1, 2):
        pp._empezar_oleada(pa, 1000.0)
        assert pa.cola[-1][0] == 'jefe' and sum(1 for t, _ in pa.cola if t == 'jefe') == 1
        assert pp.aspecto(pa, 'jefe', CFG['enemigos']['jefe']) == jefes[n - 1]
        pa.cola = []
    vistos = {pp.aspecto(pa, 'normal', CFG['enemigos']['normal']) for _ in range(40)}
    assert len(vistos) > 5 and vistos <= set(CFG['enemigos']['normal']['npc_types'])


def test_la_escarcha_ralentiza():
    import time
    t = NS(ataque=120, magico=True, ralentiza=2.5, area=0, entidad=1, ficha={'nombre': 'Water Elf'})
    m = combate.Monstruo(9001, 6, 'Fire Goblin', (5, 5), 0, stage=45)
    m.hp_max = m.hp = 10_000
    pd.disparar(t, m)
    assert m.lento_hasta > time.time() + 2


def test_las_espadas_pegan_a_tres(monkeypatch):
    ses = Ses(45)
    bichos = {}
    for k in range(5):
        m = combate.Monstruo(9100 + k, 6, 'Fire Goblin', (12 + k, 10), 0, stage=45)
        m.hp_max = m.hp = 10_000
        bichos[m.entity_id] = m
    ses.monstruos = bichos
    monkeypatch.setattr(pd, '_sesiones_del_mapa', lambda stage: [ses])
    monkeypatch.setattr(pd, '_arrancar', lambda: None)
    monkeypatch.setattr(app, '_pet_puede_atacar', lambda s, m: True)
    pd._TORRES.clear()
    pd.crear(ses, 'espada', dict(CFG['torres']['espada']), (10, 10))
    pd.tick(ahora=5000.0)
    tocados = sorted(m.entity_id for m in bichos.values() if m.hp < 10_000)
    assert tocados == [9100, 9101, 9102]                      # los tres mas cercanos
    pd._TORRES.clear()


def test_las_ventanas_y_el_lua_casan():
    xml = v.bloque()
    funciones = set(re.findall(r'<OnCommand>(\w+)</OnCommand>', xml))
    assert funciones and all(re.search(r'function %s\(' % f, LUA) for f in funciones), funciones
    for wid in (v.V_MENU, v.V_ELEGIR, v.V_TORRE, v.V_HUD, v.V_FIN):
        assert 'id="%d"' % wid in xml and str(wid) in LUA
    for nombre in ('M_SUB', 'M_ARTE', 'M_NOMBRE', 'M_COSTE', 'E_TITULO', 'E_OPCION', 'E_COSTE', 'T_RETRATO',
                   'T_MEJORAR', 'H_CRISTAL', 'H_SIGUIENTE', 'F_LINEA', 'I_RETRATO', 'I_VICTORIA', 'I_DERROTA'):
        assert str(getattr(v, nombre)) in LUA, nombre
    for w, h in ((v.MW, v.MH), (v.EW, v.EH), (v.TW, v.TH), (v.HW, v.HH), (v.FW, v.FH)):
        assert str(w + 2 * v.MARCO_X) in LUA and str(h + v.MARCO_Y + v.MARCO_ABAJO) in LUA


def test_los_ids_no_chocan_con_los_del_cliente():
    xml = v.bloque()
    nuevos = set(int(x) for x in re.findall(r'\bid="(\d+)"', xml))
    resto = ''
    for f in (RAIZ / 'parches' / 'extras' / 'setting' / 'eng').glob('wnd*.xml'):
        resto += re.sub(r'<!-- %s -->.*?<!-- /%s -->' % (v.MARCA, v.MARCA), '',
                        f.read_text(encoding='utf-8-sig', errors='ignore'), flags=re.S)
    viejos = set(int(x) for x in re.findall(r'\bid\s*=\s*"(\d+)"', resto))
    assert not (nuevos & viejos), sorted(nuevos & viejos)
    assert max(i for i in nuevos if i < 59700) < 59399 and max(i for i in nuevos if i >= 59700) < 59841


def test_el_boton_de_la_barra_es_idempotente():
    texto = '<root>\n\t\t<child>59004</child>\n</root>\n'
    una = v.wnd01(texto)
    assert v.wnd01(una) == una and una.count('<child>59005</child>') == 1 and 'OnCommandPetDefense' in una
    assert 'OnCommandPetDefense' in ui.SALUDO_LUA and str(ui.CMD_PD) in ui.SALUDO_LUA


def _torre_con_bichos(monkeypatch, clave, posiciones, stage=917):
    ses = Ses(stage)
    bichos = {}
    for k, (x, y) in enumerate(posiciones):
        m = combate.Monstruo(9200 + k, 6, 'Fire Goblin', (x, y), 0, stage=stage)
        m.hp_max = m.hp = 100_000
        bichos[m.entity_id] = m
    ses.monstruos = bichos
    monkeypatch.setattr(pd, '_sesiones_del_mapa', lambda st: [ses])
    monkeypatch.setattr(pd, '_arrancar', lambda: None)
    monkeypatch.setattr(app, '_pet_puede_atacar', lambda s, m: True)
    pd._TORRES.clear()
    return ses, bichos


def test_la_mascota_usa_los_poderes_de_su_especie(monkeypatch):
    """"La mascota usa sus poderes" (21/11/2026): los de ataque de su especie y fase, con su efecto y recarga."""
    import random
    mp = CFG['mapa']
    casa = pp.espacios(917, pp.camino(917, mp['portal'], mp['cristal']), mp['separacion_espacios'], mp['distancia_espacio'])[0]
    ses, bichos = _torre_con_bichos(monkeypatch, 'oso', [(casa[0] + 1, casa[1])])
    t = pd.crear(ses, 'oso', dict(CFG['torres']['oso']), casa, nivel=3)
    assert t.skills and all(combate.datos_magia(s).get('es_ataque') or combate.datos_magia(s).get('es_debuff')
                            for s in t.skills)
    m = next(iter(bichos.values()))
    lanzado = pd.poder(t, m, 1000.0, rng=random.Random(1))
    while lanzado is None:
        lanzado = pd.poder(t, m, 1000.0, rng=random.Random())
    ya, luego, retraso, tocados = lanzado
    sk = next(s for s in t.skills if t.cd_skills.get(s, 0) > 1000.0)        # el lanzado queda en recarga
    assert m.hp < 100_000 and retraso > 0 and m in tocados
    assert struct.unpack_from('<H', ya[1])[0] == struct.unpack_from('<H', luego[0])[0] or ya and luego
    pd._TORRES.clear()


def test_la_mascota_se_mueve_cerca_de_su_piedra_y_vuelve(monkeypatch):
    """"La mascota se mueve cierto rango de su torre" (21/11/2026)."""
    mp = CFG['mapa']
    casa = pp.espacios(917, pp.camino(917, mp['portal'], mp['cristal']), mp['separacion_espacios'], mp['distancia_espacio'])[3]
    radio = CFG['radio_movimiento']
    alcance = CFG['torres']['lobo']['alcance']
    ses, bichos = _torre_con_bichos(monkeypatch, 'lobo', [])
    t = pd.crear(ses, 'lobo', dict(CFG['torres']['lobo']), casa)
    # un enemigo fuera de su alcance pero dentro de alcance + radio: se acerca, sin pasarse de radio
    import transitable
    cerca = next((casa[0] + dx, casa[1] + dy) for dx in range(-8, 9) for dy in range(-8, 9)
                 if max(abs(dx), abs(dy)) == alcance + 2 and transitable.se_pisa(917, casa[0] + dx, casa[1] + dy))
    m = combate.Monstruo(9300, 6, 'Fire Goblin', cerca, 0, stage=917)
    m.hp_max = m.hp = 100_000
    ses.monstruos = {m.entity_id: m}
    t_ahora = 2000.0
    for _ in range(40):
        pd.tick(ahora=t_ahora)
        t_ahora += 0.5
        assert max(abs(t.x - casa[0]), abs(t.y - casa[1])) <= radio
    assert (t.x, t.y) != casa and m.hp < 100_000                # se acerco y le pego
    # sin enemigos, vuelve a su piedra
    ses.monstruos = {}
    for _ in range(40):
        pd.tick(ahora=t_ahora)
        t_ahora += 0.5
    assert (t.x, t.y) == casa
    pd._TORRES.clear()


def test_el_dano_es_por_nivel_y_por_coste():
    """"Que el dano sea 500, 700, 1200" y "relativo al costo de cada pet, el que cuesta mas pega mas" (21/11/2026)."""
    torres = CFG['torres']
    barata = min(torres.values(), key=lambda d: d['coste'])
    assert [pd.dano_de(barata, n) for n in (1, 2, 3)] == CFG['dano_por_nivel'] == [500, 700, 1200]
    por_coste = sorted(torres.values(), key=lambda d: d['coste'])
    for n in (1, 2, 3):
        danos = [pd.dano_de(d, n) for d in por_coste]
        assert danos == sorted(danos) and danos[-1] > danos[0]
    m = combate.Monstruo(9400, 6, 'Fire Goblin', (5, 5), 0, stage=917)
    m.hp_max = m.hp = 10_000
    m.defensa = 5000                                            # sin defensa: quita lo justo
    t = NS(dano_fijo=pd.dano_de(barata, 3), ataque=1, magico=False, ralentiza=0, area=0, entidad=1, ficha={'nombre': 'Wolf'})
    pd.disparar(t, m)
    assert m.hp == 10_000 - 1200
