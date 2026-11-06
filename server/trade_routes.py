"""Trade Routes: jobs (Trader / Hunter / Thief) y encargos de carga entre ciudades (05/11/2026).

Diseño pactado con el usuario (resumen; el texto completo esta en la conversacion del 05/11/2026):

  * JOBS. El Guild Clerk de las cuatro ciudades da el job. Se cambia cada 7 dias (/job del GM salta la espera). Con el
    job activo se lleva su PD (paper doll) y no se cambia hasta dejar el job.
  * ENCARGO (Trader). Montado, sin otro encargo y con una casilla libre, compra la carga con su oro y recibe el objeto
    de carga. El destino es otra de las cuatro ciudades, al azar. Mientras lleva carga va un 50% mas lento (montado o
    no) y no puede teletransportarse: tiene que ir por los mapas (portales a pie).
  * ENTREGA. En el Guild Clerk de la ciudad de destino, dentro del tiempo. El Trader recupera lo invertido y gana un
    extra al azar (1M como mucho, en la Gem); los Hunters de su grupo que esten en el mismo mapa se reparten su premio;
    cada uno (Trader y Hunters) recibe un vale de canje al azar del Event Overview.
  * ANTI-ABUSO. En el grupo no puede haber dos personajes con job de la misma IP.
  * ROBO (fase 3). Al morir o desconectarse, la carga cae al suelo (objeto de mapa) 5 minutos. La recoge, acercandose
    y montado, un Thief (de otra IP que el Trader) o el Trader / un Hunter de su grupo ("The cargo was recovered!"). El
    Thief la lleva al Fence de uno de sus 4 mapas, menos el del mapa donde la robo, y cobra lo suyo y un vale.
  * PVP DEL EVENTO fuera de ciudades y zonas seguras: el Thief contra quien lleva la carga y los Hunters de su grupo, y
    Traders / Hunters contra el Thief que lleva carga robada. El cliente lo sabe por la marca hostil (42) que se le
    pone a cada uno solo para quien puede atacarle; quien lleva carga lleva ademas el aro (AURA_CARGA).
"""
import json
import logging
import os
import pathlib
import random
import time

log = logging.getLogger('trade_routes')

TRADER, HUNTER, THIEF = 1, 2, 3
NOMBRE_JOB = {TRADER: 'Trader', HUNTER: 'Hunter', THIEF: 'Thief'}
CLAVE_JOB, CLAVE_DESDE, CLAVE_ULTIMO = 'trade_job', 'trade_job_desde', 'trade_job_ultimo'      # en personaje.logros_cont (se guarda con los logros)
DIAS_CAMBIO = 7
SEGUNDOS_CAMBIO = DIAS_CAMBIO * 86400

CIUDADES = {3: 'Aurora City', 26: 'Dark City', 29: 'Breeze Woods', 38: 'Iron Castle'}
FENCES = {8: 'Crashing Hillock', 30: 'Cryptic Moon Swamp', 25: 'Fungus Forest North', 39: 'Cactus Plain'}
NPC_CLERK, NPC_FENCE = 'Guild Clerk', 'Fence'
ZONAS_SEGURAS = frozenset(CIUDADES) | {41, 500}         # ciudades, el Lyceum y las casas: sin PvP del evento
SUELO_SEGUNDOS = 5 * 60
BLOQUEO_RECOGER = 2 * 60                                  # quien la solto no la recoge en 2 min
# El objeto del suelo es de SETTING/SERVER.OBD (los que se crean con el 0x000E, serie 60000+): 62329 / 62330 montones de
# sacos, 60092 cofre azul. Los de mapobj.obd (8399, 7550, 12431) son decoracion del .mpc y no se veian (06/11/2026).
ENTIDAD_SUELO = 97_100_000                                # + char_id del Trader: el objeto de mapa de la carga
# EL RELOJ DE LA CARGA: un icono de buff propio (magic.xml 23410, cliente_local.MAGIAS_PROPIAS) con el tiempo que
# queda, en quien la lleva; y avisos en el chat a los 10, 5 y 1 minutos ("donde veo el tiempo que tengo para
# entregar??", 06/11/2026).
MAGIA_CARGA = 23410
AVISOS_MINUTOS = (10, 5, 1)
RETRASO_PD = 1.0                                          # segundos tras entrar al mapa para volver a vestir la PD
AURA_CARGA = 1                                            # valor del aro (hb.equipo) de quien lleva carga; /aro <n>

RANURA_MONTURA = 10
FACTOR_CON_CARGA = 0.5          # 50% mas lento con carga, montado o a pie

# Las cargas: objeto propio (item9, cliente_local), precio, minutos, ganancia del Trader al azar, bolsa de los Hunters
# (se reparte entre ellos) y lo que gana el Thief que la entrega en el Fence.
GRAIN, SILK, GEM = 1, 2, 3
CARGAS = {
    GRAIN: dict(nombre='Grain Cargo', item=89074, icono=5146, suelo=62329, precio=500_000, minutos=20,
                ganancia=(100_000, 300_000), hunters=500_000, thief=250_000),
    SILK: dict(nombre='Silk Cargo', item=89075, icono=5729, suelo=62330, precio=2_000_000, minutos=25,
               ganancia=(300_000, 600_000), hunters=1_000_000, thief=500_000),
    GEM: dict(nombre='Gem Cargo', item=89076, icono=8731, suelo=60092, precio=5_000_000, minutos=30,
              ganancia=(600_000, 1_000_000), hunters=2_000_000, thief=1_000_000),
}
ITEMS_CARGA = {c['item']: k for k, c in CARGAS.items()}

# Un vale de canje al azar para cada uno al entregar: Mount Coin (monturas) y los tickets de Event Overview > Exchange.
VALES = (89073, 20229, 20228, 20231)    # Mount Coin, Lucky Ride, Lucky Enhanced Pestle, Lucky Hammer Ticket

# Las PD de cada job: {casilla de fashion: item}, por sexo (True = hombre).
PD = {
    TRADER: {True: {167: 26700, 168: 26701, 171: 26702, 172: 26703},      # Romantic Gentleman
             False: {167: 26704, 168: 26705, 171: 26706, 172: 26707}},     # Romantic Lady
    HUNTER: {True: {167: 74748, 168: 74749, 171: 74750, 172: 74751},      # Azure Hunter (unisex)
             False: {167: 74748, 168: 74749, 171: 74750, 172: 74751}},
    THIEF: {True: {167: 70524, 168: 70525, 171: 70526, 172: 70527},       # Holy Thief's (M)
            False: {167: 70520, 168: 70521, 171: 70522, 172: 70523}},     # Holy Thief's (F)
}
CASILLAS_FASHION = range(167, 175)

# TEXTOS PROPIOS de msg.xml (cliente_local los mete en el parche). Rango libre: 160609..500000.
M_SALUDO, M_JOB_ACTUAL, M_CARGAS, M_ENCARGO, M_FENCE, M_EN_CAMINO = 300001, 300002, 300003, 300004, 300005, 300006
OP_TRADER, OP_HUNTER, OP_THIEF, OP_DEJAR = 300010, 300011, 300012, 300013
OP_ENCARGO, OP_ENTREGAR, OP_FENCE, OP_SALIR = 300014, 300015, 300016, 300019
OP_GRAIN, OP_SILK, OP_GEM = 300020, 300021, 300022
TEXTOS = {
    M_SALUDO: 'Choose your job. You can change it again in 7 days.',
    M_JOB_ACTUAL: 'You are a %1. What do you want to do?',
    M_CARGAS: 'Choose a cargo. You pay for it now and get your gold back with a profit when you deliver it.',
    M_ENCARGO: 'Deliver the %1 to %2 within %3 minutes.',
    M_EN_CAMINO: 'Your %1 goes to %2. Time left: %3.',
    M_FENCE: 'Got something that is not yours? I pay well for stolen cargo, and nobody asks questions.',
    OP_FENCE: 'Sell the stolen cargo',
    OP_TRADER: 'Become a Trader', OP_HUNTER: 'Become a Hunter', OP_THIEF: 'Become a Thief',
    OP_DEJAR: 'Quit my job', OP_ENCARGO: 'Take a cargo order', OP_ENTREGAR: 'Deliver my cargo', OP_SALIR: 'Leave',
    OP_GRAIN: 'Grain Cargo (500,000 gold, 20 min)', OP_SILK: 'Silk Cargo (2,000,000 gold, 25 min)',
    OP_GEM: 'Gem Cargo (5,000,000 gold, 30 min)',
}
OPCIONES = frozenset((OP_TRADER, OP_HUNTER, OP_THIEF, OP_DEJAR, OP_ENCARGO, OP_ENTREGAR, OP_FENCE, OP_SALIR,
                      OP_GRAIN, OP_SILK, OP_GEM))
OP_A_JOB = {OP_TRADER: TRADER, OP_HUNTER: HUNTER, OP_THIEF: THIEF}
OP_A_CARGA = {OP_GRAIN: GRAIN, OP_SILK: SILK, OP_GEM: GEM}
RETRATO = 2

# Los encargos activos, por char_id del Trader que la compro. SE GUARDAN EN DISCO (data/trade_routes.json): cada
# subida reinicia el servidor y, solo en memoria, la carga se borraba de la mochila y el Trader perdia lo invertido
# (hasta 5M). Al arrancar se restauran sumando a sus relojes el tiempo que el servidor estuvo apagado.
_ENCARGOS = {}
_ARCHIVO = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'trade_routes.json'
GUARDAR_CADA = 10                 # segundos: para saber cuanto estuvo apagado
_ULTIMO_GUARDADO = [0.0]


def guardar(ahora=None):
    ahora = ahora or time.time()
    _ULTIMO_GUARDADO[0] = ahora
    try:
        _ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        tmp = _ARCHIVO.with_suffix('.tmp')
        tmp.write_text(json.dumps({'guardado_en': ahora, 'encargos': list(_ENCARGOS.values())}), encoding='utf-8')
        os.replace(tmp, _ARCHIVO)
    except Exception:
        log.exception('trade routes: no se pudo guardar %s', _ARCHIVO)


def cargar(ahora=None):
    """Restaura los encargos del disco, con el tiempo apagado sumado a sus relojes."""
    ahora = ahora or time.time()
    _ENCARGOS.clear()
    try:
        d = json.loads(_ARCHIVO.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return 0
    apagado = max(0.0, ahora - float(d.get('guardado_en') or ahora))
    for e in d.get('encargos') or []:
        e['fin'] = float(e['fin']) + apagado
        s = e.get('suelo')
        if s:
            s['hasta'] = float(s['hasta']) + apagado
            if s.get('libre_para_el'):
                s['libre_para_el'] = float(s['libre_para_el']) + apagado
        _ENCARGOS[int(e['trader'])] = e
    if _ENCARGOS:
        log.info('trade routes: %d encargos restaurados (%.0f s apagado)', len(_ENCARGOS), apagado)
    return len(_ENCARGOS)


# --------------------------------------------------------------------------------------------------- jobs
def _cont(p):
    c = getattr(p, 'logros_cont', None)
    if not isinstance(c, dict):
        c = {}
        p.logros_cont = c
    return c


def _listo(ses):
    """Los logros_cont (donde va el job) se cargan de la ficha la primera vez que se piden (app._logros_datos). Al
    volver a entrar se miraba el job antes de cargarlos y parecia perdido ("si me salgo debo mantener el job", 06/11)."""
    p = getattr(ses, 'personaje', None)
    if p is not None and not getattr(p, '_logros_cargado', False) and getattr(ses, 'usuario', None):
        try:
            import app
            app._logros_datos(ses)
        except Exception:
            log.debug('cargar logros', exc_info=True)


def job_de(p) -> int:
    return int(_cont(p).get(CLAVE_JOB) or 0) if p else 0


def espera_cambio(p, ahora=None) -> int:
    """Segundos que faltan para poder ELEGIR otro job: 7 dias desde que eligio el ultimo (0 si nunca tuvo). Dejarlo
    se puede siempre ("no me deja quitar el job", 06/11/2026), pero no reinicia la cuenta: dejar y volver a elegir
    no se salta la espera."""
    desde = float(_cont(p).get(CLAVE_DESDE) or 0)
    if not desde:
        return 0
    return max(0, int(desde + SEGUNDOS_CAMBIO - (ahora or time.time())))


def texto_espera(segundos: int) -> str:
    d, h = segundos // 86400, (segundos % 86400) // 3600
    return 'You can change your job again in %d days %d hours.' % (d, h)


def poner_job(ses, job: int, ahora=None, forzar=False):
    """(ok, mensaje). job 0 deja el job. Con encargo activo no se cambia."""
    _listo(ses)
    p = ses.personaje
    ahora = ahora or time.time()
    if encargo_de(ses) or lleva_carga(ses):
        return False, 'You cannot change your job while carrying cargo.'
    if job == job_de(p):
        return False, 'You are already a %s.' % NOMBRE_JOB.get(job, 'nobody') if job else 'You have no job.'
    # Volver al MISMO job que se dejo no espera: los 7 dias son para cambiar a otro distinto ("me quite el job y no me
    # deja volver a serlo; no me lo cambie, solo me quite el traje", 06/11/2026).
    # (Quien lo dejo antes de guardar el ultimo job no tiene CLAVE_ULTIMO: se le deja elegir sin esperar.)
    _c = _cont(p)
    mismo = bool(job) and (job == int(_c.get(CLAVE_ULTIMO) or 0)
                           or (CLAVE_ULTIMO not in _c and CLAVE_DESDE in _c and not job_de(p)))
    falta = 0 if (forzar or not job or mismo) else espera_cambio(p, ahora)
    if falta:
        return False, texto_espera(falta)
    c = _cont(p)
    if job:
        if not mismo or CLAVE_DESDE not in c:
            c[CLAVE_DESDE] = int(ahora)
        c[CLAVE_JOB] = c[CLAVE_ULTIMO] = int(job)
        return True, 'You are now a %s.' % NOMBRE_JOB[job]
    c[CLAVE_ULTIMO] = job_de(p)
    c.pop(CLAVE_JOB, None)
    return True, 'You quit your job.'


def anunciar_job(ses):
    """A todos los conectados: quien acaba de tomar un job ("que de un aviso cuando una persona se una a un job",
    06/11/2026)."""
    job = job_de(ses.personaje)
    if not job:
        return
    texto = '%s is now a %s!' % (ses.personaje.nombre, NOMBRE_JOB[job])
    for s in _sesiones() or [ses]:
        aviso(s, texto)


def pd_de(ses) -> dict:
    """{casilla de fashion: item} de la PD de su job, o {} sin job."""
    _listo(ses)
    p = getattr(ses, 'personaje', None)
    job = job_de(p)
    if not job:
        return {}
    ap = getattr(p, 'apariencia', None)
    hombre = bool(ap) and bool(int(ap[0]) & 1)
    return dict(PD[job][hombre])


def fashion_bloqueada(ses, ranura) -> bool:
    """Con job no se toca la fashion: lleva la PD del job hasta dejarlo."""
    return bool(job_de(getattr(ses, 'personaje', None))) and int(ranura) in CASILLAS_FASHION


# ----------------------------------------------------------------------------------------------- grupo / IP
def ip_de(ses):
    a = getattr(ses, 'addr', None)
    return a[0] if isinstance(a, (tuple, list)) and a else a


def ips_repetidas(sesiones) -> bool:
    """Si entre los que tienen job hay dos de la misma IP."""
    vistas = set()
    for s in sesiones:
        if not job_de(getattr(s, 'personaje', None)):
            continue
        ip = ip_de(s)
        if ip in vistas:
            return True
        vistas.add(ip)
    return False


def _grupo(ses):
    try:
        import equipos
        g = equipos.grupo_de(ses)
    except Exception:
        g = []
    return g or [ses]


# ----------------------------------------------------------------------------------------------- encargos
def encargo_de(ses):
    p = getattr(ses, 'personaje', None)
    return _ENCARGOS.get(getattr(p, 'char_id', None)) if p else None


def encargo_que_lleva(ses):
    """El encargo cuya carga lleva ahora este jugador (Trader, Hunter que la recupero o Thief que la robo)."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return None
    return next((e for e in _ENCARGOS.values() if e.get('portador') == p.char_id), None)


def _sesiones():
    try:
        import app
        return [s for s in app._tw_sesiones() if getattr(s, 'personaje', None)]
    except Exception:
        return []


def _sesion(char_id):
    return next((s for s in _sesiones() if s.personaje.char_id == char_id), None)


def item_carga_en(ses):
    """(ranura, item) del objeto de carga que lleva, o (None, None)."""
    for r, it in (getattr(ses, 'inventario', None) or {}).items():
        if int(it or 0) in ITEMS_CARGA:
            return r, int(it)
    return None, None


def lleva_carga(ses) -> bool:
    return item_carga_en(ses)[0] is not None


def montado(ses) -> bool:
    return bool((getattr(ses, 'inventario', None) or {}).get(RANURA_MONTURA))


def factor_velocidad(ses) -> float:
    return FACTOR_CON_CARGA if lleva_carga(ses) else 1.0


def bloquea_teleport(ses):
    """El texto si no puede teletransportarse (lleva carga), o None."""
    return 'You cannot teleport while carrying cargo.' if lleva_carga(ses) else None


def destino_para(stage_salida, rng=None):
    rng = rng or random
    return rng.choice(sorted(s for s in CIUDADES if s != int(stage_salida)))


def aceptar(ses, tipo: int, ahora=None, rng=None):
    """(ok, mensaje) del Trader que compra una carga en el Guild Clerk de su ciudad."""
    _listo(ses)
    import app
    p = ses.personaje
    ahora = ahora or time.time()
    c = CARGAS.get(int(tipo))
    if not c:
        return False, 'Unknown cargo.'
    if job_de(p) != TRADER:
        return False, 'Only Traders can take cargo orders.'
    if int(p.stage) not in CIUDADES:
        return False, 'Cargo orders are taken in the cities.'
    if encargo_de(ses) or lleva_carga(ses):
        return False, 'You already have a cargo order.'
    if not montado(ses):
        return False, 'You must be riding a mount to carry cargo.'
    if ips_repetidas(_grupo(ses)):
        return False, 'Two characters with a job from the same IP cannot be in the same party.'
    if int(getattr(ses, 'oro', 0) or 0) < c['precio']:
        return False, 'You need %s gold to buy the %s.' % (format(c['precio'], ','), c['nombre'])
    res = app._gm_dar_item(ses, c['item'], 1)
    if not res.startswith('dado'):
        return False, 'You need a free slot in your bag.' if 'llena' in res else 'The cargo is not available.'
    _cambiar_oro(ses, -c['precio'])
    destino = destino_para(p.stage, rng)
    _ENCARGOS[p.char_id] = dict(tipo=int(tipo), trader=p.char_id, nombre=p.nombre, salida=int(p.stage),
                                destino=destino, fin=ahora + c['minutos'] * 60, ip=ip_de(ses),
                                portador=p.char_id, suelo=None, robada_en=None)
    guardar()
    refrescar_marcas(ses)
    log.info('%s compra %s por %d: de %s a %s', p.nombre, c['nombre'], c['precio'],
             CIUDADES[int(p.stage)], CIUDADES[destino])
    return True, 'Deliver the %s to %s within %d minutes.' % (c['nombre'], CIUDADES[destino], c['minutos'])


def _de_su_grupo(ses, e):
    """Si `ses` es el Trader del encargo o esta en su grupo."""
    p = ses.personaje
    if p.char_id == e['trader']:
        return True
    return any(getattr(s, 'personaje', None) and s.personaje.char_id == e['trader'] for s in _grupo(ses))


def entregar(ses, ahora=None, rng=None):
    """(ok, mensajes) al entregar la carga en el Guild Clerk de la ciudad de destino (el Trader o un Hunter de su
    grupo que la recupero). Cobra el Trader (lo invertido y la ganancia) y los Hunters del grupo en el mapa."""
    rng = rng or random
    p = ses.personaje
    ahora = ahora or time.time()
    e = encargo_que_lleva(ses)
    ranura, item = item_carga_en(ses)
    if not e or ranura is None:
        return False, ['You have no cargo to deliver.']
    if job_de(p) == THIEF or not _de_su_grupo(ses, e):
        return False, ['This cargo is not yours. The Fence buys stolen cargo.']
    c = CARGAS[e['tipo']]
    if ahora > e['fin']:
        expirar(ses, e)
        return False, ['Time is up. The cargo was lost.']
    if int(p.stage) != e['destino']:
        return False, ['This cargo goes to %s.' % CIUDADES[e['destino']]]
    if ips_repetidas(_grupo(ses)):
        return False, ['Two characters with a job from the same IP cannot be in the same party.']
    _quitar_carga(ses, ranura)
    _ENCARGOS.pop(e['trader'], None)
    guardar()
    refrescar_marcas(ses)
    trader = ses if p.char_id == e['trader'] else _sesion(e['trader'])
    ganancia = rng.randint(*c['ganancia'])
    pago = c['precio'] + ganancia
    msgs = []
    if trader is not None:
        _cambiar_oro(trader, pago)
        _dar_vale(trader, rng)
        texto = 'Cargo delivered! You received %s gold.' % format(pago, ',')
        if trader is ses:
            msgs.append(texto)
        else:
            aviso(trader, texto)
    hunters = [s for s in _grupo(ses)
               if s is not trader and job_de(getattr(s, 'personaje', None)) == HUNTER
               and getattr(getattr(s, 'personaje', None), 'stage', None) == p.stage
               and ip_de(s) != e['ip']]
    if hunters:
        parte = c['hunters'] // len(hunters)
        for h in hunters:
            _cambiar_oro(h, parte)
            _dar_vale(h, rng)
            texto = 'Cargo delivered! You received %s gold.' % format(parte, ',')
            if h is ses:
                msgs.append(texto)
            else:
                aviso(h, texto)
    log.info('%s entrega %s en %s: %d al trader, %d hunters', p.nombre, c['nombre'], CIUDADES[p.stage], pago,
             len(hunters))
    return True, msgs or ['Cargo delivered!']


def entregar_fence(ses, ahora=None, rng=None):
    """(ok, mensajes) del Thief que vende la carga robada al Fence. No en el mapa donde la robo."""
    rng = rng or random
    p = ses.personaje
    ahora = ahora or time.time()
    e = encargo_que_lleva(ses)
    ranura, _ = item_carga_en(ses)
    if not e or ranura is None or job_de(p) != THIEF:
        return False, ['You have no stolen cargo.']
    if ahora > e['fin']:
        expirar(ses, e)
        return False, ['Time is up. The cargo was lost.']
    if int(p.stage) not in FENCES:
        return False, ['There is no Fence here.']
    if int(p.stage) == e.get('robada_en'):
        return False, ['Too hot to sell here. Take it to another Fence.']
    c = CARGAS[e['tipo']]
    _quitar_carga(ses, ranura)
    _ENCARGOS.pop(e['trader'], None)
    guardar()
    refrescar_marcas(ses)
    _cambiar_oro(ses, c['thief'])
    _dar_vale(ses, rng)
    trader = _sesion(e['trader'])
    if trader is not None:
        aviso(trader, 'The cargo was stolen!')
    log.info('%s vende al Fence la %s de %s en %s', p.nombre, c['nombre'], e['nombre'], FENCES[int(p.stage)])
    return True, ['The Fence paid you %s gold.' % format(c['thief'], ',')]


# ----------------------------------------------------------------------------------------------- la carga en el suelo
def _paquete_suelo(e):
    import login
    return login._map_object_spawn(ENTIDAD_SUELO + e['trader'], CARGAS[e['tipo']]['suelo'], tuple(e['suelo']['tile']))


def _quitar_suelo_paquete(e):
    import struct
    return struct.pack('<HIB', 0x0007, (ENTIDAD_SUELO + e['trader']) & 0xFFFFFFFF, 1)


def _en_mapa(stage):
    try:
        import presencia
        return [s for lista in list(presencia._POR_MAPA.values()) for s in list(lista)
                if getattr(getattr(s, 'personaje', None), 'stage', None) == int(stage)]
    except Exception:
        return []


def _a_todos(stage, *paquetes):
    for s in _en_mapa(stage):
        try:
            s.enviar(*paquetes)
        except Exception:
            log.debug('envio al mapa', exc_info=True)


def soltar(ses, ahora=None):
    """Muerte o desconexion: la carga cae donde estaba el portador, 5 minutos."""
    ahora = ahora or time.time()
    ranura, _ = item_carga_en(ses)
    e = encargo_que_lleva(ses)
    if ranura is None:
        return False
    _quitar_carga(ses, ranura)
    if not e:
        return False
    p = ses.personaje
    e['portador'] = None
    # Quien la suelta no la vuelve a coger en BLOQUEO_RECOGER: al desconectarse y volver a entrar en el mismo sitio,
    # el primer paso la recogia otra vez y parecia que no habia caido ("me sali del juego y no se cayo", 06/11/2026).
    e['suelo'] = dict(stage=int(p.stage), tile=[int(p.tile_x), int(p.tile_y)], hasta=ahora + SUELO_SEGUNDOS,
                      solto=p.char_id, libre_para_el=ahora + BLOQUEO_RECOGER)
    guardar()
    _a_todos(p.stage, _paquete_suelo(e))
    refrescar_marcas(ses)
    log.info('cae la %s de %s en %s %s', CARGAS[e['tipo']]['nombre'], e['nombre'], p.stage, e['suelo']['tile'])
    return True


RANGO_CLIC = 3                    # casillas desde las que un clic en la carga del suelo la recoge


def por_que_no(ses, e, ahora=None):
    """El motivo por el que `ses` no puede recoger la carga del suelo de `e`, o '' si puede."""
    ahora = ahora or time.time()
    p = ses.personaje
    s = e.get('suelo') or {}
    if getattr(ses, 'muerto', False):
        return 'You cannot pick it up while dead.'
    if lleva_carga(ses):
        return 'You already carry cargo.'
    if s.get('solto') == p.char_id and ahora < s.get('libre_para_el', 0):
        return 'You dropped this cargo. You can pick it up again in %d s.' % (s['libre_para_el'] - ahora + 1)
    job = job_de(p)
    if not job:
        return 'Only Traders, Hunters and Thieves can pick up cargo.'
    if job == THIEF:
        if ip_de(ses) == e['ip']:
            return 'You cannot steal cargo from a Trader of your own IP.'
    elif not _de_su_grupo(ses, e):
        return 'This cargo belongs to another Trader. Only a Thief can take it.'
    if not montado(ses):
        return 'You must be riding a mount to carry cargo.'
    return ''


def pulsar(ses, entidad, ahora=None):
    """Clic en la carga del suelo (objeto ENTIDAD_SUELO + trader): la recoge si esta cerca y puede; si no, dice por
    que ("ahora lo veo pero no lo puedo recoger", 06/11/2026). False si la entidad no es una carga."""
    e = _ENCARGOS.get(int(entidad) - ENTIDAD_SUELO)
    if not e or not e.get('suelo'):
        return False
    p = ses.personaje
    s = e['suelo']
    if s['stage'] != int(p.stage):
        return False
    if max(abs(p.tile_x - s['tile'][0]), abs(p.tile_y - s['tile'][1])) > RANGO_CLIC:
        aviso(ses, 'Get closer to pick up the cargo.')
        return True
    motivo = por_que_no(ses, e, ahora)
    if motivo:
        aviso(ses, motivo)
        return True
    _recoger(ses, e)
    return True


def contacto(ses, ahora=None):
    """Al acabar un paso: si hay una carga en el suelo a 1 casilla y puede llevarla, la recoge."""
    ahora = ahora or time.time()
    p = getattr(ses, 'personaje', None)
    if not p or getattr(ses, 'muerto', False) or lleva_carga(ses):
        return False
    for e in list(_ENCARGOS.values()):
        s = e.get('suelo')
        if not s or s['stage'] != int(p.stage):
            continue
        if max(abs(p.tile_x - s['tile'][0]), abs(p.tile_y - s['tile'][1])) > 1:
            continue
        motivo = por_que_no(ses, e, ahora)
        if motivo:
            if 'mount' in motivo:
                aviso(ses, motivo)
            continue
        return _recoger(ses, e)
    return False


def _recoger(ses, e):
    p = ses.personaje
    import app
    res = app._gm_dar_item(ses, CARGAS[e['tipo']]['item'], 1)
    if not res.startswith('dado'):
        aviso(ses, 'You need a free slot in your bag.')
        return False
    _a_todos(p.stage, _quitar_suelo_paquete(e))
    e['suelo'] = None
    e['portador'] = p.char_id
    guardar()
    nombre = CARGAS[e['tipo']]['nombre']
    if job_de(p) == THIEF:
        e['robada_en'] = int(p.stage)
        aviso(ses, 'You picked up the %s. Bring it to the Fence.' % nombre)
        trader = _sesion(e['trader'])
        if trader is not None and trader is not ses:
            aviso(trader, 'The cargo was stolen!')
    else:
        aviso(ses, 'The cargo was recovered!')
    refrescar_marcas(ses)
    log.info('%s recoge la %s de %s', p.nombre, nombre, e['nombre'])
    return True


def al_entrar_mapa(ses):
    """Al llegar a un mapa: las cargas que hay en su suelo y las marcas del evento."""
    _listo(ses)
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    paquetes = [_paquete_suelo(e) for e in _ENCARGOS.values()
                if e.get('suelo') and e['suelo']['stage'] == int(p.stage)]
    if paquetes:
        ses.enviar(*paquetes)
    if any(e.get('portador') for e in _ENCARGOS.values()):
        refrescar_marcas(ses)
    # LA PD DEL JOB OTRA VEZ, un momento despues: al cargar el mapa el cliente recibe el inventario y vuelve a pintar
    # la fashion de verdad ("se pierde el traje de trader al pasar de mapa", 06/11/2026).
    # Ya al entrar (antes solo a 1 s y se veia el salto: "hace como 1 salto de 2 seg y luego le sale el traje",
    # 06/11/2026), y otra vez a RETRASO_PD por si el cliente la tapa al acabar de cargar.
    if job_de(p):
        import app
        try:
            app._trade_routes_vestir(ses)
        except Exception:
            log.debug('vestir la PD al entrar', exc_info=True)
        try:
            import asyncio
            asyncio.get_event_loop().call_later(RETRASO_PD, lambda: app._trade_routes_vestir(ses)
                                                if getattr(ses, 'personaje', None) else None)
        except RuntimeError:
            pass


def expirar(ses, e=None):
    """Se acabo el tiempo (o el GM la cancela): la carga desaparece, este donde este, y nadie cobra."""
    e = e or encargo_que_lleva(ses) or encargo_de(ses)
    if e:
        _perder(e, avisar=False)
    ranura, _ = item_carga_en(ses)
    if ranura is not None:
        _quitar_carga(ses, ranura)
        refrescar_marcas(ses)


def _perder(e, avisar=True, conocida=None):
    _ENCARGOS.pop(e['trader'], None)
    guardar()
    cid = getattr(getattr(conocida, 'personaje', None), 'char_id', None)
    _buscar = lambda c: conocida if (c is not None and c == cid) else _sesion(c)
    if e.get('suelo'):
        _a_todos(e['suelo']['stage'], _quitar_suelo_paquete(e))
        e['suelo'] = None
    portador = _buscar(e['portador']) if e.get('portador') else None
    if portador is not None:
        ranura, _ = item_carga_en(portador)
        if ranura is not None:
            _quitar_carga(portador, ranura)
            refrescar_marcas(portador)
        if avisar:
            aviso(portador, 'Time is up. The cargo was lost.')
    trader = _buscar(e['trader'])
    if avisar and trader is not None and trader is not portador:
        aviso(trader, 'Time is up. The cargo was lost.')


def tick(ses, ahora=None):
    """Cada segundo, por jugador: los encargos caducados o en el suelo mas de 5 minutos se pierden; y una carga que ya
    no tiene encargo (reinicio del servidor) desaparece."""
    ahora = ahora or time.time()
    if _ENCARGOS and ahora - _ULTIMO_GUARDADO[0] >= GUARDAR_CADA:
        guardar(ahora)
    for e in list(_ENCARGOS.values()):
        if ahora > e['fin'] or (e.get('suelo') and ahora > e['suelo']['hasta']):
            _perder(e, conocida=ses)
    recordatorios(ses, ahora)
    if lleva_carga(ses) and not encargo_que_lleva(ses):
        ranura, _ = item_carga_en(ses)
        _quitar_carga(ses, ranura)
        refrescar_marcas(ses)
        aviso(ses, 'Time is up. The cargo was lost.')


# ----------------------------------------------------------------------------------------------- PvP del evento
def motivo_pvp(ses, otro):
    """'' si el evento deja que `ses` le pegue a `otro`; None si el evento no dice nada (siguen las otras reglas)."""
    p, q = getattr(ses, 'personaje', None), getattr(otro, 'personaje', None)
    if (not p or not q or int(p.stage) in ZONAS_SEGURAS or getattr(ses, 'muerto', False)
            or getattr(otro, 'muerto', False)):
        return None
    deja = puede_atacar(ses, otro)
    if job_de(p) and job_de(q):
        log.info('PvP del evento %s (%s) -> %s (%s) en %s: %s', p.nombre, NOMBRE_JOB[job_de(p)], q.nombre,
                 NOMBRE_JOB[job_de(q)], p.stage, 'SI' if deja else 'no (sin carga de por medio)')
    return '' if deja else None


def puede_atacar(ses, otro) -> bool:
    _listo(ses)
    _listo(otro)
    a, b = job_de(ses.personaje), job_de(otro.personaje)
    if a == THIEF:
        if encargo_que_lleva(otro) and b in (TRADER, HUNTER):
            return True
        # Los Hunters del grupo del que lleva la carga, en el mismo mapa
        if b == HUNTER:
            return any(encargo_que_lleva(s) and job_de(s.personaje) in (TRADER, HUNTER)
                       and s.personaje.stage == otro.personaje.stage for s in _grupo(otro) if s is not otro)
        return False
    if a in (TRADER, HUNTER) and b == THIEF:
        return encargo_que_lleva(otro) is not None
    return False


def _hostil(eid, activo):
    """Lo que hace atacable a un jugador en el cliente, como en Arena (competiciones.marcas_actor, daily_events.marcas):
    el modo arena (36) y la marca hostil (42). Con la 42 sola el cliente no dejaba ni seleccionarlo ("siguen sin poder
    targetearme", 06/11/2026)."""
    import struct
    import competiciones
    return (competiciones.modo_arena(eid, activo), struct.pack('<HIBBII', 0x001D, eid, 1, 42, eid, int(bool(activo))))


def _mapa_de_competicion(stage):
    try:
        st = int(stage or 0)
        return (st in __import__('competiciones').MAPAS or st in __import__('daily_events').STAGES
                or st in __import__('league_war').STAGES)
    except Exception:
        return False


def marcas_para(visor, sujeto):
    """Lo que `visor` tiene que saber de `sujeto`: el aro si lleva carga y que es atacable si puede atacarle."""
    import holy_battlefield as hb
    import presencia
    if (visor is sujeto or int(getattr(sujeto.personaje, 'stage', 0) or 0) in ZONAS_SEGURAS
            or _mapa_de_competicion(sujeto.personaje.stage)):
        return ()
    eid = presencia.entidad_de(sujeto)
    out = []
    if lleva_carga(sujeto):
        out.append(hb.equipo(eid, AURA_CARGA))
    if puede_atacar(visor, sujeto):
        out.extend(_hostil(eid, True))
    return tuple(out)


def refrescar_marcas(ses):
    """Tras coger, soltar o entregar la carga: a todos los del mapa, las marcas de todos (son pocos jugadores)."""
    import struct
    import holy_battlefield as hb
    import presencia
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    if _mapa_de_competicion(p.stage):
        return                      # alli mandan las marcas de la competicion
    gente = _en_mapa(p.stage)
    if ses not in gente:
        gente.append(ses)
    seguro = int(p.stage) in ZONAS_SEGURAS
    for visor in gente:
        ataca = False
        for sujeto in gente:
            if sujeto is visor:
                continue
            try:
                eid = presencia.entidad_de(sujeto)
                base = (hb.equipo(eid, 0),) + _hostil(eid, False)
                marcas = marcas_para(visor, sujeto)
                ataca = ataca or any(m[6:8] == bytes((1, 36)) for m in marcas)
                # Por presencia._mandar: la 42 tiene que llevar de cabecera el jugador LOCAL de quien la recibe
                # (para_receptor). Mandada tal cual, el cliente la tiraba y no dejaba seleccionar al objetivo;
                # solo funcionaba tras volver a entrar, porque la presentacion si pasa por _mandar (06/11/2026).
                presencia._mandar(visor, *base, *marcas)
            except Exception:
                log.debug('marcas de trade routes', exc_info=True)
        # Y el propio cliente del que puede atacar, en modo arena: sin el no apunta a jugadores.
        try:
            yo = visor.personaje.entity_id
            visor.enviar(*_hostil(yo, ataca and not seguro))
        except Exception:
            log.debug('modo arena propio', exc_info=True)
    try:
        ses.enviar(hb.equipo(p.entity_id, AURA_CARGA if (lleva_carga(ses) and not seguro) else 0), icono(ses))
    except Exception:
        log.debug('aro propio', exc_info=True)


def restante(e, ahora=None) -> int:
    return max(0, int(e['fin'] - (ahora or time.time())))


def texto_restante(segundos: int) -> str:
    m, s = divmod(int(segundos), 60)
    return '%d min %02d s' % (m, s)


def icono(ses, ahora=None):
    """El 0x001D del icono de la carga con su cuenta atras (0 lo quita)."""
    import struct
    e = encargo_que_lleva(ses) if lleva_carga(ses) else None
    ms = restante(e, ahora) * 1000 if e else 0
    return struct.pack('<HIBBII', 0x001D, ses.personaje.entity_id, 1, 4, MAGIA_CARGA, ms)


def recordatorios(ses, ahora=None):
    """Los avisos de 10, 5 y 1 minuto al que lleva la carga (cada uno una vez)."""
    e = encargo_que_lleva(ses)
    if not e or not lleva_carga(ses):
        return
    queda = restante(e, ahora)
    hechos = e.setdefault('avisos', [])
    for m in AVISOS_MINUTOS:
        if queda <= m * 60 and m not in hechos:
            hechos.extend(x for x in AVISOS_MINUTOS if x >= m and x not in hechos)
            destino = (FENCES if job_de(ses.personaje) == THIEF else CIUDADES)
            sitio = 'a Fence' if destino is FENCES else CIUDADES[e['destino']]
            aviso(ses, '%s: %d minute%s left to reach %s.' % (CARGAS[e['tipo']]['nombre'], m, '' if m == 1 else 's', sitio))
            break


# ----------------------------------------------------------------------------------------------- oro y objetos
def aviso(ses, texto):
    import clases
    try:
        ses.enviar(clases.aviso(texto, tipo=0))
    except Exception:
        log.debug('aviso', exc_info=True)


def _cambiar_oro(ses, delta):
    import app
    import cuentas
    ses.oro = max(0, int(getattr(ses, 'oro', 0) or 0) + int(delta))
    if getattr(ses, 'personaje', None):
        ses.personaje.oro = ses.oro
    try:
        ses.enviar(*app._refrescar(ses, [], con_oro=True))
    except Exception:
        log.debug('refresco del oro', exc_info=True)
    if getattr(ses, 'usuario', None):
        cuentas.guardar_oro(ses.usuario, ses.personaje.char_id, ses.oro)


def _dar_vale(ses, rng):
    import app
    app._gm_dar_item(ses, rng.choice(VALES), 1)


def _quitar_carga(ses, ranura):
    import app
    ses.inventario.pop(ranura, None)
    getattr(ses, 'cantidades', {}).pop(ranura, None)
    try:
        ses.enviar(*app._refrescar(ses, [ranura]))
        app._guardar_bolsa(ses, ses.personaje.char_id)
    except Exception:
        log.debug('quitar la carga', exc_info=True)


# ----------------------------------------------------------------------------------------------- dialogo
def _linea(mid, opts=None, cadenas=None):
    import dialogos
    return dialogos.armar_linea(mid, RETRATO, list(opts or []), strings=list(cadenas or []))


def saludo(ses):
    """El 0x0012 del Guild Clerk segun el job del jugador."""
    _listo(ses)
    p = ses.personaje
    job = job_de(p)
    if not job:
        return _linea(M_SALUDO, [OP_TRADER, OP_HUNTER, OP_THIEF, OP_SALIR])
    e = encargo_que_lleva(ses) if lleva_carga(ses) else None
    if e and job in (TRADER, HUNTER):
        return _linea(M_EN_CAMINO, [OP_ENTREGAR, OP_SALIR],
                      ['1', CARGAS[e['tipo']]['nombre'], '2', CIUDADES[e['destino']], '3',
                       texto_restante(restante(e))])
    opts = []
    if job == TRADER:
        opts.append(OP_ENTREGAR if (encargo_de(ses) or lleva_carga(ses)) else OP_ENCARGO)
    opts += [o for j, o in ((TRADER, OP_TRADER), (HUNTER, OP_HUNTER), (THIEF, OP_THIEF)) if j != job]
    opts += [OP_DEJAR, OP_SALIR]
    return _linea(M_JOB_ACTUAL, opts, ['1', NOMBRE_JOB[job]])


def saludo_fence(ses):
    _listo(ses)
    return _linea(M_FENCE, [OP_FENCE, OP_SALIR])


def opcion(ses, op: int, ahora=None, rng=None):
    """(paquetes 0x0012 o None para cerrar, avisos) de una opcion del Guild Clerk."""
    _listo(ses)
    if op == OP_SALIR:
        return None, []
    if op in OP_A_JOB or op == OP_DEJAR:
        ok, msg = poner_job(ses, OP_A_JOB.get(op, 0), ahora)
        return None, [msg]
    if op == OP_ENCARGO:
        return _linea(M_CARGAS, [OP_GRAIN, OP_SILK, OP_GEM, OP_SALIR]), []
    if op in OP_A_CARGA:
        ok, msg = aceptar(ses, OP_A_CARGA[op], ahora, rng)
        return None, [msg]
    if op == OP_FENCE:
        ok, msgs = entregar_fence(ses, ahora, rng)
        return None, msgs
    if op == OP_ENTREGAR:
        ok, msgs = entregar(ses, ahora, rng)
        return None, msgs
    return None, []


def info():
    """Para /caravana info."""
    ahora = time.time()
    if not _ENCARGOS:
        return 'No active cargo orders.'
    return ' | '.join('%s: %s to %s, %d s left' % (e['nombre'], CARGAS[e['tipo']]['nombre'], CIUDADES[e['destino']],
                                                     max(0, int(e['fin'] - ahora))) for e in _ENCARGOS.values())


def cancelar(char_id):
    hubo = _ENCARGOS.pop(int(char_id), None) is not None
    guardar()
    return hubo


cargar()
