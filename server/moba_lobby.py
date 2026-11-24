"""Angel MOBA, fase 2b (23/11/2026): la inscripcion y la ventana para elegir clase.

* A LAS HORAS FIJAS de plantillas/moba.json "inscripcion.horarios" (hora del servidor, competiciones zona_horaria) se
  abre la inscripcion 'abierta_min' minutos antes y se anuncia a todo el mundo. Cada uno se apunta desde la ventana
  (boton 59006 de la barra) con la clase que haya elegido ("que se deba elegir que clase se quiere jugar en ese
  evento"). A la hora, los apuntados se reparten en partidas de 5 contra 5 (por_equipo), equilibradas por orden de
  llegada; si en la ultima no hay 'minimo' jugadores, esos se quedan sin partida y se les avisa.
* LA VENTANA (server/lua/moba.lua, tools/ventana_moba.py): las 9 clases como tarjetas; el clic ensena su papel, sus
  numeros y sus 4 poderes (la ultimate desde nivel 6) y la deja elegida; Join apunta con ella, Leave quita de la cola.
* c2s 0x002F [u8 175][u32 accion][u32 valor]:
      1 abrir la ventana        2 elegir la clase `valor` (0..8)        3 apuntarse        4 desapuntarse
      5 el ranking de la temporada (moba_ranking.py)      6 en partida: gastar un punto en el poder `valor` (0..3)
      7 en partida: comprar el objeto `valor` de la tienda (moba_tienda.py); el 1 en partida abre la tienda
* EL GM: /moba open (abre la inscripcion ya, 'abierta_min' minutos) y /moba go (empieza ya con los apuntados).
"""
import datetime as dt
import logging
import time

import canal_lua

log = logging.getLogger('moba')

CMD_MOBA = 175
# "El npc del MOBA en el mapa donde esta el de HBF, que no sea 1 icono" (24/11/2026): la inscripcion es el NPC
# Angel MOBA de la Sign Up Office (114, en 66,30, junto al BattlefieldClerk; plantillas/sign_up_office.json). Ya no
# hay icono en la barra (tools/ventana_moba.wnd01 lo quita): la tienda es el boton Shop del marcador de la partida.
NPC_NOMBRE, NPC_STAGE = 'Angel MOBA', 114
# Para el cliente que aun tenga el boton 59006 de antes.
SALUDO_LUA = ('function OnCommandMoba(dwID, dwCmdID, dwParam, pParam) '
              'game.netcommand2(%d, 1, 0) return 1 end' % CMD_MOBA)

_COLA = {}                   # sesion -> clase (por orden de llegada: los dict lo guardan)
_ESTADO = {'empieza': None, 'abierta_desde': None, 'anunciado': set(), 'ultimo': None}


def _cfg():
    import moba
    return moba.config().get('inscripcion') or {}


def _clases():
    import moba
    return list((moba.config().get('clases') or {}).items())


def _ahora_local():
    try:
        import competiciones
        zona = competiciones.config_eventos().get('zona_horaria')
        if zona:
            import zoneinfo
            return dt.datetime.now(zoneinfo.ZoneInfo(zona))
    except Exception:
        pass
    return dt.datetime.now().astimezone()


def proxima(ahora_local=None):
    """El datetime de la proxima partida programada (hoy o manana)."""
    ahora_local = ahora_local or _ahora_local()
    horas = []
    for h in _cfg().get('horarios') or []:
        hh, mm = (int(x) for x in str(h).split(':'))
        for dias in (0, 1):
            t = (ahora_local + dt.timedelta(days=dias)).replace(hour=hh, minute=mm, second=0, microsecond=0)
            if t > ahora_local:
                horas.append(t)
    return min(horas) if horas else None


def abierta(ahora=None):
    ahora = time.time() if ahora is None else ahora
    e = _ESTADO['empieza']
    return e is not None and _ESTADO['abierta_desde'] is not None and _ESTADO['abierta_desde'] <= ahora < e


def _anunciar(texto):
    try:
        import competiciones
        competiciones.anunciar(texto)
    except Exception:
        log.debug('moba: anunciar', exc_info=True)


def abrir_inscripcion(empieza, ahora=None):
    ahora = time.time() if ahora is None else ahora
    _ESTADO['empieza'], _ESTADO['abierta_desde'], _ESTADO['anunciado'] = float(empieza), ahora, set()
    minutos = max(1, int(round((empieza - ahora) / 60.0)))
    _anunciar('Angel MOBA sign-up is open! 5 vs 5 in %d minute%s. Talk to Angel MOBA in the Sign Up Office and pick your class.'
              % (minutos, '' if minutos == 1 else 's'))
    log.info('MOBA: inscripcion abierta, empieza en %d min', minutos)


def cron(ahora=None):
    """Cada pocos segundos (competiciones.reloj): abre la inscripcion, avisa y arma las partidas a la hora."""
    ahora = time.time() if ahora is None else ahora
    c = _cfg()
    if _ESTADO['empieza'] is None:
        t = proxima()
        if t is not None and t.timestamp() - ahora <= float(c.get('abierta_min', 10)) * 60:
            if _ESTADO['ultimo'] != t.timestamp():
                abrir_inscripcion(t.timestamp(), ahora)
        return
    falta = _ESTADO['empieza'] - ahora
    for m in (5, 1):
        if 0 < falta <= m * 60 and m not in _ESTADO['anunciado'] and falta < float(c.get('abierta_min', 10)) * 60 - 30:
            _ESTADO['anunciado'].add(m)
            _anunciar('Angel MOBA starts in %d minute%s! %d player%s signed up.' % (
                m, '' if m == 1 else 's', len(_vivos()), '' if len(_vivos()) == 1 else 's'))
    if falta <= 0:
        _ESTADO['ultimo'] = _ESTADO['empieza']
        _ESTADO['empieza'] = _ESTADO['abierta_desde'] = None
        armar()


def _vivos():
    import moba
    for s in list(_COLA):
        if getattr(s, 'cerrada', False) or getattr(s, 'personaje', None) is None or moba.partida_de(s) is not None:
            _COLA.pop(s, None)
    return list(_COLA)


def repartir(gente, por_equipo=5, minimo=2):
    """[[(sesion, equipo)], ...]: grupos de hasta 2 x por_equipo, alternando equipos. El ultimo, si no llega al minimo,
    no juega (devuelve tambien los que se quedan fuera)."""
    grupos, fuera = [], []
    tam = 2 * int(por_equipo)
    for i in range(0, len(gente), tam):
        trozo = gente[i:i + tam]
        if len(trozo) < int(minimo):
            fuera += trozo
            continue
        grupos.append([(s, 1 + k % 2) for k, s in enumerate(trozo)])
    return grupos, fuera


def armar(ahora=None):
    """Empieza las partidas con los apuntados. Devuelve cuantas."""
    import clases
    import moba
    c = _cfg()
    gente = _vivos()
    grupos, fuera = repartir(gente, int(c.get('por_equipo', 5)), int(c.get('minimo', 2)))
    for s in fuera:
        try:
            s.enviar(clases.aviso('Not enough players for an Angel MOBA match this time. See you at the next one!', tipo=0))
        except Exception:
            pass
    for grupo in grupos:
        moba.empezar_partida([(s, eq, _COLA.get(s)) for s, eq in grupo], ahora)
    _COLA.clear()
    if not grupos and gente:
        _anunciar('Angel MOBA: not enough players this time.')
    elif grupos:
        _anunciar('Angel MOBA has begun! %d match%s, %d heroes.' % (len(grupos), '' if len(grupos) == 1 else 'es',
                                                                   sum(len(g) for g in grupos)))
    return len(grupos)


# ---------------------------------------------------------------------------------------------- apuntarse
def apuntar(ses, clave):
    import moba
    nombres = dict(_clases())
    if clave not in nombres:
        return False, 'Choose a class first.'
    if moba.partida_de(ses) is not None:
        return False, 'You are already in a match.'
    if not abierta():
        return False, 'Sign-up is closed.'          # el horario ya va en la linea de arriba (cabe al lado de Join)
    nivel_min = int(_cfg().get('nivel_min', 0))
    if int(getattr(ses.personaje, 'nivel', 0) or 0) < nivel_min:
        return False, 'You need level %d.' % nivel_min
    _COLA[ses] = clave
    return True, 'Signed up as %s.' % nombres[clave]['nombre']


def quitar(ses):
    return _COLA.pop(ses, None) is not None


def _texto_horario():
    t = proxima()
    horas = ', '.join(str(h) for h in _cfg().get('horarios') or [])
    if t is None:
        return 'No matches scheduled.'
    return 'Next match at %s (daily: %s).' % (t.strftime('%H:%M'), horas)


def estado(ses):
    """La linea de arriba de la ventana."""
    import moba
    if moba.partida_de(ses) is not None:
        return 'You are in a match. Good luck!'
    if abierta():
        falta = max(0, int(_ESTADO['empieza'] - time.time()))
        yo = (' You: %s.' % dict(_clases())[_COLA[ses]]['nombre']) if ses in _COLA else ''
        return 'Sign-up open: %d signed up, starts in %d:%02d.%s' % (len(_vivos()), falta // 60, falta % 60, yo)
    return 'Sign-up closed. ' + _texto_horario()


# ---------------------------------------------------------------------------------------------- la ventana
def _lua():
    return (canal_lua.CARPETA / 'moba.lua').read_text(encoding='utf-8')


def preparar(ses):
    if getattr(ses, '_mb_lua', False):
        return []
    ses._mb_lua = True
    return [canal_lua.paquete(_lua())]


def ficha(clave):
    """[titulo, linea de numeros, 4 lineas de poderes]."""
    d = dict(_clases())[clave]
    b = d['base']
    titulo = '%s - %s (%s)' % (d['nombre'], d.get('rol', ''), 'physical' if d.get('fisico', True) else 'magic')
    numeros = 'HP %d  MP %d  ATK %d  DEF %d  Range %d' % (b['hp'], b['mp'], b['atk'], b['def'], int(d.get('alcance', 1)))
    lineas = []
    for p in d['poderes']:
        extra = []
        if p.get('radio'):
            extra.append('area')
        for k, t in (('lento', 'slow'), ('aturde', 'stun'), ('dot', 'poison'), ('drenaje', 'drain')):
            if p.get(k):
                extra.append(t)
        tipo = {'dano': 'damage', 'area': 'area damage', 'cura': 'heal', 'escudo': 'shield'}.get(p['tipo'], p['tipo'])
        lineas.append('%s%s: %s%s  CD %ds  MP %d' % ('ULT (Lv %d) ' % int(p.get('nivel_min', 1)) if p.get('ultimate') else '', p['nombre'], tipo,
                                                   (' + ' + ', '.join(e for e in extra if e != 'area')) if [e for e in extra if e != 'area'] else '',
                                                   int(p.get('cd', 0)), int(p.get('mana', 0))))
    return titulo, numeros, lineas


def abrir(ses):
    clases_ = [[d['nombre'], d.get('rol', '')] for _c, d in _clases()]
    pk = preparar(ses) + [canal_lua.llamar('MBAbrir', clases_, estado(ses))]
    elegida = getattr(ses, '_mb_clase', None) or _COLA.get(ses)
    claves = [c for c, _ in _clases()]
    if elegida in claves:
        pk.append(canal_lua.llamar('MBClase', claves.index(elegida) + 1, *ficha(elegida)))
    return pk


def _linea_marca(ses):
    import moba_ranking as rk
    n = rk.temporada()[0]
    puesto, f = rk.mi_marca(getattr(ses.personaje, 'char_id', 0), n)
    if f is None:
        return 'You have no points yet in season %d.' % n
    r = rk.rango(int(f[3] or 0), puesto)
    return 'You: #%d  %d pts  %d wins / %d games%s' % (puesto, int(f[3] or 0), int(f[4] or 0), int(f[5] or 0),
                                                       ('  (%s)' % r) if r else '')


def ranking(ses):
    """La ventana del ranking de la temporada: los 10 primeros, la marca del jugador, los rangos y los premios."""
    import moba_ranking as rk
    n, _desde, hasta = rk.temporada()
    falta = max(0, hasta - time.time())
    titulo = 'Season %d - ends in %dd %dh' % (n, int(falta // 86400), int(falta % 86400 // 3600))
    filas = []
    for i, (_cid, _u, nombre, puntos, victorias, partidas, bajas) in enumerate(rk.ranking(n)):
        filas.append([i + 1, nombre, rk.rango(int(puntos or 0), i + 1) or '-', '{:,}'.format(int(puntos or 0)),
                      '%dW %dG %dK' % (int(victorias or 0), int(partidas or 0), int(bajas or 0))])
    c = rk._cfg()
    r, pr = c.get('rangos') or {}, c.get('premios') or {}
    rangos = 'Bronze {}  Silver {}  Gold {}  Angel top {}  Champion #1'.format(
        r.get('Bronze', 100), r.get('Silver', 300), r.get('Gold', 600), r.get('angel_top', 10))
    premios = 'Rewards (AG): ' + '  '.join('%s %s' % (k, '{:,}'.format(int((pr.get(k) or {}).get('angel_gold', 0))))
                                           for k in ('Champion', 'Angel', 'Gold', 'Silver', 'Bronze') if pr.get(k))
    return preparar(ses) + [canal_lua.llamar('MBRanking', titulo, filas, _linea_marca(ses), rangos, premios)]


def procesar(ses, cuerpo, addr='?') -> bool:
    """El 0x002F de la ventana del MOBA. True si era suyo."""
    import struct
    if len(cuerpo) < 9 or cuerpo[0] != CMD_MOBA:
        return False
    a, b = struct.unpack_from('<II', cuerpo, 1)
    claves = [c for c, _ in _clases()]
    if a == 1:
        import moba
        pa = moba.partida_de(ses)
        h = pa.heroes.get(ses) if pa else None
        if h is not None:                             # en partida: la tienda (y los puntos de poder si le quedan)
            import moba_heroe
            import moba_tienda
            ses.enviar(*moba_tienda.ventana(pa, h))
            if h.puntos > 0:
                ses.enviar(*moba_heroe.ventana_puntos(h))
            return True
        ses.enviar(*abrir(ses))
    elif a == 2 and b < len(claves):
        ses._mb_clase = claves[b]
        if ses in _COLA and abierta():
            _COLA[ses] = claves[b]
        ses.enviar(*(preparar(ses) + [canal_lua.llamar('MBClase', b + 1, *ficha(claves[b])),
                                      canal_lua.llamar('MBEstado', estado(ses))]))
    elif a == 3:
        ok, msg = apuntar(ses, getattr(ses, '_mb_clase', None))
        log.info('MOBA: %s se apunta: %s', getattr(ses.personaje, 'nombre', '?'), msg)
        ses.enviar(canal_lua.llamar('MBAviso', msg), canal_lua.llamar('MBEstado', estado(ses)))
    elif a == 5:
        ses.enviar(*ranking(ses))
    elif a == 7:
        __import__('moba_tienda').procesar(ses, b)
    elif a == 6:
        import moba
        import moba_heroe
        pa = moba.partida_de(ses)
        h = pa.heroes.get(ses) if pa else None
        if h is not None:
            ok, msg = moba_heroe.subir(h, b)
            ses.enviar(*moba_heroe.ventana_puntos(h))
            if not ok:
                ses.enviar(canal_lua.llamar('MBPuntosAviso', msg))
    elif a == 4:
        msg = 'You left the queue.' if quitar(ses) else 'You were not signed up.'
        ses.enviar(canal_lua.llamar('MBAviso', msg), canal_lua.llamar('MBEstado', estado(ses)))
    return True
