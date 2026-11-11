"""La raid Flamefang (server/raid.py, 11/11/2026): grupo de 20 de nivel 60, copia compartida, botin y lockout."""
import datetime
import pathlib
import random
import struct
import sys
from types import SimpleNamespace as NS

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import raid  # noqa: E402


def _ses(cid, nivel=60, stage=41):
    enviados = []
    p = NS(char_id=cid, nombre='P%d' % cid, nivel=nivel, stage=stage, tile_x=10, tile_y=10, hp=1000, entity_id=cid)
    return NS(personaje=p, enviar=lambda *a: enviados.extend(a), canal_lua=1, cerrada=False, inventario={},
              enviados=enviados, volcar=lambda: None)


def _limpiar():
    raid._RAIDS.clear()
    raid._DE_QUIEN.clear()
    raid._INVITACIONES.clear()


def test_crear_invitar_aceptar_y_salir():
    _limpiar()
    lider, otro = _ses(1), _ses(2)
    raid._CONECTADOS[0] = [lider, otro]
    assert raid.crear(lider) is None and raid.raid_de(lider)['lider'] == 1
    assert raid.invitar(lider, otro) is None
    rid = raid.raid_de(lider)['id']
    assert raid.aceptar(otro, rid) is None and raid.raid_de(otro) is raid.raid_de(lider)
    assert raid.salir(lider) is None and raid.raid_de(otro)['lider'] == 2      # el liderazgo pasa al siguiente
    assert raid.salir(otro) is None and not raid._RAIDS                       # vacia, se deshace


def test_nivel_minimo_y_maximo_de_20():
    _limpiar()
    lider = _ses(1)
    raid._CONECTADOS[0] = [lider]
    assert 'level 60' in raid.crear(_ses(9, nivel=59))
    raid.crear(lider)
    assert 'needs level' in raid.invitar(lider, _ses(3, nivel=55))
    r = raid.raid_de(lider)
    r['miembros'] += list(range(100, 119))                                    # 20 en total
    assert 'full' in raid.invitar(lider, _ses(4))


def test_solo_el_lider_invita_y_la_invitacion_caduca():
    _limpiar()
    lider, otro, tercero = _ses(1), _ses(2), _ses(3)
    raid._CONECTADOS[0] = [lider, otro, tercero]
    raid.crear(lider)
    rid = raid.raid_de(lider)['id']
    raid.invitar(lider, otro)
    raid.aceptar(otro, rid)
    assert 'leader' in raid.invitar(otro, tercero)
    raid.invitar(lider, tercero)
    raid._INVITACIONES[3] = (rid, 0)
    assert 'expired' in raid.aceptar(tercero, rid)


def test_toda_la_raid_comparte_copia_aunque_sean_varias_parties():
    import eventos_mundo
    _limpiar()
    lider, otro = _ses(1, stage=raid.STAGE), _ses(2, stage=raid.STAGE)
    raid._CONECTADOS[0] = [lider, otro]
    raid.crear(lider)
    raid.invitar(lider, otro)
    raid.aceptar(otro, raid.raid_de(lider)['id'])
    assert eventos_mundo._clave_corrida(lider) == eventos_mundo._clave_corrida(otro) == ('raid', raid.raid_de(lider)['id'])


def test_el_botin_da_vales_monedas_y_al_final_siempre_una_caja():
    inv = {3: 9000}
    for zona in range(3):
        salen = dict(raid.premios(zona, inv, random.Random(zona)))
        assert sum(salen.get(v, 0) for v in raid.VALES) >= 2 and salen[raid.MOUNT_COIN] >= 2
    cajas = set(raid.CAJA_DE_SKILL.values()) | {raid.CAJA_ARMAS, raid.CAJA_MONTURAS}
    for semilla in range(50):
        assert cajas & set(dict(raid.premios(2, inv, random.Random(semilla))))


def test_la_caja_de_clase_sale_del_arma_equipada(monkeypatch):
    import clases
    monkeypatch.setattr(clases, 'skills_de_equipo', lambda inv: {11})        # lanza
    assert raid.caja_de_clase({3: 1}) == raid.CAJA_DE_SKILL[11]


def test_el_lockout_cambia_el_lunes():
    lunes = datetime.datetime(2026, 11, 9, 0, 30).timestamp()                # lunes
    domingo = datetime.datetime(2026, 11, 15, 23, 0).timestamp()
    siguiente = datetime.datetime(2026, 11, 16, 0, 1).timestamp()
    assert raid.semana(lunes) == raid.semana(domingo) != raid.semana(siguiente)


def test_un_jefe_ya_saqueado_no_da_mas(monkeypatch):
    s = _ses(1)
    s.personaje.raid_lockout = {}
    monkeypatch.setattr(raid, '_anotar_lockout', lambda s, z: s.personaje.raid_lockout.__setitem__(str(z), raid.semana()))
    dados = []
    import app
    monkeypatch.setattr(app, '_aplicar_efectos', lambda s, a, ef, m: dados.append(ef))
    raid._botin(s, 0)
    raid._botin(s, 0)
    assert len(dados) == 1 and raid.bloqueado(s, 0)


def test_la_plantilla_tiene_tres_zonas_con_bichos_que_existen():
    import combate
    d = raid.datos()
    assert d['stage'] == raid.STAGE and len(d['zonas']) == 3
    for z in d['zonas']:
        assert z['grupos'] and combate._datos(z['jefe'])['hp'] >= 1000000
        for g in z['grupos']:
            for x, y, npc in g:
                assert combate._datos(npc) and combate._datos(npc)['hp'] >= 8000


def test_herir_quita_el_porcentaje_y_mata(monkeypatch):
    import app
    s = _ses(1)
    monkeypatch.setattr(raid, '_vida_max', lambda s: 2000)
    monkeypatch.setattr(app, '_quitar_buffs_al_morir', lambda s: None)
    monkeypatch.setattr(app, '_avisar_muerte_a_los_demas', lambda s, e: None)
    s.personaje.hp = 2000
    m = NS(entity_id=77)
    assert raid.herir(s, m, 45) == 900 and s.personaje.hp == 1100
    raid.herir(s, m, 60)
    assert s.personaje.hp == 0 and s.muerto


def test_el_nombre_escrito_llega_en_trozos(monkeypatch):
    _limpiar()
    lider, otro = _ses(1), _ses(2)
    otro.personaje.nombre = 'Baco'
    raid._CONECTADOS[0] = [lider, otro]
    raid.crear(lider)
    monkeypatch.setattr(raid, 'abrir', lambda s, aviso='': [])
    trozo = struct.unpack('<I', b'Baco')[0]
    raid.procesar(lider, struct.pack('<BII', raid.CMD_RAID, 20, trozo))
    raid.procesar(lider, struct.pack('<BII', raid.CMD_RAID, 7, 0))
    assert raid._INVITACIONES[2][0] == raid.raid_de(lider)['id']


def test_panel_por_parties_con_rol_vida_y_estado(monkeypatch):
    import equipos
    _limpiar()
    sesiones = [_ses(c, stage=raid.STAGE) for c in range(1, 9)]
    sesiones[2].muerto = True
    sesiones[3].personaje.stage = 41
    sesiones[0].personaje.habilidades = [(14, 60, 0)]                       # escudo: tanque
    sesiones[1].personaje.habilidades = [(1, 60, 0)]                        # Life: sanador
    for s in sesiones:
        s.personaje.mp = 50
    raid._CONECTADOS[0] = sesiones
    raid.crear(sesiones[0])
    rid = raid.raid_de(sesiones[0])['id']
    for s in sesiones[1:]:
        raid.invitar(sesiones[0], s)
        raid.aceptar(s, rid)
    monkeypatch.setattr(raid, '_vida_max', lambda s: 1000)
    import app
    monkeypatch.setattr(app, '_mana_max', lambda p, bolsa=None: 100)
    monkeypatch.setattr(equipos, '_DE_QUIEN', {5: 5, 6: 5, 7: 5}, raising=False)
    monkeypatch.setattr(equipos, '_GRUPOS', {5: object()}, raising=False)
    titulo, grupos = raid.panel_de(raid.raid_de(sesiones[0]))
    assert titulo == 'Raid (8/20)'
    assert [f[0] for f in grupos[0]] == ['P5', 'P6', 'P7']                 # la party es un grupo
    sueltos = {f[0]: f for f in grupos[1]}
    assert sueltos['P1'][3] == raid.TANQUE and sueltos['P1'][4] and sueltos['P2'][3] == raid.SANADOR
    assert sueltos['P3'][5] == 'dead' and sueltos['P4'][5] == 'away' and sueltos['P1'][1] == 100


def test_el_listado_aof_raids_y_el_saludo(monkeypatch):
    import app
    monkeypatch.setattr(app, '_monstruo_bd', lambda npc: ('Jefe %d' % npc,))
    _limpiar()
    s = _ses(1)
    s.personaje.raid_lockout = {}
    filas = raid.lista_de_raids(s)
    assert filas[0][0] == raid.NOMBRE and filas[0][1] == 60 and filas[0][4] == '3/3 bosses left'
    s.personaje.raid_lockout = {str(i): raid.semana() for i in range(3)}
    assert raid.lista_de_raids(s)[0][4] == 'Locked until Monday'
    assert raid.lista_de_raids(s)[0][5][0] == ['Jefe 23940', 'looted']
    # El boton de la barra abre el listado, y el menu del jugador se envuelve para "Invite to raid".
    assert 'netcommand2(CMD_RAID, 30, 0)' in raid.SALUDO_LUA and 'OnClickChatOption' in raid.SALUDO_LUA


def test_la_guia_cabe_en_la_ventana_y_dice_los_numeros_del_json():
    titulo, paginas = raid.guia(0)
    assert titulo == raid.NOMBRE + ' Guide' and len(paginas) == 5
    for _tab, _titulo, retrato, lineas in paginas:
        ancho = raid.ANCHO_GUIA_JEFE if retrato else raid.ANCHO_GUIA
        assert len(lineas) <= raid.LINEAS_GUIA and all(len(l) <= ancho and '%%' not in l for l in lineas)
    mec = raid.datos()['mecanicas']
    texto = '\n'.join(sum((p[3] for p in paginas), []))
    assert 'every %d s' % mec['23940']['lava']['cada'] in texto
    assert 'her %d Firals' % mec['23942']['adds'] in texto
    assert [p[2] for p in paginas] == [0, 1, 2, 3, 0]


def test_el_boton_guide_manda_la_guia():
    s = _ses(1)
    raid.procesar(s, struct.pack('<BII', raid.CMD_RAID, 32, 0))
    assert any(b'RaidGuia' in bytes(x) for x in s.enviados if isinstance(x, (bytes, bytearray)))
    assert 'OnRaidListaGuia' in raid.SALUDO_LUA and 'function RaidGuia(' in raid.SALUDO_LUA


def test_el_lider_saca_y_pasa_el_liderazgo_desde_el_panel(monkeypatch):
    _limpiar()
    lider, otro, tercero = _ses(1), _ses(2), _ses(3)
    raid._CONECTADOS[0] = [lider, otro, tercero]
    monkeypatch.setattr(raid, '_mandar_panel', lambda r, abrir=False: None)
    monkeypatch.setattr(raid, 'abrir', lambda s, aviso='': [])
    raid.crear(lider)
    rid = raid.raid_de(lider)['id']
    for s in (otro, tercero):
        raid.invitar(lider, s)
        raid.aceptar(s, rid)
    assert 'leader' in raid.expulsar(otro, 3)                                  # solo el lider
    assert 'Leave' in raid.expulsar(lider, 1)                                  # a si mismo no
    raid.procesar(lider, struct.pack('<BII', raid.CMD_RAID, 9, 3))
    assert raid.raid_de(tercero) is None and raid.raid_de(lider)['miembros'] == [1, 2]
    raid.procesar(lider, struct.pack('<BII', raid.CMD_RAID, 10, 2))
    assert raid.raid_de(lider)['lider'] == 2
    assert 'leader' in raid.expulsar(lider, 2)                                 # ya no es el lider


def test_el_panel_lleva_el_char_id_para_el_menu(monkeypatch):
    _limpiar()
    s = _ses(7, stage=raid.STAGE)
    raid._CONECTADOS[0] = [s]
    raid.crear(s)
    monkeypatch.setattr(raid, '_vida_max', lambda s: 1000)
    _titulo, grupos = raid.panel_de(raid.raid_de(s))
    assert grupos[0][0][6] == 7
