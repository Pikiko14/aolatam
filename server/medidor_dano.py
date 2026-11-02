"""El contador de dano en vivo (02/11/2026): una ventana pequena y movible que se actualiza sola.

"Contador de dano de verdad: ventana pequena y movible con el top de dano del jefe o de la party". Usa el canal
servidor -> Lua (canal_lua.py, el 0x01A0 de tools/parche_canal_lua.py): la ventana es la 59010 de wnd03.xml
(tools/parche_subasta_ventana.py la anade) y su Lua es server/lua/medidor.lua.

QUE ENSENA:
* JEFE: si lo ultimo que golpeaste es un jefe (contador_dano.es_jefe), su ranking: el dano que le hizo cada uno
  (Monstruo.dano_por, que ya cuenta mascota e invocaciones para su dueno) y su %. Sigue ahi un rato tras matarlo.
* PARTY (o tu solo): el dano de los de tu grupo en la pelea en curso. La pelea se reinicia tras PAUSA_PELEA
  segundos sin dano; el titulo dice cuanto dura y el DPS del grupo.

COMO LLEGA: combate.Monstruo.registrar_dano llama a anotar() con cada golpe. Mientras la ventana esta abierta, un
bucle por sesion manda MedidorDatos(titulo, filas) cada segundo, solo si cambio. El cliente avisa al cerrarla.

c2s 0x002F [u8 168][u32 a][u32 b]: a = 1 abrir (el boton de la barra; si ya esta abierta la trae al frente), 0 se cerro
con la X, 8/9 la ventana se creo o no (b = su numero, para el log).
"""
import asyncio
import logging
import time
import weakref

import canal_lua

log = logging.getLogger('medidor_dano')

CMD_MEDIDOR = 168
PAUSA_PELEA = 20.0          # segundos sin dano: la pelea de party empieza de cero
JEFE_TRAS_MORIR = 30.0      # segundos que sigue el ranking del jefe tras matarlo
TOP = 8                     # filas de la lista (rows="8")
INTERVALO = 1.0

# Lo que define el cliente al saludar (subasta_ventana.procesar): el boton de la barra llama a esto.
SALUDO_LUA = ('function OnCommandMedidor(dwID, dwCmdID, dwParam, pParam) '
              'game.netcommand2(%d, 1, 0) return 1 end' % CMD_MEDIDOR)

_NOMBRES = {}               # char_id -> nombre (de quien haya golpeado algo)
_PELEAS = {}                # clave del grupo -> {'dano': {cid: n}, 'inicio': t, 'ultimo': t}
_OBJETIVO = {}              # char_id -> (weakref al monstruo, cuando)


def _cid(ses):
    p = getattr(ses, 'personaje', None)
    return int(getattr(p, 'char_id', 0) or 0) if p else 0


def _clave(ses):
    """El grupo: el lider si va en party, si no el propio jugador."""
    import equipos
    lider = equipos.lider_de(ses)
    return ('party', lider) if lider else ('solo', _cid(ses))


def anotar(ses, m, cantidad, ahora=None):
    """Un golpe de `ses` (o de su mascota) a `m`. Lo llama Monstruo.registrar_dano: tiene que ser barato."""
    cid = _cid(ses)
    if not cid or cantidad <= 0:
        return
    ahora = ahora or time.time()
    _NOMBRES[cid] = getattr(ses.personaje, 'nombre', '') or '?'
    clave = _clave(ses)
    pelea = _PELEAS.get(clave)
    if not pelea or ahora - pelea['ultimo'] > PAUSA_PELEA:
        pelea = _PELEAS[clave] = {'dano': {}, 'inicio': ahora, 'ultimo': ahora}
    pelea['dano'][cid] = pelea['dano'].get(cid, 0) + int(cantidad)
    pelea['ultimo'] = ahora
    try:
        _OBJETIVO[cid] = (weakref.ref(m), ahora)
    except TypeError:
        pass


def _miles(n) -> str:
    return '{:,}'.format(int(n))


def _filas(dano: dict):
    """[[nombre, dano, %], ...] de mas a menos, como mucho TOP."""
    total = sum(dano.values()) or 1
    orden = sorted(dano.items(), key=lambda kv: -kv[1])[:TOP]
    return [[_NOMBRES.get(cid, '?'), _miles(d), int(round(100.0 * d / total))] for cid, d in orden]


def vista(ses, ahora=None):
    """(titulo, filas) de lo que tiene que ver ahora ese jugador."""
    import contador_dano
    ahora = ahora or time.time()
    cid = _cid(ses)
    obj = _OBJETIVO.get(cid)
    m = obj[0]() if obj else None
    if m is not None and contador_dano.es_jefe(m):
        muerto_en = getattr(m, 'muerto_en', 0) or 0
        if getattr(m, 'hp', 0) > 0 or ahora - muerto_en < JEFE_TRAS_MORIR:
            dano = {int(k): int(v) for k, v in (getattr(m, 'dano_por', None) or {}).items() if int(v) > 0}
            if dano:
                estado = '' if getattr(m, 'hp', 0) > 0 else ' (defeated)'
                return '%s%s' % (getattr(m, 'nombre', '') or 'Boss', estado), _filas(dano)
    clave = _clave(ses)
    pelea = _PELEAS.get(clave)
    if not pelea or not pelea['dano']:
        return 'Hit something to start.', []
    dura = max(1.0, pelea['ultimo'] - pelea['inicio'])
    total = sum(pelea['dano'].values())
    quien = 'Party' if clave[0] == 'party' else 'You'
    return '%s  %ds  DPS %s' % (quien, int(dura), _miles(total / dura)), _filas(pelea['dano'])


def _lua():
    return (canal_lua.CARPETA / 'medidor.lua').read_text(encoding='utf-8')


def abierto(ses) -> bool:
    return bool(getattr(ses, 'medidor_abierto', False))


async def _bucle(ses):
    ultimo = None
    try:
        while abierto(ses) and getattr(ses, 'personaje', None) and not getattr(ses, 'desconectado', False):
            datos = vista(ses)
            if datos != ultimo:
                ultimo = datos
                ses.enviar(canal_lua.llamar('MedidorDatos', *datos))
                ses.volcar()
            await asyncio.sleep(INTERVALO)
    except Exception:
        log.exception('el bucle del contador de dano')
    finally:
        ses.medidor_tarea = None


def abrir(ses):
    ses.medidor_abierto = True
    ses.enviar(canal_lua.paquete(_lua()), canal_lua.llamar('MedidorAbrir'))
    if getattr(ses, 'medidor_tarea', None) is None:
        try:
            ses.medidor_tarea = asyncio.get_event_loop().create_task(_bucle(ses))
        except RuntimeError:
            ses.medidor_tarea = None            # sin bucle (tests): los datos se piden con vista()


def cerrar(ses, avisar_cliente=True):
    ses.medidor_abierto = False
    if avisar_cliente:
        ses.enviar(canal_lua.llamar('MedidorCerrar'))


def procesar(ses, cuerpo) -> bool:
    """El 0x002F del contador. True si era suyo."""
    import struct
    if len(cuerpo) < 9 or cuerpo[0] != CMD_MEDIDOR:
        return False
    a, b = struct.unpack_from('<II', cuerpo, 1)
    nombre = getattr(getattr(ses, 'personaje', None), 'nombre', '?')
    if a in (8, 9):                           # el cliente dice si pudo crear la ventana (MedidorAbrir)
        log.info('%s: ventana del contador %s (%d)', nombre, 'creada' if a == 8 else 'NO se pudo crear', b)
        return True
    log.info('%s: contador de dano %s', nombre, 'cerrado con la X' if a == 0 else 'abierto')
    if a == 0:
        cerrar(ses, avisar_cliente=False)     # lo cerro con la X
    else:
        abrir(ses)                            # el boton solo abre (o trae al frente); se cierra con su X
    return True
