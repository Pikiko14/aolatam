"""Puzzles de la instancia oscura (stage 46): sellos y puertas.

La cueva tiene dos puertas invisibles en sus pasillos. Cada una se abre al derrotar a ciertos Guardianes del Sello
(los monstruos de la plantilla con `sello: N`). Mientras esta cerrada, ningun paso, salto ni carga puede cruzar su
zona: el cliente vuelve a la casilla de salida con un aviso. Los datos salen de `plantillas/dark_cavern.json`
(clave `puzzles`, escrita por tools/generar_instancia_oscura.py). El estado vive en la sesion y se reinicia al entrar.
"""
import json
import pathlib
import time

STAGE = 900
_PLANTILLA = pathlib.Path(__file__).parent / 'plantillas' / 'dark_cavern.json'
_CACHE = {}
ENTIDAD_BARRERA = 7551000
_PRUEBA = pathlib.Path(__file__).parent / 'plantillas' / 'instancia_oscura_prueba.json'


def prueba():
    """Interruptores para aislar que cierra el cliente: plantillas/instancia_oscura_prueba.json (si no existe, todo normal).
    sin_cortinas, sin_jefe, sin_elites, max_bichos (cuantos monstruos normales), solo_tipos (lista de npc_type)."""
    try:
        return json.loads(_PRUEBA.read_text(encoding='utf-8')) if _PRUEBA.exists() else {}
    except (OSError, ValueError):
        return {}


def filtrar(bichos, spawns):
    """Quita monstruos segun prueba(); `spawns` es la lista de la plantilla."""
    cfg = prueba()
    if not cfg:
        return bichos
    quitar = set()
    normales = 0
    for e in spawns:
        eid = e['entity_id']
        if e.get('jefe') and cfg.get('sin_jefe'):
            quitar.add(eid)
        elif e.get('elite') and cfg.get('sin_elites'):
            quitar.add(eid)
        elif cfg.get('solo_tipos') and e['npc_type'] not in cfg['solo_tipos']:
            quitar.add(eid)
        elif not e.get('jefe') and not e.get('elite'):
            normales += 1
            if 'max_bichos' in cfg and normales > int(cfg['max_bichos']):
                quitar.add(eid)
    return {k: v for k, v in bichos.items() if k not in quitar}


def datos():
    marca = _PLANTILLA.stat().st_mtime_ns
    if _CACHE.get('marca') != marca:
        _CACHE['marca'] = marca
        _CACHE['datos'] = json.loads(_PLANTILLA.read_text(encoding='utf-8')).get('puzzles') or {}
    return _CACHE['datos']


def _zona(puerta):
    if '_set' not in puerta:
        puerta['_set'] = {tuple(c) for c in puerta['zona']}
    return puerta['_set']


def _eid(puerta, i):
    return ENTIDAD_BARRERA + (ord(puerta['id']) - 65) * 100 + i


def barreras(puerta):
    """Los 0x000E (cortina de luz) de una puerta, uno por casilla del centro del pasillo."""
    import login
    obj = datos().get('objeto_barrera', 60402)
    return [login._map_object_spawn(_eid(puerta, i), obj, tuple(t)) for i, t in enumerate(puerta['barrera'])]


def poblar(stage):
    """Las barreras de las puertas cerradas al cargar el mapa (el estado se reinicia al entrar: todas cerradas)."""
    if stage != STAGE or prueba().get('sin_cortinas'):
        return []
    return [pk for p in datos().get('puertas', []) for pk in barreras(p)]


def reiniciar(ses):
    ses.sellos_oscura = set()
    ses._aviso_puerta_oscura = 0.0


def rotos(ses):
    if getattr(ses, 'sellos_oscura', None) is None:
        reiniciar(ses)
    return ses.sellos_oscura


def puerta_abierta(ses, puerta):
    return set(puerta['requiere']) <= rotos(ses)


def _aviso(ses, texto):
    import clases
    ses.enviar(clases.aviso(texto, tipo=0))


def al_morir(ses, m):
    """Un monstruo cayo: si era un Guardian del Sello, cuenta y avisa."""
    n = getattr(m, 'sello', None)
    if not n or not ses.personaje or ses.personaje.stage != STAGE:
        return
    r = rotos(ses)
    if n in r:
        return
    antes = {p['id'] for p in datos().get('puertas', []) if puerta_abierta(ses, p)}
    r.add(n)
    total = len(datos().get('sellos', []))
    _aviso(ses, 'Seal %d of %d broken.' % (len(r), total))
    for p in datos().get('puertas', []):
        if p['id'] not in antes and puerta_abierta(ses, p):
            import combate
            ses.enviar(*(combate.despawn_monstruo(_eid(p, i)) for i in range(len(p['barrera']))))
            _aviso(ses, 'The sealing power fades. The way %s is open.' % p.get('nombre', 'ahead'))


def bloquear_paso(ses, desde, hasta):
    """True si ir de `desde` a `hasta` cruza una puerta cerrada."""
    import app
    if not ses.personaje or ses.personaje.stage != STAGE:
        return False
    cerradas = [p for p in datos().get('puertas', []) if not puerta_abierta(ses, p)]
    if not cerradas:
        return False
    cruzadas = set(app._casillas_del_tramo(desde, hasta))
    for p in cerradas:
        if cruzadas & _zona(p):
            ahora = time.time()
            if ahora - getattr(ses, '_aviso_puerta_oscura', 0.0) > 3:
                ses._aviso_puerta_oscura = ahora
                faltan = sorted(set(p['requiere']) - rotos(ses))
                _aviso(ses, 'A sealing force blocks the way. Defeat the Seal Guardians (%d left).' % len(faltan))
            return True
    return False


# TICKETS DEL JEFE: el Dragonkin Moowad (el spawn con "jefe" de la plantilla) suelta de 2 a 5 tickets al azar de los
# cuatro tipos que se canjean en Event Overview > Exchange > Enhanced Pestle and Ride Feed (grupo 595 de
# exchange.xml, tools/canje_straw.py). Pedido del usuario el 31/10/2026.
TICKETS = (20228, 20229, 20230, 20231)   # Lucky Enhanced Pestle / Ride / Piercing Hammer / Lucky Hammer Ticket
TICKETS_DEL_JEFE = (2, 5)


def _tipos_jefe():
    marca = _PLANTILLA.stat().st_mtime_ns
    if _CACHE.get('jefes_marca') != marca:
        spawns = json.loads(_PLANTILLA.read_text(encoding='utf-8')).get('spawns') or []
        _CACHE['jefes'] = {int(e['npc_type']) for e in spawns if e.get('jefe') and e.get('npc_type')}
        _CACHE['jefes_marca'] = marca
    return _CACHE['jefes']


def tickets_del_jefe(stage, m):
    """[(ticket, cantidad)] si `m` es el jefe de la instancia; [] si no."""
    import random
    if int(stage or 0) != STAGE or int(getattr(m, 'npc_type', 0) or 0) not in _tipos_jefe():
        return []
    cuantos = random.randint(*TICKETS_DEL_JEFE)
    salen = {}
    for _ in range(cuantos):
        t = random.choice(TICKETS)
        salen[t] = salen.get(t, 0) + 1
    return sorted(salen.items())
