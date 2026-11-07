"""Eventos propios del servidor: "cuando pase X, si se cumple Y, haz Z".

No tocan el .mpc (no hace falta parche del cliente): viven en
server/plantillas/eventos_propios.json y los edita el editor de mapas (pestana
Eventos, "Reglas del servidor"). Se releen solos cuando cambia el archivo.

    {"reglas": [{
        "id": "dc_cazador", "nombre": "Cazador de Dark Cavern", "activa": true,
        "stage": 900,                       # 0 = cualquier mapa
        "cuando": "matar",                  # "matar" (por defecto), "entrar" o "horario"
        "matar": {"mobs": [8138, "dc50"],   # npc_type o id de monstruo propio; [] = cualquiera
                  "cantidad": 30,
                  "alcance": "jugador",     # "jugador": cada uno cuenta lo suyo; "mapa": cuentan todos juntos
                  "repetir": true},         # false = una sola vez (por jugador o por mapa)
        "entrar": {"repetir": false,        # "entrar": al llegar al mapa; false = la primera vez de cada jugador
                   "enfriamiento_min": 0},  #   si se repite, no antes de estos minutos
        "horario": {"horas": ["20:00"],     # "horario": a esas horas (hora del servidor)...
                    "cada_min": 0},         #   ...o cada N minutos
        "si": {"nivel_min": 0, "nivel_max": 0,          # condiciones (0 = sin limite)
               "desde": "18:00", "hasta": "23:59",      # solo en esa franja horaria
               "prob": 100},                            # % de que ocurra cuando se cumple
        "aviso": "texto que sale al cumplirse",
        "premios": [
            {"tipo": "dar", "item": 89055, "cantidad": 1},
            {"tipo": "soltar", "items": [[8537, 1], [8770, 1]], "prob": 50},   # uno al azar, con prob %
            {"tipo": "oro", "cantidad": 1000},
            {"tipo": "ag", "cantidad": 50},
            {"tipo": "exp", "cantidad": 5000},
            {"tipo": "portal", "destino": 41, "llegada": [160, 36],
             "donde": "monstruo",            # "monstruo", "jugador" o [x, y] en el mapa de la regla
             "segundos": 120},
            {"tipo": "monstruo", "npc_type": 209, "cantidad": 1,
             "donde": "monstruo",            # "monstruo", "jugador" o [x, y]
             "segundos": 0},                 # 0 = se queda hasta que lo maten
            {"tipo": "llevar", "destino": 3, "llegada": [100, 100]},       # mueve al jugador
            {"tipo": "aviso_global", "texto": "..."}                       # cartel para todo el servidor
        ]}]}

Los premios van al que hace la baja que completa la cuenta (o al que entra). En
las reglas de horario no hay un jugador: los premios personales van a todos los
que esten en el mapa de la regla. El portal y los monstruos los ven todos los
del mapa. Las cuentas viven en memoria: un reinicio del servidor las pone a cero.
"""
import json
import logging
import pathlib
import random
import re
import time

log = logging.getLogger('eventos_propios')

ARCHIVO = pathlib.Path(__file__).parent / 'plantillas' / 'eventos_propios.json'
PRIMER_PORTAL = 112_600_000
PRIMER_MONSTRUO = 112_700_000
SPRITE_PORTAL = 60001
RADIO_PORTAL = 3
TIPOS_PREMIO = ('dar', 'soltar', 'oro', 'ag', 'exp', 'portal', 'monstruo', 'llevar', 'aviso_global')
DISPARADORES = ('matar', 'entrar', 'horario')
# Premios que necesitan un sitio: en una regla de horario no hay monstruo ni jugador del que tomarlo.
CON_SITIO = ('portal', 'monstruo')

_cache = {'mtime': None, 'reglas': []}
_cuentas = {}          # (id_regla, clave) -> bajas
_hechas = set()        # (id_regla, clave) de las que no se repiten
_ultima = {}           # (id_regla, clave) -> time.time() de la ultima vez (enfriamiento y horario)
_portales = {}         # entity -> {stage, tile, destino, llegada, hasta}
_sig_portal = [PRIMER_PORTAL]
_sig_monstruo = [PRIMER_MONSTRUO]


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


def cuando(r):
    return r.get('cuando') or 'matar'


_HORA = re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')


def _minutos(hhmm):
    m = _HORA.match(str(hhmm or '').strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def validar(r):
    """Lista de problemas de una regla ([] = valida). La usa tambien el editor."""
    mal = []
    if not str(r.get('id') or '').strip():
        mal.append('falta el id')
    c = cuando(r)
    if c not in DISPARADORES:
        mal.append('disparador desconocido: %r' % c)
    if c == 'matar':
        m = r.get('matar') or {}
        if int(m.get('cantidad') or 0) < 1:
            mal.append('la cantidad a matar debe ser 1 o mas')
        if m.get('alcance', 'jugador') not in ('jugador', 'mapa'):
            mal.append('alcance debe ser "jugador" o "mapa"')
    if c == 'entrar' and not int(r.get('stage') or 0):
        mal.append('"al entrar al mapa" necesita un mapa')
    if c == 'horario':
        h = r.get('horario') or {}
        horas = h.get('horas') or []
        if any(_minutos(x) is None for x in horas):
            mal.append('las horas van como HH:MM (20:00)')
        if not horas and int(h.get('cada_min') or 0) < 1:
            mal.append('el horario necesita alguna hora o "cada N minutos"')
    si = r.get('si') or {}
    for k in ('desde', 'hasta'):
        if si.get(k) and _minutos(si[k]) is None:
            mal.append('"%s" va como HH:MM' % k)
    if int(si.get('nivel_min') or 0) and int(si.get('nivel_max') or 0) and int(si['nivel_min']) > int(si['nivel_max']):
        mal.append('el nivel minimo es mayor que el maximo')
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
        elif t in ('oro', 'ag', 'exp') and int(p.get('cantidad') or 0) <= 0:
            mal.append('"%s" sin cantidad' % t)
        elif t in ('portal', 'llevar') and (int(p.get('destino') or 0) <= 0 or len(p.get('llegada') or []) != 2
                                            or not any(p['llegada'])):
            mal.append('"%s" sin mapa o casilla de llegada' % t)
        elif t == 'monstruo' and int(p.get('npc_type') or 0) <= 0:
            mal.append('"monstruo" sin elegir cual')
        elif t == 'aviso_global' and not str(p.get('texto') or '').strip():
            mal.append('"aviso para todos" sin texto')
        if t in CON_SITIO:
            donde = p.get('donde', 'monstruo')
            if c == 'horario' and not isinstance(donde, (list, tuple)):
                mal.append('en una regla de horario "%s" necesita una casilla fija' % t)
            elif c == 'entrar' and donde == 'monstruo':
                mal.append('al entrar no hay monstruo: "%s" debe salir junto al jugador o en una casilla' % t)
            if c == 'horario' and not int(r.get('stage') or 0):
                mal.append('en una regla de horario "%s" necesita un mapa' % t)
    return mal


def cumple_si(r, p=None, ahora=None, rnd=random):
    """Las condiciones "si" de la regla: nivel del jugador, franja horaria y probabilidad."""
    si = r.get('si') or {}
    if p is not None:
        nv = int(getattr(p, 'nivel', 1) or 1)
        if int(si.get('nivel_min') or 0) and nv < int(si['nivel_min']):
            return False
        if int(si.get('nivel_max') or 0) and nv > int(si['nivel_max']):
            return False
    d, h = _minutos(si.get('desde')), _minutos(si.get('hasta'))
    if d is not None or h is not None:
        t = time.localtime(ahora or time.time())
        m = t.tm_hour * 60 + t.tm_min
        d = 0 if d is None else d
        h = 24 * 60 - 1 if h is None else h
        dentro = d <= m <= h if d <= h else (m >= d or m <= h)      # franja que cruza la medianoche
        if not dentro:
            return False
    prob = si.get('prob')
    if prob is not None and float(prob) < 100 and rnd.random() * 100 >= float(prob):
        return False
    return True


def al_entrar(ses, ahora=None):
    """Reglas "al entrar al mapa" que se cumplen para este jugador: [(regla, [premios])]."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return []
    ahora = ahora or time.time()
    out = []
    for r in reglas():
        if r.get('activa', True) is False or cuando(r) != 'entrar' or int(r.get('stage') or 0) != int(p.stage):
            continue
        e = r.get('entrar') or {}
        llave = (r['id'], ('pj', p.char_id))
        if llave in _hechas:
            continue
        enf = float(e.get('enfriamiento_min') or 0) * 60
        if enf and ahora - _ultima.get(llave, 0) < enf:
            continue
        if not cumple_si(r, p, ahora):
            continue
        _ultima[llave] = ahora
        if not e.get('repetir', False):
            _hechas.add(llave)
        log.info('[eventos_propios] %s entra y cumple "%s"', p.nombre, r.get('nombre') or r['id'])
        out.append((r, list(r['premios'])))
    return out


def horario_pendientes(ahora=None):
    """Reglas de horario a las que les toca ahora: [(regla, [premios])]. Se llama cada pocos segundos."""
    ahora = ahora or time.time()
    t = time.localtime(ahora)
    minuto = t.tm_hour * 60 + t.tm_min
    out = []
    for r in reglas():
        if r.get('activa', True) is False or cuando(r) != 'horario':
            continue
        h = r.get('horario') or {}
        llave = (r['id'], 'horario')
        ultima = _ultima.get(llave, 0)
        toca = False
        if any(_minutos(x) == minuto for x in h.get('horas') or []):
            toca = ahora - ultima >= 61                  # una vez por cada hora marcada
        cada = int(h.get('cada_min') or 0)
        if cada and ahora - ultima >= cada * 60:
            toca = toca or bool(ultima)                  # la primera vuelta solo arranca el reloj
            if not ultima:
                _ultima[llave] = ahora
        if not toca or not cumple_si(r, None, ahora):
            continue
        _ultima[llave] = ahora
        log.info('[eventos_propios] toca la regla de horario "%s"', r.get('nombre') or r['id'])
        out.append((r, list(r['premios'])))
    return out


def extras_de(premios):
    """Los premios nuevos que no son efectos del interprete: exp, monstruos, llevar y avisos para todos."""
    out = {'exp': 0, 'monstruos': [], 'llevar': None, 'avisos': []}
    for pr in premios:
        t = pr.get('tipo')
        if t == 'exp':
            out['exp'] += int(pr['cantidad'])
        elif t == 'monstruo':
            out['monstruos'].append(pr)
        elif t == 'llevar':
            out['llevar'] = pr
        elif t == 'aviso_global':
            out['avisos'].append(str(pr['texto']))
    return out


def sitio(donde, monstruo=None, jugador=None):
    """La casilla de un portal o monstruo: la del monstruo, la del jugador o una fija."""
    if isinstance(donde, (list, tuple)) and len(donde) == 2:
        return int(donde[0]), int(donde[1])
    if donde == 'jugador' and jugador is not None:
        return int(jugador.tile_x), int(jugador.tile_y)
    if monstruo is not None:
        return int(monstruo.tile_x), int(monstruo.tile_y)
    if jugador is not None:
        return int(jugador.tile_x), int(jugador.tile_y)
    return None


def aparecer_monstruos(stage, pr, tile):
    """Saca `cantidad` monstruos de ese tipo junto a la casilla, para todos los del mapa. Devuelve los creados."""
    import app
    import combate as cb
    import login as lg
    sala = app._SALAS_DEL_MUNDO.setdefault(int(stage), app._SalaDelMundo(int(stage)))
    if sala.monstruos is None:
        sala.monstruos = app._monstruos_de(int(stage))
    npc = int(pr['npc_type'])
    datos = cb._datos(npc) or {}
    nombre = datos.get('nombre') or 'Monster'
    sprite = int(datos.get('sprite') or 0) or lg.sprite_de(npc, 0)
    creados = []
    for k in range(max(1, min(50, int(pr.get('cantidad') or 1)))):
        x = int(tile[0]) + (k % 3) - 1 if k else int(tile[0])
        y = int(tile[1]) + (k // 3) % 3 - 1 if k else int(tile[1])
        _sig_monstruo[0] += 1
        m = cb.Monstruo(_sig_monstruo[0], npc, nombre, [x, y], sprite, stage=int(stage))
        m.generado = True                    # no reaparece solo
        m.spawn_x, m.spawn_y = x, y
        sala.monstruos[m.entity_id] = m
        creados.append(m)
        pkt = lg._npc_spawn(m.entity_id, npc, nombre, (x, y), sprite=sprite, klass=1)
        for s in list(getattr(sala, 'sesiones', []) or []):
            try:
                s.enviar_inmediato(pkt)
            except Exception:
                pass
    segundos = int(pr.get('segundos') or 0)
    if segundos > 0:
        try:
            import asyncio
            asyncio.get_event_loop().call_later(segundos, lambda: retirar_monstruos(stage, creados))
        except RuntimeError:
            pass
    log.info('[eventos_propios] aparecen %d x %s en stage %s %s', len(creados), nombre, stage, tile)
    return creados


def retirar_monstruos(stage, lista):
    import app
    import combate as cb
    sala = app._SALAS_DEL_MUNDO.get(int(stage))
    for m in lista:
        if not getattr(m, 'vivo', False):
            continue
        m.vivo = False
        if sala is not None and sala.monstruos is not None:
            sala.monstruos.pop(m.entity_id, None)
        for s in (list(getattr(sala, 'sesiones', []) or []) if sala else []):
            try:
                s.enviar_inmediato(cb.despawn_monstruo(m.entity_id))
            except Exception:
                pass


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
        if r.get('activa', True) is False or cuando(r) != 'matar':
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
        if not cumple_si(r, p):
            continue                     # la cuenta vuelve a empezar: esta vez no toca
        if not k.get('repetir', True):
            _hechas.add(llave)
        log.info('[eventos_propios] %s cumple "%s" (%d bajas)', p.nombre, r.get('nombre') or r['id'], total)
        cumplidas.append((r, list(r['premios'])))
    return cumplidas


def progreso(ses, regla_id):
    """(llevadas, total) para el jugador en esa regla, o None."""
    r = next((x for x in reglas() if x['id'] == regla_id), None)
    p = getattr(ses, 'personaje', None)
    if not r or not p or cuando(r) != 'matar':
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


def portal_abierto(stage, destino, sala=None):
    """El portal que ya esta abierto en ese mapa (o copia de instancia) hacia ese destino, o None."""
    _limpiar()
    return next((e for e, d in _portales.items()
                 if d['stage'] == int(stage) and d['destino'] == int(destino) and d.get('sala') == sala), None)


def alargar(eid, segundos):
    """Le da al portal `segundos` mas desde ahora. Asi no se apilan: el jefe de Dark Cavern reaparece cada minuto
    y medio y cada baja abria otro portal de cinco minutos, hasta cuatro remolinos a la vez (02/11/2026)."""
    d = _portales.get(int(eid))
    if d:
        d['hasta'] = max(d['hasta'], time.time() + max(5, int(segundos or 60)))


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
    # presencia guarda a los de una instancia bajo (stage, copia) -- ver presencia.clave_de_mapa --, no bajo el stage:
    # buscando en _vivas(900) la lista salia vacia y el portal no le llegaba a nadie, ni al que mato al jefe.
    import presencia
    clave = int(stage)
    if sala is not None:
        try:
            import eventos_mundo
            if eventos_mundo.grupo_de_instancia(int(stage)):
                clave = (int(stage), sala)
        except Exception:
            pass
    return [s for s in presencia._vivas(clave) if sala is None or sala_de(s) == sala]


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
