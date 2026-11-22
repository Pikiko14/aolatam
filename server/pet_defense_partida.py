"""Pet Defense, fase 2 (21/11/2026): la partida jugable. Las torres son las de pet_defense.py; aqui va lo demas.

* EL MAPA: el 45, Training Cave(small) (plantillas/pet_defense.json, "mapa"), que nadie usaba: una cueva con un camino
  largo en zigzag. Cada jugador tiene su propia copia (plantillas/instancias.json: dinamica, individual). El CAMINO es el
  mas corto por casillas pisables (transitable.bin) del portal al cristal; los ESPACIOS para torres salen solos a los
  lados del camino, uno cada "separacion_espacios" casillas, y se marcan con un NPC ("npc_espacio") que se clica.
* LA PARTIDA: /pd start lleva al jugador junto al cristal; al cargar el mapa (al_entrar) salen el cristal y los
  espacios, y a los "pausa_inicial" segundos la primera oleada. Cada oleada sale del portal de uno en uno y camina por
  el camino (los mueve esto, no la IA de monstruos: app la salta con m.pet_defense). Al llegar al cristal le quitan su
  "dano_cristal" y desaparecen. Al morir (los mate una torre o el heroe) dan su Essence, sin EXP ni botin.
* ESSENCE: clic en un espacio libre = construir la torre elegida (/pd tipo <guardian|arquero|fuego>) si alcanza; clic
  en el espacio de una torre = mejorarla (coste x nivel nuevo, hasta "nivel_maximo").
* FIN: victoria al acabar con la ultima oleada; derrota si el cristal llega a 0. Tambien acaba (abandono) si el jugador
  sale del mapa o se desconecta. El resultado queda en partida.resultado (puntos, oleadas, tiempo) para el ranking de
  la fase 4; por ahora se avisa en el chat.

Lo de las fases 3 (ventanas propias) y 4 (ranking, temporadas, premios) se apoya en esto.
"""
import collections
import logging
import time

import pet_defense as pd

log = logging.getLogger('pet_defense')

_PARTIDAS = {}                    # sesion -> Partida
_CAMINOS = {}                     # (stage, portal, cristal) -> [casillas]


# ---------------------------------------------------------------------------------------------------------------------
# El mapa: camino y espacios
# ---------------------------------------------------------------------------------------------------------------------
def camino(stage, desde, hasta):
    """Las casillas del camino mas corto de desde a hasta (las dos incluidas), en 8 direcciones sin cortar esquinas.
    BFS sin tope (transitable.camino corta a las 4096 casillas y la cueva tiene 6480)."""
    import transitable
    clave = (int(stage), tuple(desde), tuple(hasta))
    if clave in _CAMINOS:
        return _CAMINOS[clave]
    pisa = lambda x, y: transitable.se_pisa(stage, x, y)
    desde, hasta = tuple(desde), tuple(hasta)
    prev = {desde: None}
    cola = collections.deque([desde])
    while cola:
        a = cola.popleft()
        if a == hasta:
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            n = (a[0] + dx, a[1] + dy)
            if n in prev or not pisa(*n):
                continue
            if dx and dy and not (pisa(a[0] + dx, a[1]) and pisa(a[0], a[1] + dy)):
                continue
            prev[n] = a
            cola.append(n)
    if hasta not in prev:
        _CAMINOS[clave] = []
        return []
    ruta, c = [], hasta
    while c is not None:
        ruta.append(c)
        c = prev[c]
    _CAMINOS[clave] = ruta[::-1]
    return _CAMINOS[clave]


def espacios(stage, ruta, separacion, distancia):
    """Las casillas para torres: una cada `separacion` casillas del camino, a `distancia` de el hacia un lado (alterno),
    pisable y sin pisar el camino. Se salta el principio y el final (ni en el portal ni encima del cristal)."""
    import transitable
    en_camino = set(ruta)
    cerca = {(x + dx, y + dy) for x, y in ruta for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    out, lado = [], 1
    for i in range(separacion // 2, len(ruta) - separacion // 2, separacion):
        x, y = ruta[i]
        ax, ay = ruta[max(0, i - 2)]
        bx, by = ruta[min(len(ruta) - 1, i + 2)]
        dx, dy = bx - ax, by - ay                       # direccion del camino; la perpendicular es (-dy, dx)
        px, py = (-dy > 0) - (-dy < 0), (dx > 0) - (dx < 0)
        for s in (lado, -lado):
            for d in range(distancia, distancia + 3):
                t = (x + px * s * d, y + py * s * d)
                if t not in cerca and t not in en_camino and transitable.se_pisa(stage, *t) and t not in out:
                    out.append(t)
                    break
            else:
                continue
            break
        lado = -lado
    return out


# ---------------------------------------------------------------------------------------------------------------------
# La partida
# ---------------------------------------------------------------------------------------------------------------------
class Partida:
    def __init__(self, ses, cfg, ahora):
        mp, pt = cfg['mapa'], cfg['partida']
        self.ses, self.cfg = ses, cfg
        self.stage = int(mp['stage'])
        self.ruta = camino(self.stage, mp['portal'], mp['cristal'])
        self.espacios = espacios(self.stage, self.ruta, int(mp.get('separacion_espacios', 20)),
                                 int(mp.get('distancia_espacio', 3)))
        self.vida = self.vida_max = int(pt.get('vida_cristal', 20))
        self.essence = int(pt.get('essence_inicial', 100))
        self.oleada = 0                     # la que esta en marcha (1..N); 0 antes de la primera
        self.cola = []                      # [(tipo, datos)] que faltan por salir de la oleada en curso
        self.proxima_salida = 0.0
        self.proxima_oleada = ahora + float(pt.get('pausa_inicial', 15))
        self.enemigos = {}                  # entidad -> Monstruo vivo de la partida
        self.torres = {}                    # indice de espacio -> Torre
        self.npc_espacio = {}               # entidad del NPC -> indice de espacio
        self.npc_cristal = None
        self.inicio = ahora
        self.muertos = 0
        self.fugados = 0
        self.resultado = None

    @property
    def total_oleadas(self):
        return len(self.cfg.get('oleadas') or [])


def partida(ses):
    return _PARTIDAS.get(ses)


def _aviso(ses, texto):
    import clases
    try:
        (getattr(ses, 'enviar_sin_espejo', None) or ses.enviar)(clases.aviso(texto, tipo=0))
    except Exception:
        log.debug('aviso pet defense', exc_info=True)


def _estado(pa):
    return 'Crystal %d/%d  |  Wave %d/%d  |  Essence %d' % (pa.vida, pa.vida_max, pa.oleada, pa.total_oleadas, pa.essence)


def empezar(ses, addr='?'):
    """/pd start: lleva al jugador al mapa de Pet Defense; la partida arranca al cargarlo (al_entrar)."""
    import app
    cfg = pd.config()
    mp = cfg.get('mapa') or {}
    if not getattr(ses, 'personaje', None):
        return 'no character in world yet'
    if not camino(int(mp['stage']), mp['portal'], mp['cristal']):
        return 'Pet Defense: no path from the portal to the crystal on map %s' % mp.get('stage')
    terminar(ses, 'abandono', avisar=False)
    ses._pd_pendiente = True
    app._viajar_por_portal(ses, addr, {'destino': int(mp['stage']), 'llegada': tuple(mp['llegada'])}, motivo='a Pet Defense')
    return 'Pet Defense: going to %s' % mp.get('nombre', mp['stage'])


def al_entrar(ses, addr='?'):
    """El jugador cargo un mapa. En el de Pet Defense: arranca la partida si venia a eso, y si no, fuera."""
    import app
    cfg = pd.config()
    mp = cfg.get('mapa') or {}
    p = getattr(ses, 'personaje', None)
    if not p or int(getattr(p, 'stage', 0) or 0) != int(mp.get('stage', -1)):
        return
    if partida(ses) is not None:
        _dibujar_mapa(partida(ses))                 # recargo el mapa (revivir, etc.): se le vuelve a dibujar todo
        __import__('pet_defense_ui').refrescar(partida(ses), forzar=True)
        return
    if not getattr(ses, '_pd_pendiente', False):
        _aviso(ses, 'Pet Defense: start a game first.')
        st, (x, y) = mp.get('salida', [41, [173, 91]])
        app._sincronizar_cambio_mapa(ses, int(st), int(x), int(y))
        return
    ses._pd_pendiente = False
    pa = _PARTIDAS[ses] = Partida(ses, cfg, time.time())
    _dibujar_mapa(pa)
    pd._arrancar()
    __import__('pet_defense_ui').refrescar(pa, forzar=True)
    log.info('Pet Defense: empieza %s (%d casillas de camino, %d espacios)', p.nombre, len(pa.ruta), len(pa.espacios))
    _aviso(ses, 'Pet Defense! Defend the crystal from %d waves. Click a stone to choose which pet goes there; click '
                'it again to upgrade or sell. First wave in %d s.' % (pa.total_oleadas, int(pa.proxima_oleada - pa.inicio)))
    _aviso(ses, _estado(pa))


def _dibujar_mapa(pa):
    """El cristal y las piedras de los espacios (NPCs de npc.xml, como el Exit Guide de los eventos)."""
    import app
    import combate
    ses, mp = pa.ses, pa.cfg['mapa']
    for eid in [pa.npc_cristal] + list(pa.npc_espacio):
        if eid:
            ses.enviar(combate.despawn_monstruo(eid))
    pa.npc_espacio.clear()
    pa.npc_cristal = _cristal(ses, mp)
    for i, t in enumerate(pa.espacios):
        eid = _npc(ses, int(mp['npc_espacio']), t)
        if eid:
            pa.npc_espacio[eid] = i
    for t in pa.torres.values():
        ses.enviar(*pd.paquetes_spawn(t))
    for m in pa.enemigos.values():
        _mostrar_enemigo(ses, m)


def _cristal(ses, mp):
    """El cristal-base: el de la Holy Battlefield ("que el cristal sea 1 crystal de holybattlefield", 21/11/2026), un
    objeto de mapa con el sprite de los cristales de sus bases (competiciones.CRISTALES: 60368 y 60367), como lo pinta
    holy_battlefield.objeto. Sin 'objeto_cristal', el NPC 'npc_cristal' de antes."""
    import app
    import login
    sprite = mp.get('objeto_cristal')
    if not sprite:
        return _npc(ses, int(mp['npc_cristal']), mp['cristal'])
    eid = app._SIG_GENERADO[0]
    app._SIG_GENERADO[0] += 1
    ses.enviar(login._map_object_spawn(eid, int(sprite), tuple(mp['cristal'])))
    return eid


def _npc(ses, npc_type, tile):
    import app
    eid = app._SIG_GENERADO[0]
    app._SIG_GENERADO[0] += 1
    app._poner_generado(ses, eid, npc_type, tuple(tile), 0)
    return eid


def _mostrar_enemigo(ses, m):
    import combate
    import login
    ses.enviar(login._npc_spawn(m.entity_id, int(m.npc_type), m.nombre, (m.tile_x, m.tile_y),
                                sprite=getattr(m, 'sprite', 0), klass=1),
               combate.atributo(m.entity_id, m.porcentaje))


# ---------------------------------------------------------------------------------------------------------------------
# Torres: construir y mejorar
# ---------------------------------------------------------------------------------------------------------------------
def tipo_elegido(ses):
    cfg = pd.config()
    t = getattr(ses, '_pd_tipo', None)
    return t if t in (cfg.get('torres') or {}) else cfg.get('torre_por_defecto')


def elegir_tipo(ses, tipo):
    torres = pd.config().get('torres') or {}
    tipo = str(tipo or '').lower()
    if tipo not in torres:
        return 'Tower types: %s' % ', '.join('%s (%d)' % (k, int(v.get('coste', 0))) for k, v in torres.items())
    ses._pd_tipo = tipo
    return 'Pet Defense: next tower is %s (%d Essence)' % (torres[tipo].get('nombre', tipo), int(torres[tipo].get('coste', 0)))


def _nombre_tipo(ses):
    return (pd.config()['torres'].get(tipo_elegido(ses)) or {}).get('nombre', tipo_elegido(ses))


def _coste(ses, nivel, tipo=None):
    datos = pd.config()['torres'].get(tipo or tipo_elegido(ses)) or {}
    return int(datos.get('coste', 0)) * max(1, int(nivel))


def pulsar(ses, ent, addr='?'):
    """Clic en una entidad de su partida. Piedra libre: la ventana para elegir que mascota poner (PDElegir); piedra con
    torre: su ficha (PDTorre) para mejorarla o venderla; el cristal: el estado. True si era nuestra."""
    import pet_defense_ui as ui
    pa = partida(ses)
    if pa is None:
        return False
    if int(ent) == pa.npc_cristal:
        _aviso(ses, _estado(pa))
        return True
    i = pa.npc_espacio.get(int(ent))
    if i is None:
        return False
    ses._pd_espacio = i
    ses.enviar(*(ui.ficha_torre(pa, i) if torre_en(pa, i) is not None else ui.elegir(pa, i)))
    return True


def torre_en(pa, i):
    """La torre del espacio i (None si esta libre o se quito)."""
    t = pa.torres.get(i)
    if t is not None and t.entidad not in pd._TORRES:
        pa.torres.pop(i, None)
        t = None
    return t


def construir(pa, i, tipo=None):
    """Pone en el espacio libre i una torre de ese tipo (sin tipo: la elegida con /pd tipo, o mejora la que haya, como
    en la fase 2). Devuelve (ok, texto para el jugador)."""
    ses, cfg = pa.ses, pd.config()
    t = torre_en(pa, i)
    if t is not None:
        if tipo is None:
            return mejorar(pa, i)
        return False, 'There is already a %s here.' % t.datos.get('nombre', t.tipo)
    tipo = tipo or tipo_elegido(ses)
    datos = (cfg.get('torres') or {}).get(tipo)
    if not datos:
        return False, 'Unknown tower.'
    coste = _coste(ses, 1, tipo)
    if pa.essence < coste:
        return False, 'Not enough Essence: %s costs %d (you have %d).' % (datos.get('nombre', tipo), coste, pa.essence)
    pa.essence -= coste
    t = pa.torres[i] = pd.crear(ses, tipo, dict(datos), pa.espacios[i])
    t.gastado = coste
    return True, '%s built (-%d Essence).' % (datos.get('nombre', tipo), coste)


def coste_mejora(t):
    return _coste(None, t.nivel + 1, t.tipo)


def mejorar(pa, i):
    """Sube de nivel (y evoluciona) la torre del espacio i. Devuelve (ok, texto)."""
    ses, cfg = pa.ses, pd.config()
    t = torre_en(pa, i)
    if t is None:
        return False, 'There is no tower here.'
    tope = int(cfg.get('nivel_maximo', 3))
    nombre = t.datos.get('nombre', t.tipo)
    if t.nivel >= tope:
        return False, '%s is already at max level %d.' % (nombre, tope)
    coste = coste_mejora(t)
    if pa.essence < coste:
        return False, 'Not enough Essence: level %d costs %d (you have %d).' % (t.nivel + 1, coste, pa.essence)
    pa.essence -= coste
    t.gastado = getattr(t, 'gastado', 0) + coste
    pd.evolucionar(t, t.nivel + 1)
    _efecto_mejora(ses, t)
    return True, '%s is now level %d (-%d Essence).' % (nombre, t.nivel, coste)


def vender(pa, i):
    """Quita la torre del espacio i y devuelve venta_reembolso de lo gastado en ella. Devuelve (ok, texto)."""
    import mascotas
    t = torre_en(pa, i)
    if t is None:
        return False, 'There is no tower here.'
    vuelta = int(getattr(t, 'gastado', 0) * float(pd.config().get('venta_reembolso', 0.5)))
    pa.essence += vuelta
    pa.torres.pop(i, None)
    pd._TORRES.pop(t.entidad, None)
    pd._mandar_al_mapa(t.stage, mascotas.quitar(t.entidad), extra=pa.ses)
    return True, '%s sold (+%d Essence).' % (t.datos.get('nombre', t.tipo), vuelta)


def _efecto_mejora(ses, t):
    """El "Level N" del totem de la Totem War (efecto 0x0020) sobre la torre mejorada."""
    import struct
    try:
        import totem_war
        n = totem_war.efecto_de_nivel(t.nivel)
        if n is not None:
            ses.enviar(struct.pack('<HIHI', 0x0020, t.entidad, int(n) & 0xFFFF, t.entidad))
    except Exception:
        log.debug('efecto de mejora', exc_info=True)


# ---------------------------------------------------------------------------------------------------------------------
# Oleadas
# ---------------------------------------------------------------------------------------------------------------------
def _sacar_enemigo(pa, tipo, datos, ahora):
    import app
    ses = pa.ses
    eid = app._SIG_GENERADO[0]
    app._SIG_GENERADO[0] += 1
    portal = pa.ruta[0]
    npc_type = aspecto(pa, tipo, datos)
    m = app._poner_generado(ses, eid, npc_type, portal, 0)
    if m is None:
        log.warning('Pet Defense: no salio el enemigo %s (%s)', tipo, npc_type)
        return None
    if tipo == 'jefe':
        _aviso(ses, 'BOSS: %s appears!' % m.nombre)
    k = 1.0 + float(pa.cfg['partida'].get('hp_por_oleada', 0.15)) * (pa.oleada - 1)
    m.hp_max = m.hp = max(1, int(int(datos.get('hp', 100)) * k))
    m.defensa, m.mdef = int(datos.get('defensa', 0)), int(datos.get('mdef', 0))
    m.atk = m.matk = 0
    m.pet_defense = True                      # app salta su IA y su muerte normal (sin EXP ni botin)
    m.pd_tipo, m.pd_datos = tipo, datos
    m.pd_indice = 0
    m.pd_llega = ahora + 0.5
    m.pd_partida = pa
    pa.enemigos[eid] = m
    ses.enviar(__import__('combate').atributo(eid, m.porcentaje))
    return m


def aspecto(pa, tipo, datos):
    """El npc_type (el aspecto) de un enemigo: el jefe, el de su oleada en la lista; los demas, uno al azar de la suya
    ("que los mob normales varien, siempre sale el mismo", 21/11/2026). Sin lista, su npc_type."""
    import random
    lista = datos.get('npc_types') or []
    if not lista:
        return int(datos['npc_type'])
    if tipo == 'jefe':
        return int(lista[(max(1, pa.oleada) - 1) % len(lista)])
    return int(random.choice(lista))


def _empezar_oleada(pa, ahora):
    pa.oleada += 1
    ol = pa.cfg['oleadas'][pa.oleada - 1]
    cola, jefes = [], []
    for tipo, n in ol.get('enemigos') or ():
        datos = pa.cfg['enemigos'].get(tipo)
        if datos:
            (jefes if tipo == 'jefe' else cola).extend([(tipo, datos)] * int(n))
    # Un jefe al final de cada oleada ("al final de cada wave salga un jefe", 21/11/2026)
    if not jefes and pa.cfg.get('jefe_cada_oleada') and pa.cfg['enemigos'].get('jefe'):
        jefes = [('jefe', pa.cfg['enemigos']['jefe'])]
    # Mezclados por tipos, en el orden de la oleada pero alternando (no todos los rapidos al final)
    grupos = collections.OrderedDict()
    for c in cola:
        grupos.setdefault(c[0], []).append(c)
    pa.cola = []
    while any(grupos.values()):
        for g in grupos.values():
            if g:
                pa.cola.append(g.pop(0))
    pa.cola += jefes                                   # los jefes, los ultimos
    pa.proxima_salida = ahora
    jefe = any(t == 'jefe' for t, _ in pa.cola)
    _aviso(pa.ses, 'Wave %d/%d: %d enemies%s!' % (pa.oleada, pa.total_oleadas, len(pa.cola), ', BOSS incoming' if jefe else ''))


def _mover(pa, m, ahora):
    """El siguiente tramo recto del camino (hasta casillas_por_paso casillas en la misma direccion)."""
    import app
    import combate
    from codec import Msg
    if ahora < m.pd_llega:
        return
    ruta = pa.ruta
    i = m.pd_indice
    if i >= len(ruta) - 1:
        _llega_al_cristal(pa, m)
        return
    pasos_max = int(pa.cfg['partida'].get('casillas_por_paso', 3))
    d = (ruta[i + 1][0] - ruta[i][0], ruta[i + 1][1] - ruta[i][1])
    j = i + 1
    while j < len(ruta) - 1 and j - i < pasos_max and (ruta[j + 1][0] - ruta[j][0], ruta[j + 1][1] - ruta[j][1]) == d:
        j += 1
    (x0, y0), (x1, y1) = ruta[i], ruta[j]
    vel = int(m.pd_datos.get('velocidad', 45))
    if ahora < getattr(m, 'lento_hasta', 0):
        vel = max(5, vel // 2)
    pk = Msg.registry[(0x0005, 's2c', '*')].build(entity_id=m.entity_id, cur_x=x0 * 32, cur_y=y0 * 32,
                                                    dst_x=x1 * 32, dst_y=y1 * 32, speed=vel)
    pa.ses.enviar(pk)
    m.pd_indice = j
    m.tile_x, m.tile_y = x1, y1
    m.tile = [x1, y1]
    m.pd_llega = ahora + combate.segundos_de_tramo(max(abs(x1 - x0), abs(y1 - y0)), vel)


def _quitar_enemigo(pa, m):
    import combate
    pa.enemigos.pop(m.entity_id, None)
    bichos = getattr(pa.ses, 'monstruos', None)
    if isinstance(bichos, dict):
        bichos.pop(m.entity_id, None)
    m.vivo = False
    try:
        pa.ses.enviar(combate.despawn_monstruo(m.entity_id))
    except Exception:
        log.debug('despawn pet defense', exc_info=True)


def _llega_al_cristal(pa, m):
    import combate
    dano = int(m.pd_datos.get('dano_cristal', 1))
    pa.vida = max(0, pa.vida - dano)
    pa.fugados += 1
    _quitar_enemigo(pa, m)
    if pa.npc_cristal:
        pa.ses.enviar(combate.numero_flotante(pa.npc_cristal, dano))
    _aviso(pa.ses, 'A %s reached the crystal! (-%d)  %s' % (m.nombre, dano, _estado(pa)))
    if pa.vida <= 0:
        terminar(pa.ses, 'derrota')


def al_morir(ses, m):
    """Desde app._procesar_muerte_monstruo: un enemigo de Pet Defense murio (torre o heroe). Da su Essence, sin EXP ni
    botin, y desaparece. True si era de Pet Defense."""
    pa = getattr(m, 'pd_partida', None)
    if not getattr(m, 'pet_defense', False):
        return False
    if pa is None or pa.resultado is not None or m.entity_id not in pa.enemigos:
        return True
    ganada = int(m.pd_datos.get('essence', 0))
    pa.essence += ganada
    pa.muertos += 1
    import combate
    ses_p = pa.ses
    ses_p.enviar(combate.atributo(m.entity_id, 0))
    pa.enemigos.pop(m.entity_id, None)
    try:
        import asyncio
        asyncio.get_running_loop().call_later(1.0, _quitar_enemigo, pa, m)
    except RuntimeError:
        _quitar_enemigo(pa, m)
    if m.pd_tipo == 'jefe':
        _aviso(ses_p, 'The boss is down! (+%d Essence)' % ganada)
    return True


def tick_partida(pa, ahora):
    if pa.resultado is not None:
        return
    ses = pa.ses
    p = getattr(ses, 'personaje', None)
    if getattr(ses, 'cerrada', False) or getattr(ses, 'desconectado', False) or p is None \
            or int(getattr(p, 'stage', 0) or 0) != pa.stage:
        terminar(ses, 'abandono', avisar=False)
        return
    if getattr(ses, 'mapa_cargando', False):
        return
    pt = pa.cfg['partida']
    # Siguiente oleada
    if not pa.cola and not pa.enemigos and 0.0 < pa.proxima_oleada <= ahora:
        if pa.oleada >= pa.total_oleadas:
            terminar(ses, 'victoria')
            return
        _empezar_oleada(pa, ahora)
    # Salen los de la cola, de uno en uno
    if pa.cola and ahora >= pa.proxima_salida:
        tipo, datos = pa.cola.pop(0)
        _sacar_enemigo(pa, tipo, datos, ahora)
        pa.proxima_salida = ahora + float(pt.get('separacion_enemigos', 1.2))
        if not pa.cola:
            pa.proxima_oleada = 0.0      # se marca al vaciarse el mapa
    for m in list(pa.enemigos.values()):
        if m.hp <= 0 or not getattr(m, 'vivo', True):
            continue
        _mover(pa, m, ahora)
        if pa.resultado is not None:
            return
    # Oleada limpia: pausa antes de la siguiente
    if not pa.cola and not pa.enemigos and pa.proxima_oleada == 0.0:
        if pa.oleada >= pa.total_oleadas:
            terminar(ses, 'victoria')
            return
        pa.proxima_oleada = ahora + float(pt.get('pausa_entre_oleadas', 10))
        extra = sum(t.essence_por_oleada for t in pa.torres.values() if t.entidad in pd._TORRES)
        pa.essence += extra
        _aviso(ses, 'Wave %d cleared!%s Next wave in %d s.  %s' % (
            pa.oleada, (' Your towers give +%d Essence.' % extra) if extra else '',
            int(pt.get('pausa_entre_oleadas', 10)), _estado(pa)))
    if pa.resultado is None:
        __import__('pet_defense_ui').refrescar(pa, ahora)


def saltar_pausa(pa, ahora=None):
    """Next wave now: si esta en la pausa entre oleadas (o antes de la primera), la siguiente sale ya. True si salto."""
    ahora = time.time() if ahora is None else ahora
    if pa.resultado is None and not pa.cola and not pa.enemigos and pa.proxima_oleada > ahora:
        pa.proxima_oleada = ahora
        return True
    return False


def puntos(pa, ahora=None):
    """Oleadas x 1000 + vida del cristal x 200 + bonus de tiempo (hasta 2000), x1,5 si gana."""
    ahora = time.time() if ahora is None else ahora
    superadas = pa.oleada if pa.resultado == 'victoria' else max(0, pa.oleada - 1)
    segundos = max(0, int(ahora - pa.inicio))
    bonus = max(0, 2000 - segundos) if pa.resultado == 'victoria' else 0
    total = superadas * 1000 + pa.vida * 200 + bonus
    return int(total * (1.5 if pa.resultado == 'victoria' else 1.0)), superadas, segundos


def terminar(ses, resultado, avisar=True):
    """Acaba la partida de ses (victoria, derrota o abandono): quita enemigos, torres, cristal y piedras."""
    import combate
    pa = _PARTIDAS.pop(ses, None)
    if pa is None:
        return None
    pa.resultado = resultado
    total, superadas, segundos = puntos(pa)
    pa.resultado_datos = {'resultado': resultado, 'puntos': total, 'oleadas': superadas, 'segundos': segundos,
                          'muertos': pa.muertos, 'fugados': pa.fugados}
    for m in list(pa.enemigos.values()):
        _quitar_enemigo(pa, m)
    pd.quitar(ses)
    for eid in [pa.npc_cristal] + list(pa.npc_espacio):
        if eid:
            try:
                ses.enviar(combate.despawn_monstruo(eid))
            except Exception:
                pass
    log.info('Pet Defense: %s termina (%s) %s', getattr(getattr(ses, 'personaje', None), 'nombre', '?'), resultado,
             pa.resultado_datos)
    try:
        __import__('pet_defense_ui').fin(pa)
    except Exception:
        log.exception('Pet Defense: ventana del final')
    if avisar:
        titulo = {'victoria': 'VICTORY!', 'derrota': 'DEFEAT... the crystal fell.'}.get(resultado, 'Game over.')
        _aviso(ses, 'Pet Defense - %s Waves: %d/%d, crystal %d/%d, time %d:%02d, score %d.' % (
            titulo, superadas, pa.total_oleadas, pa.vida, pa.vida_max, segundos // 60, segundos % 60, total))
    return pa


def tick(ahora=None):
    ahora = time.time() if ahora is None else ahora
    for pa in list(_PARTIDAS.values()):
        try:
            tick_partida(pa, ahora)
        except Exception:
            log.exception('Pet Defense: tick de la partida')


def hay_partidas():
    return bool(_PARTIDAS)
