"""Angel MOBA, fase 3 (23/11/2026): el marcador de la partida y la ventana del final (server/lua/moba.lua,
tools/ventana_moba.py).

* EL MARCADOR (58350, arriba en el centro): bajas de cada equipo, torres que les quedan y el tiempo; debajo, lo del
  jugador (nivel, bajas, muertes) y el buff del jefe si su equipo lo tiene. Se manda cada segundo SOLO si cambio.
* EL FINAL (58360): VICTORY o DEFEAT y los heroes de los dos equipos (clase, nivel, bajas/muertes), el suyo primero.
"""
import logging
import time

import canal_lua

log = logging.getLogger('moba')


def _torres(pa, eq):
    return sum(1 for u in pa.unidades.values() if u.moba_tipo == 'torre' and u.moba_equipo == eq)


def lineas_hud(pa, ses, ahora=None):
    ahora = time.time() if ahora is None else ahora
    e = pa.cfg['equipos']
    s = max(0, int(ahora - pa.inicio))
    arriba = '%s %d  -  %d %s     Towers %d - %d     %d:%02d' % (
        e['1']['nombre'], pa.bajas.get(1, 0), pa.bajas.get(2, 0), e['2']['nombre'], _torres(pa, 1), _torres(pa, 2),
        s // 60, s % 60)
    h = pa.heroes.get(ses)
    if h is None:
        return arriba, ''
    abajo = '%s  Lv %d   K %d  D %d   Gold %d' % (h.datos['nombre'], h.nivel, h.bajas, h.muertes, h.oro)
    b = pa.buffs.get(h.equipo)
    if b and ahora < b[0]:
        abajo += '   Boss buff %d s' % int(b[0] - ahora)
    elif pa.jefe_proximo is None:
        abajo += '   Boss is up!'
    if h.muerto:
        abajo += '   Respawn in %d s' % max(0, int(h.muerto_hasta - ahora + 0.99))
    return arriba, abajo


def refrescar(pa, ahora=None):
    import moba_lobby
    for ses in pa.sesiones():
        try:
            lineas = lineas_hud(pa, ses, ahora)
            if pa._hud.get(ses) == lineas:
                continue
            pa._hud[ses] = lineas
            ses.enviar(*(moba_lobby.preparar(ses) + [canal_lua.llamar('MBHud', *lineas)]))
        except Exception:
            log.debug('moba: marcador', exc_info=True)


def lineas_fin(pa, ses):
    """Los heroes por equipos, el suyo primero: 'Nombre  Archer Lv 9  3/1'."""
    mio = int(pa.jugadores.get(ses, 1) or 1)
    out = []
    for eq in (mio, 3 - mio):
        hs = sorted((h for h in pa.heroes.values() if h.equipo == eq), key=lambda h: (-h.bajas, h.muertes))
        out.append('%s  (%d kills)' % (pa.cfg['equipos'][str(eq)]['nombre'], pa.bajas.get(eq, 0)))
        filas = ['  %s   %s  Lv %d   %d / %d' % (h.ses.personaje.nombre[:14], h.datos['nombre'], h.nivel, h.bajas,
                                                h.muertes) for h in hs[:5]]
        out += filas + [''] * (5 - len(filas))        # el segundo equipo siempre en la linea 7 (la de color)
    return out[:12]


def fin(pa, ganador):
    """La ventana del final a cada uno (antes de que moba_heroe.salir les quite el heroe: la llama moba.terminar)."""
    import moba_lobby
    for ses in pa.sesiones():
        try:
            if not ganador:
                ses.enviar(canal_lua.llamar('MBHudCerrar'))
                continue
            gana = int(pa.jugadores.get(ses, 0)) == int(ganador)
            ses.enviar(*(moba_lobby.preparar(ses) + [canal_lua.llamar('MBFin', gana, lineas_fin(pa, ses))]))
        except Exception:
            log.debug('moba: fin', exc_info=True)
