"""El calendario semanal de eventos (25/11/2026): "calendario semanal de eventos, rotarlos por dia y hora, con anuncio".

* UNA SOLA SEMANA en plantillas/calendario.json "semana" (lunes a domingo, hora del servidor como el resto de los
  relojes): a que hora toca cada evento. Cada sistema sigue arrancando lo suyo, pero toma las horas de aqui con
  slots(clave): el Angel MOBA (moba_lobby.proxima), el Holy Battlefield (competiciones.cron), la Totem War
  (totem_war._toca_por_horario), la League War (league_war.cron) y los Daily Events (daily_events). Si un evento no esta
  en el calendario (o falta el archivo), ese sistema usa su propio horario de siempre.
* AVISOS: 'aviso_min' minutos antes de cada evento, un cartel a todo el servidor (cron, desde el reloj de
  competiciones); al conectar, los eventos que quedan hoy (al_conectar); y /events (cualquier jugador) da la semana.
"""
import datetime as dt
import json
import logging
import pathlib

log = logging.getLogger('calendario')

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'calendario.json'
DIAS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
_CACHE = {'mtime': None, 'cfg': {}}
_AVISADOS = set()


def config():
    """plantillas/calendario.json (se relee si cambia); {} si no esta o esta roto."""
    try:
        mtime = RUTA.stat().st_mtime
    except OSError:
        return {}
    if _CACHE['mtime'] != mtime:
        try:
            _CACHE['cfg'] = json.loads(RUTA.read_text('utf-8'))
        except Exception:
            log.exception('calendario.json roto: cada evento usa su propio horario')
            _CACHE['cfg'] = {}
        _CACHE['mtime'] = mtime
    return _CACHE['cfg']


def _hora(texto):
    hh, mm = (int(x) for x in str(texto).split(':'))
    return hh, mm


def semana():
    """[(weekday 0=lunes, 'HH:MM', clave)] ordenado por dia y hora."""
    cfg = config()
    filas = []
    for dia, nombre in enumerate(DIAS):
        for hora, clave in (cfg.get('semana') or {}).get(nombre, ()):
            _hora(hora)
            filas.append((dia, '%02d:%02d' % _hora(hora), str(clave)))
    return sorted(filas)


def slots(clave):
    """[(weekday, 'HH:MM')] del evento, o None si el calendario no lo lleva (entonces manda su propio horario)."""
    cfg = config()
    if clave not in (cfg.get('eventos') or {}):
        return None
    return [(d, h) for d, h, c in semana() if c == clave]


def nombre(clave):
    return ((config().get('eventos') or {}).get(clave) or {}).get('nombre', clave)


def _ahora():
    try:
        import competiciones
        zona = competiciones.config_eventos().get('zona_horaria')
        if zona:
            import zoneinfo
            return dt.datetime.now(zoneinfo.ZoneInfo(zona))
    except Exception:
        pass
    return dt.datetime.now().astimezone()


def de_hoy(ahora=None, solo_pendientes=True):
    """[('HH:MM', clave)] de hoy; con solo_pendientes, los que aun no han terminado."""
    ahora = ahora or _ahora()
    eventos = config().get('eventos') or {}
    out = []
    for d, h, c in semana():
        if d != ahora.weekday():
            continue
        hh, mm = _hora(h)
        fin = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0) + dt.timedelta(
            minutes=int((eventos.get(c) or {}).get('duracion', 30)))
        if not solo_pendientes or fin > ahora:
            out.append((h, c))
    return out


def texto_hoy(ahora=None):
    hoy = de_hoy(ahora)
    if not hoy:
        return 'No more events today. Type /events for the week.'
    return "Today's events: %s. Type /events for the week." % ', '.join('%s %s' % (h, nombre(c)) for h, c in hoy)


def lineas_semana():
    """Una linea por dia: 'Monday: 14:00 Angel MOBA, 18:00 Quick Reflexes'."""
    por_dia = {}
    for d, h, c in semana():
        por_dia.setdefault(d, []).append('%s %s' % (h, nombre(c)))
    return ['%s: %s' % (DIAS[d], ', '.join(por_dia[d])) for d in sorted(por_dia)]


def _aviso(ses, texto):
    import clases
    ses.enviar(clases.aviso(texto, tipo=0, msg_id=clases.MSG_TEXTO))


def comando(ses):
    """/events: la semana entera, linea por linea."""
    lineas = lineas_semana()
    if not lineas:
        _aviso(ses, 'There is no weekly event calendar.')
        return
    _aviso(ses, 'Weekly events (server time):')
    for linea in lineas:
        _aviso(ses, linea)
    _aviso(ses, texto_hoy())


def al_conectar(ses):
    """Al entrar al juego: los eventos que quedan hoy."""
    if not config().get('semana') or getattr(ses, '_calendario_saludado', False):
        return
    ses._calendario_saludado = True
    _aviso(ses, texto_hoy())


def cron(ahora=None):
    """'aviso_min' minutos antes de cada evento, un cartel a todos (una vez por evento)."""
    cfg = config()
    if not cfg.get('semana'):
        return
    ahora = ahora or _ahora()
    antes = int(cfg.get('aviso_min', 30))
    eventos = cfg.get('eventos') or {}
    for d, h, c in semana():
        if d != ahora.weekday():
            continue
        hh, mm = _hora(h)
        empieza = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        aviso = empieza - dt.timedelta(minutes=antes)
        clave = (empieza.date().isoformat(), h, c)
        if aviso <= ahora < aviso + dt.timedelta(minutes=2) and clave not in _AVISADOS:
            _AVISADOS.add(clave)
            donde = (eventos.get(c) or {}).get('donde')
            texto = '%s starts in %d minutes (%s)!%s' % (nombre(c), antes, h, (' ' + donde) if donde else '')
            try:
                import competiciones
                competiciones.anunciar(texto)
            except Exception:
                log.debug('calendario: anunciar', exc_info=True)
            log.info('calendario: aviso %s', texto)
