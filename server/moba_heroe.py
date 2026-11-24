"""Angel MOBA, fase 2a (23/11/2026): el heroe. "Que el personaje empiece lvl 1 y suba max a 18, elige 3 poderes y 1
ultimate por clase, que se deba elegir que clase se quiere jugar en ese evento".

* LA CLASE: cada jugador elige una de plantillas/moba.json "clases" (no hace falta que sea la de su personaje). Sus
  estadisticas en el evento son las de la clase a su nivel (base + por_nivel x (nivel - 1)): vida, mana, ataque,
  defensa y defensa magica. Empieza a nivel 1 y sube hasta el 18 con la experiencia de la partida ("niveles").
* NADA SE GUARDA EN EL PERSONAJE: el combate del heroe lo lleva este modulo. Su vida y su mana del evento viven aqui
  (Heroe.hp / mp) y al cliente se le ENSENAN (nivel, vida, mana, barra de atajos con sus 4 poderes); p.nivel, p.hp,
  p.barra... no se tocan. Al salir se le vuelven a mandar los suyos.
* LOS PODERES se desbloquean con puntos: uno por nivel (y uno al empezar); en la ventana MBPuntos el jugador elige
  cual desbloquear o subir de rango (rangos_poder de moba.json). La barra solo tiene los aprendidos.
* EL COMBATE: el c2s 0x0006 (ataque basico 656 o el hechizo pedido) de un heroe llega a accion() y no al combate
  normal. Solo valen el basico y los 4 poderes de su clase (la ultimate desde nivel_min). Pegan a las unidades del
  MOBA (moba.py) y a los heroes enemigos. Las unidades le pegan con unidad_golpea().
* LA MUERTE: vida 0 = el paquete de muerte de siempre; reaparece en su base a los respawn.base + por_nivel x nivel
  segundos (no se puede revivir antes: app ignora el boton de revivir de un heroe).
* LA EXPERIENCIA: por cada unidad o heroe enemigo que cae, la reciben los heroes del otro equipo que esten a 'radio'
  casillas (y el que lo mato, este donde este).
"""
import logging
import random
import struct
import time

log = logging.getLogger('moba')


def _cfg():
    import moba
    return moba.config()


class Heroe:
    def __init__(self, ses, pa, clave):
        self.ses, self.pa, self.clave = ses, pa, clave
        self.datos = _cfg()['clases'][clave]
        self.nivel, self.exp = 1, 0
        self.cds = {}
        self.proximo_basico = 0.0
        self.escudo_hasta, self.escudo = 0.0, 0.0
        self.aturdido_hasta = 0.0
        self.dots = []                      # [(fin, dano por segundo, entidad que lo puso)]
        self.muerto_hasta = 0.0
        self.proxima_regen = 0.0
        self.bajas, self.muertes = 0, 0
        self.rangos = {int(p['id']): 0 for p in self.datos['poderes']}
        self.puntos = 1                     # "los poderes debo irlos desbloqueando, que me de la opcion" (23/11/2026)
        self.objetos = []                   # indices de moba_tienda.objetos()
        self.invisible_hasta = 0.0          # la Stealth Potion de la tienda
        self.oro = int((((_cfg().get('tienda') or {}).get('oro')) or {}).get('inicial', 0))
        self.hp, self.mp = self.hp_max, self.mp_max

    # -------------------------------------------------------------------- estadisticas
    def _stat(self, k):
        import moba_tienda
        d = self.datos
        return int(d['base'][k] + d['por_nivel'][k] * (self.nivel - 1) + moba_tienda.bonus(self, k))

    @property
    def hp_max(self):
        return int(self._stat('hp') * (1 + self.buff('vida')))

    @property
    def mp_max(self):
        return self._stat('mp')

    def buff(self, clave, ahora=None):
        """El buff del jefe de su equipo (moba.Partida.buffs, mientras dure) mas los de sus dragones (para toda la
        partida, moba._cae_dragon), 0 si no tiene."""
        dragones = sum(float(d.get(clave, 0)) for d in (getattr(self.pa, 'dragones', None) or {}).get(self.equipo, ()))
        b = getattr(self.pa, 'buffs', {}).get(self.equipo)
        if not b or (time.time() if ahora is None else ahora) >= b[0]:
            return dragones
        return float(b[1].get(clave, 0)) + dragones

    @property
    def atk(self):
        return int(self._stat('atk') * (1 + self.buff('ataque')))

    def defensa(self, magica=False, ahora=None):
        base = self._stat('mdef' if magica else 'def')
        if (time.time() if ahora is None else ahora) < self.escudo_hasta:
            base = int(base * (1 + self.escudo))
        return int(base * (1 + self.buff('defensa', ahora)))

    @property
    def entidad(self):
        return self.ses.personaje.entity_id

    @property
    def equipo(self):
        return int(self.pa.jugadores.get(self.ses, 0))

    @property
    def muerto(self):
        return self.muerto_hasta > 0

    def poderes(self):
        return {int(p['id']): p for p in self.datos['poderes']}

    def aprendidos(self):
        return [int(p['id']) for p in self.datos['poderes'] if self.rangos.get(int(p['id']), 0) > 0]


# ---------------------------------------------------------------------------------------------- puntos de poder
def _rp():
    return _cfg().get('rangos_poder') or {}


def rango_max(poder):
    return len(_rp().get('ult_niveles', [6, 11, 16])) if poder.get('ultimate') else int(_rp().get('basico_max', 5))


def nivel_para(poder, rango):
    """El nivel del heroe que pide ese rango (1..) del poder."""
    if poder.get('ultimate'):
        niveles = _rp().get('ult_niveles', [6, 11, 16])
        return int(niveles[min(rango, len(niveles)) - 1])
    return 2 * int(rango) - 1


def puede_subir(h, poder):
    """None si con un punto puede desbloquear / subir ese poder, o el motivo."""
    r = h.rangos.get(int(poder['id']), 0)
    if h.puntos <= 0:
        return 'No skill points.'
    if r >= rango_max(poder):
        return 'Max rank.'
    if h.nivel < nivel_para(poder, r + 1):
        return 'Needs level %d.' % nivel_para(poder, r + 1)
    return None


def mult_de(h, poder):
    """El mult del poder a su rango: +basico_extra (o ult_extra) por cada rango por encima del 1."""
    r = max(1, h.rangos.get(int(poder['id']), 1))
    extra = float(_rp().get('ult_extra' if poder.get('ultimate') else 'basico_extra', 0.15))
    return float(poder.get('mult', 1)) * (1 + extra * (r - 1))


def subir(h, i):
    """Gasta un punto en el poder i (0..3). (ok, mensaje)."""
    import clases
    import combate as cb
    ps = h.datos['poderes']
    if not 0 <= int(i) < len(ps):
        return False, 'Unknown skill.'
    poder = ps[int(i)]
    motivo = puede_subir(h, poder)
    if motivo:
        return False, motivo
    sk = int(poder['id'])
    h.rangos[sk] = h.rangos.get(sk, 0) + 1
    h.puntos -= 1
    pk = []
    if h.rangos[sk] == 1:                       # desbloqueado: a la barra (el cliente ya lo tiene desde entrar)
        pk += _paquete_poderes(h) + [_paquete_barra_heroe(h)]
        msg = '%s unlocked!' % poder['nombre']
    else:
        msg = '%s rank %d!' % (poder['nombre'], h.rangos[sk])
    pk.append(clases.aviso(msg, tipo=0))
    h.ses.enviar(*pk)
    if h.rangos[sk] == 1:
        # La barra otra vez, cuando el cliente ya tiene el hechizo: mandada junto a la concesion, la casilla quedaba
        # sin icono ("al aprender el primer poder no sale", 23/11/2026).
        import moba

        def _barra_otra_vez():
            try:
                if h.pa.heroes.get(h.ses) is h:
                    h.ses.enviar(_paquete_barra_heroe(h))
            except Exception:
                log.debug('moba: barra', exc_info=True)
        moba._despues(0.5, _barra_otra_vez)
    return True, msg


ICONO_PODER0 = 58600            # tools/ventana_moba.py: los iconos del juego de los poderes, por clase y poder


def icono_poder(clave, sk):
    """El id de icono (wnd03) del poder `sk` de la clase `clave`: ICONO_PODER0 + clase x 4 + poder, en el orden de
    moba.json (el mismo con el que tools/ventana_moba.py los copia del cliente)."""
    k = 0
    for c, d in (_cfg().get('clases') or {}).items():
        for p in d['poderes']:
            if c == clave and int(p['id']) == int(sk):
                return ICONO_PODER0 + k
            k += 1
    return 0


def ventana_puntos(h):
    """Los paquetes de la ventana para gastar los puntos (MBPuntos) o para cerrarla si no le quedan."""
    import canal_lua
    import moba_lobby
    if h.puntos <= 0:
        return [canal_lua.llamar('MBPuntosCerrar')]
    filas = []
    for poder in h.datos['poderes']:
        r = h.rangos.get(int(poder['id']), 0)
        motivo = puede_subir(h, poder)
        nombre = '%s%s  %s' % ('ULT ' if poder.get('ultimate') else '', poder['nombre'],
                               'Rank %d/%d' % (r, rango_max(poder)) if r else 'Locked')
        if r >= rango_max(poder):
            detalle = 'Max rank'
        elif motivo and motivo.startswith('Needs'):
            detalle = motivo
        else:
            detalle = 'Learn' if not r else 'Power x%.2f -> x%.2f' % (
                mult_de(h, poder), float(poder.get('mult', 1)) * (1 + float(_rp().get(
                    'ult_extra' if poder.get('ultimate') else 'basico_extra', 0.15)) * r))
        filas.append([nombre, detalle, motivo is None, 'Learn' if not r else 'Upgrade', icono_poder(h.clave, poder['id'])])
    titulo = 'Level %d - %d skill point%s to spend' % (h.nivel, h.puntos, '' if h.puntos == 1 else 's')
    return moba_lobby.preparar(h.ses) + [canal_lua.llamar('MBPuntos', titulo, filas)]


# ---------------------------------------------------------------------------------------------- paquetes
def _u64(v):
    v = max(0, min(int(v or 0), 0xFFFFFFFFFFFFFFFF))
    return v & 0xFFFFFFFF, v >> 32


def _paquete_nivel(eid, nivel, exp, sig, base=0):
    """Nivel y experiencia (las de 64 bits en dos mitades: la de un personaje de nivel alto no cabe en 32,
    "struct.error" al salir del MOBA, 23/11/2026). El 30 es la experiencia con la que EMPIEZA el nivel (como
    app.py al subir de nivel): la barra es (exp - base) / (sig - base). Con la actual ahi salia siempre al 0 %
    ("no sube la exp a medida que mata minions", 24/11/2026)."""
    return (struct.pack('<HIB', 0x001D, eid, 4) + struct.pack('<BII', 29, int(nivel), 0)
            + struct.pack('<BII', 30, *_u64(base)) + struct.pack('<BII', 31, *_u64(sig))
            + struct.pack('<BII', 32, *_u64(exp)))


def _recarga(h, sk, segundos, ahora=None):
    """La recarga del poder en la barra del cliente (0x001D kind 3, como app._avisar_enfriamiento). Sin ella el
    cliente lo daba por listo y lo volvia a pedir cada 0,25 s ("que se vea el cooldown", 23/11/2026)."""
    ms = int(max(0.0, segundos) * 1000)
    if ms <= 0:
        return
    ahora = time.time() if ahora is None else ahora
    avisos = h.__dict__.setdefault('_recargas', {})
    if ahora - avisos.get(sk, 0) < 0.5 and segundos < 1.0:
        return
    avisos[sk] = ahora
    yo = h.entidad
    import combate as cb
    # Con el GCD a 0 (combate.gcd_paquete, como app en cada habilidad): sin el, el cliente aplicaba su recarga global
    # a TODA la barra y un poder dejaba en espera a los otros ("que el cd de los poderes no stakee en otros", 23/11/2026).
    h.ses.enviar(struct.pack('<HIBBII', 0x001D, yo, 1, 3, int(sk), ms), cb.gcd_paquete())

    def _lista():
        try:
            (getattr(h.ses, 'enviar_inmediato', None) or h.ses.enviar)(struct.pack('<HIBBII', 0x001D, yo, 1, 3, int(sk), 0))
        except Exception:
            pass
    try:
        import asyncio
        asyncio.get_running_loop().call_later(ms / 1000.0, _lista)
    except RuntimeError:
        pass


def _rechazo(h, sk, motivo, ahora):
    """Un poder que no sale: el aviso (como mucho uno por segundo) y medio segundo de recarga para que el cliente no
    lo pida en bucle."""
    import clases
    ultimo = h.__dict__.setdefault('_avisos', {})
    if ahora - ultimo.get(motivo, 0) >= 1.0:
        ultimo[motivo] = ahora
        h.ses.enviar(clases.aviso(motivo, tipo=0))
    _recarga(h, sk, 0.5, ahora)


def _paquete_stats(h):
    """Las estadisticas del heroe, SIN la ropa ni las habilidades del personaje: con ellas el cliente ensenaba la vida
    maxima de verdad (760 / 7400 a nivel 1, "la vida maxima debe ir acorde", 23/11/2026). Ataque y defensas, las del
    heroe (con los objetos de la tienda y el buff del jefe)."""
    import inventario as inv
    b = bytearray(inv.stats(None, None, hp=h.hp, hp_max=h.hp_max, mp=h.mp, mp_max=h.mp_max, buffs=None))
    struct.pack_into('<IIII', b, 2, max(0, int(h.hp)), int(h.hp_max), max(0, int(h.mp)), int(h.mp_max))
    atk, df, mdf = h.atk, h.defensa(), h.defensa(magica=True)
    struct.pack_into('<IIIIIIIII', b, 2 + 20, atk, atk, atk, df, df, atk, atk, mdf, mdf)
    return bytes(b)


def _paquete_poderes(h):
    """Los 4 poderes de su clase, con su nivel de magia de verdad. Se conceden al entrar aunque esten bloqueados
    (accion no deja lanzarlos): concedidos al aprenderlos, y con nivel 1, la casilla de la barra salia sin icono
    ("todavia cuando aprendo 1 poder no sale el icono", 23/11/2026); en la fase 2a, concedidos al entrar, salian."""
    import skills
    return clases_paquetes(h.entidad, [(int(p['id']), skills.nivel_de_magia(int(p['id']))) for p in h.datos['poderes']])


def clases_paquetes(eid, pares):
    import clases
    return [struct.pack('<HIB', 0x001D, eid, len(pares))
            + b''.join(struct.pack('<BII', clases.KIND_HECHIZO, mid, mlv) for mid, mlv in pares)]


def _paquete_barra_heroe(h):
    """La barra del heroe: cada poder en su casilla (1..4), vacia hasta que lo aprende."""
    return _paquete_barra([int(p['id']) if h.rangos.get(int(p['id']), 0) > 0 else 0 for p in h.datos['poderes']])


def _paquete_barra(ids):
    from codec import Msg
    r = [{'usada': 1 if i else 0, 'magic_id': int(i), 'resto': bytes(4)} for i in ids][:24]
    r += [{'usada': 0, 'magic_id': 0, 'resto': bytes(4)}] * (24 - len(r))
    return Msg.registry[(0x005B, 's2c', 'privado')].build(ranuras=r)


def _base_exp(nivel):
    niveles = _cfg()['niveles']
    return niveles[min(nivel, len(niveles)) - 1]


def _sig_exp(nivel):
    niveles = _cfg()['niveles']
    return niveles[nivel] if nivel < len(niveles) else niveles[-1]


def paquetes_heroe(h):
    """Todo lo que el cliente tiene que ensenar del heroe: nivel, estadisticas, vida, mana."""
    import combate as cb
    return [_paquete_nivel(h.entidad, h.nivel, h.exp, _sig_exp(h.nivel), _base_exp(h.nivel)), _paquete_stats(h),
            cb.atributo(h.entidad, h.hp, cb.KIND_HP), cb.atributo(h.entidad, h.mp, cb.KIND_MP)]


def entrar(ses, pa, clave):
    """El jugador se vuelve heroe de esa clase: sus 4 poderes (concedidos y en la barra), nivel 1 y sus estadisticas."""
    import clases
    if clave not in _cfg()['clases']:
        clave = next(iter(_cfg()['clases']))
    h = Heroe(ses, pa, clave)
    pa.heroes[ses] = h
    pk = _paquete_poderes(h) + [_paquete_barra_heroe(h)] + paquetes_heroe(h)
    pk.append(clases.aviso('You are a %s (%s). You get a skill point every level: choose which skill to unlock.' % (
        h.datos['nombre'], h.datos.get('rol', '')), tipo=0))
    ses.enviar(*pk)
    __import__('moba_tienda').armar_al_entrar(ses, h.clave)   # el arma de su clase: sin ella no salen sus poderes
    try:
        ses.enviar(*ventana_puntos(h))
    except Exception:
        log.debug('moba: ventana de puntos', exc_info=True)
    log.info('MOBA %s: %s juega de %s', pa.id, ses.personaje.nombre, h.datos['nombre'])
    return h


def salir(ses, pa):
    """Deja de ser heroe: se le vuelven a ensenar su nivel, sus estadisticas, su vida y su barra de verdad."""
    import app
    import combate as cb
    import login
    h = pa.heroes.pop(ses, None)
    p = getattr(ses, 'personaje', None)
    if h is None or p is None:
        return
    romper_invisible(pa, h)
    pk = []
    if h.muerto or getattr(ses, 'muerto', False):
        ses.muerto = False
        pk.append(struct.pack('<HIII', 0x000A, p.entity_id, 0, 0))
    pk += [_paquete_nivel(p.entity_id, int(p.nivel), int(p.exp), min(0xFFFFFFFF, cb.exp_para_nivel(p.nivel + 1)),
                          cb.exp_para_nivel(p.nivel)),
           app._stats_ses(ses), cb.atributo(p.entity_id, p.hp, cb.KIND_HP), cb.atributo(p.entity_id, p.mp, cb.KIND_MP),
           login._barra(p, b'')]
    if getattr(ses, '_mb_lua', False):            # sus ventanas del evento, fuera
        import canal_lua
        pk += [canal_lua.llamar('MBPuntosCerrar'), canal_lua.llamar('MBHudCerrar'), canal_lua.llamar('MBTiendaCerrar')]
    try:
        ses.enviar(*pk)
    except Exception:
        log.debug('moba: salir del heroe', exc_info=True)
    __import__('moba_tienda').desvestir(ses)       # lo comprado deja de verse puesto


# ---------------------------------------------------------------------------------------------- dano y curas
def _factor(defensa):
    return 420.0 / (max(0, int(defensa)) + 420.0)


def _a_unidad(pa, h, u, dano):
    """Dano a una unidad del MOBA (sin su defensa: ya se aplico)."""
    import moba
    if not u.moba_equipo and h is not None:
        moba.provocar(pa, u, h)
    hecho = u.recibir_extra(max(1, int(dano)))
    if u.hp <= 0:
        moba.muere(pa, u, h.ses if h else None)
    return hecho


def recibir(pa, objetivo, dano, atacante_eid, matador=None, ahora=None, critico=False):
    """Dano a un heroe (ya con su defensa). Manda su vida a todos; si cae, muere."""
    import combate as cb
    import moba
    if objetivo.muerto:
        return 0
    dano = max(1, int(dano))
    objetivo.hp = max(0, objetivo.hp - dano)
    tipo = _tipo_num(critico)
    difundir(pa, lambda v: (cb.numero_flotante(eid_para(v, objetivo), dano, tipo), vida_para(v, objetivo)))
    objetivo.ses.ultimo_combate = time.time() if ahora is None else ahora
    if objetivo.hp <= 0:
        morir(pa, objetivo, atacante_eid, matador, ahora)
    return dano


def curar(pa, h, cantidad):
    import combate as cb
    import moba
    if h.muerto:
        return 0
    antes = h.hp
    h.hp = min(h.hp_max, h.hp + int(cantidad))
    hecho = h.hp - antes
    if hecho:
        difundir(pa, lambda v: (cb.numero_flotante(eid_para(v, h), hecho, cb.TIPO_CURA_HP), vida_para(v, h)))
    return hecho


def publica(ses):
    """El id con el que los DEMAS ven a ese jugador (presencia.entidad_de)."""
    try:
        import presencia
        return presencia.entidad_de(ses)
    except Exception:
        return ses.personaje.entity_id


def eid_para(visor, x):
    """El id de x (heroe o unidad) en el cliente de `visor`: el propio a uno mismo, el publico a los demas."""
    if hasattr(x, 'ses'):
        return x.entidad if visor is x.ses else publica(x.ses)
    return int(x.entity_id)


def vida_para(visor, h):
    """La vida del heroe: tal cual a el; a los demas en porcentaje (como presencia._vida_publica)."""
    import combate as cb
    if visor is h.ses:
        return cb.atributo(h.entidad, h.hp, cb.KIND_HP)
    pct = 0 if h.hp <= 0 else max(1, min(100, int(round(h.hp * 100.0 / max(1, h.hp_max)))))
    return cb.atributo(publica(h.ses), pct, cb.KIND_HP)


def difundir(pa, hacer):
    """Manda a cada uno de la partida lo que `hacer(visor)` le construye."""
    for visor in pa.sesiones():
        try:
            pk = [x for x in hacer(visor) if x]
            if pk:
                (getattr(visor, 'enviar_sin_espejo', None) or visor.enviar)(*pk)
        except Exception:
            log.debug('moba: difundir', exc_info=True)


def heroe_por_entidad(pa, eid):
    """El heroe de ese id: el publico (el que pulsan los demas) o el propio."""
    eid = int(eid or 0)
    return (next((h for h in pa.heroes.values() if getattr(h.ses, '_entidad_publica', None) == eid), None)
            or next((h for h in pa.heroes.values() if h.entidad == eid), None))


# ---------------------------------------------------------------------------------------------- acciones del jugador
def accion(ses, tipo, objetivo, tx=0, ty=0, ahora=None):
    """El c2s 0x0006 de un heroe: ataque basico o uno de sus poderes. True si lo lleva el MOBA (siempre, si es heroe)."""
    import clases
    import combate as cb
    import moba
    pa = moba.partida_de(ses)
    h = pa.heroes.get(ses) if pa else None
    if h is None:
        return False
    ahora = time.time() if ahora is None else ahora
    if h.muerto or ahora < h.aturdido_hasta or pa.resultado is not None:
        return True
    blanco = pa.unidades.get(int(objetivo or 0)) or heroe_por_entidad(pa, objetivo)
    if blanco is not None and getattr(blanco, 'moba_equipo', getattr(blanco, 'equipo', None)) == h.equipo:
        blanco = None                                           # a los suyos no
    if blanco is not None and hasattr(blanco, 'ses') and invisible(blanco, ahora):
        blanco = None                                           # al invisible no se le apunta
    if int(tipo) == cb.ATAQUE_NORMAL:
        if blanco is not None and ahora >= h.proximo_basico and _a_tiro(h, blanco, int(h.datos.get('alcance', 1)) + 1):
            import moba_tienda
            rapidez = min(float(moba_tienda.cfg().get('vel_ataque_max', 0.5)),
                          moba_tienda.extra(h, 'vel_ataque') + h.buff('vel_ataque', ahora))     # tienda y dragones
            h.proximo_basico = ahora + float(h.datos.get('cadencia', 1.0)) * (1 - rapidez)
            _basico(pa, h, blanco, ahora)
        return True
    poder = h.poderes().get(int(tipo))
    if poder is None:
        ses.enviar(clases.aviso('In the MOBA you can only use your %s skills.' % h.datos['nombre'], tipo=0))
        return True
    if h.rangos.get(int(tipo), 0) <= 0:
        _rechazo(h, int(tipo), 'Unlock %s first with a skill point.' % poder['nombre'], ahora)
        return True
    motivo = _no_puede(h, poder, blanco, ahora)
    if motivo:
        if ahora < h.cds.get(int(tipo), 0):
            _recarga(h, int(tipo), h.cds[int(tipo)] - ahora, ahora)     # en recarga: que el cliente la ensene
        else:
            _rechazo(h, int(tipo), motivo, ahora)
        return True
    lanzar(pa, h, poder, blanco, ahora)
    return True


def _pos(x):
    if hasattr(x, 'ses'):
        p = x.ses.personaje
        return int(p.tile_x), int(p.tile_y)
    return int(x.tile_x), int(x.tile_y)


def _a_tiro(h, blanco, alcance):
    a, b = _pos(h), _pos(blanco)
    return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= alcance


def _no_puede(h, poder, blanco, ahora):
    if h.rangos.get(int(poder['id']), 0) <= 0:
        if h.nivel < nivel_para(poder, 1):
            return '%s unlocks at level %d.' % (poder['nombre'], nivel_para(poder, 1))
        return 'Unlock %s first with a skill point.' % poder['nombre']
    if ahora < h.cds.get(int(poder['id']), 0):
        return '%s is not ready (%d s).' % (poder['nombre'], int(h.cds[int(poder['id'])] - ahora + 0.99))
    if h.mp < int(poder.get('mana', 0)):
        return 'Not enough mana for %s.' % poder['nombre']
    if poder['tipo'] == 'dano' and blanco is None:
        return 'Select an enemy for %s.' % poder['nombre']
    # 'area' sin enemigo elegido: alrededor del propio heroe (el cliente manda al que lanza como objetivo en las de
    # area propia, como Spliting Attack; se descartaba como aliado y no salia ni gastaba MP, 23/11/2026).
    if blanco is not None and poder['tipo'] in ('dano', 'area') and not _a_tiro(h, blanco, int(poder.get('alcance', 1)) + 1):
        return 'Too far for %s.' % poder['nombre']
    return None


def _dano_a(h, blanco, mult, magia, ahora):
    """(dano, critico). Lo de la tienda (moba_tienda.extra): 'crit' la probabilidad de critico (x crit_dano), 'pen' la
    parte de la defensa del blanco que se ignora ("objetos que den critical, armor ignore", 24/11/2026)."""
    import moba_tienda
    base = h.atk * float(mult) * random.uniform(0.92, 1.08)
    critico = random.random() < moba_tienda.extra(h, 'crit')
    if critico:
        base *= float(moba_tienda.cfg().get('crit_dano', 1.75))
    defensa = blanco.defensa(magia, ahora) if hasattr(blanco, 'ses') else (blanco.mdef if magia else blanco.defensa)
    return max(1, int(base * _factor(defensa * (1 - moba_tienda.extra(h, 'pen'))))), critico


def _robar(pa, h, hecho):
    """El robo de vida de la tienda ('robo': esa parte del dano hecho vuelve como vida)."""
    import moba_tienda
    r = moba_tienda.extra(h, 'robo')
    if r > 0 and hecho:
        curar(pa, h, int(hecho) * r)


def _tipo_num(critico):
    import combate as cb
    return cb.TIPO_DANO_CRITICO if critico else cb.TIPO_DANO


def _aplicar(pa, h, blanco, dano, ahora, critico=False):
    if hasattr(blanco, 'ses'):
        return recibir(pa, blanco, dano, h.entidad, h, ahora, critico)
    return _a_unidad(pa, h, blanco, dano)


def _basico(pa, h, blanco, ahora):
    import combate as cb
    import moba
    magia = not h.datos.get('fisico', True)
    romper_invisible(pa, h)
    dano, critico = _dano_a(h, blanco, 1.0, magia, ahora)
    beid = eid_para(None, blanco)
    difundir(pa, lambda v: (cb.ataque(eid_para(v, h), eid_para(v, blanco), 0),
                            cb.numero_de_dano(eid_para(v, h), eid_para(v, blanco), dano, ataque=0, efecto=0),
                            cb.cierre_de_dano(eid_para(v, h), eid_para(v, blanco), ataque=0, efecto=0)))
    hecho = _aplicar(pa, h, blanco, dano, ahora, critico)
    if not hasattr(blanco, 'ses'):
        moba._mandar(pa, cb.numero_flotante(beid, hecho or dano, _tipo_num(critico)),
                     cb.atributo(beid, blanco.porcentaje if blanco.hp > 0 else 0))
    _robar(pa, h, hecho or dano)


def lanzar(pa, h, poder, blanco, ahora):
    """Lanza el poder: el lanzamiento ahora y el efecto al acabar el tiempo de cast (como las mascotas)."""
    import combate as cb
    import moba
    sk = int(poder['id'])
    d = cb.datos_magia(sk)
    efecto = d.get('efecto') or 0
    magia = not h.datos.get('fisico', True)
    cast = max(100, int(d.get('cast_time') or 300))
    import moba_tienda
    cd = float(poder.get('cd', 8)) * (1 - moba_tienda.cdr(h))
    h.cds[sk] = ahora + cd
    romper_invisible(pa, h)
    h.mp = max(0, h.mp - int(poder.get('mana', 0)))
    _recarga(h, sk, cd, ahora)
    destino = h if blanco is None else blanco
    difundir(pa, lambda v: (cb.numero_de_dano(eid_para(v, h), eid_para(v, destino), 0, ataque=sk, efecto=efecto,
                                              cast_time=cast, es_magia=magia),))
    h.ses.enviar(cb.atributo(h.entidad, h.mp, cb.KIND_MP))

    def efecto_final():
        if h.muerto or pa.resultado is not None:
            return
        difundir(pa, lambda v: (cb.cierre_de_dano(eid_para(v, h), eid_para(v, destino), ataque=sk, efecto=efecto,
                                                  es_magia=magia),))
        _resolver(pa, h, poder, blanco, magia, time.time())
    moba._despues(cast / 1000.0, efecto_final)


def _enemigos_cerca(pa, h, centro, radio):
    out = []
    for u in list(pa.unidades.values()):
        if u.moba_equipo != h.equipo and u.hp > 0 and max(abs(int(u.tile_x) - centro[0]), abs(int(u.tile_y) - centro[1])) <= radio:
            out.append(u)
    for o in list(pa.heroes.values()):
        if o.equipo != h.equipo and not o.muerto:
            q = _pos(o)
            if max(abs(q[0] - centro[0]), abs(q[1] - centro[1])) <= radio:
                out.append(o)
    return out


def _aliados_cerca(pa, h, radio):
    c = _pos(h)
    return [o for o in pa.heroes.values() if o.equipo == h.equipo and not o.muerto
            and max(abs(_pos(o)[0] - c[0]), abs(_pos(o)[1] - c[1])) <= radio]


def _resolver(pa, h, poder, blanco, magia, ahora):
    tipo = poder['tipo']
    if tipo in ('dano', 'area'):
        if blanco is not None and (getattr(blanco, 'hp', 0) <= 0 or getattr(blanco, 'muerto', False)):
            return
        blancos = [blanco] if tipo == 'dano' else _enemigos_cerca(pa, h, _pos(blanco if blanco is not None else h),
                                                                  int(poder.get('radio', 2)))
        total = 0
        for b in blancos:
            dano, critico = _dano_a(h, b, mult_de(h, poder), magia, ahora)
            hecho = _aplicar(pa, h, b, dano, ahora, critico) or dano
            total += hecho
            if not hasattr(b, 'ses'):
                import combate as cb
                import moba
                moba._mandar(pa, cb.numero_flotante(b.entity_id, hecho, _tipo_num(critico)),
                             cb.atributo(b.entity_id, b.porcentaje if b.hp > 0 else 0))
            if poder.get('lento'):
                _lento(b, float(poder['lento']), ahora)
            if poder.get('aturde'):
                _aturdir(b, float(poder['aturde']), ahora)
            if poder.get('dot'):
                _dot(b, int(h.atk * float(poder['dot'])), float(poder.get('dura', 4)), h.entidad, ahora)
        if poder.get('drenaje') and total:
            curar(pa, h, total * float(poder['drenaje']))
        _robar(pa, h, total)
        if poder.get('cura_aliados'):
            for a in _aliados_cerca(pa, h, int(poder.get('radio', 4))):
                curar(pa, a, h.atk * float(poder['cura_aliados']))
    elif tipo == 'cura':
        for a in _aliados_cerca(pa, h, int(poder.get('radio', 0))) or [h]:
            curar(pa, a, h.atk * mult_de(h, poder))
    elif tipo == 'escudo':
        for a in _aliados_cerca(pa, h, int(poder.get('radio', 0))) or [h]:
            a.escudo = float(poder.get('defensa', 0.3))
            a.escudo_hasta = ahora + float(poder.get('dura', 5))


def _lento(b, s, ahora):
    if hasattr(b, 'ses'):
        return                                      # la velocidad del jugador la lleva su cliente
    b.lento_hasta = max(getattr(b, 'lento_hasta', 0), ahora + s)


def _aturdir(b, s, ahora):
    if hasattr(b, 'ses'):
        b.aturdido_hasta = max(b.aturdido_hasta, ahora + s)
    else:
        b.aturdido_hasta = max(getattr(b, 'aturdido_hasta', 0), ahora + s)


def _dot(b, dps, s, de, ahora):
    lista = b.dots if hasattr(b, 'ses') else b.__dict__.setdefault('moba_dots', [])
    lista.append((ahora + s, max(1, dps), de))


# ---------------------------------------------------------------------------------------------- las unidades pegan
def unidad_golpea(pa, m, h, ahora):
    """Un subdito o una torre pega a un heroe enemigo."""
    import combate as cb
    import moba
    m.moba_proximo = ahora + float(moba.datos_de(pa, m.moba_tipo).get('cadencia', 1.2))
    dano = max(1, int(m.atk * random.uniform(0.9, 1.1) * _factor(h.defensa(False, ahora))))
    if moba.rayo(pa, m, lambda v: eid_para(v, h)):          # las estatuas: el rayo (se ve llegar)
        return moba._despues(moba.RAYO_MS / 1000.0, lambda: recibir(pa, h, dano, m.entity_id, None, time.time())
                             if not h.muerto and pa.resultado is None else None)
    # El objetivo, el de cada uno (antes iba un 0 y el golpe no se veia ir a ningun sitio)
    difundir(pa, lambda v: (cb.ataque(m.entity_id, eid_para(v, h), cb.anim_de_monstruo(m.nombre)),))
    recibir(pa, h, dano, m.entity_id, None, ahora)


# ---------------------------------------------------------------------------------------------- invisible
# "Y que vuelvan invisible" (24/11/2026): la Stealth Potion de la tienda. Es el sigilo del juego (app._paquete_sigilo, el
# bit del Sneak en el 0x0185): el cliente lo dibuja casi transparente, sin nombre ni barra, y el cursor no lo elige; el
# que llega despues tambien lo ve asi (presencia, por ses.sigilo_hasta). Torres, subditos y jungla no lo atacan
# (moba._tick_unidad) ni se le apunta (accion). Se rompe al atacar o lanzar un poder, al morir y al salir.
def invisible(h, ahora=None):
    return (time.time() if ahora is None else ahora) < h.invisible_hasta


def volver_invisible(pa, h, segundos, ahora=None):
    import app
    ahora = time.time() if ahora is None else ahora
    h.invisible_hasta = ahora + float(segundos)
    h.ses.sigilo_hasta = h.invisible_hasta
    app._avisar_sigilo(h.ses, True)


def romper_invisible(pa, h):
    if not h.invisible_hasta:
        return
    import app
    h.invisible_hasta = 0.0
    h.ses.sigilo_hasta = 0
    try:
        app._avisar_sigilo(h.ses, False)
    except Exception:
        log.debug('moba: fin de invisible', exc_info=True)


# ---------------------------------------------------------------------------------------------- dobles, triples...
# "Sonidos de doble kill, triple kill, cuadruple kill y pentakill" (23/11/2026). El Lua del cliente no puede tocar un
# sonido suelto, pero los efectos de magia si. El sonido NO sale del numero de efecto: lo pide por nombre el script
# del efecto (script\magic.so, la llamada nativa 132 con la cadena); con 203/204/184/116 "no suena" porque sus
# scripts no piden ningun magicNNN. Estos cuatro piden un sonido que no existe en el cliente (Magic053_Burst ->
# "magic053", Magic055_Ball -> "magic055", Magic072_Ice -> "magic072", Magic301_Ices -> "magic301") y ninguna
# habilidad los usa (magic.xml); el parche trae esos wav con la voz (parches/extras/sound, voz del sistema).
# Bajas del mismo heroe con menos de RACHA_SEGUNDOS entre una y otra.
RACHA_SEGUNDOS = 10.0
RACHAS = {2: ('DOUBLE KILL', 53), 3: ('TRIPLE KILL', 55), 4: ('QUADRA KILL', 72), 5: ('PENTA KILL', 301)}


def racha(pa, h, ahora):
    """Suma la baja a la racha del heroe; con 2..5 seguidas, el anuncio y su sonido a toda la partida. La racha."""
    import combate as cb
    import moba
    n = h.__dict__.get('_racha', 0) + 1 if ahora - h.__dict__.get('_racha_t', -1e9) <= RACHA_SEGUNDOS else 1
    h._racha, h._racha_t = n, ahora
    nombre, efecto = RACHAS.get(min(n, 5), (None, 0)) if n >= 2 else (None, 0)
    if not nombre:
        return n
    moba._aviso_todos(pa, '%s: %s!' % (h.ses.personaje.nombre, nombre))
    difundir(pa, lambda v: (cb.numero_de_dano(eid_para(v, h), eid_para(v, h), 0, ataque=0, efecto=efecto,
                                              cast_time=100, es_magia=True),
                            cb.cierre_de_dano(eid_para(v, h), eid_para(v, h), ataque=0, efecto=efecto, es_magia=True)))
    log.info('MOBA %s: %s %s', pa.id, h.ses.personaje.nombre, nombre)
    return n


# ---------------------------------------------------------------------------------------------- muerte y experiencia
def morir(pa, h, atacante_eid, matador, ahora=None):
    import combate as cb
    import moba
    ahora = time.time() if ahora is None else ahora
    r = _cfg().get('respawn') or {}
    h.muerto_hasta = ahora + float(r.get('base', 6)) + float(r.get('por_nivel', 2)) * h.nivel
    h.dots.clear()
    romper_invisible(pa, h)
    h.ses.muerto = True
    def _muerte(v):
        a = eid_para(v, matador) if matador is not None else int(atacante_eid or 0)
        if v is h.ses:
            return (cb.ataque(h.entidad, a, 0, cb.TIPO_MUERTE), cb.atributo(h.entidad, 0, cb.KIND_HP))
        return (cb.muerte_monstruo(eid_para(v, h), a), cb.atributo(eid_para(v, h), 0, cb.KIND_HP))
    difundir(pa, _muerte)
    h.muertes += 1
    if matador is not None:
        matador.bajas += 1
        try:
            racha(pa, matador, ahora)
        except Exception:
            log.exception('MOBA: racha')
    nombre_m =matador.ses.personaje.nombre if matador is not None else 'the %s units' % pa.cfg['equipos'][str(3 - h.equipo)]['nombre']
    moba._aviso_todos(pa, '%s was slain by %s! Respawn in %d s.' % (h.ses.personaje.nombre, nombre_m,
                                                                      int(h.muerto_hasta - ahora)))
    try:
        __import__('moba_tienda').al_caer(pa, 'heroe', 3 - h.equipo, matador.ses if matador is not None else None, _pos(h))
    except Exception:
        log.exception('MOBA: oro de la baja')
    ex = _cfg().get('exp') or {}
    repartir_exp(pa, 3 - h.equipo, _pos(h), int(ex.get('heroe', 300)) + int(ex.get('por_nivel_heroe', 0)) * h.nivel,
                 matador)
    pa.bajas[h.equipo] = pa.bajas.get(h.equipo, 0)
    pa.bajas[3 - h.equipo] = pa.bajas.get(3 - h.equipo, 0) + 1


def repartir_exp(pa, equipo, centro, cantidad, matador=None):
    """La experiencia de una baja: a los heroes del `equipo` a 'radio' casillas, y al que la hizo."""
    radio = int((_cfg().get('exp') or {}).get('radio', 12))
    for h in list(pa.heroes.values()):
        if h.equipo != int(equipo) or h.muerto:
            continue
        q = _pos(h)
        if h is matador or max(abs(q[0] - centro[0]), abs(q[1] - centro[1])) <= radio:
            dar_exp(pa, h, cantidad)


def dar_exp(pa, h, cantidad):
    import clases
    import combate as cb
    tope = len(_cfg()['niveles'])
    h.exp += int(cantidad)
    subio = False
    while h.nivel < tope and h.exp >= _cfg()['niveles'][h.nivel]:
        hp_pct, mp_pct = h.hp / max(1, h.hp_max), h.mp / max(1, h.mp_max)
        h.nivel += 1
        h.hp, h.mp = max(1, int(h.hp_max * hp_pct)), int(h.mp_max * mp_pct)
        h.puntos += 1
        subio = True
        ult = next((p for p in h.datos['poderes'] if p.get('ultimate') and nivel_para(p, 1) == h.nivel), None)
        if ult:
            h.ses.enviar(clases.aviso('Level %d: you can unlock your ultimate %s!' % (h.nivel, ult['nombre']), tipo=0))
    pk = [_paquete_nivel(h.entidad, h.nivel, h.exp, _sig_exp(h.nivel), _base_exp(h.nivel))]
    if subio:
        pk = [cb.efecto_level_up(h.entidad, es_skill=False)] + paquetes_heroe(h)
        try:
            pk += ventana_puntos(h)
        except Exception:
            log.debug('moba: ventana de puntos', exc_info=True)
    h.ses.enviar(*pk)


# ---------------------------------------------------------------------------------------------- reloj
def tick(pa, ahora):
    """Reaparecer, regenerar y los danos que duran (heroes y unidades)."""
    import combate as cb
    import moba
    reg = _cfg().get('regeneracion') or {}
    for h in list(pa.heroes.values()):
        if h.invisible_hasta and ahora >= h.invisible_hasta:
            romper_invisible(pa, h)
        if h.muerto:
            if ahora >= h.muerto_hasta:
                reaparecer(pa, h)
            continue
        if ahora >= h.proxima_regen:
            h.proxima_regen = ahora + float(reg.get('cada', 2))
            base = pa.cfg['equipos'][str(h.equipo)]['nucleo']
            en_base = max(abs(_pos(h)[0] - base[0]), abs(_pos(h)[1] - base[1])) <= 8
            k = float(reg.get('en_base_pct', 0.08)) if en_base else 1.0
            hp = int(h.hp_max * (k if en_base else float(reg.get('hp_pct', 0.01))))
            mp = int(h.mp_max * (k if en_base else float(reg.get('mp_pct', 0.015))))
            if h.hp < h.hp_max or h.mp < h.mp_max:
                h.hp, h.mp = min(h.hp_max, h.hp + hp), min(h.mp_max, h.mp + mp)
                h.ses.enviar(cb.atributo(h.entidad, h.mp, cb.KIND_MP))
                difundir(pa, lambda v, h=h: (vida_para(v, h),))
        _tick_dots(pa, h, h.dots, ahora)
    for u in list(pa.unidades.values()):
        if getattr(u, 'moba_dots', None):
            _tick_dots(pa, u, u.moba_dots, ahora)


def _tick_dots(pa, b, dots, ahora):
    import combate as cb
    import moba
    vivos = []
    for fin, dps, de in dots:
        if ahora >= fin:
            continue
        ultimo = getattr(b, '_dot_ultimo', 0)
        if ahora - ultimo >= 1.0:
            if hasattr(b, 'ses'):
                recibir(pa, b, dps, de, heroe_por_entidad(pa, de), ahora)
            else:
                _a_unidad(pa, heroe_por_entidad(pa, de), b, dps)
                moba._mandar(pa, cb.numero_flotante(b.entity_id, dps), cb.atributo(b.entity_id, b.porcentaje if b.hp > 0 else 0))
        vivos.append((fin, dps, de))
    if vivos and ahora - getattr(b, '_dot_ultimo', 0) >= 1.0:
        b._dot_ultimo = ahora
    dots[:] = vivos


def reaparecer(pa, h):
    import combate as cb
    import desplazamientos
    import presencia
    h.muerto_hasta = 0.0
    h.hp, h.mp = h.hp_max, h.mp_max
    h.ses.muerto = False
    llegada = tuple(pa.cfg['equipos'][str(h.equipo)]['llegada'])
    try:
        desplazamientos.reubicar(h.ses, llegada, 'moba')
    except Exception:
        log.debug('moba: reubicar', exc_info=True)
    h.ses.enviar(struct.pack('<HIII', 0x000A, h.entidad, 0, 0), *paquetes_heroe(h))
    try:
        presencia.entrar(h.ses, h.ses.personaje.stage)
    except Exception:
        log.debug('moba: presencia al reaparecer', exc_info=True)
    difundir(pa, lambda v: () if v is h.ses else (vida_para(v, h),))
    import moba
    moba.refrescar_marcas(pa)
