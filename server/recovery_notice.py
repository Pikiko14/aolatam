"""Recovery Notice (4297) y High Effect Recovery Notice (20139).

Usan la misma ventana de nombre que Love Broadcasting: Angel.exe 0x6659E0
manda C2S 0x004D [u8 casilla][nombre 17]. Medido el 26/10/2026:
25 "Impacty" con el notice en la casilla 37.

El buff es el 常駐法術 del objeto (1897: +500 de HP maximo, 6758: +2000,
3 h) y lo recibe el personaje nombrado. Ese buff lleva en 轉嫁法術 una marca
oculta de 24 h (1928 / 6759): "Every character can only use one time in 24
hours" va por quien lo recibe.
"""
import logging
import time

log = logging.getLogger('recovery_notice')

MAGIA = {4297: 1897, 20139: 6758}
NOMBRE = {4297: 'Recovery Notice', 20139: 'High Effect Recovery Notice'}
MARCA = {1897: 1928, 6758: 6759}
ESPERA = 24 * 3600

# (char_id del objetivo, marca) -> hasta cuando no puede recibir otro.
# Solo en memoria: un reinicio del servidor la borra.
_ESPERA_HASTA = {}


def procesar(ses, body) -> bool:
    """True si el 0x004D era de un Recovery Notice (lo haya aplicado o no)."""
    if len(body) != 18:
        return False
    casilla = body[0]
    item = int(ses.inventario.get(casilla) or 0)
    if item not in MAGIA:
        return False
    import app
    import clases
    import combate
    import recent_mall

    def aviso(texto):
        ses.enviar(clases.aviso(texto, tipo=0))

    try:
        nombre = body[1:].split(b'\0', 1)[0].decode('ascii', 'strict').strip()
    except UnicodeDecodeError:
        nombre = ''
    if not nombre:
        aviso('Please enter the target name.')
        return True
    objetivo = next((s for s in app._tw_sesiones()
                     if getattr(s, 'personaje', None)
                     and str(s.personaje.nombre).casefold() == nombre.casefold()
                     and getattr(s, 'conectado', True)
                     and not getattr(s, 'desconectado', False)), None)
    if objetivo is None:
        aviso('%s is not online. Your item was not consumed.' % nombre)
        return True
    q = objetivo.personaje
    magia = MAGIA[item]
    ahora = time.time()
    clave = (int(q.char_id), MARCA[magia])
    if _ESPERA_HASTA.get(clave, 0) > ahora:
        horas = max(1, int((_ESPERA_HASTA[clave] - ahora) // 3600))
        aviso('%s already received this notice. Try again in %d h. Your item was not consumed.'
              % (q.nombre, horas))
        return True
    mag = combate.datos_magia(magia) or {}
    dur_ms = int(mag.get('dur_ms') or 10800000)
    try:
        recent_mall.cambiar(ses, {casilla: 1}, [])
    except recent_mall.Rechazo as exc:
        aviso(str(exc))
        return True
    _ESPERA_HASTA[clave] = ahora + ESPERA
    app._buff_a_otro(objetivo, magia, app._entrada_de_buff(mag, dur_ms / 1000.0), dur_ms, mag,
                     lanzador=ses if objetivo is not ses else None,
                     ef=int(mag.get('efecto') or 0))
    texto = 'used a %s on %s: Maximum HP +%d for %d h.' % (
        NOMBRE[item], q.nombre, int(mag.get('hp_bonus') or 0), dur_ms // 3600000)
    retrato = int((getattr(ses.personaje, 'apariencia', None) or [0])[0]) & 1
    bc = clases.chat_super_broadcast(0, ses.personaje.nombre, texto, retrato)
    for s in app._tw_sesiones():
        if getattr(s, 'personaje', None) and not getattr(s, 'desconectado', False):
            s.enviar(bc)
    log.info('[%s] %s: %s -> %s (magia %s)', getattr(ses, 'addr', '?'),
             ses.personaje.nombre, item, q.nombre, magia)
    return True
