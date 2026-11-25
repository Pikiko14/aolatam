"""NPC con memoria (25/11/2026): "un mercader que sube o baja sus precios segun cuanto le compres; algunos NPC te
reconocen y te piden favores personales" (plantillas/npc_memoria.json).

* Al hablar con un NPC se apunta (ses._npc_tienda). Si compras en la tienda en los 'minutos_tienda' siguientes, ese NPC
  recuerda el oro que le gastaste (por personaje y NPC) y, segun 'niveles', te hace descuento en la compra. Si pasas
  'olvido_dias' sin comprarle, baja un nivel (te va olvidando).
* Un NPC que ya te conoce te saluda por tu nombre con tu descuento, y una vez al dia te pide un favor (derrotar
  monstruos de tu nivel o jefes). Cuando lo cumples, vuelves a hablarle y te paga; el favor cuenta como gasto.
* /favor: el favor que tienes pendiente.
"""
import datetime as dt
import json
import logging
import pathlib
import random
import sqlite3
import time

log = logging.getLogger('npc_memoria')

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'npc_memoria.json'
DB_PATH = pathlib.Path(__file__).parent.parent / 'data' / 'npc_memoria.db'


def config():
    return json.loads(RUTA.read_text('utf-8'))


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.execute('create table if not exists memoria (char_id int, npc text, gasto int, ultima real, '
                'primary key (char_id, npc))')
    con.execute('create table if not exists favor (char_id int primary key, npc text, nombre text, mapa text, '
                'dia text, tipo text, n int, valor int, lvmin int, lvmax int, cumplido int, cobrado int)')
    return con


def _aviso(ses, texto):
    import clases
    try:
        ses.enviar(clases.aviso(texto, tipo=0, msg_id=clases.MSG_TEXTO))
    except Exception:
        log.debug('npc memoria: aviso', exc_info=True)


def _clave(nombre, stage):
    return '%s@%s' % (nombre, int(stage or 0))


def _hoy(ahora=None):
    return (ahora or dt.datetime.now()).date().isoformat()


def gasto(cid, npc, ahora_ts=None):
    """El oro que recuerda ese NPC, ya con el olvido aplicado."""
    con = _db()
    try:
        fila = con.execute('select gasto, ultima from memoria where char_id=? and npc=?', (cid, npc)).fetchone()
    finally:
        con.close()
    if not fila:
        return 0
    g, ultima = int(fila[0]), float(fila[1] or 0)
    dias = ((ahora_ts or time.time()) - ultima) / 86400.0
    olvido = float(config().get('olvido_dias', 14))
    niveles = sorted(int(n['desde']) for n in config()['niveles'])
    while dias >= olvido and g > 0:          # cada tramo de olvido, un nivel menos
        dias -= olvido
        debajo = [d for d in niveles if d <= g]
        g = (debajo[-2] if len(debajo) >= 2 else 0) if debajo else 0
    return g


def nivel(g):
    """(pct, titulo) del que ha gastado g, o (0, None)."""
    mejor = (0, None)
    for n in sorted(config()['niveles'], key=lambda n: int(n['desde'])):
        if g >= int(n['desde']):
            mejor = (int(n['pct']), n['titulo'])
    return mejor


def _sumar_gasto(cid, npc, cuanto, ahora_ts=None):
    ahora_ts = ahora_ts or time.time()
    g = gasto(cid, npc, ahora_ts) + int(cuanto)
    con = _db()
    try:
        con.execute('insert or replace into memoria values (?,?,?,?)', (cid, npc, g, ahora_ts))
        con.commit()
    finally:
        con.close()
    return g


# ---------------------------------------------------------------- tienda
def descuento(ses, ahora_ts=None):
    """El % de descuento del NPC con el que se hablo hace poco (0 si ninguno)."""
    t = getattr(ses, '_npc_tienda', None)
    p = getattr(ses, 'personaje', None)
    if not t or p is None:
        return 0
    npc, ts = t
    if (ahora_ts or time.time()) - ts > float(config().get('minutos_tienda', 10)) * 60:
        return 0
    return nivel(gasto(p.char_id, npc, ahora_ts))[0]


def precio(ses, total, ahora_ts=None):
    """El total de la compra con el descuento del NPC."""
    pct = descuento(ses, ahora_ts)
    return max(1, int(total * (100 - pct) // 100)) if pct and total > 0 else total


def al_comprar(ses, pagado, sin_descuento, ahora_ts=None):
    """Tras una compra en tienda: la memoria del NPC y el aviso del ahorro / del nivel nuevo."""
    t = getattr(ses, '_npc_tienda', None)
    p = getattr(ses, 'personaje', None)
    if not t or p is None or pagado <= 0:
        return
    npc, ts = t
    ahora_ts = ahora_ts or time.time()
    if ahora_ts - ts > float(config().get('minutos_tienda', 10)) * 60:
        return
    antes = nivel(gasto(p.char_id, npc, ahora_ts))
    despues = nivel(_sumar_gasto(p.char_id, npc, pagado, ahora_ts))
    nombre = npc.split('@')[0]
    if sin_descuento > pagado:
        _aviso(ses, '%s: For you, %d%% off. You saved %d Gold.' % (nombre, antes[0], sin_descuento - pagado))
    if despues[0] > antes[0]:
        _aviso(ses, '%s: You are now my %s! From now on, %d%% off everything you buy from me.'
               % (nombre, despues[1], despues[0]))


# ---------------------------------------------------------------- favores
def favor(cid):
    con = _db()
    try:
        f = con.execute('select npc, nombre, mapa, dia, tipo, n, valor, lvmin, lvmax, cumplido, cobrado '
                        'from favor where char_id=?', (cid,)).fetchone()
    finally:
        con.close()
    if not f:
        return None
    return dict(zip(('npc', 'nombre', 'mapa', 'dia', 'tipo', 'n', 'valor', 'lvmin', 'lvmax', 'cumplido', 'cobrado'), f))


def _guardar_favor(cid, f):
    con = _db()
    try:
        con.execute('insert or replace into favor values (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (cid, f['npc'], f['nombre'], f['mapa'], f['dia'], f['tipo'], f['n'], f['valor'], f['lvmin'],
                     f['lvmax'], f['cumplido'], f['cobrado']))
        con.commit()
    finally:
        con.close()


def texto_favor(f):
    for d in config()['favores']:
        if d['tipo'] == f['tipo']:
            txt = d['texto'] % ((f['n'], f['lvmin'], f['lvmax']) if '%d-%d' in d['texto'] else (f['n'],))
            return txt
    return '%s %d' % (f['tipo'], f['n'])


def _pedir_favor(ses, npc, mapa, ahora=None, rng=None):
    rng = rng or random
    p = ses.personaje
    d = rng.choice(config()['favores'])
    m = int(config().get('margen_nivel', 10))
    f = {'npc': npc, 'nombre': npc.split('@')[0], 'mapa': mapa, 'dia': _hoy(ahora), 'tipo': d['tipo'],
         'n': int(d['n']), 'valor': 0, 'lvmin': max(1, p.nivel - m), 'lvmax': p.nivel + m, 'cumplido': 0, 'cobrado': 0}
    _guardar_favor(p.char_id, f)
    _aviso(ses, '%s: %s, could I ask you a favor? Please %s. Come back to me when it is done.'
           % (f['nombre'], p.nombre, texto_favor(f)))
    return f


def _cobrar_favor(ses, f):
    import app
    import combate
    import trade_routes
    p = ses.personaje
    pr = config()['premio']
    exp = int((combate.exp_para_nivel(p.nivel + 1) - combate.exp_para_nivel(p.nivel)) * float(pr.get('exp', 0)))
    oro = int(pr.get('oro_por_nivel', 0)) * int(p.nivel)
    try:
        if exp > 0:
            app._dar_exp_y_creditos(ses, exp=exp)
        if oro > 0:
            trade_routes._cambiar_oro(ses, oro)
    except Exception:
        log.exception('npc memoria: premio del favor')
    f['cobrado'] = 1
    _guardar_favor(p.char_id, f)
    g = _sumar_gasto(p.char_id, f['npc'], int(config().get('gasto_favor', 0)))
    pct, titulo = nivel(g)
    _aviso(ses, '%s: Thank you, %s! Take this: %d EXP and %d Gold. I won\'t forget it.%s'
           % (f['nombre'], p.nombre, exp, oro, (' (%d%% off with me)' % pct) if pct else ''))


def al_hablar(ses, nombre, stage, ahora=None):
    """Al pulsar un NPC: lo apunta para la tienda, cobra el favor que le debias y, si te conoce, te saluda."""
    p = getattr(ses, 'personaje', None)
    if p is None or not nombre:
        return
    try:
        npc = _clave(nombre, stage)
        ahora = ahora or dt.datetime.now()
        ses._npc_tienda = (npc, ahora.timestamp())
        f = favor(p.char_id)
        if f and f['npc'] == npc and f['cumplido'] and not f['cobrado']:
            _cobrar_favor(ses, f)
            return
        g = gasto(p.char_id, npc, ahora.timestamp())
        pct, titulo = nivel(g)
        if not pct:
            return
        ultimo = getattr(ses, '_npc_saludo', {}).get(npc, 0)
        if ahora.timestamp() - ultimo < 1800:
            return
        ses._npc_saludo = {**getattr(ses, '_npc_saludo', {}), npc: ahora.timestamp()}
        _aviso(ses, '%s: Welcome back, %s! For my %s, %d%% off today.' % (nombre, p.nombre, titulo, pct))
        if f is None or (f['dia'] != _hoy(ahora) and (f['cobrado'] or not f['cumplido'])):
            import mundo_vivo
            _pedir_favor(ses, npc, mundo_vivo.nombre_mapa(stage), ahora)
    except Exception:
        log.exception('npc memoria: al hablar')


def al_matar(ses, m):
    """Cuenta para el favor pendiente del que lo mato (los jefes, para todos los que le pegaron)."""
    import app
    import combate
    try:
        jefe = combate.es_jefe(getattr(m, 'npc_type', 0)) or getattr(m, 'jefe_mundo', False) \
            or getattr(m, 'jefe_local', False)
        quienes = [ses]
        if jefe:
            cids = {int(c) for c in (getattr(m, 'dano_por', None) or {})}
            quienes = [s for s in app._tw_sesiones() if getattr(s, 'personaje', None)
                       and int(s.personaje.char_id) in cids] or [ses]
        for s in quienes:
            p = getattr(s, 'personaje', None)
            if p is None:
                continue
            f = favor(p.char_id)
            if not f or f['cumplido']:
                continue
            if f['tipo'] == 'jefes' and jefe:
                f['valor'] += 1
            elif f['tipo'] == 'matar' and s is ses and \
                    f['lvmin'] <= int(getattr(m, 'nivel', 0) or 0) <= f['lvmax']:
                f['valor'] += 1
            else:
                continue
            if f['valor'] >= f['n']:
                f['cumplido'] = 1
                _aviso(s, '[Favor] Done! Go back to %s (%s) to get your reward.' % (f['nombre'], f['mapa']))
            _guardar_favor(p.char_id, f)
    except Exception:
        log.exception('npc memoria: al matar')


def comando(ses):
    p = ses.personaje
    f = favor(p.char_id)
    if not f or f['cobrado']:
        _aviso(ses, '[Favor] No favor pending. Buy from the same merchant and he will remember you: regular '
                    'customers get discounts and personal favors.')
        return
    if f['cumplido']:
        _aviso(ses, '[Favor] %s (%s) is waiting for you with your reward.' % (f['nombre'], f['mapa']))
    else:
        _aviso(ses, '[Favor] %s (%s) asked you to %s: %d / %d.' % (f['nombre'], f['mapa'], texto_favor(f),
                                                                   f['valor'], f['n']))
