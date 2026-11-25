"""El torneo de mascotas (25/11/2026): "las mascotas del jugador luchan solas, como un autobattler, y el dueno solo elige
la estrategia" (plantillas/mecanicas.json "torneo").

* Inscripcion (pestana Pet Tournament de Challenges): la mascota mas fuerte del jugador (nivel y stats reales,
  mascotas.totales) con una estrategia: Aggressive, Defensive o Tricky. Se puede cambiar hasta que empieza.
* A las horas del calendario semanal (evento 'torneo') se juega: eliminacion directa (con pase libre si son impares).
  Cada combate se simula por turnos: actua primero la mas rapida; dano = ataque x K / (defensa + K), +-15 %, criticos y
  esquivas segun la estrategia; la que gana el piedra-papel-tijera de estrategias pega un 'ventaja' % mas.
* Al acabar: cartel con el podio, premios por puesto ('premios') y la pestana ensena el cuadro y tus combates.
"""
import datetime as dt
import json
import logging
import pathlib
import random

import sociales

log = logging.getLogger('torneo_mascotas')

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'mecanicas.json'
K = 60.0
INSCRITOS = {}        # char_id -> {'estrategia', 'nombre'}
ULTIMO = {'lineas': [], 'combates': {}, 'podio': []}
_HECHAS = set()


def cfg():
    return json.loads(RUTA.read_text('utf-8'))['torneo']


def mascota_de(ses):
    """La mascota mas fuerte del jugador: (ficha, stats) o (None, None)."""
    import mascotas
    p = getattr(ses, 'personaje', None)
    fichas = [f for f in (getattr(p, 'mascotas', None) or {}).values() if isinstance(f, dict) and f.get('nivel')]
    if not fichas:
        return None, None
    mejor = max(fichas, key=lambda f: (int(f.get('nivel') or 0), sum(mascotas.totales(f).values())))
    return mejor, mascotas.totales(mejor)


def luchador(nombre_dueno, ficha, stats, estrategia):
    e = cfg()['estrategias'][estrategia]
    nivel = int(ficha.get('nivel') or 1)
    hp = max(50, int(stats.get('hp') or 100)) * (100 + e['hp']) / 100.0
    atk = max(10, max(int(stats.get('atk') or 0), int(stats.get('matk') or 0)) + nivel * 2) * (100 + e['atk']) / 100.0
    df = max(5, (int(stats.get('dfs') or 0) + int(stats.get('mdef') or 0)) / 2.0 + nivel) * (100 + e['def']) / 100.0
    vel = max(1, int(stats.get('agilidad') or 0) + nivel) * (100 + e['vel']) / 100.0
    return {'dueno': nombre_dueno, 'nombre': str(ficha.get('nombre') or 'Pet'), 'nivel': nivel, 'hp': hp,
            'atk': atk, 'def': df, 'vel': vel, 'crit': e['crit'], 'esquiva': e['esquiva'], 'estrategia': estrategia}


def combate(a, b, rng=None):
    """(ganador, perdedor, lineas) de un combate simulado."""
    c = cfg()
    rng = rng or random
    vida = {id(a): a['hp'], id(b): b['hp']}
    ventaja = {id(a): 1.0, id(b): 1.0}
    if c['gana_a'].get(a['estrategia']) == b['estrategia']:
        ventaja[id(a)] = 1 + c['ventaja'] / 100.0
    elif c['gana_a'].get(b['estrategia']) == a['estrategia']:
        ventaja[id(b)] = 1 + c['ventaja'] / 100.0
    lineas = ['%s (%s, Lv%d, %s) vs %s (%s, Lv%d, %s)' % (
        a['nombre'], a['dueno'], a['nivel'], c['estrategias'][a['estrategia']]['nombre'],
        b['nombre'], b['dueno'], b['nivel'], c['estrategias'][b['estrategia']]['nombre'])]
    orden = sorted((a, b), key=lambda x: (-x['vel'], rng.random()))
    for turno in range(1, int(c['turnos_max']) + 1):
        for yo in orden:
            otro = b if yo is a else a
            if rng.random() * 100 < otro['esquiva']:
                continue
            dano = yo['atk'] * K / (otro['def'] + K) * rng.uniform(0.85, 1.15) * ventaja[id(yo)]
            if rng.random() * 100 < yo['crit']:
                dano *= 1.5
            vida[id(otro)] -= max(1.0, dano)
            if vida[id(otro)] <= 0:
                lineas.append('%s wins in %d turns with %d%% HP left.' % (
                    yo['nombre'], turno, max(1, int(100 * vida[id(yo)] / yo['hp']))))
                return yo, otro, lineas
    gana = a if vida[id(a)] / a['hp'] >= vida[id(b)] / b['hp'] else b
    lineas.append('%s wins on points after %d turns.' % (gana['nombre'], int(c['turnos_max'])))
    return gana, (b if gana is a else a), lineas


def inscribir(ses, estrategia):
    if estrategia not in cfg()['estrategias']:
        return 'Pick a strategy.'
    ficha, _st = mascota_de(ses)
    if ficha is None:
        return 'You need a pet to enter the tournament.'
    INSCRITOS[int(ses.personaje.char_id)] = {'estrategia': estrategia, 'nombre': ses.personaje.nombre}
    return '%s is signed up with the %s strategy.' % (ficha.get('nombre') or 'Your pet',
                                                       cfg()['estrategias'][estrategia]['nombre'])


def retirar(ses):
    return 'You left the tournament.' if INSCRITOS.pop(int(ses.personaje.char_id), None) else 'You were not signed up.'


def jugar(rng=None):
    """Juega el torneo con los inscritos conectados. Devuelve el podio [nombre dueno]."""
    rng = rng or random
    gente = []
    for cid, ins in list(INSCRITOS.items()):
        s = sociales.por_cid(cid)
        ficha, st = mascota_de(s) if s else (None, None)
        if ficha is not None:
            gente.append((s, luchador(s.personaje.nombre, ficha, st, ins['estrategia'])))
    INSCRITOS.clear()
    if len(gente) < 2:
        sociales.cartel('[Pet Tournament] Not enough pets signed up. Next time!')
        return []
    rng.shuffle(gente)
    lineas, combates = [], {}
    ronda, eliminados = 1, []
    vivos = gente
    while len(vivos) > 1:
        siguientes = []
        if len(vivos) % 2:
            siguientes.append(vivos.pop())                       # pase libre
        for i in range(0, len(vivos), 2):
            (sa, la), (sb, lb) = vivos[i], vivos[i + 1]
            g, p, log_ = combate(la, lb, rng)
            ganador = (sa, la) if g is la else (sb, lb)
            perdedor = (sb, lb) if g is la else (sa, la)
            siguientes.append(ganador)
            eliminados.append((ronda, perdedor))
            texto = 'Round %d: %s beat %s.' % (ronda, g['nombre'] + ' (' + g['dueno'] + ')',
                                              p['nombre'] + ' (' + p['dueno'] + ')')
            lineas.append(texto)
            for s, _l in (vivos[i], vivos[i + 1]):
                combates.setdefault(int(s.personaje.char_id), []).extend(['Round %d: ' % ronda + l for l in log_])
        vivos = siguientes
        ronda += 1
    campeon = vivos[0]
    orden = [campeon] + [x[1] for x in sorted(eliminados, key=lambda e: -e[0])]
    podio = [s.personaje.nombre for s, _l in orden]
    for puesto, (s, _l) in enumerate(orden, 1):
        premio = next(p for p in cfg()['premios'] if puesto <= p['puesto'])
        texto = sociales.premiar(s, premio)
        sociales.aviso(s, '[Pet Tournament] You finished #%d. Reward: %s.' % (puesto, texto))
    ULTIMO.update({'lineas': lineas, 'combates': combates, 'podio': podio})
    sociales.cartel('[Pet Tournament] Champion: %s and %s! %s' % (
        campeon[1]['nombre'], podio[0], ('Runner-up: %s.' % podio[1]) if len(podio) > 1 else ''))
    return podio


def toca(ahora):
    import calendario
    for wd, h in (calendario.slots('torneo') or []):
        if wd != ahora.weekday():
            continue
        hh, mm = (int(x) for x in h.split(':'))
        ini = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if ini <= ahora < ini + dt.timedelta(minutes=5):
            return '%s %s' % (ini.date().isoformat(), h)
    return None


def tick(ahora=None):
    ahora = ahora or dt.datetime.now()
    clave = toca(ahora)
    if clave and clave not in _HECHAS:
        _HECHAS.add(clave)
        jugar()
