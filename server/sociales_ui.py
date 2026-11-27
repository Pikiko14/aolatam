"""Los eventos sociales con botones, sin comandos (25/11/2026): "que sea con accion: clic en el personaje, duelo, y ahi
colocar el monto; un panel de duelos y que se apueste por los demas antes que comiencen" y "para los usuarios normales
nada de comandos". Ventanas de tools/ventana_sociales.py, Lua en server/lua/sociales.lua.

c2s 0x002F [u8 178][u32 a][u32 b]:
    a=1 abrir el panel, 0 lo cerraron, 9 el cliente no tiene las ventanas (va por el chat); a=2 pestana b; a=3 dia b del calendario (0 lunes)
    a=20..23 el nombre del retado en trozos de 4 letras; a=24 retar con b de oro; 25 aceptar; 26 rechazar
    a=30+i / 40+i apostar b de oro al primero / segundo del duelo i del panel
    a=50 apuntarse / salir de El cazador cazado; a=60+i votar la opcion i
El panel abierto se refresca solo (sociales.vigilar, cada 5 s) y tras cada accion.
"""
import datetime as dt
import logging
import struct
import time

import canal_lua
import sociales

log = logging.getLogger('sociales_ui')

CMD_SO = 178
SALUDO_LUA = (canal_lua.CARPETA / 'sociales.lua').read_text(encoding='utf-8')


def _miles(n):
    return format(int(n), ',')


def _corto(n):
    """1,500,000 -> 1.5M, 40,000 -> 40K."""
    n = int(n)
    for div, suf in ((1000000000, 'B'), (1000000, 'M'), (1000, 'K')):
        if n >= div:
            t = ('%.1f' % (n / div)).rstrip('0').rstrip('.')
            return t + suf
    return str(n)


def proxima(clave, ahora=None):
    """'HH:MM' (o 'Day HH:MM') de la proxima vez del evento en el calendario, o ''."""
    import calendario
    ahora = ahora or calendario._ahora()
    mejor = None
    for wd, h in (calendario.slots(clave) or []):
        hh, mm = (int(x) for x in h.split(':'))
        dias = (wd - ahora.weekday()) % 7
        cuando = (ahora + dt.timedelta(days=dias)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if cuando <= ahora:
            cuando += dt.timedelta(days=7)
        if mejor is None or cuando < mejor:
            mejor = cuando
    if mejor is None:
        return ''
    return mejor.strftime('%H:%M') if mejor.date() == ahora.date() else mejor.strftime('%A %H:%M')


PESTANAS = ('Duels', 'Hunted Hunter', 'Weekly Vote', 'Treasure Hunt', 'Calendar')
DIAS_CORTOS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
N_DUELOS = 5


def _duelos(ses, ahora):
    import duelos
    cid = int(ses.personaje.char_id)
    filas, ids = [], []
    for d in duelos._DUELOS[:N_DUELOS]:
        ba, bb = duelos._botes(d)
        a, b = duelos._nombre(d['a']), duelos._nombre(d['b'])
        if d['fase'] == 'apuestas':
            resto = '%ds to bet' % max(0, int(d['fin_apuestas'] - ahora))
            puede = cid not in (d['a'], d['b']) and cid not in d['apuestas']
        else:
            resto, puede = 'FIGHTING!', False
        # la tarjeta: [centro, luchador A, luchador B, 1 si se puede apostar]; las apuestas a cada uno, junto al nombre
        filas.append(['VS  Pot %s  -  %s' % (_corto(d['oro'] * 2), resto),
                      '%s (%s)' % (a, _corto(ba)) if ba else a, '%s (%s)' % (b, _corto(bb)) if bb else b,
                      1 if puede else 0])
        ids.append(d['id'])
    ses._soc_duelos = ids
    return filas


CAJAS = ((89171, 'Lv40 Gear Gacha'), (89200, 'Lv60 Box'))     # santa_clausula.GACHAS_40 / CAJAS_60


def _caja(ids):
    for base, nombre in CAJAS:
        if base in ids:
            return nombre
    return 'an item'


def _premio_txt(p):
    partes = []
    if p.get('ag'):
        partes.append('%s Angel Gold' % _miles(p['ag']))
    if p.get('oro_por_nivel'):
        partes.append('%s gold x lv' % _miles(p['oro_por_nivel']))
    if p.get('exp'):
        partes.append('%d%% lv EXP' % int(round(float(p['exp']) * 100)))
    for it in p.get('items') or []:
        prob = float(it.get('prob', 1))
        partes.append(_caja(it['de']) + ('' if prob >= 1 else ' (%d%%)' % int(round(prob * 100))))
    return ', '.join(partes)


def _p_duelos(ses, ahora):
    c = sociales.config()['duelo']
    filas = _duelos(ses, ahora)
    abiertos = sum(1 for f in filas if f[3])
    estado = ('%d duel%s right now, %d open for bets.' % (len(filas), '' if len(filas) == 1 else 's', abiertos)
              if filas else 'No duels right now. Be the first: right-click a player!')
    reglas = ['Right-click a player, pick Duel and set the stake (min %s gold).' % _miles(c['oro_min']),
              'Once accepted, everyone has %d s to bet: amount, then a name.' % int(c['apuestas_s']),
              'Winner takes both stakes. Right bets share the rest (-%d%% fee).' % int(c['comision']),
              'Duels are safe: no EXP is lost. Fights last up to %d minutes.' % (int(c['pelea_max_s']) // 60)]
    return estado, reglas, ['then click a fighter', filas]


def _p_caza(ses):
    import cazador
    c = sociales.config()['caza']
    act = cazador.activa()
    dentro = cazador.apuntado(ses)
    nxt = proxima('caza')
    boton = 'Leave' if dentro else 'Join'
    if act:
        presa = cazador._presa()
        nombre = presa.personaje.nombre if presa else '?'
        resto = int((act['fin'] - time.time()) // 60) + 1
        estado = 'LIVE: %s is the prey! %d min left.' % (nombre, resto)
        if cazador.es_presa(ses):
            lineas = ['YOU ARE THE PREY! Survive %d more minutes in hunting fields.' % resto,
                      'Hiding in towns does not count: stay in the fields.']
            boton = ''
        else:
            lineas = ['Prey: %s' % nombre, 'Last seen: %s' % (cazador._posicion(presa) if presa else '?')]
        lineas += ['Hunters online: %d' % len(cazador._cazadores()),
                   'You are %s.' % ('signed up' if dentro else 'not signed up')]
    else:
        estado = ('Next hunt: %s.' % nxt if nxt else 'No hunt scheduled.') + ' %d signed up.' % len(cazador.APUNTADOS)
        lineas = ['You are %s.' % ('SIGNED UP: wait in a hunting field' if dentro else 'not signed up yet'),
                  'Next hunt: %s' % (nxt or '-'),
                  'Players signed up: %d (at least 2 needed)' % len(cazador.APUNTADOS),
                  'Minimum level: %d' % int(c['nivel_min'])]
    lineas += ['Prey wins: %s' % _premio_txt(c['premio_presa']),
               'Hunter wins: %s' % _premio_txt(c['premio_cazador'])]
    reglas = ['Sign up here. At hunt time one player in a field becomes the prey.',
              'The prey is announced every minute for %d minutes.' % int(c['duracion_min']),
              'Only signed-up players can attack the prey. The prey fights back.',
              'Survive to win. Hiding in towns twice loses. No EXP is lost.']
    return estado, reglas, [lineas[:6], boton]


def _p_voto(ses):
    import votacion
    ahora = votacion._ahora()
    titulo, l1, l2, _pie, filas = votacion.vista(ses, ahora)
    clave = votacion.clave_semana(ahora)
    mio = votacion._semana(clave)['votos'].get(str(ses.personaje.char_id))
    opciones = ['%s  -  %s (%d%%)%s' % (f[0].split('. ', 1)[-1], f[1], f[2], '   [YOUR VOTE]' if mio == i else '')
                for i, f in enumerate(filas)]
    reglas = ['Vote Monday to Thursday. You can change your vote until then.',
              'Voting closes Friday 00:00. The most voted option wins.',
              'A double EXP map gives +%d%% EXP there all weekend.'
              % int(sociales.config()['votacion']['exp_doble']),
              'Extra events join the weekend calendar. One vote per character.']
    return titulo, reglas, [l2, opciones, l1]


def _p_tesoro():
    import tesoro_servidor as ts
    c = ts.cfg()
    t = ts.activo()
    nxt = proxima('tesoro')
    if t:
        resto = int((t['fin'] - time.time()) // 60) + 1
        estado = 'LIVE! A chest is hidden somewhere. %d min left.' % resto
        lineas = ['CLUES SO FAR (a new one every %d min):' % int(c['pista_cada_min'])]
        lineas += ['Clue %d: %s' % (n + 1, ts.pista(n, t)) for n in range(min(5, int(t['pistas'])))]
    else:
        estado = ('Next treasure hunt: %s.' % nxt) if nxt else 'No treasure hunt scheduled.'
        lineas = ['Next treasure hunt: %s' % (nxt or '-'),
                  'The clues will appear here when the hunt starts.',
                  'REWARD FOR THE WINNER:']
        p = c['premio']
        lineas += ['%s Angel Gold  +  %s gold x your level' % (_miles(p.get('ag', 0)), _miles(p.get('oro_por_nivel', 0))),
                   '%d%% of a level in EXP' % int(round(float(p.get('exp', 0)) * 100)),
                   ', '.join(_caja(it['de']) + ('' if float(it.get('prob', 1)) >= 1 else
                                                ' (%d%% chance)' % int(round(float(it['prob']) * 100)))
                             for it in p.get('items') or [])]
    reglas = ['A chest appears on a random hunting map at the times shown.',
              'A new clue every %d min: letters, map, area, coordinates.' % int(c['pista_cada_min']),
              'The first to click the chest (within %d tiles) wins it.' % int(c['radio']),
              'It vanishes after %d minutes. Anyone can join, no sign-up.' % int(c['duracion_min'])]
    return estado, reglas, [lineas[:6]]


def _semana_entera():
    """[(dia, 'HH:MM', nombre, duracion_min)] de toda la semana: el calendario (calendario.py, con lo votado; el
    Angel Arena Lv50-89 tambien va en el)."""
    import calendario
    eventos = calendario.config().get('eventos') or {}
    filas = [(d, h, calendario.nombre(c), int((eventos.get(c) or {}).get('duracion', 30)))
             for d, h, c in calendario.semana()]
    return sorted(filas)


def _cuanto(minutos):
    h, m = divmod(int(minutos), 60)
    return ('in %dh %02dm' % (h, m)) if h else ('in %d min' % max(1, m))


def _p_calendario(ses):
    import calendario
    ahora = calendario._ahora()
    hoy = ahora.weekday()
    dia = getattr(ses, '_soc_dia', None)
    dia = hoy if dia is None else int(dia) % 7
    semana = _semana_entera()
    filas, siguiente = [], None
    for d, h, nombre, dur in semana:
        if d != dia:
            continue
        hh, mm = (int(x) for x in h.split(':'))
        estado = ''
        if d == hoy:
            ini = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
            fin = ini + dt.timedelta(minutes=dur)
            if ahora >= fin:
                estado = 'done'
            elif ahora >= ini:
                estado = '>> LIVE NOW <<'
            else:
                estado = _cuanto((ini - ahora).total_seconds() // 60)
        filas.append(['%s   %s  (%d min)' % (h, nombre, dur), estado])
    for d, h, nombre, dur in semana:                 # el proximo de hoy, para la cabecera
        hh, mm = (int(x) for x in h.split(':'))
        if d == hoy and ahora < ahora.replace(hour=hh, minute=mm, second=0, microsecond=0):
            siguiente = (h, nombre)
            break
    estado = ('Next today: %s at %s.' % (siguiente[1], siguiente[0])) if siguiente else 'No more events today.'
    titulos = [('Today' if i == hoy else DIAS_CORTOS[i]) for i in range(7)]
    pie = 'Server time now: %s. A warning goes out %d min before each event.' % (
        ahora.strftime('%H:%M'), int(calendario.config().get('aviso_min', 30)))
    if not filas:
        filas = [['No events this day.', '']]
    return estado, ['', '', '', ''], [dia, titulos, filas[:14], pie]


def _titulos(ses):
    import cazador
    import duelos
    import tesoro_servidor as ts
    n = len(duelos._DUELOS)
    return ['Duels (%d)' % n if n else 'Duels', 'Hunt: LIVE!' if cazador.activa() else 'Hunted Hunter',
            'Weekly Vote', 'Treasure LIVE!' if ts.activo() else 'Treasure Hunt', 'Calendar']


def vista(ses, ahora=None):
    ahora = ahora or time.time()
    pestana = int(getattr(ses, '_soc_tab', 1) or 1)
    if pestana == 1:
        estado, reglas, d = _p_duelos(ses, ahora)
    elif pestana == 2:
        estado, reglas, d = _p_caza(ses)
    elif pestana == 3:
        estado, reglas, d = _p_voto(ses)
    elif pestana == 4:
        estado, reglas, d = _p_tesoro()
    else:
        estado, reglas, d = _p_calendario(ses)
    return pestana, _titulos(ses), estado, reglas, d


def abrir(ses):
    ses._soc_abierto = True
    ses.enviar(canal_lua.paquete(SALUDO_LUA), canal_lua.llamar('SocialAbrir', *vista(ses)))


def refrescar(ses):
    if getattr(ses, '_soc_abierto', False):
        try:
            ses.enviar(canal_lua.llamar('SocialDatos', *vista(ses)))
        except Exception:
            log.debug('sociales: refrescar el panel', exc_info=True)


def refrescar_todos():
    for s in sociales.sesiones():
        refrescar(s)


def reto_recibido(otro, nombre, oro):
    """Al retado: la ventanita con Accept / Decline."""
    try:
        otro.enviar(canal_lua.paquete(SALUDO_LUA), canal_lua.llamar('DueloAbrir', 'recibido', nombre, int(oro)))
    except Exception:
        log.debug('sociales: reto recibido', exc_info=True)


def lineas(ses):
    """Sin las ventanas (va por el chat): el estado de cada pestana."""
    out = []
    viejo = getattr(ses, '_soc_tab', 1)
    try:
        for k, nombre in enumerate(PESTANAS, 1):
            ses._soc_tab = k
            out.append('[Events] %s: %s' % (nombre, vista(ses)[2]))
    finally:
        ses._soc_tab = viejo
    return out


def _duelo_por_indice(ses, i):
    import duelos
    ids = getattr(ses, '_soc_duelos', None) or []
    if not 0 <= i < len(ids):
        return None
    return next((d for d in duelos._DUELOS if d['id'] == ids[i]), None)


def procesar(ses, cuerpo) -> bool:
    """El 0x002F del panel y de la ventanita del duelo. True si era suyo."""
    if len(cuerpo) < 9 or cuerpo[0] != CMD_SO or getattr(ses, 'personaje', None) is None:
        return False
    import cazador
    import duelos
    import votacion
    a, b = struct.unpack_from('<II', cuerpo, 1)
    texto = None
    if a == 1:
        abrir(ses)
        return True
    if a == 0:
        ses._soc_abierto = False
        return True
    if a == 2:
        ses._soc_tab = max(1, min(len(PESTANAS), int(b)))
        if ses._soc_tab == len(PESTANAS):
            ses._soc_dia = None                       # el calendario se abre en hoy
        refrescar(ses)
        return True
    if a == 3:
        ses._soc_dia = int(b) % 7
        refrescar(ses)
        return True
    if a == 9:
        ses._soc_abierto = False
        for linea in lineas(ses):
            sociales.aviso(ses, linea)
        return True
    if 20 <= a <= 23:
        trozos = getattr(ses, '_soc_nombre', None) or [b'\0' * 4] * 4
        trozos[a - 20] = struct.pack('<I', b)
        ses._soc_nombre = trozos
        return True
    if a == 24:
        nombre = b''.join(getattr(ses, '_soc_nombre', None) or []).split(b'\0')[0].decode('latin-1', 'replace')
        ses._soc_nombre = None
        texto = duelos.retar(ses, nombre, int(b))
    elif a == 25:
        texto = duelos.aceptar(ses)
    elif a == 26:
        texto = duelos.rechazar(ses)
    elif 30 <= a < 30 + N_DUELOS or 40 <= a < 40 + N_DUELOS:
        d = _duelo_por_indice(ses, a % 10)
        if d is None or d['fase'] != 'apuestas':
            texto = 'That duel is no longer open for bets.'
        else:
            lado = d['a'] if a < 40 else d['b']
            texto = duelos.apostar(ses, duelos._nombre(lado), int(b))
    elif a == 50:
        cazador.comando(ses, ['hunt', 'leave' if cazador.apuntado(ses) else 'join'])
    elif 60 <= a <= 64:
        texto = votacion.votar(ses, a - 59)
    if texto:
        sociales.aviso(ses, '[Events] ' + texto)
    refrescar(ses)
    return True
