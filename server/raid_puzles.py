"""Los puzles de las raids (11/11/2026: "que tengas uno que otro puzzle"; server/raid.py).

Uno antes de cada jefe: muertos los grupos de la zona, una barrera de luz rodea el sitio del jefe y no sale hasta que
se resuelve el puzle de la zona (plantillas/raid_*.json, zona['puzle'], de tools/generar_raid.py):

  placas    altares de luz en el suelo: hace falta un jugador vivo encima de cada uno A LA VEZ durante unos segundos
            (como mucho tantos como jugadores vivos haya en la copia, para que una raid pequena pueda).
  totems    cuatro pilares de colores (no pegan ni se mueven) que hay que tumbar en un orden; tres pistas lo dan.
            Si cae uno fuera de orden, todos se levantan otra vez y la raid recibe un golpe.
  sellos    tres altares del infierno, cada uno con un guardian (un minijefe del mapa): muerto el guardian, su sello
            se rompe. Rotos los tres, la barrera cae.
  antorcha  el altar de llamas da la antorcha a quien se queda a su lado; hay que llevarla hasta el altar de fuego
            antes de que se apague (sin morir), mientras salen bichos detras. Hacen falta varias entregas.

Las marcas son NPC de npc.xml (altares de la guerra de totems) y la barrera el objeto 60402 (cortina de luz), que se
mandan a todos los de la copia y a los que entran despues (paquetes). Todo se comprueba en un bucle cada TICK.
"""
import asyncio
import itertools
import logging
import math
import random
import time

log = logging.getLogger('raid')

TICK = 0.5
BARRERA = 60402
ALTAR = {'placa': 2018, 'sello': 2016, 'origen': 2015, 'destino': 2014}      # Light / Hell / Flame / Fire Altar
COLOR = {0: 'crimson', 1: 'golden', 2: 'jade', 3: 'azure'}                     # los pilares, en orden de 'pilares'
DANO_FALLO = 15          # % de la vida maxima a toda la raid si cae un pilar fuera de orden
CADA_ACOSO = 8.0         # segundos entre los bichos que persiguen a la antorcha
RADIO_PLACA, RADIO_ALTAR = 1, 2


def _raid():
    import raid
    return raid


def _enviar_copia(r, *paquetes):
    for s in _raid()._en_la_copia(r):
        try:
            (getattr(s, 'enviar_sin_espejo', None) or s.enviar)(*paquetes)
        except Exception:
            pass


def _marca(c, npc, casilla, clave):
    """Un altar (NPC de npc.xml) en `casilla`; queda en c['puzle']['marcas'] para borrarlo y para los que lleguen."""
    import app
    import login
    eid = _raid()._nuevo_eid()
    nombre, sprite = app._npc_de_npc_xml(npc) or ('Altar', 0)
    pk = login._npc_spawn(eid, npc, nombre, tuple(casilla), sprite=sprite, klass=199, direccion=6)
    c['puzle']['marcas'][clave] = (eid, pk)
    return eid, pk


def _quitar_marca(r, c, clave):
    import combate
    m = c['puzle']['marcas'].pop(clave, None)
    if m:
        _enviar_copia(r, combate.despawn_monstruo(m[0]))


def _distancia(s, casilla):
    p = s.personaje
    return max(abs(int(p.tile_x) - casilla[0]), abs(int(p.tile_y) - casilla[1]))


def _vivos(r):
    return [s for s in _raid()._en_la_copia(r) if not getattr(s, 'muerto', False) and s.personaje.hp > 0]


def paquetes(c):
    """Lo que ve el que entra a la copia en mitad de un puzle: la barrera y los altares."""
    pz = (c or {}).get('puzle')
    if not pz or pz.get('hecho'):
        return []
    return [pk for _eid, pk in pz['marcas'].values()]


# ------------------------------------------------------------------------------------------------- empezar
def empezar(ses, r, c, zona):
    """Muertos los grupos: la barrera y el puzle de la zona. Devuelve False si la zona no tiene puzle."""
    import login
    R = _raid()
    datos = zona.get('puzle')
    if not datos or c.get('puzle_zona') == c['zona']:
        return False
    c['puzle_zona'] = c['zona']
    pz = c['puzle'] = {'tipo': datos['tipo'], 'datos': datos, 'marcas': {}, 'monstruos': set(), 'hecho': False,
                       'inicio': time.time()}
    eid = R._nuevo_eid()
    pz['marcas']['barrera'] = (eid, login._map_object_spawn(eid, BARRERA, tuple(zona['casilla_jefe'])))
    tipo = datos['tipo']
    if tipo == 'placas':
        for i, cas in enumerate(datos['casillas']):
            _marca(c, ALTAR['placa'], cas, ('placa', i))
        pz['llenas_desde'] = None
        pz['ultimas'] = -1
        R._cartel(r, 'A barrier of light protects the lair. Stand on the Light Altars together to break it!')
    elif tipo == 'totems':
        pz['orden'] = random.sample(range(len(datos['pilares'])), len(datos['pilares']))
        pz['caidos'] = []
        _levantar_pilares(ses, r, c)
        R._cartel(r, 'Four pillars hold the barrier. Bring them down in the right order!')
        for pista in pistas(pz['orden']):
            R._cartel(r, pista)
        pz['proxima_pista'] = time.time() + 30
    elif tipo == 'sellos':
        for i, cas in enumerate(datos['casillas']):
            _marca(c, ALTAR['sello'], cas, ('sello', i))
            m = R._sacar_bicho(ses, datos['guardianes'][i % len(datos['guardianes'])], cas, r, c)
            if m is not None:
                m.agro = 8
                m.sello = i
                pz['monstruos'].add(m.entity_id)
        pz['rotos'] = set()
        R._cartel(r, 'Three seals feed the barrier. Defeat their guardians to break them!')
    else:
        _marca(c, ALTAR['origen'], datos['origen'], 'origen')
        _marca(c, ALTAR['destino'], datos['destino'], 'destino')
        pz.update(entregas=0, portador=None, hasta=0, proximo_acoso=0)
        R._cartel(r, 'The barrier only fears fire. Take the flame from the Flame Altar to the Fire Altar '
                     '(%d times) before it goes out!' % datos['entregas'])
    _enviar_copia(r, *paquetes(c))
    try:
        pz['tarea'] = asyncio.get_event_loop().create_task(_bucle(ses, r, c, pz))
    except RuntimeError:
        pz['tarea'] = None
    log.info('raid %d: puzle %s en la zona %d', r['id'], tipo, c['zona'])
    return True


def pistas(orden):
    """Tres pistas que dan un solo orden posible: a va justo antes que b, d es el ultimo y c no es el primero."""
    a, b, c, d = (COLOR[i].capitalize() for i in orden)
    return ['Clue: the %s pillar falls right after the %s one.' % (b.lower(), a.lower()),
            'Clue: the %s pillar must fall last.' % d.lower(),
            'Clue: the %s pillar is not the first.' % c.lower()]


def _resuelve(orden):
    """Los ordenes que cumplen las pistas de `orden` (para los tests: tiene que ser uno solo)."""
    a, b, c, d = orden
    return [o for o in itertools.permutations(orden)
            if o.index(b) == o.index(a) + 1 and o[-1] == d and o[0] != c]


def _levantar_pilares(ses, r, c):
    R = _raid()
    pz = c['puzle']
    for eid in list(pz['monstruos']):
        R._quitar(r, eid)
        c['vivos'].discard(eid)
    pz['monstruos'] = set()
    pz['caidos'] = []
    for i, cas in enumerate(pz['datos']['casillas']):
        m = R._sacar_bicho(ses, pz['datos']['pilares'][i], cas, r, c)
        if m is not None:
            m.agro = 0
            m.es_estatico = True
            m.pilar = i
            pz['monstruos'].add(m.entity_id)


# ------------------------------------------------------------------------------------------------- al morir
def al_morir(ses, r, c, m):
    """Un bicho del puzle cayo. True si era suyo."""
    pz = c.get('puzle')
    eid = int(m.entity_id)
    if not pz or pz.get('hecho') or eid not in pz['monstruos']:
        return False
    R = _raid()
    pz['monstruos'].discard(eid)
    if pz['tipo'] == 'totems':
        i = getattr(m, 'pilar', None)
        esperado = pz['orden'][len(pz['caidos'])]
        if i != esperado:
            R._cartel(r, 'Wrong order! The pillars resonate and rise again.')
            for s in _vivos(r):
                R.herir(s, m, DANO_FALLO)
            _diferido(1.5, _levantar_pilares, ses, r, c)
            return True
        pz['caidos'].append(i)
        R._cartel(r, 'The %s pillar crumbles. (%d/%d)' % (COLOR[i], len(pz['caidos']), len(pz['orden'])))
        if len(pz['caidos']) == len(pz['orden']):
            resuelto(ses, r, c)
    elif pz['tipo'] == 'sellos':
        i = getattr(m, 'sello', None)
        if i is not None and i not in pz['rotos']:
            pz['rotos'].add(i)
            _quitar_marca(r, c, ('sello', i))
            R._cartel(r, 'A seal shatters! (%d/%d)' % (len(pz['rotos']), len(pz['datos']['casillas'])))
            if len(pz['rotos']) >= len(pz['datos']['casillas']):
                resuelto(ses, r, c)
    return True


def _diferido(segundos, fn, *args):
    try:
        asyncio.get_event_loop().call_later(segundos, fn, *args)
    except RuntimeError:
        fn(*args)


# ------------------------------------------------------------------------------------------------- el bucle
async def _bucle(ses, r, c, pz):
    while not pz.get('hecho') and r.get('corrida') is c and not c.get('fin'):
        await asyncio.sleep(TICK)
        try:
            tic(ses, r, c, time.time())
        except Exception:
            log.exception('raid: puzle %s', pz.get('tipo'))


def tic(ses, r, c, ahora):
    pz = c.get('puzle')
    if not pz or pz.get('hecho'):
        return
    R = _raid()
    vivos = _vivos(r)
    if pz['tipo'] == 'placas':
        casillas = pz['datos']['casillas']
        necesarias = max(1, min(len(casillas), len(vivos)))
        llenas = sum(1 for cas in casillas if any(_distancia(s, cas) <= RADIO_PLACA for s in vivos))
        if llenas != pz['ultimas']:
            pz['ultimas'] = llenas
            if llenas:
                R._cartel(r, 'Light Altars active: %d/%d' % (min(llenas, necesarias), necesarias))
        if llenas >= necesarias:
            if pz['llenas_desde'] is None:
                pz['llenas_desde'] = ahora
            elif ahora - pz['llenas_desde'] >= pz['datos'].get('segundos', 3):
                resuelto(ses, r, c)
        else:
            pz['llenas_desde'] = None
    elif pz['tipo'] == 'totems':
        if ahora >= pz.get('proxima_pista', 0):
            pz['proxima_pista'] = ahora + 30
            for pista in pistas(pz['orden']):
                R._cartel(r, pista)
    elif pz['tipo'] == 'antorcha':
        _tic_antorcha(ses, r, c, pz, vivos, ahora)


def _tic_antorcha(ses, r, c, pz, vivos, ahora):
    R = _raid()
    d = pz['datos']
    portador = pz.get('portador')
    if portador is not None and (portador not in vivos or ahora > pz['hasta']):
        R._cartel(r, 'The flame went out! Take it again from the Flame Altar.')
        pz['portador'] = None
        portador = None
    if portador is None:
        for s in vivos:
            if _distancia(s, d['origen']) <= RADIO_ALTAR:
                pz['portador'] = s
                pz['hasta'] = ahora + d.get('segundos', 45)
                pz['proximo_acoso'] = ahora + CADA_ACOSO / 2
                R._marcar(s, d.get('segundos', 45))
                R._cartel(r, '%s carries the flame! %d seconds to reach the Fire Altar.'
                          % (R._nombre(s), d.get('segundos', 45)))
                break
        return
    if _distancia(portador, d['destino']) <= RADIO_ALTAR:
        pz['entregas'] += 1
        pz['portador'] = None
        R._cartel(r, 'The Fire Altar burns brighter! (%d/%d)' % (pz['entregas'], d['entregas']))
        if pz['entregas'] >= d['entregas']:
            resuelto(ses, r, c)
        return
    if ahora >= pz['proximo_acoso'] and d.get('acosadores'):
        pz['proximo_acoso'] = ahora + CADA_ACOSO
        x, y = R._casilla(portador)
        for k in range(2):
            m = R._sacar_bicho(ses, random.choice(d['acosadores']), (x + (2 if k else -2), y + 2), r, c)
            if m is not None:
                m.agro = 10
                m.en_combate_con = portador.personaje.entity_id
                pz['monstruos'].add(m.entity_id)


# ------------------------------------------------------------------------------------------------- resuelto
def resuelto(ses, r, c):
    pz = c.get('puzle')
    if not pz or pz.get('hecho'):
        return
    R = _raid()
    pz['hecho'] = True
    for clave in list(pz['marcas']):
        _quitar_marca(r, c, clave)
    for eid in list(pz['monstruos']):
        R._quitar(r, eid)
    pz['monstruos'] = set()
    segundos = int(time.time() - pz['inicio'])
    R._cartel(r, 'The barrier falls! (%d:%02d)' % divmod(segundos, 60))
    vivos = _vivos(r)
    R._sacar_jefe(vivos[0] if vivos else ses, r, c)


def terminar(r, c):
    """La zona se acaba o la raid se deshace: fuera marcas y bichos del puzle, sin sacar al jefe."""
    pz = (c or {}).get('puzle')
    if not pz:
        return
    pz['hecho'] = True
    for clave in list(pz['marcas']):
        _quitar_marca(r, c, clave)
    for eid in list(pz['monstruos']):
        _raid()._quitar(r, eid)
    pz['monstruos'] = set()


def cerca_de(casilla, s, radio):
    return math.dist(_raid()._casilla(s), tuple(casilla)) <= radio
