"""Lo comun de los eventos sociales (25/11/2026): config, avisos, premios y el PvP fuera de las arenas.

El PvP de El cazador cazado (cazador.py) y de los duelos de apuesta (duelos.py) va como el de Trade Routes: cada uno
dice a quien puede pegar cada jugador (puede_atacar) y aqui se juntan para pvp_liga (motivo_pvp, baja) y para las marcas
del cliente (marcas_para / refrescar): el modo arena (36), la marca hostil (42) y el aro de equipo (38). El cliente no
deja apuntar al de SU equipo, asi que cada visor se ve a si mismo en el equipo 1 y a su rival en el 2.
"""
import json
import logging
import pathlib
import random
import struct

log = logging.getLogger('sociales')

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'eventos_sociales.json'


def config():
    return json.loads(RUTA.read_text('utf-8'))


def aviso(ses, texto):
    import clases
    try:
        ses.enviar(clases.aviso(texto, tipo=0, msg_id=clases.MSG_TEXTO))
    except Exception:
        log.debug('sociales: aviso', exc_info=True)


def cartel(texto):
    try:
        import competiciones
        competiciones.anunciar(texto)
    except Exception:
        log.debug('sociales: cartel', exc_info=True)


def cartel_a(ses, texto):
    try:
        import totem_war
        ses.enviar(totem_war.cartel_deslizante(texto))
    except Exception:
        log.debug('sociales: cartel a uno', exc_info=True)


def sesiones():
    try:
        import app
        return [s for s in app._tw_sesiones() if getattr(s, 'personaje', None) and not getattr(s, 'cerrada', False)]
    except Exception:
        return []


def por_nombre(nombre):
    n = str(nombre or '').strip().lower()
    return next((s for s in sesiones() if s.personaje.nombre.lower() == n), None)


def por_cid(cid):
    return next((s for s in sesiones() if int(s.personaje.char_id) == int(cid)), None)


def nombre_mapa(stage):
    try:
        import clases
        return clases.nombre_de_mapa(int(stage)) or 'stage %s' % stage
    except Exception:
        return 'stage %s' % stage


def mapas_de_caza():
    import mundo_vivo
    return list(mundo_vivo.campos())


def es_de_caza(stage):
    import mundo_vivo
    return mundo_vivo.es_campo(stage)


def oro(ses):
    return int(getattr(ses, 'oro', 0) or 0)


def cambiar_oro(ses, delta):
    import trade_routes
    trade_routes._cambiar_oro(ses, delta)


def premiar(ses, premio, mult=1.0, rng=None):
    """exp (partes de lo que pide el nivel), oro_por_nivel x nivel, ag (Angel Gold del item mall, a la cuenta) e items
    (uno de 'de' con 'prob'). Devuelve texto."""
    import app
    import combate
    rng = rng or random
    p = ses.personaje
    exp = int((combate.exp_para_nivel(p.nivel + 1) - combate.exp_para_nivel(p.nivel)) * float(premio.get('exp', 0)) * mult)
    oro_ = int(int(premio.get('oro_por_nivel', 0)) * int(p.nivel) * mult)
    ag = int(int(premio.get('ag', 0)) * mult) if getattr(ses, 'usuario', None) else 0
    items = []
    for it in premio.get('items') or []:
        if rng.random() < float(it.get('prob', 1)):
            items.append(int(rng.choice(it['de'])))
    try:
        if exp > 0:
            app._dar_exp_y_creditos(ses, exp=exp)
        if oro_ > 0:
            cambiar_oro(ses, oro_)
        for it in items:
            app._gm_dar_item(ses, it, 1)
    except Exception:
        log.exception('sociales: premio')
    if ag > 0:
        try:
            __import__('item_mall').sumar_ag(ses.usuario, ag)
        except Exception:
            log.exception('sociales: Angel Gold del premio')
            ag = 0
    partes = []
    if exp:
        partes.append('%d EXP' % exp)
    if oro_:
        partes.append('%d Gold' % oro_)
    if ag:
        partes.append('%d Angel Gold' % ag)
    if items:
        partes.append('%d item%s' % (len(items), '' if len(items) == 1 else 's'))
    return ', '.join(partes)


# ---------------------------------------------------------------- PvP fuera de las arenas
def _reglas():
    return (__import__('cazador'), __import__('duelos'))


def puede_atacar(a, b):
    if a is b or not getattr(a, 'personaje', None) or not getattr(b, 'personaje', None):
        return False
    if a.personaje.stage != b.personaje.stage:
        return False
    try:
        return any(r.puede_atacar(a, b) for r in _reglas())
    except Exception:
        log.debug('sociales: puede_atacar', exc_info=True)
        return False


def motivo_pvp(ses, otro):
    """'' si un evento social deja pegar; None si no dice nada (siguen las otras reglas de pvp_liga)."""
    if getattr(ses, 'muerto', False) or getattr(otro, 'muerto', False):
        return None
    return '' if puede_atacar(ses, otro) else None


def baja(ses, otro):
    """Un jugador cae ante otro: si es de un evento social, lo resuelve el evento (sin creditos ni perder EXP)."""
    for r in _reglas():
        try:
            if r.baja(ses, otro):
                return True
        except Exception:
            log.exception('sociales: baja')
    return False


def _hostil(eid, activo):
    import competiciones
    return (competiciones.modo_arena(eid, activo), struct.pack('<HIBBII', 0x001D, eid, 1, 42, eid, int(bool(activo))))


def marcas_para(visor, sujeto):
    """Lo que `visor` tiene que saber de `sujeto` si puede pegarle: equipo 2 y hostil."""
    import holy_battlefield as hb
    import presencia
    if visor is None or visor is sujeto or not puede_atacar(visor, sujeto):
        return ()
    eid = presencia.entidad_de(sujeto)
    return (hb.equipo(eid, 2),) + _hostil(eid, True)


def refrescar(*sesiones_):
    """Las marcas otra vez en los mapas de esos jugadores (al empezar o acabar una caza o un duelo)."""
    import holy_battlefield as hb
    import presencia
    import trade_routes
    vistos = set()
    for s in sesiones_:
        st = getattr(getattr(s, 'personaje', None), 'stage', None)
        if st is None or st in vistos:
            continue
        vistos.add(st)
        if trade_routes._mapa_de_competicion(st):
            continue
        gente = trade_routes._en_mapa(st)
        for visor in gente:
            ataca = False
            for sujeto in gente:
                if sujeto is visor:
                    continue
                try:
                    eid = presencia.entidad_de(sujeto)
                    marcas = marcas_para(visor, sujeto) or tuple(trade_routes.marcas_para(visor, sujeto))
                    if not marcas:
                        marcas = (hb.equipo(eid, 0),) + _hostil(eid, False)
                    ataca = ataca or any(m[6:8] == bytes((1, 36)) and m[8] == 1 for m in marcas if len(m) > 8)
                    presencia._mandar(visor, *marcas)
                except Exception:
                    log.debug('sociales: marcas', exc_info=True)
            try:
                yo = visor.personaje.entity_id
                visor.enviar(*_hostil(yo, ataca), hb.equipo(yo, 1 if ataca else 0))
            except Exception:
                log.debug('sociales: modo arena propio', exc_info=True)


def revivir(ses, retraso=2.0):
    """Al que cae en un evento social: de pie con toda la vida al rato, donde estaba."""
    import asyncio

    def _ya():
        try:
            import app
            if getattr(ses, 'muerto', False):
                app._revivir_alli(ses, 100)
        except Exception:
            log.exception('sociales: revivir')
    try:
        asyncio.get_event_loop().call_later(retraso, _ya)
    except Exception:
        _ya()


async def vigilar(cada=5.0):
    """El reloj de los eventos sociales: tesoro, cazador cazado, duelos y votacion."""
    import asyncio
    while True:
        await asyncio.sleep(cada)
        for nombre in ('tesoro_servidor', 'cazador', 'duelos', 'votacion', 'contratos', 'torneo_mascotas',
                       'hardcore'):
            try:
                __import__(nombre).tick()
            except Exception:
                log.exception('sociales: reloj de %s', nombre)
        try:
            __import__('sociales_ui').refrescar_todos()      # los paneles abiertos (cuenta atras de los duelos)
        except Exception:
            log.exception('sociales: refrescar paneles')
