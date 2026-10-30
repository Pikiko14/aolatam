"""Puzzles de la instancia oscura (stage 46): sellos y puertas.

La cueva tiene dos puertas invisibles en sus pasillos. Cada una se abre al derrotar a ciertos Guardianes del Sello
(los monstruos de la plantilla con `sello: N`). Mientras esta cerrada, ningun paso, salto ni carga puede cruzar su
zona: el cliente vuelve a la casilla de salida con un aviso. Los datos salen de `plantillas/training_cave_big.json`
(clave `puzzles`, escrita por tools/generar_instancia_oscura.py). El estado vive en la sesion y se reinicia al entrar.
"""
import json
import pathlib
import time

STAGE = 46
_PLANTILLA = pathlib.Path(__file__).parent / 'plantillas' / 'training_cave_big.json'
_CACHE = {}
ENTIDAD_BARRERA = 7551000


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
    if stage != STAGE:
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
