"""Angel MOBA (23/11/2026): el oro de la partida y la tienda. "Que se puedan comprar items para mejorar los stats".

* EL ORO es solo de la partida (no se guarda): 'oro.inicial' al empezar, 'oro.cada' segundos 'oro.goteo', y por cada
  baja: el subdito, la unidad de jungla y el heroe al que lo mato (mas 'asistencia' a los de su equipo que esten
  cerca); la torre y el jefe a todo el equipo (plantillas/moba.json "tienda").
* LA TIENDA (58560, server/lua/moba.lua): los objetos de "tienda.objetos", objetos de verdad del juego con su icono
  (el cliente lo pone con game.getitemicon). Se compra en la base (a 'radio_base' casillas de su nucleo), muerto o,
  en cualquier sitio, tras 'fuera_de_combate' segundos sin recibir golpes ("no me deja comprar nada": solo en la base
  habia que cruzar el mapa, 23/11/2026). Se llevan como mucho 'max_objetos'. Cada uno suma a las estadisticas del heroe (hp, mp, atk, def, mdef) o resta
  recarga (cdr, con tope 'cdr_max'); la pocion (cura_pct) se gasta al comprarla.
* Se abre con el boton del MOBA de la barra estando en la partida. c2s 0x002F [175][7][i] compra el objeto i.
"""
import logging
import time

import canal_lua

log = logging.getLogger('moba')


def cfg():
    import moba
    return moba.config().get('tienda') or {}


def objetos():
    return cfg().get('objetos') or []


def bonus(h, clave):
    """Lo que suman los objetos del heroe a esa estadistica."""
    objs = objetos()
    return sum(float((objs[i].get('stats') or {}).get(clave, 0)) for i in getattr(h, 'objetos', ()) if i < len(objs))


def cdr(h):
    objs = objetos()
    total = sum(float(objs[i].get('cdr', 0)) for i in getattr(h, 'objetos', ()) if i < len(objs))
    return min(float(cfg().get('cdr_max', 0.3)), total)


# ---------------------------------------------------------------------------------------------- el oro
def dar_oro(h, cantidad, motivo=''):
    if h is None or cantidad <= 0:
        return
    h.oro += int(cantidad)
    try:
        if motivo:
            import clases
            h.ses.enviar(clases.aviso('+%d gold (%s)' % (int(cantidad), motivo), tipo=0))
        if getattr(h.ses, '_mb_tienda', False):
            h.ses.enviar(canal_lua.llamar('MBTiendaOro', titulo(h)))
    except Exception:
        log.debug('moba: oro', exc_info=True)


def al_caer(pa, tipo, equipo_ganador, matador_ses, centro):
    """Reparte el oro de una baja (moba.muere, moba_heroe.morir)."""
    import moba_heroe
    o = cfg().get('oro') or {}
    h = pa.heroes.get(matador_ses) if matador_ses is not None else None
    if tipo in ('torre', 'jefe'):
        for x in pa.heroes.values():
            if x.equipo == int(equipo_ganador):
                dar_oro(x, int(o.get(tipo, 0)), 'tower' if tipo == 'torre' else 'boss')
        return
    dar_oro(h, int(o.get(tipo, 0)), {'heroe': 'hero kill'}.get(tipo, ''))
    if tipo == 'heroe':
        radio = int((pa.cfg.get('exp') or {}).get('radio', 12))
        for x in pa.heroes.values():
            if x is not h and x.equipo == int(equipo_ganador) and not x.muerto:
                q = moba_heroe._pos(x)
                if max(abs(q[0] - centro[0]), abs(q[1] - centro[1])) <= radio:
                    dar_oro(x, int(o.get('asistencia', 0)), 'assist')


def goteo(pa, ahora):
    o = cfg().get('oro') or {}
    if ahora < getattr(pa, '_proximo_oro', 0):
        return
    primera = getattr(pa, '_proximo_oro', None) is None
    pa._proximo_oro = ahora + float(o.get('cada', 5))
    if primera:
        return
    for h in pa.heroes.values():
        dar_oro(h, int(o.get('goteo', 10)))


# ---------------------------------------------------------------------------------------------- comprar
def en_base(pa, h):
    import moba_heroe
    base = pa.cfg['equipos'][str(h.equipo)]['nucleo']
    q = moba_heroe._pos(h)
    return max(abs(q[0] - base[0]), abs(q[1] - base[1])) <= int(cfg().get('radio_base', 10))


def puede_comprar(pa, h, ahora=None):
    """'' si puede comprar ahora; si no, por que."""
    if h.muerto or en_base(pa, h):
        return ''
    espera = float(cfg().get('fuera_de_combate', 6))
    if espera <= 0:
        return 'Go back to your base to buy.'
    ahora = time.time() if ahora is None else ahora
    falta = espera - (ahora - float(getattr(h.ses, 'ultimo_combate', 0) or 0))
    if falta > 0:
        return 'In combat: you can buy in %d s (or at your base).' % int(falta + 0.99)
    return ''


def comprar(pa, h, i):
    """(ok, mensaje)."""
    import combate as cb
    import moba_heroe
    objs = objetos()
    if not 0 <= int(i) < len(objs):
        return False, 'Unknown item.'
    o = objs[int(i)]
    motivo = puede_comprar(pa, h)
    if motivo:
        return False, motivo
    if h.oro < int(o['precio']):
        return False, 'Not enough gold (%d).' % int(o['precio'])
    if o.get('cura_pct'):                            # se toma al momento
        if h.hp >= h.hp_max and h.mp >= h.mp_max:
            return False, 'You are already full.'
        h.oro -= int(o['precio'])
        moba_heroe.curar(pa, h, h.hp_max * float(o['cura_pct']))
        h.mp = min(h.mp_max, h.mp + int(h.mp_max * float(o['cura_pct'])))
        h.ses.enviar(cb.atributo(h.entidad, h.mp, cb.KIND_MP))
        return True, '%s used.' % o['nombre']
    if len(h.objetos) >= int(cfg().get('max_objetos', 6)):
        return False, 'Your bag is full (%d items).' % int(cfg().get('max_objetos', 6))
    hp_antes, mp_antes = h.hp_max, h.mp_max
    h.oro -= int(o['precio'])
    h.objetos.append(int(i))
    h.hp += h.hp_max - hp_antes                     # la vida y el mana nuevos llegan llenos
    h.mp += h.mp_max - mp_antes
    h.ses.enviar(*moba_heroe.paquetes_heroe(h))
    vestir(h.ses, int(o['id']))
    log.info('MOBA %s: %s compra %s', pa.id, h.ses.personaje.nombre, o['nombre'])
    return True, 'Bought %s!' % o['nombre']


# ---------------------------------------------------------------------------------------------- se ve puesto
def _redibujar(ses):
    """Su apariencia, a el (app._apariencia) y a los demas del mapa (presencia.notificar_equipo, el 0x0001)."""
    try:
        import app
        import presencia
        ses.enviar(*app._apariencia(ses))
        presencia.notificar_equipo(ses)
    except Exception:
        log.debug('moba: vestir', exc_info=True)


def vestir(ses, item_id):
    """Lo comprado se le ve puesto ("compro 1 espada, se me ve esa espada", 23/11/2026): solo a la vista
    (ses._mb_visual, que app._apariencia y presencia._spawn ponen por encima de lo suyo), el inventario no se toca.
    El ultimo de cada ranura es el que se ve; el collar no tiene ranura visible."""
    import app
    import inventario as inv
    r = inv.ranura_equipo_de(int(item_id))
    if r not in app.RANURAS_VISIBLES:
        return False
    ses.__dict__.setdefault('_mb_visual', {})[int(r)] = int(item_id)
    _redibujar(ses)
    return True


def desvestir(ses):
    """Al salir del MOBA: vuelve lo suyo (moba_heroe.salir)."""
    if getattr(ses, '_mb_visual', None):
        ses._mb_visual = {}
        _redibujar(ses)


# ---------------------------------------------------------------------------------------------- la ventana
def titulo(h):
    return 'Gold %d   Items %d/%d' % (h.oro, len(h.objetos), int(cfg().get('max_objetos', 6)))


def ventana(pa, h):
    import moba_lobby
    h.ses._mb_tienda = True
    filas = [[o['nombre'], int(o['precio']), o.get('texto', ''), int(o['id'])] for o in objetos()]
    propios = [int(objetos()[i]['id']) for i in h.objetos if i < len(objetos())]
    estado = puede_comprar(pa, h) or 'Click an item to buy it.'
    return moba_lobby.preparar(h.ses) + [canal_lua.llamar('MBTienda', titulo(h), estado, filas, propios)]


def procesar(ses, b):
    """Accion 7 del 0x002F del MOBA: comprar el objeto b."""
    import moba
    pa = moba.partida_de(ses)
    h = pa.heroes.get(ses) if pa else None
    if h is None:
        return
    ok, msg = comprar(pa, h, b)
    ses.enviar(*ventana(pa, h))
    ses.enviar(canal_lua.llamar('MBTiendaAviso', msg))
