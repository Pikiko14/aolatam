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
            {"tipo": "aviso_global", "texto": "..."},                      # cartel para todo el servidor
            {"tipo": "abrir", "barrera": "puerta1"}, {"tipo": "cerrar", "barrera": "puerta1"},
            {"tipo": "dano", "cantidad": 300, "pct": 0},                    # quita vida (fija o % de la maxima)
            {"tipo": "cuenta_atras", "segundos": 300, "regla": "fuera"},  # al acabar, ejecuta esa regla
            {"tipo": "activar", "regla": "otra"},                           # ejecuta otra regla ya
            {"tipo": "reiniciar"}                                           # cierra barreras y pone a cero el puzle
        ]}],
     "objetos": [{"id": "palanca1", "stage": 900, "tile": [50, 60], "sprite": 60306, "nombre": "Lever"}],
     "barreras": [{"id": "puerta1", "stage": 900, "zona": [40, 60, 42, 64], "sprite": 60402, "abierta": false}]}

PUZLES (07/11/2026): "cuando" tambien puede ser
    "pulsar":  {"objetos": ["palanca1", "palanca2"], "en_orden": true}   clic en objetos del mapa (en orden o no);
                                                                          con uno solo es un clic simple
    "pisar":   {"zona": [x1, y1, x2, y2], "repetir": true, "enfriamiento_s": 5}   entrar en esa zona (trampas)
Las barreras cerradas no dejan pasar: el que lo intenta vuelve a su casilla. Su estado y el de los puzles va por
mapa (o por copia de la instancia) y vuelve al de partida con "reiniciar" o al reiniciar el servidor.

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
TIPOS_PREMIO = ('dar', 'soltar', 'oro', 'ag', 'exp', 'portal', 'monstruo', 'llevar', 'aviso_global',
                'abrir', 'cerrar', 'dano', 'cuenta_atras', 'parar_cuenta', 'activar', 'reiniciar')
DISPARADORES = ('matar', 'entrar', 'horario', 'pulsar', 'pisar', 'manual')     # manual: solo con activar o cuenta atras
PRIMER_OBJETO = 112_800_000
RADIO_PULSAR = 3
# Objetos de mapa (0x000E) que ya usa el servidor y el cliente pinta sin problemas. Un sprite que no exista
# tumba al cliente (06/11/2026, con el 40442), asi que el editor solo deja elegir de aqui.
SPRITES_OBJETO = {60306: 'caja fuerte', 60402: 'cortina de luz', 60001: 'remolino', 60051: 'totem 1', 60052: 'totem 2',
                  60053: 'totem 3', 60054: 'totem 4', 60155: 'maquina (huevo)', 62358: 'buzon', 62329: 'carga en el suelo'}
# Premios que necesitan un sitio: en una regla de horario no hay monstruo ni jugador del que tomarlo.
CON_SITIO = ('portal', 'monstruo')

_cache = {'mtime': None, 'reglas': [], 'objetos': [], 'barreras': []}
_abiertas = {}         # (stage, sala) -> ids de barreras con el estado cambiado respecto al de partida
_secuencias = {}       # (id_regla, stage, sala) -> objetos ya pulsados en orden
_pisadas = {}          # (id_regla, char_id) -> time.time() de la ultima vez que la piso
_relojes = {}          # (id_regla_destino, stage, sala) -> asyncio.TimerHandle
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
            _cache['objetos'] = [o for o in datos.get('objetos', []) if validar_objeto(o) == []]
            _cache['barreras'] = [b for b in datos.get('barreras', []) if validar_barrera(b) == []]
            _cache['reglas'] = [r for r in datos.get('reglas', []) if validar(r) == []]
        except Exception:
            log.exception('eventos_propios.json no se pudo leer')
            _cache.update(reglas=[], objetos=[], barreras=[])
        _cache['mtime'] = mt
    return _cache['reglas']


def objetos():
    reglas()
    return _cache['objetos']


def barreras():
    reglas()
    return _cache['barreras']


def _zona_ok(z):
    return isinstance(z, (list, tuple)) and len(z) == 4 and all(isinstance(v, (int, float)) for v in z)


def _en_zona(z, x, y):
    x1, y1, x2, y2 = (int(v) for v in z)
    return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


def validar_objeto(o):
    mal = []
    if not str(o.get('id') or '').strip():
        mal.append('objeto sin id')
    if not int(o.get('stage') or 0):
        mal.append('objeto %s sin mapa' % o.get('id'))
    if len(o.get('tile') or []) != 2:
        mal.append('objeto %s sin casilla' % o.get('id'))
    if int(o.get('sprite') or 0) not in SPRITES_OBJETO:
        mal.append('objeto %s: dibujo no permitido' % o.get('id'))
    return mal


def validar_barrera(b):
    mal = []
    if not str(b.get('id') or '').strip():
        mal.append('barrera sin id')
    if not int(b.get('stage') or 0):
        mal.append('barrera %s sin mapa' % b.get('id'))
    if not _zona_ok(b.get('zona')):
        mal.append('barrera %s sin zona' % b.get('id'))
    if int(b.get('sprite') or 0) and int(b['sprite']) not in SPRITES_OBJETO:
        mal.append('barrera %s: dibujo no permitido' % b.get('id'))
    return mal


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
    if c == 'pulsar' and not (r.get('pulsar') or {}).get('objetos'):
        mal.append('"al pulsar" necesita al menos un objeto')
    if c == 'pisar':
        if not _zona_ok((r.get('pisar') or {}).get('zona')):
            mal.append('"al pisar" necesita una zona (x1, y1, x2, y2)')
        if not int(r.get('stage') or 0):
            mal.append('"al pisar" necesita un mapa')
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
        elif t in ('abrir', 'cerrar') and not str(p.get('barrera') or '').strip():
            mal.append('"%s" sin barrera' % t)
        elif t == 'dano' and int(p.get('cantidad') or 0) <= 0 and int(p.get('pct') or 0) <= 0:
            mal.append('"dano" sin cantidad ni %')
        elif t == 'cuenta_atras' and (int(p.get('segundos') or 0) < 5 or not str(p.get('regla') or '').strip()):
            mal.append('"cuenta atras" necesita 5 segundos o mas y la regla que salta al acabar')
        elif t in ('activar', 'parar_cuenta') and not str(p.get('regla') or '').strip():
            mal.append('"%s" sin regla' % t)
        if t in CON_SITIO:
            donde = p.get('donde', 'monstruo')
            if c == 'horario' and not isinstance(donde, (list, tuple)):
                mal.append('en una regla de horario "%s" necesita una casilla fija' % t)
            elif c in ('entrar', 'pulsar', 'pisar', 'manual') and donde == 'monstruo':
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
    out = {'exp': 0, 'monstruos': [], 'llevar': None, 'avisos': [], 'abrir': [], 'cerrar': [], 'dano': [],
           'relojes': [], 'parar': [], 'activar': [], 'reiniciar': False}
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
        elif t in ('abrir', 'cerrar'):
            out[t].append(str(pr['barrera']))
        elif t == 'dano':
            out['dano'].append(pr)
        elif t == 'cuenta_atras':
            out['relojes'].append(pr)
        elif t == 'activar':
            out['activar'].append(str(pr['regla']))
        elif t == 'parar_cuenta':
            out['parar'].append(str(pr['regla']))
        elif t == 'reiniciar':
            out['reiniciar'] = True
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
    return ([paquete_portal(e) for e, d in _portales.items() if d['stage'] == int(stage) and d.get('sala') is None]
            + paquetes_puzle(stage, None))


def de_sala(stage, sala):
    """Los portales abiertos de esa copia de la instancia."""
    _limpiar()
    if sala is None:
        return []
    return ([paquete_portal(e) for e, d in _portales.items() if d['stage'] == int(stage) and d.get('sala') == sala]
            + paquetes_puzle(stage, sala))


def portal(eid):
    _limpiar()
    return _portales.get(int(eid))


def pulsar(ses, eid):
    """Clic en un portal temporal (lleva a su destino) o en un objeto de puzle. True si era uno de los dos."""
    if pulsar_objeto(ses, eid):
        return True
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


# ------------------------------------------------------------------ puzles: objetos, barreras y zonas
def _eid_objeto(o):
    lista = objetos()
    return PRIMER_OBJETO + lista.index(o) if o in lista else None


def _eid_barrera(b, i):
    return PRIMER_OBJETO + 50_000 + barreras().index(b) * 100 + i


def objeto_por_eid(eid):
    eid = int(eid or 0)
    return next((o for o in objetos() if _eid_objeto(o) == eid), None)


def barrera_abierta(b, stage, sala):
    """Abierta o cerrada ahora: la de partida ("abierta") con lo que hayan cambiado las reglas."""
    cambiada = b['id'] in _abiertas.get((int(stage), sala), set())
    return bool(b.get('abierta')) != cambiada


def _poner_barrera(bid, stage, sala, abrir):
    b = next((x for x in barreras() if x['id'] == bid and int(x['stage']) == int(stage)), None)
    if b is None or barrera_abierta(b, stage, sala) == abrir:
        return None
    _abiertas.setdefault((int(stage), sala), set()).symmetric_difference_update({b['id']})
    return b


def casillas_dibujo(b):
    """Donde se pinta la barrera: toda la zona si es pequena, si no su linea central (como mucho 20 objetos)."""
    x1, y1, x2, y2 = (int(v) for v in b['zona'])
    x1, x2, y1, y2 = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
    todas = [(x, y) for y in range(y1, y2 + 1) for x in range(x1, x2 + 1)]
    if len(todas) <= 20:
        return todas
    if x2 - x1 >= y2 - y1:
        cy = (y1 + y2) // 2
        return [(x, cy) for x in range(x1, x2 + 1)][:20]
    cx = (x1 + x2) // 2
    return [(cx, y) for y in range(y1, y2 + 1)][:20]


def paquetes_barrera(b, cerrada):
    import combate
    import login
    if not int(b.get('sprite') or 0):
        return []
    if cerrada:
        return [login._map_object_spawn(_eid_barrera(b, i), int(b['sprite']), t) for i, t in enumerate(casillas_dibujo(b))]
    return [combate.despawn_monstruo(_eid_barrera(b, i)) for i in range(len(casillas_dibujo(b)))]


def paquetes_puzle(stage, sala):
    """Los objetos de puzle del mapa y el dibujo de sus barreras cerradas, para quien entra."""
    import login
    out = [login._map_object_spawn(_eid_objeto(o), int(o['sprite']), tuple(o['tile']))
           for o in objetos() if int(o['stage']) == int(stage)]
    for b in barreras():
        if int(b['stage']) == int(stage) and not barrera_abierta(b, stage, sala):
            out += paquetes_barrera(b, True)
    return out


def bloquear_paso(ses, desde, hasta):
    """True si el tramo cruza una barrera cerrada: el jugador vuelve a su casilla."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return False
    cerradas = [b for b in barreras() if int(b['stage']) == int(p.stage) and not barrera_abierta(b, p.stage, sala_de(ses))]
    if not cerradas:
        return False
    import app
    casillas = list(app._casillas_del_tramo(desde, hasta))
    for b in cerradas:
        if any(_en_zona(b['zona'], x, y) for x, y in casillas):
            ahora = time.time()
            if ahora - getattr(ses, '_aviso_barrera', 0.0) > 3:
                ses._aviso_barrera = ahora
                try:
                    import clases
                    ses.enviar(clases.aviso(str(b.get('aviso') or 'The way is closed.'), tipo=0))
                except Exception:
                    pass
            return True
    return False


def al_pisar(ses, casillas, ahora=None):
    """Reglas "al pisar una zona" que el tramo acaba de cruzar: [(regla, [premios])]."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return []
    ahora = ahora or time.time()
    out = []
    for r in reglas():
        if r.get('activa', True) is False or cuando(r) != 'pisar' or int(r.get('stage') or 0) != int(p.stage):
            continue
        z = (r.get('pisar') or {})
        if not any(_en_zona(z['zona'], x, y) for x, y in casillas):
            continue
        llave = (r['id'], p.char_id)
        if llave in _hechas:
            continue
        if ahora - _pisadas.get(llave, 0) < float(z.get('enfriamiento_s', 5) or 0):
            continue
        if not cumple_si(r, p, ahora):
            continue
        _pisadas[llave] = ahora
        if z.get('repetir', True) is False:
            _hechas.add(llave)
        out.append((r, list(r['premios'])))
    return out


def pulsar_objeto(ses, eid):
    """Clic en un objeto de puzle: comprueba la distancia y ejecuta las reglas que lo esperan. True si era uno."""
    o = objeto_por_eid(eid)
    p = getattr(ses, 'personaje', None)
    if o is None or not p or int(p.stage) != int(o['stage']):
        return False
    import clases
    if max(abs(p.tile_x - o['tile'][0]), abs(p.tile_y - o['tile'][1])) > RADIO_PULSAR:
        ses.enviar(clases.aviso('Move closer.', tipo=0))
        return True
    import app
    for r, premios in al_pulsar(ses, o['id']):
        app._ejecutar_regla_propia(ses, r, premios, getattr(ses, 'addr', '?'))
    return True


def al_pulsar(ses, oid, ahora=None):
    """Reglas que se cumplen al pulsar ese objeto: [(regla, [premios])]. Las de varios objetos llevan la cuenta por
    mapa (o copia de instancia); con "en_orden" un objeto equivocado la pone a cero."""
    p = ses.personaje
    sala = sala_de(ses)
    out = []
    for r in reglas():
        if r.get('activa', True) is False or cuando(r) != 'pulsar':
            continue
        if int(r.get('stage') or 0) and int(r['stage']) != int(p.stage):
            continue
        k = r.get('pulsar') or {}
        lista = [str(x) for x in k.get('objetos') or []]
        if oid not in lista:
            continue
        clave = (r['id'], int(p.stage), sala)
        if clave in _hechas:
            continue
        hechos = _secuencias.setdefault(clave, [])
        if k.get('en_orden'):
            if lista[len(hechos)] != oid:
                if hechos:
                    try:
                        import clases
                        ses.enviar(clases.aviso(str(k.get('aviso_error') or 'Wrong order... everything resets.'), tipo=0))
                    except Exception:
                        pass
                hechos.clear()
                if lista[0] != oid:
                    continue
            hechos.append(oid)
        elif oid not in hechos:
            hechos.append(oid)
        if len(lista) > 1 and len(set(hechos)) < len(lista):
            try:
                import clases
                ses.enviar(clases.aviso('%d / %d' % (len(set(hechos)), len(lista)), tipo=0))
            except Exception:
                pass
            continue
        hechos.clear()
        if not cumple_si(r, p, ahora):
            continue
        if k.get('repetir', True) is False:
            _hechas.add(clave)
        log.info('[eventos_propios] %s resuelve "%s"', p.nombre, r.get('nombre') or r['id'])
        out.append((r, list(r['premios'])))
    return out


def regla(rid):
    return next((r for r in reglas() if r['id'] == rid), None)


def reiniciar(stage, sala):
    """Barreras a su estado de partida, secuencias y cuentas del mapa a cero; devuelve los paquetes de las barreras."""
    cambiadas = _abiertas.pop((int(stage), sala), set())
    for k in [k for k in _secuencias if k[1] == int(stage) and k[2] == sala]:
        _secuencias.pop(k, None)
    for k in [k for k in _cuentas if k[1][:1] == ('mapa',) and k[1][1] == int(stage) and k[1][2] == sala]:
        _cuentas.pop(k, None)
    for k in [k for k in _relojes if k[1] == int(stage) and k[2] == sala]:
        try:
            _relojes.pop(k).cancel()
        except Exception:
            pass
    pk = []
    for b in barreras():
        if b['id'] in cambiadas and int(b['stage']) == int(stage):
            pk += paquetes_barrera(b, not b.get('abierta'))
    return pk
