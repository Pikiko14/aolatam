"""Angel MOBA (23/11/2026): el oro de la partida y la tienda. "Que se puedan comprar items para mejorar los stats".

* EL ORO es solo de la partida (no se guarda): 'oro.inicial' al empezar, 'oro.cada' segundos 'oro.goteo', y por cada
  baja: el subdito, la unidad de jungla y el heroe al que lo mato (mas 'asistencia' a los de su equipo que esten
  cerca); la torre y el jefe a todo el equipo (plantillas/moba.json "tienda").
* LA TIENDA (58560, server/lua/moba.lua): los objetos de "tienda.objetos", objetos de verdad del juego con su icono
  (el cliente lo pone con game.getitemicon). Se compra en la base (a 'radio_base' casillas de su nucleo), muerto o,
  en cualquier sitio, tras 'fuera_de_combate' segundos sin recibir golpes ("no me deja comprar nada": solo en la base
  habia que cruzar el mapa, 23/11/2026). Se llevan como mucho 'max_objetos'. Cada uno suma a las estadisticas del heroe (hp, mp, atk, def, mdef) o resta
  recarga (cdr, con tope 'cdr_max'); la pocion (cura_pct) se gasta al comprarla.
* Se abre con el boton Shop del marcador estando en la partida. c2s 0x002F [175][7][i] compra la casilla i de la
  pagina que ve; [175][8][0|1] pasa a la pagina anterior / siguiente (POR_PAGINA por pagina: "agrega mas de 30 items
  que se puedan comprar para las diferentes clases", 24/11/2026) y [175][9][k] cambia a la categoria k ("categorizalos":
  Weapons, Armor, Special, Potions; tienda.categorias y el 'cat' de cada objeto).
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


POR_PAGINA = 12                                  # tools/ventana_moba.py T_CASILLAS: las de la ventana


def indices_de(h):
    """Los objetos que ve ese heroe (indices de objetos()): las armas de su clase y los de todas."""
    return [i for i, o in enumerate(objetos()) if not o.get('clases') or h.clave in o['clases']]


def categorias():
    return cfg().get('categorias') or [['arma', 'Weapons'], ['defensa', 'Armor'], ['especial', 'Special'],
                                       ['consumible', 'Potions']]


def categoria(h):
    """La categoria que ve (0..)."""
    return max(0, min(int(getattr(h.ses, '_mb_cat', 0) or 0), len(categorias()) - 1))


def de_categoria(h):
    clave = categorias()[categoria(h)][0]
    return [i for i in indices_de(h) if objetos()[i].get('cat', 'arma') == clave]


def paginas(h):
    return max(1, (len(de_categoria(h)) + POR_PAGINA - 1) // POR_PAGINA)


def pagina(h):
    """La pagina que ve (0..), dentro de las que hay."""
    return max(0, min(int(getattr(h.ses, '_mb_pagina', 0) or 0), paginas(h) - 1))


def de_la_pagina(h):
    p = pagina(h)
    return de_categoria(h)[p * POR_PAGINA:(p + 1) * POR_PAGINA]


def bonus(h, clave):
    """Lo que suman los objetos del heroe a esa estadistica."""
    objs = objetos()
    return sum(float((objs[i].get('stats') or {}).get(clave, 0)) for i in getattr(h, 'objetos', ()) if i < len(objs))


# Lo que no es una estadistica entera del heroe: probabilidad de critico, parte de la defensa enemiga que se ignora,
# robo de vida y velocidad de ataque (24/11/2026), cada una con su tope ('<clave>_max').
TOPES = {'crit': 0.6, 'pen': 0.5, 'robo': 0.3, 'vel_ataque': 0.5}


def extra(h, clave):
    return max(0.0, min(float(cfg().get(clave + '_max', TOPES.get(clave, 1.0))), bonus(h, clave)))


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
    if tipo in ('torre', 'jefe', 'dragon'):
        for x in pa.heroes.values():
            if x.equipo == int(equipo_ganador):
                dar_oro(x, int(o.get(tipo, 0)), {'torre': 'tower', 'jefe': 'boss'}.get(tipo, tipo))
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
    if o.get('invisible'):                           # Stealth Potion: se toma al momento
        import moba_heroe
        if moba_heroe.invisible(h):
            return False, 'You are already invisible.'
        h.oro -= int(o['precio'])
        moba_heroe.volver_invisible(pa, h, float(o['invisible']))
        return True, 'Invisible for %d s: attacking reveals you.' % int(o['invisible'])
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


def _fashion_de(r):
    """La ranura de fashion que tapa a la de equipo r (presencia._spawn: 1..7 -> 167..173, 10 -> 174)."""
    return {10: 174}.get(int(r), int(r) + 166)


# El arma inicial del juego de cada clase de heroe (clases.ARMA_POR_SKILL): sin un arma de su tipo en la casilla 3 el
# cliente no deja usar sus poderes ni los ensena en la barra ("It needs equipment Sword Blade": "lo aprendi y no esta",
# 24/11/2026, un mago jugando de Swordsman). Se le pone a la vista al entrar, como lo comprado.
ARMA_INICIAL = {'espada': 10, 'hacha': 14, 'lanza': 15, 'arco': 16, 'sombra': 13485,
                'vida': 18, 'espectro': 18, 'caos': 18, 'tierra': 18}


def armar_al_entrar(ses, clave):
    arma = ARMA_INICIAL.get(clave)
    return vestir(ses, arma) if arma else False


def vestir(ses, item_id):
    """Lo comprado se le ve puesto ("compro 1 espada, se me ve esa espada", 23/11/2026): solo a la vista
    (ses._mb_visual, que app._apariencia y presencia._spawn ponen por encima de lo suyo), el inventario no se toca.
    El ultimo de cada ranura es el que se ve; el collar no tiene ranura visible.

    El jugador mismo lo dibuja desde SU INVENTARIO, no desde el 0x001D de apariencia (se mandaba bien, ranura 3 y
    169 con la Arclight Sword, y "no se ve el item"): al equipar de verdad va tambien el 0x001B de la casilla. Asi que
    a su cliente se le manda la casilla con lo comprado (y vacia la de fashion que lo taparia); en el servidor la
    bolsa sigue igual y al salir se le reenvian las casillas de verdad (desvestir)."""
    import app
    import inventario as inv
    r = inv.ranura_equipo_de(int(item_id))
    if r not in app.RANURAS_VISIBLES:
        return False
    ses.__dict__.setdefault('_mb_visual', {})[int(r)] = int(item_id)
    try:
        cid = ses.personaje.char_id
        pk = [inv.actualizar_ranura(cid, int(r), int(item_id), 1, inv.instancia_nueva(), app._dueno(ses))]
        if (getattr(ses, 'inventario', None) or {}).get(_fashion_de(r)):
            pk.append(inv.vaciar_ranura(ses.personaje.entity_id, _fashion_de(r)))
        ses.enviar(*pk)
    except Exception:
        log.debug('moba: casilla de lo comprado', exc_info=True)
    _redibujar(ses)
    return True


def desvestir(ses):
    """Al salir del MOBA: vuelve lo suyo (moba_heroe.salir), las casillas de verdad tambien."""
    tocadas = getattr(ses, '_mb_visual', None)
    if not tocadas:
        return
    ses._mb_visual = {}
    try:
        import app
        ses.enviar(*app._refrescar(ses, [x for r in tocadas for x in (int(r), _fashion_de(r))]))
    except Exception:
        log.debug('moba: casillas de verdad', exc_info=True)
    _redibujar(ses)


# ---------------------------------------------------------------------------------------------- la ventana
def titulo(h):
    return 'Gold %d   Items %d/%d   %s %d/%d' % (h.oro, len(h.objetos), int(cfg().get('max_objetos', 6)),
                                                 categorias()[categoria(h)][1], pagina(h) + 1, paginas(h))


def ventana(pa, h):
    import moba_lobby
    h.ses._mb_tienda = True
    filas = [[o['nombre'], int(o['precio']), o.get('texto', ''), int(o['id'])]
             for o in (objetos()[i] for i in de_la_pagina(h))]
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
    lista = de_la_pagina(h)                     # b es la casilla de la ventana, no el indice del catalogo
    ok, msg = comprar(pa, h, lista[int(b)]) if 0 <= int(b) < len(lista) else (False, 'Unknown item.')
    ses.enviar(*ventana(pa, h))
    ses.enviar(canal_lua.llamar('MBTiendaAviso', msg))


def pasar(ses, b):
    """Accion 8 del 0x002F del MOBA: b = 0 la pagina anterior, 1 la siguiente (da la vuelta)."""
    import moba
    pa = moba.partida_de(ses)
    h = pa.heroes.get(ses) if pa else None
    if h is None:
        return
    ses._mb_pagina = (pagina(h) + (1 if int(b) else -1)) % paginas(h)
    ses.enviar(*ventana(pa, h))


def elegir_categoria(ses, b):
    """Accion 9 del 0x002F del MOBA: la pestana b (0..), desde su primera pagina."""
    import moba
    pa = moba.partida_de(ses)
    h = pa.heroes.get(ses) if pa else None
    if h is None or not 0 <= int(b) < len(categorias()):
        return
    ses._mb_cat, ses._mb_pagina = int(b), 0
    ses.enviar(*ventana(pa, h))
