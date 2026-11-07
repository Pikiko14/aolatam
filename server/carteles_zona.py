"""Carteles con los bichos de cada zona del mapa (06/11/2026).

"el nombre de los mobs en la zona donde esta para saber que mobs hay en que zonas": un tablon de anuncios del propio
cliente (npc.obd 40702, 告示欄02-1: \\stage\\24\\24-015-1U0) en el centro de cada grupo de bichos, con su nombre y
nivel encima ("Slarm Lv5"). Sale en el mundo y en el mapa (Alt+M), como cualquier NPC.

Un cartel por clase de bicho y zona: los spawns de la plantilla del mapa se agrupan por clase y, dentro de ella, por
cercania (DISTANCIA_GRUPO casillas). Las instancias y los mapas de eventos no llevan carteles.
"""
import json
import logging
import pathlib

log = logging.getLogger('carteles_zona')

# Primero se uso el tablon 40702 y se veia el edificio entero ("pero que no se vea eso", 06/11/2026). El 40442
# (日版新手教學圖片頭像) es el unico objeto de npc.obd sin ninguna animacion: sin dibujo, solo queda el nombre.
SPRITE = 40442
NPC_TYPE = 1                  # sin ficha propia en npc.xml
# 199 = NPC. Con 200 (el de las mascotas) el clic abria "Set Deal Password or not?".
KLASS = 199
# Un objeto sin animaciones podria tumbar al cliente: hasta comprobarlo, solo lo ven los GM (marcas_npc lo filtra).
SOLO_GM = True
# APAGADO (06/11/2026): con el 40442 el cliente se cierra al entrar al mapa ("This program will be terminated
# because an error occur", en el Angel Lyceum con Zetha). Sin un sprite invisible que aguante, no se mandan.
ACTIVOS = False
EID_BASE = 7_000_000          # + stage * 1000 + n
DISTANCIA_GRUPO = 40
LARGO_NOMBRE = 16
PLANTILLAS = pathlib.Path(__file__).parent / 'plantillas'

_CACHE = {}


def _grupos(puntos):
    """Agrupa casillas que esten a menos de DISTANCIA_GRUPO de alguna del grupo."""
    grupos = []
    for x, y in puntos:
        cerca = [g for g in grupos if any(max(abs(x - a), abs(y - b)) <= DISTANCIA_GRUPO for a, b in g)]
        nuevo = [(x, y)]
        for g in cerca:
            nuevo += g
            grupos.remove(g)
        grupos.append(nuevo)
    return grupos


_NIVELES = None


def _nivel(npc_type):
    """El nivel del monstruo segun content.db (la plantilla a veces no lo trae o trae otro)."""
    global _NIVELES
    if _NIVELES is None:
        import sqlite3
        _NIVELES = {}
        try:
            con = sqlite3.connect(PLANTILLAS.parent.parent / 'corpus' / 'content.db')
            for mid, lv in con.execute('select id, level from monster'):
                try:
                    _NIVELES[int(mid)] = int(lv)
                except (TypeError, ValueError):
                    pass
            con.close()
        except Exception:
            log.exception('niveles de monster')
    return _NIVELES.get(int(npc_type or 0), 0)


def _texto(nombre, niveles):
    niveles = [n for n in niveles if n > 0] or [0]
    lo, hi = min(niveles), max(niveles)
    nv = '' if not hi else (('Lv%d' % lo) if lo == hi else ('Lv%d-%d' % (lo, hi)))
    if not nv:
        return str(nombre).strip()[:LARGO_NOMBRE]
    nombre = str(nombre).strip()
    sitio = LARGO_NOMBRE - len(nv) - 1
    return ('%s %s' % (nombre[:max(1, sitio)], nv))[:LARGO_NOMBRE]


def carteles(stage):
    """[(entity_id, texto, (x, y))] de ese mapa."""
    stage = int(stage)
    if stage in _CACHE:
        return _CACHE[stage]
    res = []
    try:
        import app
        if app.es_instancia(stage) or stage in __import__('daily_events').STAGES:
            _CACHE[stage] = res
            return res
        nombre = app.mapas_poblados().get(stage)
        f = PLANTILLAS / nombre if nombre else None
        if f and f.exists():
            spawns = [e for e in json.loads(f.read_text(encoding='utf-8')).get('spawns', [])
                      if e.get('monstruo') and not e.get('apagado') and e.get('tile')]
            por_clase = {}
            for e in spawns:
                por_clase.setdefault((e['npc_type'], e.get('nombre') or '?'), []).append(e)
            n = 0
            for (_tipo, nom), lista in sorted(por_clase.items(), key=lambda kv: kv[0][1]):
                niveles = [_nivel(_tipo) or int(e.get('nivel') or 0) for e in lista]
                for g in _grupos([tuple(e['tile'][:2]) for e in lista]):
                    cx = round(sum(p[0] for p in g) / len(g))
                    cy = round(sum(p[1] for p in g) / len(g))
                    res.append((EID_BASE + stage * 1000 + n, _texto(nom, niveles), (cx, cy)))
                    n += 1
    except Exception:
        log.exception('carteles del stage %s', stage)
    _CACHE[stage] = res
    return res


def poblar(stage):
    """Los 0x0008 de los carteles del mapa (login.poblar)."""
    if not ACTIVOS:
        return []
    import login
    return [login._npc_spawn(eid, NPC_TYPE, texto, tile, sprite=SPRITE, klass=KLASS, direccion=6)
            for eid, texto, tile in carteles(stage)]


def es_cartel(entidad) -> bool:
    return EID_BASE <= int(entidad or 0) < EID_BASE + 1_000_000
