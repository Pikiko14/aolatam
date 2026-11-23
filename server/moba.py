"""Angel MOBA (23/11/2026): "podemos crear un evento de moba?" ... "aplica todo lo que me dices".

FASE 2b: la inscripcion a horas fijas y la ventana para elegir clase (moba_lobby.py), partidas de 5 contra 5 que
comparten el mapa (presencia.clave_de_mapa), PvP entre heroes (marcas) y sin objetos (app).

FASE 1: el mapa con sus tres carriles, las oleadas de subditos, las torres y los nucleos, que ya pelean entre
si y contra los jugadores. Se prueba con el GM: /moba start (te mete en el equipo Jiabli en una copia del mapa) y
/moba stop. Las fases siguientes: equipos de 5 con inscripcion a horas fijas, nivel 1-18 y clase elegida con sus 3
poderes y su ultimate, jungla, marcador, premios y ranking.

* EL MAPA: el 918 "Angel MOBA" (tools/mapa_moba.py). Las bases en esquinas opuestas: Jiabli (equipo 1) abajo a la
  izquierda, Raphael (equipo 2) arriba a la derecha (plantillas/moba.json).
* LAS UNIDADES son monstruos (combate.Monstruo) con m.moba: subditos, torres y nucleos, con los guardianes y las
  estatuas del Holy Battlefield. Su IA normal no corre (app la salta con m.moba) salvo cuando pelean con un jugador
  (m.moba_jugador): entonces la lleva la IA de monstruos de siempre, que ya sabe pegar a jugadores (defensas,
  esquivas, escudos, muerte). Contra otras unidades pelea este modulo.
* LOS SUBDITOS salen de cada nucleo por los tres carriles cada 'cada' segundos. Andan por su carril hacia la base
  enemiga; si ven (vision) una unidad enemiga van a por ella y le pegan; si no, a un jugador enemigo (lo lleva la IA,
  hasta 'persecucion' casillas de su carril); si no, siguen andando.
* LAS TORRES pegan a la unidad enemiga mas cercana a su alcance y, si no hay, al jugador enemigo mas cercano.
* EL NUCLEO no pega; si cae, gana el otro equipo.
* QUIEN PEGA A QUIEN: holy_battlefield.puede_atacar pregunta a puede_atacar de aqui; un jugador no puede pegar a las
  unidades de su equipo.
"""
import asyncio
import json
import logging
import pathlib
import random
import time

log = logging.getLogger('moba')

CONFIG = pathlib.Path(__file__).parent / 'plantillas' / 'moba.json'
TICK = 0.2
_CFG = [None, 0.0]
_PARTIDAS = {}              # id -> Partida
_DE_SESION = {}             # sesion -> Partida
_TAREA = [None]


def config() -> dict:
    try:
        mt = CONFIG.stat().st_mtime
    except OSError:
        return _CFG[0] or {}
    if _CFG[0] is None or mt != _CFG[1]:
        _CFG[0], _CFG[1] = json.loads(CONFIG.read_text(encoding='utf-8')), mt
    return _CFG[0]


# ---------------------------------------------------------------------------------------------- carriles
_RUTAS = {}


def ruta(carril, equipo):
    """Las casillas del carril de la base del `equipo` a la enemiga: el camino por casillas pisables entre sus puntos."""
    import pet_defense_partida as pp
    cfg = config()
    clave = (carril, int(equipo), json.dumps(cfg['carriles'][carril]))
    if clave not in _RUTAS:
        st = int(cfg['mapa']['stage'])
        puntos = [tuple(p) for p in cfg['carriles'][carril]]
        if int(equipo) == 2:
            puntos = puntos[::-1]
        out = []
        for a, b in zip(puntos, puntos[1:]):
            tramo = pp.camino(st, a, b)
            if not tramo:
                raise ValueError('carril %s: sin camino de %s a %s' % (carril, a, b))
            out += tramo if not out else tramo[1:]
        _RUTAS[clave] = out
    return _RUTAS[clave]


def _dist(a, b):
    return max(abs(int(a[0]) - int(b[0])), abs(int(a[1]) - int(b[1])))


# ---------------------------------------------------------------------------------------------- la partida
class Partida:
    def __init__(self, pid, ahora):
        self.id = pid
        self.cfg = config()
        self.stage = int(self.cfg['mapa']['stage'])
        self.jugadores = {}            # sesion -> equipo
        self.unidades = {}             # entidad -> Monstruo
        self.proxima_oleada = ahora + float(self.cfg['oleadas'].get('primera', 15))
        self.cola = []                 # [(cuando, equipo, carril)] subditos por salir
        self.resultado = None
        self.inicio = ahora
        self.montada = False
        self.heroes = {}               # sesion -> moba_heroe.Heroe
        self.clases = {}               # sesion -> clase elegida (hasta que entra)
        self.bajas = {}                # equipo -> heroes enemigos abatidos
        jg = self.cfg.get('jungla') or {}
        self.jungla_proxima = {i: ahora + float(jg.get('primera', 20)) for i in range(len(jg.get('campamentos') or []))}
        self.jefe_proximo = ahora + float((self.cfg.get('jefe') or {}).get('primera', 120))
        self.buffs = {}                # equipo -> (hasta, {'ataque': x, 'defensa': y})
        self._hud = {}                 # sesion -> lo ultimo que se le mando
        self._proximo_hud = 0.0

    def sesiones(self):
        return [s for s in self.jugadores if getattr(s, 'personaje', None) is not None]


def partida_de(ses):
    try:
        return _DE_SESION.get(ses)
    except TypeError:                        # una sesion que no sirve de clave (las de mentira de algunos tests)
        return None


def equipo_de(ses):
    pa = partida_de(ses)
    return pa.jugadores.get(ses) if pa else None


def _mandar(pa, *pk):
    for s in pa.sesiones():
        try:
            (getattr(s, 'enviar_sin_espejo', None) or s.enviar)(*pk)
        except Exception:
            log.debug('moba: mandar', exc_info=True)


NEUTRALES = ('grande', 'pequeno', 'jefe')
ESTATUAS = ('torre', 'nucleo')
RAYO_MAGIA, RAYO_EFECTO, RAYO_MS = 283, 7, 350     # Thunder Strike V (magic.xml; el efecto 7 esta en shape/magic)


def rayo(pa, m, blanco_para):
    """Las estatuas disparan un rayo al blanco, visible para todos ("que lance algun rayo, no se ve el efecto de
    ataque", 23/11/2026): el lanzamiento ahora y el impacto a los RAYO_MS. blanco_para(visor) -> la entidad del
    blanco para ese visor. False si m no es una estatua."""
    if getattr(m, 'moba_tipo', None) not in ESTATUAS:
        return False
    import combate as cb
    import moba_heroe

    def _pk(v, cierre=False):
        b = blanco_para(v)
        if cierre:
            return (cb.cierre_de_dano(m.entity_id, b, ataque=RAYO_MAGIA, efecto=RAYO_EFECTO, es_magia=True),)
        return (cb.numero_de_dano(m.entity_id, b, 0, ataque=RAYO_MAGIA, efecto=RAYO_EFECTO, cast_time=RAYO_MS,
                                  es_magia=True),)
    moba_heroe.difundir(pa, _pk)
    _despues(RAYO_MS / 1000.0, lambda: moba_heroe.difundir(pa, lambda v: _pk(v, True)))
    return True


def datos_de(pa, tipo):
    """Los numeros de ese tipo de unidad: subdito, torre, nucleo (arriba en moba.json), grande y pequeno (jungla) o jefe."""
    if tipo in ('grande', 'pequeno'):
        return pa.cfg['jungla'][tipo]
    return pa.cfg[tipo]


def _nueva_unidad(pa, tipo, equipo, tile, carril=None, npc=None):
    """Una unidad del MOBA, metida en los monstruos de todos los de la partida y dibujada."""
    import app
    import combate
    import login
    cfg = pa.cfg
    if npc is None:
        eq = cfg['equipos'][str(equipo)]
        npc = int(eq[{'subdito': 'npc_subdito', 'torre': 'npc_torre', 'nucleo': 'npc_nucleo'}[tipo]])
    datos = datos_de(pa, tipo)
    eid = app._SIG_GENERADO[0]
    app._SIG_GENERADO[0] += 1
    nombre, sprite = app._monstruo_bd(npc)
    m = combate.Monstruo(eid, npc, nombre, list(tile), sprite, stage=pa.stage)
    m.generado = True
    m.moba, m.moba_tipo, m.moba_equipo, m.moba_carril, m.moba_partida = True, tipo, int(equipo), carril, pa
    m.moba_jugador = False
    m.hp_max = m.hp = int(datos.get('hp', 1000))
    m.defensa = m.mdef = int(datos.get('defensa', 0))
    m.atk = int(datos.get('ataque', 0))
    m.var = max(1, m.atk // 10)
    m.matk = 0
    m.atk_range = int(datos.get('alcance', 1))
    m.agro = 0
    m.moba_proximo = 0.0
    m.moba_llega = 0.0
    m.moba_casa, m.moba_blanco, m.moba_campamento = (int(tile[0]), int(tile[1])), None, None
    if tipo == 'subdito':
        m.moba_ruta = ruta(carril, equipo)
        m.moba_i = 0
        m.move_speed = int(datos.get('velocidad', 45))
    else:
        m.move_speed = m.move_range = 0
        m.es_estatico = True
    pa.unidades[eid] = m
    for s in pa.sesiones():
        if getattr(s, 'monstruos', None) is None:
            s.monstruos = {}
        s.monstruos[eid] = m
    m.compartido = True
    _mandar(pa, login._npc_spawn(eid, npc, nombre, tuple(tile), sprite=sprite, klass=1),
            combate.atributo(eid, m.porcentaje))
    return m


def montar(pa):
    """Los nucleos y las torres de los dos equipos."""
    cfg = pa.cfg
    for eq in ('1', '2'):
        _nueva_unidad(pa, 'nucleo', int(eq), cfg['equipos'][eq]['nucleo'])
        for carril, t in posiciones_torres(int(eq)):
            _nueva_unidad(pa, 'torre', int(eq), t, carril)
    pa.montada = True                  # sin esto el reloj (tick) se salta la partida: ni subditos ni jungla


def posiciones_torres(equipo):
    """[(carril, casilla)] de las torres de un equipo: en cada carril, una en cada fraccion de su recorrido desde su
    base ('torres': {'fracciones': [interior, exterior]})."""
    out = []
    for carril in config()['carriles']:
        r = ruta(carril, equipo)
        for f in (config().get('torres') or {}).get('fracciones', (0.15, 0.32)):
            out.append((carril, r[min(len(r) - 1, int(len(r) * float(f)))]))
    return out


def _redibujar(pa, ses):
    """Quien entra (o recarga el mapa) ve todas las unidades vivas."""
    import combate
    import login
    if getattr(ses, 'monstruos', None) is None:
        ses.monstruos = {}
    for eid, m in pa.unidades.items():
        ses.monstruos[eid] = m
        ses.enviar(login._npc_spawn(eid, int(m.npc_type), m.nombre, (int(m.tile_x), int(m.tile_y)),
                                    sprite=getattr(m, 'sprite', 0), klass=1),
                   combate.atributo(eid, m.porcentaje))


# ---------------------------------------------------------------------------------------------- combate entre unidades
def puede_atacar(ses, objetivo):
    """Un jugador del MOBA no puede pegar a las unidades de su equipo (lo pregunta holy_battlefield.puede_atacar)."""
    if not getattr(objetivo, 'moba', False):
        return True
    eq = equipo_de(ses)
    return eq is not None and int(eq) != int(getattr(objetivo, 'moba_equipo', 0))


def _enemigos(pa, m):
    """Las unidades enemigas de m (las neutrales de la jungla no son de nadie: ni pegan ni reciben de las demas)."""
    if not m.moba_equipo:
        return []
    return [u for u in pa.unidades.values()
            if u.moba_equipo and u.moba_equipo != m.moba_equipo and u.hp > 0 and getattr(u, 'vivo', True)]


def _jugadores_enemigos(pa, m):
    out = []
    for s, eq in pa.jugadores.items():
        p = getattr(s, 'personaje', None)
        if (p is None or int(eq) == int(m.moba_equipo) or getattr(s, 'muerto', False) or getattr(p, 'hp', 1) <= 0
                or int(getattr(p, 'stage', 0) or 0) != pa.stage):
            continue
        out.append(s)
    return out


def _cercano(m, cosas, posicion, alcance):
    mejor = None
    for c in cosas:
        d = _dist((m.tile_x, m.tile_y), posicion(c))
        if d <= alcance and (mejor is None or d < mejor[0]):
            mejor = (d, c)
    return mejor


def golpear(pa, m, u, ahora):
    """m pega a la unidad u (el dano de m contra la defensa de u, con la misma curva que los monstruos)."""
    import combate
    m.moba_proximo = ahora + float(datos_de(pa, m.moba_tipo).get('cadencia', 1.2))
    base = max(1, int(m.atk * random.uniform(0.9, 1.1)))
    dano = max(1, int(base * 420 / (max(0, int(u.defensa)) + 420)))
    hecho = u.recibir_extra(dano)
    if not rayo(pa, m, lambda v: u.entity_id):
        _mandar(pa, combate.ataque(m.entity_id, u.entity_id, combate.anim_de_monstruo(m.nombre)))
    _mandar(pa, combate.numero_flotante(u.entity_id, hecho or dano),
            combate.atributo(u.entity_id, u.porcentaje if u.hp > 0 else 0))
    if u.hp <= 0:
        muere(pa, u, None)


def _pelear_con_jugador(m, s):
    """La IA de monstruos de siempre se encarga: el objetivo es ese jugador."""
    m.moba_jugador = True
    m.en_combate_con = s.personaje.entity_id
    m.agro = max(1, int(m.atk_range))


def _soltar_jugador(m):
    m.moba_jugador = False
    m.en_combate_con = None


def _mover_subdito(pa, m, ahora, destino=None):
    """El siguiente tramo recto de su carril (o hacia `destino`, una unidad enemiga a la vista)."""
    import combate
    import transitable
    from codec import Msg
    if ahora < m.moba_llega:
        return
    x0, y0 = int(m.tile_x), int(m.tile_y)
    if destino is not None:
        (x1, y1), _ok = transitable.tramo(pa.stage, (x0, y0), destino, 2, parar_a=max(1, m.atk_range))
    else:
        r = m.moba_ruta
        # vuelve al carril por el punto mas cercano por delante (tras perseguir a alguien)
        if _dist((x0, y0), r[m.moba_i]) > 2:
            m.moba_i = min(range(m.moba_i, len(r)), key=lambda k: _dist((x0, y0), r[k]))
        i = m.moba_i
        if i >= len(r) - 1:
            return
        pasos = int(pa.cfg.get('casillas_por_paso', 3))
        d = (r[i + 1][0] - r[i][0], r[i + 1][1] - r[i][1])
        j = i + 1
        while j < len(r) - 1 and j - i < pasos and (r[j + 1][0] - r[j][0], r[j + 1][1] - r[j][1]) == d:
            j += 1
        (x1, y1) = r[j]
        m.moba_i = j
    if (x1, y1) == (x0, y0):
        return
    vel = int(m.move_speed or 45)
    if ahora < getattr(m, 'lento_hasta', 0):
        vel = max(10, vel // 2)
    _mandar(pa, Msg.registry[(0x0005, 's2c', '*')].build(entity_id=m.entity_id, cur_x=x0 * 32, cur_y=y0 * 32,
                                                           dst_x=x1 * 32, dst_y=y1 * 32, speed=vel))
    m.tile_x, m.tile_y = x1, y1
    m.tile = [x1, y1]
    # Su "casa" va con el: si la IA de monstruos lo suelta tras perseguir a un jugador, vuelve aqui y no a su base
    m.spawn_x, m.spawn_y, m.spawn_tile = x1, y1, [x1, y1]
    m.moba_llega = ahora + combate.segundos_de_tramo(max(abs(x1 - x0), abs(y1 - y0)), vel)


def _tick_neutral(pa, m, ahora):
    """Jungla y jefe: quietos; pegan al heroe que les pego mientras siga cerca de su sitio. Si se va (o muere), vuelven
    a vida completa."""
    import combate
    import moba_heroe
    d = datos_de(pa, m.moba_tipo)
    correa = int(d.get('correa', (pa.cfg.get('jungla') or {}).get('correa', 9)))
    h = pa.heroes.get(m.moba_blanco) if m.moba_blanco is not None else None
    if h is None or h.muerto or _dist(m.moba_casa, moba_heroe._pos(h)) > correa:
        if m.moba_blanco is not None:
            m.moba_blanco = None
            m.moba_dots = []
            if m.hp < m.hp_max:
                m.hp = m.hp_max
                _mandar(pa, combate.atributo(m.entity_id, m.porcentaje))
        return
    if ahora < getattr(m, 'aturdido_hasta', 0) or ahora < m.moba_proximo:
        return
    if _dist((m.tile_x, m.tile_y), moba_heroe._pos(h)) <= max(1, m.atk_range):
        moba_heroe.unidad_golpea(pa, m, h, ahora)
        if m.moba_tipo == 'jefe':                    # el jefe pega tambien a los que estan pegados al objetivo
            centro = moba_heroe._pos(h)
            for o in list(pa.heroes.values()):
                if o is not h and not o.muerto and o.equipo == h.equipo and _dist(centro, moba_heroe._pos(o)) <= 2:
                    moba_heroe.unidad_golpea(pa, m, o, ahora)


def provocar(pa, u, h):
    """Un heroe pego a una unidad neutral: ella y las de su campamento van a por el."""
    if u.moba_equipo or h is None:
        return
    for o in pa.unidades.values():
        if o is u or (u.moba_campamento is not None and o.moba_campamento == u.moba_campamento):
            if o.moba_blanco is None:
                o.moba_blanco = h.ses


def _jungla(pa, ahora):
    """Los campamentos y el jefe que tocan."""
    jg = pa.cfg.get('jungla') or {}
    for i, sitio in enumerate(jg.get('campamentos') or []):
        cuando = pa.jungla_proxima.get(i)
        if cuando is None or ahora < cuando:
            continue
        pa.jungla_proxima[i] = None
        x, y = int(sitio[0]), int(sitio[1])
        puestos = [('grande', (x, y))] + [('pequeno', p) for p in ((x - 2, y + 1), (x + 2, y - 1), (x + 1, y + 2))
                                          [:int(jg.get('pequenos', 2))]]
        for tipo, tile in puestos:
            npc = random.choice(jg[tipo]['npc_types'])
            m = _nueva_unidad(pa, tipo, 0, tile, npc=int(npc))
            m.moba_campamento = i
    j = pa.cfg.get('jefe') or {}
    if j and pa.jefe_proximo is not None and ahora >= pa.jefe_proximo:
        pa.jefe_proximo = None
        m = _nueva_unidad(pa, 'jefe', 0, tuple(j['sitio']), npc=int(random.choice(j['npc_types'])))
        _aviso_todos(pa, '%s has appeared in the middle of the jungle! Slay it to empower your team.' % m.nombre)


def _caida_neutral(pa, u, matador_ses, ahora):
    """Cae una unidad de la jungla o el jefe: exp al equipo del que la mato, reaparicion y, el jefe, el buff."""
    import moba_heroe
    h = pa.heroes.get(matador_ses) if matador_ses is not None else None
    if u.moba_tipo == 'jefe':
        j = pa.cfg['jefe']
        pa.jefe_proximo = ahora + float(j.get('reaparece', 240))
        if h is not None:
            b = j.get('buff') or {}
            pa.buffs[h.equipo] = (ahora + float(b.get('dura', 120)), {'ataque': float(b.get('ataque', 0)),
                                                                       'defensa': float(b.get('defensa', 0))})
            _aviso_todos(pa, '%s slew %s! Team %s is empowered for %d s.' % (
                h.ses.personaje.nombre, u.nombre, pa.cfg['equipos'][str(h.equipo)]['nombre'], int(b.get('dura', 120))))
    elif u.moba_campamento is not None:
        if not any(o.moba_campamento == u.moba_campamento for o in pa.unidades.values()):
            pa.jungla_proxima[u.moba_campamento] = ahora + float(pa.cfg['jungla'].get('reaparece', 60))
    try:
        __import__('moba_tienda').al_caer(pa, u.moba_tipo, h.equipo if h is not None else 0, matador_ses,
                                          (int(u.tile_x), int(u.tile_y)))
    except Exception:
        log.exception('MOBA: oro de la jungla')
    cantidad = int((pa.cfg.get('exp') or {}).get(u.moba_tipo, 0))
    if h is not None and cantidad:
        moba_heroe.repartir_exp(pa, h.equipo, (int(u.tile_x), int(u.tile_y)), cantidad, h)


def _tick_unidad(pa, m, ahora):
    if m.moba_tipo in NEUTRALES:
        return _tick_neutral(pa, m, ahora)
    cfg = datos_de(pa, m.moba_tipo)
    if m.moba_tipo == 'nucleo' and not int(cfg.get('ataque', 0)):
        return                                  # la estatua grande tambien pega ("las estatuas deben atacar", 23/11/2026)
    vision = int(cfg.get('vision', cfg.get('alcance', 1)))
    # Peleando con un jugador: lo lleva la IA. Se suelta si se fue, murio o se alejo demasiado.
    if m.moba_jugador:
        s = next((s for s in _jugadores_enemigos(pa, m) if s.personaje.entity_id == m.en_combate_con), None)
        lejos = int(cfg.get('persecucion', cfg.get('alcance', 1)))
        ancla = m.moba_ruta[m.moba_i] if m.moba_tipo == 'subdito' else (m.tile_x, m.tile_y)
        if s is None or _dist(ancla, (s.personaje.tile_x, s.personaje.tile_y)) > lejos:
            _soltar_jugador(m)
        else:
            return
    if ahora < m.moba_llega or ahora < getattr(m, 'aturdido_hasta', 0):
        return
    u = _cercano(m, _enemigos(pa, m), lambda u: (u.tile_x, u.tile_y), vision)
    if u is not None:
        d, u = u
        if d <= max(1, m.atk_range):
            if ahora >= m.moba_proximo:
                golpear(pa, m, u, ahora)
        elif m.moba_tipo == 'subdito':
            _mover_subdito(pa, m, ahora, (int(u.tile_x), int(u.tile_y)))
        return
    heroes = [h for h in pa.heroes.values() if h.equipo != m.moba_equipo and not h.muerto
              and int(getattr(h.ses.personaje, 'stage', 0) or 0) == pa.stage]
    h = _cercano(m, heroes, lambda h: (h.ses.personaje.tile_x, h.ses.personaje.tile_y), vision)
    if h is not None:
        d, h = h
        if d <= max(1, m.atk_range):
            if ahora >= m.moba_proximo:
                import moba_heroe
                moba_heroe.unidad_golpea(pa, m, h, ahora)
            return
        if m.moba_tipo == 'subdito':
            ancla = m.moba_ruta[m.moba_i]
            pos = (int(h.ses.personaje.tile_x), int(h.ses.personaje.tile_y))
            if _dist(ancla, pos) <= int(cfg.get('persecucion', 10)):
                _mover_subdito(pa, m, ahora, pos)
                return
    if m.moba_tipo == 'subdito':
        _mover_subdito(pa, m, ahora)


def _oleadas(pa, ahora):
    o = pa.cfg['oleadas']
    if ahora >= pa.proxima_oleada:
        pa.proxima_oleada = ahora + float(o.get('cada', 30))
        for k in range(int(o.get('por_carril', 4))):
            for eq in (1, 2):
                for carril in pa.cfg['carriles']:
                    pa.cola.append((ahora + k * float(o.get('separacion', 1.2)), eq, carril))
    listos = [c for c in pa.cola if c[0] <= ahora]
    pa.cola = [c for c in pa.cola if c[0] > ahora]
    for _cuando, eq, carril in listos:
        _nueva_unidad(pa, 'subdito', eq, ruta(carril, eq)[0], carril)


def muere(pa, u, matador_ses):
    """Una unidad cae (la mate otra unidad o un jugador): fuera, y si es un nucleo gana el otro equipo."""
    import combate
    if pa.unidades.pop(u.entity_id, None) is None:
        return
    u.hp = 0
    _soltar_jugador(u)
    for s in pa.sesiones():
        if isinstance(getattr(s, 'monstruos', None), dict):
            s.monstruos.pop(u.entity_id, None)
    _mandar(pa, combate.atributo(u.entity_id, 0))

    def _fuera(eid=u.entity_id):
        _mandar(pa, combate.despawn_monstruo(eid))
    try:
        asyncio.get_running_loop().call_later(1.0, _fuera)
    except RuntimeError:
        _fuera()
    if u.moba_tipo in NEUTRALES:
        try:
            _caida_neutral(pa, u, matador_ses, time.time())
        except Exception:
            log.exception('MOBA: cae una neutral')
        return
    try:
        __import__('moba_tienda').al_caer(pa, u.moba_tipo, 3 - int(u.moba_equipo), matador_ses,
                                          (int(u.tile_x), int(u.tile_y)))
    except Exception:
        log.exception('MOBA: oro')
    try:
        import moba_heroe
        matador = pa.heroes.get(matador_ses) if matador_ses is not None else None
        cantidad = int((pa.cfg.get('exp') or {}).get(u.moba_tipo, 0))
        if cantidad:
            moba_heroe.repartir_exp(pa, 3 - int(u.moba_equipo), (int(u.tile_x), int(u.tile_y)), cantidad, matador)
    except Exception:
        log.exception('MOBA: experiencia')
    if u.moba_tipo == 'torre':
        _aviso_todos(pa, 'A %s tower has fallen!' % pa.cfg['equipos'][str(u.moba_equipo)]['nombre'])
    elif u.moba_tipo == 'nucleo':
        ganador = 3 - int(u.moba_equipo)
        terminar(pa, ganador)


def al_morir(ses, m):
    """Desde app._procesar_muerte_monstruo: un jugador mato una unidad del MOBA. True si era del MOBA."""
    if not getattr(m, 'moba', False):
        return False
    pa = getattr(m, 'moba_partida', None)
    if pa is not None:
        muere(pa, m, ses)
    return True


def _aviso_todos(pa, texto):
    import clases
    _mandar(pa, clases.aviso(texto, tipo=0))


def terminar(pa, ganador=None):
    """Acaba la partida: gana `ganador` (1 o 2) o nadie. Quita todas las unidades."""
    import combate
    if pa.resultado is not None:
        return
    pa.resultado = ganador or 0
    for m in list(pa.unidades.values()):
        _soltar_jugador(m)
    eids = list(pa.unidades)
    for s in pa.sesiones():
        if isinstance(getattr(s, 'monstruos', None), dict):
            for e in eids:
                s.monstruos.pop(e, None)
    _mandar(pa, *[combate.despawn_monstruo(e) for e in eids])
    pa.unidades.clear()
    if ganador:
        _aviso_todos(pa, 'VICTORY for team %s!' % pa.cfg['equipos'][str(ganador)]['nombre'])
    if ganador:
        try:
            import clases
            for s, (pts, ag) in __import__('moba_ranking').registrar(pa, ganador).items():
                s.enviar(clases.aviso('Angel MOBA: +%d season points%s.' % (pts, ', %d Angel Gold' % ag if ag else ''),
                                      tipo=0))
        except Exception:
            log.exception('MOBA: guardar la partida')
    try:
        __import__('moba_marcador').fin(pa, ganador)
    except Exception:
        log.exception('MOBA: ventana de fin')
    _PARTIDAS.pop(pa.id, None)
    import moba_heroe
    for s in list(pa.heroes):
        moba_heroe.salir(s, pa)
    for s in list(pa.jugadores):
        _DE_SESION.pop(s, None)
        quitar_marcas(s)
    quedan = [s for s in pa.sesiones() if not getattr(s, 'cerrada', False)]
    if quedan and ganador:
        _aviso_todos(pa, 'Back to town in 10 seconds.')
    _despues(10.0 if ganador else 0.0, lambda: _sacar(pa, quedan))
    log.info('MOBA %s: termina, gana %s', pa.id, ganador)


def _sacar(pa, sesiones):
    """Los que siguen en el mapa del MOBA, a la ciudad."""
    import app
    st, (x, y) = config()['mapa'].get('salida', [41, [173, 91]])
    for s in sesiones:
        p = getattr(s, 'personaje', None)
        if p is None or getattr(s, 'cerrada', False) or int(getattr(p, 'stage', 0) or 0) != pa.stage:
            continue
        if partida_de(s) is not None:
            continue                                  # ya esta en otra
        try:
            app._sincronizar_cambio_mapa(s, int(st), int(x), int(y))
        except Exception:
            log.debug('moba: sacar', exc_info=True)


def tick(ahora=None):
    ahora = time.time() if ahora is None else ahora
    for pa in list(_PARTIDAS.values()):
        try:
            if not pa.montada:
                continue
            for s in list(pa.jugadores):
                p = getattr(s, 'personaje', None)
                if getattr(s, 'cerrada', False) or p is None or int(getattr(p, 'stage', 0) or 0) != pa.stage:
                    __import__('moba_heroe').salir(s, pa)
                    if not getattr(s, 'cerrada', False):
                        quitar_marcas(s)
                    pa.jugadores.pop(s, None)
                    _DE_SESION.pop(s, None)
            if not pa.jugadores:
                terminar(pa)
                continue
            _oleadas(pa, ahora)
            _jungla(pa, ahora)
            __import__('moba_heroe').tick(pa, ahora)
            __import__('moba_tienda').goteo(pa, ahora)
            for m in list(pa.unidades.values()):
                if m.hp > 0 and pa.resultado is None:
                    _tick_unidad(pa, m, ahora)
            if ahora >= pa._proximo_hud and pa.resultado is None:
                pa._proximo_hud = ahora + 1.0
                __import__('moba_marcador').refrescar(pa, ahora)
        except Exception:
            log.exception('MOBA: tick de la partida %s', pa.id)


async def _bucle():
    while _PARTIDAS:
        tick()
        await asyncio.sleep(TICK)
    _TAREA[0] = None


def _despues(segundos, funcion):
    try:
        asyncio.get_running_loop().call_later(segundos, funcion)
    except RuntimeError:                      # sin bucle (tests): ya
        funcion()


def _arrancar():
    if _TAREA[0] is None:
        try:
            _TAREA[0] = asyncio.get_running_loop().create_task(_bucle())
        except RuntimeError:
            _TAREA[0] = None


# ---------------------------------------------------------------------------------------------- entrar y salir
def marcas(pa, visor):
    """Lo que `visor` tiene que saber de los demas de la partida para poder pegar a los enemigos en su cliente: el
    equipo de cada uno (hb.equipo) y el modo arena con la marca hostil (trade_routes._hostil), como en Trade Routes."""
    import holy_battlefield as hb
    import presencia
    import trade_routes as tr
    out = []
    mio = int(pa.jugadores.get(visor, 0))
    for sujeto, eq in list(pa.jugadores.items()):
        if sujeto is visor or getattr(sujeto, 'personaje', None) is None:
            continue
        eid = presencia.entidad_de(sujeto)
        out += [hb.equipo(eid, int(eq))] + list(tr._hostil(eid, int(eq) != mio))
    return out


def refrescar_marcas(pa):
    """A cada uno, las marcas de todos y el modo arena propio (sin el, el cliente no apunta a jugadores)."""
    import holy_battlefield as hb
    import presencia
    import trade_routes as tr
    for visor in pa.sesiones():
        try:
            presencia._mandar(visor, *marcas(pa, visor))
            yo = visor.personaje.entity_id
            visor.enviar(*tr._hostil(yo, True), hb.equipo(yo, int(pa.jugadores.get(visor, 0))))
        except Exception:
            log.debug('moba: marcas', exc_info=True)


def quitar_marcas(ses):
    """Al salir: ni modo arena ni equipo."""
    import holy_battlefield as hb
    import trade_routes as tr
    p = getattr(ses, 'personaje', None)
    if p is None:
        return
    try:
        ses.enviar(*tr._hostil(p.entity_id, False), hb.equipo(p.entity_id, 0))
    except Exception:
        log.debug('moba: quitar marcas', exc_info=True)


def empezar_partida(gente, ahora=None, addr='?'):
    """Una partida de verdad: gente = [(sesion, equipo, clase)]. Los lleva a todos a su base del mapa del MOBA; la
    partida se monta cuando llega el primero (al_entrar) y todos la comparten (presencia.clave_de_mapa)."""
    import app
    ahora = time.time() if ahora is None else ahora
    pid = 'moba-%d-%d' % (int(ahora), len(_PARTIDAS))
    pa = _PARTIDAS[pid] = Partida(pid, ahora)
    for ses, eq, clase in gente:
        pa.jugadores[ses] = int(eq)
        pa.clases[ses] = clase if clase in (pa.cfg.get('clases') or {}) else next(iter(pa.cfg.get('clases') or {'': 0}))
        _DE_SESION[ses] = pa
        ses._moba_pendiente = pa
    for ses, eq, _c in gente:
        try:
            llegada = tuple(pa.cfg['equipos'][str(eq)]['llegada'])
            app._viajar_por_portal(ses, getattr(ses, 'addr', addr), {'destino': pa.stage, 'llegada': llegada},
                                   motivo='al MOBA')
        except Exception:
            log.exception('MOBA: llevar a %s', getattr(getattr(ses, 'personaje', None), 'nombre', '?'))
    log.info('MOBA %s: empieza con %d (%s)', pid, len(gente),
             ', '.join('%s/%d' % (getattr(s.personaje, 'nombre', '?'), e) for s, e, _c in gente))
    return pa


def empezar_prueba(ses, addr='?', equipo=1, clase=None):
    """/moba start [equipo] [clase] (GM): una partida para el solo, en el equipo y con la clase dados, en su copia del
    mapa."""
    import app
    if partida_de(ses) is not None:
        return 'You are already in a MOBA game (/moba stop).'
    pid = 'prueba-%s-%d' % (getattr(ses.personaje, 'char_id', 0), int(time.time()))
    pa = _PARTIDAS[pid] = Partida(pid, time.time())
    pa.jugadores[ses] = int(equipo)
    pa.clases[ses] = clase if clase in (pa.cfg.get('clases') or {}) else next(iter(pa.cfg.get('clases') or {'': 0}))
    _DE_SESION[ses] = pa
    ses._moba_pendiente = pa
    llegada = tuple(pa.cfg['equipos'][str(equipo)]['llegada'])
    app._viajar_por_portal(ses, addr, {'destino': pa.stage, 'llegada': llegada}, motivo='al MOBA')
    return 'MOBA test: team %s' % pa.cfg['equipos'][str(equipo)]['nombre']


def al_entrar(ses, addr='?'):
    """El jugador cargo un mapa. En el del MOBA: monta la partida que lo esperaba (o le redibuja la suya); sin
    partida, fuera."""
    import app
    p = getattr(ses, 'personaje', None)
    cfg = config()
    if not p or int(getattr(p, 'stage', 0) or 0) != int(cfg.get('mapa', {}).get('stage', -1)):
        return
    pa = partida_de(ses)
    if pa is None:
        st, (x, y) = cfg['mapa'].get('salida', [41, [173, 91]])
        app._sincronizar_cambio_mapa(ses, int(st), int(x), int(y))
        return
    if not pa.montada:
        montar(pa)
        _arrancar()
        _aviso_todos(pa, 'Angel MOBA! Destroy the enemy statue. Minions every %d s.' % int(pa.cfg['oleadas'].get('cada', 30)))
    else:
        _redibujar(pa, ses)
    import moba_heroe
    if ses not in pa.heroes:
        moba_heroe.entrar(ses, pa, pa.clases.get(ses))
    else:
        ses.enviar(*moba_heroe.paquetes_heroe(pa.heroes[ses]))
    _despues(1.0, lambda: refrescar_marcas(pa) if pa.resultado is None else None)


def salir(ses, addr='?'):
    import app
    pa = partida_de(ses)
    if pa is None:
        return 'You are not in a MOBA game.'
    __import__('moba_heroe').salir(ses, pa)
    quitar_marcas(ses)
    pa.jugadores.pop(ses, None)
    _DE_SESION.pop(ses, None)
    if not pa.jugadores:
        terminar(pa)
    st, (x, y) = config()['mapa'].get('salida', [41, [173, 91]])
    app._sincronizar_cambio_mapa(ses, int(st), int(x), int(y))
    return 'Left the MOBA.'
