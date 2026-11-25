"""El tesoro del servidor (25/11/2026): "pistas en el chat; el primero que llega al punto se lleva el cofre" y "que en
vez de dig salga 1 cofre del tesoro" (plantillas/eventos_sociales.json "tesoro").

* A las horas del calendario semanal (evento 'tesoro') aparece un cofre (el del juego de los mapas del tesoro, el
  objeto 60153 de server.obd, con el 0x000E) en una casilla de un mapa de caza donde sale algun monstruo. Lo ve todo el
  que este o entre en ese mapa. Cartel a todos con la primera pista; cada 'pista_cada_min' una mas: la letra y el
  largo del nombre del mapa, el mapa, la zona del mapa, las coordenadas aproximadas y al final las exactas.
* El primero que lo pulsa a 'radio' casillas o menos se lo lleva ('premio') y desaparece para todos.
* Si nadie lo abre en 'duracion_min', se va y se dice donde estaba.
* GM: /treasure [start [stage] | stop | status].
"""
import datetime as dt
import logging
import random
import time

import sociales

log = logging.getLogger('tesoro_servidor')

_ACTIVO = {}
_HECHAS = set()
EID_COFRE = 97_200_000
SPRITE_COFRE = 60153            # Dusty Wooden Box, el cofre de los mapas del tesoro


def _paquete_cofre(t):
    import login
    return login._map_object_spawn(EID_COFRE, SPRITE_COFRE, (t['x'], t['y']))


def _paquete_quitar():
    import struct
    return struct.pack('<HIB', 0x0007, EID_COFRE, 1)


def _a_los_del_mapa(stage, pkt):
    import trade_routes
    for s in trade_routes._en_mapa(stage):
        try:
            s.enviar(pkt)
        except Exception:
            log.debug('tesoro: paquete', exc_info=True)


def al_entrar(ses):
    """Al cargar un mapa: el cofre, si esta en ese."""
    t = dict(activo() or {}) or None
    p = getattr(ses, 'personaje', None)
    if t and p is not None and int(p.stage) == t['stage']:
        ses.enviar(_paquete_cofre(t))


def cfg():
    return sociales.config()['tesoro']


def activo():
    return _ACTIVO if _ACTIVO.get('stage') is not None else None


def _zona(stage, x, y):
    """'north-east' etc., respecto a donde salen los monstruos del mapa."""
    import app
    try:
        bichos = list((app._monstruos_de(stage) or {}).values())
        xs = [getattr(m, 'spawn_x', m.tile_x) for m in bichos]
        ys = [getattr(m, 'spawn_y', m.tile_y) for m in bichos]
        cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    except Exception:
        cx, cy = x, y
    ns = 'north' if y < cy - 15 else ('south' if y > cy + 15 else '')
    eo = 'west' if x < cx - 15 else ('east' if x > cx + 15 else '')
    return '-'.join(p for p in (ns, eo) if p) or 'center'


def pista(n, t=None):
    t = t or _ACTIVO
    nombre = sociales.nombre_mapa(t['stage'])
    if n == 0:
        return "The land's name starts with '%s' and has %d letters." % (nombre[0], len(nombre.replace(' ', '')))
    if n == 1:
        return 'It is buried in %s.' % nombre
    if n == 2:
        return 'Search the %s part of %s.' % (_zona(t['stage'], t['x'], t['y']), nombre)
    if n == 3:
        return 'It is around (%d, %d) in %s.' % (round(t['x'], -1), round(t['y'], -1), nombre)
    return 'The chest is right at (%d, %d) in %s! Hurry!' % (t['x'], t['y'], nombre)


def empezar(stage=None, rng=None):
    import app
    import santa_clausula as sc
    rng = rng or random
    if activo():
        return 'already active in %s' % sociales.nombre_mapa(_ACTIVO['stage'])
    mapas = sociales.mapas_de_caza()
    stage = int(stage) if stage else rng.choice(mapas)
    x, y = sc._tile_de_aparicion(stage, app._monstruos_de(stage))
    ahora = time.time()
    _ACTIVO.clear()
    _ACTIVO.update({'stage': stage, 'x': int(x), 'y': int(y), 'inicio': ahora,
                    'fin': ahora + float(cfg()['duracion_min']) * 60, 'pistas': 1})
    _a_los_del_mapa(stage, _paquete_cofre(_ACTIVO))
    sociales.cartel('[Treasure Hunt] A treasure chest has appeared somewhere! The first to open it keeps it. '
                    'Clue 1: %s' % pista(0))
    log.info('tesoro en %s (%d) casilla (%d, %d)', sociales.nombre_mapa(stage), stage, x, y)
    return 'treasure in %s (%d, %d)' % (sociales.nombre_mapa(stage), x, y)


def terminar(motivo=''):
    t = dict(activo() or {}) or None
    if not t:
        return 'no treasure'
    _ACTIVO.clear()
    _a_los_del_mapa(t['stage'], _paquete_quitar())
    if motivo:
        sociales.cartel('[Treasure Hunt] %s' % motivo)
    return 'stopped'


def pulsar(ses, ent):
    """Clic en el cofre: si esta cerca, es suyo. False si no era el cofre."""
    t = dict(activo() or {}) or None
    p = getattr(ses, 'personaje', None)
    if not t or p is None or int(ent) != EID_COFRE:
        return False
    if int(p.stage) != t['stage']:
        return True
    if max(abs(int(p.tile_x) - t['x']), abs(int(p.tile_y) - t['y'])) > int(cfg()['radio']):
        sociales.aviso(ses, '[Treasure Hunt] Get closer to open the chest.')
        return True
    mapa = sociales.nombre_mapa(t['stage'])
    _ACTIVO.clear()
    _a_los_del_mapa(t['stage'], _paquete_quitar())
    premio = sociales.premiar(ses, cfg()['premio'])
    sociales.aviso(ses, '[Treasure Hunt] You opened the treasure chest! You get %s.' % premio)
    sociales.cartel('[Treasure Hunt] %s found the treasure chest in %s! Congratulations!' % (p.nombre, mapa))
    log.info('tesoro abierto por %s', p.nombre)
    return True


def toca(ahora):
    import calendario
    for wd, h in (calendario.slots('tesoro') or []):
        if wd != ahora.weekday():
            continue
        hh, mm = (int(x) for x in h.split(':'))
        ini = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if ini <= ahora < ini + dt.timedelta(minutes=5):
            return '%s %s' % (ini.date().isoformat(), h)
    return None


def tick(ahora=None):
    ahora = ahora or dt.datetime.now()
    ts = ahora.timestamp()
    t = dict(activo() or {}) or None
    if t:
        if ts >= t['fin']:
            terminar('Nobody opened the chest. It was at (%d, %d) in %s.'
                     % (t['x'], t['y'], sociales.nombre_mapa(t['stage'])))
            return
        n = int((ts - t['inicio']) // (float(cfg()['pista_cada_min']) * 60))
        if n >= t['pistas'] and t['pistas'] <= 4:
            sociales.cartel('[Treasure Hunt] Clue %d: %s' % (t['pistas'] + 1, pista(t['pistas'])))
            _ACTIVO['pistas'] = t['pistas'] + 1
        return
    clave = toca(ahora)
    if clave and clave not in _HECHAS:
        _HECHAS.add(clave)
        empezar()


def comando_gm(partes):
    sub = partes[1].lower() if len(partes) > 1 else 'status'
    if sub == 'start':
        return empezar(partes[2] if len(partes) > 2 else None)
    if sub == 'stop':
        return terminar('The treasure hunt was cancelled.')
    t = dict(activo() or {}) or None
    return ('treasure at (%d, %d) in %s, clue %d' % (t['x'], t['y'], sociales.nombre_mapa(t['stage']), t['pistas'])
            if t else 'no treasure')
