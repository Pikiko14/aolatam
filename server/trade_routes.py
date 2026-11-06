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
  * Pendiente (fase 3): la carga cae al morir o desconectarse, los Thieves la roban y la llevan al Fence (4 mapas;
    robada en uno de ellos no se entrega en ese mismo), PvP del evento y aro morado.
"""
import logging
import random
import time

log = logging.getLogger('trade_routes')

TRADER, HUNTER, THIEF = 1, 2, 3
NOMBRE_JOB = {TRADER: 'Trader', HUNTER: 'Hunter', THIEF: 'Thief'}
CLAVE_JOB, CLAVE_DESDE = 'trade_job', 'trade_job_desde'      # en personaje.logros_cont (se guarda con los logros)
DIAS_CAMBIO = 7
SEGUNDOS_CAMBIO = DIAS_CAMBIO * 86400

CIUDADES = {3: 'Aurora City', 26: 'Dark City', 29: 'Breeze Woods', 38: 'Iron Castle'}
FENCES = {8: 'Crashing Hillock', 30: 'Cryptic Moon Swamp', 25: 'Fungus Forest North', 39: 'Cactus Plain'}
NPC_CLERK, NPC_FENCE = 'Guild Clerk', 'Fence'

RANURA_MONTURA = 10
FACTOR_CON_CARGA = 0.5          # 50% mas lento con carga, montado o a pie

# Las cargas: objeto propio (item9, cliente_local), precio, minutos, ganancia del Trader al azar, bolsa de los Hunters
# (se reparte entre ellos) y lo que gana el Thief que la entrega en el Fence.
GRAIN, SILK, GEM = 1, 2, 3
CARGAS = {
    GRAIN: dict(nombre='Grain Cargo', item=89074, icono=5146, precio=500_000, minutos=20,
                ganancia=(100_000, 300_000), hunters=500_000, thief=250_000),
    SILK: dict(nombre='Silk Cargo', item=89075, icono=5729, precio=2_000_000, minutos=25,
               ganancia=(300_000, 600_000), hunters=1_000_000, thief=500_000),
    GEM: dict(nombre='Gem Cargo', item=89076, icono=8731, precio=5_000_000, minutos=30,
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
M_SALUDO, M_JOB_ACTUAL, M_CARGAS, M_ENCARGO = 300001, 300002, 300003, 300004
OP_TRADER, OP_HUNTER, OP_THIEF, OP_DEJAR = 300010, 300011, 300012, 300013
OP_ENCARGO, OP_ENTREGAR, OP_SALIR = 300014, 300015, 300019
OP_GRAIN, OP_SILK, OP_GEM = 300020, 300021, 300022
TEXTOS = {
    M_SALUDO: 'Choose your job. You can change it again in 7 days.',
    M_JOB_ACTUAL: 'You are a %1. What do you want to do?',
    M_CARGAS: 'Choose a cargo. You pay for it now and get your gold back with a profit when you deliver it.',
    M_ENCARGO: 'Deliver the %1 to %2 within %3 minutes.',
    OP_TRADER: 'Become a Trader', OP_HUNTER: 'Become a Hunter', OP_THIEF: 'Become a Thief',
    OP_DEJAR: 'Quit my job', OP_ENCARGO: 'Take a cargo order', OP_ENTREGAR: 'Deliver my cargo', OP_SALIR: 'Leave',
    OP_GRAIN: 'Grain Cargo (500,000 gold, 20 min)', OP_SILK: 'Silk Cargo (2,000,000 gold, 25 min)',
    OP_GEM: 'Gem Cargo (5,000,000 gold, 30 min)',
}
OPCIONES = frozenset((OP_TRADER, OP_HUNTER, OP_THIEF, OP_DEJAR, OP_ENCARGO, OP_ENTREGAR, OP_SALIR,
                      OP_GRAIN, OP_SILK, OP_GEM))
OP_A_JOB = {OP_TRADER: TRADER, OP_HUNTER: HUNTER, OP_THIEF: THIEF}
OP_A_CARGA = {OP_GRAIN: GRAIN, OP_SILK: SILK, OP_GEM: GEM}
RETRATO = 2

# Los encargos activos, por char_id del Trader que la compro.
_ENCARGOS = {}


# --------------------------------------------------------------------------------------------------- jobs
def _cont(p):
    c = getattr(p, 'logros_cont', None)
    if not isinstance(c, dict):
        c = {}
        p.logros_cont = c
    return c


def job_de(p) -> int:
    return int(_cont(p).get(CLAVE_JOB) or 0) if p else 0


def espera_cambio(p, ahora=None) -> int:
    """Segundos que faltan para poder cambiar de job (0 si ya puede o no tiene)."""
    if not job_de(p):
        return 0
    desde = float(_cont(p).get(CLAVE_DESDE) or 0)
    return max(0, int(desde + SEGUNDOS_CAMBIO - (ahora or time.time())))


def texto_espera(segundos: int) -> str:
    d, h = segundos // 86400, (segundos % 86400) // 3600
    return 'You can change your job again in %d days %d hours.' % (d, h)


def poner_job(ses, job: int, ahora=None, forzar=False):
    """(ok, mensaje). job 0 deja el job. Con encargo activo no se cambia."""
    p = ses.personaje
    ahora = ahora or time.time()
    if encargo_de(ses) or lleva_carga(ses):
        return False, 'You cannot change your job while carrying cargo.'
    if job == job_de(p):
        return False, 'You are already a %s.' % NOMBRE_JOB.get(job, 'nobody')
    falta = 0 if forzar else espera_cambio(p, ahora)
    if falta:
        return False, texto_espera(falta)
    c = _cont(p)
    if job:
        c[CLAVE_JOB], c[CLAVE_DESDE] = int(job), int(ahora)
        return True, 'You are now a %s.' % NOMBRE_JOB[job]
    c.pop(CLAVE_JOB, None)
    c[CLAVE_DESDE] = int(ahora)
    return True, 'You quit your job.'


def pd_de(ses) -> dict:
    """{casilla de fashion: item} de la PD de su job, o {} sin job."""
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
                                destino=destino, fin=ahora + c['minutos'] * 60, ip=ip_de(ses))
    log.info('%s compra %s por %d: de %s a %s', p.nombre, c['nombre'], c['precio'],
             CIUDADES[int(p.stage)], CIUDADES[destino])
    return True, 'Deliver the %s to %s within %d minutes.' % (c['nombre'], CIUDADES[destino], c['minutos'])


def entregar(ses, ahora=None, rng=None):
    """(ok, mensajes) al entregar la carga en el Guild Clerk de la ciudad de destino."""
    import app
    rng = rng or random
    p = ses.personaje
    ahora = ahora or time.time()
    e = encargo_de(ses)
    ranura, item = item_carga_en(ses)
    if not e or ranura is None:
        return False, ['You have no cargo to deliver.']
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
    ganancia = rng.randint(*c['ganancia'])
    pago = c['precio'] + ganancia
    _cambiar_oro(ses, pago)
    msgs = ['Cargo delivered! You received %s gold.' % format(pago, ',')]
    _dar_vale(ses, rng)
    hunters = [s for s in _grupo(ses)
               if s is not ses and job_de(getattr(s, 'personaje', None)) == HUNTER
               and getattr(getattr(s, 'personaje', None), 'stage', None) == p.stage
               and ip_de(s) != ip_de(ses)]
    if hunters:
        parte = c['hunters'] // len(hunters)
        for h in hunters:
            _cambiar_oro(h, parte)
            _dar_vale(h, rng)
            aviso(h, 'Cargo delivered! You received %s gold.' % format(parte, ','))
    log.info('%s entrega %s en %s: %d al trader, %d hunters', p.nombre, c['nombre'], CIUDADES[p.stage], pago,
             len(hunters))
    return True, msgs


def expirar(ses, e=None):
    """Se acabo el tiempo: la carga desaparece y nadie cobra."""
    e = e or encargo_de(ses)
    if e:
        _ENCARGOS.pop(e['trader'], None)
    ranura, _ = item_carga_en(ses)
    if ranura is not None:
        _quitar_carga(ses, ranura)


def tick(ses, ahora=None):
    """Cada segundo: si su encargo caduco, se pierde. Una carga sin encargo (reinicio del servidor) tambien."""
    ahora = ahora or time.time()
    e = encargo_de(ses)
    if (e and ahora > e['fin']) or (not e and lleva_carga(ses)):
        expirar(ses, e)
        try:
            aviso(ses, 'Time is up. The cargo was lost.')
        except Exception:
            log.debug('aviso de carga perdida', exc_info=True)


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
    p = ses.personaje
    job = job_de(p)
    if not job:
        return _linea(M_SALUDO, [OP_TRADER, OP_HUNTER, OP_THIEF, OP_SALIR])
    opts = []
    if job == TRADER:
        opts.append(OP_ENTREGAR if (encargo_de(ses) or lleva_carga(ses)) else OP_ENCARGO)
    opts += [o for j, o in ((TRADER, OP_TRADER), (HUNTER, OP_HUNTER), (THIEF, OP_THIEF)) if j != job]
    opts += [OP_DEJAR, OP_SALIR]
    return _linea(M_JOB_ACTUAL, opts, ['1', NOMBRE_JOB[job]])


def opcion(ses, op: int, ahora=None, rng=None):
    """(paquetes 0x0012 o None para cerrar, avisos) de una opcion del Guild Clerk."""
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
    return _ENCARGOS.pop(int(char_id), None) is not None
