"""Eventos propios del servidor: "al matar X monstruos, pasa algo".

No tocan el .mpc (no hace falta parche del cliente): viven en
server/plantillas/eventos_propios.json y los edita el editor de mapas (pestana
Eventos, "Reglas del servidor"). Se releen solos cuando cambia el archivo.

    {"reglas": [{
        "id": "dc_cazador", "nombre": "Cazador de Dark Cavern", "activa": true,
        "stage": 900,                       # 0 = cualquier mapa
        "matar": {"mobs": [8138, "dc50"],   # npc_type o id de monstruo propio; [] = cualquiera
                  "cantidad": 30,
                  "alcance": "jugador",     # "jugador": cada uno cuenta lo suyo; "mapa": cuentan todos juntos
                  "repetir": true},         # false = una sola vez (por jugador o por mapa)
        "aviso": "texto que sale al cumplirse",
        "premios": [
            {"tipo": "dar", "item": 89055, "cantidad": 1},
            {"tipo": "soltar", "items": [[8537, 1], [8770, 1]], "prob": 50},   # uno al azar, con prob %
            {"tipo": "oro", "cantidad": 1000},
            {"tipo": "ag", "cantidad": 50},
            {"tipo": "portal", "destino": 41, "llegada": [160, 36],
             "donde": "monstruo",            # o [x, y] en el mapa de la regla
             "segundos": 120}
        ]}]}

Los premios van al que hace la baja que completa la cuenta. El portal lo ven
todos los del mapa y se va solo pasado su tiempo. Las cuentas viven en memoria:
un reinicio del servidor las pone a cero.
"""
import json
import logging
import pathlib
import random
import time

log = logging.getLogger('eventos_propios')

ARCHIVO = pathlib.Path(__file__).parent / 'plantillas' / 'eventos_propios.json'
PRIMER_PORTAL = 112_600_000
SPRITE_PORTAL = 60001
RADIO_PORTAL = 3
TIPOS_PREMIO = ('dar', 'soltar', 'oro', 'ag', 'portal')

_cache = {'mtime': None, 'reglas': []}
_cuentas = {}          # (id_regla, clave) -> bajas
_hechas = set()        # (id_regla, clave) de las que no se repiten
_portales = {}         # entity -> {stage, tile, destino, llegada, hasta}
_sig_portal = [PRIMER_PORTAL]


def reglas():
    try:
        mt = ARCHIVO.stat().st_mtime
    except OSError:
        _cache.update(mtime=None, reglas=[])
        return []
    if mt != _cache['mtime']:
        try:
            datos = json.loads(ARCHIVO.read_text(encoding='utf-8'))
            _cache['reglas'] = [r for r in datos.get('reglas', []) if validar(r) == []]
        except Exception:
            log.exception('eventos_propios.json no se pudo leer')
            _cache['reglas'] = []
        _cache['mtime'] = mt
    return _cache['reglas']


def validar(r):
    """Lista de problemas de una regla ([] = valida). La usa tambien el editor."""
    mal = []
    if not str(r.get('id') or '').strip():
        mal.append('falta el id')
    m = r.get('matar') or {}
    if int(m.get('cantidad') or 0) < 1:
        mal.append('la cantidad a matar debe ser 1 o mas')
    if m.get('alcance', 'jugador') not in ('jugador', 'mapa'):
        mal.append('alcance debe ser "jugador" o "mapa"')
    if not r.get('premios'):
        mal.append('no tiene premios')
    for p in r.get('premios') or []:
        t = p.get('tipo')
        if t not in TIPOS_PREMIO:
            mal.append('premio desconocido: %r' % t)
        elif t == 'dar' and int(p.get('item') or 0) <= 0:
            mal.append('"dar" sin objeto')
        elif t == 'soltar' and not p.get('items'):
            mal.append('"soltar" sin objetos')
        elif t in ('oro', 'ag') and int(p.get('cantidad') or 0) <= 0:
            mal.append('"%s" sin cantidad' % t)
        elif t == 'portal' and (int(p.get('destino') or 0) <= 0 or len(p.get('llegada') or []) != 2
                                or not any(p['llegada'])):
            mal.append('"portal" sin mapa o casilla de llegada')
    return mal


def _cuenta_el_mob(regla, m):
    mobs = (regla.get('matar') or {}).get('mobs') or []
    if not mobs:
        return True
    propio = getattr(m, 'propio', None)
    npc = int(getattr(m, 'npc_type', 0) or 0)
    return any((isinstance(x, str) and not x.isdigit() and x == propio) or
               (str(x).isdigit() and int(x) == npc) for x in mobs)


def al_morir(ses, m):
    """Cuenta la baja en las reglas que la piden y devuelve lo que toca dar:
    [(regla, [premios])] de las reglas que se acaban de cumplir."""
    p = getattr(ses, 'personaje', None)
    if not p or getattr(m, 'es_estructura_hb', False):
        return []
    cumplidas = []
    for r in reglas():
        if r.get('activa', True) is False:
            continue
        if int(r.get('stage') or 0) and int(r['stage']) != int(p.stage):
            continue
        if not _cuenta_el_mob(r, m):
            continue
        k = r['matar']
        # "mapa" en una instancia es la copia del equipo: cada equipo lleva su propia cuenta.
        clave = ('mapa', int(p.stage), sala_de(ses)) if k.get('alcance') == 'mapa' else ('pj', p.char_id)
        llave = (r['id'], clave)
        if llave in _hechas:
            continue
        n = _cuentas.get(llave, 0) + 1
        total = int(k['cantidad'])
        if n < total:
            _cuentas[llave] = n
            continue
        _cuentas.pop(llave, None)
        if not k.get('repetir', True):
            _hechas.add(llave)
        log.info('[eventos_propios] %s cumple "%s" (%d bajas)', p.nombre, r.get('nombre') or r['id'], total)
        cumplidas.append((r, list(r['premios'])))
    return cumplidas


def progreso(ses, regla_id):
    """(llevadas, total) para el jugador en esa regla, o None."""
    r = next((x for x in reglas() if x['id'] == regla_id), None)
    p = getattr(ses, 'personaje', None)
    if not r or not p:
        return None
    clave = ('mapa', int(p.stage), sala_de(ses)) if r['matar'].get('alcance') == 'mapa' else ('pj', p.char_id)
    return _cuentas.get((r['id'], clave), 0), int(r['matar']['cantidad'])


def efectos_de(premios, rnd=random):
    """Los premios que se resuelven como efectos del interprete de eventos
    (app._aplicar_efectos) y los que hace este modulo: (efectos, ag, portales)."""
    efectos, ag, portales = [], 0, []
    for pr in premios:
        t = pr.get('tipo')
        if t == 'dar':
            efectos.append(('dar', [(int(pr['item']), max(1, int(pr.get('cantidad') or 1)))]))
        elif t == 'soltar':
            if rnd.random() * 100 < float(pr.get('prob', 100)):
                iid, cant = rnd.choice([tuple(x) for x in pr['items']])
                efectos.append(('dar', [(int(iid), max(1, int(cant)))]))
        elif t == 'oro':
            efectos.append(('oro', int(pr['cantidad'])))
        elif t == 'ag':
            ag += int(pr['cantidad'])
        elif t == 'portal':
            portales.append(pr)
    return efectos, ag, portales


# ------------------------------------------------------------------ portales temporales
def sala_de(ses):
    """En una instancia, la copia en la que esta (la del equipo o la suya si va solo); fuera de una, None.
    Los portales de una instancia solo los ven y los usan los de esa copia."""
    p = getattr(ses, 'personaje', None)
    try:
        import app
        if not p or not app.es_instancia(int(p.stage)):
            return None
        import eventos_mundo
        return eventos_mundo._clave_corrida(ses)
    except Exception:
        return None


def abrir_portal(stage, tile, destino, llegada, segundos, sala=None):
    _limpiar()
    _sig_portal[0] += 1
    eid = _sig_portal[0]
    _portales[eid] = dict(stage=int(stage), tile=(int(tile[0]), int(tile[1])), destino=int(destino),
                          llegada=(int(llegada[0]), int(llegada[1])),
                          hasta=time.time() + max(5, int(segundos or 60)), sala=sala)
    return eid


def destinatarios(stage, sala):
    """Las sesiones del mapa que ven ese portal: todas, o solo las de esa copia de la instancia."""
    import presencia
    return [s for s in presencia._vivas(int(stage)) if sala is None or sala_de(s) == sala]


def _limpiar(ahora=None):
    ahora = ahora or time.time()
    idos = [e for e, d in _portales.items() if d['hasta'] <= ahora]
    for e in idos:
        _portales.pop(e)
    return idos


def paquete_portal(eid):
    import login
    d = _portales[eid]
    return login._map_object_spawn(eid, SPRITE_PORTAL, d['tile'])


def poblar(stage):
    """Los portales abiertos del mapa, para quien entra despues (login.monstruos/npc del mapa). Los de una
    copia de instancia no van aqui (no se sabe quien entra): los manda de_sala al engancharse a su sala."""
    _limpiar()
    return [paquete_portal(e) for e, d in _portales.items() if d['stage'] == int(stage) and d.get('sala') is None]


def de_sala(stage, sala):
    """Los portales abiertos de esa copia de la instancia."""
    _limpiar()
    if sala is None:
        return []
    return [paquete_portal(e) for e, d in _portales.items() if d['stage'] == int(stage) and d.get('sala') == sala]


def portal(eid):
    _limpiar()
    return _portales.get(int(eid))


def pulsar(ses, eid):
    """Clic en un portal temporal: lleva a su destino si esta cerca. True si era uno."""
    d = portal(eid)
    p = getattr(ses, 'personaje', None)
    if not d or not p or int(p.stage) != d['stage']:
        return False
    if d.get('sala') is not None and sala_de(ses) != d['sala']:
        return False
    import app
    import clases
    if max(abs(p.tile_x - d['tile'][0]), abs(p.tile_y - d['tile'][1])) > RADIO_PORTAL:
        ses.enviar(clases.aviso('Move closer to the portal.', tipo=0))
        return True
    app._viajar_por_portal(ses, getattr(ses, 'addr', '?'), {'destino': d['destino'], 'llegada': d['llegada']},
                           motivo='por un portal de evento')
    return True
