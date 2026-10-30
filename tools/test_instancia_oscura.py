"""Instancia oscura Lv55-60 (mapa propio map900, stage 900): plantilla, portales y jefe con piedras de Holy."""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import app
import combate
import transitable

PLANT = RAIZ / 'server' / 'plantillas'
STAGE = 900
JEFE = 209
STAGES_PROHIBIDOS = (55, 66)       # stage.xml con 強制傳送: el cliente se cierra al entrar
PIEDRAS_HOLY = {8537, 8770, 24882, 28866, 40921}


def _spawns():
    return json.loads((PLANT / 'dark_cavern.json').read_text(encoding='utf-8'))['spawns']


def test_es_instancia_y_tiene_plantilla():
    assert app.es_instancia(STAGE)
    assert app.mapas_poblados()[STAGE] == 'dark_cavern.json'


def test_niveles_mezcla_de_normales_y_elites_y_un_jefe():
    sp = _spawns()
    normales = [s for s in sp if not s.get('elite') and not s.get('jefe')]
    elites = [s for s in sp if s.get('elite')]
    jefes = [s for s in sp if s.get('jefe')]
    assert len(normales) >= 40 and len(elites) >= 8 and len(jefes) == 1
    assert all(55 <= s['nivel'] <= 60 for s in normales + elites)
    assert jefes[0]['npc_type'] == JEFE
    assert all(0 < s['hp_mult'] <= (1.4 if s.get('sello') else 1) for s in normales + elites)
    assert len({s['entity_id'] for s in sp}) == len(sp)


def test_todos_pisan_suelo_y_se_llega_a_ellos_desde_la_entrada():
    portales = json.loads((PLANT / 'portales.json').read_text(encoding='utf-8'))['mapas']
    llegada = tuple(next(p for p in portales['41'] if p.get('destino') == STAGE)['llegada'])
    visto, cola = {llegada}, [llegada]
    while cola:
        x, y = cola.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if n not in visto and transitable.se_pisa(STAGE, *n):
                    visto.add(n)
                    cola.append(n)
    for s in _spawns():
        assert tuple(s['tile']) in visto, s


def test_los_monstruos_se_arman_con_vida_extra_para_elites_y_jefe():
    bichos = app._monstruos_de(STAGE)
    por_tipo = {}
    for m in bichos.values():
        por_tipo.setdefault(m.npc_type, m)
    assert len(bichos) == len(_spawns())
    assert bichos[next(e['entity_id'] for e in _spawns() if e.get('jefe'))].hp_max > 500000
    assert por_tipo[JEFE].hp_max > 20 * por_tipo[205].hp_max


def test_portales_de_ida_y_vuelta_validos():
    portales = json.loads((PLANT / 'portales.json').read_text(encoding='utf-8'))['mapas']
    ida = next(p for p in portales['41'] if p.get('destino') == STAGE)
    vuelta = next(p for p in portales[str(STAGE)] if p.get('destino') == 41)
    assert transitable.se_pisa(41, *ida['tile']) and transitable.se_pisa(STAGE, *ida['llegada'])
    assert transitable.se_pisa(STAGE, *vuelta['tile']) and transitable.se_pisa(41, *vuelta['llegada'])
    cheb = lambda a, b: max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    assert cheb(ida['llegada'], vuelta['tile']) > 1 and cheb(vuelta['llegada'], ida['tile']) > 1
    assert ida['entity'] != vuelta['entity']


def test_el_jefe_solo_suelta_piedras_de_holy():
    for _ in range(50):
        botin = combate.botin_items(JEFE, 'Dragonkin Moowad', 65)
        assert botin and all(item in PIEDRAS_HOLY for item, _n in botin)


def test_la_fila_de_stage_xml_no_lleva_flags_especiales(tmp_path):
    """El 強制傳送 del 55 cerraba el cliente: la fila nueva (copia de la del 46) va sin ninguno."""
    import pytest
    if not (RAIZ / 'parches' / 'update27.pak').exists():
        pytest.skip('sin parches/update27.pak')
    sys.path.insert(0, str(RAIZ / 'tools'))
    import generar_instancia_oscura as g
    g.registrar_stage(tmp_path)
    xml = (tmp_path / 'setting' / 'eng' / 'stage.xml').read_text(encoding='utf-8')
    fila = next(l for l in xml.splitlines() if '編號="%d"' % STAGE in l and '<場景' in l)
    assert 'map%03d.mpc' % STAGE in fila
    for flag in ('強制傳送', '陣營', '平行空間', 'PVP陣營對戰', '動態空間', '不可標記'):
        assert flag not in fila, (flag, fila)
    assert STAGE not in STAGES_PROHIBIDOS


def test_el_mapa_46_original_no_se_toca():
    """El 46 vuelve a ser el Training Cave original: ni su mapa se reparte ni la instancia lo usa."""
    import pathlib as _p
    assert 46 not in app.mapas_poblados() or app.mapas_poblados()[46] != 'dark_cavern.json'
    assert not (RAIZ / 'parches' / 'extras' / 'map' / 'map046.mpc').exists()


def test_los_sprites_de_los_monstruos_vienen_en_el_cliente():
    """Con sprites que no estan en ningun .pak el monstruo existe pero no se ve."""
    import re
    import cliente_local
    ruta = pathlib.Path(cliente_local.ruta_cliente())
    if not ruta.is_dir():
        import pytest
        pytest.skip('sin cliente')
    nombres = set(cliente_local.indice_paks(ruta))
    for sprite in {s['sprite'] for s in _spawns()}:
        assert any(re.fullmatch(r'SHAPE[\\/]MON[\\/][^\\/]+[\\/]%d_WAIT\.SPR' % sprite, n.upper()) for n in nombres), sprite


def test_el_mapa_propio_es_el_que_usa_el_servidor():
    """map046.mpc (tools/mapas_propios) y transitable.bin cuentan lo mismo."""
    import struct
    datos = (RAIZ / 'tools' / 'mapas_propios' / 'map900.mpc').read_bytes()
    ancho, alto = struct.unpack_from('<II', datos, 4)
    for x, y in ((24, 62), (187, 62), (0, 0), (100, 3), (155, 95)):
        celda = (alto - 1 - y) * ancho + x
        libre = datos[96 + celda * 6 + 1] & 3 == 0
        assert transitable.se_pisa(STAGE, x, y) == libre, (x, y)


class _Ses:
    def __init__(self):
        self.enviados = []
        self.personaje = type('P', (), {'stage': STAGE})()

    def enviar(self, *paquetes):
        self.enviados.extend(paquetes)


def test_puzzles_las_puertas_cierran_el_paso_hasta_romper_los_sellos():
    import instancia_oscura as io
    datos = io.datos()
    a, b = datos['puertas']
    ses = _Ses()
    io.reiniciar(ses)
    cruce = lambda p: (tuple(p['zona'][0]), tuple(p['zona'][0]))
    assert io.bloquear_paso(ses, *cruce(a)) and io.bloquear_paso(ses, *cruce(b))
    monstruos = {s['sello']: type('M', (), {'sello': s['sello']})() for s in _spawns() if s.get('sello')}
    io.al_morir(ses, monstruos[1])
    assert io.bloquear_paso(ses, *cruce(a))
    io.al_morir(ses, monstruos[2])
    assert not io.bloquear_paso(ses, *cruce(a)) and io.bloquear_paso(ses, *cruce(b))
    io.al_morir(ses, monstruos[3])
    assert not io.bloquear_paso(ses, *cruce(b))
    io.reiniciar(ses)
    assert io.bloquear_paso(ses, *cruce(a))


def test_puzzles_los_sellos_llegan_al_monstruo_y_estan_antes_de_su_puerta():
    bichos = app._monstruos_de(STAGE)
    sellos = [b for b in bichos.values() if getattr(b, 'sello', None)]
    assert sorted(b.sello for b in sellos) == [1, 2, 3]
    import instancia_oscura as io
    a, b = io.datos()['puertas']
    s = {x.sello: x for x in sellos}
    # el tercero esta pasada la puerta A y antes de la B, en el eje x del recorrido
    assert s[1].tile[0] < a['zona'][0][0] and s[2].tile[0] < a['zona'][0][0]
    assert a['zona'][0][0] < s[3].tile[0] < b['zona'][0][0]


def test_puzzles_cada_puerta_cerrada_dibuja_su_cortina_de_luz_y_al_abrirse_la_quita():
    import struct
    import instancia_oscura as io
    puertas = io.datos()['puertas']
    paquetes = io.poblar(STAGE)
    assert io.poblar(41) == []
    assert len(paquetes) == sum(len(p['barrera']) for p in puertas) >= 6
    assert all(struct.unpack_from('<H', pk)[0] == 0x000E for pk in paquetes)
    assert len({struct.unpack_from('<I', pk, 2)[0] for pk in paquetes}) == len(paquetes)
    ses = _Ses()
    io.reiniciar(ses)
    monstruos = {s['sello']: type('M', (), {'sello': s['sello']})() for s in _spawns() if s.get('sello')}
    io.al_morir(ses, monstruos[1])
    io.al_morir(ses, monstruos[2])
    quitados = [pk for pk in ses.enviados if len(pk) == 7 and struct.unpack_from('<H', pk)[0] == 0x0007]
    assert len(quitados) == len(puertas[0]['barrera'])


def test_quien_se_desconecta_dentro_de_la_instancia_vuelve_al_lyceum_al_entrar():
    """La casilla guardada de la instancia puede caer en roca del mapa nuevo: el cliente se cerraba al cargar."""
    import cuentas
    ficha = {'ranura': 0, 'char_id': 7, 'nombre': 'X', 'habilidades': [], 'barra': [], 'quests': [],
             'stage_id': STAGE, 'tile_x': 13, 'tile_y': 50, 'inventario': {}}
    assert not transitable.se_pisa(STAGE, 13, 50)
    p = cuentas.personaje_de({'personajes': [ficha]}, 0)
    assert (p.stage, p.tile_x, p.tile_y) == (41, 160, 36)
    ficha.update(stage_id=41, tile_x=100, tile_y=100)
    p = cuentas.personaje_de({'personajes': [ficha]}, 0)
    assert (p.stage, p.tile_x, p.tile_y) == (41, 100, 100)
