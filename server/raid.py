"""La raid Flamefang (11/11/2026): hasta 20 jugadores de nivel 60 contra tres jefes con mecanicas tipo WoW.

"20 jugadores max, toma un mapa de las expansiones nuevas y haz ciertos ajustes y hagamoslo raid. nivel 60, que de
items lvl 60 clase S, rides, items para intensificar ride y gear, con datos tipo wow, usa mob de las nuevas
expansiones ... con stats lvl 60 pero un poco mas fuerte."

* EL MAPA es la escena 902, copia del Flamefang Sanctum (292), y es una instancia: cada raid tiene su copia
  (eventos_mundo._clave_corrida da ('raid', id) a los de la raid). Sus saltos y eventos no hacen nada aqui (app).
* LOS DATOS (bichos de cada zona, jefes, adds, numeros de las mecanicas) estan en plantillas/raid_flamefang.json, y
  los monstruos (clones 239xx de los del 292, nivel 60-65) en content.db: tools/generar_raid.py.
* EL GRUPO: una raid son hasta MAX_MIEMBROS jugadores de nivel NIVEL_MINIMO, con un lider. Se crea, se invita (por
  nombre o a toda la party) y se acepta desde la ventana (server/lua/raid.lua, ventana 59600 de wnd03.xml, boton de
  la barra 59004). c2s 0x002F [u8 171][u32 a][u32 b]: ver procesar().
* EL RECORRIDO: el lider entra y empieza la corrida en la primera zona; los demas entran con el mismo boton. En cada
  zona salen sus grupos de bichos; muertos todos, sale su jefe. Al morir el jefe, botin y, a los PAUSA_PORTAL
  segundos, todos los de la copia pasan a la zona siguiente. Tras el ultimo, la raid esta completa.
* LAS MECANICAS (bucle _mecanicas cada TICK segundos mientras el jefe vive), con aviso antes de cada golpe:
    Infernal Lavamon: charcos de lava bajo 3 jugadores (moverse), al 50% se parte en Lava Blobs.
    Hellfire Razorex: Searing Claw al que le pega cada vez mas fuerte (cambiar de tanque), aliento frontal
                      (apartarse del frente), furia al 30%.
    Satrixia: Inferno Nova a toda la raid (curar), al 66% escudo mientras vivan sus Firal, al 33% Doom sobre un
              jugador que tiene que alejarse de los demas.
  Todos con ENRAGE: pasado el tiempo pegan x3. Si la raid entera cae (wipe), el jefe se recupera y vuelve a empezar.
* EL BOTIN es personal: cada jefe da premio a cada jugador una vez por semana (lockout, se reinicia el lunes), en su
  ficha ('raid_lockout'). Vales de Enhanced Pestle / Ride Feed / Piercing Hammer / Hammer, Mount Coins y, con suerte,
  la caja de su clase (S lvl 60), la de armas o la de monturas (tools/generar_lucky_bags.py, cajas_raid).
"""
import asyncio
import datetime
import json
import logging
import math
import pathlib
import random
import struct
import time

import canal_lua

log = logging.getLogger('raid')

STAGE = 902
CMD_RAID = 171
MAX_MIEMBROS = 20
NIVEL_MINIMO = 60
PAUSA_PORTAL = 8.0
TICK = 0.5
ENRAGE_MULT = 3.0
SALIDA = (41, (173, 91))            # el Angel Lyceum, como la Torre de Babel
PLANTILLA = pathlib.Path(__file__).parent / 'plantillas' / 'raid_flamefang.json'
NOMBRE = 'Flamefang Raid'
EFECTO_AVISO, MAGIA_AVISO = 8, 212  # el fuego del Phoenix Fire sobre el marcado
EFECTO_PORTAL, MAGIA_PORTAL = 45, 1640

# EL BOTIN (por jugador y jefe, una vez por semana).
VALES = (20228, 20229, 20230, 20231)     # Lucky Enhanced Pestle / Ride Feed / Piercing Hammer / Hammer Voucher
MOUNT_COIN = 89073
CAJA_DE_SKILL = {9: 89300, 10: 89301, 11: 89302, 17: 89303, 8: 89304, 30: 89305}   # arma -> caja de su clase
CAJA_ARMAS, CAJA_MONTURAS = 89306, 89307
# por jefe: (vales minimo, maximo), Mount Coins, probabilidad de caja de clase, de armas y de monturas
BOTIN = (
    ((2, 3), 2, 0.25, 0.10, 0.08),
    ((2, 4), 3, 0.30, 0.15, 0.12),
    ((3, 5), 5, 0.40, 0.25, 0.20),
)

# Lo que se manda al entrar (subasta_ventana, con los demas saludos): el boton "AOF Raid" de la barra abre el listado
# de raids, y el menu de clic derecho sobre un jugador lleva "Invite to raid" si eres el lider (lua/raid_menu.lua).
SALUDO_LUA = (canal_lua.CARPETA / 'raid_menu.lua').read_text(encoding='utf-8')

# LAS RAIDS DEL LISTADO "AOF Raids" (11/11/2026: "en vez de ser 1 icono por raid, sea un listado de raid ... y se
# puedan seleccionar ahi las raid a las que quiera ir"). Por ahora una; las siguientes se anaden aqui.
CATALOGO = (
    {'clave': 'flamefang', 'nombre': NOMBRE, 'nivel': NIVEL_MINIMO, 'jugadores': MAX_MIEMBROS},
)

_RAIDS = {}            # id -> dict(id, lider, miembros [char_id], nombres {char_id: nombre}, corrida)
_DE_QUIEN = {}         # char_id -> id de su raid
_INVITACIONES = {}     # char_id -> (id de la raid, caduca)
_NOMBRE_ESCRITO = {}   # char_id -> {trozo: 4 bytes}: el nombre que se escribe en la ventana para invitar
_SIG = [1]
_DATOS = None


def datos():
    global _DATOS
    if _DATOS is None:
        _DATOS = json.loads(PLANTILLA.read_text(encoding='utf-8'))
    return _DATOS


def _cid(ses):
    return int(getattr(getattr(ses, 'personaje', None), 'char_id', 0) or 0)


def _nombre(ses):
    return getattr(getattr(ses, 'personaje', None), 'nombre', '?')


def raid_de(ses):
    r = _RAIDS.get(_DE_QUIEN.get(_cid(ses)))
    return r


def _aviso(ses, texto):
    import clases
    try:
        ses.enviar(clases.aviso(texto, tipo=0))
    except Exception:
        pass


# ------------------------------------------------------------------------------------------------------- el grupo
def crear(ses):
    if raid_de(ses):
        return 'You are already in a raid.'
    if int(getattr(ses.personaje, 'nivel', 0) or 0) < NIVEL_MINIMO:
        return 'You need level %d to join a raid.' % NIVEL_MINIMO
    rid = _SIG[0]
    _SIG[0] += 1
    _RAIDS[rid] = {'id': rid, 'lider': _cid(ses), 'miembros': [_cid(ses)], 'nombres': {_cid(ses): _nombre(ses)},
                   'corrida': None}
    _DE_QUIEN[_cid(ses)] = rid
    log.info('raid %d creada por %s', rid, _nombre(ses))
    return None


def invitar(ses, otro):
    """El lider invita a `otro` (sesion). Devuelve el motivo si no se puede."""
    r = raid_de(ses)
    if not r:
        return 'Create a raid first.'
    if r['lider'] != _cid(ses):
        return 'Only the raid leader can invite.'
    if otro is None or not getattr(otro, 'personaje', None):
        return 'That player is not online.'
    if otro is ses:
        return 'You are already in the raid.'
    if raid_de(otro):
        return '%s is already in a raid.' % _nombre(otro)
    if int(getattr(otro.personaje, 'nivel', 0) or 0) < NIVEL_MINIMO:
        return '%s needs level %d.' % (_nombre(otro), NIVEL_MINIMO)
    if len(r['miembros']) >= MAX_MIEMBROS:
        return 'The raid is full (%d players).' % MAX_MIEMBROS
    _INVITACIONES[_cid(otro)] = (r['id'], time.time() + 120)
    if getattr(otro, 'canal_lua', 0):
        otro.enviar(canal_lua.paquete(_lua()), canal_lua.llamar('RaidInvitacion', _nombre(ses), r['id']))
    _aviso(otro, '%s invites you to the %s: press Accept in the raid window.' % (_nombre(ses), NOMBRE))
    return None


def aceptar(ses, rid):
    inv = _INVITACIONES.pop(_cid(ses), None)
    r = _RAIDS.get(rid)
    if not inv or inv[0] != rid or inv[1] < time.time() or not r:
        return 'The invitation expired.'
    if raid_de(ses):
        return 'You are already in a raid.'
    if len(r['miembros']) >= MAX_MIEMBROS:
        return 'The raid is full.'
    r['miembros'].append(_cid(ses))
    r['nombres'][_cid(ses)] = _nombre(ses)
    _DE_QUIEN[_cid(ses)] = rid
    log.info('%s se une a la raid %d', _nombre(ses), rid)
    return None


def salir(ses, sesiones=()):
    r = raid_de(ses)
    if not r:
        return 'You are not in a raid.'
    cid = _cid(ses)
    r['miembros'].remove(cid)
    r['nombres'].pop(cid, None)
    _DE_QUIEN.pop(cid, None)
    if getattr(getattr(ses, 'personaje', None), 'stage', None) == STAGE:
        _sacar(ses)
    if not r['miembros']:
        _deshacer(r)
    elif r['lider'] == cid:
        r['lider'] = r['miembros'][0]
    _refrescar_ventanas(r, sesiones)
    return None


def _deshacer(r):
    for cid in list(r['miembros']):
        _DE_QUIEN.pop(cid, None)
    _RAIDS.pop(r['id'], None)
    if r.get('corrida'):
        r['corrida']['fin'] = True
    log.info('raid %d deshecha', r['id'])


# ------------------------------------------------------------------------------------------------------- la copia
def _en_la_copia(r):
    """Las sesiones de la raid que estan en su copia del mapa."""
    return [s for s in _sesiones_de(r) if getattr(getattr(s, 'personaje', None), 'stage', None) == STAGE]


_CONECTADOS = [[]]      # [la lista de sesiones del servidor (app.Servidor.mundos)]: la pone procesar(), y al ser la
                        # misma lista (no una copia) los que entran despues ya estan


def conectados():
    return list(_CONECTADOS[0])


def _sesiones_de(r):
    miembros = set(r['miembros'])
    return [s for s in conectados() if not getattr(s, 'cerrada', False) and _cid(s) in miembros]


def _sacar(ses):
    import app
    try:
        app._sincronizar_cambio_mapa(ses, SALIDA[0], *SALIDA[1])
    except Exception:
        log.exception('raid: no se pudo sacar a %s', _nombre(ses))


def entrar(ses, addr='?'):
    """El boton de entrar: el lider empieza la corrida; los demas entran a la que este en marcha."""
    import app
    r = raid_de(ses)
    if not r:
        return 'Create or join a raid first.'
    if int(getattr(ses.personaje, 'nivel', 0) or 0) < NIVEL_MINIMO:
        return 'You need level %d.' % NIVEL_MINIMO
    if getattr(ses, 'muerto', False):
        return 'You cannot enter while dead.'
    c = r.get('corrida')
    if c is None or c.get('fin'):
        if r['lider'] != _cid(ses):
            return 'Wait for the raid leader to enter first.'
        c = r['corrida'] = {'zona': 0, 'vivos': set(), 'poblada': -1, 'jefe': None, 'adds': set(),
                            'inicio': time.time(), 'jefes_muertos': [], 'fin': False}
        log.info('raid %d: %s empieza la corrida', r['id'], _nombre(ses))
    if c['zona'] >= len(datos()['zonas']):
        return 'This raid is already complete. Create a new one next week.'
    llegada = tuple(datos()['entrada'] if c['zona'] == 0 and not c['jefes_muertos'] else
                    datos()['zonas'][c['zona']]['inicio'])
    app._viajar_por_portal(ses, addr, {'destino': STAGE, 'llegada': llegada}, motivo='a la raid')
    return None


def corrida_de(ses):
    r = raid_de(ses)
    c = r.get('corrida') if r else None
    return (r, c) if c and not c.get('fin') else (r, None)


def al_entrar(ses, addr='?'):
    """El jugador termino de cargar un mapa. En el de la raid: sin raid o sin corrida, fuera; si no, la zona."""
    p = getattr(ses, 'personaje', None)
    if not p or getattr(p, 'stage', None) != STAGE:
        return
    r, c = corrida_de(ses)
    if c is None:
        _aviso(ses, 'You are not in an active raid.')
        _sacar(ses)
        return
    if c['poblada'] != c['zona']:
        _poblar(ses, r, c)
    zona = datos()['zonas'][c['zona']]
    _aviso(ses, '%s - %s (%d/%d)' % (NOMBRE, zona['nombre'], c['zona'] + 1, len(datos()['zonas'])))


def _nuevo_eid():
    import app
    eid = app._SIG_GENERADO[0]
    app._SIG_GENERADO[0] += 1
    return eid


def _sacar_bicho(ses, npc_type, casilla, r, c):
    import app
    m = app._poner_generado(ses, _nuevo_eid(), int(npc_type), tuple(casilla), 0)
    if m is None:
        return None
    m.raid = r['id']
    m.agro = max(int(getattr(m, 'agro', 0) or 0), 6)
    for s in _en_la_copia(r):
        if s is not ses:
            _mostrar(s, m)
    return m


def _mostrar(s, m):
    """Le dibuja el bicho a `s` si no lo tiene ya (como torre_babel._mostrar_jefe)."""
    import combate
    import login
    if getattr(s, 'cerrada', False):
        return
    if getattr(s, 'monstruos', None) is None:
        s.monstruos = {}
    if s.monstruos.get(m.entity_id) is m:
        return
    s.monstruos[m.entity_id] = m
    m.compartido = True
    aparece = login._npc_spawn(m.entity_id, int(m.npc_type), m.nombre, (m.tile_x, m.tile_y),
                               sprite=getattr(m, 'sprite', 0), klass=1)
    (getattr(s, 'enviar_sin_espejo', None) or s.enviar)(aparece, combate.atributo(m.entity_id, m.porcentaje))


def _poblar(ses, r, c):
    """Los grupos de bichos de la zona de la corrida."""
    zona = datos()['zonas'][c['zona']]
    c['poblada'] = c['zona']
    c['vivos'] = set()
    for grupo in zona['grupos']:
        for x, y, npc in grupo:
            m = _sacar_bicho(ses, npc, (x, y), r, c)
            if m is not None:
                c['vivos'].add(m.entity_id)
    log.info('raid %d: zona %d (%s) con %d bichos', r['id'], c['zona'], zona['nombre'], len(c['vivos']))
    if not c['vivos']:
        _sacar_jefe(ses, r, c)


def _sacar_jefe(ses, r, c):
    zona = datos()['zonas'][c['zona']]
    m = _sacar_bicho(ses, zona['jefe'], zona['casilla_jefe'], r, c)
    if m is None:
        log.warning('raid %d: no salio el jefe %s', r['id'], zona['jefe'])
        return
    m.agro = max(int(getattr(m, 'agro', 0) or 0), 10)
    c['jefe'] = m
    c['jefe_estado'] = {'hp_ini': m.hp_max, 'atk_ini': m.atk, 'pull': None, 'hechos': set(), 'proximo': {}}
    _cartel(r, '%s awakens! Prepare yourselves.' % m.nombre)
    try:
        c['tarea'] = asyncio.get_event_loop().create_task(_mecanicas(ses, r, c, m))
    except RuntimeError:
        c['tarea'] = None


def _cartel(r, texto):
    for s in _en_la_copia(r):
        _aviso(s, texto)
        try:
            s.volcar()
        except Exception:
            pass


def al_morir(ses, m, addr='?'):
    """Un bicho cayo en la copia de la raid."""
    p = getattr(ses, 'personaje', None)
    if not p or getattr(p, 'stage', None) != STAGE or getattr(m, 'raid', None) is None:
        return
    r = _RAIDS.get(m.raid)
    c = r.get('corrida') if r else None
    if not c or c.get('fin'):
        return
    eid = int(m.entity_id)
    c['adds'].discard(eid)
    if eid in c['vivos']:
        c['vivos'].discard(eid)
        if not c['vivos'] and c['jefe'] is None:
            _sacar_jefe(ses, r, c)
        elif len(c['vivos']) in (10, 5):
            _cartel(r, '%d enemies remain before the guardian appears.' % len(c['vivos']))
        return
    if c['jefe'] is not None and eid == int(c['jefe'].entity_id):
        _jefe_muerto(ses, r, c, m)


def _jefe_muerto(ses, r, c, m):
    zona_idx = c['zona']
    c['jefe'] = None
    c['jefes_muertos'].append(zona_idx)
    for eid in list(c['adds']):
        _quitar(r, eid)
    c['adds'] = set()
    segundos = int(time.time() - ((c.get('jefe_estado') or {}).get('pull') or time.time()))
    _cartel(r, '%s has been defeated! (%d:%02d)' % ((m.nombre,) + divmod(segundos, 60)))
    for s in _en_la_copia(r):
        try:
            _botin(s, zona_idx)
        except Exception:
            log.exception('raid: botin de %s', _nombre(s))
    c['zona'] = zona_idx + 1
    if c['zona'] >= len(datos()['zonas']):
        segundos = int(time.time() - c['inicio'])
        _cartel(r, 'The %s is complete! Total time %d:%02d. Leave from the raid window.'
                % ((NOMBRE,) + divmod(segundos, 60)))
        log.info('raid %d completa en %ds: %s', r['id'], segundos, ', '.join(r['nombres'].values()))
        return
    _cartel(r, 'A portal opens to %s in %d seconds...' % (datos()['zonas'][c['zona']]['nombre'], int(PAUSA_PORTAL)))
    try:
        asyncio.get_event_loop().call_later(PAUSA_PORTAL, _siguiente_zona, r, c)
    except RuntimeError:
        _siguiente_zona(r, c)


def _siguiente_zona(r, c):
    import combate
    import desplazamientos
    if r.get('corrida') is not c or c.get('fin'):
        return
    zona = datos()['zonas'][c['zona']]
    gente = _en_la_copia(r)
    for s in gente:
        try:
            p = s.personaje
            s.enviar(combate.efecto_magia_self_inicio(p.entity_id, EFECTO_PORTAL, MAGIA_PORTAL, cast_time=0))
            desplazamientos.reubicar(s, tuple(zona['inicio']), 'raid')
            s.enviar(combate.efecto_magia_self_fin(p.entity_id, EFECTO_PORTAL, MAGIA_PORTAL))
        except Exception:
            log.exception('raid: portal de %s', _nombre(s))
    vivos = [s for s in gente if not getattr(s, 'muerto', False)]
    if vivos:
        _poblar(vivos[0], r, c)
    _cartel(r, '%s - %s (%d/%d)' % (NOMBRE, zona['nombre'], c['zona'] + 1, len(datos()['zonas'])))


def _quitar(r, eid):
    import combate
    for s in _en_la_copia(r):
        m = (getattr(s, 'monstruos', None) or {}).pop(eid, None)
        try:
            (getattr(s, 'enviar_sin_espejo', None) or s.enviar)(combate.despawn_monstruo(eid))
        except Exception:
            pass
        if m is not None:
            m.vivo = False
            m.hp = 0


def antes_de_viajar(ses, stage_destino):
    """Alguien sale de la copia: si ya no queda nadie de la raid dentro, el jefe en pie se recupera."""
    p = getattr(ses, 'personaje', None)
    if not p or getattr(p, 'stage', None) != STAGE or int(stage_destino) == STAGE:
        return
    r, c = corrida_de(ses)
    if c is None:
        return
    if not [s for s in _en_la_copia(r) if s is not ses] and c.get('jefe') is not None:
        _reiniciar_jefe(r, c, 'Everyone left: %s recovers.')


def al_desconectar(ses):
    antes_de_viajar(ses, 0)


# ------------------------------------------------------------------------------------------------------- mecanicas
def _vida_max(s):
    import app
    try:
        return int(app._vida_max(s.personaje, bolsa=s.inventario))
    except Exception:
        return int(getattr(s.personaje, 'hp_max', 0) or getattr(s.personaje, 'hp', 1) or 1)


def herir(s, m, pct, magia=MAGIA_AVISO, efecto=EFECTO_AVISO):
    """Quita `pct` % de la vida maxima de `s` (una mecanica del jefe `m`) y lo mata si llega a 0, como el golpe de un
    bicho en app (absorcion del Avatar, numeros, vida y muerte a la vista de los demas)."""
    import app
    import combate as cb
    p = getattr(s, 'personaje', None)
    if p is None or getattr(s, 'muerto', False) or p.hp <= 0:
        return 0
    dano = max(1, int(_vida_max(s) * pct / 100.0))
    try:
        dano = __import__('avatar_clones').absorber(s, dano)
    except Exception:
        pass
    p.hp = max(0, p.hp - dano)
    yo = p.entity_id
    pk = [cb.numero_de_dano(m.entity_id, yo, dano, ataque=magia, efecto=efecto),
          cb.cierre_de_dano(m.entity_id, yo, magia, efecto=efecto),
          cb.numero_flotante(yo, dano), cb.atributo(yo, p.hp, cb.KIND_HP)]
    if p.hp <= 0:
        s.enviar(*pk)
        app._quitar_buffs_al_morir(s)
        s.enviar(cb.ataque(yo, m.entity_id, 0, cb.TIPO_MUERTE), cb.atributo(yo, 0, cb.KIND_HP))
        s.muerto = True
        app._avisar_muerte_a_los_demas(s, m.entity_id)
    else:
        s.enviar(*pk)
    try:
        __import__('equipos').notificar_stats(s)
        s.volcar()
    except Exception:
        pass
    return dano


def _marcar(s, segundos):
    """El fuego del aviso sobre el jugador (lo ve el y los demas)."""
    import combate
    import presencia
    try:
        p = s.personaje
        s.enviar(combate.efecto_magia_self_inicio(p.entity_id, EFECTO_AVISO, MAGIA_AVISO,
                                                  cast_time=int(segundos * 1000)))
        presencia.notificar_companero_accion(
            s, combate.efecto_magia_self_inicio(presencia.entidad_de(s), EFECTO_AVISO, MAGIA_AVISO,
                                                cast_time=int(segundos * 1000)))
    except Exception:
        log.debug('raid: marca', exc_info=True)


def _casilla(s):
    p = s.personaje
    return (int(p.tile_x), int(p.tile_y))


def _diferido(segundos, fn, *args):
    try:
        asyncio.get_event_loop().call_later(segundos, fn, *args)
    except RuntimeError:
        fn(*args)


def _jefe_vivo(c, m):
    return c.get('jefe') is m and getattr(m, 'hp', 0) > 0 and getattr(m, 'vivo', True) and not c.get('fin')


def _objetivo(r, m):
    """La sesion a la que le esta pegando el jefe (su en_combate_con), o None."""
    import presencia
    eid = getattr(m, 'en_combate_con', None)
    for s in _en_la_copia(r):
        if eid in (s.personaje.entity_id, presencia.entidad_de(s)):
            return s
    return None


def _reiniciar_jefe(r, c, texto):
    import combate
    m = c.get('jefe')
    if m is None:
        return
    e = c['jefe_estado']
    m.hp = m.hp_max = e['hp_ini']
    m.atk = e['atk_ini']
    m.en_combate_con = None
    e.update(pull=None, hechos=set(), proximo={}, pilas={}, escudo=None, enfurecido=False)
    for eid in list(c['adds']):
        _quitar(r, eid)
    c['adds'] = set()
    for s in _en_la_copia(r):
        try:
            (getattr(s, 'enviar_sin_espejo', None) or s.enviar)(combate.atributo(m.entity_id, m.porcentaje))
        except Exception:
            pass
    _cartel(r, texto % m.nombre)


def _sacar_adds(ses, r, c, npc, cuantos):
    zona = datos()['zonas'][c['zona']]
    casillas = zona.get('casillas_adds') or [zona['casilla_jefe']]
    for k in range(cuantos):
        m = _sacar_bicho(ses, npc, casillas[k % len(casillas)], r, c)
        if m is not None:
            m.agro = 12
            c['adds'].add(m.entity_id)


async def _mecanicas(ses, r, c, m):
    """El bucle del jefe: mientras viva, sus mecanicas (ver el docstring del modulo)."""
    mec = datos()['mecanicas'].get(str(m.npc_type), {})
    e = c['jefe_estado']
    e.setdefault('pilas', {})
    while _jefe_vivo(c, m):
        await asyncio.sleep(TICK)
        if not _jefe_vivo(c, m):
            break
        try:
            gente = _en_la_copia(r)
            vivos = [s for s in gente if not getattr(s, 'muerto', False) and s.personaje.hp > 0]
            if e['pull'] is None:
                if m.hp < m.hp_max:
                    e['pull'] = time.time()
                    e['proximo'] = {k: time.time() + v.get('cada', 0) for k, v in mec.items() if isinstance(v, dict)}
                continue
            if gente and not vivos:
                _reiniciar_jefe(r, c, 'The raid has fallen. %s recovers its strength.')
                continue
            pct = 100.0 * m.hp / max(1, m.hp_max)
            ahora = time.time()
            if not e.get('enfurecido') and ahora - e['pull'] >= mec.get('enrage', 600):
                e['enfurecido'] = True
                m.atk = int(e['atk_ini'] * ENRAGE_MULT)
                _cartel(r, '%s is ENRAGED!' % m.nombre)
            _mecanica(ses, r, c, m, mec, e, pct, ahora, vivos)
        except Exception:
            log.exception('raid: mecanicas de %s', m.nombre)


def _toca(e, clave, mec, ahora):
    t = e['proximo'].get(clave)
    if t is None or ahora < t:
        return False
    e['proximo'][clave] = ahora + mec[clave]['cada']
    return True


def _mecanica(ses, r, c, m, mec, e, pct, ahora, vivos):
    if not vivos:
        return
    # Infernal Lavamon: charcos de lava y, al 50%, se parte en Lava Blobs.
    if 'lava' in mec and _toca(e, 'lava', mec, ahora):
        k = mec['lava']
        marcados = random.sample(vivos, min(k['marcados'], len(vivos)))
        sitios = [_casilla(s) for s in marcados]
        for s in marcados:
            _marcar(s, k['aviso'])
            _aviso(s, 'Lava is erupting under you! MOVE!')
        _cartel(r, '%s spews lava under %s!' % (m.nombre, ', '.join(_nombre(s) for s in marcados)))
        _diferido(k['aviso'], _lava, r, c, m, sitios, k)
    for umbral in mec.get('adds_al', []):
        if pct <= umbral and ('adds', umbral) not in e['hechos']:
            e['hechos'].add(('adds', umbral))
            _cartel(r, '%s splits apart! Kill the Lava Blobs!' % m.nombre)
            _sacar_adds(ses, r, c, datos()['zonas'][c['zona']]['adds'], mec.get('adds', 6))
    # Hellfire Razorex: Searing Claw que se acumula en el tanque, aliento frontal y furia.
    if 'garra' in mec and _toca(e, 'garra', mec, ahora):
        k = mec['garra']
        t = _objetivo(r, m)
        if t is not None and not getattr(t, 'muerto', False):
            cid = _cid(t)
            pila, hasta = e['pilas'].get(cid, (0, 0))
            pila = pila + 1 if hasta > ahora else 1
            e['pilas'][cid] = (pila, ahora + k['dura'])
            herir(t, m, min(90, 10 + k['mas_por_pila'] * (pila - 1)))
            _aviso(t, 'Searing Claw x%d! Another tank should take over.' % pila)
    if 'aliento' in mec and _toca(e, 'aliento', mec, ahora):
        k = mec['aliento']
        t = _objetivo(r, m) or random.choice(vivos)
        _cartel(r, '%s inhales deeply... get out of its front!' % m.nombre)
        _diferido(k['aviso'], _aliento, r, c, m, _casilla(t), k)
    if 'furia_al' in mec and pct <= mec['furia_al'] and 'furia' not in e['hechos']:
        e['hechos'].add('furia')
        m.atk = int(m.atk * mec.get('furia_velocidad', 1.3))
        _cartel(r, '%s flies into a fury!' % m.nombre)
    # Satrixia: Inferno Nova a todos, escudo de Firal al 66% y Doom al 33%.
    if 'nova' in mec and _toca(e, 'nova', mec, ahora):
        k = mec['nova']
        _cartel(r, '%s is casting Inferno Nova! Healers, get ready!' % m.nombre)
        _diferido(k['aviso'], _nova, r, c, m, k)
    if 'fase2_al' in mec and pct <= mec['fase2_al'] and 'fase2' not in e['hechos']:
        e['hechos'].add('fase2')
        e['escudo'] = m.hp
        _cartel(r, '%s raises a shield of fire! Kill her Firals!' % m.nombre)
        _sacar_adds(ses, r, c, datos()['zonas'][c['zona']]['adds'], mec.get('adds', 8))
    if e.get('escudo') is not None:
        if c['adds']:
            if m.hp < e['escudo']:
                m.hp = e['escudo']                     # mientras vivan los Firal no se le baja la vida
        else:
            e['escudo'] = None
            _cartel(r, "%s's shield breaks!" % m.nombre)
    if 'fase3_al' in mec and pct <= mec['fase3_al'] and 'fase3' not in e['hechos']:
        e['hechos'].add('fase3')
        e['proximo']['condena'] = ahora + 3
        _cartel(r, '%s: "Burn, all of you!"' % m.nombre)
    if 'fase3' in e['hechos'] and 'condena' in mec and _toca(e, 'condena', mec, ahora):
        k = mec['condena']
        s = random.choice(vivos)
        _marcar(s, k['aviso'])
        _aviso(s, 'You are marked by DOOM! Run away from everyone!')
        _cartel(r, '%s is marked by Doom! Stay away from %s!' % (_nombre(s), _nombre(s)))
        _diferido(k['aviso'], _condena, r, c, m, s, k)


def _lava(r, c, m, sitios, k):
    if not _jefe_vivo(c, m):
        return
    for s in _en_la_copia(r):
        if any(math.dist(_casilla(s), sitio) <= k['radio'] for sitio in sitios):
            herir(s, m, k['dano'])


def _aliento(r, c, m, hacia, k):
    if not _jefe_vivo(c, m):
        return
    bx, by = m.tile_x, m.tile_y
    dx, dy = hacia[0] - bx, hacia[1] - by
    largo_d = math.hypot(dx, dy) or 1.0
    for s in _en_la_copia(r):
        x, y = _casilla(s)
        vx, vy = x - bx, y - by
        d = math.hypot(vx, vy)
        if d <= k['largo'] and (d < 1 or (vx * dx + vy * dy) / (d * largo_d) >= 0.5):
            herir(s, m, k['dano'])


def _nova(r, c, m, k):
    if not _jefe_vivo(c, m):
        return
    for s in _en_la_copia(r):
        herir(s, m, k['dano'])


def _condena(r, c, m, marcado, k):
    if not _jefe_vivo(c, m):
        return
    centro = _casilla(marcado)
    herir(marcado, m, 30)
    for s in _en_la_copia(r):
        if s is not marcado and math.dist(_casilla(s), centro) <= k['radio']:
            herir(s, m, k['dano'])


# ------------------------------------------------------------------------------------------------------- el botin
def semana(ahora=None):
    """El numero de la semana del lockout: cambia el lunes a las 00:00."""
    d = datetime.date.fromtimestamp(ahora or time.time())
    lunes = d - datetime.timedelta(days=(d.weekday() - datos().get('lockout_dia', 0)) % 7)
    return lunes.toordinal()


def _lockout(s):
    """{zona (str): semana} de la ficha del personaje."""
    import cuentas
    p = s.personaje
    if getattr(p, 'raid_lockout', None) is None:
        p.raid_lockout = {}
        try:
            con = cuentas._get_conn()
            try:
                fila = con.execute('SELECT datos FROM personajes WHERE char_id=? AND usuario=?',
                                   (int(p.char_id), getattr(s, 'usuario', ''))).fetchone()
            finally:
                con.close()
            p.raid_lockout = dict((json.loads(fila[0]) if fila and fila[0] else {}).get('raid_lockout') or {})
        except Exception:
            log.exception('raid: no se pudo leer el lockout de %s', _nombre(s))
    return p.raid_lockout


def bloqueado(s, zona):
    return _lockout(s).get(str(zona)) == semana()


def _anotar_lockout(s, zona):
    import cuentas
    lo = _lockout(s)
    lo[str(zona)] = semana()
    if getattr(s, 'usuario', None):
        try:
            cuentas._actualizar_personaje(s.usuario, s.personaje.char_id,
                                          lambda d: d.update(raid_lockout=dict(lo)))
        except Exception:
            log.exception('raid: no se pudo guardar el lockout de %s', _nombre(s))


def caja_de_clase(inventario):
    import clases
    for sid in sorted(clases.skills_de_equipo(inventario)):
        if sid in CAJA_DE_SKILL:
            return CAJA_DE_SKILL[sid]
    return None


def premios(zona, inventario, rng=random):
    """[(item, cantidad)] del botin de un jefe para un jugador."""
    (vmin, vmax), monedas, p_clase, p_armas, p_montura = BOTIN[min(zona, len(BOTIN) - 1)]
    salen = {}
    for _ in range(rng.randint(vmin, vmax)):
        v = rng.choice(VALES)
        salen[v] = salen.get(v, 0) + 1
    salen[MOUNT_COIN] = monedas
    cajas = []
    clase = caja_de_clase(inventario)
    if rng.random() < p_clase:
        cajas.append(clase or CAJA_ARMAS)
    if rng.random() < p_armas:
        cajas.append(CAJA_ARMAS)
    if rng.random() < p_montura:
        cajas.append(CAJA_MONTURAS)
    if not cajas and zona >= len(BOTIN) - 1:          # el jefe final siempre da una caja
        cajas.append(rng.choice([clase or CAJA_ARMAS, CAJA_ARMAS, CAJA_MONTURAS]))
    for k in cajas:
        salen[k] = salen.get(k, 0) + 1
    return sorted(salen.items())


def _botin(s, zona):
    import app
    if bloqueado(s, zona):
        _aviso(s, 'You already looted this boss this week. It resets on Monday.')
        return
    salen = premios(zona, getattr(s, 'inventario', None) or {})
    _anotar_lockout(s, zona)
    app._aplicar_efectos(s, getattr(s, 'addr', '?'), [('dar', salen)], ' por la raid (jefe %d)' % (zona + 1))
    log.info('raid: %s recibe %s (jefe %d)', _nombre(s), salen, zona + 1)


# ------------------------------------------------------------------------------------------------------- el panel
# "Podria verse el team asi como si fuera el panel de team pero este seria de raid" (11/11/2026): la ventana 59700
# (tools/parche_raid.py), 4 grupos de 5 con vida, mana, rol, lider y estado, refrescada cada PANEL_CADA segundos.
PANEL_CADA = 1.0
TANQUE, SANADOR, DANO = 1, 2, 3
RAMA_ESCUDO, RAMA_VIDA = 14, 1          # Shield y Life (skills.NOMBRE_RAMA)
_BUCLE = [None]


def rol_de(personaje):
    ramas = {int(h[0]) for h in (getattr(personaje, 'habilidades', None) or [])}
    if RAMA_ESCUDO in ramas:
        return TANQUE
    if RAMA_VIDA in ramas:
        return SANADOR
    return DANO


def grupos_de(r):
    """Los miembros en hasta 4 grupos de 5: cada party de la raid es un grupo, y los que no tienen party (o no caben)
    rellenan los huecos. [[char_id, ...], ...]"""
    import equipos
    por_party, sueltos = {}, []
    for cid in r['miembros']:
        lider = equipos._DE_QUIEN.get(cid) if hasattr(equipos, '_DE_QUIEN') else None
        if lider and lider in getattr(equipos, '_GRUPOS', {}):
            por_party.setdefault(lider, []).append(cid)
        else:
            sueltos.append(cid)
    grupos = [g[:5] for g in por_party.values()][:4]
    sueltos += [cid for g in por_party.values() for cid in g[5:]] + [cid for g in list(por_party.values())[4:] for cid in g]
    # Los sueltos van a sus propios grupos mientras quepan (cada party se ve entera y aparte); solo si ya hay 4,
    # rellenan los huecos de las parties.
    de_sueltos = []
    for cid in sueltos:
        hueco = next((g for g in de_sueltos if len(g) < 5), None)
        if hueco is None and len(grupos) < 4:
            hueco = []
            grupos.append(hueco)
            de_sueltos.append(hueco)
        if hueco is None:
            hueco = next((g for g in grupos if len(g) < 5), None)
        if hueco is not None:
            hueco.append(cid)
    return grupos


def panel_de(r):
    """(titulo, grupos) para RaidPanel."""
    por_cid = {_cid(s): s for s in _sesiones_de(r)}
    grupos = []
    for g in grupos_de(r):
        filas = []
        for cid in g:
            s = por_cid.get(cid)
            if s is None:
                filas.append([r['nombres'].get(cid, '?'), 0, 0, DANO, cid == r['lider'], 'off'])
                continue
            p = s.personaje
            vida = int(100 * max(0, p.hp) / max(1, _vida_max(s)))
            try:
                import app
                mana = int(100 * max(0, p.mp) / max(1, int(app._mana_max(p, bolsa=s.inventario))))
            except Exception:
                mana = 0
            estado = 'dead' if getattr(s, 'muerto', False) or p.hp <= 0 else ('' if p.stage == STAGE else 'away')
            filas.append([_nombre(s), min(100, vida), min(100, mana), rol_de(p), cid == r['lider'], estado])
        grupos.append(filas)
    return 'Raid (%d/%d)' % (len(r['miembros']), MAX_MIEMBROS), grupos


def _mandar_panel(r, abrir=False):
    titulo, grupos = panel_de(r)
    pk = canal_lua.llamar('RaidPanel', titulo, grupos)
    for s in _sesiones_de(r):
        if getattr(s, 'canal_lua', 0):
            try:
                if abrir:
                    s.enviar(canal_lua.paquete(_lua()), canal_lua.llamar('RaidPanelAbrir'))
                s.enviar(pk)
            except Exception:
                pass


async def _bucle_panel():
    while _RAIDS:
        await asyncio.sleep(PANEL_CADA)
        for r in list(_RAIDS.values()):
            try:
                _mandar_panel(r)
            except Exception:
                log.exception('raid: panel de la raid %s', r.get('id'))
    _BUCLE[0] = None


def _asegurar_bucle():
    if _BUCLE[0] is None:
        try:
            _BUCLE[0] = asyncio.get_event_loop().create_task(_bucle_panel())
        except RuntimeError:
            _BUCLE[0] = None


# ------------------------------------------------------------------------------------------------------- ventana
def _lua():
    return (canal_lua.CARPETA / 'raid.lua').read_text(encoding='utf-8')


def estado_para(ses):
    """Lo que pinta la ventana: (titulo, miembros [[nombre, nivel, donde]], soy_lider, jefes [[nombre, estado]],
    hay_corrida, en_raid)."""
    r = raid_de(ses)
    zonas = datos()['zonas']
    jefes = []
    for i, z in enumerate(zonas):
        import app
        nombre = app._monstruo_bd(z['jefe'])[0]
        if r and r.get('corrida') and i in r['corrida']['jefes_muertos']:
            estado = 'Defeated'
        elif bloqueado(ses, i):
            estado = 'Looted this week'
        else:
            estado = 'Available'
        jefes.append([nombre, estado])
    if not r:
        return ['No raid', [], False, jefes, False, False]
    por_cid = {_cid(s): s for s in _sesiones_de(r)}
    miembros = []
    for cid in r['miembros']:
        s = por_cid.get(cid)
        if s is None:
            miembros.append([r['nombres'].get(cid, '?'), 0, 'Offline'])
        else:
            donde = 'In raid' if s.personaje.stage == STAGE else 'Outside'
            miembros.append([_nombre(s), int(s.personaje.nivel), donde + (' (Leader)' if cid == r['lider'] else '')])
    titulo = '%s - %d/%d players' % (NOMBRE, len(r['miembros']), MAX_MIEMBROS)
    c = r.get('corrida')
    return [titulo, miembros, r['lider'] == _cid(ses), jefes, bool(c and not c.get('fin')), True]


def abrir(ses, aviso=''):
    return [canal_lua.paquete(_lua()), canal_lua.llamar('RaidAbrir', *(estado_para(ses) + [aviso]))]


def _refrescar_ventanas(r, sesiones=()):
    for s in _sesiones_de(r) if r else []:
        if getattr(s, 'canal_lua', 0):
            try:
                s.enviar(canal_lua.llamar('RaidRefrescar', *estado_para(s)))
            except Exception:
                pass


def _buscar(nombre):
    n = (nombre or '').strip().lower()
    for s in conectados():
        if (getattr(getattr(s, 'personaje', None), 'nombre', '') or '').strip().lower() == n:
            return s
    return None


def procesar(ses, cuerpo, addr='?', sesiones=None) -> bool:
    """c2s 0x002F [u8 171][u32 a][u32 b]:
        a=30 abrir el listado AOF Raids; 31 abrir la raid b del listado (CATALOGO);
        a=1 abrir la ventana; 2 crear; 3 salir de la raid; 4 invitar a mi party; 5 entrar al mapa;
        6 aceptar la invitacion (b = id de la raid); 7 invitar al nombre escrito; 8 salir del mapa;
        20..23 un trozo del nombre escrito (b = 4 letras)."""
    if len(cuerpo) < 9 or cuerpo[0] != CMD_RAID:
        return False
    if sesiones is not None:
        _CONECTADOS[0] = sesiones
    a, b = struct.unpack_from('<II', cuerpo, 1)
    motivo = None
    r = raid_de(ses)
    if a == 1:
        ses.enviar(*abrir(ses))
        _abrir_panel(ses)
        return True
    if a == 30:
        ses.enviar(canal_lua.paquete(SALUDO_LUA), canal_lua.llamar('RaidListaAbrir', lista_de_raids(ses)))
        return True
    if a == 31:
        if 0 <= int(b) < len(CATALOGO):
            ses.enviar(*abrir(ses))
            _abrir_panel(ses)
        return True
    if 20 <= a <= 23:
        _NOMBRE_ESCRITO.setdefault(_cid(ses), {})[a - 20] = struct.pack('<I', b)
        return True
    if a == 2:
        motivo = crear(ses)
    elif a == 3:
        motivo = salir(ses, sesiones or ())
    elif a == 4:
        import equipos
        if not r:
            motivo = crear(ses)
        if not motivo:
            n = 0
            for s in equipos.grupo_de(ses):
                if s is not ses and invitar(ses, s) is None:
                    n += 1
            motivo = 'Invitation sent to %d party member(s).' % n
    elif a == 5:
        motivo = entrar(ses, addr)
    elif a == 6:
        motivo = aceptar(ses, int(b))
    elif a == 7:
        trozos = _NOMBRE_ESCRITO.pop(_cid(ses), {})
        nombre = b''.join(trozos.get(i, b'') for i in range(4)).split(b'\0')[0].decode('latin-1').strip()
        otro = _buscar(nombre)
        motivo = invitar(ses, otro) or 'Invitation sent to %s.' % _nombre(otro)
    elif a == 8:
        if getattr(ses.personaje, 'stage', None) == STAGE:
            _sacar(ses)
    ses.enviar(*abrir(ses, motivo or ''))
    _refrescar_ventanas(raid_de(ses) or r, sesiones or ())
    if raid_de(ses) and a in (2, 4, 5, 6):
        _abrir_panel(ses)
    elif r and not raid_de(ses) and getattr(ses, 'canal_lua', 0):
        ses.enviar(canal_lua.llamar('RaidPanelCerrar'))
    return True


def lista_de_raids(ses):
    """Las filas del listado: [nombre, nivel, jugadores, jefes, como va esta semana]."""
    filas = []
    for raid in CATALOGO:
        jefes = len(datos()['zonas'])
        libres = sum(1 for i in range(jefes) if not bloqueado(ses, i))
        r = raid_de(ses)
        if r and r.get('corrida') and not r['corrida'].get('fin'):
            estado = 'In progress'
        elif libres == 0:
            estado = 'Locked until Monday'
        else:
            estado = '%d/%d bosses left' % (libres, jefes)
        filas.append([raid['nombre'], raid['nivel'], '%d max' % raid['jugadores'], jefes, estado])
    return filas


def _abrir_panel(ses):
    """El panel de la raid a `ses`, si esta en una, y el bucle que lo refresca en marcha."""
    r = raid_de(ses)
    if not r or not getattr(ses, 'canal_lua', 0):
        return
    titulo, grupos = panel_de(r)
    ses.enviar(canal_lua.paquete(_lua()), canal_lua.llamar('RaidPanelAbrir'), canal_lua.llamar('RaidPanel', titulo, grupos))
    _asegurar_bucle()
