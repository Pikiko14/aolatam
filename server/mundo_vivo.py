"""El mundo vivo (25/11/2026): clima que cambia el juego y mapas que evolucionan (plantillas/mundo_vivo.json).

* CLIMA: cada hora, cada mapa de caza tiene un clima ("climas", sorteado por peso con la fecha, la hora y el mapa: el
  mismo para todos y aunque se reinicie el servidor). Cambia el dano de hechizos y fisico de los jugadores, la EXP y el
  oro de los monstruos y lo que pegan. El cliente pinta la lluvia y la nieve desde stage.xml, que no se puede cambiar en
  vivo: el clima se dice por el chat al entrar al mapa y cuando cambia, y con /weather.
* EVOLUCION: si se cazan muchos monstruos en un mapa ('agitado' en 'ventana_min'), salen 'elites' (monstruos del mapa
  con mas vida, ataque y EXP); si se siguen cazando ('jefe_local'), sale el monstruo mas fuerte del mapa como jefe local,
  con premio por puesto en el dano. Al morir (o irse a los 'jefe_min') el mapa se calma.
* ABANDONO: un mapa en el que nadie entra en 'abandono_h' horas se vuelve salvaje ('salvaje': mas EXP y oro, pero los
  monstruos pegan mas) hasta que alli se maten 'domar' monstruos.
"""
import datetime as dt
import json
import logging
import pathlib
import random
import time
from collections import deque

log = logging.getLogger('mundo_vivo')

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'mundo_vivo.json'
ESTADO = pathlib.Path(__file__).parent.parent / 'data' / 'mundo_vivo.json'
_EID = [96_700_000]
_CFG = {'mtime': None, 'd': None}
_CAMPOS = []
_CAMPOS_SET = set()
_MUERTES = {}          # stage -> deque[ts]
_FASE = {}             # stage -> {'fase': 'agitado'|'jefe', 'elites': [m], 'jefe': m, 'fin': ts}
_VISTO = {}            # stage -> ultimo ts con alguien dentro
_SALVAJE = {}          # stage -> muertes que faltan para domarlo
_CLIMA_DICHO = {}      # stage -> clima anunciado a los de dentro
_INICIO = [time.time()]


def config():
    try:
        mt = RUTA.stat().st_mtime
    except OSError:
        mt = None
    if _CFG['d'] is None or mt != _CFG['mtime']:
        _CFG['d'] = json.loads(RUTA.read_text('utf-8'))
        _CFG['mtime'] = mt
    return _CFG['d']


def campos():
    """Los mapas de caza abiertos: con plantilla de monstruos, sin ser instancia ni de evento, y no cerrados
    (configuracion.MAPAS_APAGADOS: "el treasure hunt debe ser solo en los mapas habilitados", 26/11/2026; el cofre
    salio en Machinery Ruins, que esta cerrado)."""
    if not _CAMPOS:
        try:
            import app
            import configuracion
            fuera = set(__import__('daily_events').STAGES) | set(__import__('league_war').STAGES) | {501}
            plantillas = pathlib.Path(__file__).parent / 'plantillas'
            minimo = int(config().get('minimo_monstruos', 20))
            for s, nombre in sorted((k, v) for k, v in app.mapas_poblados().items() if isinstance(k, int)):
                if s in fuera or app.es_instancia(s) or configuracion.mapa_apagado(s):
                    continue
                try:
                    d = json.loads((plantillas / nombre).read_text(encoding='utf-8'))
                except Exception:
                    continue
                if sum(1 for e in d.get('spawns', []) if e.get('monstruo') and not e.get('apagado')) >= minimo:
                    _CAMPOS.append(s)
        except Exception:
            log.exception('mundo vivo: mapas de caza')
    return _CAMPOS


def es_campo(stage):
    try:
        if not _CAMPOS_SET:
            _CAMPOS_SET.update(campos())
        return int(stage) in _CAMPOS_SET
    except (TypeError, ValueError):
        return False


def nombre_mapa(stage):
    try:
        import clases
        return clases.nombre_de_mapa(int(stage)) or 'stage %s' % stage
    except Exception:
        return 'stage %s' % stage


# ---------------------------------------------------------------- clima
_TECHO = {}


def bajo_techo(stage):
    """Cuevas, laberintos, palacios...: sin clima (por las palabras de 'bajo_techo' en el nombre del mapa)."""
    st = int(stage)
    if st not in _TECHO:
        palabras = set(nombre_mapa(st).lower().replace('-', ' ').split())
        _TECHO[st] = bool(palabras & set(config().get('bajo_techo', [])))
    return _TECHO[st]


def clima(stage, ahora=None):
    """El clima de ese mapa a esa hora (dict de 'climas'), o None si no es de caza."""
    if not es_campo(stage) or bajo_techo(stage):
        return None
    ahora = ahora or dt.datetime.now()
    lista = config()['climas']
    clave = '%s-%02d-%d' % (ahora.date().isoformat(), ahora.hour, int(stage))
    c = _CLIMA_CACHE.get(clave)
    if c is None or c[0] is not lista:
        if len(_CLIMA_CACHE) > 5000:
            _CLIMA_CACHE.clear()
        rng = random.Random(clave)
        c = _CLIMA_CACHE[clave] = (lista, rng.choices(lista, weights=[float(x.get('peso', 1)) for x in lista])[0])
    return c[1]


_CLIMA_CACHE = {}


def _texto_efectos(ef):
    nombres = {'mag': 'spell damage', 'fis': 'physical damage', 'exp': 'EXP', 'oro': 'gold', 'atk': 'monster damage'}
    return ', '.join('%s %+d%%' % (nombres[k], v) for k, v in ef.items() if v and k in nombres)


def texto_clima(stage, ahora=None):
    c = clima(stage, ahora)
    if c is None:
        return None
    ahora = ahora or dt.datetime.now()
    ef = _texto_efectos(c.get('efectos') or {})
    return '%s in %s until %02d:00%s' % (c['nombre'], nombre_mapa(stage), (ahora.hour + 1) % 24,
                                       (': ' + ef) if ef else '.')


def _efectos(stage, ahora=None):
    """Los % que suman el clima y el estado salvaje del mapa."""
    tot = {}
    c = clima(stage, ahora)
    if c:
        for k, v in (c.get('efectos') or {}).items():
            tot[k] = tot.get(k, 0) + v
    if salvaje(stage):
        for k, v in config()['salvaje'].items():
            tot[k] = tot.get(k, 0) + v
    return tot


def mult(stage, clave, ahora=None):
    """El multiplicador (1.0 = nada) de 'mag', 'fis', 'exp', 'oro' o 'atk' en ese mapa ahora."""
    try:
        return max(0.1, 1.0 + _efectos(stage, ahora).get(clave, 0) / 100.0)
    except Exception:
        return 1.0


def mult_dano(stage, es_magico):
    return mult(stage, 'mag' if es_magico else 'fis')


# ---------------------------------------------------------------- abandono
def salvaje(stage):
    return _SALVAJE.get(int(stage), 0) > 0 if stage is not None else False


def _marcar_presencia(ahora_ts):
    import presencia
    cfg = config()
    for st in campos():
        if presencia._vivas(st):
            _VISTO[st] = ahora_ts
        elif (st not in _SALVAJE and ahora_ts - _VISTO.get(st, _INICIO[0]) >= float(cfg['abandono_h']) * 3600):
            _SALVAJE[st] = int(cfg['domar'])
            log.info('mundo vivo: %s (%d) se vuelve salvaje', nombre_mapa(st), st)


def _leer_estado():
    try:
        d = json.loads(ESTADO.read_text(encoding='utf-8'))
        _VISTO.update({int(k): float(v) for k, v in d.get('visto', {}).items()})
        _SALVAJE.update({int(k): int(v) for k, v in d.get('salvaje', {}).items()})
    except Exception:
        pass


def _guardar_estado():
    try:
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps({'visto': _VISTO, 'salvaje': _SALVAJE}), encoding='utf-8')
    except Exception:
        log.exception('mundo vivo: guardar estado')


# ---------------------------------------------------------------- avisos
def _aviso(ses, texto):
    import clases
    try:
        ses.enviar(clases.aviso(texto, tipo=0, msg_id=clases.MSG_TEXTO))
    except Exception:
        log.debug('mundo vivo: aviso', exc_info=True)


def _a_los_del_mapa(stage, texto):
    import presencia
    for s in presencia._vivas(stage):
        _aviso(s, texto)


def lineas(stage, ahora=None):
    """Lo que se dice al entrar y con /weather."""
    if not es_campo(stage):
        return ['[Weather] Towns have no weather. Field maps change every hour.']
    out = ['[Weather] ' + (texto_clima(stage, ahora) or 'No weather down here, but the land still remembers.')]
    if salvaje(stage):
        out.append('[Wild] Nobody has hunted here for a long time: %s. Defeat %d more monsters to tame it.'
                   % (_texto_efectos(config()['salvaje']), _SALVAJE[int(stage)]))
    f = _FASE.get(int(stage))
    if f and f.get('fase') == 'jefe' and getattr(f.get('jefe'), 'vivo', False):
        j = f['jefe']
        out.append('[Local Boss] %s is loose here (%d, %d)!' % (j.nombre, j.tile_x, j.tile_y))
    elif f and f.get('fase') == 'agitado':
        out.append('[Restless] So much hunting has stirred this land: elite monsters roam here.')
    return out


def al_entrar(ses):
    p = getattr(ses, 'personaje', None)
    if p is None:
        return
    st = getattr(p, 'stage', None)
    iconos(ses)
    cielo(ses, forzar=True)
    if not es_campo(st):
        return
    _VISTO[int(st)] = time.time()
    for l in lineas(st):
        _aviso(ses, l)
    cartel = texto_cartel(st)
    if cartel:
        _cartel(ses, cartel)


def comando(ses):
    for l in lineas(getattr(ses.personaje, 'stage', None)):
        _aviso(ses, l)


# ---------------------------------------------------------------- que se note
# "pero haz que se note" (25/11/2026): el cliente no deja cambiar la lluvia del mapa en vivo, asi que el clima se ve
# con lo que si se puede mandar: (1) un icono propio en la barra de buffs (magic.xml 23420..23428, en el parche via
# cliente_local.MAGIAS_PROPIAS) con el clima, sus efectos y lo que le queda; (2) el cartel que cruza la pantalla al
# entrar y al cambiar; (3) los efectos de los hechizos del juego (Thunder Storm, Icy Storm, Hellfire...) cayendo
# sobre los monstruos que tienes cerca cada pocos segundos.
# EL CIELO DE VERDAD (25/11/2026, "o genera los efectos e implementalos al cliente no??"). Leido en angel.dat con
# capstone: el s2c 0x0015 (manejador 0x5f12e0; el 0x0014 es el 0x5f1230, que escribe los flags en +0x20d0) trae
# [u8 sub] y luego:
#   sub 1: [u8 hora]            -> 0x5b8770: la hora del dia (mod 24) y con ella la luz del mapa
#   sub 2: [u8 codigo][u8 nivel] -> CWeather::Start (0x6846b0) -> Set (0x684770): 0 quita el clima, 1/2/3 lluvia
#          (SF_RainDrop1 / SF_RainDrop / SF_RainDrop2), 4 nieve (SF_SnowBall), 5 petalos (SF_SPetal03/04); nivel
#          1/2/3 = 32/128/256 particulas (con mas de 128 el propio cliente oscurece).
# El 0x0014 de cada carga de mapa lleva clima 0 y hora 0xff (255 % 24 = 15): por eso se manda DESPUES, en al_entrar.
# El jugador que apago "ShowWeather" en las opciones no lo ve (lo mira el cliente).
HORA_NORMAL = 15


def paquetes_cielo(codigo, nivel, hora):
    import struct
    return [struct.pack('<HBBB', 0x0015, 2, int(codigo) & 0xFF, int(nivel) & 0xFF),
            struct.pack('<HBB', 0x0015, 1, int(hora) % 24)]


def cielo_de(stage, ahora=None):
    """(codigo, nivel, hora) que toca pintar en ese mapa ahora."""
    c = clima(stage, ahora)
    if c and c.get('cielo'):
        codigo, nivel, hora = (int(x) for x in c['cielo'])
        # Los codigos 6+ son climas propios que solo entiende el angel.dat nuevo; uno viejo (START.EXE de IGG o sin
        # actualizar) se cierra al recibirlos ("se me esta crasheando en el vps", 26/11/2026). Sin 'cielo_propios'
        # van a su equivalente nativo de 'cielo_nativo' (0 = sin particulas; la luz de la hora se manda igual).
        if codigo > 5 and not config().get('cielo_propios', False):
            codigo = int((config().get('cielo_nativo') or {}).get(str(codigo), 0))
            nivel = nivel if codigo else 0
        return (codigo, nivel, hora)
    return (0, 0, HORA_NORMAL)


def cielo(ses, ahora=None, forzar=False):
    """Manda el clima y la luz del mapa donde esta (solo si cambia, o siempre tras cargar un mapa)."""
    p = getattr(ses, 'personaje', None)
    if p is None:
        return
    try:
        quiero = cielo_de(getattr(p, 'stage', None), ahora)
        tengo = getattr(ses, '_mv_cielo', None)
        if forzar and tengo is None and quiero == (0, 0, HORA_NORMAL):
            return                      # nunca se le mando nada: el 0x0014 del mapa ya lo deja asi
        if forzar or quiero != tengo:
            ses._mv_cielo = quiero
            ses.enviar(*paquetes_cielo(*quiero))
    except Exception:
        log.debug('mundo vivo: cielo', exc_info=True)


def magias_propias():
    """Las filas de magic.xml de los iconos del clima, de lo salvaje y de lo agitado."""
    cfg = config()
    filas = {}

    def fila(mid, icono, nombre, texto):
        filas[int(mid)] = {'編號': str(mid), '介面圖號': str(icono), '名稱': nombre, '對象': '自己',
                           '高權位': str(mid), '低權位': '1', '後置時間': '500', '持續時間': '3600', '公式': '2',
                           '說明': texto, '死亡不消失': '是', '同類無法使用': '是'}
    for c in cfg['climas']:
        if c.get('magia'):
            fila(c['magia'], c['icono'], 'Weather: ' + c['nombre'],
                 '%s here: %s. The weather changes in %%1.' % (c['nombre'], _texto_efectos(c.get('efectos') or {})))
    w = cfg.get('magia_salvaje')
    if w:
        fila(w['magia'], w['icono'], 'Wild Land',
             'Nobody has hunted here for a long time: %s. Hunt here to tame it.' % _texto_efectos(cfg['salvaje']))
    a = cfg.get('magia_agitado')
    if a:
        fila(a['magia'], a['icono'], 'Restless Land',
             'So much hunting has stirred this land: elite monsters roam here, and a local boss may come.')
    return filas


def _paquete_icono(ses, mid, ms):
    import struct
    return struct.pack('<HIBBII', 0x001D, ses.personaje.entity_id, 1, 4, int(mid), int(max(0, ms)))


def iconos_de(stage, ahora=None):
    """{magia: ms} de los iconos que tocan en ese mapa ahora."""
    ahora = ahora or dt.datetime.now()
    cfg = config()
    out = {}
    if not es_campo(stage):
        return out
    c = clima(stage, ahora)
    if c and c.get('magia'):
        fin = ahora.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
        out[int(c['magia'])] = int((fin - ahora).total_seconds() * 1000)
    if salvaje(stage) and cfg.get('magia_salvaje'):
        out[int(cfg['magia_salvaje']['magia'])] = 3600 * 1000
    if (_FASE.get(int(stage)) or {}).get('fase') and cfg.get('magia_agitado'):
        out[int(cfg['magia_agitado']['magia'])] = 1800 * 1000
    return out


def iconos(ses, ahora=None):
    """Pone y quita los iconos de la barra de buffs segun el mapa donde esta (solo manda lo que cambia)."""
    p = getattr(ses, 'personaje', None)
    if p is None or not getattr(p, 'entity_id', None):
        return
    try:
        quiero = iconos_de(getattr(p, 'stage', None), ahora)
        tengo = getattr(ses, '_mv_iconos', None) or {}
        pk = [_paquete_icono(ses, mid, 0) for mid in tengo if mid not in quiero]
        pk += [_paquete_icono(ses, mid, ms) for mid, ms in quiero.items() if mid not in tengo]
        ses._mv_iconos = dict(quiero)
        if pk:
            ses.enviar(*pk)
    except Exception:
        log.debug('mundo vivo: iconos', exc_info=True)


def texto_cartel(stage, ahora=None, cambio=False):
    c = clima(stage, ahora)
    partes = []
    if c and (c.get('efectos') or cambio):
        partes.append('%s in %s%s' % (c['nombre'], nombre_mapa(stage),
                                     (': ' + _texto_efectos(c['efectos'])) if c.get('efectos') else ''))
    if salvaje(stage):
        partes.append('Wild Land: ' + _texto_efectos(config()['salvaje']))
    return ('  |  '.join(partes)) if partes else None


def _cartel(ses, texto):
    try:
        import totem_war
        ses.enviar(totem_war.cartel_deslizante(texto))
    except Exception:
        log.debug('mundo vivo: cartel', exc_info=True)


def _fx_del_mapa(stage, ahora=None):
    """El hechizo del juego cuyo efecto cae sobre los monstruos: el del clima o, si no, el de lo salvaje."""
    if not config().get('fx_monstruos', False):    # "que los mobs no hagan ningun efecto" (25/11/2026)
        return 0
    c = clima(stage, ahora)
    if c and c.get('fx'):
        return int(c['fx'])
    if salvaje(stage) and (config().get('magia_salvaje') or {}).get('fx'):
        return int(config()['magia_salvaje']['fx'])
    return 0


def paquetes_ambiente(ses, stage, monstruos, rng=None, ahora=None):
    """Los efectos de este momento para un jugador: el hechizo del clima sobre monstruos vivos cerca de el."""
    import combate
    rng = rng or random
    mid = _fx_del_mapa(stage, ahora)
    p = getattr(ses, 'personaje', None)
    if not mid or p is None:
        return []
    cfg = config()
    radio = int(cfg.get('fx_radio', 14))
    px, py = int(getattr(p, 'tile_x', 0) or 0), int(getattr(p, 'tile_y', 0) or 0)
    cerca = [m for m in (monstruos or {}).values() if getattr(m, 'vivo', True)
             and abs(int(getattr(m, 'tile_x', 0)) - px) <= radio and abs(int(getattr(m, 'tile_y', 0)) - py) <= radio]
    if not cerca:
        return []
    ef = combate.efecto_de_ataque(mid) or 0
    if not ef:
        return []
    out = []
    for m in rng.sample(cerca, min(len(cerca), int(cfg.get('fx_por_jugador', 2)))):
        out += combate.efecto_magia_self(m.entity_id, ef, mid, cast_time=100)
    return out


def ambiente(ahora=None, rng=None):
    """Un pulso de efectos en todos los mapas de caza con gente."""
    import app
    import presencia
    for st in campos():
        sesiones = presencia._vivas(st)
        if not sesiones or not _fx_del_mapa(st, ahora):
            continue
        sala = app._SALAS_DEL_MUNDO.get(st)
        if sala is None or not sala.monstruos:
            continue
        for s in sesiones:
            try:
                pk = paquetes_ambiente(s, st, sala.monstruos, rng, ahora)
                if pk:
                    (getattr(s, 'enviar_sin_espejo', None) or s.enviar)(*pk)
            except Exception:
                log.debug('mundo vivo: ambiente', exc_info=True)


async def vigilar_ambiente():
    import asyncio
    while True:
        await asyncio.sleep(float(config().get('fx_cada', 5)))
        try:
            ambiente()
        except Exception:
            log.exception('mundo vivo: ambiente')


# ---------------------------------------------------------------- evolucion
def _sala(stage):
    import app
    sala = app._SALAS_DEL_MUNDO.setdefault(stage, app._SalaDelMundo(stage))
    if sala.monstruos is None:
        sala.monstruos = app._monstruos_de(stage)
    return sala


def _generar(stage, npc, refuerzo, marca):
    """Un monstruo del juego (npc) en el mapa, reforzado: {'vida','atk','exp'} multiplicadores."""
    import app
    import combate as cb
    import login as lg
    import santa_clausula as sc
    sala = _sala(stage)
    nombre, sprite = app._monstruo_bd(npc)
    x, y = sc._tile_de_aparicion(stage, sala.monstruos)
    _EID[0] += 1
    m = cb.Monstruo(_EID[0], npc, nombre, [x, y], sprite, stage=stage)
    m.generado = True
    m.spawn_x, m.spawn_y = x, y
    m.hp_max = m.hp = max(1, int(m.hp_max * float(refuerzo.get('vida', 1))))
    m.atk = int(m.atk * float(refuerzo.get('atk', 1)))
    m.matk = int(getattr(m, 'matk', 0) * float(refuerzo.get('atk', 1)))
    m.exp_propia = int(cb.calcular_exp(npc, {}) * float(refuerzo.get('exp', 1)))
    setattr(m, marca, True)
    sala.monstruos[m.entity_id] = m
    pkt = lg._npc_spawn(m.entity_id, npc, nombre, (x, y), sprite=sprite, klass=1)
    for s in list(getattr(sala, 'sesiones', []) or []):
        try:
            s.enviar_inmediato(pkt)
        except Exception:
            pass
    return m


def _quitar(stage, m):
    import combate as cb
    if m is None or not getattr(m, 'vivo', False):
        return
    m.vivo = False
    sala = _sala(stage)
    sala.monstruos.pop(m.entity_id, None)
    for s in list(getattr(sala, 'sesiones', []) or []):
        try:
            s.enviar_inmediato(cb.despawn_monstruo(m.entity_id))
        except Exception:
            pass


def _del_mapa(stage):
    """Los npc_type de los monstruos normales del mapa: (todos, el mas fuerte)."""
    bichos = [m for m in (_sala(stage).monstruos or {}).values()
              if not getattr(m, 'generado', False) and getattr(m, 'hp_max', 0) > 0]
    if not bichos:
        return [], None
    fuerte = max(bichos, key=lambda m: (getattr(m, 'nivel', 0) or 0, m.hp_max))
    return [m.npc_type for m in bichos], fuerte.npc_type


def agitar(stage):
    cfg = config()['evolucion']
    todos, _f = _del_mapa(stage)
    if not todos:
        return 'no monsters in %s' % stage
    elites = [_generar(stage, random.choice(todos), cfg['elite'], 'elite') for _ in range(int(cfg['elites']))]
    _FASE[int(stage)] = {'fase': 'agitado', 'elites': elites}
    _a_los_del_mapa(stage, '[Restless] So much hunting has stirred %s: %d elite monsters appeared! Keep hunting '
                           'and something worse will come...' % (nombre_mapa(stage), len(elites)))
    log.info('mundo vivo: %s agitado', nombre_mapa(stage))
    return 'restless: %d elites' % len(elites)


def sacar_jefe(stage):
    cfg = config()['evolucion']
    _t, fuerte = _del_mapa(stage)
    if fuerte is None:
        return 'no monsters in %s' % stage
    j = _generar(stage, fuerte, cfg['jefe'], 'jefe_local')
    f = _FASE.setdefault(int(stage), {'fase': 'agitado', 'elites': []})
    f.update({'fase': 'jefe', 'jefe': j, 'fin': time.time() + float(cfg['jefe_min']) * 60})
    try:
        import competiciones
        competiciones.anunciar('[Local Boss] The hunters angered %s: %s appeared at (%d, %d)!'
                               % (nombre_mapa(stage), j.nombre, j.tile_x, j.tile_y))
    except Exception:
        _a_los_del_mapa(stage, '[Local Boss] %s appeared at (%d, %d)!' % (j.nombre, j.tile_x, j.tile_y))
    log.info('mundo vivo: jefe local %s en %s', j.nombre, nombre_mapa(stage))
    return 'local boss %s' % j.nombre


def calmar(stage, motivo=''):
    f = _FASE.pop(int(stage), None)
    _MUERTES.pop(int(stage), None)
    if not f:
        return 'calm'
    for e in f.get('elites') or []:
        _quitar(stage, e)
    _quitar(stage, f.get('jefe'))
    if motivo:
        _a_los_del_mapa(stage, '[%s] %s' % (nombre_mapa(stage), motivo))
    return 'calm'


def _premio_jefe(m):
    import app
    import combate
    import jefe_mundo
    filas = jefe_mundo.ranking(m)
    por_cid = {int(s.personaje.char_id): s for s in app._tw_sesiones() if getattr(s, 'personaje', None)}
    tabla = config()['evolucion']['premio_jefe']
    for puesto, (cid, _d) in enumerate(filas, 1):
        s = por_cid.get(cid)
        p = getattr(s, 'personaje', None)
        if p is None:
            continue
        fila = next((f for f in tabla if int(f['desde']) <= puesto <= int(f['hasta'])), None)
        if not fila:
            continue
        try:
            exp = int((combate.exp_para_nivel(p.nivel + 1) - combate.exp_para_nivel(p.nivel)) * float(fila['exp']))
            if exp > 0:
                app._dar_exp_y_creditos(s, exp=exp)
            for it in fila.get('items') or []:
                if random.random() < float(it.get('prob', 1)):
                    app._gm_dar_item(s, int(random.choice(it['de'])), 1)
        except Exception:
            log.exception('mundo vivo: premio del jefe local')
    return filas


def al_matar(ses, m, ahora_ts=None):
    """Cada monstruo muerto en un mapa de caza: lo salvaje, las elites/jefe y el contador de caza."""
    st = getattr(m, 'stage', None)
    if not es_campo(st):
        return
    st = int(st)
    ahora_ts = ahora_ts or time.time()
    if _SALVAJE.get(st, 0) > 0:
        _SALVAJE[st] -= 1
        if _SALVAJE[st] <= 0:
            _SALVAJE.pop(st, None)
            _VISTO[st] = ahora_ts
            _a_los_del_mapa(st, '[%s] The land has been tamed. Thanks, hunters!' % nombre_mapa(st))
    if getattr(m, 'jefe_local', False):
        filas = _premio_jefe(m)
        import app
        nombres = {int(s.personaje.char_id): s.personaje.nombre for s in app._tw_sesiones()
                   if getattr(s, 'personaje', None)}
        top = ', '.join(nombres.get(c, '?') for c, _d in filas[:3])
        calmar(st)
        _a_los_del_mapa(st, '[Local Boss] %s defeated! Top hunters: %s. %s is calm again.'
                        % (m.nombre, top or '-', nombre_mapa(st)))
        return
    if getattr(m, 'generado', False) and not getattr(m, 'elite', False):
        return
    cfg = config()['evolucion']
    q = _MUERTES.setdefault(st, deque())
    q.append(ahora_ts)
    while q and q[0] < ahora_ts - float(cfg['ventana_min']) * 60:
        q.popleft()
    fase = (_FASE.get(st) or {}).get('fase')
    if fase is None and len(q) >= int(cfg['agitado']):
        agitar(st)
    elif fase == 'agitado' and len(q) >= int(cfg['jefe_local']):
        sacar_jefe(st)


# ---------------------------------------------------------------- reloj
def tick(ahora=None):
    ahora = ahora or dt.datetime.now()
    ts = ahora.timestamp()
    _marcar_presencia(ts)
    import presencia
    for st in campos():
        f = _FASE.get(st)
        if f and f.get('fase') == 'jefe' and ts >= f.get('fin', ts + 1):
            calmar(st, 'The local boss went back into hiding.')
        elif f and f.get('fase') == 'agitado' and not _MUERTES.get(st):
            calmar(st)
        c = clima(st, ahora)
        if c and _CLIMA_DICHO.get(st) != (ahora.hour, c['id']):
            previo = _CLIMA_DICHO.get(st)
            _CLIMA_DICHO[st] = (ahora.hour, c['id'])
            if previo is not None and previo[1] != c['id'] and presencia._vivas(st):
                _a_los_del_mapa(st, '[Weather] The weather changes: ' + texto_clima(st, ahora))
                for s in presencia._vivas(st):
                    _cartel(s, 'The weather changes! ' + (texto_cartel(st, ahora, cambio=True) or ''))
        for s in presencia._vivas(st):
            iconos(s, ahora)
            cielo(s, ahora)
        q = _MUERTES.get(st)
        if q:
            while q and q[0] < ts - float(config()['evolucion']['ventana_min']) * 60:
                q.popleft()


async def vigilar(cada=30.0):
    import asyncio
    _leer_estado()
    asyncio.ensure_future(vigilar_ambiente())
    n = 0
    while True:
        await asyncio.sleep(cada)
        try:
            tick()
            n += 1
            if n % 10 == 0:
                _guardar_estado()
        except Exception:
            log.exception('mundo vivo')


def comando_gm(partes, ses=None):
    """GM: /world [restless|boss|calm|wild|tame] [stage] | fx [magic_id]"""
    sub = partes[1].lower() if len(partes) > 1 else 'status'
    st = int(partes[2]) if len(partes) > 2 and str(partes[2]).isdigit() else None
    if sub == 'sky' and ses is not None:          # /world sky <codigo> <nivel> [hora]: probar el cielo a mano
        n = [int(x) for x in partes[2:5] if str(x).isdigit()] + [0, 0, HORA_NORMAL][len(partes[2:5]):]
        ses.enviar(*paquetes_cielo(*n[:3]))
        ses._mv_cielo = tuple(n[:3])
        return 'sky %s' % (n[:3],)
    if sub == 'fx' and ses is not None:
        return 'fx on %d monsters' % fx_gm(ses, partes)
    if sub == 'status' or st is None:
        agit = ['%s:%s' % (s, f.get('fase')) for s, f in _FASE.items()]
        return 'restless %s; wild %s' % (agit or '-', sorted(_SALVAJE) or '-')
    if sub == 'restless':
        return agitar(st)
    if sub == 'boss':
        return sacar_jefe(st)
    if sub == 'calm':
        return calmar(st)
    if sub == 'wild':
        _SALVAJE[st] = int(config()['domar'])
        return 'wild'
    if sub == 'tame':
        _SALVAJE.pop(st, None)
        return 'tamed'
    return 'usage: /world [restless|boss|calm|wild|tame] <stage>'


def fx_gm(ses, partes):
    """GM: /world fx <magic_id>: el efecto de ese hechizo sobre los monstruos cerca (para probar como se ve)."""
    import app
    import combate
    p = ses.personaje
    mid = int(partes[2]) if len(partes) > 2 and str(partes[2]).isdigit() else 8463
    sala = app._SALAS_DEL_MUNDO.get(int(p.stage))
    ef = combate.efecto_de_ataque(mid)
    cerca = [m for m in ((sala.monstruos if sala else None) or {}).values() if getattr(m, 'vivo', True)
             and abs(m.tile_x - p.tile_x) <= 14 and abs(m.tile_y - p.tile_y) <= 14][:5]
    pk = []
    for m in cerca:
        pk += combate.efecto_magia_self(m.entity_id, ef, mid, cast_time=100)
    if pk:
        ses.enviar(*pk)
    return len(cerca)
