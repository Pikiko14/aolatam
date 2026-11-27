"""El cazador cazado (25/11/2026): "a un jugador al azar le toca ser la presa durante 15 minutos; su posicion se
anuncia cada cierto tiempo; si sobrevive gana mucho y quien lo derrote se lleva un premio; PvP voluntario, solo para
quien se apunte" (plantillas/eventos_sociales.json "caza").

* /hunt join | leave: apuntarse (dura la sesion). /hunt: el estado.
* A las horas del calendario semanal (evento 'caza') sale de presa uno de los apuntados que este en un mapa de caza y
  tenga 'nivel_min'. Cartel a todos. Cada 'aviso_cada_s' su posicion a los apuntados. Solo los apuntados le pueden
  pegar, y el a ellos (sociales.puede_atacar); nadie pierde EXP.
* Si un cazador lo derrota: 'premio_cazador' para ese cazador y se acaba. Si aguanta 'duracion_min': 'premio_presa'.
  Si se esconde (fuera de un mapa de caza) en dos avisos seguidos, o se desconecta, pierde.
* GM: /hunt start [nombre] | stop.
"""
import datetime as dt
import logging
import random
import time

import sociales

log = logging.getLogger('cazador')

APUNTADOS = set()          # char_id
EVENTOS = 'Events (button on the bar)'
_CAZA = {}                 # {'presa': char_id, 'inicio', 'fin', 'ultimo_aviso', 'escondido'}
_HECHAS = set()


def cfg():
    return sociales.config()['caza']


def activa():
    return _CAZA if _CAZA.get('presa') is not None else None


def es_presa(ses):
    c = activa()
    return bool(c and getattr(ses, 'personaje', None) and int(ses.personaje.char_id) == c['presa'])


def apuntado(ses):
    return getattr(ses, 'personaje', None) is not None and int(ses.personaje.char_id) in APUNTADOS


def puede_atacar(a, b):
    """Presa contra cazador apuntado, en un mapa de caza (simetrico)."""
    if not activa():
        return False
    if not sociales.es_de_caza(a.personaje.stage):
        return False
    return (es_presa(a) and apuntado(b) and not es_presa(b)) or (es_presa(b) and apuntado(a) and not es_presa(a))


def _presa():
    c = activa()
    return sociales.por_cid(c['presa']) if c else None


def _cazadores():
    return [s for s in sociales.sesiones() if apuntado(s) and not es_presa(s)]


def _posicion(s):
    p = s.personaje
    return '%s (%d, %d)' % (sociales.nombre_mapa(p.stage), p.tile_x, p.tile_y)


def candidatos():
    n = int(cfg()['nivel_min'])
    return [s for s in sociales.sesiones() if apuntado(s) and s.personaje.nivel >= n
            and sociales.es_de_caza(s.personaje.stage) and not getattr(s, 'muerto', False)]


def empezar(presa=None, rng=None, ahora_ts=None):
    rng = rng or random
    if activa():
        return 'already running'
    if presa is None:
        cands = candidatos()
        if len(cands) < 1 or len(APUNTADOS) < 2:
            sociales.cartel('[Hunted Hunter] Not enough hunters signed up in %s. Maybe next time!' % EVENTOS + '')
            return 'not enough players'
        presa = rng.choice(cands)
    ahora_ts = ahora_ts or time.time()
    _CAZA.clear()
    _CAZA.update({'presa': int(presa.personaje.char_id), 'inicio': ahora_ts, 'ultimo_aviso': ahora_ts,
                  'fin': ahora_ts + float(cfg()['duracion_min']) * 60, 'escondido': 0})
    sociales.cartel('[Hunted Hunter] %s is the prey! Last seen in %s. Hunters, go! (sign up in Events on the bar)'
                    % (presa.personaje.nombre, _posicion(presa)))
    sociales.aviso(presa, '[Hunted Hunter] You are the prey! Survive %d minutes in hunting fields and you win big. '
                          'Hiding in towns does not count.' % int(cfg()['duracion_min']))
    sociales.refrescar(presa, *_cazadores())
    log.info('caza: presa %s', presa.personaje.nombre)
    return 'prey %s' % presa.personaje.nombre


def terminar(texto=None):
    if not activa():
        return 'no hunt'
    presa = _presa()
    gente = [s for s in [presa] + _cazadores() if s]
    _CAZA.clear()
    if texto:
        sociales.cartel('[Hunted Hunter] ' + texto)
    sociales.refrescar(*gente)
    return 'stopped'


def baja(ses, otro):
    """`ses` derrota a `otro`. Si es la caza, la resuelve."""
    if not activa():
        return False
    if es_presa(otro) and apuntado(ses):
        premio = sociales.premiar(ses, cfg()['premio_cazador'])
        sociales.aviso(ses, '[Hunted Hunter] You caught the prey! You get %s.' % premio)
        __import__('honor').caza(ses, False)
        sociales.revivir(otro)
        terminar('%s caught the prey %s! Well hunted.' % (ses.personaje.nombre, otro.personaje.nombre))
        return True
    if es_presa(ses) and apuntado(otro):
        sociales.aviso(otro, '[Hunted Hunter] The prey fought back! You are back on your feet in a moment.')
        sociales.revivir(otro)
        return True
    return False


def tick(ahora=None):
    ahora = ahora or dt.datetime.now()
    ts = ahora.timestamp()
    c = activa()
    if c:
        presa = _presa()
        if presa is None:
            terminar('The prey ran away (disconnected). The hunt is over.')
            return
        if ts >= c['fin']:
            premio = sociales.premiar(presa, cfg()['premio_presa'])
            sociales.aviso(presa, '[Hunted Hunter] You survived! You get %s.' % premio)
            __import__('honor').caza(presa, True)
            terminar('%s survived the hunt! The prey wins.' % presa.personaje.nombre)
            return
        if ts - c['ultimo_aviso'] >= float(cfg()['aviso_cada_s']):
            c['ultimo_aviso'] = ts
            if not sociales.es_de_caza(presa.personaje.stage):
                c['escondido'] += 1
                if c['escondido'] >= 2:
                    terminar('%s hid in %s and lost the hunt.' % (presa.personaje.nombre,
                                                                  sociales.nombre_mapa(presa.personaje.stage)))
                    return
                sociales.aviso(presa, '[Hunted Hunter] Go back to a hunting field or you lose the hunt!')
            else:
                c['escondido'] = 0
            quedan = int((c['fin'] - ts) // 60) + 1
            for s in _cazadores():
                sociales.aviso(s, '[Hunted Hunter] The prey %s is in %s. %d min left.'
                               % (presa.personaje.nombre, _posicion(presa), quedan))
        return
    clave = toca(ahora)
    if clave and clave not in _HECHAS:
        _HECHAS.add(clave)
        empezar()


def toca(ahora):
    import calendario
    for wd, h in (calendario.slots('caza') or []):
        if wd != ahora.weekday():
            continue
        hh, mm = (int(x) for x in h.split(':'))
        ini = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if ini <= ahora < ini + dt.timedelta(minutes=5):
            return '%s %s' % (ini.date().isoformat(), h)
    return None


def comando(ses, partes):
    sub = partes[1].lower() if len(partes) > 1 else ''
    cid = int(ses.personaje.char_id)
    if sub in ('join', 'on', 'si'):
        APUNTADOS.add(cid)
        sociales.aviso(ses, '[Hunted Hunter] You signed up. You can be chosen as the prey or hunt it.')
        if activa():
            sociales.refrescar(ses)
        return
    if sub in ('leave', 'off', 'no'):
        if es_presa(ses):
            sociales.aviso(ses, '[Hunted Hunter] You are the prey: you cannot leave now!')
            return
        APUNTADOS.discard(cid)
        sociales.aviso(ses, '[Hunted Hunter] You left the hunt.')
        sociales.refrescar(ses)
        return
    c = activa()
    estado = 'You are %s.' % ('signed up' if cid in APUNTADOS else 'not signed up (sign up in %s)' % EVENTOS)
    if c:
        presa = _presa()
        estado += ' The prey is %s in %s, %d min left.' % (
            presa.personaje.nombre if presa else '?', _posicion(presa) if presa else '?',
            int((c['fin'] - time.time()) // 60) + 1)
    sociales.aviso(ses, '[Hunted Hunter] ' + estado)


def comando_gm(partes):
    sub = partes[1].lower() if len(partes) > 1 else ''
    if sub == 'start':
        s = sociales.por_nombre(partes[2]) if len(partes) > 2 else None
        if s is not None:
            APUNTADOS.add(int(s.personaje.char_id))
        return empezar(s)
    if sub == 'stop':
        return terminar('The hunt was cancelled.')
    return 'hunters %d, hunt %s' % (len(APUNTADOS), 'on' if activa() else 'off')
