"""Cambio de faccion con el Census Angel del Angel Lyceum (stage 41).

El arbol de dialogo del mapa (raiz 5829) ya lo trae todo: si estas graduado
(ALIGNMENT 5 -> 5863), si sigues en una liga (HAVE_GUILD -> 5856), el precio
por nivel (PROPERTY 29), si tienes el oro (MONEY -> 5855) y el nodo final con
TAKE_MONEY, CREATE_ITEM(3541), SET_REBORN_POINT(61) y SET_ALIGNMENT(n). Lo que
faltaba era aplicarlo: _recorrer_dialogo_mapa lo cortaba con "Faction transfer
is not implemented yet" (03/11/2026, "habilita en liceum el cambio de faction").

Aqui va el SET_ALIGNMENT. Igual que al elegir faccion en el Graduation Palace,
la faccion se aplica al cerrarse el cuadro y al llegar a la ciudad nueva
(app._cerrar_viaje con faccion_al_llegar): es la ficha del cambio de mapa la
que le dice al cliente la faccion nueva. El punto de revivir pasa a esa ciudad.

Una vez cada 24 h (msg 5834 / 5861). El original lo marcaba con el objeto oculto
3541 "Faction Change Tag" (持續時間 1440 min), pero aqui los ocultos no caducan:
se guarda la hora del cambio en el personaje (cambio_faccion_ts).

El cambio de faccion de la LIGA (GUILD_CHANGE_ALIGN) sigue sin hacerse.
"""
import json
import logging
import time

log = logging.getLogger('cambio_faccion')

STAGE = 41
ESPERA = 24 * 3600
ITEM_MARCA = 3541           # Faction Change Tag: se sustituye por la hora guardada
MSG_ESPERA = 5861           # "...I will help you to change the faction after one day has passed."
MSG_SIN_ORO = 5855

# SET_ALIGNMENT(n): el n es el mismo codigo que login.CODIGO_FACCION.
NOMBRE = {1: 'Aurora', 2: 'Beasts', 3: 'Steel', 4: 'Shadow'}
# Clave de app.CIUDAD_DE_FACCION para cada una.
CIUDAD = {1: 'Aurora', 2: 'Breeze Woods', 3: 'Iron Castle', 4: 'Dark City'}

ACC_TAKE_MONEY, ACC_CREATE_ITEM, ACC_SET_REBORN_POINT, ACC_SET_ALIGNMENT = 20, 10, 17, 29
ACC_GUILD_CHANGE_ALIGN = 61


def _ultimo(ses):
    p = ses.personaje
    ts = getattr(p, 'cambio_faccion_ts', None)
    if ts is None:
        ts = 0
        try:
            import cuentas
            con = cuentas._get_conn()
            try:
                fila = con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',
                                   (ses.usuario, p.char_id)).fetchone()
            finally:
                con.close()
            if fila:
                ts = float(json.loads(fila[0]).get('cambio_faccion_ts') or 0)
        except Exception:
            log.debug('no se pudo leer cambio_faccion_ts', exc_info=True)
        p.cambio_faccion_ts = ts
    return float(ts or 0)


def en_espera(ses, ahora=None):
    ahora = time.time() if ahora is None else ahora
    return ahora - _ultimo(ses) < ESPERA


def es_nodo_de_cambio(acciones):
    return any(num == ACC_SET_ALIGNMENT for num, _ in acciones)


def precio(acciones):
    return sum(int(parms[0]) for num, parms in acciones if num == ACC_TAKE_MONEY and parms)


def rechazo(ses, acciones):
    """El mensaje que sale en vez del cambio, o None si se puede hacer."""
    if en_espera(ses):
        return MSG_ESPERA
    if int(getattr(ses.personaje, 'oro', 0) or 0) < precio(acciones):
        return MSG_SIN_ORO
    return None


def aplicar(ses, addr, acciones):
    """Deja el cambio hecho para cuando se cierre el cuadro. El oro lo quita el
    TAKE_MONEY del nodo, que sigue el camino normal de los efectos."""
    import app
    import cuentas
    p = ses.personaje
    n = next(int(parms[0]) for num, parms in acciones if num == ACC_SET_ALIGNMENT)
    nombre = NOMBRE.get(n)
    if not nombre:
        log.warning('[%s] SET_ALIGNMENT(%s) desconocido', addr, n)
        return False
    stage, tile = app.CIUDAD_DE_FACCION[CIUDAD[n]]
    ahora = time.time()
    p.cambio_faccion_ts = ahora
    usuario = getattr(ses, 'usuario', None)
    # Como la insignia de faccion: el punto de revivir en la ciudad de antes pasa a la nueva (seria una ciudad
    # enemiga); uno fijado con Cupid en otro sitio (el Lyceum, un campo) no se toca.
    if getattr(p, 'checkpoint_stage', 0) in app.CIUDADES_DE_FACCION and p.checkpoint_stage != stage:
        p.checkpoint_stage, p.checkpoint_x, p.checkpoint_y = stage, tile[0], tile[1]
        if usuario:
            cuentas.guardar_checkpoint(usuario, p.char_id, stage, tile[0], tile[1])
    if usuario:
        def _mut(d):
            d['cambio_faccion_ts'] = ahora
        cuentas._actualizar_personaje(usuario, p.char_id, _mut)
    ses.faccion_al_llegar = nombre
    ses.viaje_pendiente = (stage, tile, nombre)
    log.info('[%s] %s cambia de faccion %s -> %s (%d de oro); viaja al stage %s al cerrarse el dialogo',
             addr, p.nombre, getattr(p, 'faction', '?'), nombre, precio(acciones), stage)
    return True
