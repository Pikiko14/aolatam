"""El jefe de mundo (25/11/2026): "jefe grande que aparece en un mapa aleatorio cada pocas horas, con aviso a todo el
servidor y botin repartido segun el dano".

* A LAS HORAS del calendario semanal (calendario.py, evento 'jefe'; sin el, plantillas/jefe_mundo.json "horas") sale
  uno de los jefes del juego de "jefes" (su monstruo de content.db, con la vida de "vida") en uno de los mapas de caza de
  "mapas", en una casilla donde sale algun monstruo del mapa (como Santa Clausula). Cartel a todo el servidor. Si nadie
  lo mata en "duracion_min", se va.
* AL MORIR: el ranking de dano (Monstruo.dano_por, por char_id; mascotas e invocaciones cuentan para su dueno) en un
  cartel a todos, y cada uno que le pego cobra segun su puesto ("premios": exp en partes de lo que pide su nivel e
  items del juego, con su probabilidad). El EXP y el botin normales del monstruo siguen como siempre.
* GM: /worldboss [spawn [stage] | despawn | status].
"""
import datetime as dt
import json
import logging
import pathlib
import random
import time

log = logging.getLogger('jefe_mundo')

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'jefe_mundo.json'
ESTADO = pathlib.Path(__file__).parent.parent / 'data' / 'jefe_mundo.json'
_EID = [96_600_000]
_ACTIVO = {}              # {'m': Monstruo, 'stage': int, 'fin': ts}


def config():
    return json.loads(RUTA.read_text('utf-8'))


def _cartel(texto):
    try:
        import competiciones
        competiciones.anunciar(texto)
    except Exception:
        log.debug('jefe de mundo: cartel', exc_info=True)


def _leer_estado():
    try:
        return json.loads(ESTADO.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _guardar_estado(d):
    try:
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(d), encoding='utf-8')
    except Exception:
        log.exception('guardar estado del jefe de mundo')


def nombre_mapa(stage):
    return dict((int(s), n) for s, n in config()['mapas']).get(int(stage), 'stage %d' % int(stage))


def horas_de_hoy(ahora):
    """['HH:MM'] en que sale hoy (calendario semanal o "horas" todos los dias)."""
    import calendario
    cal = calendario.slots('jefe')
    if cal is None:
        return list(config().get('horas') or [])
    return [h for wd, h in cal if wd == ahora.weekday()]


def toca(ahora):
    """El identificador de la salida que toca ahora (dentro de los 5 minutos de su hora), o None."""
    for h in horas_de_hoy(ahora):
        hh, mm = (int(x) for x in h.split(':'))
        ini = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if ini <= ahora < ini + dt.timedelta(minutes=5):
            return '%s %s' % (ini.date().isoformat(), h)
    return None


def activo():
    m = _ACTIVO.get('m')
    return m if m is not None and getattr(m, 'vivo', False) else None


def aparecer(stage=None, npc=None):
    """Lo saca (en ese mapa o uno al azar). Devuelve un texto para el log/GM."""
    import app
    import combate as cb
    import login as lg
    import santa_clausula as sc
    if activo() is not None:
        return '%s is already in %s' % (_ACTIVO['m'].nombre, nombre_mapa(_ACTIVO['stage']))
    cfg = config()
    mapas = [int(s) for s, _n in cfg['mapas']]
    santa = sc._ACTIVO.get('stage')
    stage = int(stage) if stage else random.choice([s for s in mapas if s != santa] or mapas)
    npc = int(npc) if npc else int(random.choice(cfg['jefes']))
    nombre, sprite = app._monstruo_bd(npc)
    sala = app._SALAS_DEL_MUNDO.setdefault(stage, app._SalaDelMundo(stage))
    if sala.monstruos is None:
        sala.monstruos = app._monstruos_de(stage)
    x, y = sc._tile_de_aparicion(stage, sala.monstruos)
    _EID[0] += 1
    m = cb.Monstruo(_EID[0], npc, nombre, [x, y], sprite, stage=stage)
    m.generado = True
    m.jefe_mundo = True
    m.spawn_x, m.spawn_y = x, y
    m.hp_max = m.hp = int(cfg.get('vida', 1500000))
    sala.monstruos[m.entity_id] = m
    pkt = lg._npc_spawn(m.entity_id, npc, nombre, (x, y), sprite=sprite, klass=1)
    for s in list(getattr(sala, 'sesiones', []) or []):
        try:
            s.enviar_inmediato(pkt)
        except Exception:
            pass
    minutos = int(cfg.get('duracion_min', 45))
    _ACTIVO.update({'m': m, 'stage': stage, 'fin': time.time() + minutos * 60})
    _cartel('[World Boss] %s has appeared in %s (%d, %d)! Defeat it within %d minutes: rewards by damage dealt.'
            % (nombre, nombre_mapa(stage), x, y, minutos))
    log.info('jefe de mundo %s (%d) en %s (%d) casilla (%d, %d)', nombre, npc, nombre_mapa(stage), stage, x, y)
    return '%s in %s (%d, %d)' % (nombre, nombre_mapa(stage), x, y)


def retirar(motivo='se fue'):
    import app
    import combate as cb
    m = _ACTIVO.get('m')
    if m is None:
        return 'no world boss'
    stage = _ACTIVO.get('stage')
    _ACTIVO.clear()
    sala = app._SALAS_DEL_MUNDO.get(stage)
    if getattr(m, 'vivo', False):
        m.vivo = False
        if sala is not None and sala.monstruos is not None:
            sala.monstruos.pop(m.entity_id, None)
        for s in (list(getattr(sala, 'sesiones', []) or []) if sala else []):
            try:
                s.enviar_inmediato(cb.despawn_monstruo(m.entity_id))
            except Exception:
                pass
        _cartel('[World Boss] %s left %s. Better luck next time!' % (m.nombre, nombre_mapa(stage)))
    log.info('jefe de mundo retirado: %s', motivo)
    return 'removed'


def premio_de(puesto, rng=None):
    """(fraccion de exp del nivel, [item_id]) del que queda en ese puesto del ranking de dano."""
    rng = rng or random
    for p in config()['premios']:
        if int(p['desde']) <= puesto <= int(p['hasta']):
            items = []
            for it in p.get('items') or []:
                if rng.random() < float(it.get('prob', 1)):
                    items.append(int(rng.choice(it['de'])))
            return float(p.get('exp', 0)), items
    return 0.0, []


def ranking(m):
    """[(char_id, dano)] de mayor a menor."""
    dano = {int(c): int(d) for c, d in (getattr(m, 'dano_por', None) or {}).items() if int(d) > 0}
    return sorted(dano.items(), key=lambda kv: -kv[1])


def al_morir(ses, m):
    """El ranking a todos y el premio de cada uno segun su puesto (antes de que se vacie dano_por)."""
    import app
    import combate
    if not getattr(m, 'jefe_mundo', False):
        return False
    filas = ranking(m)
    total = sum(d for _c, d in filas) or 1
    por_cid = {int(s.personaje.char_id): s for s in app._tw_sesiones() if getattr(s, 'personaje', None)}
    premiados = 0
    for puesto, (cid, _d) in enumerate(filas, 1):
        s = por_cid.get(cid)
        if s is None:
            continue
        frac, items = premio_de(puesto)
        p = s.personaje
        exp = int((combate.exp_para_nivel(p.nivel + 1) - combate.exp_para_nivel(p.nivel)) * frac)
        try:
            if exp > 0:
                app._dar_exp_y_creditos(s, exp=exp)
            for it in items:
                app._gm_dar_item(s, it, 1)
            __import__('misiones_diarias').sumar(s, 'jefe_mundo')
        except Exception:
            log.exception('premio del jefe de mundo')
        premiados += 1
    nombres = {cid: (por_cid[cid].personaje.nombre if cid in por_cid else '?') for cid, _d in filas}
    top = '  '.join('%d. %s %d%%' % (i, nombres[cid], round(100.0 * d / total)) for i, (cid, d) in
                    enumerate(filas[:5], 1))
    _ACTIVO.clear()
    _cartel('[World Boss] %s defeated! %s' % (m.nombre, top))
    log.info('jefe de mundo %s muerto: premio a %d jugadores', m.nombre, premiados)
    return True


def tick(ahora=None):
    """El reloj: lo saca a su hora (una vez por salida, aunque se reinicie el servidor) y lo retira al vencer."""
    import calendario
    ahora = ahora or calendario._ahora()
    if _ACTIVO.get('m') is not None and (not getattr(_ACTIVO['m'], 'vivo', False) or time.time() >= _ACTIVO['fin']):
        if getattr(_ACTIVO['m'], 'vivo', False):
            retirar('tiempo')
        else:
            _ACTIVO.clear()
    salida = toca(ahora)
    if salida is None or activo() is not None:
        return
    est = _leer_estado()
    if est.get('ultima') == salida:
        return
    est['ultima'] = salida
    _guardar_estado(est)
    aparecer()


async def vigilar(cada=20.0):
    import asyncio
    while True:
        await asyncio.sleep(cada)
        try:
            tick()
        except Exception:
            log.exception('jefe de mundo')


def comando(partes) -> str:
    """GM: worldboss [spawn [stage] [npc] | despawn | status]"""
    sub = partes[1].lower() if len(partes) > 1 else 'status'
    if sub in ('spawn', 'aparecer', 'ya'):
        return aparecer(partes[2] if len(partes) > 2 else None, partes[3] if len(partes) > 3 else None)
    if sub in ('despawn', 'retirar', 'quitar'):
        return retirar('GM')
    m = activo()
    if m is not None:
        return '%s in %s, HP %d/%d, leaves in %d min' % (m.nombre, nombre_mapa(_ACTIVO['stage']), m.hp, m.hp_max,
                                                          max(0, int((_ACTIVO['fin'] - time.time()) // 60)))
    import calendario
    return 'no world boss; today at %s' % (', '.join(horas_de_hoy(calendario._ahora())) or 'none')
