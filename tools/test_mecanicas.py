"""Mecanicas nuevas (25/11/2026): Torre roguelike, contratos, torneo de mascotas y hardcore, con su ventana."""
import datetime as dt
import pathlib
import struct
import sys
from types import SimpleNamespace as NS

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app  # noqa: E402
import contratos  # noqa: E402
import hardcore  # noqa: E402
import mecanicas_ui  # noqa: E402
import sociales  # noqa: E402
import torneo_mascotas as tm  # noqa: E402
import torre_roguelike as tr  # noqa: E402


def _ses(cid, nombre, oro=100000, nivel=30):
    enviados = []
    return NS(personaje=NS(char_id=cid, nombre=nombre, nivel=nivel, stage=6, tile_x=1, tile_y=1, entity_id=cid,
                           buffs={}, hp=1000, mascotas={}), oro=oro, inventario={}, enviar=lambda *p: enviados.extend(p),
              enviados=enviados, usuario=None)


@pytest.fixture
def mundo(monkeypatch, tmp_path):
    gente, avisos, carteles = [], [], []
    monkeypatch.setattr(sociales, 'sesiones', lambda: list(gente))
    monkeypatch.setattr(sociales, 'aviso', lambda s, t: avisos.append((s.personaje.nombre, t)))
    monkeypatch.setattr(sociales, 'cartel', lambda t: carteles.append(t))

    def _oro(s, d):
        s.oro = max(0, s.oro + d)
    monkeypatch.setattr(sociales, 'cambiar_oro', _oro)
    monkeypatch.setattr(contratos, 'DB_PATH', tmp_path / 'contratos.db')
    monkeypatch.setattr(hardcore, 'DB_PATH', tmp_path / 'hardcore.db')
    tm.INSCRITOS.clear()
    return NS(gente=gente, avisos=avisos, carteles=carteles)


# ---------------------------------------------------------------- torre roguelike
def test_cada_subida_ofrece_bendiciones_distintas():
    a = tr.sorteo(1000.0, 3, 7)
    assert len(a) == 3 and len(set(a)) == 3 and a == tr.sorteo(1000.0, 3, 7)
    distintas = {tuple(tr.sorteo(1000.0 + k, 3, 7)) for k in range(20)}
    assert len(distintas) > 5


def test_elegir_y_perder_las_bendiciones(monkeypatch):
    monkeypatch.setattr(tr, '_refrescar', lambda s: None)
    s = _ses(7, 'Ana')
    ids = tr.ofrecer(s, 4, 1000.0)
    assert any(b'TBAbrir' in p for p in s.enviados)
    nombre = tr.elegir(s, 2, ahora=50.0)
    b = tr.bendiciones()[ids[1]]
    assert nombre == b['nombre'] and tr.tiene(s) == [b['id']]
    buff = s.personaje.buffs['torre_b_' + b['id']]
    assert all(buff[k] == v for k, v in b['efectos'].items())
    assert tr.elegir(s, 1) is None                             # una por piso
    assert struct.pack('<HIBBII', 0x001D, 7, 1, 4, b['magia'], tr.config()['duracion_s'] * 1000) in s.enviados
    assert tr.limpiar(s) == 1 and not tr.tiene(s)
    assert struct.pack('<HIBBII', 0x001D, 7, 1, 4, b['magia'], 0) in s.enviados


def test_la_vida_baja_con_las_bendiciones():
    import time
    import inventario as iv
    base = iv.vida_maxima(1000, [], buffs={})
    menos = iv.vida_maxima(1000, [], buffs={'torre_b_ojo': {'hp_pct': -20, 'fin': time.time() + 60}})
    assert menos == round(base * 0.8)


def test_los_iconos_en_el_parche():
    import cliente_local
    xml = (RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'magic.xml').read_text(encoding='utf-8')
    for b in tr.config()['bendiciones']:
        assert int(b['magia']) in cliente_local.MAGIAS_PROPIAS and '編號="%d"' % b['magia'] in xml
    assert '編號="%d"' % hardcore.cfg()['magia'] in xml


# ---------------------------------------------------------------- contratos
def test_contrato_de_objeto(mundo, monkeypatch):
    poster, otro = _ses(1, 'Ana', oro=100000), _ses(2, 'Bob', oro=0)
    mundo.gente += [poster, otro]
    item = contratos.buscar('item', 'pet feed')[0][0]
    assert contratos.publicar(poster, 'item', item, 5, 20000) == 'Contract posted.'
    assert poster.oro == 80000 and 'New contract' in mundo.carteles[-1]
    c = contratos.abiertos()[0]
    assert 'Need' not in contratos.entregar(otro, c['id']) and otro.oro == 0       # no los tiene
    dados = []
    monkeypatch.setattr(contratos, '_contar', lambda s, it: 5)
    monkeypatch.setattr(app, '_consumir_item_total', lambda s, it, n: [3])
    monkeypatch.setattr(app, '_refrescar', lambda s, t, **k: [])
    monkeypatch.setattr(app, '_gm_dar_item', lambda s, it, n=1: dados.append((s.personaje.nombre, it, n)))
    assert contratos.entregar(otro, c['id']).startswith('Delivered')
    assert otro.oro == 19000 and dados == [('Ana', item, 5)] and not contratos.abiertos()


def test_contrato_de_jefe_y_cancelar_y_pendientes(mundo):
    poster, cazador = _ses(1, 'Ana'), _ses(2, 'Bob', oro=0)
    mundo.gente += [poster, cazador]
    jefe = contratos.buscar('jefe', 'wind lord')[0][0]
    contratos.publicar(poster, 'jefe', jefe, 1, 10000)
    contratos.publicar(poster, 'jefe', jefe, 1, 5000)
    otro_id = contratos.abiertos()[0]['id']
    assert contratos.cancelar(cazador, otro_id).startswith('That contract is not yours')
    assert contratos.cancelar(poster, otro_id).startswith('Contract cancelled') and poster.oro == 90000
    mundo.gente.remove(poster)                                 # Ana se desconecta
    contratos.al_matar(cazador, NS(npc_type=jefe, dano_por={2: 100}))
    assert cazador.oro == 9500 and not contratos.abiertos()
    mundo.gente.append(poster)
    contratos.al_conectar(poster)
    assert any('defeated' in t for n, t in mundo.avisos if n == 'Ana')


def test_contrato_vence(mundo):
    poster = _ses(1, 'Ana')
    mundo.gente.append(poster)
    item = contratos.buscar('item', 'pet feed')[0][0]
    contratos.publicar(poster, "item", item, 1, 5000, ahora=1000.0)
    contratos.tick(ahora=1000.0 + 73 * 3600.0)
    assert poster.oro == 100000 and not contratos.abiertos()


# ---------------------------------------------------------------- torneo de mascotas
def _con_mascota(s, nivel, atk):
    s.personaje.mascotas = {'1': {'nombre': 'Pet' + s.personaje.nombre, 'nivel': nivel, 'hp': 500, 'hp_max': 500,
                                  'atk': atk, 'dfs': 50, 'matk': 10, 'mdef': 40, 'agilidad': 20, 'bonos': {}}}
    return s


def test_el_torneo(mundo):
    import random
    gente = [_con_mascota(_ses(i, 'J%d' % i), 10 + i, 40 + 10 * i) for i in range(1, 6)]
    mundo.gente += gente
    for i, s in enumerate(gente):
        assert 'signed up' in tm.inscribir(s, ('agresiva', 'defensiva', 'astuta')[i % 3])
    podio = tm.jugar(random.Random(4))
    assert len(podio) == 5 and len(set(podio)) == 5 and 'Champion' in mundo.carteles[-1]
    assert tm.ULTIMO['combates'] and not tm.INSCRITOS


def test_la_estrategia_cuenta():
    import random
    a = tm.luchador('A', {'nombre': 'a', 'nivel': 20}, {'hp': 800, 'atk': 100, 'dfs': 60, 'agilidad': 30}, 'agresiva')
    b = tm.luchador('B', {'nombre': 'b', 'nivel': 20}, {'hp': 800, 'atk': 100, 'dfs': 60, 'agilidad': 30}, 'astuta')
    gana_a = sum(tm.combate(a, b, random.Random(k))[0] is a for k in range(400))
    assert gana_a > 220                                         # agresiva gana a astuta mas a menudo


# ---------------------------------------------------------------- hardcore
def test_hardcore_pierde_la_temporada(mundo, monkeypatch):
    s = _ses(5, 'Duro', oro=1000, nivel=5)
    mundo.gente.append(s)
    assert hardcore.apuntar(s).startswith('Hardcore started') and hardcore.vivo(s)
    assert hardcore.mult_exp(s) == 1.3
    niveles = []
    import gm
    monkeypatch.setattr(gm, 'poner_nivel', lambda ses, n: niveles.append(n))
    s.personaje.nivel, s.oro = 25, 90000
    hardcore.al_subir(s)
    assert hardcore.ranking()[0] == ('Duro', 25, 'vivo')
    assert hardcore.al_morir(s) and niveles == [5] and s.oro == 1000 and not hardcore.vivo(s)
    assert 'fell at level 25' in mundo.carteles[-1]
    assert 'Try again next month' in hardcore.apuntar(s)
    alto = _ses(6, 'Alto', nivel=40)
    assert 'up to level' in hardcore.apuntar(alto)


def test_hardcore_50k_al_nivel_60_sin_morir(mundo, monkeypatch):
    import item_mall
    ag = []
    monkeypatch.setattr(item_mall, 'sumar_ag', lambda u, n: ag.append((u, n)))
    s = _ses(8, 'Sesenta', oro=0, nivel=5)
    s.usuario = 'cuenta8'
    hardcore.apuntar(s)
    s.personaje.nivel = 59
    assert hardcore.al_subir(s) == 0 and ag == []
    s.personaje.nivel = 60
    assert hardcore.al_subir(s) == 50000 and ag == [('cuenta8', 50000)] and s.oro == 0
    assert 'Angel Gold' in mundo.carteles[-1]
    s.personaje.nivel = 61
    assert hardcore.al_subir(s) == 0 and len(ag) == 1                # una sola vez
    caido = _ses(9, 'Caido', oro=0, nivel=5)
    hardcore.apuntar(caido)
    caido.personaje.nivel = 50
    import gm
    gm_antes = gm.poner_nivel
    gm.poner_nivel = lambda ses, n: None
    try:
        hardcore.al_morir(caido)
    finally:
        gm.poner_nivel = gm_antes
    caido.personaje.nivel = 60
    assert hardcore.al_subir(caido) == 0 and len(ag) == 1


def test_hardcore_solo_cuentan_las_muertes_pve():
    import inspect
    import app
    fuente = inspect.getsource(app._quitar_buffs_al_morir)
    assert "pve and __import__('hardcore').vivo(ses)" in fuente
    import pvp_liga
    import recovery_notice
    assert 'pve=True' not in inspect.getsource(pvp_liga) and 'pve=True' not in inspect.getsource(recovery_notice)


def test_hardcore_premia_a_los_supervivientes(mundo, monkeypatch):
    s = _ses(5, 'Duro', nivel=5)
    mundo.gente.append(s)
    noviembre = dt.datetime(2026, 11, 20)
    hardcore.apuntar(s, ahora=noviembre)
    dados = []
    monkeypatch.setattr(app, '_gm_dar_item', lambda ses, it, n=1: dados.append(it))
    hardcore._TEMPORADA.clear()
    hardcore.tick(dt.datetime(2026, 12, 1))
    assert dados == hardcore.cfg()['premios'] and 'Survivors: Duro' in mundo.carteles[-1]
    hardcore._TEMPORADA.clear()
    hardcore.tick(dt.datetime(2026, 12, 1))
    assert len(dados) == len(hardcore.cfg()['premios'])          # una sola vez


# ---------------------------------------------------------------- la ventana
def _cmd(a, b=0):
    return struct.pack('<BII', mecanicas_ui.CMD_CH, a, b)


def _trozos(texto):
    b = texto.encode('latin-1').ljust(16, b'\0')
    return [struct.unpack_from('<I', b, 4 * t)[0] for t in range(4)]


def test_publicar_y_entregar_desde_la_ventana(mundo, monkeypatch):
    a = _ses(1, 'Ana')
    mundo.gente.append(a)
    for t, v in enumerate(_trozos('pet feed')):
        mecanicas_ui.procesar(a, _cmd(23 + t, v))
    mecanicas_ui.procesar(a, _cmd(27))
    assert a._ch['resultados'] and a._ch['resultados'][0][1].lower().startswith('pet feed')
    mecanicas_ui.procesar(a, _cmd(31, 3))
    mecanicas_ui.procesar(a, _cmd(30, 9000))
    assert contratos.abiertos()[0]['cantidad'] == 3 and a.oro == 91000
    datos = mecanicas_ui.datos(a, 1)
    assert datos[1][0][1] == 'Cancel' and datos[5] == 1
    mecanicas_ui.procesar(a, _cmd(10))                             # Cancel en la fila 0
    assert a.oro == 100000 and not contratos.abiertos()
    mecanicas_ui.procesar(a, _cmd(22))                             # Boss: sin cantidad
    assert mecanicas_ui.datos(a, 1)[3] == 'Boss' and mecanicas_ui.datos(a, 1)[5] == 0


def test_torneo_y_hardcore_desde_la_ventana(mundo):
    s = _con_mascota(_ses(1, 'Ana', nivel=5), 12, 60)
    mundo.gente.append(s)
    assert mecanicas_ui.datos(s, 2)[2] == 1
    mecanicas_ui.procesar(s, _cmd(42))                             # Tricky
    assert tm.INSCRITOS[1]['estrategia'] == 'astuta' and mecanicas_ui.datos(s, 2)[3] == 1
    mecanicas_ui.procesar(s, _cmd(43))
    assert not tm.INSCRITOS
    assert mecanicas_ui.datos(s, 3)[2] == 1
    mecanicas_ui.procesar(s, _cmd(50))
    assert hardcore.vivo(s) and mecanicas_ui.datos(s, 3)[2] == 0


def test_ventanas_y_lua():
    sys.path.insert(0, str(RAIZ / 'tools'))
    import ventana_mecanicas as vm
    x = vm.bloque()
    assert 'id="57000"' in x and 'id="58960"' in x and x.count('WND_CLASS_EDIT') == 3
    w1 = (RAIZ / 'parches' / 'extras' / 'setting' / 'eng' / 'wnd01.xml').read_text(encoding='utf-8')
    assert '<child>59009</child>' in w1 and vm.wnd01(vm.wnd01(w1)) == vm.wnd01(w1)
    lua = (RAIZ / 'server' / 'lua' / 'mecanicas.lua').read_text(encoding='utf-8')
    for f in ('OnCommandChallenges', 'CHAbrir', 'CHDatos', 'OnCHPublicar', 'OnCHEstrategia', 'OnCHHardcore'):
        assert 'function %s(' % f in lua
    assert 'function OnTorreBendicion(' in (RAIZ / 'server' / 'lua' / 'roguelike.lua').read_text(encoding='utf-8')
    import calendario
    assert calendario.slots('torneo')
