"""Duelos de apuesta (25/11/2026): "dos jugadores apuestan oro en un duelo, y el resto puede apostar a uno de los
dos" (plantillas/eventos_sociales.json "duelo").

* /duel <nombre> <oro>: reto a alguien de tu mapa (a 'distancia' casillas o menos). El otro: /duel accept o /duel no.
  Al aceptar se les quita el oro a los dos (queda en el bote).
* Durante 'apuestas_s' segundos cualquiera, este donde este, apuesta con /bet <nombre> <oro> (una vez por duelo).
* Luego pelean (solo entre ellos: sociales.puede_atacar) hasta que uno cae; nadie pierde EXP y el que cae se levanta.
  El ganador se lleva las dos apuestas. Los que acertaron recuperan lo suyo y se reparten lo que apostaron los que
  fallaron, en proporcion, menos la 'comision' %. Si en 'pelea_max_s' nadie cae, o uno se va antes de empezar, se
  devuelve todo; si se va peleando, gana el otro.
* /duel: el estado de los duelos en marcha (con lo apostado a cada uno).
"""
import logging
import time

import sociales

log = logging.getLogger('duelos')

_RETOS = {}        # char_id retado -> {'de': char_id, 'oro': n, 'ts': t}
_ID = [0]
_DUELOS = []       # {'a', 'b', 'oro', 'fase', 'fin_apuestas', 'fin', 'apuestas': {cid: [lado, oro]}, 'stage'}


def cfg():
    return sociales.config()['duelo']


def duelo_de(ses):
    if not getattr(ses, 'personaje', None):
        return None
    cid = int(ses.personaje.char_id)
    return next((d for d in _DUELOS if cid in (d['a'], d['b'])), None)


def puede_atacar(a, b):
    d = duelo_de(a)
    return bool(d and d['fase'] == 'pelea' and int(b.personaje.char_id) in (d['a'], d['b'])
                and int(b.personaje.char_id) != int(a.personaje.char_id))


def _nombre(cid):
    s = sociales.por_cid(cid)
    return s.personaje.nombre if s else '?'


def _botes(d):
    a = sum(o for lado, o in d['apuestas'].values() if lado == d['a'])
    b = sum(o for lado, o in d['apuestas'].values() if lado == d['b'])
    return a, b


def retar(ses, nombre, oro, ahora=None):
    """Devuelve el texto para el que reta."""
    c = cfg()
    ahora = ahora or time.time()
    otro = sociales.por_nombre(nombre)
    p = ses.personaje
    if otro is None or otro is ses:
        return 'There is no player called %s online.' % nombre
    q = otro.personaje
    if oro < int(c['oro_min']) or oro > int(c['oro_max']):
        return 'The stake must be between %d and %d Gold.' % (int(c['oro_min']), int(c['oro_max']))
    if duelo_de(ses) or duelo_de(otro):
        return 'One of you is already in a duel.'
    import trade_routes
    if (p.stage != q.stage or trade_routes._mapa_de_competicion(p.stage)
            or max(abs(p.tile_x - q.tile_x), abs(p.tile_y - q.tile_y)) > int(c['distancia'])):
        return '%s must be close to you, in the same map (not in an event arena).' % q.nombre
    if sociales.oro(ses) < oro:
        return 'You do not have %d Gold.' % oro
    _RETOS[int(q.char_id)] = {'de': int(p.char_id), 'oro': int(oro), 'ts': ahora}
    __import__('sociales_ui').reto_recibido(otro, p.nombre, oro)          # la ventanita con Accept / Decline
    sociales.aviso(otro, '[Duel] %s challenges you to a duel for %d Gold! Accept or decline it in the Duel window (60 s).'
                   % (p.nombre, oro))
    return 'Challenge sent to %s for %d Gold.' % (q.nombre, oro)


def aceptar(ses, ahora=None):
    c = cfg()
    ahora = ahora or time.time()
    r = _RETOS.pop(int(ses.personaje.char_id), None)
    if not r or ahora - r['ts'] > 60:
        return 'Nobody has challenged you.'
    retador = sociales.por_cid(r['de'])
    if retador is None or duelo_de(retador) or duelo_de(ses):
        return 'The duel can no longer start.'
    if sociales.oro(ses) < r['oro'] or sociales.oro(retador) < r['oro']:
        return 'One of you no longer has %d Gold.' % r['oro']
    sociales.cambiar_oro(ses, -r['oro'])
    sociales.cambiar_oro(retador, -r['oro'])
    _ID[0] += 1
    d = {'id': _ID[0], 'a': r['de'], 'b': int(ses.personaje.char_id), 'oro': r['oro'], 'fase': 'apuestas',
         'fin_apuestas': ahora + float(c['apuestas_s']), 'fin': 0, 'apuestas': {}, 'stage': ses.personaje.stage}
    _DUELOS.append(d)
    sociales.cartel('[Duel] %s vs %s for %d Gold in %s! Place your bets in Events (button on the bar), %d s.'
                    % (retador.personaje.nombre, ses.personaje.nombre, r['oro'] * 2,
                       sociales.nombre_mapa(d['stage']), int(c['apuestas_s'])))
    sociales.aviso(retador, '[Duel] %s accepted! The fight starts in %d seconds.' % (ses.personaje.nombre,
                                                                                      int(c['apuestas_s'])))
    return 'Duel accepted. The fight starts in %d seconds.' % int(c['apuestas_s'])


def rechazar(ses):
    r = _RETOS.pop(int(ses.personaje.char_id), None)
    if not r:
        return 'Nobody has challenged you.'
    retador = sociales.por_cid(r['de'])
    if retador:
        sociales.aviso(retador, '[Duel] %s declined your challenge.' % ses.personaje.nombre)
    return 'Challenge declined.'


def apostar(ses, nombre, oro):
    c = cfg()
    cid = int(ses.personaje.char_id)
    lado = sociales.por_nombre(nombre)
    if lado is None:
        return 'There is no player called %s online.' % nombre
    d = duelo_de(lado)
    if not d or d['fase'] != 'apuestas':
        return '%s is not in a duel open for bets.' % lado.personaje.nombre
    if cid in (d['a'], d['b']):
        return 'You cannot bet on your own duel.'
    if cid in d['apuestas']:
        return 'You already bet on this duel.'
    if oro < int(c['apuesta_min']):
        return 'The minimum bet is %d Gold.' % int(c['apuesta_min'])
    if sociales.oro(ses) < oro:
        return 'You do not have %d Gold.' % oro
    sociales.cambiar_oro(ses, -oro)
    d['apuestas'][cid] = [int(lado.personaje.char_id), int(oro)]
    ba, bb = _botes(d)
    return 'You bet %d Gold on %s. Bets: %s %d - %s %d.' % (oro, lado.personaje.nombre, _nombre(d['a']), ba,
                                                             _nombre(d['b']), bb)


def _devolver(d):
    for cid in (d['a'], d['b']):
        s = sociales.por_cid(cid)
        if s:
            sociales.cambiar_oro(s, d['oro'])
    for cid, (lado, oro) in d['apuestas'].items():
        s = sociales.por_cid(cid)
        if s:
            sociales.cambiar_oro(s, oro)
            sociales.aviso(s, '[Duel] The duel was cancelled: your %d Gold are back.' % oro)


def reparto(d, ganador):
    """{char_id: oro que cobra} de los apostadores (sin los duelistas)."""
    com = float(cfg()['comision']) / 100.0
    aciertan = {cid: o for cid, (lado, o) in d['apuestas'].items() if lado == ganador}
    fallan = sum(o for lado, o in d['apuestas'].values() if lado != ganador)
    total_ok = sum(aciertan.values())
    if not total_ok:
        return {}
    extra = fallan * (1 - com)
    return {cid: o + int(extra * o / total_ok) for cid, o in aciertan.items()}


def _cerrar(d, ganador, motivo=''):
    if d in _DUELOS:
        _DUELOS.remove(d)
    perdedor = d['b'] if ganador == d['a'] else d['a']
    sg = sociales.por_cid(ganador)
    if sg:
        sociales.cambiar_oro(sg, d['oro'] * 2)
        sociales.aviso(sg, '[Duel] You won the duel and %d Gold!' % (d['oro'] * 2))
    for cid, cobra in reparto(d, ganador).items():
        s = sociales.por_cid(cid)
        if s:
            sociales.cambiar_oro(s, cobra)
            sociales.aviso(s, '[Duel] Your bet won! You get %d Gold.' % cobra)
    sociales.cartel('[Duel] %s defeated %s%s and wins %d Gold!' % (_nombre(ganador), _nombre(perdedor), motivo,
                                                                 d['oro'] * 2))
    sociales.refrescar(*[s for s in (sg, sociales.por_cid(perdedor)) if s])
    try:
        __import__('honor').duelo(ganador, perdedor, d['oro'])
    except Exception:
        log.exception('honor del duelo')


def baja(ses, otro):
    d = duelo_de(ses)
    if not d or d['fase'] != 'pelea' or int(otro.personaje.char_id) not in (d['a'], d['b']):
        return False
    sociales.revivir(otro)
    _cerrar(d, int(ses.personaje.char_id))
    return True


def tick(ahora=None):
    ahora = ahora or time.time()
    for cid, r in list(_RETOS.items()):
        if ahora - r['ts'] > 60:
            _RETOS.pop(cid, None)
    for d in list(_DUELOS):
        sa, sb = sociales.por_cid(d['a']), sociales.por_cid(d['b'])
        if d['fase'] == 'apuestas':
            if sa is None or sb is None:
                _DUELOS.remove(d)
                _devolver(d)
                sociales.cartel('[Duel] %s vs %s was cancelled.' % (_nombre(d['a']), _nombre(d['b'])))
            elif ahora >= d['fin_apuestas']:
                d['fase'] = 'pelea'
                d['fin'] = ahora + float(cfg()['pelea_max_s'])
                ba, bb = _botes(d)
                for s in (sa, sb):
                    sociales.cartel_a(s, 'FIGHT! Defeat your opponent.')
                sociales.cartel('[Duel] %s vs %s: fight! Bets %d - %d.' % (sa.personaje.nombre, sb.personaje.nombre,
                                                                            ba, bb))
                sociales.refrescar(sa, sb)
            continue
        if sa is None or sb is None:
            _cerrar(d, d['b'] if sa is None else d['a'], ' (they ran away)')
        elif ahora >= d['fin']:
            _DUELOS.remove(d)
            _devolver(d)
            sociales.cartel('[Duel] %s vs %s ended in a draw: everything was refunded.'
                            % (sa.personaje.nombre, sb.personaje.nombre))
            sociales.refrescar(sa, sb)


def comando(ses, partes):
    sub = partes[1] if len(partes) > 1 else ''
    if sub.lower() in ('accept', 'aceptar', 'yes', 'si'):
        texto = aceptar(ses)
    elif sub.lower() in ('no', 'decline', 'rechazar'):
        texto = rechazar(ses)
    elif sub and len(partes) > 2 and str(partes[2]).isdigit():
        texto = retar(ses, sub, int(partes[2]))
    elif _DUELOS:
        filas = []
        for d in _DUELOS:
            ba, bb = _botes(d)
            filas.append('%s (%d) vs %s (%d), %s' % (_nombre(d['a']), ba, _nombre(d['b']), bb,
                                                    'bets open' if d['fase'] == 'apuestas' else 'fighting'))
        texto = 'Duels: ' + ' | '.join(filas)
    else:
        texto = 'Right-click a player and pick Duel to challenge them. Bet on duels from Events (button on the bar).'
    sociales.aviso(ses, '[Duel] ' + texto)


def comando_bet(ses, partes):
    if len(partes) < 3 or not str(partes[2]).isdigit():
        sociales.aviso(ses, '[Duel] Bet on duels from Events (button on the bar).')
        return
    sociales.aviso(ses, '[Duel] ' + apostar(ses, partes[1], int(partes[2])))
