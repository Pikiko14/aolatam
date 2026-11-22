"""Pet Defense, el minijuego tower defense (21/11/2026): "las construcciones defensivas son mascotas de Angels Online.
Cada mascota funciona como una torre con aspecto, alcance, velocidad y tipo de ataque propios."

FASE 1 (esta): comprobar en el cliente que una mascota SIN dueno que la siga se ve quieta en una casilla y pega a los
monstruos que entran en su alcance, con su animacion, el numero de dano y la muerte del bicho (EXP y drops para el
jugador que la puso, como cuando mata su propia mascota). Se prueba con el GM:

    /torre [tipo|item de huevo]   pone una torre en tu casilla (tipos de plantillas/pet_defense.json)
    /torre quitar                 quita las tuyas

La torre es el mismo 0x0050 que pinta la mascota de un jugador (mascotas.entidad_mundo) con su sprite, pero SIN el
enlace 0x001D jugador -> mascota: asi el cliente no la trata como la mascota activa y no la mueve con el dueno. El
dueno va en el campo de la entidad (offset 75) solo para la faccion (anillo de aliado). Los golpes son los del golpe
basico de la mascota (app.py: ataque + numero + cierre + flotante + vida), y la muerte va por
app._procesar_muerte_monstruo.

Las fases que siguen (oleadas, Essence, colocar y mejorar, el cristal, las pantallas y el ranking) se apoyan en esto.
"""
import asyncio
import json
import logging
import pathlib
import time

log = logging.getLogger('pet_defense')

CONFIG = pathlib.Path(__file__).parent / 'plantillas' / 'pet_defense.json'
TICK = 0.2                       # segundos entre repasos de las torres
_CFG = [None, 0.0]               # (config, mtime)
_TORRES = {}                     # entidad -> Torre
_TAREA = [None]


def config() -> dict:
    """plantillas/pet_defense.json, releido si cambia (se puede ajustar sin reiniciar)."""
    try:
        mt = CONFIG.stat().st_mtime
    except OSError:
        return _CFG[0] or {'torres': {}, 'torre_por_defecto': '', 'max_torres_por_jugador': 0}
    if _CFG[0] is None or mt != _CFG[1]:
        _CFG[0], _CFG[1] = json.loads(CONFIG.read_text(encoding='utf-8')), mt
    return _CFG[0]


class Torre:
    def __init__(self, entidad, dueno_ses, stage, x, y, tipo, datos, ficha, nivel=1):
        self.entidad, self.dueno, self.stage, self.x, self.y = entidad, dueno_ses, stage, x, y
        self.casa = (x, y)                                   # su piedra: se mueve como mucho radio_movimiento de aqui
        self.tipo, self.datos, self.ficha = tipo, datos, ficha
        self.nivel = 1
        self.proximo = 0.0
        self.llega_mov = 0.0                                 # mientras camina no pega
        self.cd_skills = {}
        self.poner_nivel(nivel)

    def poner_nivel(self, nivel):
        """Cada nivel por encima del 1 multiplica el ataque por 'mejora_ataque' y suma 'mejora_alcance' casillas."""
        d, cfg = self.datos, config()
        self.nivel = max(1, int(nivel))
        extra = self.nivel - 1
        self.alcance = int(d.get('alcance', 5)) + extra * int(cfg.get('mejora_alcance', 1))
        self.cadencia = float(d.get('cadencia', 1.0))
        self.ataque = int(round(int(d.get('ataque', 100)) * float(cfg.get('multiplicador_ataque', 1))
                                * float(cfg.get('mejora_ataque', 1.5)) ** extra))
        self.magico = bool(d.get('magico', False))
        self.area = int(d.get('area', 0))                  # casillas alrededor del objetivo que tambien reciben
        self.ralentiza = float(d.get('ralentiza', 0))      # segundos a media velocidad (pet_defense_partida._mover)
        self.n_objetivos = max(1, int(d.get('objetivos', 1)))   # a cuantos pega a la vez (los mas cercanos)
        self.essence_por_oleada = int(d.get('essence_por_oleada', 0)) * self.nivel
        self.skills = skills_de_ataque(sprite_de(d, self.nivel))
        self.dano_fijo = dano_de(d, self.nivel)

    def sprite(self):
        """La mascota de su nivel: 'sprites' lleva una por nivel (evoluciona al mejorarla); si no, 'sprite'."""
        return sprite_de(self.datos, self.nivel)


def dano_de(datos, nivel):
    """El dano de cada golpe (sin defensa del enemigo): dano_por_nivel de su nivel x su coste / coste_referencia.
    "Que el dano sea 500, 700, 1200 el tercer nivel del pet" y "relativo al costo de cada pet, el que cuesta mas pega
    mas" (21/11/2026): la mas barata (coste_referencia, por defecto el coste mas bajo) pega eso y las demas en
    proporcion. 0 si no hay dano_por_nivel (entonces cuenta su ataque contra la defensa)."""
    cfg = config()
    fijos = cfg.get('dano_por_nivel') or []
    if not fijos:
        return 0
    costes = [int(x.get('coste', 0)) for x in (cfg.get('torres') or {}).values() if int(x.get('coste', 0)) > 0]
    ref = float(cfg.get('coste_referencia') or (min(costes) if costes else 1))
    base = int(fijos[min(len(fijos), max(1, int(nivel))) - 1])
    return int(round(base * max(1, int(datos.get('coste', ref))) / ref / 10.0)) * 10


def sprite_de(datos, nivel):
    lista = datos.get('sprites') or []
    if lista:
        return int(lista[min(len(lista), max(1, int(nivel))) - 1])
    return int(datos.get('sprite', 3049))


def skills_de_ataque(sprite):
    """Los poderes de esa mascota que pegan o maldicen (los de su especie y fase en petskill.xml, al nivel maximo de
    skill): "que usen sus poderes, en base al tipo que este" (21/11/2026). Los de apoyo (escudos, curas) no."""
    import combate
    import mascotas
    out = []
    for s in mascotas.skills_de(int(sprite), 260):
        d = combate.datos_magia(int(s)) if s else {}
        if s and (d.get('es_ataque') or d.get('es_debuff')):
            out.append(int(s))
    return out


def ficha_de(datos, nivel):
    """La ficha de mascota (mascotas.recien_nacida) con el sprite del nivel y su nombre de pet.xml."""
    import mascotas
    sp = sprite_de(datos, nivel)
    nombre = mascotas.ficha_de_sprite(sp).get('nombre') or datos.get('nombre', 'Pet')
    return mascotas.recien_nacida(nombre, sp, nivel=1)


def datos_de_tipo(tipo):
    """(clave, datos) del tipo pedido: una clave de 'torres', o el item de un huevo de mascota (con los stats de la torre
    por defecto y el nombre y sprite del huevo). None si no se reconoce."""
    cfg = config()
    torres = cfg.get('torres') or {}
    tipo = str(tipo or cfg.get('torre_por_defecto') or '').lower()
    if tipo in torres:
        return tipo, dict(torres[tipo])
    if tipo.isdigit():
        import inventario as _iv
        d = _iv.datos_mascota(int(tipo)) or {}
        if d.get('sprite') and d.get('nombre') not in (None, '', 'Pet'):     # 'Pet' es lo que da si no es un huevo
            base = dict(torres.get(cfg.get('torre_por_defecto'), {}))
            base.update({'nombre': d.get('nombre') or 'Pet', 'sprite': int(d['sprite'])})
            return tipo, base
    return None


def _mapa(ses):
    p = getattr(ses, 'personaje', None)
    return int(getattr(p, 'stage', 0) or 0) if p else 0


def _sesiones_del_mapa(stage):
    import presencia
    return list(presencia._vivas(stage))


def _mandar_al_mapa(stage, *paquetes, extra=None):
    import presencia
    destinos = _sesiones_del_mapa(stage)
    if extra is not None and extra not in destinos:
        destinos.append(extra)
    for s in destinos:
        presencia._mandar(s, *paquetes)


def paquetes_spawn(t: Torre) -> list:
    import app
    import combate
    import mascotas
    import presencia
    est = dict(t.ficha)
    # SIN dueno: con la entidad del jugador en el campo del dueno el cliente la tomaba por SU mascota y le abria el
    # panel de su mascota ("que no salga eso cuando pongo 1 pet", 21/11/2026). La faccion (el anillo de aliado) va
    # aparte, la del jugador.
    est.update({'entidad': t.entidad, 'x': t.x, 'y': t.y, 'dueno': 0, 'dueno_nombre': '', 'instancia': t.entidad,
                'faccion': presencia.faccion_de_entidad(t.dueno.personaje.entity_id) or 0})
    return [mascotas.entidad_mundo(app._pet_plantilla(), est),
            combate.atributo(t.entidad, mascotas.hp_eff(t.ficha), combate.KIND_HP)]


def crear(ses, clave, datos, tile, nivel=1):
    """Pone una torre de ese tipo en esa casilla y la dibuja a todos los del mapa. Devuelve la Torre."""
    import app
    ficha = ficha_de(datos, nivel)
    t = Torre(app._pet_siguiente_entidad(ses), ses, _mapa(ses), int(tile[0]), int(tile[1]), clave, datos, ficha, nivel)
    _TORRES[t.entidad] = t
    _mandar_al_mapa(t.stage, *paquetes_spawn(t), extra=ses)
    _arrancar()
    log.info('torre %s (%s, nivel %d) de %s en %s %s', t.entidad, clave, t.nivel, ses.personaje.nombre, t.stage, tuple(tile))
    return t


def evolucionar(t: Torre, nivel):
    """Sube la torre de nivel y, si su mascota cambia, la vuelve a dibujar con la evolucion. Con una entidad NUEVA,
    como app._pet_recrear cuando evoluciona la mascota de un jugador: quitarla y volver a sacarla con la misma no la
    redibujaba y la torre desaparecia ("le di upgrade y no sale", 21/11/2026)."""
    import app
    import mascotas
    antes = t.sprite()
    t.poner_nivel(nivel)
    if t.sprite() != antes:
        vieja = t.entidad
        t.ficha = ficha_de(t.datos, t.nivel)
        t.entidad = app._pet_siguiente_entidad(t.dueno)
        _TORRES.pop(vieja, None)
        _TORRES[t.entidad] = t
        _mandar_al_mapa(t.stage, mascotas.quitar(vieja), *paquetes_spawn(t), extra=t.dueno)


def poner(ses, tipo=None):
    """/torre: pone una torre en la casilla del jugador, gratis (es para probar). Devuelve el texto para el GM."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return 'no character in world yet'
    elegido = datos_de_tipo(tipo)
    if elegido is None:
        return 'unknown tower %r. Types: %s, or a pet egg item id' % (tipo, ', '.join(config().get('torres') or ()))
    clave, datos = elegido
    mias = [t for t in _TORRES.values() if t.dueno is ses]
    tope = int(config().get('max_torres_por_jugador', 10) or 0)
    if tope and len(mias) >= tope:
        return 'you already have %d towers (/torre quitar)' % len(mias)
    t = crear(ses, clave, datos, (p.tile_x, p.tile_y))
    return 'tower %s placed at (%d,%d): range %d, every %.1fs, attack %d' % (
        datos.get('nombre', clave), t.x, t.y, t.alcance, t.cadencia, t.ataque)


def quitar(ses=None):
    """Quita las torres de ese jugador (o todas). Devuelve cuantas."""
    import mascotas
    fuera = [t for t in list(_TORRES.values()) if ses is None or t.dueno is ses]
    for t in fuera:
        _TORRES.pop(t.entidad, None)
        _mandar_al_mapa(t.stage, mascotas.quitar(t.entidad), extra=t.dueno)
    return len(fuera)


def objetivo(t: Torre, n=0):
    """El monstruo vivo mas cercano dentro del alcance (distancia de casillas, la de ajedrez como la mascota)."""
    import app
    ses = t.dueno
    bichos = getattr(ses, 'monstruos', None) or {}
    lista = bichos.values() if isinstance(bichos, dict) else bichos
    cerca = []
    for m in list(lista):
        if not getattr(m, 'vivo', True) or getattr(m, 'hp', 0) <= 0 or getattr(m, 'encantado', False):
            continue
        if int(getattr(m, 'stage', t.stage) or t.stage) != t.stage:
            continue
        d = max(abs(int(m.tile_x) - t.x), abs(int(m.tile_y) - t.y))
        if d > t.alcance or not app._pet_puede_atacar(ses, m):
            continue
        cerca.append((d, m.entity_id, m))
    cerca.sort(key=lambda c: c[:2])
    return [m for _, _, m in cerca[:n]] if n else (cerca[0][2] if cerca else None)


def objetivos(t: Torre):
    """Los n_objetivos monstruos vivos mas cercanos dentro del alcance."""
    return objetivo(t, t.n_objetivos)


def bono(t: Torre, clave):
    """Lo que suma la mejora `clave` elegida en la partida de su dueno (pet_defense_partida.BONOS): veces x 'paso'."""
    try:
        import pet_defense_partida
        veces = int(pet_defense_partida.bonos_de(t.dueno).get(clave, 0))
    except Exception:
        veces = 0
    if not veces:
        return 0
    return veces * float(((config().get('bonos') or {}).get(clave) or {}).get('paso', 0))


def _golpe(t: Torre, m, mult_extra=1.0, magico=None) -> int:
    """Le quita la vida a m y devuelve el dano que se ensena: el fijo de su nivel (dano_por_nivel, sin defensa) o, sin
    el, el ataque contra su defensa como el golpe basico de la mascota."""
    import combate as cb
    mult_extra *= 1.0 + bono(t, 'ataque')
    if getattr(t, 'dano_fijo', 0):
        dano = int(round(t.dano_fijo * mult_extra))
        m.recibir_extra(dano, es_pet=True)
        return dano
    return m.recibir(t.ataque, es_magico=t.magico if magico is None else magico, mult=cb.MULT_DANO_MASCOTA * mult_extra,
                     var_pct=0.03, es_pet=True)


def disparar(t: Torre, m) -> list:
    """Un golpe de la torre a m (y, si es de area, a los de alrededor): les baja la vida y devuelve los paquetes (los
    mismos del golpe basico de la mascota). Los muertos quedan con hp 0 para tick()."""
    import combate as cb
    dano = _golpe(t, m)
    if t.ralentiza > 0 and m.hp > 0:
        m.lento_hasta = time.time() + t.ralentiza
    pk = [cb.ataque(t.entidad, m.entity_id, cb.anim_de_monstruo(t.ficha.get('nombre', ''))),
          cb.numero_de_dano(t.entidad, m.entity_id, dano, ataque=0, efecto=0),
          cb.cierre_de_dano(t.entidad, m.entity_id, ataque=0, efecto=0),
          cb.numero_flotante(m.entity_id, dano),
          cb.atributo(m.entity_id, m.porcentaje if m.hp > 0 else 0)]
    if t.area > 0:
        for otro in _vecinos(t, m):
            d2 = _golpe(t, otro)
            pk += [cb.numero_flotante(otro.entity_id, d2), cb.atributo(otro.entity_id, otro.porcentaje if otro.hp > 0 else 0)]
    return pk


def _vecinos(t: Torre, m, radio=None):
    radio = t.area if radio is None else radio
    bichos = getattr(t.dueno, 'monstruos', None) or {}
    for o in list(bichos.values() if isinstance(bichos, dict) else bichos):
        if o is m or getattr(o, 'hp', 0) <= 0 or not getattr(o, 'vivo', True):
            continue
        if max(abs(int(o.tile_x) - int(m.tile_x)), abs(int(o.tile_y) - int(m.tile_y))) <= radio:
            yield o


def poder(t: Torre, m, ahora, rng=None):
    """Si toca (prob_poder y sin recarga), la torre lanza uno de sus poderes a m, como la mascota de un jugador
    (app.py): el lanzamiento con su tiempo de cast ahora, y el cierre, la vida y el numero al acabar. Pega
    mult_poder veces el golpe basico; los de area (es_aoe) tambien a los de alrededor. Devuelve (paquetes de ahora,
    paquetes de despues, segundos hasta despues, golpeados) o None si no lanza nada."""
    import random
    import combate as cb
    rng = rng or random
    cfg = config()
    libres = [sk for sk in getattr(t, 'skills', ()) if ahora >= t.cd_skills.get(sk, 0)]
    prob = float(cfg.get('prob_poder', 0.5)) + bono(t, 'poder') * float(((cfg.get('bonos') or {}).get('poder') or {}).get(
        'prob_por_paso', 0.25))
    if not libres or rng.random() >= min(0.95, prob):
        return None
    sk = rng.choice(libres)
    d = cb.datos_magia(sk)
    t.cd_skills[sk] = ahora + max(1.0, int(d.get('cd_ms') or 2000) / 1000.0)
    magia = bool(d.get('es_magia_visual'))
    efecto = d.get('efecto') or 101
    cast = max(100, int(d.get('cast_time') or 100))
    mult = float(cfg.get('mult_poder', 1.5)) * (1.0 + bono(t, 'poder'))
    dano = _golpe(t, m, mult, magia or t.magico)
    ahora_pk = [cb.ataque(t.entidad, m.entity_id, cb.anim_de_monstruo(t.ficha.get('nombre', ''))),
                cb.numero_de_dano(t.entidad, m.entity_id, dano, ataque=sk, efecto=efecto, cast_time=cast, es_magia=magia)]
    despues = [cb.cierre_de_dano(t.entidad, m.entity_id, ataque=sk, efecto=efecto, es_magia=magia),
               cb.atributo(m.entity_id, m.porcentaje if m.hp > 0 else 0),
               cb.numero_flotante(m.entity_id, dano)]
    golpeados = [m]
    if d.get('es_aoe') or t.area > 0:
        radio = max(t.area, 2 if d.get('es_aoe') else 0)
        for o in _vecinos(t, m, radio):
            d2 = _golpe(t, o, mult, magia or t.magico)
            despues += [cb.numero_flotante(o.entity_id, d2), cb.atributo(o.entity_id, o.porcentaje if o.hp > 0 else 0)]
            golpeados.append(o)
    if t.ralentiza > 0 and m.hp > 0:
        m.lento_hasta = time.time() + t.ralentiza
    return ahora_pk, despues, cast / 1000.0, golpeados


def mover(t: Torre, ahora):
    """Se acerca al enemigo mas cercano que este a su alcance + radio_movimiento de su piedra (sin alejarse mas de
    radio_movimiento de ella) y, sin enemigos, vuelve a su piedra: "que los pet se muevan cierto rango" (21/11/2026).
    True si echo a andar."""
    import combate as cb
    import transitable
    from codec import Msg
    radio = int(config().get('radio_movimiento', 3)) + int(round(bono(t, 'movimiento')))
    if radio <= 0 or ahora < t.llega_mov:
        return False
    destino, parar = None, 0
    lejos = _cerca_de_casa(t, t.alcance + radio)
    if lejos is not None:
        destino, parar = (int(lejos.tile_x), int(lejos.tile_y)), t.alcance
    elif (t.x, t.y) != t.casa:
        destino = t.casa
    if destino is None:
        return False
    (nx, ny), _ok = transitable.tramo(t.stage, (t.x, t.y), destino, 2, parar_a=parar)
    if (nx, ny) == (t.x, t.y) or max(abs(nx - t.casa[0]), abs(ny - t.casa[1])) > radio:
        return False
    vel = int(config().get('velocidad_torres', 60))
    pk = Msg.registry[(0x0005, 's2c', '*')].build(entity_id=t.entidad, cur_x=t.x * 32, cur_y=t.y * 32,
                                                    dst_x=nx * 32, dst_y=ny * 32, speed=vel)
    t.llega_mov = ahora + cb.segundos_de_tramo(max(abs(nx - t.x), abs(ny - t.y)), vel)
    t.x, t.y = nx, ny
    _mandar_al_mapa(t.stage, pk, extra=t.dueno)
    return True


def _cerca_de_casa(t: Torre, distancia):
    """El enemigo vivo mas cercano a la torre de entre los que estan a `distancia` de su piedra."""
    bichos = getattr(t.dueno, 'monstruos', None) or {}
    mejor = None
    for m in list(bichos.values() if isinstance(bichos, dict) else bichos):
        if getattr(m, 'hp', 0) <= 0 or not getattr(m, 'vivo', True) or getattr(m, 'encantado', False):
            continue
        if max(abs(int(m.tile_x) - t.casa[0]), abs(int(m.tile_y) - t.casa[1])) > distancia:
            continue
        d = max(abs(int(m.tile_x) - t.x), abs(int(m.tile_y) - t.y))
        if mejor is None or d < mejor[0]:
            mejor = (d, m)
    return mejor[1] if mejor else None


def _despues(segundos, funcion):
    try:
        asyncio.get_running_loop().call_later(segundos, funcion)
    except RuntimeError:                      # sin bucle (tests, simulaciones): ya
        funcion()


def tick(ahora=None):
    """Un repaso: cada torre lista pega a sus objetivos (a veces con un poder); si no tiene ninguno a tiro, se mueve.
    Las de un dueno que se fue o cambio de mapa se quitan."""
    ahora = time.time() if ahora is None else ahora
    for t in list(_TORRES.values()):
        ses = t.dueno
        if getattr(ses, 'cerrada', False) or getattr(ses, 'personaje', None) is None or _mapa(ses) != t.stage:
            quitar_una(t)
            continue
        if ahora < t.llega_mov:
            continue
        blancos = objetivos(t)
        if not blancos:
            mover(t, ahora)
            continue
        if ahora < t.proximo:
            continue
        t.proximo = ahora + t.cadencia * max(0.3, 1.0 - bono(t, 'velocidad'))
        golpeados, paquetes = [], []
        for m in blancos:
            if m.hp <= 0:
                continue
            lanzado = poder(t, m, ahora)
            if lanzado:
                ya, luego, retraso, tocados = lanzado
                paquetes += ya

                def _fin(_t=t, _luego=luego, _tocados=tocados, _ses=ses):
                    _mandar_al_mapa(_t.stage, *_luego, extra=_ses)
                    _matar(_ses, _tocados)
                _despues(retraso, _fin)
                continue
            golpeados += [m] + (list(_vecinos(t, m)) if t.area > 0 else [])
            paquetes += disparar(t, m)
        if paquetes:
            _mandar_al_mapa(t.stage, *paquetes, extra=ses)
        _matar(ses, golpeados)


def _matar(ses, golpeados):
    """La muerte de los que se quedaron sin vida (una sola vez por bicho, aunque le peguen dos torres)."""
    import app
    for v in dict.fromkeys(golpeados):
        if v.hp <= 0 and not getattr(v, '_pd_procesado', False):
            v.hp = 0
            v._pd_procesado = True
            app._procesar_muerte_monstruo(ses, v, ses.personaje.entity_id, getattr(ses, 'addr', 'pet_defense'),
                                          espera=0.1)


def quitar_una(t: Torre):
    import mascotas
    _TORRES.pop(t.entidad, None)
    try:
        _mandar_al_mapa(t.stage, mascotas.quitar(t.entidad))
    except Exception:
        log.debug('quitar torre', exc_info=True)


def al_entrar_al_mapa(ses):
    """Quien entra a un mapa ve las torres que ya hay en el."""
    st = _mapa(ses)
    for t in list(_TORRES.values()):
        if t.stage == st and t.dueno is not ses:
            import presencia
            presencia._mandar(ses, *paquetes_spawn(t))


async def _bucle():
    """Las torres y las partidas (pet_defense_partida) en el mismo bucle, mientras haya algo."""
    import pet_defense_partida as partida
    while _TORRES or partida.hay_partidas():
        try:
            partida.tick()
            tick()
        except Exception:
            log.exception('pet defense tick')
        await asyncio.sleep(TICK)
    _TAREA[0] = None


def _arrancar():
    if _TAREA[0] is None:
        try:
            _TAREA[0] = asyncio.get_running_loop().create_task(_bucle())
        except RuntimeError:          # sin bucle (tests): se llama a tick() a mano
            _TAREA[0] = None
