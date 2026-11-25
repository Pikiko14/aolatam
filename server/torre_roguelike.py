"""La Torre de Babel roguelike (25/11/2026): "cada piso te ofrece elegir entre 3 mejoras temporales, por ejemplo +30%
de critico pero -20% de vida. Al morir pierdes las mejoras pero te quedas con los premios. Cada subida es distinta"
(plantillas/torre_roguelike.json).

* Al superar un piso (torre_babel.al_morir) a cada uno de la copia le sale la ventana "Tower Blessing" (58960, de
  tools/ventana_mecanicas.py) con 'por_piso' bendiciones sorteadas con su corrida, el piso y el personaje. Elige una con
  un clic (c2s 0x002F [u8 179][u32 1..3]); se puede elegir hasta que cae el jefe del piso siguiente.
* Cada bendicion es un buff ('torre_b_<id>') con sus efectos (crit, phys_dmg_pct, mag_dmg_pct, hp_pct, cast_redux) y
  su icono en la barra de buffs (magic.xml 23440.., cliente_local.MAGIAS_PROPIAS). Se acumulan.
* Al salir de la torre (muerte, portal, desconexion) o al acabar la corrida se pierden todas (limpiar); los premios
  de los pisos ya se dieron y se quedan.
"""
import json
import logging
import pathlib
import random
import struct
import time

import canal_lua

log = logging.getLogger('torre_roguelike')

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'torre_roguelike.json'
CMD_TR = 179
PREFIJO = 'torre_b_'
_CFG = {}


def config():
    if not _CFG:
        _CFG.update(json.loads(RUTA.read_text('utf-8')))
    return _CFG


def bendiciones():
    return {b['id']: b for b in config()['bendiciones']}


def magias_propias():
    """Las filas de magic.xml de los iconos de las bendiciones."""
    filas = {}
    for b in config()['bendiciones']:
        filas[int(b['magia'])] = {'編號': str(b['magia']), '介面圖號': str(b['icono']), '名稱': 'Tower: ' + b['nombre'],
                                  '對象': '自己', '高權位': str(b['magia']), '低權位': '1', '後置時間': '500',
                                  '持續時間': str(config()['duracion_s']), '公式': '2',
                                  '說明': '%s, but %s. Lost when you leave the Tower of Babel.' % (b['bueno'], b['malo']),
                                  '同類無法使用': '是'}
    return filas


def sorteo(semilla, piso, cid, n=None):
    """Los ids de las bendiciones que se le ofrecen: distintas en cada corrida, piso y personaje."""
    ids = sorted(bendiciones())
    rng = random.Random('%s-%d-%d' % (semilla, int(piso), int(cid)))
    return rng.sample(ids, min(len(ids), int(n or config()['por_piso'])))


def tiene(ses):
    p = getattr(ses, 'personaje', None)
    return sorted(k[len(PREFIJO):] for k in (getattr(p, 'buffs', None) or {}) if str(k).startswith(PREFIJO))


def _lua():
    return (canal_lua.CARPETA / 'roguelike.lua').read_text(encoding='utf-8')


def ofrecer(ses, piso, semilla):
    p = getattr(ses, 'personaje', None)
    if p is None:
        return []
    ids = sorteo(semilla, piso, p.char_id)
    ses._torre_oferta = {'piso': int(piso), 'ids': ids}
    b = bendiciones()
    opciones = [[b[i]['nombre'], b[i]['bueno'], b[i]['malo']] for i in ids]
    llevas = len(tiene(ses))
    try:
        ses.enviar(canal_lua.paquete(_lua()), canal_lua.llamar(
            'TBAbrir', 'Floor %d cleared! Choose a blessing for the climb.' % int(piso), opciones,
            'Blessings so far: %d. You lose them all if you fall or leave the tower.' % llevas))
    except Exception:
        log.debug('torre roguelike: ventana', exc_info=True)
    return ids


def _refrescar(ses):
    try:
        import app
        p = ses.personaje
        tope = app._vida_max(p)
        if p.hp > tope:
            p.hp = tope
        import combate
        ses.enviar(app._stats_ses(ses), combate.atributo(p.entity_id, p.hp, combate.KIND_HP))
    except Exception:
        log.debug('torre roguelike: refrescar stats', exc_info=True)


def elegir(ses, i, ahora=None):
    """Elige la i-esima (1..n) de la oferta. Devuelve el nombre o None."""
    of = getattr(ses, '_torre_oferta', None)
    p = getattr(ses, 'personaje', None)
    if not of or p is None or not 1 <= i <= len(of['ids']):
        return None
    ses._torre_oferta = None
    b = bendiciones()[of['ids'][i - 1]]
    ahora = ahora or time.time()
    clave = PREFIJO + b['id']
    previo = (p.buffs or {}).get(clave)
    efectos = dict(b['efectos'])
    if previo:                                   # repetida: se suma
        for k, v in efectos.items():
            efectos[k] = v + previo.get(k, 0)
    p.buffs[clave] = dict(efectos, fin=ahora + float(config()['duracion_s']), nombre='Tower: ' + b['nombre'],
                          magic_id=int(b['magia']))
    try:
        ses.enviar(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, int(b['magia']),
                               int(config()['duracion_s']) * 1000))
    except Exception:
        pass
    _refrescar(ses)
    log.info('torre roguelike: %s elige %s en el piso %d', p.nombre, b['nombre'], of['piso'])
    return b['nombre']


def limpiar(ses):
    """Fuera todas las bendiciones (al salir de la torre o acabar la corrida)."""
    p = getattr(ses, 'personaje', None)
    if p is None:
        return 0
    ses._torre_oferta = None
    claves = [k for k in (getattr(p, 'buffs', None) or {}) if str(k).startswith(PREFIJO)]
    b = bendiciones()
    for k in claves:
        info = b.get(k[len(PREFIJO):])
        p.buffs.pop(k, None)
        if info:
            try:
                ses.enviar(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, int(info['magia']), 0))
            except Exception:
                pass
    if claves:
        _refrescar(ses)
        try:
            ses.enviar(canal_lua.llamar('TBCerrar'))
        except Exception:
            pass
    return len(claves)


def procesar(ses, cuerpo) -> bool:
    if len(cuerpo) < 9 or cuerpo[0] != CMD_TR or getattr(ses, 'personaje', None) is None:
        return False
    a, _b = struct.unpack_from('<II', cuerpo, 1)
    nombre = elegir(ses, int(a))
    if nombre:
        import clases
        ses.enviar(clases.aviso('[Tower of Babel] Blessing: %s.' % nombre, tipo=0, msg_id=clases.MSG_TEXTO))
    return True
