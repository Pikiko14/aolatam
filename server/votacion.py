"""La votacion del servidor (25/11/2026): "cada semana los jugadores votan que evento extra habra el fin de semana, o
que mapa tendra experiencia doble; la ventana parecida a la de misiones" (plantillas/eventos_sociales.json "votacion").

* Cada semana (ISO) hay una papeleta: 'opciones_exp' mapas de caza con EXP doble el fin de semana y
  'eventos_por_semana' eventos extra de 'eventos' (sorteados con la semana: los mismos para todos).
* De lunes a jueves: /vote abre el panel (la ventana de misiones, con el titulo "Weekly Vote": cada opcion con sus
  votos en la barra) y /vote <n> vota (se puede cambiar el voto). Un voto por personaje.
* El viernes a las 00:00 se cuenta y se anuncia. Sabado y domingo: el mapa ganador da +'exp_doble' % de EXP
  (mult_exp, en app._premiar) o el evento ganador sale en el calendario (calendario.semana, slots_extra).
* GM: /vote close (cuenta ya) | reset.
"""
import datetime as dt
import json
import logging
import pathlib
import random
import struct

import sociales

log = logging.getLogger('votacion')

ESTADO = pathlib.Path(__file__).parent.parent / 'data' / 'votacion.json'
CMD_VT = 177
_ESTADO = {}


def cfg():
    return sociales.config()['votacion']


def _ahora():
    try:
        import calendario
        return calendario._ahora()
    except Exception:
        return dt.datetime.now()


def clave_semana(ahora):
    y, w, _d = ahora.isocalendar()
    return '%d-W%02d' % (y, w)


def _estado():
    if not _ESTADO:
        try:
            _ESTADO.update(json.loads(ESTADO.read_text(encoding='utf-8')))
        except Exception:
            pass
    return _ESTADO


def _guardar():
    try:
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(_ESTADO), encoding='utf-8')
    except Exception:
        log.exception('votacion: guardar')


def _semana(clave):
    return _estado().setdefault(clave, {'votos': {}, 'ganador': None})


def opciones(clave):
    """[{'tipo': 'exp', 'stage', 'texto'} | {'tipo': 'evento', 'id', 'texto', 'slots'}] de esa semana."""
    c = cfg()
    rng = random.Random('votacion-' + clave)
    import mundo_vivo
    mapas = [s for s in sociales.mapas_de_caza() if not mundo_vivo.bajo_techo(s)] or sociales.mapas_de_caza()
    out = [{'tipo': 'exp', 'stage': st, 'texto': 'Double EXP in %s on the weekend' % sociales.nombre_mapa(st)}
           for st in rng.sample(mapas, min(len(mapas), int(c['opciones_exp'])))]
    eventos = list(c['eventos'])
    for e in rng.sample(eventos, min(len(eventos), int(c['eventos_por_semana']))):
        out.append({'tipo': 'evento', 'id': e['id'], 'texto': e['texto'], 'slots': e['slots']})
    return out


def abierta(ahora):
    return ahora.weekday() <= 3


def recuento(clave):
    n = [0] * len(opciones(clave))
    for i in _semana(clave)['votos'].values():
        if 0 <= int(i) < len(n):
            n[int(i)] += 1
    return n


def votar(ses, n, ahora=None):
    ahora = ahora or _ahora()
    clave = clave_semana(ahora)
    ops = opciones(clave)
    if not abierta(ahora):
        return 'Voting is closed until Monday.'
    if not 1 <= n <= len(ops):
        return 'Choose an option from 1 to %d.' % len(ops)
    _semana(clave)['votos'][str(ses.personaje.char_id)] = n - 1
    _guardar()
    return 'You voted for: %s.' % ops[n - 1]['texto']


def ganador(clave):
    """El indice ganador (el mas votado; en empate, el primero), o None si nadie voto."""
    n = recuento(clave)
    if not any(n):
        return None
    return max(range(len(n)), key=lambda i: (n[i], -i))


def cerrar(clave):
    s = _semana(clave)
    if s.get('cerrada'):
        return s.get('ganador')
    s['cerrada'] = True
    s['ganador'] = ganador(clave)
    _guardar()
    if s['ganador'] is None:
        sociales.cartel('[Weekly Vote] Nobody voted this week. Vote from Monday in Events (button on the bar)!')
    else:
        sociales.cartel('[Weekly Vote] The players have spoken: %s!' % opciones(clave)[s['ganador']]['texto'])
    return s['ganador']


def _ganadora(ahora):
    s = _estado().get(clave_semana(ahora))
    if not s or s.get('ganador') is None:
        return None
    return opciones(clave_semana(ahora))[s['ganador']]


def mult_exp(stage, ahora=None):
    ahora = ahora or _ahora()
    if ahora.weekday() < 5:
        return 1.0
    g = _ganadora(ahora)
    if g and g['tipo'] == 'exp' and int(g['stage']) == int(stage or 0):
        return 1.0 + float(cfg()['exp_doble']) / 100.0
    return 1.0


def slots_extra(ahora=None):
    """[(dia, 'HH:MM', clave)] del evento ganador de esta semana (para calendario.semana)."""
    ahora = ahora or _ahora()
    g = _ganadora(ahora)
    if not g or g['tipo'] != 'evento':
        return []
    return [(int(d), h, g['id']) for d, h in g['slots']]


def vista(ses, ahora=None):
    ahora = ahora or _ahora()
    clave = clave_semana(ahora)
    ops = opciones(clave)
    n = recuento(clave)
    total = sum(n) or 1
    mio = _semana(clave)['votos'].get(str(ses.personaje.char_id))
    g = _semana(clave).get('ganador')
    if abierta(ahora):
        cierre = (ahora.replace(hour=0, minute=0, second=0, microsecond=0)
                  + dt.timedelta(days=4 - ahora.weekday()))
        resto = cierre - ahora
        titulo = 'Voting closes Friday 00:00 (in %dd %dh). %d votes so far.' % (
            resto.days, resto.seconds // 3600, sum(n))
        l1 = ('Your vote: option %d.' % (mio + 1)) if mio is not None else 'You have not voted yet.'
        l2 = 'Click an option to vote. You can change your vote until Thursday.'
    else:
        titulo = 'Voting is closed. New vote on Monday.'
        l1 = ('Winner: %s.' % ops[g]['texto']) if g is not None else 'Nobody voted this week.'
        l2 = 'It applies this Saturday and Sunday.'
    filas = [['%d. %s' % (i + 1, o['texto']), '%d vote%s' % (n[i], '' if n[i] == 1 else 's'),
              int(round(100.0 * n[i] / total))] for i, o in enumerate(ops)]
    return titulo, l1, l2, 'The most voted option wins. One vote per character.', filas[:6]


def abrir(ses, ahora=None):
    import canal_lua
    ses._md_abierto = False                       # la ventana deja de ser la de misiones
    ses.enviar(canal_lua.paquete((canal_lua.CARPETA / 'misiones.lua').read_text(encoding='utf-8')),
               canal_lua.paquete((canal_lua.CARPETA / 'votacion.lua').read_text(encoding='utf-8')),
               canal_lua.llamar('VTAbrir', *vista(ses, ahora)))


def lineas(ses, ahora=None):
    titulo, l1, l2, pie, filas = vista(ses, ahora)
    return ['[Weekly Vote] ' + titulo, '[Weekly Vote] ' + l1] + \
        ['[Weekly Vote] %s - %s' % (f[0], f[1]) for f in filas] + ['[Weekly Vote] ' + l2]


def procesar(ses, cuerpo) -> bool:
    if len(cuerpo) < 9 or cuerpo[0] != CMD_VT or getattr(ses, 'personaje', None) is None:
        return False
    a, _b = struct.unpack_from('<II', cuerpo, 1)
    if a == 9:
        for l in lineas(ses):
            sociales.aviso(ses, l)
    return True


def comando(ses, partes):
    if len(partes) > 1 and str(partes[1]).isdigit():
        sociales.aviso(ses, '[Weekly Vote] ' + votar(ses, int(partes[1])))
    abrir(ses)


def comando_gm(partes):
    sub = partes[1].lower() if len(partes) > 1 else ''
    clave = clave_semana(_ahora())
    if sub == 'close':
        g = cerrar(clave)
        return 'closed: %s' % (opciones(clave)[g]['texto'] if g is not None else 'no votes')
    if sub == 'reset':
        _estado().pop(clave, None)
        _guardar()
        return 'reset'
    return 'votes %s' % recuento(clave)


_AVISADO = set()


def tick(ahora=None):
    ahora = ahora or _ahora()
    clave = clave_semana(ahora)
    if ahora.weekday() >= 4:
        cerrar(clave)
    elif ahora.weekday() == 0 and clave not in _AVISADO and ahora.hour >= 12:
        _AVISADO.add(clave)
        sociales.cartel('[Weekly Vote] Vote for this weekend: double EXP in a map or an extra event. Open Events on the bar!')
